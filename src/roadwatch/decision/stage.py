"""The pure decision stage (spec §3.3–3.7): journal input in, traces/alerts/audio plan out.

Runtime and rerun-B call the same `DecisionStage.consume`, so a journal replays to identical output.
"""

from ..contracts.base import Q, Record
from ..contracts.config import RwConfig
from ..contracts.streams import AlertDecision, AudioPlan, DecisionInput, DecisionTrace, Measurement, Trigger
from .arbiter import AudioArbiter, Outcome
from .capability import Capabilities
from .episodes import DistanceEpisode, EmergencyEpisode
from .join import SpeedTracker, SpeedView, headway, legal_threshold

MS = 1_000_000
PAIR_KIND = {("on", "on"): "recovery", ("off", "on"): "cap_distance_off", ("on", "off"): "cap_ttc_off",
             ("off", "off"): "system_off"}


class Announcer:
    """Status messages follow the capability pair (3.4): debounced by T_notify except system_fault."""

    def __init__(self, cfg: RwConfig):
        self.t_notify = cfg.status_msgs.t_notify_ms * MS
        self.remind = cfg.status_msgs.remind_interval_ms
        self.announced = ("on", "on")
        self.pending: tuple[str, str] | None = None
        self.pending_since = 0
        self.last_status_t = 0

    def update(self, t: int, pair: tuple[str, str], fault_now: bool) -> str | None:
        if fault_now:
            self.announced, self.pending, self.last_status_t = ("off", "off"), None, t
            return "system_off"
        if pair == self.announced:
            self.pending = None
        elif pair != self.pending:
            self.pending, self.pending_since = pair, t
        elif t - self.pending_since >= self.t_notify:
            self.announced, self.pending, self.last_status_t = pair, None, t
            return PAIR_KIND[pair]
        if self.remind and self.announced != ("on", "on") and t - self.last_status_t >= self.remind * MS:
            self.last_status_t = t
            return "reminder"
        return None


