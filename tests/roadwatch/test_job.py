import json
import os
import subprocess
import time

import numpy as np
import pytest

from src.roadwatch import job
from src.roadwatch.pipeline import Result


def test_prune_keeps_the_newest_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(job, 'KEEP_RUNS', 2)
    for k in range(4):
        (tmp_path / f'r{k}').mkdir()
        (tmp_path / f'r{k}' / 'run.json').write_text('{}')
        os.utime(tmp_path / f'r{k}', (k, k))
    job.Job(tmp_path).prune()
    assert sorted(p.name for p in tmp_path.iterdir()) == ['r2', 'r3']


def test_health_reports_a_hung_run(tmp_path):
    j = job.Job(tmp_path)
    assert j.health()['status'] == 'ok'
    j.status, j.last_frame_at = {'state': 'running'}, time.monotonic() - 2 * job.HANG_S
    assert j.health() == {'status': 'degraded', 'job': 'running', 'hung': True}



class FakePipeline:
    """Stands in for BT-A: a lead 30 m ahead at 90 km/h (below the 70 m legal gap; spoken after the 4 s cut-in grace), or raises on chosen frames."""
    fail = set()

    def __init__(self, w, h, fy, d, model, tick_dt=.05, **kw):
        self.K, self.coverage, self.n, self.kw = np.eye(3) * fy, 1.0, 0, kw
        self.cal = type('Cal', (), {'resets': 0, 'est': np.zeros(3)})()

    def step(self, y, u, v, pts=None):
        self.n += 1
        if self.n in self.fail:
            raise RuntimeError('bad frame')
        return Result('calibrated', np.zeros(3), 1.3, 25.0, 0.99, 30.0, 25.0, None, {}, fy_px=self.K[0, 0])

    def save_csv(self, path):
        path.write_text('time_s\n')


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'run' / 'input.mp4'
    path.parent.mkdir()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=8', str(path)], check=True)
    return path


@pytest.fixture
def run(monkeypatch, video):
    monkeypatch.setattr(job, 'Gr14VinAI', lambda *a, **k: None)
    monkeypatch.setattr(job, 'Pipeline', FakePipeline)
    monkeypatch.setattr(job, 'draw', lambda frame, *a: frame)

    def go(fail=()):
        FakePipeline.fail = set(fail)
        j = job.Job(video.parent.parent)
        j._run('abc123abc123', video, 20.0, 1.5, 900.0, False, name='clip.mp4')
        return j, video.parent
    return go


def test_a_run_writes_its_outputs_and_speaks_once(run):
    j, folder = run()
    assert j.status['state'] == 'done' and j.status['ops']['said']['warning'] == 1
    meta = json.loads((folder / 'run.json').read_text())
    assert meta['state'] == 'done' and meta['video'] == 'clip.mp4' and meta['frames'] == 160
    assert json.loads((folder / 'decisions.json').read_text())['events'][0]['kind'] == 'warning'
    assert (folder / 'annotated.mp4').stat().st_size > 0
    assert json.loads((folder.parent / 'heartbeat.json').read_text())['state'] == 'done'


def test_a_bad_frame_is_skipped(run):
    j, _ = run(fail={5, 6})
    assert j.status['state'] == 'done' and j.status['ops']['bad_frames'] == 2


def test_too_many_bad_frames_in_a_row_fail_the_run(run):
    j, folder = run(fail=set(range(10, 10 + job.MAX_BAD_FRAMES)))
    assert j.status['state'] == 'failed' and 'liên tiếp' in j.status['error']
    assert json.loads((folder / 'run.json').read_text())['state'] == 'failed'


def test_a_30_fps_video_feeds_the_model_every_second_frame_and_keeps_every_frame(run, tmp_path):
    """Like comma_ai realtime_lead: model ticks close to 20 Hz, every video frame drawn and written."""
    path = tmp_path / 'r30' / 'input.mp4'
    path.parent.mkdir()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=30:d=2', str(path)], check=True)
    FakePipeline.fail = set()   # the run fixture stands in for the model, BT-A and the HUD
    j = job.Job(tmp_path)
    j._run('abc123abc124', path, 30.0, 1.5, 900.0, False, name='clip30.mp4')
    assert j.status['state'] == 'done' and json.loads((path.parent / 'run.json').read_text())['frames'] == 30
    n = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                        'stream=nb_read_frames', '-of', 'csv=p=0', str(path.parent / 'annotated.mp4')],
                       capture_output=True, text=True, check=True).stdout.strip()
    assert int(n) == 60


