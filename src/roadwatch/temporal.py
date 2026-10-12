"""Temporal modelling of the lead: motion from the previous frames, not from one picture.

gr14VinAI sees the last 5 frames (0.25 s), but its lead distance is still one tick's guess. MotionEstimator keeps
a sliding window of the recent lead distances and fits a straight line weighted by the model's std: the distance at
the latest sample (noise averaged out, motion-compensated), the range rate (< 0 when closing in) with its std, and a
short-horizon prediction. Through a short drop-out the fit is carried forward (coast); after a restart it takes over
from the caller's estimate gradually (Motion.weight), so the gap does not jump when the source changes. Pure functions of the inputs: time comes from the frame timestamps, never from the system clock.
"""
from collections import deque
from dataclasses import dataclass

import numpy as np

WINDOW_S = 2.0       # history used for the fit (comma2k19 sweep 1-3 s: best MAE and jitter together)
MIN_SAMPLES = 5
MAX_GAP_S = 0.5      # longer without a lead measurement: forget the history
JUMP_M = 8.          # |innovation| > max(JUMP_M, 30 % of the distance): a different vehicle (as LeadTracker)
RATE_STD_FLOOR = 0.3  # m/s: a straight-line fit on a short window is never certain below this
RAMP_SAMPLES = 20    # a new fit takes over from the caller's estimate over this many samples (1 s)


@dataclass(frozen=True)
class Motion:
    dist: float       # fitted camera->lead distance at the latest sample, m
    rate: float       # d(distance)/dt, m/s (< 0 closing in)
    rate_std: float
    t: float
    n: int = 0        # samples in the fit

    @property
    def weight(self):
        """Trust in the fit, 0..1: low right after a restart (few samples), 1 once the history is long enough."""
        return min(1., (self.n - MIN_SAMPLES + 1) / RAMP_SAMPLES)

    def predict(self, horizon_s):
        """Distance after horizon_s seconds at the fitted rate (constant velocity), floored at 0."""
        return max(0., self.dist + self.rate * horizon_s)


class MotionEstimator:
    def __init__(self, window_s=WINDOW_S):
        self.window_s = window_s
        self.hist = deque()   # (t, distance, std)
        self.last = None      # Motion of the latest fit

    def reset(self):
        self.hist.clear()
        self.last = None

    def coast(self, t):
        """No measurement at time t: the latest fit carried forward at its rate, or None after MAX_GAP_S
        (keeps the gap continuous through a short drop-out instead of falling back to another estimator)."""
        if self.last is None or not self.hist or t - self.hist[-1][0] > MAX_GAP_S:
            return None
        return Motion(self.last.dist + self.last.rate * (t - self.last.t), self.last.rate, self.last.rate_std, float(t),
                      self.last.n)

    def update(self, t, dist, std):
        """Add the lead distance measured at time t (s). Returns Motion, or None while the history is too short."""
        if self.hist:
            t0, d0, _ = self.hist[-1]
            if t - t0 > MAX_GAP_S or abs(dist - d0) > max(JUMP_M, .3 * dist):
                self.reset()
        self.hist.append((t, float(dist), max(float(std), .5)))
        while self.hist[0][0] < t - self.window_s:
            self.hist.popleft()
        if len(self.hist) < MIN_SAMPLES:
            return None
        ts, ds, ss = (np.array(c, float) for c in zip(*self.hist))
        fit = _line_fit(ts - t, ds, 1. / ss ** 2)
        if fit is None:
            return None
        self.last = Motion(float(fit[0]), float(fit[1]), float(max(fit[2], RATE_STD_FLOOR)), float(t), len(self.hist))
        return self.last


def _line_fit(x, d, w):
    """Weighted least squares d = a + b x -> (a, b, std of b), or None when degenerate."""
    sw, sx = w.sum(), (w * x).sum()
    sxx, sxd, sd = (w * x * x).sum(), (w * x * d).sum(), (w * d).sum()
    den = sw * sxx - sx ** 2
    if den <= 1e-9:
        return None
    return (sxx * sd - sx * sxd) / den, (sw * sxd - sx * sd) / den, np.sqrt(sw / den)
