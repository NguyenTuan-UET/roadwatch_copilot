"""Sign relevance, temporal confirmation and speed-limit arbitration.

Relevance: a reading counts only if its box is large enough to read and it is
on the right side of the road or overhead (right-hand traffic; left-side signs
usually face the other direction).

Confirmation: a sign (model class; for speed limits the read value) is
confirmed when it appears in >= sign_confirm_hits distinct sign results
within sign_window_s. A sign result reused across frames counts once.

Arbitration of speed-limit values: each reading votes with
    det_conf * (cls_conf * sign_classifier_weight   if read by the digit classifier
                sign_detector_class_weight          if taken from the class name)
             * sign_disagree_weight                  if classifier and class disagree.
Among confirmed values in the window the highest total wins, but only with at
least `sign_margin` x the runner-up; otherwise the limit is left unchanged and
marked ambiguous. The active limit persists after the sign passes, until a new
confirmed limit or an end sign (group speed_limit_end, or code 135 "end of all
prohibitions").
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from roadwatch.config import RiskConfig

END_ALL_CODES = {"135"}


@dataclass
class SpeedLimit:
    value: int
    since_ts: float
    confidence: float  # winner votes / all speed votes in the window
    ambiguous: bool = False  # a conflicting reading is currently too close to call


@dataclass
class ConfirmedSign:
    code: str
    sign_cls: str
    group: str
    name_vi: str
    speed_value: int | None
    ts: float  # when it was (last) confirmed


@dataclass
class SignState:
    speed_limit: SpeedLimit | None
    recent: list[ConfirmedSign] = field(default_factory=list)
    new: list[ConfirmedSign] = field(default_factory=list)  # confirmed in this update


def _key(r) -> tuple:
    return ("speed", r.speed_value) if r.is_speed_limit else ("sign", r.sign_cls)


class SignArbiter:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._obs: deque[tuple[float, tuple, float, object]] = deque()
        self._last_seq: int | None = None
        self._confirmed: dict[tuple, ConfirmedSign] = {}
        self._limit: SpeedLimit | None = None

    def relevant(self, r, image_hw: tuple[int, int]) -> bool:
        h, w = image_hw
        x1, y1, x2, y2 = r.xyxy
        if y2 - y1 < self.cfg.sign_min_box_px:
            return False
        return (x1 + x2) / 2 >= self.cfg.sign_min_x_frac * w or y2 <= self.cfg.sign_overhead_y_frac * h

    def weight(self, r) -> float:
        cfg = self.cfg
        if r.source == "digit_classifier":
            wt = r.det_conf * (r.cls_conf or 0.0) * cfg.sign_classifier_weight
        else:
            wt = r.det_conf * cfg.sign_detector_class_weight
        if r.agree is False:
            wt *= cfg.sign_disagree_weight
        return wt

    def update(self, ts: float, readings, result_seq: int | None,
               image_hw: tuple[int, int]) -> SignState:
        cfg = self.cfg
        if readings is not None and result_seq is not None and result_seq != self._last_seq:
            self._last_seq = result_seq
            seen: set[tuple] = set()
            for r in readings:
                if not self.relevant(r, image_hw):
                    continue
                k = _key(r)
                if k in seen:  # one vote per sign per result; keep the first (highest conf)
                    continue
                seen.add(k)
                self._obs.append((ts, k, self.weight(r), r))
        while self._obs and self._obs[0][0] < ts - cfg.sign_window_s:
            self._obs.popleft()

        hits: dict[tuple, int] = {}
        votes: dict[tuple, float] = {}
        latest: dict[tuple, object] = {}
        for _, k, wt, r in self._obs:
            hits[k] = hits.get(k, 0) + 1
            votes[k] = votes.get(k, 0.0) + wt
            latest[k] = r
        confirmed = {k for k, n in hits.items() if n >= cfg.sign_confirm_hits}

        new: list[ConfirmedSign] = []
        for k in confirmed:
            r = latest[k]
            cs = ConfirmedSign(r.code, r.sign_cls, r.group, r.name_vi,
                               r.speed_value if r.is_speed_limit else None, ts)
            if k not in self._confirmed or ts - self._confirmed[k].ts > cfg.sign_window_s:
                new.append(cs)
            self._confirmed[k] = cs
        self._confirmed = {k: c for k, c in self._confirmed.items()
                           if ts - c.ts <= cfg.sign_show_s}

        # End signs first, so an end sign and a new limit seen together leave the new limit.
        if any(c.group == "speed_limit_end" or c.code in END_ALL_CODES for c in new):
            self._limit = None
        speed = sorted(((votes[k], k[1]) for k in confirmed if k[0] == "speed" and k[1] is not None),
                       reverse=True)
        if speed:
            total = sum(v for k, v in votes.items() if k[0] == "speed")
            (best, value), runner = speed[0], (speed[1][0] if len(speed) > 1 else 0.0)
            if best >= cfg.sign_margin * runner:
                if self._limit is None or self._limit.value != value:
                    self._limit = SpeedLimit(value, ts, best / total)
                else:
                    self._limit.confidence = best / total
                    self._limit.ambiguous = False
            elif self._limit is not None:
                self._limit.ambiguous = True

        recent = sorted(self._confirmed.values(), key=lambda c: -c.ts)
        return SignState(self._limit, recent, new)
