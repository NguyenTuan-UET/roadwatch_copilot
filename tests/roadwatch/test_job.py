import json
import os
import subprocess
import threading
import time

import numpy as np
import pytest

from src.roadwatch import job, phone
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
    """Stands in for BT-A: a lead 50 m ahead at 90 km/h (below the 70 m legal gap, above the 35 m "far too close"), or raises
    on chosen frames."""
    fail = set()

    def __init__(self, w, h, fy, d, model, tick_dt=.05, **kw):
        self.K, self.coverage, self.n, self.kw = np.eye(3) * fy, 1.0, 0, kw
        self.cal = type('Cal', (), {'resets': 0, 'est': np.zeros(3)})()

    def step(self, y, u, v, pts=None):
        self.n += 1
        if self.n in self.fail:
            raise RuntimeError('bad frame')
        v_ref = self.kw.get('v_ref')
        synced = v_ref is not None and v_ref.synced
        return Result('calibrated', np.zeros(3), 1.3, 25.0, 0.99, 50.0, 25.0, None, {}, gap_std_m=1.24, fy_px=self.K[0, 0],
                      model_speed_mps=24.0, gps_speed_mps=22.0 if synced else None)

    def save_csv(self, path):
        path.write_text('time_s\n')


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'run' / 'input.mp4'
    path.parent.mkdir()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=8', str(path)], check=True)
    return path


class FakeLane:
    def update(self, r):
        return None


drawn = []


@pytest.fixture
def run(monkeypatch, video):
    drawn.clear()
    monkeypatch.setattr(job, 'Gr14VinAI', lambda *a, **k: None)
    monkeypatch.setattr(job, 'Pipeline', FakePipeline)
    monkeypatch.setattr(job, 'draw', lambda frame, *a, **kw: drawn.append(kw) or frame)
    monkeypatch.setattr(job, 'overlay', lambda cam_k, r, w, h, lane=None: {'lane': None, 'lead': None, 'size': [w, h]})
    monkeypatch.setattr(job, 'LaneSmoother', FakeLane)

    def go(fail=()):
        FakePipeline.fail = set(fail)
        j = job.Job(video.parent.parent)
        j._run('abc123abc123', video, 20.0, 1.5, 900.0, False, name='clip.mp4')
        return j, video.parent
    return go


def test_the_run_video_has_no_debug_box(run):
    run()
    assert drawn and all(kw.get('debug') is False for kw in drawn)   # angles and GPS state are on the web panel


def test_a_run_writes_its_outputs_and_speaks(run):
    j, folder = run()   # 8 s below the legal gap, not opening: warning at 0.5 s, repeated at 3.5 s
    assert j.status['state'] == 'done' and j.status['ops']['said'] == dict(chime=0, info=0, warning=2, emergency=0)
    meta = json.loads((folder / 'run.json').read_text())
    assert meta['state'] == 'done' and meta['video'] == 'clip.mp4' and meta['frames'] == 160
    assert json.loads((folder / 'decisions.json').read_text())['events'][0]['kind'] == 'warning'
    assert (folder / 'annotated.mp4').stat().st_size > 0
    assert json.loads((folder.parent / 'heartbeat.json').read_text())['state'] == 'done'
    m = j.status['measure']   # the phone overlay shows the image speed beside GPS and the gap with its ±
    assert m['model_kmh'] == pytest.approx(86.4) and m['lead']['gap_std_m'] == pytest.approx(1.2)
    assert m['gps_kmh'] is None   # no GPS log: no speed from it


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
    m = j.status['measure']
    assert m['gps_kmh'] == pytest.approx(79.2) and m['ego_source'] == 'gps'   # the log's own speed


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


