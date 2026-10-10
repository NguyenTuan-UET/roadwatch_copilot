import numpy as np
import pytest

from src.roadwatch.calibration import AutoCalib, intrinsics
from src.roadwatch.hud import CLOSE_BGR, LEAD_BGR, draw, ego_lane_borders, project
from src.roadwatch.model import (
    PRUNED_PATH,
    detect_content_box,
    model_ticks,
    pack_frame,
    resample_tick,
    tick,
    warp_matrices,
    wide_mode,
)
from src.roadwatch.pipeline import LeadTracker, Pipeline, Result


def test_pack_order_matches_openpilot_frames_to_tensor():
    y = np.arange(256 * 512, dtype=np.uint32).reshape(256, 512).astype(np.uint8)
    u, v = np.full((128, 256), 37, np.uint8), np.full((128, 256), 91, np.uint8)
    packed = pack_frame(y, u, v, (np.eye(3), None))   # identity warp; wide input = the narrow one duplicated
    assert packed.shape == (2, 6, 128, 256)
    for i, (row, col) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        np.testing.assert_array_equal(packed[0, i], y[row::2, col::2])
    assert (packed[:, 4] == 37).all() and (packed[:, 5] == 91).all()
    np.testing.assert_array_equal(packed[0], packed[1])


def test_zero_rpy_warp_is_comma_crop():
    # openpilot MEDMODEL at fy=910 on a 1164x874 camera is a pure crop (CODEX_REPORT_2: offset 326, 389.4)
    narrow, wide = warp_matrices(intrinsics(910, 1164, 874), np.zeros(3), 1164)
    corner = narrow @ [0, 0, 1]
    assert corner[:2] / corner[2] == pytest.approx([326, 389.4])
    assert wide is not None   # 65 deg lens > 60 deg: the wide input is warped, not duplicated


def test_wide_input_is_warped_only_for_a_wide_lens():
    assert wide_mode(intrinsics(910, 1164, 874), 1164) == 'warp'          # 65 deg
    assert wide_mode(intrinsics(1100, 1164, 874), 1164) == 'dup'          # 56 deg


def test_tick_feeds_the_model_close_to_20_hz():
    assert tick(20) == (1, .05, 1.)
    stride, dt, scale = tick(30)
    assert stride == 2 and dt == pytest.approx(2 / 30) and scale == pytest.approx(.75)


@pytest.fixture
def letterbox(tmp_path):
    import cv2
    path = tmp_path / 'letterbox.mp4'
    wr = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 20, (320, 240))
    for k in range(60):
        f = np.zeros((240, 320, 3), np.uint8)
        f[40:200] = 100 + k   # 40-px black bars top and bottom
        wr.write(f)
    wr.release()
    return path


def test_content_box_crops_letterbox_bars(letterbox):
    x, y, w, h = detect_content_box(letterbox)
    assert x == 0 and w == 320 and abs(y - 40) <= 2 and abs(h - 160) <= 4 and y % 2 == 0


def test_content_box_samples_keyframes_without_seeking_in_opencv(letterbox, monkeypatch):
    """OpenCV seeks decode from the previous keyframe: 43 s on a 4K upload with a keyframe every 12.5 s."""
    from src.roadwatch import model

    class NoSeek:
        def __init__(self, *_):
            raise AssertionError('OpenCV must not be used to sample frames')
    monkeypatch.setattr(model.cv2, 'VideoCapture', NoSeek)
    assert detect_content_box(letterbox)[1] in (40, 42)


def test_autocalib_converges_and_applies_roll_pitch_and_yaw():
    cal = AutoCalib()
    pose, road = np.array([10., .1, .2, 0, 0, 0]), np.array([0, 0, 1.3, .03, 0, 0])
    for _ in range(300):
        cal.update(pose)
    np.testing.assert_allclose(cal.est[1:], [-np.arctan2(.2, 10), np.arctan2(.1, 10)], atol=1e-4)
    assert cal.settled and cal.rpy[1:] == pytest.approx(cal.est[1:])
    cal.update(np.zeros(6), road, np.zeros(6))
    assert cal.est[0] != 0 and cal.rpy[0] == cal.est[0]
    assert not cal.update(pose * [0, 1, 1, 1, 1, 1])   # stopped, no road_transform: nothing learned