class DecisionStage:
    def __init__(self, cfg: RwConfig, run_id: str, mount_checklist: bool, driver_mode: str):
        self.cfg = cfg
        self.run_id = run_id
        self.margin = cfg.dispatch.novice_margin_m if driver_mode == "novice" else 0.0
        self.speed = SpeedTracker(cfg.speed)
        self.caps = Capabilities(cfg, mount_checklist)
        self.dist = DistanceEpisode(cfg.dispatch)
        self.emerg = EmergencyEpisode(cfg.ttc, cfg.dispatch.t_hold_ms)
        self.announcer = Announcer(cfg)
        self.arb = {"B": AudioArbiter(cfg.audio), "baseline": AudioArbiter(cfg.audio)}
        self.base_prev = {"warning": False, "emergency": False}
        self.seq = {"trace": 0, "alert": 0, "plan": 0}
        self.alert_n = {"B": 0, "baseline": 0}
        self.now = 0
        self.last = {"threshold": Q.missing("unavailable", "no_measurement_yet"),
                     "headway": Q.missing("unavailable", "no_measurement_yet"), "age": None}

    # --- record builders ---------------------------------------------------------------------
    def _next(self, key: str) -> int:
        n = self.seq[key]
        self.seq[key] += 1
        return n

    def _alert(self, arbiter: str, kind: str, inp: DecisionInput, t_trigger: int, episode: str | None) -> AlertDecision:
        n = self.alert_n[arbiter]
        self.alert_n[arbiter] += 1
        source = {"measurement": "frame", "tick": "tick", "event": "event"}[inp.kind]
        return AlertDecision(
            run_id=self.run_id, seq=self._next("alert"), t_ns=self.now, alert_id=f"{arbiter}-{n}", arbiter=arbiter,
            cls="hazard" if kind in ("emergency", "warning", "info") else "status", kind=kind, phrase_id=kind,
            episode_id=episode, trigger=Trigger(source=source, input_seq=inp.seq), t_trigger_ns=t_trigger,
            t_decided_ns=self.now, capability_epoch=self.caps.epoch,
            expires_t_ns=t_trigger + self.cfg.audio.max_cmd_age_ms * MS)

    def _plans(self, arbiter: str, outcomes: list[Outcome]) -> list[AudioPlan]:
        return [AudioPlan(run_id=self.run_id, seq=self._next("plan"), t_ns=o.t_ns, alert_id=o.alert_id, arbiter=arbiter,
                          outcome=o.outcome, preempted_by=o.preempted_by, reasons=list(o.reasons)) for o in outcomes]

    def _trace(self, inp: DecisionInput, arbiter: str, sv: SpeedView, why: list[str], states: tuple[str, str]):
        cap_d, cap_t = self.caps.pair
        reasons = sorted(self.caps.distance_off | self.caps.ttc_off)
        return DecisionTrace(
            run_id=self.run_id, seq=self._next("trace"), t_ns=inp.t_ns, input_seq=inp.seq, arbiter=arbiter,
            cap_distance=cap_d, cap_ttc=cap_t, capability_epoch=self.caps.epoch, distance_state=states[0],
            emergency_state=states[1], speed_used=sv.used(), headway_s=self.last["headway"],
            threshold_m=self.last["threshold"], why=why + reasons, measurement_age_ms=self.last["age"])

    # --- main entry ----------------------------------------------------------------------------
    def consume(self, inp: DecisionInput, payload) -> list[Record]:
        self.now = max(self.now, inp.t_consumed_ns)
        out: list[Record] = []
        for name, arb in self.arb.items():
            out += self._plans(name, arb.advance(self.now, self.caps.epoch))
        hazards: dict[str, list[tuple[str, str | None]]] = {"B": [], "baseline": []}
        why = {"B": [], "baseline": []}
        fault_before = self.caps.fault
        if inp.kind == "speed":
            self.speed.update(payload)
        elif inp.kind == "event":
            self.caps.on_event(payload, inp.t_ns)
        elif inp.kind == "tick":
            self.caps.on_tick(inp.t_ns)
            why["B"] += self.dist.on_time(inp.t_ns) + self.emerg.on_time(inp.t_ns)
        else:
            self._measurement(payload, hazards, why)
        sv = self.speed.at(inp.t_ns)

        t_trigger = inp.t_ns
        for kind, episode in hazards["B"]:
            out += self._submit("B", self._alert("B", kind, inp, t_trigger, episode))
        for kind, _ in hazards["baseline"]:
            out += self._submit("baseline", self._alert("baseline", kind, inp, t_trigger, None))
        out += self._cancel_stale_hazards()
        # speed inputs are not a trigger source; a due announcement fires on the next tick/event/frame
        status = None if inp.kind == "speed" else self.announcer.update(
            self.now, self.caps.pair, self.caps.fault and not fault_before)
        if status:
            out += self._submit("B", self._alert("B", status, inp, t_trigger, None))

        out.append(self._trace(inp, "B", sv, why["B"], (self.dist.state, self.emerg.state)))
        base_states = tuple("VIOLATING" if self.base_prev[k] else "OK" for k in ("warning", "emergency"))
        out.append(self._trace(inp, "baseline", sv, why["baseline"], base_states))
        return out

    def _submit(self, arbiter: str, alert: AlertDecision) -> list[Record]:
        return [alert] + self._plans(arbiter, self.arb[arbiter].submit(alert, self.now, self.caps.epoch))

    def _cancel_stale_hazards(self) -> list[Record]:
        dist_live = self.dist.state == "ALERTED" and self.caps.pair[0] == "on"
        emerg_live = self.emerg.state == "ACTIVE" and self.caps.pair[1] == "on"
        out = self._plans("B", self.arb["B"].cancel_pending(
            lambda a: (a.kind == "warning" and not dist_live) or (a.kind == "emergency" and not emerg_live),
            self.now, "episode_left"))
        out += self._plans("baseline", self.arb["baseline"].cancel_pending(
            lambda a: a.cls == "hazard" and not self.base_prev[a.kind], self.now, "condition_false"))
        return out

    def _measurement(self, m: Measurement, hazards: dict, why: dict) -> None:
        t_k = m.t_ns
        age_ms = (self.now - t_k) / MS
        stale = age_ms > self.cfg.runtime.max_measurement_age_ms
        sv = self.speed.at(t_k)
        self.caps.on_measurement(m, t_k, sv)
        thr = legal_threshold(self.cfg.legal_table, self.margin, sv)
        self.last = {"threshold": thr, "headway": headway(m.distance_m, sv), "age": age_ms}
        cap_d, cap_t = self.caps.pair
        dist_ok = not stale and cap_d == "on" and m.distance_m.usable and thr.usable
        ttc_ok = not stale and cap_t == "on" and m.ttc_s.status in ("ok", "not_applicable")
        ttc = m.ttc_s.value if m.ttc_s.usable else None
        identity = m.lead.identity_id if m.lead.status == "ok" else None
        no_lead = m.lead.status == "not_applicable"
        extra = ["stale_measurement"] if stale else []
        d_val, thr_val = m.distance_m.value, thr.value

        if no_lead:
            emit_w, why_w = self.dist.step(t_k, None, True, None, None)
            emit_e, why_e = self.emerg.step(t_k, None, True, None)
        else:
            lead_id = identity if identity is not None else self.dist.identity
            emit_w, why_w = self.dist.step(t_k, lead_id, dist_ok, d_val, thr_val)
            emit_e, why_e = self.emerg.step(t_k, lead_id if identity is not None else self.emerg.identity, ttc_ok, ttc)
        why["B"] += extra + why_w + why_e
        if emit_e:
            hazards["B"].append(("emergency", self.emerg.episode_id))
        if emit_w:
            hazards["B"].append(("warning", self.dist.episode_id))

        # Baseline (ADR-03): rising edge on the same thresholds and the same validity/fail-safe gating.
        viol = {"warning": dist_ok and d_val < thr_val,
                "emergency": ttc_ok and ttc is not None and ttc <= self.cfg.ttc.ttc_emergency_s}
        for kind in ("emergency", "warning"):
            if viol[kind] and not self.base_prev[kind]:
                hazards["baseline"].append((kind, None))
            self.base_prev[kind] = viol[kind]
        why["baseline"] += extra