def test_a_live_run_reads_the_phone_until_it_disconnects(run, tmp_path, monkeypatch):
    """The /phone page: frames and GPS fixes on the session clock instead of a video file and a GPS log."""
    seen = {}
    monkeypatch.setattr(job, 'Pipeline', lambda *a, **kw: seen.update(kw, tick_dt=a[6] if len(a) > 6 else None)
                        or FakePipeline(*a, **kw))
    src, speed = phone.FrameSource(), phone.LiveGps()
    speed.add(0., dict(speed=25., lat=10., lon=106., acc=5.))
    pts = []

    def feed():
        for k in range(40):
            src.push(np.full((72, 64), 128, np.uint8), k * .05)
            end = time.monotonic() + 5   # first frame: wait until the run (still starting) takes it, or a later one replaces it
            while k == 0 and src.latest is not None and time.monotonic() < end:
                time.sleep(.001)
            time.sleep(.005)
        src.close()
    threading.Thread(target=feed).start()
    j = job.Job(tmp_path / 'runs')
    real_step = FakePipeline.step
    monkeypatch.setattr(FakePipeline, 'step', lambda self, y, u, v, t=None: pts.append(t) or real_step(self, y, u, v, t))
    j._run('abc123abc128', src, 20.0, 1.5, None, False, name='iPhone',
           opts=job.Options(f_mm=26., speed=speed, crop='full'))
    folder = tmp_path / 'runs' / 'abc123abc128'
    meta = json.loads((folder / 'run.json').read_text())
    assert j.status['state'] == 'done' and meta['video'] == 'iPhone' and meta['source'] == 'phone'
    assert seen['v_ref'] is speed and meta['crop'] == [0, 0, 64, 48]
    assert 1 <= meta['frames'] <= 40 and pts == sorted(pts) and pts[0] == 0.   # model fed on the session clock
    assert (folder / 'gps.csv').read_text().splitlines()[1].startswith('0.000,25.000')
    assert (folder / 'annotated.mp4').stat().st_size > 0 and j.status['measure']['gps']['state'] == 'synced'
    run_id, frame, geo = j.overlay   # lane and lead for the phone to draw on its live camera
    assert run_id == 'abc123abc128' and frame == meta['frames'] - 1 and geo['size'] == [64, 48]


def test_a_live_run_without_frames_fails(run, tmp_path, monkeypatch):
    monkeypatch.setattr(phone.FrameSource, 'WAIT_S', .05)
    src = phone.FrameSource()
    j = job.Job(tmp_path / 'runs')
    j._run('abc123abc129', src, 20.0, 1.5, None, False, name='iPhone', opts=job.Options(f_mm=26.))
    assert j.status['state'] == 'failed' and 'điện thoại' in j.status['error']


def test_a_live_run_from_a_phone_held_upright_fails(run, tmp_path):
    src = phone.FrameSource()
    src.push(np.zeros((96, 48), np.uint8), 0.)   # 48 x 64: portrait
    j = job.Job(tmp_path / 'runs')
    j._run('abc123abc12a', src, 20.0, 1.5, None, False, name='iPhone', opts=job.Options(f_mm=26.))
    assert j.status['state'] == 'failed' and 'xoay ngang' in j.status['error']


@pytest.fixture
def upright(tmp_path):
    """A phone video filmed upright: 320x240 stored, shown rotated by 90 deg (as iPhone files carry it)."""
    plain, path = tmp_path / 'plain.mp4', tmp_path / 'run2' / 'input.mp4'
    path.parent.mkdir()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=1', str(plain)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-display_rotation', '90', '-i', str(plain), '-c', 'copy', str(path)], check=True)
    return path


def test_video_size_is_the_size_as_shown(video, upright):
    """ffmpeg rotates frames while decoding, so the crop must use the rotated size."""
    assert job.video_size(video) == (320, 240) and job.video_size(upright) == (240, 320)


def test_an_upright_video_fails_with_the_reason(run, upright):
    j = job.Job(upright.parent.parent)
    j._run('abc123abc12b', upright, 20.0, 1.5, 900., False, name='2.mp4')
    assert j.status['state'] == 'failed' and 'quay dọc' in j.status['error']


