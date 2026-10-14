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
    """Model outputs with a lead at (x, y), probability p, ego at 10 m/s per model frame turning at yaw rad/s,
    a certain road; lanes: ego-lane centre y at each X_IDXS (lane lines 1.8 m either side, confident), or None."""
    def __init__(self):
        self.x, self.y, self.p, self.yaw, self.lanes, self.plan_y = 30., 0., .9, 0., None, None

    def reset(self):
        pass

    def step(self, _):
        lead, stds = np.zeros((1, 3, 6, 4)), np.ones((1, 3, 6, 4))
        lead[0, 0, 0, :3] = self.x, self.y, 8.
        out = dict(pose=np.array([[10., 0, 0, 0, 0, self.yaw]]), road_transform=np.array([[0, 0, 1.3, 0, 0, 0]]),
                   road_transform_stds=np.zeros((1, 6)), lead=lead, lead_stds=stds,
                   lead_prob=np.array([[self.p, 0, 0]]))
        if self.lanes is not None:   # an ego-lane centre per X_IDXS, or the y of all 4 lines (4, 33)
            lanes = np.zeros((1, 4, 33, 2))
            if np.ndim(self.lanes) == 2:
                lanes[0, :, :, 0] = self.lanes
            else:
                lanes[0, 1, :, 0], lanes[0, 2, :, 0] = self.lanes - 1.8, self.lanes + 1.8
            out.update(lane_lines=lanes, lane_lines_prob=np.full((1, 8), .9))
        if self.plan_y is not None:   # the model's trajectory: straight ahead, plan_y m to the right
            plan = np.zeros((1, 33, 15))
            plan[0, :, 0], plan[0, :, 1] = np.linspace(0, 100, 33), self.plan_y
            out['plan'] = plan
        return out


def _step(pipe):
    return pipe.step(np.zeros((874, 1164), np.uint8), *[np.full((437, 582), 128, np.uint8)] * 2)


def test_lead_needs_settled_calibration_and_the_lane_from_the_camera_axis():
    """Like comma_ai realtime_lead: settled angles, p >= 0.5, |y| <= 2 m, x > 0; no lead before calibration.
    Straight ahead with no lane lines, the ego-lane centre is the camera axis."""
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


def _settled(m):
    pipe = Pipeline(1164, 874, 910, 1.5, m)
    for _ in range(AutoCalib.SETTLED_SAMPLES + 60):
        r = _step(pipe)
    return pipe, r


def test_ego_path_curvature_is_the_yaw_rate_over_the_speed():
    """Ego motion from the model (pose): yaw rate / speed, + = turning right like the lane lines, smoothed."""
    m = FakeModel()
    m.yaw = .05                                          # 10 m/s -> a 200 m radius to the right
    _, r = _settled(m)
    assert r.curvature == pytest.approx(.005, rel=1e-3)
    m.yaw = -5.                                          # a spike: bounded by 4 m/s^2 sideways at 10 m/s
    _, r = _settled(m)
    assert r.curvature == pytest.approx(-.04, rel=1e-3)


def test_curvature_bound_allows_tight_turns_only_when_slow():
    from src.roadwatch.pipeline import curvature_max
    assert curvature_max(2.) == pytest.approx(.1) and curvature_max(10.) == pytest.approx(.04)
    assert curvature_max(30.) == pytest.approx(4 / 900)


def _lines(*ys):
    return np.array([np.full(33, y, float) for y in ys])


def test_on_a_lane_line_the_ego_lane_is_both_lanes_beside_it():
    """Driving on line 2 (0.3 m right of the camera): the lane is lines 1 to 3 and its centre is line 2, so a car
    on the line ahead is the lead and one a lane over is not; leaving needs > 0.9 m (no flicker at 0.6 m)."""
    m = FakeModel()
    m.lanes, m.y = _lines(-7., -3.2, .3, 3.8), .5
    _, r = _settled(m)
    assert r.straddle == 2 and r.lane_ref == 'lane_lines' and r.gap_m == pytest.approx(28.5)
    m.y = 2.5
    _, r = _settled(m)
    assert r.straddle == 2 and r.gap_m is None
    pipe, r = _settled(m)
    m.lanes = _lines(-7., -3.2, .8, 4.3)                 # 0.8 m: still on it (hysteresis)
    assert _step(pipe).straddle == 2
    m.lanes = _lines(-7., -2.6, 1., 4.5)
    assert _step(pipe).straddle is None
    m.lanes = _lines(-7., -.4, 3.1, 6.6)                 # on line 1 (left)
    assert _step(pipe).straddle == 1


