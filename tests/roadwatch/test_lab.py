"""Lab page backend: comma2k19 segments, radar reference, the car's speed log, cached results."""
import json
import subprocess

import numpy as np
import pytest

from src.roadwatch import lab


@pytest.fixture
def segment(tmp_path):
    """A 2 s comma2k19-like segment: 40 frames at 20 Hz, a radar track 30 m ahead, CAN speed 20 -> 24 m/s."""
    seg = tmp_path / 'seg1'
    (seg / 'global_pose').mkdir(parents=True)
    (seg / 'processed_log/CAN/radar').mkdir(parents=True)
    (seg / 'processed_log/CAN/speed').mkdir(parents=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=2',
                    str(seg / 'video.mp4')], check=True)
    ft = 100. + np.arange(40) / 20
    np.save(seg / 'global_pose/frame_times', ft)
    t = np.repeat(ft, 2)
    value = np.zeros((80, 7))
    value[0::2, :2] = 30., 0.5      # same lane
    value[1::2, :2] = 12., 3.0      # neighbour lane: ignored
    value[10, 0] = np.nan
    np.save(seg / 'processed_log/CAN/radar/t', t)
    np.save(seg / 'processed_log/CAN/radar/value', value)
    np.save(seg / 'processed_log/CAN/speed/t', np.array([99., 103.]))
    np.save(seg / 'processed_log/CAN/speed/value', np.array([[20.], [24.]]))
    return seg


def test_segments_lists_folders_with_a_video(segment, tmp_path):
    (segment.parent / 'empty').mkdir()
    assert [s['id'] for s in lab.segments(segment.parent, tmp_path / 'cache')] == ['seg1']
    s = lab.segments(segment.parent, tmp_path / 'cache')[0]
    assert s['has_radar'] and s['has_speed'] and s['frames'] == 40 and not s['cached']


def test_radar_reference_is_the_nearest_track_in_the_lane(segment):
    ref = lab.radar_reference(segment)
    assert len(ref) == 40 and ref[0] == 30. and ref[6] == 30.
    assert np.isnan(ref[5])   # its in-lane track is invalid; the 12 m track is in the next lane


def test_speed_log_follows_the_video_time(segment):
    log = lab.SpeedLog(segment)
    assert log(0.) == pytest.approx(21.) and log(1.) == pytest.approx(22.)   # video t = 0 is frame_times[0] = 100 s
    log.observe(0., 5.)   # already synced: nothing to learn


def test_segment_id_cannot_escape_the_root(segment):
    with pytest.raises(KeyError):
        lab.segment_dir(segment.parent, '../seg1')
    assert lab.segment_dir(segment.parent, 'seg1') == segment


def test_lead_mask_matches_comma(segment):
    x, y, p = np.full(60, 30.), np.zeros(60), np.r_[np.full(30, .9), np.full(5, .3), np.full(25, .1)]
    m = lab.lead_mask(x, y, p)
    assert not m[:20].any() and m[20:35].all()             # warm-up, then kept while p >= 0.25
    assert m[35:43].all() and not m[43:].any()             # 8 dropped frames bridged


