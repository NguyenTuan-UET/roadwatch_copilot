"""A phone as the live camera and GPS: the /phone page sends its back camera over WebRTC and its GPS fixes over a
data channel of the same connection (webrtc.PhoneReceiver); a demo run (job.Job) reads them from here.

Both are on the session clock (spec 3.3, live): seconds since the connection was set up, stamped when a frame or fix
arrives (t_recv), never the phone's own clock. Live never queues (spec 3.2): FrameSource keeps only the newest frame
and hands one out per model tick (about 20 Hz); frames replaced before they were taken are counted as dropped.
LiveGps gives the newest speed while it is at most STALE_S old, else NaN (no speed: no legal distance threshold).
"""
import csv
import math
import threading

import cv2
import numpy as np

from .model import MODEL_DT

TICK_TOL_S = .015   # a frame this much before the next tick is taken (30 fps phones: 50 ms on average)


class FrameSource:
    WAIT_S = 10.0   # no new frame for this long: the phone is gone and the run ends (4G drops for seconds)

    def __init__(self):
        self.cond = threading.Condition()
        self.latest = None    # (pts, yuv420p array (h * 3 / 2, w)), not taken yet
        self.size = None      # (w, h) of the first frame; later frames are scaled to it
        self.closed = False
        self.dropped = 0
        self.received = 0
        self.due = None       # session time of the next model tick

    def push(self, img, pts):
        """A decoded yuv420p frame (av VideoFrame.to_ndarray(format='yuv420p')) that arrived at session time pts."""
        h, w = img.shape[0] * 2 // 3, img.shape[1]
        with self.cond:
            if self.size is None:
                self.size = (w // 2 * 2, h // 2 * 2)
            if (w, h) != self.size:   # WebRTC changes the resolution with the bandwidth
                bgr = cv2.cvtColor(img[:h * 3 // 2 // 2 * 2, :w // 2 * 2] if w % 2 or h % 2 else img, cv2.COLOR_YUV2BGR_I420)
                img = cv2.cvtColor(cv2.resize(bgr, self.size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2YUV_I420)
            if self.latest is not None:
                self.dropped += 1
            self.latest = (float(pts), img)
            self.received += 1
            self.cond.notify_all()

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()

    def wait_size(self, stop, timeout=None):
        """(w, h) of the camera picture once the first frame is in (3 x WAIT_S); RuntimeError when none comes."""
        with self.cond:
            self.cond.wait_for(lambda: self.size is not None or self.closed or stop.is_set(),
                               3 * self.WAIT_S if timeout is None else timeout)
            if self.size is None:
                raise RuntimeError('không nhận được hình từ điện thoại')
            return self.size

    def poll(self):
        """((y, u, v), pts) when the newest frame is due for a model tick, else None (never blocks)."""
        with self.cond:
            if self.latest is None:
                return None
            pts, img = self.latest
            if self.due is not None and pts < self.due - TICK_TOL_S:
                return None
            self.latest = None
            # on the 20 Hz grid while the run keeps up; after a slow tick, the grid starts again at this frame
            self.due = pts + MODEL_DT if self.due is None or pts >= self.due + MODEL_DT else self.due + MODEL_DT
        w, h = self.size
        flat = img.reshape(-1)
        y = flat[:w * h].reshape(h, w)
        u = flat[w * h:w * h * 5 // 4].reshape(h // 2, w // 2)
        v = flat[w * h * 5 // 4:w * h * 3 // 2].reshape(h // 2, w // 2)
        return (y, u, v), pts

    def frames(self, stop):
        """Yield ((y, u, v), pts) per model tick until the phone disconnects, stop is set or no frame comes."""
        while not stop.is_set():
            f = self.poll()
            if f is not None:
                yield f
                continue
            with self.cond:
                if self.closed:
                    return
                received = self.received
                if not self.cond.wait_for(lambda: self.received != received or self.closed or stop.is_set(),
                                          self.WAIT_S):
                    return
                if self.received == received:   # closed or stopped
                    continue


class LiveGps:
    """Ego speed from the phone's GPS on the session clock; the interface of gps.GpsRef that the run uses."""
    STALE_S = 3.0          # older than this: no speed (as gps.speed_at across gaps > 3 s)
    MAX_ACCURACY_M = 50.0  # horizontal accuracy worse than this: the fix is ignored
    MAX_SPEED = 90.0       # m/s, as gps.load_gps

    synced, low_confidence, offset, corr = True, False, 0.0, math.nan   # same clock as the frames: nothing to align

    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []   # (t, speed_mps, lat, lon, accuracy_m)

    @property
    def count(self):
        """Fixes with a usable speed."""
        return sum(math.isfinite(r[1]) for r in self.rows)

    def add(self, t, fix):
        """A fix {speed (m/s, null or < 0 if unknown), lat, lon, acc (m)} that arrived at session time t."""
        try:
            lat, lon, acc = float(fix['lat']), float(fix['lon']), float(fix['acc'])
            speed = fix.get('speed')
            speed = None if speed is None or float(speed) < 0 else float(speed)
        except (TypeError, KeyError, ValueError, AttributeError):
            return
        if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(acc)) or acc > self.MAX_ACCURACY_M:
            return
        with self.lock:
            if speed is None and self.rows:   # iOS gives no speed on some fixes: from the previous position
                t0, _, lat0, lon0, _ = self.rows[-1]
                if t > t0:
                    speed = _haversine(lat0, lon0, lat, lon) / (t - t0)
            if speed is None or not math.isfinite(speed) or speed > self.MAX_SPEED:
                if speed is None and not self.rows:   # first fix without speed: kept for the next one's position
                    self.rows.append((float(t), math.nan, lat, lon, acc))
                return
            self.rows.append((float(t), speed, lat, lon, acc))

    def observe(self, pts, v_model):
        """Nothing to align: the fixes are stamped on the session clock."""

    def __call__(self, pts):
        with self.lock:
            for t, speed, *_ in reversed(self.rows):
                if t <= pts + 1e-9 and math.isfinite(speed):
                    return speed if pts - t <= self.STALE_S else math.nan
        return math.nan

    def save(self, path):
        with self.lock, open(path, 'w', newline='') as fh:
            w = csv.writer(fh, lineterminator='\n')
            w.writerow(['t', 'speed_mps', 'lat', 'lon', 'accuracy_m'])
            for t, speed, lat, lon, acc in self.rows:
                if math.isfinite(speed):
                    w.writerow([f'{t:.3f}', f'{speed:.3f}', f'{lat:.7f}', f'{lon:.7f}', f'{acc:.1f}'])


def _haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return float(2 * 6371000.0 * np.arcsin(np.sqrt(a)))
