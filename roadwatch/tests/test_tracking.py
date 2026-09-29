import cv2
import numpy as np
import pytest

from roadwatch.config import TrackerConfig
from roadwatch.tracking import ByteTracker, CameraMotion, estimate_kinematics
from roadwatch.tracking.tracker import iou_matrix
from roadwatch.types import Detection

FPS = 30.0
NO_GMC = TrackerConfig(use_gmc=False)


def run(tracker, frames):
    """frames: list of detection lists; returns the list of per-frame track snapshots."""
    return [tracker.update(dets, i / FPS) for i, dets in enumerate(frames)]


def test_iou_matrix():
    a = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], float)
    b = np.array([[5, 0, 15, 10]], float)
    np.testing.assert_allclose(iou_matrix(a, b), [[50 / 150], [0.0]])
    assert iou_matrix(a, np.zeros((0, 4))).shape == (2, 0)


def test_ids_persist_for_two_moving_objects():
    frames = [[Detection((100 + 3 * i, 100, 160 + 3 * i, 150), "car", 0.9),
               Detection((400 - 2 * i, 200, 440 - 2 * i, 280), "person", 0.8)] for i in range(30)]
    out = run(ByteTracker(NO_GMC), frames)
    assert out[0] == []  # tentative on the first frame
    ids = {(t.cls, t.track_id) for snap in out[1:] for t in snap}
    assert ids == {("car", 1), ("person", 2)}


def test_low_confidence_detections_keep_a_track_alive():
    """ByteTrack stage 2: a partly occluded object with a weak box keeps its id."""
    frames = [[Detection((100 + 2 * i, 100, 160 + 2 * i, 150), "car",
                         0.9 if i < 10 or i > 15 else 0.15)] for i in range(25)]
    out = run(ByteTracker(NO_GMC), frames)
    assert all(len(s) == 1 and s[0].track_id == 1 and s[0].observed for s in out[1:])


def test_track_survives_a_short_gap_and_dies_after_max_lost():
    cfg = TrackerConfig(use_gmc=False, max_lost_s=0.3)
    box = Detection((100, 100, 160, 150), "car", 0.9)
    tr = ByteTracker(cfg)
    run(tr, [[box]] * 5)
    # 5 frames without detections (~0.17 s): coasted, then re-matched with the same id.
    for i in range(5, 10):
        snap = tr.update([], i / FPS)
    assert snap and not snap[0].observed and snap[0].lost_frames == 5
    assert tr.update([box], 10 / FPS)[0].track_id == 1
    for i in range(11, 25):
        tr.update([], i / FPS)
    assert tr.update([box], 25 / FPS) == []  # old track deleted; new tentative track
    assert tr.update([box], 26 / FPS)[0].track_id == 2


def test_no_match_across_class_groups():
    frames = [[Detection((100, 100, 160, 150), "car" if i < 5 else "person", 0.9)] for i in range(10)]
    out = run(ByteTracker(NO_GMC), frames)
    assert [(t.track_id, t.cls) for t in out[4]] == [(1, "car")]
    # The car track only coasts (not observed); the person gets a new id.
    assert {(t.track_id, t.cls, t.observed) for t in out[9]} == {(1, "car", False),
                                                                  (2, "person", True)}


def test_class_is_a_vote_within_a_group():
    frames = [[Detection((100, 100, 160, 150), "motorcycle" if i % 4 else "bicycle", 0.8)]
              for i in range(12)]
    out = run(ByteTracker(NO_GMC), frames)
    assert out[-1][0].cls == "motorcycle" and out[-1][0].track_id == 1


def test_reset_restarts_ids():
    tr = ByteTracker(NO_GMC)
    run(tr, [[Detection((0, 0, 10, 10), "car", 0.9)]] * 3)
    tr.reset()
    out = run(tr, [[Detection((0, 0, 10, 10), "car", 0.9)]] * 3)
    assert out[-1][0].track_id == 1


