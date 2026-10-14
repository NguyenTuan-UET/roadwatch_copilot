"""Lane jitter of the laptop pipeline on a clip, to compare with the phone's `lane_jitter` log (/phone?clip=).

    python -m scripts.roadwatch.lane_jitter_ref [--video data/video_test/curve_2_clip.webm] [--crop 0 0 1596 828]
        [--size 1280 664] [--hz 20 10] [--frames 1800]

For each rate: the clip's frames at that rate go through Pipeline and LaneSmoother (as job.py) and, once calibrated, the
left / right border of the ego lane 15 m ahead is followed: accel_rms (m/s^2: RMS of the second difference / dt^2) and
rate_p95 (m/s), as onphone/jitter.mjs; also the share of ticks with a lead and the sources of the lane centre.
"""
import argparse

import numpy as np

from src.roadwatch import hud
from src.roadwatch.model import Gr14VinAI, decode
from src.roadwatch.pipeline import Pipeline

K15 = int(np.argmin(np.abs(hud.GRID - 15)))


def jitter(t, v):
    t, v = np.asarray(t), np.asarray(v)
    dt = np.diff(t)
    accel = np.diff(np.diff(v) / dt) / ((t[2:] - t[:-2]) / 2)
    return float(np.sqrt(np.mean(accel ** 2))), float(np.percentile(np.abs(np.diff(v) / dt), 95))


def reference(video, crop, size, hz, frames=1800, fy=962.0, d_cam=1.5):
    """Laptop pipeline on the clip at `hz`: {ticks, lead, accel_rms: [L, R], rate_p95: [L, R], refs, t, yl, yr, gap}."""
    w, h = size
    stride = max(1, round(20 / hz))
    pipe = Pipeline(w, h, fy, d_cam, Gr14VinAI(), tick_dt=stride / 20)
    lane, out = hud.LaneSmoother(), dict(t=[], yl=[], yr=[], gap=[], refs={})
    for i, (y, u, v) in enumerate(decode(video, w, h, frames, 20, tuple(crop))):
        if i % stride:
            continue
        r = pipe.step(y, u, v, i / 20)
        lane.update(r)
        if r.status == 'calibrated':
            out['t'].append(i / 20), out['yl'].append(lane.geom['yl'][K15]), out['yr'].append(lane.geom['yr'][K15])
            out['gap'].append(r.gap_m)
            out['refs'][r.lane_ref] = out['refs'].get(r.lane_ref, 0) + 1
    (la, lr), (ra, rr) = jitter(out['t'], out['yl']), jitter(out['t'], out['yr'])
    return dict(out, ticks=len(out['t']), lead=float(np.mean([g is not None for g in out['gap']])),
                accel_rms=[la, ra], rate_p95=[lr, rr], hz=20 // stride)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--video', default='data/video_test/curve_2_clip.webm')
    ap.add_argument('--crop', type=int, nargs=4, default=[0, 0, 1596, 828], metavar=('X', 'Y', 'W', 'H'))
    ap.add_argument('--size', type=int, nargs=2, default=[1280, 664], metavar=('W', 'H'))
    ap.add_argument('--hz', type=int, nargs='+', default=[20, 10])
    ap.add_argument('--frames', type=int, default=1800)
    ap.add_argument('--fy', type=float, default=962.0)
    a = ap.parse_args()
    for hz in a.hz:
        r = reference(a.video, a.crop, a.size, hz, a.frames, a.fy)
        print(f'{r["hz"]} Hz: {r["ticks"]} ticks, lead {100 * r["lead"]:.0f} %, accel_rms L {r["accel_rms"][0]:.2f} '
              f'R {r["accel_rms"][1]:.2f} m/s^2, rate_p95 L {r["rate_p95"][0]:.2f} R {r["rate_p95"][1]:.2f} m/s, '
              f'lane centre {r["refs"]}')


if __name__ == '__main__':
    main()
