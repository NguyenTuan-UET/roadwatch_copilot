"""Contract 5 (spec §4.5, §3.7, §3.10): versioned config, approval record, active pointer."""

from typing import ClassVar, Literal

from pydantic import Field, model_validator

from .base import Strict, canonical_json, sha256_hex

# Hard bounds are part of the guardrail: config can tune inside them, never switch safety off.
# ponytail: provisional values (OQ-B2); change only through a reviewed spec edit.
TTC_EMERGENCY_BOUNDS_S = (1.0, 3.0)
T_CLEAR_E_MAX_MS = 2000
H_TTC_MAX_S = 1.0
T_HOLD_MAX_MS = 1500


class Camera(Strict):
    fx_px: float = Field(gt=0)
    fy_px: float = Field(gt=0)
    cx_px: float
    cy_px: float
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    dist: list[float] = []


class Mount(Strict):
    h_cam_m: float = Field(gt=0)  # camera height above road, measured (KS-2) -- never the vehicle height
    d_cam_bumper_m: float = Field(ge=0)  # horizontal camera -> front bumper, 1.5 m assumed until KS-3
    pitch_deg: float
    roll_deg: float
    yaw_deg: float
    y_horizon_px: float
    provisional_keys: list[str] = []


class Detector(Strict):
    model_path: str
    model_sha256: str
    imgsz: int = Field(gt=0)
    score_thr: float = Field(gt=0, lt=1)
    nms_iou: float = Field(gt=0, lt=1)
    vehicle_class_ids: list[int]


class Perception(Strict):
    roi_bottom_half_width: float = Field(gt=0, le=0.5)  # fixed ego-lane ROI, fractions of image width
    roi_top_half_width: float = Field(gt=0, le=0.5)
    roi_top_y: float = Field(gt=0, lt=1)  # fraction of image height
    ttc_min_frames: int = Field(ge=3)
    ttc_min_bbox_w_px: float = Field(gt=0)
    ttc_max_resid: float = Field(gt=0)
    obs_min_luma: float
    obs_max_luma: float
    obs_min_std: float
    mount_enabled: bool  # flag-off path of ADR-05 when validation fails
    mount_suspect_px: float = Field(gt=0)
    mount_recover_px: float = Field(gt=0)
    mount_t_suspect_ms: int = Field(ge=0)
    mount_trust_window_ms: int = Field(ge=0)
    mount_flap_n: int = Field(ge=1)
    mount_flap_window_ms: int = Field(gt=0)
    mount_strip_frac: float = Field(gt=0, lt=0.5)
    mount_min_response: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _recover_stricter(self):
        if self.mount_recover_px >= self.mount_suspect_px:
            raise ValueError("recovery threshold must be stricter than suspect threshold")
        return self


class Runtime(Strict):
    process_hz: float = Field(gt=0)
    tick_period_ms: int = Field(gt=0)
    q_measure: int = Field(ge=1)
    q_speed: int = Field(ge=1)
    q_log: int = Field(ge=1)
    hang_timeout_ms: int = Field(gt=0)
    max_measurement_gap_ms: int = Field(gt=0)
    max_measurement_age_ms: int = Field(gt=0)


class Band(Strict):
    v_min_kmh: float = Field(ge=0)
    v_max_kmh: float = Field(gt=0)
    min_distance_m: float = Field(gt=0)


class LegalTable(Strict):
    legal_ref: str = Field(min_length=1)
    bands: list[Band] = Field(min_length=1)


class Ttc(Strict):
    ttc_emergency_s: float = Field(ge=TTC_EMERGENCY_BOUNDS_S[0], le=TTC_EMERGENCY_BOUNDS_S[1])
    t_clear_e_ms: int = Field(ge=0, le=T_CLEAR_E_MAX_MS)
    h_ttc_s: float = Field(ge=0, le=H_TTC_MAX_S)
    min_ttc_rate_hz: float = Field(gt=0)


class Dispatch(Strict):
    t_confirm_ms: int = Field(ge=0)
    h_m: float = Field(ge=0)
    t_clear_ms: int = Field(ge=0)
    cooldown_ms: int = Field(ge=0)
    t_hold_ms: int = Field(ge=0, le=T_HOLD_MAX_MS)
    novice_margin_m: float = Field(ge=0)  # can only widen the legal distance, never shrink it


class Speed(Strict):
    fresh_max_ms: int = Field(gt=0)
    lost_after_ms: int = Field(gt=0)
    stale_policy: Literal["unusable"]  # MVP: stale samples are not used (ADR-06); experiments may add more

    @model_validator(mode="after")
    def _order(self):
        if self.lost_after_ms <= self.fresh_max_ms:
            raise ValueError("lost_after_ms must exceed fresh_max_ms")
        return self


class StatusMsgs(Strict):
    t_notify_ms: int = Field(ge=0)
    remind_interval_ms: int | None = None  # null until the listening test (OQ-A8)


class Audio(Strict):
    max_cmd_age_ms: int = Field(gt=0)
    phrase_dir: str
    phrases: dict[str, int]  # phrase_id -> duration_ms, so the pure arbiter is reproducible

    @model_validator(mode="after")
    def _all_kinds(self):
        need = {"emergency", "warning", "info", "system_off", "cap_distance_off", "cap_ttc_off", "recovery",
                "reminder"}
        if missing := need - set(self.phrases):
            raise ValueError(f"missing phrases: {sorted(missing)}")
        return self


class RwConfig(Strict):
    """No field can command the vehicle (NG1): extra="forbid" rejects anything not listed here."""

    SCHEMA: ClassVar[str] = "rw.config"
    AFFECTS: ClassVar[dict[str, tuple[str, ...]]] = {
        "camera": ("A",), "mount": ("A",), "perception": ("A",), "detector": ("A", "live"),
        "runtime": ("A", "live"), "legal_table": ("B",), "ttc": ("B",), "dispatch": ("B",), "speed": ("B",),
        "status_msgs": ("B",), "audio": ("B",),
    }

    camera: Camera
    mount: Mount
    detector: Detector
    perception: Perception
    runtime: Runtime
    legal_table: LegalTable
    ttc: Ttc
    dispatch: Dispatch
    speed: Speed
    status_msgs: StatusMsgs
    audio: Audio

    def sha256(self) -> str:
        return sha256_hex(canonical_json(self.model_dump(mode="json")))

    def affected_by_change(self, other: "RwConfig") -> set[str]:
        """Union of `affects` of every section that differs from `other` (decides the report path)."""
        out: set[str] = set()
        for name, tags in self.AFFECTS.items():
            if getattr(self, name) != getattr(other, name):
                out.update(tags)
        return out


class Approval(Strict):
    approval_id: str
    config_sha256: str
    proposer: str
    approver: str
    approved_at: str
    report_sha256: str
    base_config_sha256: str
    dataset_manifest_sha256: str
    code_commit: str
    model_sha256: str | None
    ort_version: str | None
    machine_fingerprint: str | None  # only when the change needed a live check

    def expected_id(self) -> str:
        return sha256_hex(canonical_json(self.model_dump(mode="json", exclude={"approval_id"})))

    @model_validator(mode="after")
    def _rules(self):
        if self.proposer == self.approver:
            raise ValueError("self-approval is not allowed")
        if self.approval_id != self.expected_id():
            raise ValueError("approval_id does not match content")
        return self

    @classmethod
    def create(cls, **fields) -> "Approval":
        probe = cls.model_construct(approval_id="", **fields)
        return cls(approval_id=probe.expected_id(), **fields)


class ActivePointer(Strict):
    config_sha256: str
    approval_id: str
    activation_id: str
