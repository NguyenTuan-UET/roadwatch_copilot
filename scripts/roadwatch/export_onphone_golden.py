"""Golden data for the on-phone JS port (src/roadwatch/ui/onphone/*.mjs), computed by the Python code it ports.

    python -m scripts.roadwatch.export_onphone_golden [--segment data/comma2k19/3] [--ticks 400]

Writes tests/roadwatch/fixtures/onphone/{geometry,prep,parse,pipeline,decide}.json; the JS tests
(node --test tests/roadwatch/js) replay them. pipeline.json needs the model (models/gr14VinAI.onnx) and a comma2k19
segment: gr14VinAI runs on the first --ticks frames and each tick's raw outputs (1961 with road_edges and plan) are
kept, so the JS side replays them without the model and compares every Result, and every 10th tick the HUD overlay
with and without a LaneSmoother (job.py draws the smoothed one) and the smoothed lane geometry.
"""
import argparse
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from src.roadwatch import decide, hud
from src.roadwatch import pipeline as pl
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
            'lead', 'lead_stds', 'lead_prob', 'road_edges', 'road_edges_stds', 'plan', 'plan_stds')
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
    lane, rows = hud.LaneSmoother(), []
    for i, (y, u, v) in enumerate(decode(video, w, h, ticks, 20)):
        pts = i / 20
        r = pipe.step(y, u, v, pts)
        lane.update(r)
        o = hud.overlay(pipe.K, r, w, h) if i % 10 == 0 else None
        o_lane = hud.overlay(pipe.K, r, w, h, lane) if i % 10 == 0 else None
        geom = {k: (L(v) if isinstance(v, np.ndarray) else v) for k, v in lane.geom.items()} if i % 10 == 0 else None
        rows.append(dict(pts=pts, vgps=None if np.isnan(gps(pts)) else gps(pts), status=r.status, rpy=L(r.rpy), rpy_est=L(r.rpy_est),
                         height_m=r.height_m, ego_speed_mps=float(r.ego_speed_mps), lead_prob=float(r.lead_prob), gap_m=r.gap_m,
                         lead_speed_mps=r.lead_speed_mps, ttc_s=r.ttc_s, gap_std_m=r.gap_std_m, lead_lat_m=r.lead_lat_m,
                         lead_x_m=r.lead_x_m, lead_raw_m=r.lead_raw_m, gps_speed_mps=r.gps_speed_mps, gap_pred_m=r.gap_pred_m,
                         model_speed_mps=float(r.model_speed_mps), coverage=pipe.coverage, curvature=r.curvature,
                         lane_ref=r.lane_ref, straddle=r.straddle, overlay=o, overlay_lane=o_lane, lane=geom))
    raws = np.stack(model.raws)
    return dict(w=w, h=h, fy=910.0, d=1.52, n=raws.shape[1], raws=b64(raws), rows=rows)


def lanes(segments, ticks=(60, 140, 220, 300)):
    """Lane functions of pipeline.py and hud.lane_geometry on real outputs (some ticks of each segment) and on copies whose
    lane lines are shifted sideways so the car drives on the left or the right line (straddle: no clip has it)."""
    model, cases = Recording(), []
    for seg in segments:
        video = Path(seg) / 'video.mp4'
        w, h = video_size(video)
        model.reset()
        warps = warp_matrices(intrinsics(910.0, w, h), np.zeros(3), w)
        for i, (y, u, v) in enumerate(decode(video, w, h, max(ticks) + 1, 20)):
            model.step(pack_frame(y, u, v, warps))
            if i not in ticks:
                continue
            raw = model.raws[-1]
            for shift in (0., None, 'left', 'right'):
                r = raw.copy()
                ll = r[24:24 + 264].reshape(4, 33, 2)   # lane_lines means (y, z), in place
                if shift in ('left', 'right'):   # put line 1 (left) or 2 (right) 0.3 m from the camera 5 m ahead
                    k = 1 if shift == 'left' else 2
                    ll[:, :, 0] -= np.interp(5., pl.X_IDXS, ll[k, :, 0]) - (-0.3 if k == 1 else 0.3)
                elif shift is None:
                    r[707:971] = raw[707:971] + 0   # same; then road edges marked uncertain on the right
                    r[707 + 132 + 66:707 + 132 + 132] = 2.0   # road_edges stds of edge 1: exp(2) = 7.4 m
                p = model.parser.parse_outputs({kk: r[None, s_].copy() for kk, s_ in model.slices.items()})
                curv, speed = [0.0, 0.004, -0.02][len(cases) % 3], 18.0
                on = {prev: pl.straddle(p, prev) for prev in (None, 1, 2)}
                lx = float(p['lead'][0, 0, 0, 0])
                center = pl.lane_center(p, curv, lx, pl.path_reach(speed), on[None])
                path = pl.predicted_path(p, curv, pl.X_IDXS, pl.path_reach(speed), on[None])
                res = SimpleNamespace(outputs=p, gap_m=12.0 if len(cases) % 2 else None, curvature=curv, ego_speed_mps=speed,
                                      straddle=on[None], height_m=1.3, lead_x_m=40.0, lead_lat_m=0.4)
                geom = hud.lane_geometry(res)
                cases.append(dict(raw=b64(r), curv=curv, speed=speed, straddle={str(k): v for k, v in on.items()}, lx=lx,
                                  center=[float(center[0]), float(center[1]), center[2]], path=L(path),
                                  gap=res.gap_m, geom={k: (L(v) if isinstance(v, np.ndarray) else v) for k, v in geom.items()}))
    return dict(n=len(model.raws[-1]), cases=cases)