def test_autocalib_composes_residuals_with_the_warp_in_use():
    cal = AutoCalib()
    cal.warp_rpy = np.array([0., 0., .02])   # warp already corrected by .02 rad yaw: model sees a residual
    for _ in range(300):
        cal.update(np.array([10., np.tan(.01) * 10, 0, 0, 0, 0]))
    assert cal.est[2] == pytest.approx(.03, abs=1e-4)


def test_autocalib_skips_an_uncertain_road_transform():
    cal = AutoCalib()
    road, std = np.array([0, 0, 1.3, 0, .05, 0]), np.full(6, np.radians(5))
    assert not cal.update(np.zeros(6), road, std)
    assert cal.update(np.zeros(6), road, std * 0) and cal.est[1] > 0


class FakeModel:
    """Model outputs with a lead at (x, y), probability p, ego at 10 m/s per model frame, a certain road."""
    def __init__(self):
        self.x, self.y, self.p = 30., 0., .9

    def reset(self):
        pass

    def step(self, _):
        lead, stds = np.zeros((1, 3, 6, 4)), np.ones((1, 3, 6, 4))
        lead[0, 0, 0, :3] = self.x, self.y, 8.
        return dict(pose=np.array([[10., 0, 0, 0, 0, 0]]), road_transform=np.array([[0, 0, 1.3, 0, 0, 0]]),
                    road_transform_stds=np.zeros((1, 6)), lead=lead, lead_stds=stds,
                    lead_prob=np.array([[self.p, 0, 0]]))


def _step(pipe):
    return pipe.step(np.zeros((874, 1164), np.uint8), *[np.full((437, 582), 128, np.uint8)] * 2)


def test_lead_needs_settled_calibration_and_the_lane_from_the_camera_axis():
    """Like comma_ai realtime_lead: settled angles, p >= 0.5, |y| <= 2 m, x > 0; no lead before calibration."""
    m = FakeModel()
    pipe = Pipeline(1164, 874, 910, 1.5, m)
    assert all(_step(pipe).gap_m is None for _ in range(AutoCalib.SETTLED_SAMPLES - 1))
    r = _step(pipe)
    assert r.status == 'calibrated' and r.gap_m == pytest.approx(28.5) and r.lead_x_m == pytest.approx(30.)
    m.y = 2.5                                            # neighbour lane: the Kalman track coasts 0.5 s, then drops
    assert _step(pipe).gap_m is not None
    for _ in range(11):
        r = _step(pipe)
    assert r.gap_m is None


def test_velocities_are_rescaled_to_the_tick_and_ego_is_smoothed():
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), tick_dt=2 / 30)   # 30 fps video, every 2nd frame
    r = _step(pipe)
    assert r.ego_speed_mps == pytest.approx(.15 * 10 * .75)
    for _ in range(100):
        r = _step(pipe)
    assert r.ego_speed_mps == pytest.approx(7.5) and r.lead_speed_mps == pytest.approx(6.)


def test_lead_tracker_smooths_and_restarts_on_a_new_vehicle():
    tr = LeadTracker()
    rng = np.random.default_rng(0)
    est = [tr.update(.05, 30. + rng.normal(0, 1), 1.)[0] for _ in range(100)]
    assert np.std(est[50:]) < 0.5
    assert tr.update(.05, 12., 1.)[0] == 12.        # cut-in 18 m closer: restart, not a slow slide
    assert tr.update(.05, None, 1.) is not None      # short gap keeps the track
    for _ in range(10):
        last = tr.update(.05, None, 1.)
    assert last is None


def test_project_road_point_below_principal_point():
    cam_k = intrinsics(910, 1164, 874)
    px, ok = project(cam_k, np.zeros(3), [[20., 0., 1.2]])
    u, v = px[0]
    assert ok[0] and u == pytest.approx(582) and v == pytest.approx(437 + 910 * 1.2 / 20)


@pytest.mark.skipif(not PRUNED_PATH.exists(), reason='run scripts/roadwatch/download_model.py')
def test_gr14vinai_runs_on_black_frames():
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


