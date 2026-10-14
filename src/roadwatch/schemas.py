"""API contract of the demo server (src/roadwatch/web.py) for front-end developers.

The OpenAPI document generated from these models is committed at src/roadwatch/openapi.json
(`python -m scripts.roadwatch.export_api_schema --check` fails when they drift); live docs at /docs.

Conventions: SI-ish units in the field name (`_m`, `_s`, `_kmh`, `_deg`, `_ms`, `_us`); a value that is not available
is `null`, never 0; times are seconds of video (`t_s`), not wall clock.
"""
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

API_VERSION = '1.9.0'


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(_Model):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,40}$')
    password: str = Field(min_length=8, max_length=128)


class Registration(Credentials):
    role: Literal['driver', 'engineer'] = 'driver'


class Account(_Model):
    username: str
    role: Literal['driver', 'engineer']


class LoggedOut(_Model):
    logged_out: bool


class RtcIceServer(_Model):
    urls: list[str] = Field(min_length=1)
    username: str | None = None
    credential: str | None = None

    @field_validator('urls')
    @classmethod
    def ice_urls(cls, urls: list[str]) -> list[str]:
        if any(not url.startswith(('stun:', 'stuns:', 'turn:', 'turns:')) for url in urls):
            raise ValueError('ICE URLs must use stun, stuns, turn or turns')
        return urls


class RtcConfig(_Model):
    ice_servers: list[RtcIceServer] = Field(alias='iceServers')


class RtcOffer(_Model):
    run_id: str = Field(pattern=r'^[0-9a-f]{12}$')
    type: Literal['offer']
    sdp: str = Field(min_length=1, max_length=65536)


class RtcAnswer(_Model):
    peer_id: str
    type: Literal['answer']
    sdp: str


class RtcClosed(_Model):
    closed: bool


class PhoneSettings(_Model):
    """Run settings of a live run from a phone (POST /api/phone/offer body, /api/phone/ws query)."""
    d: float = Field(ge=0, le=5, description='camera to front bumper (m)')
    f_mm: float | None = Field(None, gt=0, le=300, description='35 mm-equivalent focal length of the camera')
    hfov: float | None = Field(None, ge=20, le=170, description='horizontal field of view (deg), when f_mm is not given')
    auto_focal: bool = Field(False, description='fit the focal length to the GPS speed (experimental)')
    pitch: bool = Field(True, description='apply the estimated pitch angle')

    @model_validator(mode='after')
    def _lens(self):
        if not (self.f_mm or self.hfov):
            raise ValueError('chưa có tiêu cự: nhập tiêu cự mm hoặc góc nhìn ngang')
        return self


class PhoneOffer(PhoneSettings):
    """POST /api/phone/offer: the /phone page's WebRTC offer (back camera video + data channel of GPS fixes)
    and the run settings."""
    type: Literal['offer']
    sdp: str = Field(min_length=1, max_length=65536)


class PhoneAnswer(_Model):
    run_id: str = Field(pattern=r'^[0-9a-f]{12}$')
    type: Literal['answer']
    sdp: str


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
    status: str = Field(description="'calibrating k/40' | 'calibrated' | 'unreliable: <why>'")
    calibrated: bool = Field(description='angles converged and fy known (learned, given or fitted to GPS): distance '
                                         'alerts allowed')
    flags: list[str] = Field(description="'auto_focal_needs_gps' | 'gps_sync_low_confidence' | 'focal_calibrating' | 'fps_differs_from_video' "
                                         '(comma realtime_lead flags)')
    fy_px: float = Field(description='focal length in use (px)')
    fy_state: str = Field(description="'nhập tay' | 'từ tiêu cự mm' | 'từ góc nhìn' | 'theo GPS[: đang đồng bộ | : đang "
                                      "hiệu chỉnh]' | 'gom khung n/200 (tạm X)' | 'đang học nền (tạm X)' | 'đã học' | 'lỗi: …'")
    pitch_deg: float
    yaw_deg: float
    height_m: float = Field(description='camera height above the road')
    coverage: float = Field(ge=0, le=1, description='share of the model frame the camera image covers; < 0.95 = unreliable')
    remounts: int = Field(description='camera re-mounts detected in this run; always 0: the online calibration follows a re-mount instead')


class Lead(_Model):
    prob: float = Field(ge=0, le=1, description='model confidence that a lead vehicle exists')
    gap_m: float | None = Field(description='front bumper to the same-lane lead (Kalman-filtered); null when none')
    speed_kmh: float | None = Field(description='lead vehicle speed; null when no lead')
    gap_std_m: float | None = Field(None, description="model's std of the lead distance (the ± shown with gap_m); null when no lead")


class Gps(_Model):
    state: Literal['none', 'syncing', 'synced', 'low_confidence'] = Field(
        description="'none' = no GPS log; 'syncing' until ~20 s of driving lets it align with the model speed; "
                    "'low_confidence' = not aligned (correlation < 0.8 after 90 s), offset 0 used")
    offset_s: float | None = Field(description='GPS time at video t = 0, from the first fix; null while syncing')
    corr: float | None = Field(description='correlation of GPS and model speed at the chosen offset')


