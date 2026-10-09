"""API contract of the demo server (src/roadwatch/web.py) for front-end developers.

The OpenAPI document generated from these models is committed at src/roadwatch/openapi.json
(`python -m scripts.roadwatch.export_api_schema --check` fails when they drift); live docs at /docs.

Conventions: SI-ish units in the field name (`_m`, `_s`, `_kmh`, `_deg`, `_ms`, `_us`); a value that is not available
is `null`, never 0; times are seconds of video (`t_s`), not wall clock.
"""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = '1.2.0'


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RunState(StrEnum):
    idle = 'idle'          # no run yet
    loading = 'loading'    # video uploaded, model loading
    running = 'running'
    done = 'done'
    stopped = 'stopped'    # POST /api/stop
    failed = 'failed'      # see `error`


class Level(StrEnum):
    info = 'info'                # "Xe trước đang gần lại"
    warning = 'warning'          # "Giãn thêm khoảng cách"
    emergency = 'emergency'      # beep + "Phanh! Xe trước"


# ---- BT-A: measurement -------------------------------------------------------------------------------------------

class Calibration(_Model):
    status: str = Field(description="'calibrating k/5' | 'calibrated' | 'unreliable: <why>'")
    calibrated: bool = Field(description='pitch/yaw converged and fy known: distance alerts allowed')
    fy_px: float = Field(description='focal length in use (px)')
    fy_state: str = Field(description="'nhập tay' | 'gom khung n/200 (tạm X)' | 'đang học nền (tạm X)' | 'đã học' | 'lỗi: …'")
    pitch_deg: float
    yaw_deg: float
    height_m: float = Field(description='camera height above the road')
    coverage: float = Field(ge=0, le=1, description='share of the model frame the camera image covers; < 0.95 = unreliable')
    remounts: int = Field(description='camera re-mounts detected in this run')


class Lead(_Model):
    prob: float = Field(ge=0, le=1, description='model confidence that a lead vehicle exists')
    gap_m: float | None = Field(description='front bumper to lead vehicle; null when prob < 0.5')
    speed_kmh: float | None = Field(description='lead vehicle speed; null when no lead')
    sigma_m: float | None = Field(default=None, ge=0, allow_inf_nan=False, description='Predicted lead-distance standard deviation (1 sigma), not measured accuracy; null when unavailable')
    radar_m: float | None = Field(default=None, gt=0, allow_inf_nan=False, description='Offline radar candidate distance at the same origin; null without reference data')
    delta_m: float | None = Field(default=None, allow_inf_nan=False, description='Estimated gap minus radar reference (m); null without an aligned reference')


class Measurement(_Model):
    frame: int = Field(description='0-based index at 20 Hz')
    t_s: float = Field(description='video time')
    ego_kmh: float = Field(description='own speed estimated by the model')
    lead: Lead
    ttc_s: float | None = Field(description='time to collision; null unless closing in and < 10 s')
    calibration: Calibration


# ---- BT-B: decision ----------------------------------------------------------------------------------------------

class Decision(_Model):
    level: Level | None = Field(description='active alert level; null = safe / silent')
    say: Level | None = Field(description='phrase spoken on THIS frame; null = silent. Play /api/phrases/{say}')
    reason: str = Field(description='why it speaks or stays silent (Vietnamese, for the UI and the log)')
    threshold_m: float | None = Field(description='legal minimum gap at the current speed; null below 60 km/h')
    latency_us: int = Field(description='time BT-B took for this frame')


class SpokenEvent(_Model):
    t_s: float
    kind: Level
    text: str
    reason: str


# ---- BT-C: operations --------------------------------------------------------------------------------------------

class Latency(_Model):
    last_ms: float = Field(description='BT-A + BT-B time of the last frame')
    p50_ms: float
    p95_ms: float


class AlertCounts(_Model):
    info: int = 0
    warning: int = 0
    emergency: int = 0


class Ops(_Model):
    fps: float = Field(description='frames processed per second (20 = real time)')
    latency: Latency
    bad_frames: int = Field(description='frames skipped because processing raised')
    raw_onsets: AlertCounts = Field(description='baseline: alerts if every raw condition onset were spoken')
    said: AlertCounts = Field(description='alerts actually spoken with BT-B dispatch rules')


class Sample(_Model):
    """One chart point; the UI keeps its own 30 s buffer from the SSE stream."""
    t_s: float
    gap_m: float | None
    threshold_m: float | None
    ttc_s: float | None


class Outputs(_Model):
    video_url: str = Field(description='annotated MP4 (supports Range)')
    log_url: str = Field(description='decisions.json')


class LiveStatus(_Model):
    """GET /api/status, and the `data` of every message on GET /api/events (one per processed frame)."""
    api_version: str = API_VERSION
    state: RunState
    run_id: str | None = None
    error: str | None = Field(None, description='set when state = failed')
    measure: Measurement | None = Field(None, description='BT-A; null before the first frame')
    decision: Decision | None = Field(None, description='BT-B; null before the first frame')
    ops: Ops | None = Field(None, description='BT-C; null before the first frame')
    sample: Sample | None = Field(None, description='chart point of this frame')
    events: list[SpokenEvent] = Field([], description='last 30 spoken alerts, oldest first')
    outputs: Outputs | None = Field(None, description='set when state = done or stopped')


class History(_Model):
    """GET /api/history: the last 600 chart samples (30 s), to fill the chart when the page opens mid-run."""
    run_id: str | None
    samples: list[Sample]


# ---- runs, config, health, errors --------------------------------------------------------------------------------

class RunStarted(_Model):
    run_id: str = Field(pattern=r'^[0-9a-f]{12}$')
    state: RunState


class RunInfo(_Model):
    run_id: str
    video: str = Field(description='original file name')
    state: RunState | None = Field(None, description='null while the run has not finished')
    frames: int | None = None
    said: AlertCounts | None = None
    started_unix: float
    video_url: str | None = None
    log_url: str | None = None


class SampleVideo(_Model):
    """A video kept on the server for one-click demos (RW_SAMPLES_DIR/<id>.mp4 + <id>.json)."""
    id: str
    title: str
    note: str = ''
    fps: float = Field(gt=0, le=240, allow_inf_nan=False)
    d: float = Field(ge=0, le=5, allow_inf_nan=False, description='camera to front bumper (m)')
    fy: float | None = Field(default=None, gt=0, le=10000, allow_inf_nan=False,
                            description='known focal length (px); null = learned during the run')


class LegalBand(_Model):
    v_min_kmh: float
    v_max_kmh: float
    min_gap_m: float


class BtBConfig(_Model):
    legal_bands: list[LegalBand] = Field(description='Thông tư 38/2024 art. 11.1')
    ttc_emergency_s: float
    h_ttc_s: float
    t_confirm_s: float
    h_m: float
    t_clear_s: float
    cooldown_s: float
    grace_s: float
    info_horizon_s: float
    phrases: dict[Level, str]


class Health(_Model):
    status: str = Field(description="'ok' | 'degraded' (a running job produced no frame for 2 s)")
    job: RunState
    hung: bool
    model: bool = Field(description='models/gr14VinAI.onnx present')
    timestamp: str = Field(description='ISO 8601, UTC')
    api_version: str = API_VERSION


class Deleted(_Model):
    deleted: str


class Stopping(_Model):
    state: str = 'stopping'


class Error(_Model):
    detail: str = Field(description='Vietnamese message to show as is (422 validation errors use FastAPI\'s list form)')