def test_run_writes_a_cached_result(segment, tmp_path, monkeypatch):
    """As comma app.py: angles from a pre-pass, only the yaw applied and fixed; duplicated wide input; the video shows
    the raw lead gated by lead_mask, the radar distance and no calibration box."""
    made, drawn, calls = {}, [], []

    class FakePipe:
        def __init__(self, w, h, fy, d, model, **kw):
            self.n, self.K = 0, np.eye(3)
            made.update(kw)

        def step(self, y, u, v, pts=None):
            from src.roadwatch.pipeline import Result
            self.n += 1
            lead = np.zeros((1, 3, 6, 4))
            lead[0, 0, 0, :2] = 31.5, .2
            out = dict(lead=lead, lead_stds=np.ones((1, 3, 6, 4)), lead_prob=np.array([[.9, 0, 0]]))
            return Result('calibrated', np.zeros(3), 1.2, 21., .9, 30., 20., None, out, 1., .2, np.zeros(3), 31.5,
                          31.5, 21., 910.)
    def calibrate(video, w, h, fy, model, wide, n, progress, stop, live=None):
        calls.append((n, wide))
        progress(n)
        return np.array([0, 0, .02]), np.array([.01, -.03, .02])
    monkeypatch.setattr(lab, 'Pipeline', FakePipe)
    monkeypatch.setattr(lab, 'estimate_calibration', calibrate)
    monkeypatch.setattr(lab, 'draw', lambda frame, k, r, fy, **kw: drawn.append((r, kw)) or frame)

    class FakeLane:   # the drawn lane eases between ticks: one smoother per run, fed with what is drawn
        fed = []

        def update(self, r):
            self.fed.append(r)
    monkeypatch.setattr(lab, 'LaneSmoother', FakeLane)
    out = tmp_path / 'cache'
    seen, prog = [], []
    lab.run(segment, out, model=object(), bumper=1.5, fy=910., live=lambda jpeg, cols: seen.append((jpeg, cols)),
            progress=lambda *a: prog.append(a))
    assert seen[0][0] is None and seen[-1][0][:2] == b'\xff\xd8' and len(seen) == 41   # JPEG per frame, columns shared
    assert len(seen[-1][1]['t_s']) == 40
    assert calls == [(40, 'dup')] and prog[0] == (40, 80, 40) and prog[-1] == (80, 80, 40)   # pre-pass, then the run
    assert made['wide'] == 'dup' and list(made['rpy']) == [0, 0, .02] and list(made['rpy_est']) == [.01, -.03, .02]
    r, kw = drawn[0]
    assert r.gap_m is None and kw['radar_ref'] == 30. and kw['debug'] is False   # lead_mask warm-up: no lead yet
    assert isinstance(kw['lane'], FakeLane) and FakeLane.fed[0] is r and len(FakeLane.fed) == 40
    r, _ = drawn[20]
    assert r.gap_m == pytest.approx(30.) and r.lead_x_m == 31.5 and r.ttc_s is None   # raw lead minus bumper
    res = json.loads((out / 'seg1' / 'result.json').read_text())
    assert res['frames'] == 40 and res['radar_m'][0] == 30. and res['lead_x_m'][0] == 31.5
    assert res['curv_gt'] == [None] * 40 and res['curv_yaw'] == [None] * 40   # no ground truth; the fake has no ego motion
    assert res['gap_kalman_m'][0] == 30. and res['ego_log_mps'][0] == pytest.approx(21.) and res['bumper_m'] == 1.5
    assert res['wide'] == 'dup' and res['rpy_applied_deg'][:2] == [0, 0] and res['rpy_deg'][1] == pytest.approx(-1.72)
    assert (out / 'seg1' / 'annotated.mp4').stat().st_size > 0
    assert lab.segments(segment.parent, out)[0]['cached']


class FakeModel:
    """Ego driving straight at 10 m/s with the camera yawed: the pose points 0.01 rad to the right; the road tilted."""
    def reset(self):
        self.steps = 0

    def step(self, _):
        self.steps += 1
        return dict(pose=np.array([[10., .1, 0, 0, 0, 0]]), road_transform=np.array([[0, 0, 1.3, 0, .05, 0]]),
                    road_transform_stds=np.zeros((1, 6)))


def test_calibration_pre_pass_applies_only_the_yaw(tmp_path):
    video = tmp_path / 'v.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=4', str(video)], check=True)
    m = FakeModel()
    applied, est = lab.estimate_calibration(video, 320, 240, 300., m, n_frames=80)
    assert m.steps == 80 and applied[:2].tolist() == [0, 0] and applied[2] == est[2] > 0 and est[1] > 0
    applied, est = lab.estimate_calibration(video, 320, 240, 300., m, n_frames=50)   # 30 samples < 40: not settled
    assert not applied.any() and not est.any()


def test_calibration_pre_pass_streams_frames_and_the_angles_so_far(tmp_path):
    video = tmp_path / 'v.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=4', str(video)], check=True)
    seen = []
    lab.estimate_calibration(video, 320, 240, 300., FakeModel(), n_frames=80, live=lambda *a: seen.append(a))
    assert len(seen) == 80 and seen[0][0][:2] == b'\xff\xd8' and seen[0][2] is False   # JPEG, not settled yet
    assert seen[-1][2] is True and len(seen[-1][1]) == 3 and seen[-1][1][2] > 0


