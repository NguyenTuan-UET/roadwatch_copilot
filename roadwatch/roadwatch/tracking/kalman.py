"""Constant-velocity Kalman filter on (cx, cy, w, h) boxes, as in BoT-SORT.

Noise is proportional to the box size, so small (far) and large (near) boxes
are tracked equally well. Time unit: one frame.
"""

from __future__ import annotations

import numpy as np

_STD_POS = 1.0 / 20
_STD_VEL = 1.0 / 160

_F = np.eye(8)
_F[:4, 4:] = np.eye(4)
_H = np.eye(4, 8)


def xyxy_to_cxcywh(b) -> np.ndarray:
    x1, y1, x2, y2 = b
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], float)


def cxcywh_to_xyxy(m) -> tuple[float, float, float, float]:
    cx, cy, w, h = m[:4]
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


class KalmanBox:
    """State: mean (8,) = (cx, cy, w, h, vcx, vcy, vw, vh), cov (8, 8)."""

    def __init__(self, xyxy):
        m = xyxy_to_cxcywh(xyxy)
        self.mean = np.r_[m, np.zeros(4)]
        w, h = m[2], m[3]
        std = [2 * _STD_POS * w, 2 * _STD_POS * h, 2 * _STD_POS * w, 2 * _STD_POS * h,
               10 * _STD_VEL * w, 10 * _STD_VEL * h, 10 * _STD_VEL * w, 10 * _STD_VEL * h]
        self.cov = np.diag(np.square(std))

    def predict(self) -> None:
        w, h = max(self.mean[2], 1.0), max(self.mean[3], 1.0)
        q = np.square([_STD_POS * w, _STD_POS * h, _STD_POS * w, _STD_POS * h,
                       _STD_VEL * w, _STD_VEL * h, _STD_VEL * w, _STD_VEL * h])
        self.mean = _F @ self.mean
        self.cov = _F @ self.cov @ _F.T + np.diag(q)
        self.mean[2:4] = np.maximum(self.mean[2:4], 1.0)

    def update(self, xyxy) -> None:
        z = xyxy_to_cxcywh(xyxy)
        w, h = max(self.mean[2], 1.0), max(self.mean[3], 1.0)
        r = np.diag(np.square([_STD_POS * w, _STD_POS * h, _STD_POS * w, _STD_POS * h]))
        s = _H @ self.cov @ _H.T + r
        k = np.linalg.solve(s, _H @ self.cov).T  # cov is symmetric
        self.mean = self.mean + k @ (z - _H @ self.mean)
        self.cov = self.cov - k @ s @ k.T
        self.mean[2:4] = np.maximum(self.mean[2:4], 1.0)

    def warp(self, affine: np.ndarray) -> None:
        """Apply a 2x3 camera-motion affine to the state (positions, sizes, velocities)."""
        a = affine[:, :2]
        big = np.kron(np.eye(4), a)
        self.mean = big @ self.mean
        self.mean[:2] += affine[:, 2]
        self.cov = big @ self.cov @ big.T
        # A similarity (rotation + scale) may leave w/h mixed slightly; keep them positive.
        self.mean[2:4] = np.maximum(np.abs(self.mean[2:4]), 1.0)

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return cxcywh_to_xyxy(self.mean)
