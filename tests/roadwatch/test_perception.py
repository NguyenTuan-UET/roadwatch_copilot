"""BT-A (spec §2, §4.2, ADR-04/05/09): geometry, TTC, observation, tracker, lead choice, mount check."""

import numpy as np

from src.roadwatch.detect import Tracker, postprocess
from src.roadwatch.perception import (
    MountChecker,
    Perception,
    distance_from_bottom,
    observation_status,
    ttc_from_widths,
)
from tests.roadwatch.decision_harness import make_config

MS = 1_000_000


# --- geometry (file 3 §2) ----------------------------------------------------------------------


def test_distance_matches_the_documented_example():
    q = distance_from_bottom(557.0, fy=1000.0, h_cam=1.30, y_horizon=540.0, d_cam_bumper=1.5)
    assert abs(q.value - 74.97) < 0.01 and q.status == "ok" and q.sigma is None  # no uncertainty method yet


def test_bottom_at_or_above_horizon_is_unreliable_not_zero():
    q = distance_from_bottom(540.5, fy=1000.0, h_cam=1.30, y_horizon=540.0, d_cam_bumper=1.5)
    assert q.status == "unreliable" and "at_horizon" in q.reasons


# --- TTC from scale change -------------------------------------------------------------------


def _approach(ttc0_s=3.0, n=8, dt_s=0.1, w0=40.0):
    """Width grows as 1/Z with Z closing at constant speed: TTC(t) = ttc0 - t."""
    ts = [i * dt_s for i in range(n)]
    return [int(t * 1e9) for t in ts], [w0 * ttc0_s / (ttc0_s - t) for t in ts]


def test_ttc_from_growing_width_is_close_to_truth():
    ts, ws = _approach()
    q = ttc_from_widths(ts, ws, min_frames=5, min_w=12.0, max_resid=0.02)
    true_now = 3.0 - 0.7
    assert q.status == "ok" and abs(q.value - true_now) / true_now < 0.1


def test_ttc_not_closing_is_not_applicable():
    ts, ws = _approach()
    q = ttc_from_widths(ts, list(reversed(ws)), min_frames=5, min_w=12.0, max_resid=0.02)
    assert q.status == "not_applicable" and q.value is None


def test_ttc_needs_enough_frames_width_and_a_clean_fit():
    ts, ws = _approach()
    assert ttc_from_widths(ts[:3], ws[:3], 5, 12.0, 0.02).status == "unreliable"
    assert ttc_from_widths(ts, [w / 10 for w in ws], 5, 12.0, 0.02).status == "unreliable"  # too small
    noisy = [w * (1.3 if i % 2 else 0.8) for i, w in enumerate(ws)]
    assert "poor_fit" in ttc_from_widths(ts, noisy, 5, 12.0, 0.02).reasons


# --- observation ------------------------------------------------------------------------------


def test_observation_flags_dark_and_flat_images():
    cfg = make_config().perception
    rng = np.random.default_rng(0)
    assert observation_status(np.zeros((90, 160, 3), np.uint8), cfg).reasons == ["too_dark"]
    assert observation_status(np.full((90, 160, 3), 128, np.uint8), cfg).reasons == ["low_contrast"]
    assert observation_status(rng.integers(40, 200, (90, 160, 3), dtype=np.uint8), cfg).status == "ok"


# --- detector post-processing and tracker ------------------------------------------------------


def test_postprocess_handles_yolo_raw_and_end_to_end_layouts():
    raw = np.zeros((1, 84, 3), np.float32)  # cx, cy, w, h + 80 class scores, 3 anchors
    raw[0, :4, 0] = [320, 320, 100, 50]
    raw[0, 4 + 2, 0] = 0.9  # car
    raw[0, :4, 1] = [322, 321, 100, 50]
    raw[0, 4 + 2, 1] = 0.8  # duplicate -> NMS
    raw[0, :4, 2] = [100, 100, 20, 20]
    raw[0, 4 + 0, 2] = 0.95  # person -> filtered by class
    dets = postprocess(raw, scale=1.0, pad=(0, 0), score_thr=0.3, nms_iou=0.5, class_ids=[2, 3, 5, 7])
    assert dets.shape == (1, 6) and dets[0, 5] == 2 and np.allclose(dets[0, :4], [270, 295, 370, 345])
    e2e = np.array([[[10, 20, 110, 70, 0.9, 7], [0, 0, 5, 5, 0.1, 2]]], np.float32)
    dets = postprocess(e2e, scale=2.0, pad=(0, 10), score_thr=0.3, nms_iou=0.5, class_ids=[2, 3, 5, 7])
    assert np.allclose(dets[0, :4], [5, 5, 55, 30])  # undo letterbox: (x - pad_x) / scale


