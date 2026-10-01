"""ByteTrack-style multi-object tracker with camera-motion compensation.

Per frame:
  1. Kalman-predict every track, then warp tracks and their box histories by
     the camera motion (GMC) so ego rotation does not look like object motion.
  2. High-confidence detections vs confirmed + lost tracks (IoU fused with score).
  3. Low-confidence detections vs the still-unmatched tracked tracks (recovers
     partly occluded objects instead of dropping them).
  4. Remaining high detections vs tentative tracks; unmatched tentative tracks die.
  5. Remaining detections >= new_track_thr start tentative tracks.
Tracks are confirmed after `min_hits` matches and deleted after `max_lost_s`
without one. Matches across class groups (person / two-wheeler / four-wheeler)
are forbidden; within a group the class is a confidence-weighted vote.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from roadwatch.config import CLASS_GROUPS, TrackerConfig
from roadwatch.tracking.gmc import CameraMotion
from roadwatch.tracking.kalman import KalmanBox
from roadwatch.tracking.kinematics import Kinematics, estimate_kinematics
from roadwatch.types import Detection

__all__ = ["CLASS_GROUPS", "ByteTracker", "TrackedObject", "class_group", "iou_matrix"]


def class_group(cls: str) -> str:
    return CLASS_GROUPS.get(cls, cls)


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU between (N, 4) and (M, 4) xyxy boxes."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    ix1 = np.maximum(a[:, None, 0], b[None, :, 0])
    iy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    ix2 = np.minimum(a[:, None, 2], b[None, :, 2])
    iy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)


@dataclass
class TrackedObject:
    """Snapshot of a confirmed track for one frame (safe to keep; nothing is shared)."""

    track_id: int
    xyxy: tuple[float, float, float, float]  # observed box, or Kalman prediction if not observed
    cls: str
    conf: float  # of the last matched detection
    observed: bool  # matched a detection in this frame
    age_s: float  # since the track started
    lost_frames: int  # frames since the last match (0 if observed)
    kinematics: Kinematics | None  # None until enough temporal evidence
    history: np.ndarray  # (N, 5) ts, x1, y1, x2, y2 of observed boxes, current-frame coords
    # (N, 4) the same boxes as detected, without camera-motion compensation (sizes for tau)
    raw_history: np.ndarray | None = None

    @property
    def group(self) -> str:
        return class_group(self.cls)


class _Track:
    def __init__(self, det: Detection, ts: float, history_len: int):
        self.id = 0  # assigned on confirmation, so ids on screen stay small and contiguous
        self.kf = KalmanBox(det.xyxy)
        self.votes: Counter[str] = Counter({det.cls: det.conf})
        self.group = class_group(det.cls)
        self.conf = det.conf
        self.hits = 1
        self.confirmed = False
        self.lost_frames = 0
        self.start_ts = ts
        self.last_ts = ts
        self.history_len = history_len
        self.history = np.array([[ts, *det.xyxy]], float)  # (N, 5), oldest first
        self.raw = np.array([det.xyxy], float)  # (N, 4), never warped
        self.observed = True

    @property
    def cls(self) -> str:
        return self.votes.most_common(1)[0][0]

    def match(self, det: Detection, ts: float) -> None:
        self.kf.update(det.xyxy)
        self.votes[det.cls] += det.conf
        self.conf = det.conf
        self.hits += 1
        self.lost_frames = 0
        self.last_ts = ts
        self.history = np.vstack([self.history[-(self.history_len - 1):], [ts, *det.xyxy]])
        self.raw = np.vstack([self.raw[-(self.history_len - 1):], det.xyxy])
        self.observed = True

    def warp(self, affine: np.ndarray) -> None:
        self.kf.warp(affine)
        h = self.history
        s = float(np.sqrt(abs(np.linalg.det(affine[:, :2]))))
        c = ((h[:, 1:3] + h[:, 3:5]) / 2) @ affine[:, :2].T + affine[:, 2]
        half = s * (h[:, 3:5] - h[:, 1:3]) / 2
        h[:, 1:3] = c - half
        h[:, 3:5] = c + half


class ByteTracker:
    def __init__(self, config: TrackerConfig | None = None):
        self.cfg = config or TrackerConfig()
        self.gmc = CameraMotion(self.cfg.gmc_downscale_width, self.cfg.gmc_max_corners) \
            if self.cfg.use_gmc else None
        self.reset()

    def reset(self) -> None:
        """New session: forget all tracks, ids restart at 1."""
        self._tracks: list[_Track] = []
        self._next_id = 1
        self.last_affine = np.eye(2, 3)
        if self.gmc is not None:
            self.gmc.reset()

    # -- association ----------------------------------------------------
    def _match(self, tracks: list[_Track], dets: list[Detection], max_cost: float,
               fuse_score: bool) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        if not tracks or not dets:
            return [], list(range(len(tracks))), list(range(len(dets)))
        tb = np.array([t.kf.xyxy for t in tracks])
        db = np.array([d.xyxy for d in dets])
        sim = iou_matrix(tb, db)
        if fuse_score:
            sim = sim * np.array([d.conf for d in dets])[None, :]
        cost = 1.0 - sim
        groups_t = np.array([t.group for t in tracks])[:, None]
        groups_d = np.array([class_group(d.cls) for d in dets])[None, :]
        cost[groups_t != groups_d] = 1e6
        rows, cols = linear_sum_assignment(cost)
        pairs = [(r, c) for r, c in zip(rows, cols) if cost[r, c] <= max_cost]
        mt = {r for r, _ in pairs}
        md = {c for _, c in pairs}
        return (pairs, [i for i in range(len(tracks)) if i not in mt],
                [j for j in range(len(dets)) if j not in md])

    def _confirm(self, t: _Track) -> None:
        t.confirmed = True
        t.id = self._next_id
        self._next_id += 1

    # -- main entry -----------------------------------------------------
    def update(self, dets: list[Detection], ts: float, image: np.ndarray | None = None
               ) -> list[TrackedObject]:
        cfg = self.cfg
        for t in self._tracks:
            t.kf.predict()
            t.observed = False

        if self.gmc is not None and image is not None:
            boxes = np.array([d.xyxy for d in dets], float).reshape(-1, 4)
            self.last_affine = self.gmc.estimate(image, boxes)
            for t in self._tracks:
                t.warp(self.last_affine)

        high = [d for d in dets if d.conf >= cfg.high_conf_thr]
        low = [d for d in dets if cfg.low_conf_thr <= d.conf < cfg.high_conf_thr]

        pool = [t for t in self._tracks if t.confirmed]
        tentative = [t for t in self._tracks if not t.confirmed]

        pairs, un_t, un_d = self._match(pool, high, cfg.match_thr, fuse_score=True)
        for i, j in pairs:
            pool[i].match(high[j], ts)
        high_left = [high[j] for j in un_d]

        # Stage 2: only tracks that were being tracked last frame (not already lost).
        second = [pool[i] for i in un_t if pool[i].lost_frames == 0]
        pairs2, _, _ = self._match(second, low, cfg.low_match_thr, fuse_score=False)
        for i, j in pairs2:
            second[i].match(low[j], ts)

        pairs3, un_tent, un_d3 = self._match(tentative, high_left, cfg.unconfirmed_match_thr,
                                             fuse_score=True)
        for i, j in pairs3:
            tentative[i].match(high_left[j], ts)
            if tentative[i].hits >= cfg.min_hits:
                self._confirm(tentative[i])
        dead = {id(tentative[i]) for i in un_tent}

        for t in self._tracks:
            if not t.observed:
                t.lost_frames += 1
        self._tracks = [t for t in self._tracks
                        if id(t) not in dead and ts - t.last_ts <= cfg.max_lost_s]

        for j in un_d3:
            d = high_left[j]
            if d.conf >= cfg.new_track_thr:
                t = _Track(d, ts, cfg.history_len)
                if cfg.min_hits <= 1:
                    self._confirm(t)
                self._tracks.append(t)

        return self._snapshot(ts, image.shape[:2] if image is not None else None)

    def _snapshot(self, ts: float, image_hw: tuple[int, int] | None) -> list[TrackedObject]:
        cfg = self.cfg
        out = []
        for t in self._tracks:
            if not t.confirmed or t.lost_frames > cfg.coast_frames:
                continue
            hist = t.history.copy()
            raw = t.raw.copy()
            kin = None
            if image_hw is not None:
                kin = estimate_kinematics(hist, image_hw, cfg.kin_window_s, cfg.kin_min_points,
                                          cfg.kin_min_span_s, cfg.border_margin_px, raw=raw)
            out.append(TrackedObject(
                track_id=t.id,
                xyxy=tuple(float(v) for v in (hist[-1, 1:] if t.observed else t.kf.xyxy)),
                cls=t.cls,
                conf=t.conf,
                observed=t.observed,
                age_s=ts - t.start_ts,
                lost_frames=t.lost_frames,
                kinematics=kin,
                history=hist,
                raw_history=raw,
            ))
        return out
