"""Global (camera) motion compensation between consecutive frames.

Sparse optical flow on background corners (detected objects masked out),
fitted with a RANSAC similarity transform, as in BoT-SORT's "sparseOptFlow".
The 2x3 affine maps previous-frame pixels to current-frame pixels.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

log = logging.getLogger(__name__)

IDENTITY = np.eye(2, 3)


class CameraMotion:
    def __init__(self, downscale_width: int = 640, max_corners: int = 400,
                 min_inliers: int = 12):
        self.downscale_width = downscale_width
        self.max_corners = max_corners
        self.min_inliers = min_inliers
        self._prev_gray: np.ndarray | None = None
        self._prev_pts: np.ndarray | None = None
        self._scale = 1.0

    def reset(self) -> None:
        self._prev_gray = None
        self._prev_pts = None

    def _prepare(self, img_bgr: np.ndarray) -> np.ndarray:
        h, w = img_bgr.shape[:2]
        self._scale = min(1.0, self.downscale_width / w)
        small = img_bgr if self._scale == 1.0 else cv2.resize(
            img_bgr, (round(w * self._scale), round(h * self._scale)),
            interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    def _features(self, gray: np.ndarray, boxes: np.ndarray) -> np.ndarray | None:
        h, w = gray.shape
        mask = np.zeros_like(gray)
        my, mx = int(0.02 * h), int(0.02 * w)
        mask[my:h - my, mx:w - mx] = 255
        for x1, y1, x2, y2 in (boxes * self._scale).astype(int):
            mask[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = 0
        return cv2.goodFeaturesToTrack(gray, self.max_corners, 0.01, 5, mask=mask, blockSize=3)

    def estimate(self, img_bgr: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """Affine (2x3, full-resolution pixels) from the previous frame to this one.

        `boxes` (N, 4 xyxy) are excluded from feature detection: moving objects
        must not drive the camera estimate. Returns identity on the first frame
        or when too few background features agree.
        """
        gray = self._prepare(img_bgr)
        affine = IDENTITY.copy()
        prev_gray, prev_pts = self._prev_gray, self._prev_pts
        if prev_gray is not None and prev_pts is not None and prev_gray.shape == gray.shape:
            nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_pts, None)
            ok = status.ravel() == 1
            if ok.sum() >= self.min_inliers:
                m, inliers = cv2.estimateAffinePartial2D(
                    prev_pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
                if m is not None and inliers is not None and inliers.sum() >= self.min_inliers:
                    affine = m
                    affine[:, 2] /= self._scale
        self._prev_gray = gray
        self._prev_pts = self._features(gray, np.asarray(boxes, float).reshape(-1, 4))
        return affine
