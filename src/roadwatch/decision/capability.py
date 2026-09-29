"""Warning capabilities (spec §3.4, ADR-05/10): cap_distance and cap_ttc, each with reasons and an epoch."""

from collections import deque

from ..contracts.config import RwConfig
from ..contracts.streams import Measurement, SystemEvent
from .join import SpeedView

MS = 1_000_000


class Capabilities:
    def __init__(self, cfg: RwConfig, mount_checklist: bool):
        self.cfg = cfg
        self.p = cfg.perception
        self.distance_off: set[str] = set()
        self.ttc_off: set[str] = set()
        self.epoch = 0
        self.fault = False
        self.last_meas_t: int | None = None
        self.first_t: int | None = None
        self.checklist = mount_checklist
        self.trust_until: int | None = None  # set on the first measurement when a checklist exists
        self.latched = False
        self.prev_mount: str | None = None
        self.suspects: deque[int] = deque()
        self.ok_obs_times: deque[int] = deque()

    @property
    def pair(self) -> tuple[str, str]:
        return ("off" if self.distance_off else "on", "off" if self.ttc_off else "on")

    def _commit(self, dist: set[str], ttc: set[str]) -> None:
        before = self.pair
        self.distance_off, self.ttc_off = dist, ttc
        if self.pair != before:
            self.epoch += 1

    def _mount_reasons(self, m: Measurement, t: int) -> set[str]:
        if not self.p.mount_enabled:
            return set()  # ADR-05 flag-off: checklist only, reported as a known limitation
        state = m.mount_check.state
        if state == "suspect" and self.prev_mount != "suspect":
            self.suspects.append(t)
        self.prev_mount = state
        while self.suspects and t - self.suspects[0] > self.p.mount_flap_window_ms * MS:
            self.suspects.popleft()
        if len(self.suspects) >= self.p.mount_flap_n:
            self.latched = True
        if state == "ok":
            self.trust_until = t + self.p.mount_trust_window_ms * MS
        if self.latched:
            return {"mount_latched"}
        if state == "suspect":
            return {"mount_suspect"}
        if state == "unknown" and (self.trust_until is None or t > self.trust_until):
            return {"mount_unverified"}
        return set()

    def on_measurement(self, m: Measurement, t_k: int, sv: SpeedView) -> None:
        if self.first_t is None:
            self.first_t = t_k
            if self.checklist:
                self.trust_until = t_k + self.p.mount_trust_window_ms * MS
        self.last_meas_t = t_k
        common: set[str] = {"system_fault"} if self.fault else set()
        if m.observation.status != "ok":
            common.add(f"observation_{m.observation.status}")
        else:
            self.ok_obs_times.append(t_k)
        while self.ok_obs_times and t_k - self.ok_obs_times[0] > 1000 * MS:
            self.ok_obs_times.popleft()
        mount = self._mount_reasons(m, t_k)
        dist = common | mount
        if sv.status == "lost":
            dist.add("speed_lost")
        ttc = set(common)
        if mount and m.lead.basis != "lane_markings":
            ttc |= mount  # with a bad mount only a lane-marking lead choice is trusted for TTC
        warm = t_k - self.first_t >= 1000 * MS
        if warm and len(self.ok_obs_times) < self.cfg.ttc.min_ttc_rate_hz:
            ttc.add("low_rate")
        self._commit(dist, ttc)

    def on_event(self, e: SystemEvent, t: int) -> None:
        if e.kind == "system_fault":
            self.fault = True
            self._commit(self.distance_off | {"system_fault"}, self.ttc_off | {"system_fault"})
        elif e.kind == "mount_rechecked":
            self.latched = False
            self.suspects.clear()
            self.trust_until = t + self.p.mount_trust_window_ms * MS
            drop = {"mount_latched", "mount_unverified"}
            self._commit(self.distance_off - drop, self.ttc_off - drop)

    def on_tick(self, t: int) -> None:
        gap = self.last_meas_t is not None and t - self.last_meas_t > self.cfg.runtime.max_measurement_gap_ms * MS
        if gap:
            self._commit(self.distance_off | {"measurement_gap"}, self.ttc_off | {"measurement_gap"})