def test_widen_lane_covers_a_path_that_leaves_the_lane():
    """Both the HUD carpet and the lead window use this: a path whose light band (hw) would touch a lane line makes
    the lane reach over to it (+ BAND_MARGIN), at most two lanes wide; a path inside the lane changes nothing."""
    from src.roadwatch.pipeline import LANE_WIDTH, widen_lane
    yl, yr, hw = widen_lane(-1.8, 1.8, 0., .97)
    assert (yl, yr, hw) == (-1.8, 1.8, .97)
    yl, yr, hw = widen_lane(-1.8, 1.8, 2.6, .97)
    assert yl == -1.8 and yr == pytest.approx(2.6 + .97 + .3) and hw == .97
    yl, yr, _ = widen_lane(-1.8, 1.8, 6., .97)
    assert yr - yl == pytest.approx(2 * LANE_WIDTH)
    yl, yr, _ = widen_lane(np.array([-1.8, -1.8]), np.array([1.8, 1.8]), np.array([0., -2.4]), .97)
    assert np.allclose(yl, [-1.8, -2.4 - 1.27]) and np.allclose(yr, [1.8, 1.8])


def test_lead_window_covers_both_lanes_when_the_car_runs_between_them():
    """Lane lines at +-1.8 m, the model's path 2.6 m right (the car is between two lanes): a car in the lane beside
    ours (y 4.0) is the lead; with the path in our lane it is not; the single-lane window stays +-2 m."""
    from src.roadwatch.pipeline import MAX_LAT_M, lane_center
    lanes = np.zeros((1, 4, 33, 2))
    lanes[0, 1, :, 0], lanes[0, 2, :, 0] = -1.8, 1.8
    out = dict(lane_lines=lanes, lane_lines_prob=np.full((1, 8), .9), plan=np.zeros((1, 33, 15)))
    out['plan'][0, :, 0] = np.linspace(0, 100, 33)
    out['plan'][0, :, 1] = 2.6
    c, half, ref = lane_center(out, 0., 10., 100.)
    assert ref == 'both_lanes' and abs(4.0 - c) <= half and abs(-3.0 - c) > half
    out['plan'][0, :, 1] = 0.
    c, half, ref = lane_center(out, 0., 10., 100.)
    assert ref == 'lane_lines' and c == pytest.approx(0.) and half == MAX_LAT_M


def test_a_car_in_the_next_lane_is_the_lead_only_while_we_run_between_lanes():
    m = FakeModel()
    m.lanes, m.y = _lines(-7., -1.8, 1.8, 5.4), 3.5     # the car ahead is in the lane on the right
    m.plan_y = 0.                                       # we drive in our own lane
    _, r = _settled(m)
    assert r.gap_m is None and r.lane_ref == 'lane_lines'
    m.plan_y = 2.6                                      # the model's path runs over the right line: between two lanes
    _, r = _settled(m)
    assert r.lane_ref == 'both_lanes' and r.gap_m == pytest.approx(28.5)


def test_lead_is_kept_in_the_ego_lane_on_a_curve():
    """On a right-hand curve the car ahead in our lane is to the right of the camera axis (the lane centre is
    2.25 m right at 30 m); a car straight ahead is then in the next lane to the left."""
    from src.roadwatch.hud import X_IDXS
    m = FakeModel()
    m.lanes, m.y = .0025 * X_IDXS ** 2, 2.5
    _, r = _settled(m)
    assert r.lane_ref == 'lane_lines' and r.gap_m == pytest.approx(28.5) and r.lead_lat_m == pytest.approx(2.5)
    m.y = 0.
    _, r = _settled(m)
    assert r.gap_m is None


def test_the_predicted_path_bends_only_within_reach_then_goes_straight():
    """A steering movement is carried PATH_REACH_S ahead (at least PATH_REACH_MIN_M), then the path goes on along
    its tangent instead of bending all the way to 80 m."""
    from src.roadwatch.pipeline import PATH_REACH_MIN_M, PATH_REACH_S, path_offset, path_reach
    assert path_reach(2.) == PATH_REACH_MIN_M and path_reach(30.) == pytest.approx(30. * PATH_REACH_S)
    x = np.array([0., 10., 20., 40., 80.])
    np.testing.assert_allclose(path_offset(.01, x, 20.), [0., .5, 2., 6., 14.])   # arc to 20 m, then slope 0.2
    np.testing.assert_allclose(path_offset(.005, x, 1e9), .005 * x ** 2 / 2)   # turns < HEADING_MAX by 80 m


def test_the_yaw_path_turns_at_most_heading_max_then_goes_straight():
    """A tight turn is drawn as an arc until the path has turned HEADING_MAX (35 deg), then straight on."""
    from src.roadwatch.pipeline import HEADING_MAX, path_offset
    xa = HEADING_MAX / .1                                # 6 m at 0.1 1/m
    assert path_offset(.1, 30., 1e9) == pytest.approx(.1 * xa * (30. - xa / 2))
    assert path_offset(.005, 30., 1e9) == pytest.approx(.005 * 900 / 2)   # gentle curves unchanged


