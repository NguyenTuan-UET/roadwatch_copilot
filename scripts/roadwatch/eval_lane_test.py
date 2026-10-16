"""Evaluate lane following on data/video_test/comma2k19_lane_test: how well the curvature of the path BT-A draws
follows the real one (comma2k19 global_pose) and how far the car is from the lane centre.

Four curvature estimators are run side by side on every clip, each written as a predictions file for the test's own
scorer (evaluate_lane.py): `yaw` (ego yaw rate / speed from the model's pose, smoothed as in pipeline), `plan` (the
model's trajectory), `lane` (the middle of the two ego lane lines) and `drawn` (pipeline.predicted_path, what the HUD
and the phone draw). Signs are the test's: + = turning left, lateral offset + = left of the lane centre.

    python scripts/roadwatch/eval_lane_test.py [test_dir] [out_dir]
"""
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch.model import decode, video_size
from src.roadwatch.pipeline import (
    CURV_FIT_X,
    Pipeline,
    fit_curvature,
    lane_lines_center,
    path_reach,
    plan_offset,
    predicted_path,
)

REPO = Path(__file__).resolve().parents[2]
FY = 910.0                  # px, comma2k19 (as lab.py)
FIT_X = CURV_FIT_X
ESTIMATORS = ('yaw', 'plan', 'lane', 'drawn')


def run_clip(video, model=None):
    """Per frame {estimator: curvature (1/m, + = left) or None, offset: m or None} for one clip."""
    w, h = video_size(video)
    pipe = Pipeline(w, h, FY, 1.5, model)
    rows = []
    for y, u, v in decode(video, w, h):
        r = pipe.step(y, u, v)
        p, row = r.outputs, dict.fromkeys(ESTIMATORS)
        row['offset'] = None
        if pipe.settled:
            reach = path_reach(r.ego_speed_mps)
            row['yaw'] = -r.curvature
            plan = plan_offset(p, FIT_X)
            row['plan'] = None if plan is None else -fit_curvature(plan)
            lane = lane_lines_center(p, FIT_X)
            if lane is not None:
                row['lane'] = -fit_curvature(lane)
                row['offset'] = float(lane_lines_center(p, 3.0))   # lane centre right of the camera = car left of it
            row['drawn'] = -fit_curvature(predicted_path(p, r.curvature, FIT_X, reach, r.straddle))
        rows.append(row)
    return rows


def main():
    test = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / 'data/video_test/comma2k19_lane_test'
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / 'runs/lane_eval'
    out.mkdir(parents=True, exist_ok=True)
    clips = sorted(p.stem for p in (test / 'videos').glob('*.mp4') if not p.stem.endswith('_annotated'))
    preds = {k: [] for k in ESTIMATORS}
    for clip in clips:
        print(clip, flush=True)
        for i, row in enumerate(run_clip(test / 'videos' / f'{clip}.mp4')):
            for k in ESTIMATORS:
                preds[k].append((clip, i, row[k], row['offset']))
    for k in ESTIMATORS:
        path = out / f'predictions_{k}.csv'
        with open(path, 'w', newline='') as f:
            wr = csv.writer(f)
            wr.writerow(['clip', 'frame', 'curvature', 'lateral_offset_m'])
            for clip, i, c, o in preds[k]:
                wr.writerow([clip, i, '' if c is None else f'{c:.6f}', '' if o is None else f'{o:.3f}'])
        subprocess.run([sys.executable, str(test / 'evaluate_lane.py'), str(test), str(path), str(out / k)],
                       check=True, stdout=subprocess.DEVNULL)
        print(f'--- {k}\n' + (out / k / 'eval_log.txt').read_text().split('=== DOAN CONG')[1].split('=== DOAN THANG')[0])


if __name__ == '__main__':
    main()
