"""Golden data for the on-phone JS port (src/roadwatch/ui/onphone/*.mjs), computed by the Python code it ports.

    python -m scripts.roadwatch.export_onphone_golden [--segment data/comma2k19/3] [--ticks 400]

Writes tests/roadwatch/fixtures/onphone/{geometry,prep,parse,pipeline,decide}.json; the JS tests
(node --test tests/roadwatch/js) replay them. pipeline.json needs the model (models/gr14VinAI.onnx) and a comma2k19
segment: gr14VinAI runs on the first --ticks frames and each tick's raw 707 outputs are kept, so the JS side replays
them without the model and compares every Result.
"""
import argparse
import base64
import json
from pathlib import Path

import cv2
import numpy as np

from src.roadwatch import decide, hud
from src.roadwatch.calibration import AutoCalib, euler_from_rot, focal_px_from_mm, intrinsics, rot_from_euler
from src.roadwatch.model import (
    Gr14VinAI,
    coverage,
    decode,
    frame_to_model_input,
    pack_frame,
    video_size,
    warp_matrices,
    wide_mode,
)
from src.roadwatch.pipeline import Pipeline

OUT = Path(__file__).resolve().parents[2] / 'tests/roadwatch/fixtures/onphone'
b64 = lambda a: base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()  # noqa: E731
L = lambda a: np.asarray(a, float).tolist()  # noqa: E731
CASES = [   # fy, w, h, rpy (rad), wide
    (910.0, 1164, 874, [0., 0., 0.], 'auto'), (481.0, 640, 360, [0.01, 0.09, -0.14], 'auto'),
    (962.0, 1280, 720, [0.002, -0.08, -0.05], 'auto'), (481.0, 640, 480, [0., 0.15, 0.], 'dup'),
]


