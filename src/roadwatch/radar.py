"""Radar log of a run: the distance to the car ahead over video time, as a CSV (what the Lab reads from comma2k19's
processed_log/CAN/radar, as a file anybody can write; scripts/roadwatch/export_radar_csv.py makes one from a segment).

Columns: a time in seconds from the video start (`t`, `t_s`, `time`, `time_s`) and the distance in metres from the radar
(the front of the car) to the car ahead (`radar_m`, `distance_m`, `dist`, `d`); an empty or NaN distance = no track. Pure:
the time comes from the file and from the video, never from the system clock."""
import csv
from pathlib import Path

import numpy as np

TIME_NAMES = ('t', 't_s', 'time', 'time_s')
DIST_NAMES = ('radar_m', 'distance_m', 'dist', 'd')
MAX_DIST_M = 300.0       # a radar distance beyond this (or <= 0) is not a track
MIN_TRACKS = 3
MAX_GAP_S = 0.15         # no sample this close to the video time: no radar value (the Lab's radar frames are 50 ms apart)


def _column(header, names):
    lower = [h.strip().lower() for h in header]
    return next((lower.index(n) for n in names if n in lower), None)


def load_radar(path) -> tuple[np.ndarray, np.ndarray]:
    """(t_s, distance_m) sorted by time; NaN where there is no track or the distance is outside (0, MAX_DIST_M].
    ValueError when the columns are missing or fewer than MIN_TRACKS distances are usable."""
    path = Path(path)
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f'{path.name} is empty')
    ti, di = _column(rows[0], TIME_NAMES), _column(rows[0], DIST_NAMES)
    if ti is None or di is None:
        raise ValueError(f'{path.name}: need a time column {TIME_NAMES} and a distance column {DIST_NAMES}')
    t, d = [], []
    for row in rows[1:]:
        try:
            t.append(float(row[ti]))
        except (ValueError, IndexError):
            continue
        try:
            d.append(float(row[di]))
        except (ValueError, IndexError):
            d.append(np.nan)
    t, d = np.array(t, float), np.array(d, float)
    d[~((d > 0) & (d <= MAX_DIST_M))] = np.nan
    order = np.argsort(t)
    t, d = t[order], d[order]
    if np.isfinite(d).sum() < MIN_TRACKS:
        raise ValueError(f'{path.name}: fewer than {MIN_TRACKS} usable radar distances')
    return t, d


class RadarRef:
    """The radar distance at a video time (s): the nearest sample if it is within MAX_GAP_S, else NaN."""

    def __init__(self, t, d):
        self.t, self.d = np.asarray(t, float), np.asarray(d, float)

    def __call__(self, pts: float) -> float:
        i = int(np.clip(np.searchsorted(self.t, pts), 1, len(self.t) - 1))
        i -= abs(self.t[i - 1] - pts) <= abs(self.t[i] - pts)
        return float(self.d[i]) if abs(self.t[i] - pts) <= MAX_GAP_S else np.nan
