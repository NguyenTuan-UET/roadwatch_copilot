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
    out = tmp_path / 'cache'
    seen, prog = [], []
    lab.run(segment, out, model=object(), bumper=1.5, fy=910., live=lambda jpeg, cols: seen.append((jpeg, cols)),
            progress=lambda *a: prog.append(a))
    assert seen[0][0] is None and seen[-1][0][:2] == b'\xff\xd8' and len(seen) == 41   # JPEG per frame, columns shared
    assert len(seen[-1][1]['t_s']) == 40
    assert calls == [(40, 'dup')] and prog[0] == (40, 80, 40) and prog[-1] == (80, 80, 40)   # pre-pass, then the run
    assert made['wide'] == 'dup' and list(made['rpy']) == [0, 0, .02] and list(made['rpy_est']) == [.01, -.03, .02]
    r, kw = drawn[0]
    assert r.gap_m is None and kw == dict(radar_ref=30., debug=False)        # lead_mask warm-up: no lead yet
    r, _ = drawn[20]
    assert r.gap_m == pytest.approx(30.) and r.lead_x_m == 31.5 and r.ttc_s is None   # raw lead minus bumper
    res = json.loads((out / 'seg1' / 'result.json').read_text())
    assert res['frames'] == 40 and res['radar_m'][0] == 30. and res['lead_x_m'][0] == 31.5
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
    L = lab.Lab(tmp_path, tmp_path)
    assert L.live()['frames'] == 0
    cols = {k: [1.] * 5 for k in lab.COLUMNS}
    cols['radar_m'].pop()                                   # a frame still being appended
    L._live(b'jpg', cols)
    d = L.live(2)
    assert d['frames'] == 4 and d['start'] == 2 and d['t_s'] == [1., 1.] and L.jpeg == b'jpg'
