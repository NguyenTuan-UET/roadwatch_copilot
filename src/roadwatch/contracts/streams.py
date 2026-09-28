"""Stream records of contracts 1–4 (spec §4.1–4.4) plus dataset records (session manifest, labels)."""

from typing import Literal

from pydantic import Field, model_validator

from .base import Q, Record, Status, Strict

Arbiter = Literal["B", "baseline"]
BBox = tuple[float, float, float, float]  # x1, y1, x2, y2 in source pixels


# --- contract 1: input -> A / join ---------------------------------------------------------

class FrameMeta(Record):
    """t_ns = t_k (frame time from PTS), or s_n (schedule time) for a placeholder."""

    SCHEMA = "rw.frame"
    sched_n: int = Field(ge=0)
    status: Literal["ok", "unavailable"]
    reasons: list[str] = []
    frame_idx: int | None = None
    pts_ns: int | None = None
    t_arrive_mono_ns: int | None = None
    video_sha256: str

    @model_validator(mode="after")
    def _placeholder(self):
        if self.status == "unavailable":
            if self.frame_idx is not None or self.pts_ns is not None or not self.reasons:
                raise ValueError("placeholder: frame_idx/pts_ns must be null and reasons given")
        elif self.frame_idx is None or self.pts_ns is None:
            raise ValueError("a real frame needs frame_idx and pts_ns")
        return self


class SpeedSample(Record):
    """t_ns = t_recv (when the sample became available)."""

    SCHEMA = "rw.speed"
    gps_idx: int = Field(ge=0)
    t_fix_ns: int
    t_recv_ns: int
    t_recv_basis: Literal["logged", "modeled"]
    speed_mps: Q
    source: Literal["gps", "simulated"]
    session_id: str

    @model_validator(mode="after")
    def _times(self):
        if self.t_recv_ns < self.t_fix_ns:
            raise ValueError("t_recv cannot precede t_fix")
        if self.t_ns != self.t_recv_ns:
            raise ValueError("t_ns must equal t_recv_ns")
        return self


# --- contract 2: A -> B ---------------------------------------------------------------------

class Observation(Strict):
    status: Literal["ok", "unavailable", "unreliable"]
    reasons: list[str] = []

    @model_validator(mode="after")
    def _reasons(self):
        if self.status != "ok" and not self.reasons:
            raise ValueError("non-ok observation needs reasons")
        return self


class MountCheck(Strict):
    state: Literal["ok", "suspect", "unknown"]
    since_t_ns: int
    deviation_px: Q | None = None  # MINOR


class ChangeEvidence(Strict):  # MINOR
    observed_frames_before: int | None = None
    crossed_boundary: bool | None = None
    lane_ref: Literal["lane_markings", "fixed_roi"] | None = None
    status: Status
    reasons: list[str] = []


class LeadChange(Strict):
    reason: Literal["entered_from_left", "entered_from_right", "previous_lead_left", "appeared_ahead",
                    "likely_id_switch", "unknown"]
    t_ns: int
    evidence: ChangeEvidence | None = None


_LEAD_ID_FIELDS = ("identity_id", "track_id", "since_t_ns", "basis", "bbox_px", "det_score")


class Lead(Strict):
    status: Status
    reasons: list[str] = []
    identity_id: int | None = None  # A's estimate, kept across likely_id_switch
    track_id: int | None = None
    since_t_ns: int | None = None
    basis: Literal["lane_markings", "fixed_roi"] | None = None
    bbox_px: BBox | None = None
    det_score: float | None = Field(default=None, ge=0, le=1)  # detector score, NOT distance confidence
    change: LeadChange | None = None
    lateral_offset_m: Q | None = None  # MINOR; unmeasured => unavailable, never 0

    @model_validator(mode="after")
    def _identity(self):
        present = [getattr(self, f) is not None for f in _LEAD_ID_FIELDS]
        if self.status == "ok" and not all(present):
            raise ValueError("lead ok requires " + ", ".join(_LEAD_ID_FIELDS))
        if self.status != "ok":
            if any(present) or self.change is not None:
                raise ValueError("lead identity fields must be null when lead is not ok")
            if not self.reasons:
                raise ValueError("non-ok lead needs reasons")
        return self


class Measurement(Record):
    """One per FrameMeta (placeholders included); t_ns = t_k."""

    SCHEMA = "rw.measurement"
    sched_n: int = Field(ge=0)
    frame_idx: int | None
    observation: Observation
    mount_check: MountCheck
    lead: Lead
    distance_m: Q  # from the ego front bumper
    ttc_s: Q  # not_applicable when not closing

    @model_validator(mode="after")
    def _null_matrix(self):
        if self.frame_idx is None and self.observation.status != "unavailable":
            raise ValueError("no frame => observation unavailable")
        if self.observation.status != "ok" and self.lead.status in ("ok", "not_applicable"):
            raise ValueError("cannot see => lead must be unavailable/unreliable (no lead != cannot see)")
        if self.lead.status != "ok" and (self.distance_m.usable or self.ttc_s.usable):
            raise ValueError("distance/ttc cannot be ok without a lead")
        return self


# --- contract 4: decision journal, traces, events -------------------------------------------

class StreamRef(Strict):
    stream: Literal["measurements", "speed", "events"]
    seq: int = Field(ge=0)


