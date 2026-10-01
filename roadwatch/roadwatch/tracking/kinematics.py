"""Image-space kinematics of a track from its recent observed boxes.

Everything here is in pixels / seconds of the (camera-motion compensated)
image. There is no camera calibration, so no metres and no absolute TTC:
`tau_s` is the scale-expansion time-to-contact estimate (size / d size/dt),
valid only under a constant closing speed. Treat every value as an
uncalibrated estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Kinematics:
    vx_px_s: float  # box centre, + = right
    vy_px_s: float  # box bottom, + = down (towards the camera on a flat road)
    scale_rate: float  # d ln(size) / dt at the latest frame, 1/s; > 0 = growing (closing in)
    tau_s: float | None  # 1 / scale_rate when closing, else None (estimated, uncalibrated)
    n: int  # observations used
    span_s: float
    truncated: bool  # box cut by both a side and the top/bottom border: no size estimate
    size_from: str = "area"  # "area" | "width" (top/bottom cut) | "height" (side cut) | "none"

    uncalibrated: bool = True


def slope(t: np.ndarray, y: np.ndarray) -> float:
    """Least-squares slope dy/dt."""
    tc = t - t.mean()
    den = float(tc @ tc)
    return 0.0 if den <= 0 else float(tc @ (y - y.mean())) / den


def estimate_kinematics(history: np.ndarray, image_hw: tuple[int, int], window_s: float,
                        min_points: int, min_span_s: float, border_px: int,
                        min_closing_rate: float = 0.02,
                        raw: np.ndarray | None = None) -> Kinematics | None:
    """history: (N, 5) rows (ts, x1, y1, x2, y2), oldest first, all in current-frame
    coordinates. Returns None when there is not enough temporal evidence.

    raw: optional (N, 4) xyxy of the same observations as detected, in their own
    frame (no camera-motion compensation). Box size and border cuts are taken from
    it: the compensation is a similarity fit to the background, and when the ego
    car drives forward the background expands, so its scale would cancel (or
    invert) the expansion of a closing vehicle and make tau far too large.
    Positions (vx, vy) still come from the compensated history."""
    if len(history) < min_points:
        return None
    sel = history[:, 0] >= history[-1, 0] - window_s
    h = history[sel]
    if len(h) < min_points:
        return None
    t = h[:, 0]
    span = float(t[-1] - t[0])
    if span < min_span_s:
        return None
    # A border cuts one box dimension: measure size on the other one. A close lead
    # vehicle is typically cut at the bottom, and its width is still reliable.
    img_h, img_w = image_hw
    b = raw[sel] if raw is not None else h[:, 1:5]
    w = np.maximum(b[:, 2] - b[:, 0], 1.0)
    hh = np.maximum(b[:, 3] - b[:, 1], 1.0)
    cut_x = bool(((b[:, 0] <= border_px) | (b[:, 2] >= img_w - border_px)).any())
    cut_y = bool(((b[:, 1] <= border_px) | (b[:, 3] >= img_h - border_px)).any())
    size_from = {(False, False): "area", (False, True): "width",
                 (True, False): "height", (True, True): "none"}[(cut_x, cut_y)]
    size = {"area": np.sqrt(w * hh), "width": w, "height": hh, "none": np.sqrt(w * hh)}[size_from]
    # Under a constant closing speed the inverse size falls linearly to 0 at contact,
    # so a line fit of 1/size gives tau at the *latest* frame (a fit of ln(size)
    # would give it at the window centre, i.e. half a window too late).
    inv = 1.0 / size
    b = slope(t, inv)
    inv_now = float(inv.mean() + b * (t[-1] - t.mean()))
    scale_rate = -b / inv_now if inv_now > 0 else 0.0
    truncated = size_from == "none"
    tau = 1.0 / scale_rate if scale_rate > min_closing_rate and not truncated else None
    return Kinematics(
        vx_px_s=slope(t, (h[:, 1] + h[:, 3]) / 2),
        vy_px_s=slope(t, h[:, 4]),
        scale_rate=scale_rate,
        tau_s=tau,
        n=len(h),
        span_s=span,
        truncated=truncated,
        size_from=size_from,
    )