def _policy(plan_y=None, plan_x=None, edges=None, edge_std=.5):
    """Outputs with no confident lane lines, an optional plan (y per x) and road edges (y left, y right)."""
    out = dict(lane_lines=np.zeros((1, 4, 33, 2)), lane_lines_prob=np.zeros((1, 8)))
    if plan_y is not None:
        plan = np.zeros((1, 33, 15))
        plan[0, :, 0] = np.linspace(0, 40, 33) if plan_x is None else plan_x
        plan[0, :, 1] = plan_y(plan[0, :, 0])
        out['plan'] = plan
    if edges is not None:
        e = np.zeros((1, 2, 33, 2))
        e[0, 0, :, 0], e[0, 1, :, 0] = edges
        out.update(road_edges=e, road_edges_stds=np.full((1, 2, 33, 2), edge_std))
    return out


def test_the_model_plan_goes_straight_past_its_end():
    """The model's own trajectory (policy plan head) is continued along its last heading past its last point."""
    from src.roadwatch.pipeline import plan_offset
    out = _policy(lambda x: .005 * x ** 2)
    np.testing.assert_allclose(plan_offset(out, np.array([10., 20.])), [.5, 2.], atol=.05)
    slope = (.005 * 40 ** 2 - .005 * 38.75 ** 2) / 1.25
    assert plan_offset(out, 60.) == pytest.approx(8. + slope * 20., abs=.1)
    assert plan_offset(_policy(), 20.) is None


def test_a_u_turn_plan_is_drawn_at_most_heading_max():
    """In a U-turn the plan runs almost sideways: it is followed at no more than 35 deg from straight ahead."""
    from src.roadwatch.pipeline import HEADING_MAX, plan_offset
    t = np.linspace(0, np.pi * .9, 33)                     # a 10 m radius turn to the right
    out = _policy(lambda x: 10 * (1 - np.cos(np.arcsin(np.clip(x / 10, 0, 1)))), plan_x=10 * np.sin(t))
    y = plan_offset(out, np.array([5., 15., 30.]))
    assert np.all(np.diff(y) <= np.tan(HEADING_MAX) * np.diff([5., 15., 30.]) + 1e-6) and y[-1] < 30.


def test_the_near_path_follows_the_yaw_and_the_far_path_the_models_bend():
    """Without lane lines: near the car the path is the arc of the ego yaw (the measured turn); from `reach` on it goes
    on along that heading and adds only how the model's plan bends away from its own tangent there (the road ahead)."""
    from src.roadwatch.pipeline import ego_offset, path_offset
    out = _policy(lambda x: .004 * x ** 2)               # the plan turns right on its own: 0.008 1/m
    k, reach = .01, 15.
    x = np.array([5., 10., 15., 25., 40.])
    y = ego_offset(out, k, x, reach)
    np.testing.assert_allclose(y[:3], path_offset(k, x[:3], reach), atol=1e-6)    # near: the yaw arc, not the plan
    slope = k * reach
    want = path_offset(k, reach, reach) + slope * (x[3:] - reach) + .004 * (x[3:] - reach) ** 2
    np.testing.assert_allclose(y[3:], want, atol=.05)
    np.testing.assert_allclose(ego_offset(_policy(), k, x, reach), path_offset(k, x, reach))   # no plan: yaw only
    lines = dict(out)                                    # confident lane lines: the road shows the way, the plan is kept
    lines['lane_lines'] = np.zeros((1, 4, 33, 2))
    lines['lane_lines'][0, 1, :, 0], lines['lane_lines'][0, 2, :, 0] = -1.8, 1.8
    lines['lane_lines_prob'] = np.full((1, 8), .9)
    from src.roadwatch.pipeline import plan_offset
    np.testing.assert_allclose(ego_offset(lines, k, x, reach), plan_offset(lines, x))


def test_path_curvature_is_the_parabola_of_the_drawn_path():
    """What the Lab compares with the real curvature: the 2nd-order fit of the drawn path over 5-40 m (a shift or a
    heading error of the camera is not curvature); + = right; None without the ego motion."""
    from src.roadwatch.pipeline import CURV_FIT_X, fit_curvature, path_curvature
    assert fit_curvature(.004 * CURV_FIT_X ** 2 + .3 * CURV_FIT_X + 1.) == pytest.approx(.008)
    out = _policy()
    assert path_curvature(out, .005, 40., None) == pytest.approx(.005, rel=.02)   # 40 m/s: the arc reaches 60 m
    assert 0 < path_curvature(out, .005, 5., None) < .002                          # 5 m/s: arc to 15 m, then straight
    assert path_curvature(out, None, 5., None) is None


def test_the_path_stays_on_the_road_between_its_edges():
    """Where the road edges are known (std <= 3 m) the path keeps 0.9 m inside them: a turn that would leave
    the road is pulled back along the edge."""
    from src.roadwatch.pipeline import predicted_path
    out = _policy(lambda x: .02 * x ** 2, edges=(-2., 3.), edge_std=2.5)
    y = predicted_path(out, .04, np.array([5., 20., 40.]), 15.)       # a yaw of 0.04 1/m: the arc leaves the road
    assert y[0] == pytest.approx(.5) and np.allclose(y[1:], 3. - .9)
    loose = _policy(lambda x: .02 * x ** 2, edges=(-2., 3.), edge_std=4.)   # unsure edges: not used
    assert predicted_path(loose, .04, 20., 15.) > 5.


