"""python -m src.roadwatch VIDEO --fps 20 --d-cam-bumper 1.5 [--fy PX] [--out out.mp4] [--limit N]"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from .calibration import learn_fy
from .hud import draw
from .model import MODEL_HZ, Supercombo, decode
from .pipeline import Pipeline

LEARN_SKIP, LEARN_FRAMES = 100, 200


def main():
    ap = argparse.ArgumentParser(description='Dashcam -> auto-calibration -> supercombo -> lead gap video.')
    ap.add_argument('video')
    ap.add_argument('--fps', type=float, required=True, help='true capture rate (container fps is often wrong)')
    ap.add_argument('--d-cam-bumper', type=float, required=True, help='camera to front bumper, metres')
    ap.add_argument('--fy', type=float, help='known focal length in px; skips learning')
    ap.add_argument('--out', help='annotated video (default: <video>.roadwatch.mp4)')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if not w or w % 2 or h % 2:
        raise SystemExit(f'cannot read an even-sized frame from {a.video} ({w}x{h})')
    out = Path(a.out or Path(a.video).with_suffix('.roadwatch.mp4'))
    model = Supercombo()

    t0, table = time.perf_counter(), []
    if a.fy:
        fy = a.fy
    else:
        frames = list(decode(a.video, w, h, LEARN_SKIP + LEARN_FRAMES, a.fps))[LEARN_SKIP:]
        fy, table = learn_fy(frames, w, h, model)
    print(f'fy={fy:.1f}px ({"given" if a.fy else "learned"}, {time.perf_counter() - t0:.0f}s)', flush=True)

    pipe = Pipeline(w, h, fy, a.d_cam_bumper, model)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*'mp4v'), MODEL_HZ, (w, h))
    log, ms = [], []
    for i, (y, u, v) in enumerate(decode(a.video, w, h, a.limit, a.fps)):
        t = time.perf_counter()
        r = pipe.step(y, u, v)
        ms.append(1000 * (time.perf_counter() - t))
        frame = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                             cv2.COLOR_YUV2BGR_I420)
        writer.write(draw(frame, pipe.K, r, fy))
        log.append(dict(t_s=i / MODEL_HZ, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                        ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s))
    writer.release()
    summary = dict(video=a.video, frames=len(log), fy=fy, fy_learned=not a.fy, fy_sweep=table,
                   final_rpy=pipe.rpy.tolist(), height_m=log[-1]['height_m'] if log else None,
                   calibration_resets=pipe.cal.resets, coverage=pipe.coverage,
                   pipeline_ms_median=float(np.median(ms)) if ms else None, out=str(out))
    out.with_suffix('.json').write_text(json.dumps(dict(summary=summary, frames=log), indent=1, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'fy_sweep'}, indent=1, default=float))


if __name__ == '__main__':
    main()
