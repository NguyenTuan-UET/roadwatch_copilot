"""Central configuration. All numeric thresholds live here as dataclasses."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


def default_num_threads() -> int:
    """Half the logical cores, at least 1."""
    return max(1, (os.cpu_count() or 2) // 2)


@dataclass
class OnnxConfig:
    num_threads: int = field(default_factory=default_num_threads)
    manifest_path: Path = MODELS_DIR / "manifest.json"
    # Refuse to load a model whose file is not listed in the manifest.
    require_manifest_entry: bool = False
    # Default backend for models whose own config does not set one:
    # "onnxruntime" | "openvino" | "auto" (OpenVINO if installed). OpenVINO is optional
    # and off by default: several OpenVINO models in one process slowed the others
    # down in our benchmark, and its pip package ships usage telemetry (opt out with
    # ~/intel/openvino_telemetry containing "0").
    backend: str = "onnxruntime"


# COCO class ids kept for the person/vehicle detector.
COCO_KEEP_CLASSES: dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


@dataclass
class ObjectDetectorConfig:
    model_path: Path = MODELS_DIR / "yolo11n_320.onnx"
    # Used only if the model input is dynamic; fixed-shape models use their own size.
    imgsz: int = 320
    num_classes: int = 80
    conf_thr: float = 0.35
    iou_thr: float = 0.5
    # Runs on the foreground (P-)cores; see docs/perception_benchmark.md.
    backend: str | None = None
    num_threads: int = 8
    core_type: str = "any"  # "any" | "pcore" | "ecore" (OpenVINO on hybrid Intel CPUs only)
    device: str = "CPU"  # "GPU" = Intel iGPU via OpenVINO (needs intel-opencl-icd)
    keep_classes: dict[int, str] = field(default_factory=lambda: dict(COCO_KEEP_CLASSES))


@dataclass
class WorkerConfig:
    # Results older than this many frames (vs. the current frame) are ignored.
    max_staleness_frames: int = 10
    # Lanes change slowly and a missing overlay looks like a bug, so keep the last
    # lane result much longer than sign results.
    lane_max_staleness_frames: int = 60
    sign_every_n: int = 3
    lane_every_n: int = 2
    stop_timeout_s: float = 2.0
    # Linux nice value for background work (sign/lane workers, their inference thread
    # pools, video decoding) so the per-frame object detector wins contention. 0 = off.
    worker_nice: int = 10
    # On hybrid Intel CPUs run the main loop + object detector on P-cores and all
    # background work on E-cores. This removed most of the contention in
    # docs/perception_benchmark.md. Ignored on non-hybrid CPUs.
    place_on_hybrid_cores: bool = True
    # Frames decoded ahead by the background decode thread.
    decode_prefetch: int = 4


def default_lane_model() -> Path:
    """YOLOP 640 (release lane model), preferring the variant without the unused
    detection head (identical masks, derived by scripts/download_models.py)."""
    for name in ("yolop-640-640-seg.onnx", "yolop-640-640.onnx"):
        if (MODELS_DIR / name).exists():
            return MODELS_DIR / name
    return MODELS_DIR / "yolop-640-640-seg.onnx"


@dataclass
class LaneConfig:
    model_path: Path = field(default_factory=default_lane_model)
    imgsz: int = 640  # only used if the model input is dynamic
    backend: str | None = None
    num_threads: int = 4
    core_type: str = "any"
    device: str = "CPU"
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
    # Output names are matched by substring; the loader fails loudly if absent.
    lane_output_key: str = "lane"
    drivable_output_key: str = "drive"

    # Scan rows as fractions of image height.
    scan_rows: tuple[float, ...] = (0.7, 0.8, 0.9)
    scan_band_px: int = 4  # rows OR-ed above and below each scan row
    cluster_gap_px: int = 6  # runs closer than this are merged into one line
    min_cluster_px: int = 2
    # Plausible lane width at a scan row, as a fraction of image width.
    min_lane_width_frac: float = 0.12
    max_lane_width_frac: float = 1.2
    # A border may move outward by at most this (fraction of width) from the row below.
    perspective_tol_frac: float = 0.02
    history_frames: int = 10  # for width stability
    border_ema_alpha: float = 0.5  # weight of the new observation

    # quality = w_cov*coverage + w_width*width_stability + w_pix*min(1, pixels/pixel_norm)
    w_coverage: float = 0.5
    w_width: float = 0.3
    w_pixels: float = 0.2
    # Lane-line pixels in the bottom half giving full pixel score (fraction of that area).
    pixel_norm_frac: float = 0.004
    good_quality: float = 0.6


def default_sign_model() -> Path:
    """Prefer a locally retrained 416 model; fall back to the upstream 768 one."""
    retrained = MODELS_DIR / "vn_signs_416.onnx"
    return retrained if retrained.exists() else MODELS_DIR / "vn_signs_best.onnx"


@dataclass
class SignConfig:
    model_path: Path = field(default_factory=default_sign_model)
    classes_path: Path = MODELS_DIR / "sign_classes.json"
    imgsz: int = 416  # only used if the model input is dynamic
    conf_thr: float = 0.5
    iou_thr: float = 0.5
    backend: str | None = None
    num_threads: int = 2
    core_type: str = "any"
    device: str = "CPU"


@dataclass
class TrackerConfig:
    """ByteTrack + camera-motion compensation (roadwatch/tracking)."""

    # Detections below low_conf_thr are ignored; low..high only extend existing
    # tracks (stage 2); only >= new_track_thr can start a track.
    low_conf_thr: float = 0.1
    high_conf_thr: float = 0.3
    new_track_thr: float = 0.35
    match_thr: float = 0.8  # max cost 1 - IoU*score, confirmed/lost tracks vs high dets
    low_match_thr: float = 0.5  # max cost 1 - IoU, tracked tracks vs low dets
    unconfirmed_match_thr: float = 0.7
    min_hits: int = 2  # matches before a track is confirmed (gets an id on screen)
    max_lost_s: float = 1.0  # a track without a match for this long is deleted
    coast_frames: int = 5  # confirmed tracks are still reported (predicted box) this long
    use_gmc: bool = True
    gmc_downscale_width: int = 640
    gmc_max_corners: int = 400
    history_len: int = 45  # observed boxes kept per track
    # Kinematics (image space, uncalibrated) from the last kin_window_s of observations.
    kin_window_s: float = 0.6
    kin_min_points: int = 5
    kin_min_span_s: float = 0.25
    border_margin_px: int = 3  # boxes this close to the border count as truncated


@dataclass
class EvidenceConfig:
    """Temporal confirmation of a risk condition before it becomes an alert."""

    window_s: float = 0.5  # look-back window
    confirm_s: float = 0.3  # condition must have been observed for at least this long
    ratio: float = 0.6  # ... in at least this share of the frames in the window
    release_s: float = 0.5  # alert ends after the condition is absent this long
    hold_s: float = 1.0  # minimum time an alert stays on screen


@dataclass
class RiskConfig:
    """Deterministic risk rules on perception + tracking output (roadwatch/risk).

    Geometry is image-space only. Lateral positions are in "lane widths" of the
    ego corridor at the object's ground-contact row; depth is the normalised
    row d = (y_bottom - horizon) / (H - horizon): 0 at the horizon, 1 at the
    bottom edge. All times are estimates without camera calibration.
    """

    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)

    # Ego corridor when no good lane is available.
    default_horizon_frac: float = 0.5
    default_half_width_frac: float = 0.3  # half corridor width at the bottom row / W
    horizon_ema_alpha: float = 0.1  # horizon learned from good lane lines
    horizon_range_frac: tuple[float, float] = (0.3, 0.75)
    lane_max_age_s: float = 0.5  # older lane results are not used by risk rules

    in_path_overlap: float = 0.3  # share of the box width inside the corridor
    min_depth: float = 0.15  # ignore objects nearer the horizon than this (too far)

    # FCW: four-wheelers in path; tau = scale-expansion time-to-contact (estimated).
    fcw_warning_tau_s: float = 1.8
    fcw_caution_tau_s: float = 3.0
    fcw_min_depth: float = 0.2

    # VRU: person / bicycle / motorcycle.
    vru_near_depth: float = 0.55  # in path and at least this near: caution
    vru_warning_tau_s: float = 2.0
    vru_caution_tau_s: float = 3.5
    vru_path_margin: float = 0.15  # corridor widened by this many lane widths per side
    vru_enter_horizon_s: float = 1.5  # predicted to enter the widened corridor within this
    rider_overlap: float = 0.3  # person box share overlapping a two-wheeler = rider

    # Lateral motion in lane widths per second (du/dt), four-wheelers only.
    cut_in_min_speed: float = 0.15
    cut_in_max_gap: float = 0.6  # near box edge at most this far outside the corridor
    cut_in_horizon_s: float = 1.2  # predicted corridor entry within this
    cut_in_warning_s: float = 0.6
    cut_in_min_depth: float = 0.3
    cross_min_speed: float = 0.8  # faster lateral motion = crossing, not merging
    cross_horizon_s: float = 1.5
    cross_warning_s: float = 0.8
    lateral_window_s: float = 0.6
    lateral_min_points: int = 5
    bottom_margin_px: int = 3  # box bottom this close to the image edge: no lateral estimate

    # LDW from the lane offset (camera centre vs lane centre, in lane widths).
    ldw_line_offset: float = 0.3  # |offset| where a wheel is roughly on the line
    ldw_caution_offset: float = 0.15
    ldw_tlc_s: float = 1.0  # caution: predicted to reach ldw_line_offset within this
    ldw_min_rate: float = 0.05  # 1/s outward drift for a warning
    ldw_min_coverage: float = 0.66
    ldw_window_s: float = 1.0
    ldw_min_points: int = 3
    ldw_jump: float = 0.5  # offset jump between results = lane change done; restart

    # Sign relevance + arbitration.
    sign_min_box_px: int = 14
    sign_min_x_frac: float = 0.35  # signs left of this are for the other direction...
    sign_overhead_y_frac: float = 0.35  # ...unless overhead (bottom above this row)
    sign_window_s: float = 2.0
    sign_confirm_hits: int = 3
    sign_margin: float = 1.5  # winning speed value needs this x the runner-up's votes
    sign_classifier_weight: float = 1.0
    sign_detector_class_weight: float = 0.7
    sign_disagree_weight: float = 0.5
    sign_show_s: float = 4.0  # recent confirmed signs stay on screen this long


@dataclass
class PerceptionConfig:
    # "replay": every frame gets sign/lane results computed on schedule (every_n) in
    # the calling thread; nothing is dropped, throughput is whatever the CPU allows.
    # This is the release stack's cloud-CPU replay setting and the default.
    # "live": signs/lanes run in latest-frame workers and stale results are dropped
    # so the object detector keeps real-time pace (camera input).
    mode: str = "replay"
    objects: ObjectDetectorConfig = field(default_factory=ObjectDetectorConfig)
    lanes: LaneConfig = field(default_factory=LaneConfig)
    signs: SignConfig = field(default_factory=SignConfig)
    speed_digits: SpeedDigitConfig = field(default_factory=lambda: SpeedDigitConfig())
    workers: WorkerConfig = field(default_factory=WorkerConfig)
    tracking: TrackerConfig = field(default_factory=TrackerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    enable_objects: bool = True
    enable_lanes: bool = True
    enable_signs: bool = True
    enable_tracking: bool = True
    enable_risk: bool = True  # needs tracking
    # Use the Intel iGPU (OpenVINO GPU plugin) when present: objects, lanes and signs
    # move to it and the object model becomes the mode's GPU model below (if exported).
    # Without a GPU everything stays on the CPU with objects.model_path.
    # See docs/perception_benchmark.md (P9).
    use_gpu: bool = True
    gpu_object_model_replay: Path = MODELS_DIR / "_teacher_yolo11m_640.onnx"  # most accurate
    gpu_object_model_live: Path = MODELS_DIR / "yolo11s_640.onnx"  # fits ~30 fps


@dataclass
class SpeedDigitConfig:
    """C. Speed-limit value classifier on sign crops (see scripts/train_speed_digits.py)."""

    model_path: Path = MODELS_DIR / "speed_digits_64.onnx"
    classes_path: Path = MODELS_DIR / "speed_digits_64_classes.json"
    expand: float = 0.10  # crop = sign box grown by this fraction on each side
    # Readings below this softmax confidence are reported as unknown (value None).
    min_conf: float = 0.6
    backend: str | None = None
    num_threads: int = 1
    core_type: str = "any"