@pytest.mark.parametrize('gap', [None, 20.0])
def test_hud_draws_with_and_without_a_lead(gap):
    lanes = np.zeros((1, 4, 33, 2))
    lanes[0, 1, :, 0], lanes[0, 2, :, 0], lanes[0, :, :, 1] = -1.8, 1.8, 1.2
    lead = np.zeros((1, 3, 6, 4))
    lead[0, 0, 0, :2] = 21.5, 0.2
    outputs = dict(lead=lead, lane_lines=lanes, lane_lines_prob=np.full((1, 8), .9))
    r = Result('calibrated', np.zeros(3), 1.2, 25.0, .9, gap, 20.0, 4.0 if gap else None, outputs,
               1.5 if gap else None, .2 if gap else None, np.array([0, .02, 0]), 21.5 if gap else None)
    frame = np.full((874, 1164, 3), 90, np.uint8)
    out = draw(frame.copy(), intrinsics(910, 1164, 874), r, 910.)
    assert out.shape == frame.shape and (out != frame).any()


def _hud_result(lane_z, lane_prob=.9, gap=20.0, ego=10.0):
    lanes = np.zeros((1, 4, 33, 2))
    lanes[0, 1, :, 0], lanes[0, 2, :, 0], lanes[0, :, :, 1] = -1.8, 1.8, lane_z
    lead = np.zeros((1, 3, 6, 4))
    lead[0, 0, 0, :2] = 21.5, 0.2
    outputs = dict(lead=lead, lane_lines=lanes, lane_lines_prob=np.full((1, 8), lane_prob))
    return Result('calibrated', np.zeros(3), 1.2, ego, .9, gap, 9.0, None, outputs, 1.5, .2, np.zeros(3), 21.5)


@pytest.mark.parametrize('lane_prob, z', [(.9, .6), (.1, 1.2)])
def test_hud_chevron_sits_on_the_road_under_the_lead(lane_prob, z):
    """Like comma_ai overlay: the chevron uses the ego-lane centre height at the lead distance (the road the
    lead stands on), not the fixed camera height; without confident lanes it falls back to the camera height."""
    r, cam_k = _hud_result(.6, lane_prob), intrinsics(910, 1164, 874)
    out = draw(np.full((874, 1164, 3), 90, np.uint8), cam_k, r, 910.)
    ((u, v),), _ = project(cam_k, r.rpy, [[21.5, .2, z]])
    assert tuple(out[int(round(v)), int(round(u))]) == LEAD_BGR


def test_hud_close_is_the_time_gap_only():
    cam_k = intrinsics(910, 1164, 874)
    out = draw(np.full((874, 1164, 3), 90, np.uint8), cam_k, _hud_result(1.2, gap=20.0, ego=25.0), 910.)
    ((u, v),), _ = project(cam_k, np.zeros(3), [[21.5, .2, 1.2]])
    assert tuple(out[int(round(v)), int(round(u))]) == CLOSE_BGR


def test_ego_lane_falls_back_to_the_planned_path_on_the_road():
    """Like comma_ai overlay: a nominal lane around the planned path; the plan starts at the camera (z = 0),
    so the camera height puts it on the road."""
    lanes, plan = np.zeros((4, 33, 2)), np.zeros((33, 15))
    plan[:, 0], plan[:, 1], plan[:, 2] = np.linspace(0, 100, 33), np.linspace(0, 1, 33), np.linspace(0, -0.5, 33)
    xs, (yl, zl), (yr, zr) = ego_lane_borders(lanes, [.1, .9], plan, 30.0, 1.3)
    assert xs[-1] == 30.0
    np.testing.assert_allclose(yl, xs / 100 - 1.75)
    np.testing.assert_allclose(yr, xs / 100 + 1.75)
    np.testing.assert_allclose(zl, 1.3 - xs / 200)


def test_ego_lane_without_a_plan_head_is_on_the_camera_axis():
    xs, (yl, zl), (yr, zr) = ego_lane_borders(np.zeros((4, 33, 2)), [.1, .9], None, 30.0, 1.3)
    assert np.allclose(yl, -1.75) and np.allclose(yr, 1.75) and np.allclose(zl, 1.3)


class FixedGps:
    """GpsRef stand-in: already synced, constant speed."""
    def __init__(self, v):
        self.v, self.seen = v, []

    def observe(self, pts, v_model):
        self.seen.append((pts, v_model))

    def __call__(self, pts):
        return self.v