def test_a_video_that_gives_no_frame_fails(run, video, monkeypatch):
    monkeypatch.setattr(job, 'decode', lambda *a, **k: iter(()))
    j = job.Job(video.parent.parent)
    j._run('abc123abc12c', video, 20.0, 1.5, 900., False, name='clip.mp4')
    assert j.status['state'] == 'failed' and 'không giải mã được khung nào' in j.status['error']
    assert json.loads((video.parent / 'run.json').read_text())['state'] == 'failed'


def test_a_big_video_is_processed_at_most_max_width(run, video, monkeypatch):
    """A 1916-px screen recording took ~120 ms a frame (HUD, encoder); the model only needs 512x256."""
    monkeypatch.setattr(job, 'MAX_WIDTH', 160)
    seen = []
    monkeypatch.setattr(job, 'Pipeline', lambda *a, **kw: seen.append(a[:3]) or FakePipeline(*a, **kw))
    j = job.Job(video.parent.parent)
    j._run('abc123abc12d', video, 20.0, 1.5, 900., False, name='clip.mp4')
    assert j.status['state'] == 'done' and seen[0] == (160, 120, 450.)   # fy typed in px follows the scale
    assert job.video_size(video.parent / 'annotated.mp4') == (160, 120)
    assert json.loads((video.parent / 'run.json').read_text())['frames'] == 160


def test_a_gps_log_is_used_as_it_is_from_the_first_frame(run, video, monkeypatch):
    """No sync step: unless an offset is given the log is taken to start with the video (offset 0), so its speed drives the
    ego speed from the first frame (a steady-speed start gave the old correlation nothing to align on)."""
    log = video.parent / 'track.csv'
    log.write_text('t,speed_mps\n' + ''.join(f'{t},{20 + t % 3}\n' for t in range(30)))
    seen = {}
    monkeypatch.setattr(job, 'Pipeline', lambda *a, **kw: seen.update(kw) or FakePipeline(*a, **kw))
    j = job.Job(video.parent.parent)
    j._run('abc123abc995', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options(gps=log))   # no gps_offset
    ref = seen['v_ref']
    assert ref.synced and ref.offset == 0. and not ref.low_confidence and ref(1.) == pytest.approx(21.)
    m = j.status['measure']
    assert m['gps']['state'] == 'synced' and m['gps']['offset_s'] == 0. and m['ego_source'] == 'gps'
    assert m['gps_kmh'] == pytest.approx(79.2) and 'gps_provisional' not in m


def test_a_radar_log_is_shown_in_the_panel_and_the_measure(run, video, monkeypatch):
    """The radar's distance at the video time goes to the HUD panel (radar_ref, as in the Lab; NaN when there is none) and to
    the measure; without a log the panel still has its radar line ('Radar _')."""
    radar = video.parent / 'radar.csv'
    radar.write_text('t,radar_m\n' + ''.join(f'{t / 20},{50 - t / 20}\n' for t in range(200)))
    j = job.Job(video.parent.parent)
    j._run('abc123abc994', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options(radar=radar))
    assert j.status['measure']['radar_m'] is not None and 40. < j.status['measure']['radar_m'] < 50.
    assert drawn and all('radar_ref' in kw for kw in drawn) and np.isfinite(drawn[-1]['radar_ref'])
    drawn.clear()
    j = job.Job(video.parent.parent)
    j._run('abc123abc993', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options())
    assert j.status['measure']['radar_m'] is None and drawn and all(np.isnan(kw['radar_ref']) for kw in drawn)


def test_an_fps_that_differs_from_the_video_is_flagged(run, video):
    """The model reads the speed from the time between frames: 29.97 fps footage run as 20 fps gives 1.5 times too low."""
    from src.roadwatch.model import video_fps
    assert video_fps(video) == pytest.approx(20.0)
    j = job.Job(video.parent.parent)
    j._run('abc123abc128', video, 30.0, 1.5, 900., False, name='clip.mp4', opts=job.Options())
    assert j.status['measure']['calibration']['flags'] == ['fps_differs_from_video']
    j._run('abc123abc129', video, 20.0, 1.5, 900., False, name='clip.mp4', opts=job.Options())
    assert j.status['measure']['calibration']['flags'] == []
