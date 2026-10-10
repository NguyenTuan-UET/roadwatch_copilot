"""GPS speed log reader + time alignment to the video. Ported from comma_ai/lead_distance/gps.py (copied, not
imported: it is another repo).

Supported inputs (speed is what matters here; it is used to recover the camera focal length):
  * GPX   : <trkpt lat lon><time/>[<speed/>]</trkpt>  (speed from consecutive fixes when missing)
  * NMEA  : $GPRMC / $GNRMC sentences (UTC time, date, speed over ground in knots)
  * CSV   : header with a time column (t / time / timestamp: seconds or ISO 8601) and either a speed
            column (speed_mps / speed / speed_kmh / speed_kph) or lat + lon.
Returned times are seconds; `align_offset` finds where the GPS log sits on the video time axis.
"""
import csv
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

KNOT = 0.514444


def _parse_time(s: str) -> float:
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).timestamp()


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _speed_from_positions(t, lat, lon):
    d = _haversine(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dt = np.diff(t)
    v = np.where(dt > 0, d / np.maximum(dt, 1e-6), np.nan)
    tm = (t[:-1] + t[1:]) / 2
    return tm, v


def _load_gpx(path: Path):
    root = ET.parse(path).getroot()
    pts = [e for e in root.iter() if e.tag.split("}")[-1] == "trkpt"]
    t, lat, lon, spd = [], [], [], []
    for p in pts:
        child = {c.tag.split("}")[-1]: c for c in p.iter()}
        if "time" not in child:
            continue
        t.append(_parse_time(child["time"].text))
        lat.append(float(p.get("lat")))
        lon.append(float(p.get("lon")))
        spd.append(float(child["speed"].text) if "speed" in child and child["speed"].text else np.nan)
    t, lat, lon, spd = map(np.array, (t, lat, lon, spd))
    if np.isfinite(spd).mean() > 0.5:
        return t, spd
    return _speed_from_positions(t, lat, lon)


def _load_nmea(path: Path):
    t, v = [], []
    for line in path.read_text(errors="ignore").splitlines():
        m = re.search(r"\$(?:GP|GN|GL|GA)RMC,([^*]*)", line)
        if not m:
            continue
        f = m.group(1).split(",")
        if len(f) < 9 or f[1] != "A" or not f[0] or not f[8]:
            continue
        hh, mm, ss = int(f[0][:2]), int(f[0][2:4]), float(f[0][4:])
        day, mon, yr = int(f[8][:2]), int(f[8][2:4]), 2000 + int(f[8][4:6])
        base = datetime(yr, mon, day, tzinfo=UTC).timestamp()
        t.append(base + hh * 3600 + mm * 60 + ss)
        v.append(float(f[6] or 0) * KNOT)
    return np.array(t), np.array(v)


def _load_csv(path: Path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("empty GPS csv")
    keys = {k.lower().strip(): k for k in rows[0]}
    tk = next((keys[k] for k in ("t", "time", "timestamp", "time_s", "utc") if k in keys), None)
    if tk is None:
        raise ValueError(f"GPS csv needs a time column, got {list(rows[0])}")
    t = np.array([_parse_time(r[tk]) for r in rows])
    for k, scale in (("speed_mps", 1.0), ("speed", 1.0), ("v_ego", 1.0), ("speed_kmh", 1 / 3.6), ("speed_kph", 1 / 3.6)):
        if k in keys:
            return t, np.array([float(r[keys[k]] or "nan") for r in rows]) * scale
    if "lat" in keys and "lon" in keys:
        lat = np.array([float(r[keys["lat"]]) for r in rows])
        lon = np.array([float(r[keys["lon"]]) for r in rows])
        return _speed_from_positions(t, lat, lon)
    raise ValueError("GPS csv needs a speed column or lat/lon")


def load_gps(path) -> tuple[np.ndarray, np.ndarray]:
    """(t_s, speed_mps) sorted by time, with t relative to the first fix, outliers removed (> 5 m/s^2)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".gpx":
        t, v = _load_gpx(path)
    elif ext == ".csv":
        t, v = _load_csv(path)
    else:
        t, v = _load_nmea(path)
    ok = np.isfinite(t) & np.isfinite(v) & (v >= 0) & (v < 90)
    t, v = t[ok], v[ok]
    order = np.argsort(t)
    t, v = t[order], v[order]
    if len(t) < 3:
        raise ValueError(f"no usable GPS fixes in {path.name}")
    acc = np.abs(np.diff(v)) / np.maximum(np.diff(t), 1e-3)
    keep = np.r_[True, acc < 5.0]
    t, v = t[keep], v[keep]
    return t - t[0], v


def speed_at(t_gps, v_gps, t_video, offset):
    """GPS speed at video time t (video t = 0 is GPS time `offset`); NaN outside the log or across gaps > 3 s."""
    tq = np.asarray(t_video) + offset
    v = np.interp(tq, t_gps, v_gps, left=np.nan, right=np.nan)
    idx = np.clip(np.searchsorted(t_gps, tq), 1, len(t_gps) - 1)
    gap = (t_gps[idx] - t_gps[idx - 1]) > 3.0
    return np.where(gap, np.nan, v)


def align_offset(t_gps, v_gps, t_model, v_model, search_s=10.0, step_s=0.05, center=0.0):
    """Video->GPS time offset by cross-correlating GPS speed with the model's speed (shape only: the model's
    speed carries the unknown focal-length scale). Returns (offset, correlation)."""
    t_model, v_model = np.asarray(t_model), np.asarray(v_model)
    best = (center, -1.0)
    for off in np.arange(center - search_s, center + search_s + 1e-9, step_s):
        g = speed_at(t_gps, v_gps, t_model, off)
        m = np.isfinite(g) & np.isfinite(v_model)
        if m.sum() < 40 or np.std(g[m]) < 0.2 or np.std(v_model[m]) < 0.2:
            continue
        c = float(np.corrcoef(g[m], v_model[m])[0, 1])
        if c > best[1]:
            best = (float(off), c)
    return best


class GpsRef:
    """GPS speed on the video time axis, synchronised online while the video plays (no pre-pass):
    the model's speed is buffered and cross-correlated with the GPS speed once enough driving is seen."""
    SYNC_AFTER_S = 20.0     # first attempt after this much video
    RETRY_EVERY_S = 5.0
    GIVE_UP_S = 90.0        # then fall back to offset 0 and flag it
    MIN_CORR = 0.8

    def __init__(self, t, v, offset="auto"):
        self.t, self.v = t, v
        self.offset = 0.0 if offset in (None, "auto") else float(offset)
        self.synced = offset not in (None, "auto")
        self.corr, self.low_confidence = np.nan, False
        self._bt, self._bv, self._next_try = [], [], self.SYNC_AFTER_S

    def observe(self, pts: float, v_model: float):
        if self.synced:
            return
        self._bt.append(pts)
        self._bv.append(v_model)
        span = pts - self._bt[0]
        if span < self._next_try:
            return
        self._next_try = span + self.RETRY_EVERY_S
        off, corr = align_offset(self.t, self.v, np.array(self._bt), np.array(self._bv))
        self.corr = corr
        if corr >= self.MIN_CORR:
            self.offset, self.synced = off, True
        elif span >= self.GIVE_UP_S:
            self.synced, self.low_confidence = True, True

    def __call__(self, pts: float) -> float:
        if not self.synced:
            return np.nan
        return float(speed_at(self.t, self.v, np.array([pts]), self.offset)[0])
