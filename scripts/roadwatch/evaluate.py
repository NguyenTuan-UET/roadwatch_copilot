"""Evaluate BT-A (auto-calibration + supercombo) against ground truth (spec 5.7). Writes a Markdown report.

    python -m scripts.roadwatch.evaluate --videos ../test_videos --calib ../third_party/calib_challenge \
        --out eval/results/bt_a_eval.md

Ground truth used:
  * comma calib_challenge 0-9 (1164x874, 20 fps, fy 910): fy; per-frame pitch/yaw labels for 0-4.
  * comma2k19 Example_1 (same camera): CAN radar tracks (lead distance), CAN speed (ego speed).
Radar origin is the front of the car; openpilot puts the camera RADAR_TO_CAMERA = 1.52 m behind it.
"""
import argparse
import time
from pathlib import Path

import numpy as np

from src.roadwatch.calibration import learn_fy
from src.roadwatch.model import Supercombo, decode
from src.roadwatch.pipeline import Pipeline

W, H, FY_TRUE, HZ = 1164, 874, 910.0, 20
RADAR_TO_CAMERA = 1.52
LANE_HALF_M = 1.5
BINS = [(0, 20), (20, 40), (40, 60), (60, 200)]


def run(model, frames, fy, d_bumper=0.0):
    pipe, rows, ms = Pipeline(W, H, fy, d_bumper, model), [], []
    for y, u, v in frames:
        t = time.perf_counter()
        r = pipe.step(y, u, v)
        ms.append(1000 * (time.perf_counter() - t))
        x, ly, vl, _ = r.outputs['lead'][0, 0, 0]
        rows.append(dict(status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height=r.height_m, ego=r.ego_speed_mps,
                         prob=r.lead_prob, x=float(x), y=float(ly), v=float(vl), ttc=r.ttc_s,
                         lanes=float(r.outputs['lane_lines_prob'][0, 1::2][1:3].min())))
    return rows, ms, pipe


def learn(model, frames):
    try:
        return learn_fy(frames[100:300], W, H, model)[0]
    except ValueError:
        return None


def calibration_eval(model, calib_dir, lines):
    lines += ['## 1. Hiệu chuẩn (comma calib_challenge)', '',
              '| Video | `fy` học được (thật 910) | Sai số `fy` | Pitch MAE (mrad) | Yaw MAE (mrad) | Hội tụ (s) |',
              '|---|---|---|---|---|---|']
    fy_err = []
    for i in range(10):
        split = 'labeled' if i < 5 else 'unlabeled'
        frames = list(decode(calib_dir / split / f'{i}.hevc', W, H, fps=HZ))
        fy = learn(model, frames)
        if fy is None:
            lines.append(f'| {i} | không học được (xe chậm) | — | — | — | — |')
            continue
        fy_err.append(fy / FY_TRUE - 1)
        rows, _, _ = run(model, frames, fy)
        conv = next((k / HZ for k, r in enumerate(rows) if r['status'] == 'calibrated'), None)
        if i < 5:
            gt = np.loadtxt(calib_dir / split / f'{i}.txt')
            pred = np.array([[r['pitch'], r['yaw']] for r in rows])
            ok = np.isfinite(gt).all(1) & np.array([r['status'] == 'calibrated' for r in rows])
            mae = (1000 * np.abs(pred[ok] - gt[ok]).mean(0)).round(2) if ok.any() else ['—', '—']
        else:
            mae = ['—', '—']
        lines.append(f'| {i} | {fy:.0f} | {100 * (fy / FY_TRUE - 1):+.1f}% | {mae[0]} | {mae[1]} | '
                     f'{"—" if conv is None else f"{conv:.1f}"} |')
    if fy_err:
        lines += ['', f'Sai số `fy`: trung bình tuyệt đối {100 * np.mean(np.abs(fy_err)):.1f}%, '
                      f'lớn nhất {100 * np.max(np.abs(fy_err)):.1f}% trên {len(fy_err)} video. '
                      'Pitch/yaw tính trên khung đã `calibrated` và có nhãn.', '']