def test_tracker_keeps_ids_and_uses_low_score_detections():
    tr = Tracker(high_thr=0.5, match_iou=0.3, max_lost=3)
    a = tr.step(np.array([[100, 100, 200, 180, 0.9, 2], [400, 100, 480, 170, 0.9, 2]]), 0)
    b = tr.step(np.array([[104, 102, 204, 182, 0.35, 2], [402, 101, 482, 171, 0.9, 2]]), 100 * MS)  # low score
    assert {t.track_id for t in a} == {t.track_id for t in b} and len(b) == 2


# --- perception pipeline: lead choice, identity, measurement -----------------------------------


def _frame():
    img = np.random.default_rng(1).integers(40, 200, (1080, 1920, 3), dtype=np.uint8)
    return img


def _p():
    return Perception(make_config(), detector=None)


def test_lead_is_the_closest_vehicle_inside_the_ego_roi():
    p = _p()
    dets = np.array(
        [
            [900, 520, 1020, 600, 0.9, 2],  # in lane, farther
            [880, 560, 1040, 700, 0.9, 2],  # in lane, closer -> lead
            [100, 600, 400, 900, 0.9, 2],
        ]
    )  # adjacent lane, closest but outside ROI
    m = p.process_detections(_frame(), dets, t_ns=0, sched_n=0, frame_idx=0, run_id="r", seq=0)
    assert m.lead.status == "ok" and m.lead.bbox_px == (880.0, 560.0, 1040.0, 700.0) and m.lead.basis == "fixed_roi"
    assert m.distance_m.status == "ok" and m.ttc_s.status == "unreliable"  # one frame is not enough for TTC


def test_no_vehicle_in_roi_is_not_applicable_when_observation_ok():
    p = _p()
    m = p.process_detections(_frame(), np.zeros((0, 6)), t_ns=0, sched_n=0, frame_idx=0, run_id="r", seq=0)
    assert (m.observation.status, m.lead.status, m.distance_m.status) == ("ok", "not_applicable", "not_applicable")


def test_dark_frame_makes_lead_unavailable_not_absent():
    p = _p()
    dark = np.zeros((1080, 1920, 3), np.uint8)
    m = p.process_detections(dark, np.zeros((0, 6)), t_ns=0, sched_n=0, frame_idx=0, run_id="r", seq=0)
    assert m.observation.status == "unreliable" and m.lead.status == "unavailable"


def test_placeholder_frame_gives_unavailable_measurement():
    m = _p().placeholder(t_ns=500 * MS, sched_n=5, run_id="r", seq=3)
    assert m.frame_idx is None and m.observation.status == "unavailable" and m.lead.status == "unavailable"


def test_track_id_change_at_same_place_keeps_identity():
    p = _p()
    img = _frame()
    p.process_detections(img, np.array([[880, 560, 1040, 700, 0.9, 2]]), 0, 0, 0, "r", 0)
    first = p.tracker.tracks[0].track_id
    p.tracker.tracks.clear()  # simulate the tracker dropping and re-creating the track (occlusion)
    m = p.process_detections(img, np.array([[882, 561, 1042, 701, 0.9, 2]]), 100 * MS, 1, 1, "r", 1)
    assert m.lead.track_id != first and m.lead.identity_id == first
    assert m.lead.change.reason == "likely_id_switch"


# --- mount check (ADR-05): detect and degrade, never correct ------------------------------------


def test_mount_checker_flags_a_persistent_shift_and_recovers():
    cfg = make_config(perception={"mount_t_suspect_ms": 300}).perception
    rng = np.random.default_rng(2)
    base = rng.integers(0, 255, (1080, 1920), dtype=np.uint8)
    base = np.stack([base] * 3, axis=2)
    mc = MountChecker(cfg)
    states = [mc.update(base, i * 100 * MS).state for i in range(3)]
    shifted = np.roll(base, 12, axis=0)
    states += [mc.update(shifted, (3 + i) * 100 * MS).state for i in range(6)]
    states += [mc.update(base, (9 + i) * 100 * MS).state for i in range(2)]
    assert states[:3] == ["ok"] * 3 and states[5] == "ok" and states[8] == "suspect" and states[-1] == "ok"


def test_mount_checker_without_evidence_is_unknown():
    mc = MountChecker(make_config().perception)
    flat = np.full((1080, 1920, 3), 90, np.uint8)
    assert mc.update(flat, 0).state == "unknown"