class Measurement(_Model):
    frame: int = Field(description='0-based video frame of this model tick (the model runs every n-th frame, ~20 Hz)')
    t_s: float = Field(description='video time')
    ego_kmh: float = Field(description='own speed: GPS once the GPS log is synced, else the model, smoothed')
    ego_source: Literal['gps', 'model']
    model_kmh: float | None = Field(None, description='own speed estimated from the images alone (model), smoothed; '
                                                    'kept beside ego_kmh when the GPS drives it')
    gps_kmh: float | None = Field(None, description="the GPS log's own speed at this tick, not smoothed; null without a "
                                                  'log or outside it')
    radar_m: float | None = Field(None, description='distance to the car ahead from the radar log (front of the car) at '
                                                  'this video time; null without a log or without a track')
    gps: Gps
    lead_raw_m: float | None = Field(description="model's unfiltered gap on this tick when it is the same-lane lead")
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
    video_fps: float | None = Field(None, description="the video's frame rate: `fps` at or above it is real time")
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
    csv_url: str = Field(description='lead_distance.csv: one row per model tick, comma realtime_lead columns')
    calibration_url: str = Field(description='calibration.json: crop, focal length, angles, GPS sync, flags')


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
    error: str | None = Field(None, description='why a failed run failed (also: the server stopped mid-run)')
    frames: int | None = None
    said: AlertCounts | None = None
    started_unix: float
    video_url: str | None = None
    log_url: str | None = None
    csv_url: str | None = None
    calibration_url: str | None = None


class RadarUploaded(_Model):
    radar_id: str = Field(pattern=r'^[0-9a-f]{12}$', description='pass as `radar` to POST /api/runs')
    samples: int = Field(description='rows of the log (a row without a track counts)')
    duration_s: float


class GpsUploaded(_Model):
    gps_id: str = Field(pattern=r'^[0-9a-f]{12}$', description='pass as `gps` to POST /api/runs')
    fixes: int = Field(description='usable GPS fixes after outlier removal')
    duration_s: float


# ---- lab: BT-A vs the car's radar and speed log (comma2k19) ---------------------------------------------------

class LabSegment(_Model):
    id: str
    has_radar: bool
    has_speed: bool = Field(description="speed log of the car: CAN, or the real speed in the segment's gt.csv")
    frames: int | None
    cached: bool = Field(description='a result is saved: GET /api/lab/segments/{id}/result')


class LabStatus(_Model):
    state: Literal['idle', 'running', 'done', 'stopped', 'failed']
    segment: str | None
    done: int = Field(description='frames processed')
    total: int
    calib_frames: int = Field(0, description='the first frames of `done` / `total`: the camera-angle pre-pass')
    calib_rpy_deg: list[float] | None = Field(None, description='[roll, pitch, yaw] estimated so far during the pre-pass; '
                                              'null before the first frame. Only the yaw is applied to the run')
    calib_settled: bool = Field(False, description='the pre-pass has enough samples for its angles to be used')
    error: str | None


class LabResult(_Model):
    """One value per video frame (20 Hz); null = not available. The page gates the raw lead with its own
    thresholds (comma lead_mask) and compares `lead_x_m - bumper_m` with `radar_m`."""
    segment: str
    frames: int
    fps: float
    bumper_m: float = Field(description='camera -> radar (front of the car); subtracted from the model distance')
    fy_px: float
    use_log: bool = Field(description='the CAN speed log was used as the ego speed')
    wide: Literal['dup', 'warp'] = Field('dup', description="model's wide input: the narrow one duplicated, or warped")
    rpy_deg: list[float] = Field(description='roll, pitch, yaw estimated by the pre-pass over the first 300 frames')
    rpy_applied_deg: list[float] | None = Field(None, description='angles applied to the warp for the whole run: '
                                                                  'the yaw only (comma lead_distance app.py)')
    created_unix: float
    t_s: list[float]
    lead_x_m: list[float | None] = Field(description="model's lead distance from the camera, ungated")
    lead_y_m: list[float | None] = Field(description='lateral offset of that lead (+ = right)')
    lead_prob: list[float | None]
    lead_std_m: list[float | None]
    gap_kalman_m: list[float | None] = Field(description='BT-A gap (default thresholds, Kalman-filtered, minus bumper)')
    ego_model_mps: list[float | None]
    ego_log_mps: list[float | None] = Field(description='CAN speed of the car')
    radar_m: list[float | None] = Field(description='nearest radar track within 1.6 m laterally')
    curv_gt: list[float | None] = Field(default_factory=list, description='real curvature of the road the car drives (gt.csv of '
                                                                          'the segment, if it has one), 1/km, + = left')
    curv_yaw: list[float | None] = Field(default_factory=list, description='curvature of the ego yaw (rate / speed from '
                                                                           "the model's pose), 1/km, + = left")
    curv_drawn: list[float | None] = Field(default_factory=list, description='curvature of the path BT-A draws '
                                                                             '(parabola over 5-40 m), 1/km, + = left')


class LabLive(_Model):
    """Frames `start`..`frames`-1 of the segment being run (or of the last run until the next one), same columns as
    LabResult. Poll with `since` = the `frames` of the previous answer."""
    segment: str | None
    running: bool
    start: int
    frames: int = Field(description='whole frames processed so far')
    total: int
    fps: float
    t_s: list[float]
    lead_x_m: list[float | None]
    lead_y_m: list[float | None]
    lead_prob: list[float | None]
    lead_std_m: list[float | None]
    gap_kalman_m: list[float | None]
    ego_model_mps: list[float | None]
    ego_log_mps: list[float | None]
    radar_m: list[float | None]
    curv_gt: list[float | None] = Field(default_factory=list)
    curv_yaw: list[float | None] = Field(default_factory=list)
    curv_drawn: list[float | None] = Field(default_factory=list)


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