def test_lens_settings_give_the_focal_length_like_comma():
    o = job.Options
    assert job.given_focal(900., o(), 1164, 874) == (900., 'nhập tay')
    assert job.given_focal(None, o(lens='mm', f_mm=26.), 1920, 1080)[0] == pytest.approx(26 * 1920 / 34.6)
    assert job.given_focal(None, o(lens='mm', f_mm=4., sensor_mm=5.6), 1920, 1080)[0] == pytest.approx(4 * 1920 / 5.6)
    assert job.given_focal(None, o(lens='fov', hfov_deg=90.), 1000, 750)[0] == pytest.approx(500.)
    assert job.given_focal(None, o(lens='fov', hfov_deg=120., fisheye=True), 1000, 750)[0] == pytest.approx(500 / (np.pi / 3))
    assert job.given_focal(None, o(lens='learn'), 1164, 874) == (None, None)   # learned, only when asked
    with pytest.raises(ValueError, match='chưa có tiêu cự'):   # the default is typed in, never learned
        job.given_focal(None, o(), 1164, 874)


def test_camera_box_modes(video):
    assert job.camera_box(video, 'full') == (0, 0, 320, 240)
    assert job.camera_box(video, (11, 20, 201, 151)) == (12, 20, 200, 150)   # even, inside the picture
    with pytest.raises(ValueError, match='ngoài khung'):
        job.camera_box(video, (200, 0, 200, 240))


def test_a_run_with_a_gps_log_writes_comma_outputs(run, video, monkeypatch):
    log = video.parent / 'track.csv'
    log.write_text('t,speed_mps\n' + ''.join(f'{t},{20 + t % 3}\n' for t in range(30)))
    seen = {}
    monkeypatch.setattr(job, 'Pipeline', lambda *a, **kw: seen.update(kw) or FakePipeline(*a, **kw))
    j = job.Job(video.parent.parent)
    j._run('abc123abc125', video, 20.0, 1.5, None, False, name='clip.mp4',
           opts=job.Options(lens='fov', hfov_deg=70., gps=log, gps_offset=0.))
    assert j.status['state'] == 'done' and isinstance(seen['v_ref'], job.gpslib.GpsRef) and seen['focal'] is None
    calib = json.loads((video.parent / 'calibration.json').read_text())
    assert calib['gps_offset_s'] == 0. and calib['flags'] == [] and calib['focal_px'] == pytest.approx(160 / np.tan(np.radians(35)))
    assert (video.parent / 'lead_distance.csv').exists() and j.status['outputs']['csv_url'].endswith('lead_distance.csv')
    assert j.status['measure']['gps']['state'] == 'synced'


def test_auto_focal_without_gps_is_flagged(run, video):
    j = job.Job(video.parent.parent)
    j._run('abc123abc126', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options(auto_focal=True))
    assert j.status['measure']['calibration']['flags'] == ['auto_focal_needs_gps']


@pytest.mark.parametrize('every, shown', [(2, 80), (1, 160), (5, 32)])
def test_the_live_preview_is_refreshed_every_n_video_frames(run, video, monkeypatch, every, shown):
    """comma Upload_video.py `preview_every` (default 2); the video file still gets every frame."""
    previews = []
    monkeypatch.setattr(job.Job, '_preview', lambda self, frame, w, h: previews.append(frame))
    j = job.Job(video.parent.parent)
    j._run('abc123abc127', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options(preview_every=every))
    assert j.status['state'] == 'done' and len(previews) == shown
    assert j.status['ops']['video_fps'] == 20.0
    assert j.preview[0:2] == ('abc123abc127', 159), 'WebRTC receives every frame independently of JPEG preview_every'
