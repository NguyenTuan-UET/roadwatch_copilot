"""Ablation of the temporal distance model (src/roadwatch/temporal.py) against the comma2k19 radar.

    python -m scripts.roadwatch.eval_temporal --data data/comma2k19 --out eval/results/temporal_eval.md

Per segment the model runs once on the real frames and its outputs are recorded; the pipeline is then run twice on
the same recorded outputs, temporal=False (Kalman distance only) and temporal=True, so the only difference is the
temporal model. Camera angles come from lab.estimate_calibration (as the lab page). Ground truth: the radar track
within +-1.6 m (lab.radar_reference), camera -> radar offset 1.52 m (the Pipeline's d_cam_bumper).
"""
import argparse
import pickle
import time
from pathlib import Path

import numpy as np

from src.roadwatch.lab import (
    CALIB_FRAMES,
    FPS,
    RADAR_TO_CAMERA,
    WARMUP,
    SpeedLog,
    estimate_calibration,
    radar_reference,
)
from src.roadwatch.model import Gr14VinAI, decode, video_size
from src.roadwatch.pipeline import PREDICT_S, Pipeline
from src.roadwatch.temporal import RAMP_SAMPLES, WINDOW_S

FY = 910.0
BINS = [(0, 20), (20, 40), (40, 60), (60, 200)]


class Recorder:
    """Wraps the model: records every output on the first pass, replays them on the next ones."""

    def __init__(self, model):
        self.model, self.outs, self.k, self.replay = model, [], 0, False   # replay: serve self.outs

    def reset(self):
        self.k = 0
        if not self.replay:
            self.model.reset()

    def step(self, img):
        if self.replay:
            self.k += 1
            return self.outs[self.k - 1]
        out = self.model.step(img)
        self.outs.append(out)
        return out


