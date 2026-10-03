"""Distance and emergency episodes (spec §3.5, §3.7), with HOLD that keeps memory but re-evaluates."""

from ..contracts.config import Dispatch, Ttc

MS = 1_000_000


class DistanceEpisode:
    """IDLE -> PENDING -> ALERTED -> CLEARING -> IDLE; HOLD on unusable data; SUSPENDED after T_hold."""

    def __init__(self, cfg: Dispatch):
        self.cfg = cfg
        self.state = "IDLE"
        self.identity: int | None = None
        self.since = 0  # PENDING start, shifted by time spent in HOLD
        self.clear_since: int | None = None
        self.hold_start = 0
        self.prev = "IDLE"
        self.last_alert: dict[int, int] = {}
        self.n = 0

    @property
    def episode_id(self) -> str:
        return f"d{self.n}"

    def _reset(self) -> None:
        self.state, self.clear_since = "IDLE", None

    def on_time(self, t: int) -> list[str]:
        if self.state == "HOLD" and t - self.hold_start > self.cfg.t_hold_ms * MS:
            self.state = "SUSPENDED"
            return ["hold_expired"]
        return []

    def hold(self, t: int) -> list[str]:
        """Data invalid, missing or too old, no threshold, or cap_distance off: keep the memory, say nothing."""
        if self.state in ("PENDING", "ALERTED", "CLEARING"):
            self.prev, self.state, self.hold_start = self.state, "HOLD", t
            return ["hold"]
        return []

    def step(self, t: int, identity: int | None, usable: bool, d: float | None, thr: float | None) -> tuple[bool, list]:
        """Returns (emit_warning, why). identity None means no lead: the episode just ends (not a HOLD)."""
        if identity is None:
            self._reset()
            self.identity = None
            return False, ["no_lead"]
        if identity != self.identity:
            self._reset()
            self.identity = identity
        why = self.on_time(t)
        if not usable:
            self.hold(t)
            return False, why + ["hold" if self.state == "HOLD" else "data_unusable"]
        h = self.cfg.h_m
        # A HOLD neither erases nor stops the clearing count (3.5, OQ-A5): time without data must not prolong
        # the silence. If T_clear ran out meanwhile, the episode is over before this frame is looked at.
        if self.state == "HOLD" and self.prev == "CLEARING" and t - self.clear_since >= self.cfg.t_clear_ms * MS:
            self._reset()
            why = why + ["cleared_in_hold"]
        if self.state == "HOLD":  # resumed within T_hold: keep memory, recompute the conclusion
            held = t - self.hold_start
            if self.prev == "PENDING":
                self.state = "PENDING" if d < thr else "IDLE"
                self.since += held
            elif d <= thr + h:
                self.state = "ALERTED"
            else:
                self.clear_since = self.clear_since if self.prev == "CLEARING" else t
                self.state = "CLEARING"
            return False, why + ["resumed"]
        if self.state == "SUSPENDED":
            self._reset()
        if self.state == "IDLE":
            if d < thr:
                self.state, self.since = "PENDING", t
                self.n += 1
            return False, why + ["distance_ok" if self.state == "IDLE" else "pending_confirm"]
        if self.state == "PENDING":
            if d >= thr:
                self._reset()
                return False, why + ["distance_ok"]
            if t - self.since < self.cfg.t_confirm_ms * MS:
                return False, why + ["pending_confirm"]
            self.state = "ALERTED"
            last = self.last_alert.get(identity)
            if last is not None and t - last < self.cfg.cooldown_ms * MS:
                return False, why + ["cooldown"]
            self.last_alert[identity] = t
            return True, why + ["confirmed"]
        if self.state == "ALERTED":
            if d > thr + h:
                self.state, self.clear_since = "CLEARING", t
            return False, why + ["alerted"]
        # CLEARING: needs d > thr + h continuously for T_clear
        if d < thr:
            self.state = "ALERTED"
            return False, why + ["same_episode"]
        if d <= thr + h:
            self.clear_since = t
        elif t - self.clear_since >= self.cfg.t_clear_ms * MS:
            self._reset()
        return False, why + ["clearing"]


class EmergencyEpisode:
    """Guardrail: when cap_ttc on, TTC ok and TTC <= threshold, the state is ACTIVE; IDLE->ACTIVE emits."""

    def __init__(self, ttc: Ttc, t_hold_ms: int):
        self.cfg = ttc
        self.t_hold_ns = t_hold_ms * MS
        self.state = "IDLE"
        self.identity: int | None = None
        self.clear_since: int | None = None
        self.hold_start = 0
        self.prev = "IDLE"
        self.n = 0

    @property
    def episode_id(self) -> str:
        return f"e{self.n}"

    def on_time(self, t: int) -> list[str]:
        if self.state == "HOLD_E" and t - self.hold_start > self.t_hold_ns:
            self.state = "SUSPENDED_E"
            return ["hold_expired"]
        return []

    def hold(self, t: int) -> list[str]:
        """Data invalid, missing or too old, or cap_ttc off: keep the memory, say nothing (3.5)."""
        if self.state in ("ACTIVE", "CLEARING_E"):
            self.prev, self.state, self.hold_start = self.state, "HOLD_E", t
            return ["hold"]
        return []

    def _clear_ok(self, ttc: float | None) -> bool:
        return ttc is None or ttc > self.cfg.ttc_emergency_s + self.cfg.h_ttc_s

    def step(self, t: int, identity: int | None, usable: bool, ttc: float | None) -> tuple[bool, list]:
        """usable: cap_ttc on and TTC ok or not_applicable (ttc=None means not closing)."""
        if identity is None:
            self.state, self.identity = "IDLE", None
            return False, ["no_lead"]
        if identity != self.identity:
            self.state, self.identity = "IDLE", identity
        why = self.on_time(t)
        if not usable:
            self.hold(t)
            return False, why + ["ttc_unusable"]
        danger = ttc is not None and ttc <= self.cfg.ttc_emergency_s
        # Same rule as the distance episode (3.5, OQ-A5): the clearing count runs on through a HOLD, so a
        # danger that comes after T_clear_e is a new episode however often the data dropped out in between.
        counting = self.prev == "CLEARING_E" and self.clear_since is not None
        if self.state == "HOLD_E" and counting and t - self.clear_since >= self.cfg.t_clear_e_ms * MS:
            self.state = "IDLE"
            why = why + ["cleared_in_hold"]
        if self.state == "HOLD_E":
            if danger:
                self.state = "ACTIVE"
                return False, why + ["same_episode"]
            self.state = "CLEARING_E"
            self.clear_since = (self.clear_since if counting else t) if self._clear_ok(ttc) else None
            return False, why + ["resumed"]
        if self.state == "SUSPENDED_E":
            self.state = "IDLE"
        if self.state == "IDLE":
            if danger:
                self.state = "ACTIVE"
                self.n += 1
                return True, why + ["ttc_below_threshold"]
            return False, why + ["ttc_ok"]
        if self.state == "ACTIVE":
            if not danger:
                self.state = "CLEARING_E"
                self.clear_since = t if self._clear_ok(ttc) else None
            return False, why + ["same_episode"]
        # CLEARING_E
        if danger:
            self.state = "ACTIVE"
            return False, why + ["same_episode"]
        if not self._clear_ok(ttc):
            self.clear_since = None
        elif self.clear_since is None:
            self.clear_since = t
        elif t - self.clear_since >= self.cfg.t_clear_e_ms * MS:
            self.state = "IDLE"
        return False, why + ["clearing"]
