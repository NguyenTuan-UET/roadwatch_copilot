"""comma2k19 segment -> GPX, to add by hand in the "Log GPS" box of the Chạy video page.

Uses the segment's global_pose (fused position at every video frame, ECEF + GPS week/second): one <trkpt> per frame
with lat, lon, ele and time. No <speed>: roadwatch.gps derives it from consecutive fixes, so the file carries only
what a real GPS log carries. Writes <segment>/gps.gpx next to video.mp4, or <out>/<segment>.gpx with --out (data/ is not committed).

    python -m scripts.roadwatch.comma2k19_to_gpx data/dashcam/* [--out data/gps]
"""
import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

GPS_EPOCH = datetime(1980, 1, 6, tzinfo=UTC)
GPS_UTC_S = 18                        # leap seconds in 2018, when comma2k19 was recorded
A, F = 6378137.0, 1 / 298.257223563   # WGS84


def ecef_to_geodetic(xyz):
    """(lat deg, lon deg, height m) of ECEF points, Bowring's iteration (converges in a few steps)."""
    x, y, z = xyz.T
    e2 = F * (2 - F)
    lon, p = np.arctan2(y, x), np.hypot(x, y)
    lat = np.arctan2(z, p * (1 - e2))
    for _ in range(6):
        n = A / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        h = p / np.cos(lat) - n
        lat = np.arctan2(z, p * (1 - e2 * n / (n + h)))
    return np.degrees(lat), np.degrees(lon), h


def segment_to_gpx(seg):
    pose = Path(seg) / 'global_pose'
    pos, gt = np.load(pose / 'frame_positions'), np.load(pose / 'frame_gps_times')
    lat, lon, h = ecef_to_geodetic(pos)
    pts = []
    for la, lo, el, (week, sec) in zip(lat, lon, h, gt):
        t = GPS_EPOCH + timedelta(weeks=int(week), seconds=float(sec) - GPS_UTC_S)
        pts.append(f'<trkpt lat="{la:.7f}" lon="{lo:.7f}"><ele>{el:.2f}</ele>'
                   f'<time>{t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z</time></trkpt>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="comma2k19 global_pose" '
            'xmlns="http://www.topografix.com/GPX/1/1"><trk><name>' + Path(seg).name + '</name><trkseg>\n'
            + '\n'.join(pts) + '\n</trkseg></trk></gpx>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('segments', nargs='+', type=Path, help='comma2k19 segment folders (contain global_pose/)')
    ap.add_argument('--out', type=Path, help='one folder for all files instead of next to each video')
    a = ap.parse_args()
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    for seg in a.segments:
        if not (seg / 'global_pose/frame_positions').exists():
            print(f'{seg}: bỏ qua, không có global_pose/frame_positions (segment chỉ có log CAN)')
            continue
        path = a.out / f'{seg.name}.gpx' if a.out else seg / 'gps.gpx'
        path.write_text(segment_to_gpx(seg), encoding='utf-8')
        print(path)


if __name__ == '__main__':
    main()