def radar_lead(logs, t):
    """Closest in-lane radar track per frame time: (distance from car front, lateral left) or None."""
    rt, rv = np.load(logs / 'processed_log_CAN_radar_t'), np.load(logs / 'processed_log_CAN_radar_value')
    out = []
    for tk in t:
        near = rv[np.abs(rt - tk) < 0.05]
        near = near[np.isfinite(near[:, 0]) & (np.abs(near[:, 1]) < LANE_HALF_M) & (near[:, 0] > 0)]
        out.append(tuple(near[np.argmin(near[:, 0]), :2]) if len(near) else None)
    return out


def distance_eval(model, video, logs, lines):
    frames = list(decode(video, W, H, fps=HZ))
    fy = learn(model, frames) or FY_TRUE
    t = np.load(logs / 'global_pose_frame_times')[:len(frames)]
    st, sv = np.load(logs / 'processed_log_CAN_speed_t'), np.load(logs / 'processed_log_CAN_speed_value').ravel()
    can_speed = np.interp(t, st, sv)
    radar = radar_lead(logs, t)
    rows, ms, _ = run(model, frames, fy)

    ego = np.array([r['ego'] for r in rows])
    cal = np.array([r['status'] == 'calibrated' for r in rows])
    lines += ['## 2. Khoảng cách và tốc độ (comma2k19 Example_1, radar + CAN)', '',
              f'`fy` học được: {fy:.0f} px (thật 910). Khung đã `calibrated`: {cal.mean():.0%}.', '',
              f'- **Tốc độ xe mình** (model so với CAN, khung đã hiệu chuẩn): MAE '
              f'{3.6 * np.abs(ego - can_speed)[cal].mean():.1f} km/h, tốc độ CAN trung bình {3.6 * can_speed.mean():.0f} km/h.']

    has_gt = np.array([g is not None for g in radar])
    vis = np.array([r['prob'] >= 0.5 for r in rows])
    both = has_gt & vis & cal
    gx = np.array([g[0] if g else np.nan for g in radar])
    gy = np.array([g[1] if g else np.nan for g in radar])
    vx = np.array([r['x'] for r in rows]) - RADAR_TO_CAMERA
    vy = -np.array([r['y'] for r in rows])                      # model: right positive; radar: left positive
    same = both & (np.abs(vx - gx) < np.maximum(5, 0.25 * gx)) & (np.abs(vy - gy) < 1.5)
    lines += [f'- **Phát hiện xe trước** (khung đã hiệu chuẩn): radar có xe trong làn ở {has_gt[cal].mean():.0%} '
              f'khung; model báo xe (p ≥ 0,5) ở {vis[cal].mean():.0%}. Khi cả hai cùng có, cùng một xe '
              f'(lệch < max(5 m, 25%) và < 1,5 m ngang) ở {same[both].mean():.0%} khung.' if both.any() else
              '- Không có khung nào radar và model cùng thấy xe.',
              f'- Radar có xe nhưng model không báo: {(has_gt & ~vis & cal).sum()} khung; '
              f'model báo nhưng radar không có xe trong làn: {(~has_gt & vis & cal).sum()} khung.', '',
              '| Dải radar (m) | Số khung | Sai số trung bình (m) | MAE (m) | MAE (%) |', '|---|---|---|---|---|']
    for lo, hi in BINS:
        m = same & (gx >= lo) & (gx < hi)
        if m.any():
            e = vx[m] - gx[m]
            lines.append(f'| {lo}–{hi if hi < 200 else "…"} | {m.sum()} | {e.mean():+.2f} | {np.abs(e).mean():.2f} | '
                         f'{100 * np.mean(np.abs(e) / gx[m]):.1f} |')
        else:
            lines.append(f'| {lo}–{hi if hi < 200 else "…"} | 0 | chưa kiểm chứng | | |')
    lines += ['', 'Sai số tính trên các khung mà model và radar chọn cùng một xe; khung chọn khác xe được đếm riêng ở trên. '
              'Gốc tọa độ: khoảng cách model − 1,52 m (camera sau radar) so với khoảng cách radar.', '']
    return frames, fy, ms


