import numpy as np
import pytest

from src.roadwatch.calibration import BlockCalibration, intrinsics
from src.roadwatch.hud import project
from src.roadwatch.model import PRUNED_PATH, pack_frame, sampling_indices, warp_maps


def test_pack_order_matches_openpilot_frames_to_tensor():
    y = np.arange(256 * 512, dtype=np.uint32).reshape(256, 512).astype(np.uint8)
    u, v = np.full((128, 256), 37, np.uint8), np.full((128, 256), 91, np.uint8)
    maps = [(sampling_indices(np.eye(3, dtype=np.float32), 512, 256, 512, 256),
             sampling_indices(np.eye(3, dtype=np.float32), 256, 128, 256, 128))] * 2
    packed = pack_frame(y, u, v, maps)
    assert packed.shape == (2, 6, 128, 256)
    for i, (row, col) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        np.testing.assert_array_equal(packed[0, i], y[row::2, col::2])
    assert (packed[:, 4] == 37).all() and (packed[:, 5] == 91).all()


def test_zero_rpy_warp_is_comma_crop():
    # openpilot MEDMODEL at fy=910 on a 1164x874 camera is a pure crop (CODEX_REPORT_2: offset 326, 389.4)
    (ry, rx), _ = warp_maps(intrinsics(910, 1164, 874), np.zeros(3), 1164, 874)[0]
    assert rx[0, 0] == 326 and ry[0, 0] == 389


def test_block_calibration_converges_and_gates_speed():
    cal = BlockCalibration()
    pose = np.array([10., .1, .2, 0, 0, 0])
    for _ in range(100):
        cal.update(pose, np.zeros(6), np.zeros(6))
    np.testing.assert_allclose(cal.rpy[1:], [-np.arctan2(.2, 10), np.arctan2(.1, 10)])
    assert not cal.update(pose * [0, 1, 1, 1, 1, 1], np.zeros(6), np.zeros(6))


def test_remount_resets_calibration():
    cal = BlockCalibration()
    for _ in range(600):
        cal.update(np.array([10., 0, 0, 0, 0, 0]), np.zeros(6), np.zeros(6))
    assert cal.calibrated
    for _ in range(200):   # camera re-mounted: yaw jumps by ~1.1 deg (below calibrationd's 2 deg spread)
        cal.update(np.array([10., .2, 0, 0, 0, 0]), np.zeros(6), np.zeros(6))
    assert cal.resets == 1 and not cal.calibrated
    assert abs(cal.rpy[2] - np.arctan2(.2, 10)) < 1e-3


def test_project_road_point_below_principal_point():
    cam_k = intrinsics(910, 1164, 874)
    px, ok = project(cam_k, np.zeros(3), [[20., 0., 1.2]])
    u, v = px[0]
    assert ok[0] and u == pytest.approx(582) and v == pytest.approx(437 + 910 * 1.2 / 20)


@pytest.mark.skipif(not PRUNED_PATH.exists(), reason='run scripts/roadwatch/download_model.py')
def test_gr14vinai_runs_on_black_frames():
    from src.roadwatch.pipeline import Pipeline
    pipe = Pipeline(1164, 874, 910, 1.5)
    y, uv = np.zeros((874, 1164), np.uint8), np.full((437, 582), 128, np.uint8)
    r = pipe.step(y, uv, uv)
    assert r.status.startswith('calibrating') and np.isfinite(r.height_m)


@pytest.mark.skipif(not PRUNED_PATH.exists(), reason='run scripts/roadwatch/download_model.py')
def test_learn_fy_refuses_a_stationary_clip():
    from src.roadwatch.calibration import learn_fy
    from src.roadwatch.model import Gr14VinAI
    y, uv = np.zeros((874, 1164), np.uint8), np.full((437, 582), 128, np.uint8)
    with pytest.raises(ValueError, match='quá chậm'):
        learn_fy([(y, uv, uv)] * 8, 1164, 874, Gr14VinAI(), grid=[910.0])



def test_learn_fy_refuses_a_best_fy_at_the_grid_edge(monkeypatch):
    from src.roadwatch import calibration
    rows = [dict(fy=f, speed_mps=20.0, score=f) for f in (500.0, 900.0, 1300.0)]   # lowest score at the first fy
    monkeypatch.setattr(calibration, '_sweep', lambda *a, **k: (500.0, rows))
    with pytest.raises(ValueError, match='biên dải dò'):
        calibration.learn_fy([], 1280, 720, None, grid=[500.0, 900.0, 1300.0])