def test_lab_status_carries_the_pre_pass_angles_and_the_frame(tmp_path):
    lb = lab.Lab(tmp_path, tmp_path)
    lb._calib_live(b'jpeg', [0., 0.1, 0.2], True)
    assert lb.jpeg == b'jpeg' and lb.status['calib_rpy_deg'] == [0., 0.1, 0.2] and lb.status['calib_settled']


def test_lab_progress_keeps_the_pre_pass_out_of_the_live_total(tmp_path):
    lb = lab.Lab(tmp_path, tmp_path)
    lb._progress(100, 1500, 300)
    assert lb.status['calib_frames'] == 300 and lb.live()['total'] == 1200


def test_live_returns_only_whole_new_frames(tmp_path):
    lb = lab.Lab(tmp_path, tmp_path)
    assert lb.live()['frames'] == 0
    cols = {k: [1.] * 5 for k in lab.COLUMNS}
    cols['radar_m'].pop()                                   # a frame still being appended
    lb._live(b'jpg', cols)
    d = lb.live(2)
    assert d['frames'] == 4 and d['start'] == 2 and d['t_s'] == [1., 1.] and lb.jpeg == b'jpg'


def test_ground_truth_curvature_is_read_from_gt_csv(segment):
    """A segment with gt.csv (comma2k19_lane_test: curvature in 1/m, + = left) shows it in 1/km per frame."""
    assert np.isnan(lab.curvature_reference(segment, 3)).all() and len(lab.curvature_reference(segment, 3)) == 3
    (segment / 'gt.csv').write_text('frame,t_s,speed_m_s,curvature\n0,0,10,0.005\n1,0.05,10,-0.002\n')
    ref = lab.curvature_reference(segment, 3)
    assert ref[0] == pytest.approx(5.) and ref[1] == pytest.approx(-2.) and np.isnan(ref[2])


def test_run_records_the_curvature_columns(segment, tmp_path, monkeypatch):
    """The yaw curvature and the drawn path's curvature of every frame, in 1/km, + = left (the test's sign)."""
    from src.roadwatch.pipeline import Result
    (segment / 'gt.csv').write_text('frame,t_s,speed_m_s,curvature\n' + ''.join(f'{i},0,10,0.004\n' for i in range(40)))

    class FakePipe:
        K = np.eye(3)

        def __init__(self, *a, **kw):
            pass

        def step(self, y, u, v, pts=None):
            lead = np.zeros((1, 3, 6, 4))
            out = dict(lead=lead, lead_stds=np.ones((1, 3, 6, 4)), lead_prob=np.array([[.9, 0, 0]]))
            return Result('calibrated', np.zeros(3), 1.2, 5., .9, None, 20., None, out, curvature=.006)
    monkeypatch.setattr(lab, 'Pipeline', FakePipe)
    monkeypatch.setattr(lab, 'estimate_calibration', lambda *a, **k: (np.zeros(3), np.zeros(3)))
    monkeypatch.setattr(lab, 'draw', lambda frame, *a, **kw: frame)
    monkeypatch.setattr(lab, 'LaneSmoother', lambda: type('L', (), {'update': lambda self, r: None})())
    res = lab.run(segment, tmp_path / 'cache', model=object())
    assert res['curv_gt'][0] == pytest.approx(4.) and res['curv_yaw'][0] == pytest.approx(-6.)
    assert -6. < res['curv_drawn'][0] < 0.   # the drawn path turns the same way but only until 'reach', then goes straight