def ttc_scale_eval(model, frames, fy, lines):
    lines += ['## 3. TTC khi `fy` sai (OQ-A16)', '',
              '| `fy` dùng | Khoảng cách trung vị so với `fy` đúng | TTC: sai khác trung vị | Khung có TTC ở cả hai |',
              '|---|---|---|---|']
    base, _, _ = run(model, frames, fy)
    for k in (0.8, 1.2):
        rows, _, _ = run(model, frames, fy * k)
        both = [(a, b) for a, b in zip(base, rows) if a['prob'] >= .5 and b['prob'] >= .5]
        dx = np.median([b['x'] / a['x'] for a, b in both]) if both else np.nan
        tt = [(a['ttc'], b['ttc']) for a, b in zip(base, rows) if a['ttc'] and b['ttc']]
        dt = f'{100 * np.median([abs(b / a - 1) for a, b in tt]):.1f}%' if tt else '—'
        lines.append(f'| {k:.1f} × ({fy * k:.0f}) | {100 * (dx - 1):+.1f}% | {dt} | {len(tt)} |')
    lines += ['', 'Pipeline chỉ báo TTC khi hai xe áp sát và TTC < 10 s, nên số khung có TTC có thể ít.', '']


def remount_eval(model, calib_dir, lines):
    frames = list(decode(calib_dir / 'labeled/0.hevc', W, H, fps=HZ)) + list(decode(calib_dir / 'labeled/1.hevc', W, H, fps=HZ))
    gt = np.vstack([np.loadtxt(calib_dir / 'labeled/0.txt'), np.loadtxt(calib_dir / 'labeled/1.txt')])
    rows, _, pipe = run(model, frames, FY_TRUE)
    change = 1200
    detect = next((k for k in range(change, len(rows)) if rows[k]['status'].startswith('calibrating')), None)
    again = next((k for k in range(detect or change, len(rows)) if rows[k]['status'] == 'calibrated'), None)
    tail = np.array([[r['pitch'], r['yaw']] for r in rows[-200:]]) - gt[-200:]
    lines += ['## 4. Phát hiện lắp lại camera (video 0 rồi video 1)', '',
              f'- Phát hiện sau {(detect - change) / HZ:.1f} s; hiệu chuẩn lại xong sau {(again - change) / HZ:.1f} s; '
              f'{pipe.cal.resets} lần reset.' if detect and again else '- Không phát hiện được thay đổi.',
              f'- Pitch/yaw 10 s cuối: MAE {1000 * np.abs(tail[:, 0]).mean():.1f} / {1000 * np.abs(tail[:, 1]).mean():.1f} mrad.', '']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', type=Path, required=True)
    ap.add_argument('--calib', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path('eval/results/bt_a_eval.md'))
    a = ap.parse_args()
    model, lines, t0 = Supercombo(), [], time.perf_counter()
    calibration_eval(model, a.calib, lines)
    frames, fy, ms = distance_eval(model, a.videos / 'c2k19_example.mp4', a.videos / 'c2k19_example_logs', lines)
    ttc_scale_eval(model, frames, fy, lines)
    remount_eval(model, a.calib, lines)
    lines += ['## 5. Hiệu năng', '', f'Warp + model + giải mã đầu ra + hiệu chuẩn: trung vị {np.median(ms):.1f} ms/khung, '
              f'P95 {np.percentile(ms, 95):.1f} ms (ONNX Runtime CPU, 4 thread). Tổng thời gian đánh giá '
              f'{(time.perf_counter() - t0) / 60:.0f} phút.', '']
    head = ['# Đánh giá BT-A: hiệu chuẩn tự động + supercombo', '',
            f'Sinh bởi `python -m scripts.roadwatch.evaluate` ngày {time.strftime("%d/%m/%Y")}. Model SHA-256 '
            '`65a08adc…`. Dữ liệu: comma calib_challenge, comma2k19 Example_1 (không phải dữ liệu Việt Nam).', '']
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text('\n'.join(head + lines))
    print('\n'.join(head + lines))


if __name__ == '__main__':
    main()