def decide_seq():
    """A scripted drive at 20 Hz touching every rule of decide.Decider (docs/warning_to_do.md)."""
    def at(t):   # -> (gap or None, km/h, calibrated, ok)
        if t < 3:
            return 30.0, 50, False, True                                    # calibrating
        if t < 8:
            return max(8.0, 44 - 4 * (t - 3)), 50, True, True               # closing in: info then warning
        if t < 10:
            return None, 50, True, True                                     # lead lost
        if t < 20:
            return (60.0 if abs(t - 15) < 1e-6 else 20.0), 50, True, True   # staying close (repeats), one jumping frame
        if t < 30:
            return 20 + (t - 20), 50, True, True                            # opening: no repeat
        if t < 34:
            return 50.0, 50, True, True                                     # clear: episode ends
        if t < 40:
            return (40.0 if t < 36 else 40 - 6 * (t - 36)), 50, True, True  # gap falling fast
        if t < 44:
            return None, 50, True, True
        if t < 60:
            return (None if 52 <= t < 53 else 95.0), 110, True, True        # chime once, short loss keeps the episode
        if t < 66:
            return None, 110, True, True                                    # long loss: a new episode
        if t < 75:
            return 25.0, 110, True, True                                    # first sight far too close
        if t < 90:
            return 30 + 25 * np.sin(t / 6), 50 + 50 * np.sin(t / 25) ** 2, True, not (86 < t < 88)   # crosses bands
        if t < 100:
            return 4.0, 3, True, True                                       # standing still
        if t < 110:
            return 6.0, 12, True, True                                      # crawling
        return 85 - 2 * (t - 110), 80, True, True
    rows, dec = [], decide.Decider()
    for i in range(2400):
        t = i / 20
        gap, kmh, calibrated, ok = at(t)
        gap = None if gap is None else float(gap)
        d = dec.step(t, gap, kmh / 3.6, calibrated, ok)
        rows.append(dict(t=t, gap=gap, ego=kmh / 3.6, calibrated=calibrated, ok=ok,
                         level=d.level, say=d.say, reason=d.reason, threshold_m=d.threshold_m, raw=sorted(d.raw)))
    speeds = (0, 4.9, 5, 19.9, 20, 50, 59.9, 60, 70, 80, 90.5, 100, 110, 119, 120, 150)
    return dict(rows=rows, legal=[[k, decide.legal_gap(k)] for k in speeds],
                thresholds=[[k, decide.thresholds(k)] for k in speeds])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segment', default='data/comma2k19/3')
    ap.add_argument('--ticks', type=int, default=400)
    ap.add_argument('--curve', default='data/comma2k19/lane_c02')   # a curve without lane lines (ego_path, road edges)
    ap.add_argument('--only', nargs='+', help='write only these files, e.g. --only decide (needs no model, no data)')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = dict(geometry=geometry, prep=prep, parse=lambda: parse(Gr14VinAI()), decide=decide_seq,
                pipeline=lambda: pipeline(a.segment, a.ticks), pipeline_c02=lambda: pipeline(a.curve, 300),
                lanes=lambda: lanes([a.segment, a.curve]))
    for name in a.only or jobs:
        data = jobs[name]()
        (OUT / f'{name}.json').write_text(json.dumps(data, allow_nan=False))
        print(f'wrote {OUT / name}.json ({(OUT / f"{name}.json").stat().st_size / 1e3:.0f} kB)')
    print('AutoCalib.SETTLED_SAMPLES', AutoCalib.SETTLED_SAMPLES)


if __name__ == '__main__':
    main()
