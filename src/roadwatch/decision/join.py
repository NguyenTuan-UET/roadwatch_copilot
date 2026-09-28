"""Join (spec §3.3): speed freshness under the information cutoff, legal threshold, headway. Pure."""

from collections import deque
from dataclasses import dataclass

from ..contracts.base import Q
from ..contracts.config import LegalTable, Speed
from ..contracts.streams import SpeedSample, SpeedUsed

MS = 1_000_000


@dataclass(frozen=True)
class SpeedView:
    sample: SpeedSample | None
    status: str  # fresh | stale | lost
    age_ms: float | None

    @property
    def mps(self) -> float | None:
        return self.sample.speed_mps.value if self.sample is not None else None

    def used(self) -> SpeedUsed:
        return SpeedUsed(gps_idx=self.sample.gps_idx if self.sample else None, age_ms=self.age_ms, status=self.status)


class SpeedTracker:
    """Keeps recently consumed samples; a sample counts for frame k only if t_recv <= t_k."""

    def __init__(self, cfg: Speed):
        self.cfg = cfg
        self.recent: deque[SpeedSample] = deque(maxlen=16)

    def update(self, s: SpeedSample) -> None:
        if s.speed_mps.usable:
            self.recent.append(s)

    def at(self, t_k: int) -> SpeedView:
        usable = [s for s in self.recent if s.t_recv_ns <= t_k]
        if not usable:
            return SpeedView(None, "lost", None)
        s = max(usable, key=lambda x: x.t_fix_ns)
        age_ms = (t_k - s.t_fix_ns) / MS
        if age_ms <= self.cfg.fresh_max_ms:
            status = "fresh"
        elif age_ms <= self.cfg.lost_after_ms:
            status = "stale"
        else:
            status = "lost"
        return SpeedView(s, status, age_ms)


def legal_threshold(table: LegalTable, margin_m: float, sv: SpeedView) -> Q:
    """MVP stale policy is `unusable` (ADR-06): only fresh speed selects a legal band."""
    if sv.status == "lost":
        return Q.missing("unavailable", "speed_lost")
    if sv.status == "stale":
        return Q.missing("unreliable", "speed_stale")
    kmh = sv.mps * 3.6
    last = table.bands[-1]
    for b in table.bands:
        if b.v_min_kmh <= kmh < b.v_max_kmh or (b is last and kmh == b.v_max_kmh):
            return Q.ok(b.min_distance_m + margin_m)
    return Q.missing("not_applicable", "speed_outside_legal_table")  # F17: outside supported scope


def headway(distance: Q, sv: SpeedView) -> Q:
    if not distance.usable:
        return Q.missing("unavailable", "no_distance")
    if sv.status != "fresh":
        return Q.missing("unavailable", f"speed_{sv.status}")
    if sv.mps < 1.0:
        return Q.missing("not_applicable", "vehicle_stopped")
    return Q.ok(distance.value / sv.mps)