def replay_pipeline(rec, frames_n, w, h, rpy, rpy_est, speed, temporal):
    pipe = Pipeline(w, h, FY, RADAR_TO_CAMERA, rec, v_ref=speed, wide='dup', rpy=rpy, rpy_est=rpy_est, temporal=temporal)
    gap, pred = np.full(frames_n, np.nan), np.full(frames_n, np.nan)
    blank = np.zeros((h, w), np.uint8), np.zeros((h // 2, w // 2), np.uint8), np.zeros((h // 2, w // 2), np.uint8)
    for i in range(frames_n):
        r = pipe.step(*blank, i / FPS)
        if i >= WARMUP:
            gap[i] = np.nan if r.gap_m is None else r.gap_m
            pred[i] = np.nan if r.gap_pred_m is None else r.gap_pred_m
    return gap, pred


def stats(err, gap, truth):
    """err is NaN outside the frames evaluated; jitter only uses consecutive pairs of evaluated frames."""
    ok = np.isfinite(err)
    if not ok.any():
        return dict(n=0)
    e = err[ok]
    d = np.diff(gap)[ok[1:] & ok[:-1]]
    return dict(n=int(ok.sum()), bias=float(e.mean()), mae=float(np.abs(e).mean()), rmse=float(np.sqrt((e ** 2).mean())),
                p90=float(np.percentile(np.abs(e), 90)), mape=float(100 * np.mean(np.abs(e) / truth[ok])),
                jitter=float(d.std()) if len(d) else np.nan)


def record(seg, model, cache):
    """Calibration pre-pass + the model on every frame -> (outputs, rpy, rpy_est, size); cached as a pickle."""
    f = cache / f'{seg.name}.pkl' if cache else None
    if f and f.exists():
        return pickle.loads(f.read_bytes())
    w, h = video_size(seg / 'video.mp4')
    n = len(radar_reference(seg))
    rpy, rpy_est = estimate_calibration(seg / 'video.mp4', w, h, FY, model, 'dup', min(CALIB_FRAMES, n))
    rec = Recorder(model)
    pipe = Pipeline(w, h, FY, RADAR_TO_CAMERA, rec, wide='dup', rpy=rpy, rpy_est=rpy_est)   # gives the model its warps
    for i, (y, u, v) in enumerate(decode(seg / 'video.mp4', w, h, fps=FPS)):
        if i >= n:
            break
        pipe.step(y, u, v, i / FPS)
    out = dict(outs=rec.outs, rpy=rpy, rpy_est=rpy_est, w=w, h=h)
    if f:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(pickle.dumps(out))
    return out


def evaluate(seg, model, cache=None):
    radar = radar_reference(seg)
    rec_d = record(seg, model, cache)
    rec = Recorder(None)
    rec.outs, rec.replay = rec_d['outs'], True
    n = min(len(radar), len(rec.outs))
    speed = SpeedLog(seg) if (seg / 'processed_log/CAN/speed/t').exists() else None
    args = rec, n, rec_d['w'], rec_d['h'], rec_d['rpy'], rec_d['rpy_est'], speed
    base, _ = replay_pipeline(*args, False)
    gap_t, pred_t = replay_pipeline(*args, True)
    return base, gap_t, pred_t, radar[:n], n   # radar origin is the car front, like the Pipeline's gap (bumper = 1.52 m)


def fmt(s):
    if not s.get('n'):
        return '| 0 | | | | | | |'
    return (f"| {s['n']} | {s['bias']:+.2f} | {s['mae']:.2f} | {s['rmse']:.2f} | {s['p90']:.2f} | {s['mape']:.1f} | "
            f"{s['jitter']:.3f} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=Path('data/comma2k19'))
    ap.add_argument('--out', type=Path, default=Path('eval/results/temporal_eval.md'))
    ap.add_argument('--cache', type=Path, help='keep the recorded model outputs here (re-runs skip the model)')
    ap.add_argument('--segments', nargs='*', help='segment folder names (default: all with radar)')
    a = ap.parse_args()
    segs = [p for p in sorted(a.data.iterdir()) if (p / 'video.mp4').exists() and (p / 'processed_log/CAN/radar/t').exists()
            and (not a.segments or p.name in a.segments)]
    model, t0 = (Gr14VinAI() if not a.cache or not all((a.cache / f'{p.name}.pkl').exists() for p in segs) else None,
                 time.perf_counter())
    hdr = '| Khung | Sai số TB (m) | MAE (m) | RMSE (m) | P90 \\|sai số\\| (m) | MAPE (%) | Độ rung (m/khung) |'
    sep = '|---|---|---|---|---|---|---|'
    lines = ['# Đánh giá Temporal Modeling cho khoảng cách (comma2k19)', '',
             f'Sinh bởi `python -m scripts.roadwatch.eval_temporal` ngày {time.strftime("%d/%m/%Y")}. Hai cấu hình chạy trên '
             'cùng đầu ra model đã ghi: `temporal=False` (chỉ Kalman) và `temporal=True`. Sai số = khoảng cách pipeline − '
             'khoảng cách radar, trên khung có cả hai. Độ rung = độ lệch chuẩn của chênh lệch khoảng cách giữa hai khung liền nhau. '
             f'Dữ liệu: {len(segs)} đoạn comma2k19 (không phải dữ liệu Việt Nam). Tham số của `temporal.py` '
             f'(cửa sổ {WINDOW_S:.0f} s, chuyển dần qua {RAMP_SAMPLES} mẫu) được chọn bằng quét trên chính các đoạn này, '
             'nên số dưới đây lạc quan hơn trên dữ liệu mới.', '']
    allb, allt, allp, allr, per_seg = [], [], [], [], []
    for seg in segs:
        base, gap_t, pred_t, radar, n = evaluate(seg, model, a.cache)
        allb.append(base)
        allt.append(gap_t)
        allp.append(pred_t)
        allr.append(radar)
        both = np.isfinite(base) & np.isfinite(radar)
        per_seg.append((seg.name, n, stats(np.where(both, base - radar, np.nan), base, radar),
                        stats(np.where(both & np.isfinite(gap_t), gap_t - radar, np.nan), gap_t, radar)))
        print(seg.name, 'done', f'{time.perf_counter() - t0:.0f}s', flush=True)
    base, gap_t, pred_t, radar = (np.concatenate(x) for x in (allb, allt, allp, allr))
    ok = np.isfinite(radar) & np.isfinite(base) & np.isfinite(gap_t)
    lines += ['## 1. Tổng hợp (khung có radar, Kalman và temporal cùng có)', '', '| Cấu hình ' + hdr, '|---' + sep]
    for name, g in (('Kalman (không temporal)', base), ('Temporal', gap_t)):
        lines.append(f'| {name} ' + fmt(stats(np.where(ok, g - radar, np.nan), g, radar)))
    lines += ['', '## 2. Theo dải khoảng cách radar', '', '| Dải (m) | Cấu hình ' + hdr, '|---|---' + sep]
    for lo, hi in BINS:
        m = ok & (radar >= lo) & (radar < hi)
        for name, g in (('Kalman', base), ('Temporal', gap_t)):
            lines.append(f'| {lo}–{hi if hi < 200 else "…"} | {name} ' + fmt(stats(np.where(m, g - radar, np.nan), g, radar)))
    lines += ['', '## 3. Theo từng đoạn', '', '| Đoạn | Cấu hình ' + hdr, '|---|---' + sep]
    for name, _n, sb, st in per_seg:
        lines += [f'| {name} | Kalman ' + fmt(sb), f'| {name} | Temporal ' + fmt(st)]
    # prediction: gap_pred_m at frame i vs radar PREDICT_S later
    sh = int(round(PREDICT_S * FPS))
    pp = np.concatenate([p[:-sh] for p in allp])
    pg = np.concatenate([g[:-sh] for g in allt])
    ft = np.concatenate([r[sh:] for r in allr])
    k = np.isfinite(pp) & np.isfinite(pg) & np.isfinite(ft)
    lines += ['', f'## 4. Dự đoán khoảng cách sau {PREDICT_S:.0f} s', '',
              'So `gap_pred_m` với khoảng cách radar thật sau 1 s; đối chứng là "giữ nguyên khoảng cách hiện tại" (không có chuyển động).',
              '', '| Cách dự đoán ' + hdr, '|---' + sep]
    for name, g in (('Giữ nguyên khoảng cách hiện tại', pg), ('Temporal (gap_pred_m)', pp)):
        lines.append(f'| {name} ' + fmt(stats(np.where(k, g - ft, np.nan), g, ft)))
    lines += ['', f'Tổng thời gian đánh giá {(time.perf_counter() - t0) / 60:.0f} phút.', '']
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
