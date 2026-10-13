"""Write the radar log of a comma2k19 segment as the CSV the upload page and the API take (src/roadwatch/radar.py).

The same reference the Lab uses (lab.radar_reference: the nearest radar track within 1.6 m laterally, distance from the
radar = the front of the car), one row per video frame: time in seconds from the first frame, distance in metres, empty
where there is no track. Upload it beside the segment's video (and its gps.gpx) on the Chạy video page.

    python scripts/roadwatch/export_radar_csv.py data/comma2k19/0 [out.csv]
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root
from src.roadwatch.lab import FPS, radar_reference


def export(seg, out):
    ref = radar_reference(Path(seg))
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t_s', 'radar_m'])
        for i, d in enumerate(ref):
            w.writerow([f'{i / FPS:.2f}', '' if not np.isfinite(d) else f'{d:.2f}'])
    return int(np.isfinite(ref).sum()), len(ref)


if __name__ == '__main__':
    seg = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f'radar_{seg.name}.csv')
    tracks, frames = export(seg, out)
    print(f'{out}: {tracks}/{frames} frames with a radar track')
