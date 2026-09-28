"""Builds decision-input streams (journal + payloads) and feeds them to DecisionStage."""

import json

from src.roadwatch.contracts.base import Q, normalize
from src.roadwatch.contracts.config import RwConfig
from src.roadwatch.contracts.streams import (
    AlertDecision,
    AudioPlan,
    DecisionInput,
    DecisionTrace,
    Lead,
    LeadChange,
    Measurement,
    MountCheck,
    Observation,
    SpeedSample,
    StreamRef,
    SystemEvent,
)
from src.roadwatch.decision.stage import DecisionStage
from tests.roadwatch.factories import config_dict

MS = 1_000_000


def make_config(**sections) -> RwConfig:
    data = config_dict()
    for name, values in sections.items():
        data[name].update(values)
    return RwConfig.model_validate(data)


class Harness:
    def __init__(self, cfg: RwConfig | None = None, checklist: bool = True, driver_mode: str = "experienced"):
        self.cfg = cfg or make_config()
        self.stage = DecisionStage(self.cfg, run_id="r", mount_checklist=checklist, driver_mode=driver_mode)
        self.n = {"measurements": 0, "speed": 0, "events": 0}
        self.inputs = 0
        self.out: list = []
        self.journal: list = []

    def _feed(self, kind, t_ns, payload, consumed_ns=None, tick_n=None):
        ref = None
        if kind != "tick":
            stream = {"measurement": "measurements", "speed": "speed", "event": "events"}[kind]
            ref = StreamRef(stream=stream, seq=payload.seq)
        inp = DecisionInput(run_id="r", seq=self.inputs, t_ns=t_ns, kind=kind, ref=ref, tick_n=tick_n,
                            t_consumed_ns=t_ns if consumed_ns is None else consumed_ns)
        self.inputs += 1
        self.journal.append((inp, payload))
        self.out.extend(self.stage.consume(inp, payload))
        return inp

    def speed(self, t_ms: float, kmh: float, lag_ms: float = 0):
        t = int(t_ms * MS)
        s = SpeedSample(run_id="r", seq=self.n["speed"], t_ns=t, gps_idx=self.n["speed"], t_fix_ns=t - int(lag_ms * MS),
                        t_recv_ns=t, t_recv_basis="logged", speed_mps=Q.ok(kmh / 3.6), source="gps", session_id="s")
        self.n["speed"] += 1
        return self._feed("speed", t, s)

    def meas(self, t_ms: float, d: float | None = 80.0, ttc: float | None = None, lead_id: int | None = 1,
             obs: str = "ok", mount: str = "ok", basis: str = "fixed_roi", consumed_ms: float | None = None,
             d_status: str = "ok", ttc_status: str = "ok", change: str | None = None):
        t = int(t_ms * MS)
        if obs != "ok":
            lead = Lead(status="unavailable", reasons=["no_observation"])
            dist = tq = Q.missing("unavailable", "no_observation")
        elif lead_id is None:
            lead = Lead(status="not_applicable", reasons=["no_vehicle"])
            dist = tq = Q.missing("not_applicable", "no_lead")
        else:
            ch = LeadChange(reason=change, t_ns=t) if change else None
            lead = Lead(status="ok", identity_id=lead_id, track_id=lead_id, since_t_ns=0, basis=basis,
                        bbox_px=(900.0, 500.0, 1020.0, 560.0), det_score=0.9, change=ch)
            dist = Q.ok(d) if d_status == "ok" else Q.missing(d_status, "test", value=d)
            if ttc is None:
                tq = Q.missing("not_applicable", "not_closing")
            else:
                tq = Q.ok(ttc) if ttc_status == "ok" else Q.missing(ttc_status, "test", value=ttc)
        m = Measurement(run_id="r", seq=self.n["measurements"], t_ns=t, sched_n=self.n["measurements"],
                        frame_idx=None if obs == "unavailable" else self.n["measurements"],
                        observation=Observation(status=obs, reasons=[] if obs == "ok" else ["test"]),
                        mount_check=MountCheck(state=mount, since_t_ns=0), lead=lead, distance_m=dist, ttc_s=tq)
        self.n["measurements"] += 1
        return self._feed("measurement", t, m, None if consumed_ms is None else int(consumed_ms * MS))

    def event(self, t_ms: float, kind: str):
        t = int(t_ms * MS)
        e = SystemEvent(run_id="r", seq=self.n["events"], t_ns=t, kind=kind, reasons=["test"])
        self.n["events"] += 1
        return self._feed("event", t, e)

    def tick(self, t_ms: float):
        t = int(t_ms * MS)
        return self._feed("tick", t, None, tick_n=int(round(t_ms / self.cfg.runtime.tick_period_ms)))

    def run(self, t0_ms: float, t1_ms: float, d_of_t=None, ttc_of_t=None, kmh: float = 90.0, **kw):
        """10 Hz measurements with a 1 Hz fresh speed sample; each step also emits a tick."""
        t = t0_ms
        while t < t1_ms:
            if int(t) % 1000 == 0:
                self.speed(t, kmh)
            self.meas(t, d=d_of_t(t) if d_of_t else 80.0, ttc=ttc_of_t(t) if ttc_of_t else None, **kw)
            self.tick(t)
            t += 100

    # --- queries ---------------------------------------------------------------------------
    def alerts(self, arbiter: str = "B", kind: str | None = None) -> list[AlertDecision]:
        return [r for r in self.out if isinstance(r, AlertDecision) and r.arbiter == arbiter
                and (kind is None or r.kind == kind)]

    def started(self, arbiter: str = "B") -> list[str]:
        return [r.alert_id for r in self.out if isinstance(r, AudioPlan) and r.arbiter == arbiter
                and r.outcome == "started"]

    def traces(self, arbiter: str = "B") -> list[DecisionTrace]:
        return [r for r in self.out if isinstance(r, DecisionTrace) and r.arbiter == arbiter]

    def normalized(self) -> list:
        return [normalize(json.loads(r.to_json())) for r in self.out]