def test_without_lane_lines_the_ego_lane_follows_the_predicted_path():
    """No confident lane lines: the lane centre is where the ego motion leads (path_offset)."""
    m = FakeModel()
    m.yaw, m.y = .05, 2.4                                # 10 m/s: arc to 15 m, path 1.69 m right at 30 m
    _, r = _settled(m)
    assert r.lane_ref == 'ego_path' and r.gap_m == pytest.approx(28.5)
    m.yaw = 0.
    _, r = _settled(m)
    assert r.lane_ref == 'ego_path' and r.gap_m is None


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


def _borders(lane_y, prob, edges=None, edge_std=.5, pair=(1, 2)):
    lanes = np.zeros((4, 33, 2))
    lanes[:, :, 0] = np.asarray(lane_y, float)[:, None]
    lanes[:, :, 1] = 1.3
    e = s = None
    if edges is not None:
        e, s = np.zeros((2, 33, 2)), np.full((2, 33, 2), edge_std)
        e[:, :, 0], e[:, :, 1] = np.asarray(edges, float)[:, None], 1.3
    return ego_lane_borders(lanes, prob, None, 30.0, 1.3, e, s, pair)


def test_ego_lane_follows_each_line_on_its_own():
    """One confident line: the other side is a lane width (3.5 m) from it, not a band around the path."""
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.1, .9])
    assert np.allclose(yr, 1.9) and np.allclose(yl, 1.9 - 3.5)


def test_ego_lane_hugs_the_road_edge_where_a_line_is_missing():
    """No right line: the right border is the road edge when it is next to the car's lane (within a lane width
    of the path) and the model is sure of it (std <= 1.5 m); a less sure edge (std <= 3 m) only bounds the lane."""
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.9, .1], edges=[-9., 2.6])
    assert np.allclose(yl, -1.6) and np.allclose(yr, 2.6)
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.9, .1], edges=[-9., 7.])
    assert np.allclose(yr, -1.6 + 3.5)                   # a kerb 7 m away is not next to the car's lane
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.9, .1], edges=[-9., 2.6], edge_std=2.)
    assert np.allclose(yr, -1.6 + 3.5)                   # unsure edge: not the border...
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.9, .1], edges=[-9., 1.5], edge_std=2.)
    assert np.allclose(yr, 1.5)                          # ...but the lane stops at it
    xs, (yl, _), (yr, _) = _borders([-5., -1.6, 1.9, 5.4], [.1, .1], edges=[-2.2, 2.6])   # no lines: edges
    assert np.allclose(yl, -2.2) and np.allclose(yr, 2.6)


def test_a_far_road_edge_is_not_the_lane_border():
    """Two-way street, no lines: the far kerb across the road (5.5 m left of the path) bounds the lane but is not
    its border; the lane stays around the path. The near kerb (1.8 m right) is the border."""
    lanes = np.zeros((4, 33, 2))
    plan = np.zeros((33, 3))
    plan[:, 0] = np.linspace(0, 100, 33)
    e, s = np.zeros((2, 33, 2)), np.full((2, 33, 2), 1.)
    e[0, :, 0], e[1, :, 0] = -5.5, 1.8
    xs, (yl, _), (yr, _) = ego_lane_borders(lanes, [.1, .1], plan, 30., 1.3, e, s)
    assert np.allclose(yr, 1.8) and np.allclose(yl, 1.8 - 3.5)
    e[1, :, 0] = 6.                                      # both kerbs far: the lane around the path
    xs, (yl, _), (yr, _) = ego_lane_borders(lanes, [.1, .1], plan, 30., 1.3, e, s)
    assert np.allclose(yl, -1.75) and np.allclose(yr, 1.75)


def test_ego_lane_does_not_cross_a_known_road_edge():
    """A lane around a path that runs off the road is clipped at the road edges (std <= 3 m), keeping 1.5 m."""
    lanes = np.zeros((4, 33, 2))
    plan = np.zeros((33, 3))
    plan[:, 0], plan[:, 1] = np.linspace(0, 100, 33), 2.5
    e, s = np.zeros((2, 33, 2)), np.full((2, 33, 2), 2.5)
    e[0, :, 0], e[1, :, 0] = -3., 3.
    xs, (yl, _), (yr, _) = ego_lane_borders(lanes, [.1, .1], plan, 30., 1.3, e, s)
    assert np.allclose(yr, 3.) and np.allclose(yl, 2.5 - 1.75)
    e[1, :, 0] = 1.                                      # edge inside the nominal lane: still 1.5 m wide
    xs, (yl, _), (yr, _) = ego_lane_borders(lanes, [.1, .1], plan, 30., 1.3, e, s)
    assert np.allclose(yr, 1.) and np.allclose(yr - yl, 1.5)


def test_ego_lane_on_a_line_spans_both_lanes():
    xs, (yl, _), (yr, _) = _borders([-7., -3.2, .3, 3.8], [.9, .9], pair=(1, 3))
    assert np.allclose(yl, -3.2) and np.allclose(yr, 3.8)


