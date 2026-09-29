"""Ego corridor in image space: where the car will be if it keeps its lane.

Borders are straight lines x = a*y + b converging at the horizon. From a good
lane result they are fitted to the lane borders; otherwise a default corridor
around the image centre is used. The horizon row is learned from the vanishing
point of good lane lines (EMA) and defaults to RiskConfig.default_horizon_frac.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from roadwatch.config import RiskConfig


@dataclass
class Corridor:
    left: tuple[float, float]  # (a, b) with x = a*y + b
    right: tuple[float, float]
    horizon_y: float
    image_hw: tuple[int, int]
    source: str  # "lane" | "default"

    def bounds(self, y: float) -> tuple[float, float] | None:
        """(x_left, x_right) at row y, or None above the horizon."""
        if y <= self.horizon_y + 1:
            return None
        xl = self.left[0] * y + self.left[1]
        xr = self.right[0] * y + self.right[1]
        return (xl, xr) if xr - xl > 1 else None

    def depth(self, y: float) -> float:
        """0 at the horizon, 1 at the bottom row (inverse distance on a flat road)."""
        h = self.image_hw[0]
        return float(np.clip((y - self.horizon_y) / max(h - self.horizon_y, 1.0), 0.0, 1.0))

    def lateral(self, x: float, y: float) -> float | None:
        """Lateral position in lane widths: 0 = corridor centre, +-0.5 = its borders."""
        b = self.bounds(y)
        if b is None:
            return None
        return (x - (b[0] + b[1]) / 2) / (b[1] - b[0])

    def polygon(self) -> np.ndarray:
        """Corridor outline (4 points) from the bottom row up to near the horizon, for drawing."""
        h = self.image_hw[0]
        y0 = self.horizon_y + 0.15 * (h - self.horizon_y)
        pts = []
        for y in (h - 1, y0):
            pts.append((self.left[0] * y + self.left[1], y))
        for y in (y0, h - 1):
            pts.append((self.right[0] * y + self.right[1], y))
        return np.array(pts, np.int32)


def _line_through(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
    (x0, y0), (x1, y1) = p, q
    a = (x1 - x0) / (y1 - y0)
    return a, x0 - a * y0


class CorridorEstimator:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._horizon_frac: float | None = None

    def horizon_y(self, h: int) -> float:
        return (self._horizon_frac or self.cfg.default_horizon_frac) * h

    def default(self, image_hw: tuple[int, int]) -> Corridor:
        h, w = image_hw
        hy = self.horizon_y(h)
        vp = (w / 2, hy)
        half = self.cfg.default_half_width_frac * w
        return Corridor(_line_through(vp, (w / 2 - half, h)), _line_through(vp, (w / 2 + half, h)),
                        hy, image_hw, "default")

    def from_lane(self, lane, image_hw: tuple[int, int]) -> Corridor | None:
        """Corridor from a LaneState (caller checks quality/freshness), or None."""
        h, w = image_hw
        rows = [(lx, rx, y) for lx, rx, y in zip(lane.left_x, lane.right_x, lane.scan_y)
                if lx is not None and rx is not None]
        if not rows:
            return None
        if len(rows) >= 2:
            ys = np.array([r[2] for r in rows], float)
            al, bl = np.polyfit(ys, [r[0] for r in rows], 1)
            ar, br = np.polyfit(ys, [r[1] for r in rows], 1)
            if al < 0 < ar:  # borders converge going up
                vy = (br - bl) / (al - ar)
                lo, hi = self.cfg.horizon_range_frac
                if lo * h <= vy <= hi * h:
                    a = self.cfg.horizon_ema_alpha
                    f = vy / h
                    self._horizon_frac = f if self._horizon_frac is None else \
                        a * f + (1 - a) * self._horizon_frac
                    return Corridor((al, bl), (ar, br), self.horizon_y(h), image_hw, "lane")
        # One usable row (or implausible fit): lines from the lowest row to the vanishing point.
        lx, rx, y = max(rows, key=lambda r: r[2])
        hy = self.horizon_y(h)
        if y <= hy + 1:
            return None
        vp = ((lx + rx) / 2, hy)
        return Corridor(_line_through(vp, (lx, y)), _line_through(vp, (rx, y)), hy, image_hw,
                        "lane")