def test_the_video_shows_the_lead_the_pipeline_found_on_a_curve(segment, tmp_path, monkeypatch):
    """On a curve the car ahead in our lane is 6 m off the camera axis: comma's raw gate (|y| <= 2 m) drops it, but
    BT-A follows the lane and found it (gap_m): the video draws that lead too, at its raw distance minus the bumper."""
    from src.roadwatch.pipeline import Result
    drawn = []

    class FakePipe:
        K = np.eye(3)

        def __init__(self, *a, **kw):
            pass

        def step(self, y, u, v, pts=None):
            lead = np.zeros((1, 3, 6, 4))
            lead[0, 0, 0, :2] = 42., -6.
            out = dict(lead=lead, lead_stds=np.ones((1, 3, 6, 4)), lead_prob=np.array([[.97, 0, 0]]))
            return Result('calibrated', np.zeros(3), 1.2, 15., .97, 40.5, 20., None, out, 1., -6., np.zeros(3), 42.)
    monkeypatch.setattr(lab, 'Pipeline', FakePipe)
    monkeypatch.setattr(lab, 'estimate_calibration', lambda *a, **k: (np.zeros(3), np.zeros(3)))
    monkeypatch.setattr(lab, 'draw', lambda frame, k, r, fy, **kw: drawn.append(r) or frame)
    monkeypatch.setattr(lab, 'LaneSmoother', lambda: type('Lane', (), {'update': lambda self, r: None})())
    lab.run(segment, tmp_path / 'cache', model=object(), bumper=1.5)
    assert drawn[0].gap_m is None   # model warm-up: nothing yet
    assert drawn[25].gap_m == pytest.approx(40.5) and drawn[39].gap_m == pytest.approx(40.5)   # gap 42 - 1.5


def test_gt_csv_is_the_speed_log_of_a_segment_without_can(tmp_path):
    """comma2k19_lane_test has no CAN log, but gt.csv has the real speed per frame (global_pose): it is the speed log."""
    seg = tmp_path / 'lane_c01'
    (seg / 'global_pose').mkdir(parents=True)
    (seg / 'video.mp4').write_bytes(b'\0')
    assert not lab.segments(tmp_path, tmp_path / 'cache')[0]['has_speed']
    (seg / 'gt.csv').write_text('frame,t_s,speed_m_s,curvature\n0,0.00,10,0\n1,0.05,12,0\n2,0.10,14,0\n')
    s = lab.segments(tmp_path, tmp_path / 'cache')[0]
    assert s['has_speed'] and not s['has_radar']
    log = lab.GtSpeed(seg)
    assert log(0.) == pytest.approx(10.) and log(0.075) == pytest.approx(13.) and np.isnan(log(1.))
    log.observe(0., 5.)


def test_run_uses_the_gt_speed_as_the_speed_log_and_none_without_a_log(segment, tmp_path, monkeypatch):
    """The ego speed log (ego_log_mps, and the pipeline's v_ref when asked) is the CAN speed, else gt.csv's, else none."""
    from src.roadwatch.pipeline import Result
    made = []

    class FakePipe:
        K = np.eye(3)

        def __init__(self, *a, v_ref=None, **kw):
            made.append(v_ref)

        def step(self, y, u, v, pts=None):
            out = dict(lead=np.zeros((1, 3, 6, 4)), lead_stds=np.ones((1, 3, 6, 4)), lead_prob=np.array([[.9, 0, 0]]))
            return Result('calibrated', np.zeros(3), 1.2, 5., .9, None, 20., None, out)
    monkeypatch.setattr(lab, 'Pipeline', FakePipe)
    monkeypatch.setattr(lab, 'estimate_calibration', lambda *a, **k: (np.zeros(3), np.zeros(3)))
    monkeypatch.setattr(lab, 'draw', lambda frame, *a, **kw: frame)
    monkeypatch.setattr(lab, 'LaneSmoother', lambda: type('Lane', (), {'update': lambda self, r: None})())
    for f in ('processed_log/CAN/speed/t.npy', 'processed_log/CAN/speed/value.npy'):
        (segment / f).unlink()                                   # no CAN log
    res = lab.run(segment, tmp_path / 'c1', model=object())
    assert res['ego_log_mps'] == [None] * 40 and made[-1] is None
    (segment / 'gt.csv').write_text('frame,t_s,speed_m_s,curvature\n' + ''.join(f'{i},0,{10 + i},0\n' for i in range(40)))
    res = lab.run(segment, tmp_path / 'c2', model=object())
    assert res['ego_log_mps'][0] == pytest.approx(10.) and res['ego_log_mps'][20] == pytest.approx(30.)
    assert isinstance(made[-1], lab.GtSpeed)
    res = lab.run(segment, tmp_path / 'c3', model=object(), use_log=False)
    assert res['ego_log_mps'][20] == pytest.approx(30.) and made[-1] is None   # shown, but not given to the model