def test_ego_lane_falls_back_to_the_planned_path_on_the_road():
    """Like comma_ai overlay: a nominal lane around the planned path; the plan starts at the camera (z = 0),
    so the camera height puts it on the road."""
    lanes, plan = np.zeros((4, 33, 2)), np.zeros((33, 15))
    plan[:, 0], plan[:, 1], plan[:, 2] = np.linspace(0, 100, 33), np.linspace(0, 1, 33), np.linspace(0, -0.5, 33)
    xs, (yl, zl), (yr, zr) = ego_lane_borders(lanes, [.1, .1], plan, 30.0, 1.3)
    assert xs[-1] == 30.0
    np.testing.assert_allclose(yl, xs / 100 - 1.75)
    np.testing.assert_allclose(yr, xs / 100 + 1.75)
    np.testing.assert_allclose(zl, 1.3 - xs / 200)


def test_ego_lane_without_a_plan_head_is_on_the_camera_axis():
    xs, (yl, zl), (yr, zr) = ego_lane_borders(np.zeros((4, 33, 2)), [.1, .1], None, 30.0, 1.3)
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


def test_distance_comes_from_the_history_and_is_predicted_ahead():
    """The model's distance jitters +-1 m around a lead closing at 3 m/s: the fit smooths it and predicts 1 s ahead."""
    m, rng = FakeModel(), np.random.default_rng(1)
    pipe = Pipeline(1164, 874, 910, 1.5, m)
    for _ in range(AutoCalib.SETTLED_SAMPLES):
        r = _step(pipe)
    for k in range(60):
        true = 40. - 3. * k * .05
        m.x = true + rng.normal(0, 1.)
        r = _step(pipe)
    assert r.gap_m == pytest.approx(true - 1.5, abs=.6)
    assert r.gap_pred_m == pytest.approx(true - 1.5 - 3., abs=1.)


def test_temporal_off_keeps_the_kalman_distance():
    m = FakeModel()
    pipe = Pipeline(1164, 874, 910, 1.5, m, temporal=False)
    for _ in range(AutoCalib.SETTLED_SAMPLES + 20):
        r = _step(pipe)
    assert r.gap_m == pytest.approx(28.5) and r.gap_pred_m is None


def test_model_speed_stays_the_image_estimate_when_gps_drives_ego():
    class Gps:
        def observe(self, pts, v):
            pass

        def __call__(self, pts):
            return 20.
    pipe = Pipeline(1164, 874, 910, 1.5, FakeModel(), v_ref=Gps())
    for _ in range(100):
        r = _step(pipe)
    assert r.ego_speed_mps == pytest.approx(20.) and r.model_speed_mps == pytest.approx(10.)


def test_overlay_gives_the_hud_geometry_as_picture_fractions():
    """For the phone page, which draws the lane and the lead on its live camera: same points as the HUD."""
    from src.roadwatch.hud import overlay
    r, cam_k = _hud_result(.6), intrinsics(910, 1164, 874)
    o = overlay(cam_k, r, 1164, 874)
    ((u, v),), _ = project(cam_k, r.rpy, [[21.5, .2, .6]])
    assert o['lead'] == dict(u=round(u / 1164, 4), v=round(v / 874, 4), dist_m=21.5, close=False)
    left, right = o['lane']['left'], o['lane']['right']
    assert len(left) == len(right) >= 10 and left[0][0] < .5 < right[0][0] and left[0][1] > left[-1][1]
    none = overlay(cam_k, _hud_result(.6, gap=None), 1164, 874)
    assert none['lead'] is None and none['lane'] is not None
    assert o['path'] is None                             # no ego motion in this Result


def test_overlay_path_follows_the_ego_motion():
    """The predicted path (centre band) bends with the ego curvature; without lane lines the lane bends too."""
    from dataclasses import replace

    from src.roadwatch.hud import overlay
    cam_k = intrinsics(910, 1164, 874)
    straight = overlay(cam_k, replace(_hud_result(1.2, lane_prob=.1), curvature=0.), 1164, 874)
    right = overlay(cam_k, replace(_hud_result(1.2, lane_prob=.1), curvature=.005), 1164, 874)
    for o in (straight, right):
        assert len(o['path']['left']) == len(o['path']['right']) >= 10
    mid = lambda o, k: (o[k]['left'][-1][0] + o[k]['right'][-1][0]) / 2  # noqa: E731  far end, picture x
    assert mid(right, 'path') > mid(straight, 'path') + .02
    assert mid(right, 'lane') > mid(straight, 'lane') + .02
    lanes = overlay(cam_k, replace(_hud_result(1.2), curvature=.005), 1164, 874)   # confident lines: the road wins
    assert mid(lanes, 'lane') == pytest.approx(mid(straight, 'lane'), abs=.01)
    assert mid(lanes, 'path') == pytest.approx(mid(lanes, 'lane'), abs=.005)


