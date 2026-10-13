"""Make the most telling clips of data/video_test/comma2k19_lane_test selectable in the Lab tab.

The Lab lists folders of RW_LAB_DIR (default data/comma2k19) that hold a video.mp4; a clip becomes `lane_<clip>` with
a link to its video, the frame times the Lab reads and the real curvature gt.csv (no radar or CAN log: the Lab then
shows the lane and the ego motion from the images alone, and charts the curvature against the real one). Default clips (from scripts/roadwatch/eval_lane_test.py):
  c02  left, R 145 m, 48 km/h: the tightest turn, lane lines lost half of the time (the worst case)
  c03  left, R 135 m, 49 km/h: urban turn with junctions and many cars
  c06  right, R 710 m, 113 km/h: long highway curve, the largest offset from the lane centre, wipers
  s01  straight, 112 km/h: baseline, shows false curvature

    python scripts/roadwatch/add_lane_clips.py [clip ...]
"""
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
TEST = REPO / 'data/video_test/comma2k19_lane_test'
LAB_DIR = REPO / 'data/comma2k19'
CLIPS = ('c02', 'c03', 'c06', 's01')
FPS, FRAMES = 20.0, 600


def add(clip, test=TEST, lab_dir=LAB_DIR):
    video = test / 'videos' / f'{clip}.mp4'
    if not video.is_file():
        raise SystemExit(f'{video} missing')
    seg = lab_dir / f'lane_{clip}'
    (seg / 'global_pose').mkdir(parents=True, exist_ok=True)
    link = seg / 'video.mp4'
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(video.resolve())
    np.save(seg / 'global_pose' / 'frame_times.npy', np.arange(FRAMES) / FPS)
    shutil.copyfile(test / 'gt' / f'{clip}.csv', seg / 'gt.csv')   # real curvature per frame: the Lab charts it
    return seg


if __name__ == '__main__':
    for c in sys.argv[1:] or CLIPS:
        print(add(c).relative_to(REPO))
