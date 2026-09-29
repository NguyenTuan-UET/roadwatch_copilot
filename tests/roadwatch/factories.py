"""Small builders for valid contract objects; tests override only what they exercise."""

import copy

from src.roadwatch.contracts.base import Q
from src.roadwatch.contracts.streams import Lead, Measurement, MountCheck, Observation

_CONFIG = {
    "camera": {
        "fx_px": 1000.0,
        "fy_px": 1000.0,
        "cx_px": 960.0,
        "cy_px": 540.0,
        "width_px": 1920,
        "height_px": 1080,
        "dist": [],
    },
    "mount": {
        "h_cam_m": 1.30,
        "d_cam_bumper_m": 1.5,
        "pitch_deg": 0.0,
        "roll_deg": 0.0,
        "yaw_deg": 0.0,
        "y_horizon_px": 540.0,
        "provisional_keys": ["h_cam_m", "d_cam_bumper_m", "y_horizon_px"],
    },
    "detector": {
        "model_path": "models/detector.onnx",
        "model_sha256": "0" * 64,
        "imgsz": 640,
        "score_thr": 0.35,
        "nms_iou": 0.5,
        "vehicle_class_ids": [2, 3, 5, 7],
    },
    "perception": {
        "roi_bottom_half_width": 0.35,
        "roi_top_half_width": 0.06,
        "roi_top_y": 0.52,
        "ttc_min_frames": 5,
        "ttc_min_bbox_w_px": 12.0,
        "ttc_max_resid": 0.02,
        "obs_min_luma": 20.0,
        "obs_max_luma": 235.0,
        "obs_min_std": 8.0,
        "mount_enabled": True,
        "mount_suspect_px": 6.0,
        "mount_recover_px": 3.0,
        "mount_t_suspect_ms": 2000,
        "mount_trust_window_ms": 600000,
        "mount_flap_n": 3,
        "mount_flap_window_ms": 300000,
        "mount_strip_frac": 0.12,
        "mount_min_response": 0.1,
    },
    "runtime": {
        "process_hz": 10.0,
        "tick_period_ms": 100,
        "q_measure": 8,
        "q_speed": 16,
        "q_log": 10000,
        "hang_timeout_ms": 2000,
        "max_measurement_gap_ms": 1000,
        "max_measurement_age_ms": 500,
    },
    "legal_table": {
        "legal_ref": "TT 38/2024/TT-BGTVT Điều 11 (provisional copy)",
        "bands": [
            {"v_min_kmh": 60.0, "v_max_kmh": 80.0, "min_distance_m": 55.0},
            {"v_min_kmh": 80.0, "v_max_kmh": 100.0, "min_distance_m": 70.0},
            {"v_min_kmh": 100.0, "v_max_kmh": 120.0, "min_distance_m": 100.0},
        ],
    },
    "ttc": {"ttc_emergency_s": 1.8, "t_clear_e_ms": 1500, "h_ttc_s": 0.5, "min_ttc_rate_hz": 6.0},
    "dispatch": {
        "t_confirm_ms": 1500,
        "h_m": 5.0,
        "t_clear_ms": 2000,
        "cooldown_ms": 10000,
        "t_hold_ms": 1000,
        "novice_margin_m": 0.0,
    },
    "speed": {"fresh_max_ms": 1500, "lost_after_ms": 5000, "stale_policy": "unusable"},
    "status_msgs": {"t_notify_ms": 2000, "remind_interval_ms": None},
    "audio": {
        "max_cmd_age_ms": 1500,
        "phrase_dir": "models/phrases",
        "phrases": {
            "emergency": 1200,
            "warning": 1500,
            "info": 1400,
            "system_off": 1800,
            "cap_distance_off": 1900,
            "cap_ttc_off": 1800,
            "recovery": 1500,
            "reminder": 1800,
        },
    },
}


def config_dict() -> dict:
    return copy.deepcopy(_CONFIG)


def lead_ok(**kw) -> Lead:
    base = dict(
        status="ok",
        identity_id=1,
        track_id=7,
        since_t_ns=0,
        basis="fixed_roi",
        bbox_px=(900.0, 500.0, 1020.0, 560.0),
        det_score=0.9,
    )
    return Lead(**{**base, **kw})


def measurement(**kw) -> Measurement:
    base = dict(
        run_id="r",
        seq=0,
        t_ns=0,
        sched_n=0,
        frame_idx=0,
        observation=Observation(status="ok"),
        mount_check=MountCheck(state="ok", since_t_ns=0),
        lead=lead_ok(),
        distance_m=Q(status="ok", value=60.0),
        ttc_s=Q(status="ok", value=8.0),
    )
    return Measurement(**{**base, **kw})