def test_with_lane_lines_the_path_joins_the_lane_centre_within_reach():
    """The car drives where the road goes: from the car the path eases into the ego-lane centre by `reach`
    metres (smoothstep), then follows it; without confident lane lines it is the ego path alone."""
    from src.roadwatch.pipeline import X_IDXS, path_offset, predicted_path
    lanes = np.zeros((1, 4, 33, 2))
    lanes[0, 1, :, 0], lanes[0, 2, :, 0] = 1. - 1.8 + .001 * X_IDXS ** 2, 1. + 1.8 + .001 * X_IDXS ** 2
    sure = dict(lane_lines=lanes, lane_lines_prob=np.full((1, 8), .9))
    x = np.array([0., 5., 10., 20., 40., 80.])
    y = predicted_path(sure, -.01, x, 20.)
    centre = np.interp(x, X_IDXS, 1. + .001 * X_IDXS ** 2)   # the lane lines are sampled at X_IDXS
    assert y[0] == pytest.approx(0.) and np.all(np.diff(y) > 0)   # from the car, steering left is outweighed
    np.testing.assert_allclose(y[3:], centre[3:], atol=1e-6)
    unsure = dict(sure, lane_lines_prob=np.full((1, 8), .1))
    np.testing.assert_allclose(predicted_path(unsure, -.01, x, 20.), path_offset(-.01, x, 20.))


def test_lane_geometry_is_a_smooth_curve():
    """The drawn borders are fitted with a smooth curve: a line the model gives with a zigzag comes out flat."""
    from dataclasses import replace

    from src.roadwatch.hud import GRID, lane_geometry
    from src.roadwatch.pipeline import X_IDXS
    r = _hud_result(1.2)
    zig = .1 * (-1.) ** np.arange(33)
    r.outputs['lane_lines'][0, 2, :, 0] = 1.8 + .01 * X_IDXS + zig
    g = lane_geometry(replace(r, curvature=0.))
    assert len(g['yr']) == len(GRID) and np.abs(g['yr'] - (1.8 + .01 * GRID)).max() < .04


def test_lane_stops_where_the_road_turns_away_and_far_points_do_not_bend_the_near_lane():
    """Past a bend the model's border turns sideways or jumps (the kerb runs behind a wall): the carpet stops
    there, and that far part does not bend the near lane (the fit only uses the drawable part)."""
    from dataclasses import replace

    from src.roadwatch.hud import GRID, lane_geometry
    from src.roadwatch.pipeline import X_IDXS
    r = replace(_hud_result(1.2, gap=None), curvature=0.)
    r.outputs['lane_lines'][0, 2, :, 0] = np.where(X_IDXS < 30, 1.8, 1.8 + 3 * (X_IDXS - 30))   # sideways from 30 m
    g = lane_geometry(r)
    assert 25. <= g['end'] <= 32.
    near = GRID < 25
    assert np.abs(g['yr'][near] - 1.8).max() < .05
    assert np.all(np.diff(g['yr'][GRID > g['end']]) < 3 * np.diff(GRID[GRID > g['end']]))   # straight on, no hook


def test_the_carpet_widens_to_both_lanes_when_the_path_runs_outside_one():
    """The path (from the car, y 0 at x 0) and the borders come from different heads. When the car is near a lane
    line the path's light band touches it: the carpet reaches over (at most two lanes wide) instead of squeezing
    the path into the lane; the light band keeps its width."""
    from dataclasses import replace

    from src.roadwatch.hud import LANE_WIDTH, LaneSmoother, lane_geometry
    r = replace(_hud_result(1.2, gap=None), curvature=0.)         # lane lines at -1.8 / +1.8
    g = lane_geometry(r)
    assert np.allclose(g['yl'], -1.8, atol=.02) and np.allclose(g['yr'], 1.8, atol=.02)   # in the lane: unchanged
    r.outputs['lane_lines'][0, 1, :, 0], r.outputs['lane_lines'][0, 2, :, 0] = -.5, 3.1   # the car is next to the left line
    g = lane_geometry(r)
    assert g['yl'][0] < -.8 and np.allclose(g['yr'], 3.1, atol=.02)    # reaches over to the left, right unchanged
    assert g['yr'][0] - g['yl'][0] <= 2 * LANE_WIDTH + .01 and g['yl'][-1] > g['yl'][0]   # far: back towards the lane
    assert np.allclose(g['hw'], .27 * 3.6, atol=.02)              # the band keeps the single-lane width
    assert np.all(g['yc'] - g['hw'] >= g['yl'] - .02) and np.all(g['yc'] + g['hw'] <= g['yr'] + .02)
    sm = LaneSmoother()
    assert sm.update(r)['yl'][0] == pytest.approx(g['yl'][0])


