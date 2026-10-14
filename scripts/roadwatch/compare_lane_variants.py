"""Compare the lane-following variants of pipeline.py on the lane test and on comma2k19 segments with radar.

Variants (module switches of src/roadwatch/pipeline.py): `base` (neither), `widen` (WIDEN_LEAD: the lead window
covers both lanes when the car runs between them), `yaw` (NEAR_FROM_YAW: the path near the car is the yaw arc, the
plan only adds the far bend), `both`. One variant per process, results in <out>/<variant>.json; with no variant
argument all four run in parallel and the table is printed.

  curvature: MAE (1/km) of the yaw curvature and of the drawn path against the real one, on the curve frames of
             data/video_test/comma2k19_lane_test (frames where the real |curvature| > 1/1000 m)
  lead:      against the radar (lab.radar_reference, +-1.6 m) on data/comma2k19 segments: frames with a lead found /
             frames with a radar track, frames with a lead but no radar track (a car in another lane, or none), and the
             distance MAE where both exist

    python scripts/roadwatch/compare_lane_variants.py [variant] [out_dir]
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch import pipeline as pl
from src.roadwatch.lab import RADAR_TO_CAMERA, radar_reference
from src.roadwatch.model import Gr14VinAI, decode, video_size

REPO = Path(__file__).resolve().parents[2]
TEST = REPO / 'data/video_test/comma2k19_lane_test'
SEGMENTS = REPO / 'data/comma2k19'
FY = 910.0
VARIANTS = {'base': (False, False), 'widen': (True, False), 'yaw': (False, True), 'both': (True, True)}
WARMUP = 60   # frames before the numbers count (calibration, recurrent state)


def run(video, model, frames=0):
    w, h = video_size(video)
    pipe = pl.Pipeline(w, h, FY, RADAR_TO_CAMERA, model)
    for i, (y, u, v) in enumerate(decode(video, w, h, limit=frames)):
        yield i, pipe.step(y, u, v), pipe.settled


def curvature(model):
    out = {}
    for gt_file in sorted((TEST / 'gt').glob('*.csv')):
        clip = gt_file.stem
        gt = {int(r['frame']): float(r['curvature']) for r in csv.DictReader(open(gt_file))}
        err = {'yaw': [], 'drawn': []}
        for i, r, settled in run(TEST / 'videos' / f'{clip}.mp4', model):
            k = gt.get(i)
            if not settled or k is None or abs(k) < 1e-3 or r.curvature is None:
                continue
            drawn = pl.path_curvature(r.outputs, r.curvature, r.ego_speed_mps, r.straddle)
            err['yaw'].append(abs(-r.curvature - k) * 1000)
            err['drawn'].append(abs(-drawn - k) * 1000)
        out[clip] = {n: (float(np.mean(e)) if e else None) for n, e in err.items()} | {'n': len(err['yaw'])}
    return out


def lead(model):
    out = {}
    for seg in sorted(p for p in SEGMENTS.iterdir() if (p / 'video.mp4').is_file() and not p.name.startswith('lane_')):
        radar = radar_reference(seg)
        n_radar = n_found = n_extra = 0
        errs = []
        for i, r, settled in run(seg / 'video.mp4', model, len(radar)):
            if i < WARMUP or not settled:
                continue
            has, rad = r.gap_m is not None, radar[i]
            n_radar += bool(np.isfinite(rad))
            if has and np.isfinite(rad):
                n_found += 1
                errs.append(abs(r.gap_m - rad))
            n_extra += bool(has and not np.isfinite(rad))
        out[seg.name] = dict(radar=n_radar, found=n_found, extra=n_extra, mae=float(np.mean(errs)) if errs else None)
    return out


def one(name, out):
    pl.WIDEN_LEAD, pl.NEAR_FROM_YAW = VARIANTS[name]
    model = Gr14VinAI()
    res = dict(curvature=curvature(model), lead=lead(model))
    (out / f'{name}.json').write_text(json.dumps(res, indent=1))


def table(out):
    res = {n: json.loads((out / f'{n}.json').read_text()) for n in VARIANTS if (out / f'{n}.json').exists()}
    print('curvature MAE on curve frames, 1/km (lower is better): yaw | drawn')
    for clip in res['base']['curvature']:
        print(f'  {clip}  n={res["base"]["curvature"][clip]["n"]:4d}  ' + '   '.join(
            f'{n}: {r["curvature"][clip]["yaw"]:.2f} | {r["curvature"][clip]["drawn"]:.2f}'
            for n, r in res.items() if r['curvature'][clip]['yaw'] is not None))
    print('\nlead vs radar per segment: found/radar frames, extra (lead without a radar track), MAE m')
    for seg in res['base']['lead']:
        print(f'  seg {seg}  ' + '   '.join(
            f'{n}: {r["lead"][seg]["found"]}/{r["lead"][seg]["radar"]} +{r["lead"][seg]["extra"]} '
            f'{r["lead"][seg]["mae"]:.2f}' for n, r in res.items() if r['lead'][seg]['mae'] is not None))


if __name__ == '__main__':
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / 'runs/lane_variants'
    out.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] in VARIANTS:
        one(sys.argv[1], out)
    else:
        procs = [subprocess.Popen([sys.executable, __file__, n, str(out)]) for n in VARIANTS]
        for p in procs:
            p.wait()
        table(out)