def test_kinematics_expanding_box_gives_tau():
    # Size grows as 1 / (T - t) (constant closing speed): tau at the last frame = T - t.
    T = 2.0
    rows = []
    for i in range(20):
        t = i / FPS
        s = 40.0 / (T - t)
        rows.append([t, 320 - s, 200 - s, 320 + s, 200 + s])
    kin = estimate_kinematics(np.array(rows), (720, 1280), 0.6, 5, 0.25, 3)
    assert kin is not None and kin.uncalibrated
    assert kin.tau_s == pytest.approx(T - 19 / FPS, rel=0.1)
    assert abs(kin.vx_px_s) < 1e-6


def test_kinematics_needs_enough_evidence():
    rows = np.array([[i / FPS, 0, 0, 10, 10] for i in range(4)], float)
    assert estimate_kinematics(rows, (720, 1280), 0.6, 5, 0.25, 3) is None
    rows = np.array([[i / 100, 0, 0, 10, 10] for i in range(10)], float)  # only 0.09 s
    assert estimate_kinematics(rows, (720, 1280), 0.6, 5, 0.25, 3) is None


def test_kinematics_box_cut_on_two_sides_has_no_tau():
    rows = [[i / FPS, 0, 400 - 5 * i, 50 + 5 * i, 720] for i in range(10)]  # left + bottom
    kin = estimate_kinematics(np.array(rows, float), (720, 1280), 0.6, 5, 0.25, 3)
    assert kin.truncated and kin.size_from == "none" and kin.tau_s is None


def test_kinematics_close_lead_cut_at_the_bottom_uses_width():
    """A close lead vehicle: bottom cut by the image edge, width still grows with 1/(T-t)."""
    T = 1.5
    rows = []
    for i in range(20):
        t = i / FPS
        half = 60.0 / (T - t)
        rows.append([t, 640 - half, 500, 640 + half, 720])  # height is meaningless
    kin = estimate_kinematics(np.array(rows), (720, 1280), 0.6, 5, 0.25, 3)
    assert kin.size_from == "width" and not kin.truncated
    assert kin.tau_s == pytest.approx(T - 19 / FPS, rel=0.1)


def textured(h=360, w=640, seed=0):
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.integers(0, 255, (h, w), np.uint8), (5, 5), 0)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_camera_motion_recovers_a_shift():
    img = textured()
    shifted = cv2.warpAffine(img, np.float32([[1, 0, 7], [0, 1, -4]]), (640, 360),
                             borderMode=cv2.BORDER_REFLECT)
    gmc = CameraMotion()
    np.testing.assert_allclose(gmc.estimate(img, np.zeros((0, 4))), np.eye(2, 3))
    a = gmc.estimate(shifted, np.zeros((0, 4)))
    np.testing.assert_allclose(a[:, 2], [7, -4], atol=0.5)
    np.testing.assert_allclose(a[:, :2], np.eye(2), atol=0.02)


def test_gmc_keeps_id_under_camera_pan():
    """A static object seen by a panning camera: the pan alone would break IoU matching."""
    base = textured(360, 1280)
    frames, dets = [], []
    for i in range(12):
        dx = -25 * i  # camera pans right: the scene moves left 25 px per frame
        frames.append(cv2.warpAffine(base, np.float32([[1, 0, dx], [0, 1, 0]]), (1280, 360),
                                     borderMode=cv2.BORDER_REFLECT))
        dets.append([Detection((600 + dx, 150, 630 + dx, 180), "person", 0.9)])
    tr = ByteTracker(TrackerConfig())
    snaps = [tr.update(d, i / FPS, f) for i, (d, f) in enumerate(zip(dets, frames))]
    assert {t.track_id for s in snaps[1:] for t in s} == {1}
    # Compensated history: the object does not move relative to the scene.
    kin = snaps[-1][0].kinematics
    assert kin is not None and abs(kin.vx_px_s) < 30

    no_gmc = ByteTracker(NO_GMC)
    ids = {t.track_id for i, d in enumerate(dets) for t in no_gmc.update(d, i / FPS)}
    assert len(ids) == 0  # without compensation no box ever matches twice