class DecisionInput(Record):
    """Journal of what `decision` really consumed, in order. t_ns = measurement/event/tick time."""

    SCHEMA = "rw.decision_input"
    kind: Literal["measurement", "speed", "event", "tick"]
    ref: StreamRef | None = None
    tick_n: int | None = None
    t_consumed_ns: int

    @model_validator(mode="after")
    def _shape(self):
        if (self.kind == "tick") != (self.ref is None) or (self.kind == "tick") != (self.tick_n is not None):
            raise ValueError("tick has tick_n and no ref; other kinds have ref and no tick_n")
        return self


class SpeedUsed(Strict):
    gps_idx: int | None
    age_ms: float | None
    status: Literal["fresh", "stale", "lost"]


Cap = Literal["on", "off"]


class DecisionTrace(Record):
    """Exactly one per (input_seq, arbiter): state, inputs used and why it spoke or not."""

    SCHEMA = "rw.decision_trace"
    input_seq: int = Field(ge=0)
    arbiter: Arbiter
    cap_distance: Cap
    cap_ttc: Cap
    capability_epoch: int = Field(ge=0)
    distance_state: str
    emergency_state: str
    speed_used: SpeedUsed
    headway_s: Q
    threshold_m: Q
    why: list[str] = []  # open set
    measurement_age_ms: float | None = None


AlertKind = Literal["emergency", "warning", "info", "system_off", "cap_distance_off", "cap_ttc_off",
                    "recovery", "reminder"]


class Trigger(Strict):
    source: Literal["frame", "tick", "event"]
    input_seq: int = Field(ge=0)


class AlertDecision(Record):
    SCHEMA = "rw.alert"
    alert_id: str
    arbiter: Arbiter
    cls: Literal["hazard", "status"] = Field(alias="class")
    kind: AlertKind
    phrase_id: str
    episode_id: str | None = None
    trigger: Trigger
    t_trigger_ns: int
    t_decided_ns: int
    capability_epoch: int = Field(ge=0)
    expires_t_ns: int


class AudioPlan(Record):
    SCHEMA = "rw.audio_plan"
    alert_id: str
    arbiter: Arbiter
    outcome: Literal["started", "preempted", "cancelled", "expired"]
    preempted_by: str | None = None
    reasons: list[str] = []


class AudioEvent(Record):
    SCHEMA = "rw.audio_event"
    alert_id: str
    outcome: Literal["started", "dropped_stale", "fault"]
    t_mono_ns: int
    output_latency_ms: Q


class SystemEvent(Record):
    SCHEMA = "rw.system_event"
    kind: Literal["run_start", "run_stop", "config_loaded", "frame_dropped", "measurement_dropped",
                  "speed_dropped", "system_fault", "mount_rechecked", "capability_changed", "audio_fault",
                  "log_overflow"]
    detail: dict[str, str | int | float | bool | None] = {}
    reasons: list[str] = []


class RunManifest(Strict):
    run_id: str
    mode: Literal["live", "replay", "rerun-B"]
    created_utc: str
    inputs: dict[str, str]
    config_sha256: str
    approval_id: str
    activation_id: str | None
    code_commit: str
    code_dirty: bool
    model_sha256: str | None
    ort_version: str | None
    python_version: str
    os: str
    cpu: str
    threads: int
    machine_fingerprint: str
    process_hz: float
    driver_mode: Literal["novice", "experienced"]
    session_id: str
    mount_checklist: bool  # decides the initial mount trust (ADR-05); needed to reproduce B
    active_arbiter: Arbiter  # which arbiter drove the speaker (live latency is reported per arbiter)
    contracts_version: str
    flags: list[str] = []
    source_run_id: str | None = None


# --- dataset records (spec 4.4, 5.1, 5.2) -------------------------------------------------------

class SessionManifest(Strict):
    session_id: str
    video_file: str
    video_sha256: str
    gps_file: str | None
    gps_sha256: str | None
    video_start_utc_guess_ns: int
    gps_offset_ms: float
    gps_offset_uncertainty_ms: float | None  # null until measured, never 0
    sync_method: str
    recv_time_basis: Literal["logged", "modeled"]
    recv_delay_ms: float | None = None
    speed_source: Literal["gps", "simulated"]
    car_model_note: str | None = None  # note only, never used in computation (ADR-04)
    mount_checklist: dict[str, str] | None = None
    split: Literal["dev", "test_small", "test_final"]


class LabelTarget(Strict):
    key_frame_idx: int
    bbox_px: BBox


class EventLabel(Strict):
    event_id: str
    clip_id: str
    t_start_s: float
    t_end_s: float
    type: Literal["tailgating", "collision_risk", "cut_in", "congestion"]
    cause: Literal["lead_hard_brake", "closing_on_slower", "cut_in_close", "queue_tail", "unknown"] | None = None
    expect: Literal["must_alert", "exempt"]
    min_level: Literal["info", "warning", "emergency"] | None = None
    target: LabelTarget | None = None

    @model_validator(mode="after")
    def _rules(self):
        if self.t_end_s < self.t_start_s:
            raise ValueError("t_end_s < t_start_s")
        if (self.expect == "must_alert") != (self.min_level is not None):
            raise ValueError("must_alert needs min_level; exempt has none")
        if (self.type == "collision_risk") != (self.cause is not None):
            raise ValueError("cause is required for collision_risk only")
        return self