def test_borders_are_drawn_with_sub_pixel_precision():
    """A border that moves by 0.3 px changes the anti-aliasing instead of snapping to the pixel grid (it would shimmer);
    both the carpet and the border line."""
    from src.roadwatch import hud
    left = np.c_[np.linspace(150, 190, 12), np.linspace(290, 120, 12)]
    right = left + [110, 0]
    carpet, line = [], []
    for dx in (0., .3, .6):
        img = np.zeros((300, 400, 3), np.uint8)
        hud._blend_strips(img, left + [dx, 0], right + [dx, 0], hud.LANE_BGR, .4, .2)
        carpet.append(img)
        img = np.zeros((300, 400, 3), np.uint8)
        hud._stroke(img, left + [dx, 0], hud.EDGE_BGR, 3)
        line.append(img)
    for imgs in (carpet, line):
        assert (imgs[0] != imgs[1]).any() and (imgs[1] != imgs[2]).any()


def test_lane_smoother_ignores_a_one_frame_spike_but_follows_a_real_move():
    """A median over the last 3 ticks removes a single-frame glitch of a border (no twitch) with no extra lag on a
    border that really moves (it follows within 2 ticks, then eases as before)."""
    from dataclasses import replace

    from src.roadwatch.hud import LaneSmoother
    sm, base = LaneSmoother(), replace(_hud_result(1.2, gap=None), curvature=0.)
    for _ in range(5):
        sm.update(base)
    spike = replace(base)
    spike.outputs = dict(base.outputs, lane_lines=base.outputs['lane_lines'].copy())
    spike.outputs['lane_lines'][0, 2, :, 0] = 4.0
    assert sm.update(spike)['yr'][0] == pytest.approx(1.8, abs=.05)         # one spike: ignored
    sm.update(base)
    for _ in range(3):
        g = sm.update(spike)
    assert g['yr'][0] > 2.0                                                  # it stays: the lane follows


def test_lines_flickering_around_the_threshold_do_not_switch_the_borders():
    """Line probabilities hovering around 0.4 (0.45, 0.35, ...) keep the right border on the line (hysteresis), not
    jumping between the line and a lane width from the other border."""
    from dataclasses import replace

    from src.roadwatch.hud import LANE_PROB, LaneSmoother
    sm = LaneSmoother()
    ys = []
    for i in range(12):
        r = replace(_hud_result(1.2, gap=None), curvature=0.)
        r.outputs = dict(r.outputs, lane_lines_prob=np.full((1, 8), .9 if i < 4 else (.45 if i % 2 else .35)),
                         lane_lines=r.outputs['lane_lines'].copy())
        r.outputs['lane_lines'][0, 2, :, 0] = 2.4                       # the right line is 2.4 m away, not the 3.5 m lane width
        ys.append(sm.update(r)['yr'][0])
    assert LANE_PROB == .4 and np.ptp(ys[4:]) < .05 and ys[-1] == pytest.approx(2.4, abs=.1)


def test_lane_smoother_eases_width_and_length_instead_of_jumping():
    """Per model tick the drawn lane moves part of the way to the new one: it widens (e.g. onto both lanes when
    the car drives on a line) and collapses to a new lead over a few ticks, then settles."""
    from dataclasses import replace

    from src.roadwatch.hud import LANE_X_MAX, LaneSmoother
    sm = LaneSmoother()
    far = replace(_hud_result(1.2, gap=None), curvature=0.)
    g0 = sm.update(far)
    assert g0['end'] == LANE_X_MAX and np.allclose(g0['yr'], 1.8, atol=.01)
    wide, near = replace(far), replace(_hud_result(1.2), curvature=0.)   # lead at 21.5 m
    wide.outputs['lane_lines'][0, 2, :, 0] = 5.3
    g1 = sm.update(wide)
    assert 1.9 < g1['yr'][0] < 5.2                       # part of the way, not a jump
    for _ in range(40):
        g = sm.update(wide)
    assert np.allclose(g['yr'], 5.3, atol=.01)
    sm.update(near)                                      # the median of 3 ticks waits for the second one
    g2 = sm.update(near)
    assert 21.5 < g2['end'] < LANE_X_MAX
    for _ in range(40):
        g = sm.update(near)
    assert g['end'] == pytest.approx(21.5, abs=.05)


def test_draw_and_overlay_use_the_smoothed_lane():
    from dataclasses import replace

    from src.roadwatch.hud import LaneSmoother, overlay
    cam_k, sm = intrinsics(910, 1164, 874), LaneSmoother()
    r = replace(_hud_result(1.2), curvature=0.)
    sm.update(r)
    wide = replace(r)
    wide.outputs['lane_lines'][0, 2, :, 0] = 5.3
    eased, raw = overlay(cam_k, wide, 1164, 874, sm), overlay(cam_k, wide, 1164, 874)
    assert eased['lane']['right'][0][0] < raw['lane']['right'][0][0]   # the smoother has not moved yet
    out = draw(np.full((874, 1164, 3), 90, np.uint8), cam_k, wide, 910., lane=sm)
    assert (out != 90).any()