def test_gps_speed_replaces_the_model_speed_like_realtime_lead():
    gps = FixedGps(20.)
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), v_ref=gps)
    for _ in range(100):
        r = _step(pipe)
    assert r.ego_speed_mps == pytest.approx(20.) and r.gps_speed_mps == 20.
    assert gps.seen[1] == (pytest.approx(.05), 10.)   # observed with the model speed at the tick time


def test_focal_follows_the_gps_speed_ratio():
    from src.roadwatch.calibration import FocalFromSpeed
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), v_ref=FixedGps(20.), focal=FocalFromSpeed(910.))
    for _ in range(FocalFromSpeed.BATCH_FIRST):
        r = _step(pipe)
    assert pipe.K[0, 0] == pytest.approx(910 * 1.6) and r.fy_px == pytest.approx(910 * 1.6)   # 2x, step capped at 1.6


def test_rows_are_the_realtime_lead_csv(tmp_path):
    from src.roadwatch.pipeline import CSV_HEADER
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel())
    for _ in range(AutoCalib.SETTLED_SAMPLES + 1):
        _step(pipe)
    pipe.save_csv(tmp_path / 'lead.csv')
    lines = (tmp_path / 'lead.csv').read_text().splitlines()
    assert lines[0] == CSV_HEADER and len(lines) == AutoCalib.SETTLED_SAMPLES + 2
    last = dict(zip(CSV_HEADER.split(','), map(float, lines[-1].split(','))))
    assert last['lead_dist_raw_m'] == 30. and last['lead_dist_bumper_m'] == pytest.approx(28.5)
    assert last['calib_settled'] == 1. and last['focal_px'] == 910. and np.isnan(last['ego_speed_gps_mps'])


def test_pitch_can_be_left_out_of_the_warp():
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), use_pitch=False)
    assert pipe.cal.mask[1] == 0


def test_fixed_angles_skip_online_calibration_like_comma_app():
    """comma lead_distance app.py: the pre-pass yaw is applied for the whole run, the lead is used from the start."""
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), wide='dup', rpy=[0, 0, .02], rpy_est=[.01, -.03, .02])
    assert pipe.warps[1] is None   # 65 deg lens, but the wide input is duplicated as asked
    r = _step(pipe)
    assert r.status == 'calibrated' and r.gap_m == pytest.approx(28.5)
    assert r.rpy.tolist() == [0, 0, .02] and r.rpy_est.tolist() == [.01, -.03, .02] and pipe.cal.n == 0


def test_a_learned_calibration_can_be_handed_over():
    cal = AutoCalib()
    cal.est, cal.n = np.array([0, .01, .02]), AutoCalib.SETTLED_SAMPLES
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), cal=cal)
    assert pipe.rpy.tolist() == [0, .01, .02] and _step(pipe).gap_m is not None


def test_wide_mode_can_be_forced():
    k = intrinsics(1100, 1164, 874)   # 56 deg: auto duplicates
    assert wide_mode(k, 1164, 'warp') == 'warp' and warp_matrices(k, np.zeros(3), 1164, 'warp')[1] is not None


def _planes(value):
    return (np.full((4, 4), value, np.uint8),) * 3


def test_model_ticks_stride_and_blend_like_realtime_lead():
    frames = [_planes(10 * i) for i in range(6)]
    dt, scale = resample_tick(30, 'stride')
    ticks = [len(t) for *_, t in model_ticks(frames, 30, dt)]
    assert ticks == [1, 0, 1, 0, 1, 0] and scale == pytest.approx(.75)
    dt, scale = resample_tick(30, 'blend')
    out = [(i, [int(p[0][0, 0]) for p in t]) for i, _, _, t in model_ticks(frames, 30, dt, blend=True)]
    assert dt == .05 and scale == 1.
    # 20 Hz ticks at 0, 50, 100, 150, 200 ms on 30 fps frames (33.3 ms apart): frames 0, 2, 3, 5 and blends between
    assert out == [(0, [0]), (1, []), (2, [15]), (3, [30]), (4, []), (5, [45])]
    out = [len(t) for *_, t in model_ticks([_planes(0)] * 3, 10, .05, blend=True)]
    assert out == [1, 2, 2]   # a 10 fps video: two ticks per frame