def planes(w, h):
    """Synthetic yuv420p planes; the same formulas are in prep.test.mjs."""
    j, i = np.mgrid[0:h, 0:w]
    y = ((i * 3 + j * 5 + (i * j) % 7) % 256).astype(np.uint8)
    j2, i2 = np.mgrid[0:h // 2, 0:w // 2]
    return y, ((i2 + j2 * 2) % 256).astype(np.uint8), ((i2 * 3 + j2) % 256).astype(np.uint8)


def geometry():
    eul = [[0.1, -0.2, 0.3], [0.0, 0.05, -1.2], [-0.4, 0.3, 2.9]]
    cases = []
    for fy, w, h, rpy, wide in CASES:
        k = intrinsics(fy, w, h)
        ws = warp_matrices(k, np.array(rpy), w, wide)
        pts = [[20., 0.5, 1.2], [60., -1.8, 1.3], [5., 3., 1.]]
        uv, ok = hud.project(k, np.array(rpy), pts)
        cases.append(dict(fy=fy, w=w, h=h, rpy=rpy, wide=wide, K=L(k), narrow=L(ws[0]), wide_m=None if ws[1] is None else L(ws[1]),
                          mode=wide_mode(k, w, wide), coverage=coverage(ws, w, h), pts=pts, uv=L(uv), ok=[bool(x) for x in ok]))
    return dict(euler=[dict(e=e, rot=L(rot_from_euler(e)), back=L(euler_from_rot(rot_from_euler(e)))) for e in eul],
                focal=[dict(f_mm=26, px=640, fy=focal_px_from_mm(26, 640))], cases=cases)


def prep():
    w, h = 640, 360
    y, u, v = planes(w, h)
    k = intrinsics(481.0, w, h)
    ws = warp_matrices(k, np.array([0.01, 0.09, -0.14]), w)
    rng = np.random.default_rng(3)
    rgb = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
    i420 = cv2.cvtColor(rgb, cv2.COLOR_RGB2YUV_I420)
    return dict(w=w, h=h, narrow=L(ws[0]), wide=L(ws[1]), packed=b64(pack_frame(y, u, v, ws)),
                single=b64(frame_to_model_input(y, u, v, ws[0])), rgb=b64(rgb), i420=b64(i420))


def parse(model):
    raw = np.array(json.loads((Path('models/ort-web/reference.json')).read_text())['outputs'], np.float32)[None]
    p = model.parser.parse_outputs({kk: raw[:, s].copy() for kk, s in model.slices.items()})
    keys = ('pose', 'pose_stds', 'road_transform', 'road_transform_stds', 'lane_lines', 'lane_lines_stds', 'lane_lines_prob',
            'lead', 'lead_stds', 'lead_prob')
    return dict(raw=L(raw[0]), parsed={kk: L(p[kk][0]) for kk in keys})


class Recording(Gr14VinAI):
    """Keeps the raw output vector of every step."""
    def __init__(self):
        super().__init__()
        self.raws = []

    def step(self, new_img):
        self.inputs['new_img'] = new_img
        out = dict(zip(self.names, self.sess.run(None, self.inputs)))
        for kk in list(self.inputs):
            if 'next_' + kk in out:
                self.inputs[kk] = out['next_' + kk]
        self.raws.append(out['outputs'][0].astype(np.float32))
        return self.parser.parse_outputs({kk: out['outputs'][:, s].copy() for kk, s in self.slices.items()})


def pipeline(segment, ticks):
    video = Path(segment) / 'video.mp4'
    w, h = video_size(video)
    model = Recording()
    gps = lambda t: 25.0 if t >= 10 else np.nan  # noqa: E731   GPS speed only in the second half
    gps.observe = lambda *a: None
    pipe = Pipeline(w, h, 910.0, 1.52, model, v_ref=gps)
    rows = []
    for i, (y, u, v) in enumerate(decode(video, w, h, ticks, 20)):
        pts = i / 20
        r = pipe.step(y, u, v, pts)
        o = hud.overlay(pipe.K, r, w, h) if i % 10 == 0 else None
        rows.append(dict(pts=pts, vgps=None if np.isnan(gps(pts)) else gps(pts), status=r.status, rpy=L(r.rpy), rpy_est=L(r.rpy_est),
                         height_m=r.height_m, ego_speed_mps=float(r.ego_speed_mps), lead_prob=float(r.lead_prob), gap_m=r.gap_m,
                         lead_speed_mps=r.lead_speed_mps, ttc_s=r.ttc_s, gap_std_m=r.gap_std_m, lead_lat_m=r.lead_lat_m,
                         lead_x_m=r.lead_x_m, lead_raw_m=r.lead_raw_m, gps_speed_mps=r.gps_speed_mps, gap_pred_m=r.gap_pred_m,
                         model_speed_mps=float(r.model_speed_mps), coverage=pipe.coverage, overlay=o))
    return dict(w=w, h=h, fy=910.0, d=1.52, raws=b64(np.stack(model.raws)), rows=rows)


def decide_seq():
    """A scripted drive at 20 Hz touching every rule (calibration, cut-in grace, warning, info, emergency, congestion)."""
    rows, dec = [], decide.Decider()
    for i in range(2400):
        t = i / 20
        kmh = 50 + 50 * np.sin(t / 25) ** 2 if t < 100 else 90 if t < 115 else 40   # crosses 60 km/h; steady; congestion
        gap = None if 8 < t < 10 else (80 - 0.6 * t if t < 40 else 30 + 25 * np.sin(t / 6) if t < 100
                                       else 85 - (t - 100))           # lost lead; closing; oscillating; just above 70 m: info
        if 55 < t < 56:
            gap = 12.0                                                  # cut-in: drop > 10 m
        ttc = 1.4 + (t - 70) if 70 < t < 73 else (5.0 if gap is not None and gap < 20 else None)
        calibrated, ttc_ok = t > 3, not (90 < t < 92)
        d = dec.step(t, gap, kmh / 3.6, ttc, calibrated, ttc_ok)
        rows.append(dict(t=t, gap=gap, ego=kmh / 3.6, ttc=ttc, calibrated=calibrated, ttc_ok=ttc_ok,
                         level=d.level, say=d.say, reason=d.reason, threshold_m=d.threshold_m, raw=sorted(d.raw)))
    return dict(rows=rows, legal=[[k, decide.legal_gap(k)] for k in (0, 59.9, 60, 70, 80, 90.5, 100, 119, 120, 150)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segment', default='data/comma2k19/3')
    ap.add_argument('--ticks', type=int, default=400)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    model = Gr14VinAI()
    for name, data in (('geometry', geometry()), ('prep', prep()), ('parse', parse(model)), ('decide', decide_seq()),
                       ('pipeline', pipeline(a.segment, a.ticks))):
        (OUT / f'{name}.json').write_text(json.dumps(data, allow_nan=False))
        print(f'wrote {OUT / name}.json ({(OUT / f"{name}.json").stat().st_size / 1e3:.0f} kB)')
    print('AutoCalib.SETTLED_SAMPLES', AutoCalib.SETTLED_SAMPLES)


if __name__ == '__main__':
    main()