def test_lane_is_drawn_when_its_near_end_is_far_off_the_picture():
    """A narrow lens (fy 5400 px on 1164 px): the lane's first metres project far below and beside the picture;
    only those points are left out, the rest of the lane is still drawn and sent to the phone."""
    from dataclasses import replace

    from src.roadwatch.hud import overlay
    cam_k, r = intrinsics(5400, 1164, 874), replace(_hud_result(1.2), curvature=0.)
    out = draw(np.full((874, 1164, 3), 90, np.uint8), cam_k, r, 5400.)
    assert (out[500:, :] != 90).any()
    o = overlay(cam_k, r, 1164, 874)
    assert o['lane'] is not None and len(o['lane']['left']) >= 2 and o['path'] is not None


AMBER_BGR = (80, 200, 255)   # the radar line of the panel (255, 200, 80 in RGB)


def _panel(**kw):
    from src.roadwatch.hud import draw_panel
    img = np.full((874, 1164, 3), 90, np.uint8)
    draw_panel(img, kw.pop('gap', 20.8), 2., 9.2, None, False, **kw)
    return img


def _amber_rows(img):
    """Rows (picture y) where amber text is drawn inside the panel (x < 360)."""
    m = (np.abs(img[:, :360].astype(int) - AMBER_BGR).sum(axis=2) < 60).any(axis=1)
    return np.flatnonzero(m)


def test_panel_shows_the_radar_distance_and_the_delta_inside_it():
    """Lab video: 'Radar 23.0 m · Δ -2.2 m' in amber inside the panel (model gap - radar), the speed below it;
    no radar track: 'Radar _'; not a Lab (no radar_ref): no amber line and the panel keeps its height."""
    plain, lab_nan, lab_radar = _panel(), _panel(radar_ref=float('nan')), _panel(radar_ref=23.0)
    assert len(_amber_rows(plain)) == 0
    assert len(_amber_rows(lab_nan)) > 5 and len(_amber_rows(lab_radar)) > 5      # 'Radar _' / 'Radar 23.0 m · Δ -2.2 m'
    rows = _amber_rows(lab_radar)
    assert rows.min() > 18 + 78 and rows.max() < 18 + 170                         # under the big number, inside the panel
    assert (lab_radar[:, :360] != lab_nan[:, :360]).any()                       # the numbers differ
    assert (lab_radar[195:, :] == 90).all() and (plain[175:, :360] == 90).all()      # nothing is drawn below the panel


def _chevron_full_frame(img, u, v, dist, color):
    """hud.draw_chevron before it blended only around the chevron (copy + blend of the whole frame)."""
    import cv2
    sz = float(np.clip(25 * 30 / (dist / 3 + 30), 15, 30)) * 1.4 * img.shape[1] / 1164
    tri = np.array([[u, v - sz * 0.35], [u + sz * 1.1, v + sz * 0.65], [u - sz * 1.1, v + sz * 0.65]], np.int32)
    glow = np.array([[u, v - sz * 0.6], [u + sz * 1.45, v + sz * 0.85], [u - sz * 1.45, v + sz * 0.85]], np.int32)
    layer = img.copy()
    cv2.fillPoly(layer, [glow], (40, 40, 40), cv2.LINE_AA)
    cv2.addWeighted(layer, 0.45, img, 0.55, 0, dst=img)
    cv2.fillPoly(img, [tri], color, cv2.LINE_AA)
    return img


@pytest.mark.parametrize('u, v', [(580., 400.), (3., 870.), (1160., 2.)])   # also at the picture edges
def test_chevron_blends_only_around_itself_with_the_same_result(u, v):
    from src.roadwatch.hud import draw_chevron
    img = np.random.default_rng(0).integers(0, 255, (874, 1164, 3), dtype=np.uint8)
    want = _chevron_full_frame(img.copy(), u, v, 25., LEAD_BGR)
    got = img.copy()
    draw_chevron(got, u, v, 25., LEAD_BGR)
    assert np.abs(got.astype(int) - want).max() <= 1


def test_lane_carpet_matches_a_float_blend():
    """The carpet is blended only where the lane is, in integers; within 1 grey level of the float blend."""
    import cv2

    from src.roadwatch import hud
    img = np.random.default_rng(1).integers(0, 255, (300, 400, 3), dtype=np.uint8)
    left = np.c_[np.linspace(150, 190, 6), np.linspace(290, 120, 6)]
    right = np.c_[np.linspace(260, 210, 6), np.linspace(290, 120, 6)]
    want = img.astype(np.float32)
    mask = np.zeros(img.shape[:2], np.uint8)
    for j in range(5):
        quad = np.round(np.array([left[j], left[j + 1], right[j + 1], right[j]]) * 16).astype(np.int32)   # 1/16 px
        cv2.fillPoly(mask, [quad], int(round((.38 + (.08 - .38) * j / 4) * 255)), lineType=cv2.LINE_AA, shift=4)
    m = mask[..., None] / 255
    want = (want * (1 - m) + hud.LANE_BGR * m).astype(np.uint8)
    got = img.copy()
    hud._blend_strips(got, left, right, hud.LANE_BGR, .38, .08)
    assert np.abs(got.astype(int) - want).max() <= 1 and (got != img).any()
