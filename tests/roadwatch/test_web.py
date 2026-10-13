"""API of the demo server; the model never runs (Job.start is replaced)."""
import json

import pytest
from fastapi.testclient import TestClient

from src.roadwatch import web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, 'ACCOUNTS_ENABLED', False)
    monkeypatch.setattr(web.JOB, 'runs', tmp_path)
    started = []

    def fake_start(run_id, video, fps, d, fy, rt, name=None, opts=None):
        started.append((run_id, video, fps, d, fy, rt, opts))
        (video.parent / 'run.json').write_text(json.dumps(dict(run_id=run_id, video=name, started_unix=0.0)))
    monkeypatch.setattr(web.JOB, 'start', fake_start)
    c = TestClient(web.app)
    c.started = started
    return c


def test_health_and_security_headers(client):
    r = client.get('/health')
    assert r.status_code == (200 if r.json()['status'] == 'ok' else 503) and r.json()['timestamp']
    assert client.get('/health/live').json() == {'status': 'alive'}
    assert r.headers['x-frame-options'] == 'DENY' and 'default-src' in r.headers['content-security-policy']


def test_config_exposes_bt_b_parameters(client):
    c = client.get('/api/config').json()
    assert c['ttc_emergency_s'] == 1.8 and c['phrases']['warning']
    assert c['legal_bands'][2] == {'v_min_kmh': 80.0, 'v_max_kmh': 100.0, 'min_gap_m': 70.0}


def test_webrtc_endpoints_require_login_and_an_active_run(client, monkeypatch):
    monkeypatch.setattr(web, 'PASSWORD', 'test-password')
    assert client.get('/api/rtc').status_code == 401
    offer = {'run_id': 'abc123abc123', 'type': 'offer', 'sdp': 'v=0'}
    assert client.post('/api/rtc/offer', json=offer).status_code == 401
    assert client.delete('/api/rtc/test').status_code == 401
    client.auth = (web.USER, 'test-password')
    assert 'iceServers' in client.get('/api/rtc').json()
    monkeypatch.setattr(web.JOB, 'status', {'state': 'idle'})
    assert client.post('/api/rtc/offer', json=offer).status_code == 409
    assert client.post('/api/rtc/offer', json=offer | {'type': 'answer'}).status_code == 422
    assert client.delete('/api/rtc/test').json() == {'closed': True}


def test_upload_starts_a_run_and_lists_it(client):
    r = client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'\0' * 1000)
    assert r.status_code == 200
    run_id = r.json()['run_id']
    assert client.started[0][2:5] == (20.0, 1.5, 910.0)
    assert [(x['run_id'], x['video']) for x in client.get('/api/runs').json()] == [(run_id, 'a.mp4')]


@pytest.mark.parametrize('query, code', [
    ('name=a.exe&fps=20&d=1.5', 415),       # not a video
    ('name=a.mp4&fps=0&d=1.5', 422),        # fps must be > 0
    ('name=a.mp4&fps=20&d=-1', 422),        # camera->bumper must be >= 0
    ('name=a.mp4&fps=20&d=1.5&fy=-3', 422),
    ('name=a.mp4&fps=20&d=1.5', 422),       # the focal length is never learned: it must be given
    ('name=a.mp4&fps=20&d=1.5&lens=fov', 422),
])
def test_upload_rejects_bad_input(client, query, code):
    assert client.post('/api/runs?' + query, content=b'\0' * 10).status_code == code
    assert not client.started


def test_upload_can_ask_to_learn_the_focal_length(client):
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5&lens=learn', content=b'\0' * 10).status_code == 200
    assert client.started[0][4] is None and client.started[0][6].lens == 'learn'


def test_upload_rejects_empty_and_oversized(client, monkeypatch):
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'').status_code == 400
    monkeypatch.setattr(web, 'MAX_UPLOAD', 100)
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'\0' * 1000).status_code == 413
    assert not client.started and not list(web.JOB.runs.iterdir())


def test_single_frame_for_clients_behind_buffering_proxies(client, monkeypatch):
    """MJPEG never arrives through proxies that buffer streamed responses; the UI then polls the latest JPEG."""
    monkeypatch.setattr(web.JOB, 'jpeg', None)
    assert client.get('/api/frame').status_code == 204
    monkeypatch.setattr(web.JOB, 'jpeg', b'\xff\xd8jpeg\xff\xd9')
    r = client.get('/api/frame')
    assert r.status_code == 200 and r.content == b'\xff\xd8jpeg\xff\xd9'
    assert r.headers['content-type'] == 'image/jpeg' and 'no-store' in r.headers['cache-control']


def test_files_cannot_escape_the_run_folder(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'x').json()['run_id']
    assert client.get(f'/api/runs/{run_id}/files/run.json').status_code == 200
    assert client.get(f'/api/runs/{run_id}/files/input.mp4').status_code == 404      # uploads are not served back
    assert client.get('/api/runs/..%2F..%2Fetc/files/run.json').status_code == 404
    assert client.get('/api/phrases/..%2Fx').status_code == 404
    assert client.get('/api/phrases/beep').status_code == 422       # only the three alert levels


def test_delete_run_erases_the_upload(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'x').json()['run_id']
    assert client.delete(f'/api/runs/{run_id}').status_code == 200
    assert not (web.JOB.runs / run_id).exists() and client.get('/api/runs').json() == []
    assert client.delete(f'/api/runs/{run_id}').status_code == 404


def test_status_and_history_follow_the_schema(client):
    st = client.get('/api/status').json()
    assert st['state'] == 'idle' and st['api_version'] and st['measure'] is None
    assert client.get('/api/history').json()['samples'] == []


def test_a_running_status_validates_against_live_status():
    from src.roadwatch.schemas import LiveStatus
    lead = dict(prob=0.98, gap_m=42.3, speed_kmh=62.2)
    cal = dict(status='calibrated', calibrated=True, flags=[], fy_px=913, fy_state='đã học', pitch_deg=3.5, yaw_deg=0.8,
               height_m=1.35, coverage=1.0, remounts=0)
    counts = dict(info=0, warning=1, emergency=0)
    LiveStatus.model_validate(dict(
        state='running', run_id='5ec77ceab6a9',
        measure=dict(frame=10, t_s=0.5, ego_kmh=66.0, ego_source='gps', lead_raw_m=41.9, ttc_s=None, lead=lead,
                     gps=dict(state='synced', offset_s=1.25, corr=0.93), calibration=cal),
        decision=dict(level='warning', say=None, reason='x', threshold_m=55.0, latency_us=7),
        ops=dict(fps=20.0, bad_frames=0, latency=dict(last_ms=14.0, p50_ms=14.2, p95_ms=18.5),
                 raw_onsets=counts, said=counts),
        sample=dict(t_s=0.5, gap_m=42.3, threshold_m=55.0, ttc_s=None), events=[]))


def test_openapi_document_is_up_to_date():
    from scripts.roadwatch.export_api_schema import OUT, document
    assert OUT.read_text(encoding='utf-8') == document(), 'run python -m scripts.roadwatch.export_api_schema'


def test_password_protects_everything_but_health(client, monkeypatch, tmp_path):
    import base64
    monkeypatch.setattr(web, 'PASSWORD', 's3cret')
    model = tmp_path / 'model.onnx'
    model.touch()  # Health checks file presence only; authentication must not depend on a downloaded model.
    monkeypatch.setattr(web, 'MODEL_FILE', model)
    assert client.get('/health').status_code == 200
    r = client.get('/api/status')
    assert r.status_code == 401 and r.headers['www-authenticate'].startswith('Basic')
    bad = base64.b64encode(b'roadwatch:nope').decode()
    good = base64.b64encode(b'roadwatch:s3cret').decode()
    assert client.get('/api/status', headers={'Authorization': 'Basic ' + bad}).status_code == 401
    assert client.get('/api/status', headers={'Authorization': 'Basic !!'}).status_code == 401
    assert client.get('/api/status', headers={'Authorization': 'Basic ' + good}).status_code == 200


def test_websocket_sends_live_status_and_checks_the_password(client, monkeypatch):
    import base64

    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect('/api/ws') as w:
        assert w.receive_json()['state'] == 'idle'
    monkeypatch.setattr(web, 'PASSWORD', 's3cret')
    with pytest.raises(WebSocketDisconnect), client.websocket_connect('/api/ws') as w:
        w.receive_json()
    good = base64.b64encode(b'roadwatch:s3cret').decode()
    with client.websocket_connect('/api/ws', headers={'Authorization': 'Basic ' + good}) as w:
        assert w.receive_json()['api_version']


def test_health_is_503_without_the_model(client, monkeypatch, tmp_path):
    monkeypatch.setattr(web, 'MODEL_FILE', tmp_path / 'missing.onnx')
    assert client.get('/health').status_code == 503
    assert client.get('/health/ready').status_code == 503
    assert client.get('/health/live').status_code == 200


def test_logs_are_one_json_object_per_line():
    import logging
    rec = logging.LogRecord('x', logging.ERROR, __file__, 1, 'quote " inside', None, (ValueError, ValueError('boom'), None))
    entry = json.loads(web.JSONFormatter().format(rec))
    assert entry['message'] == 'quote " inside' and entry['exception']['type'] == 'ValueError'


def test_demo_and_engineer_views_are_available(client):
    assert client.get('/').status_code == 200
    assert client.get('/app').status_code == 200
    assert client.get('/engineer').status_code == 200
    assert client.get('/judge').status_code == 200


def test_web_app_is_served_offline_from_the_package(client):
    cockpit, page = client.get('/').text, client.get('/app').text
    assert '/ui/cockpit.js' in cockpit and '/app' in cockpit          # entry: the cockpit, the V leads to the app
    assert '/ui/app.js' in page and '/ui/app.css' in page and '/ui/scene3d.js' in page
    assert 'https://' not in cockpit + page           # CSP default-src 'self': no CDN, works without network
    files = {name: client.get(f'/ui/{name}') for name in ('app.js', 'app.css', 'scene3d.js', 'cockpit.js', 'cockpit.jpg')}
    assert all(r.status_code == 200 for r in files.values())
    js, css = files['app.js'], files['app.css']
    assert 'javascript' in js.headers['content-type'] and css.headers['content-type'].startswith('text/css')
    assert files['cockpit.jpg'].headers['content-type'] == 'image/jpeg'
    assert not any('https://' in files[n].text for n in ('app.js', 'app.css', 'scene3d.js', 'cockpit.js'))
    assert js.headers['x-frame-options'] == 'DENY'    # static files get the same security headers
    assert client.get('/ui/..%2Fweb.py').status_code == 404
    assert client.get('/ui/missing.js').status_code == 404


def test_sample_run_keeps_the_original_after_deleting_the_run(client, monkeypatch, tmp_path):
    samples = tmp_path / 'samples'
    samples.mkdir()
    (samples / 'demo.mp4').write_bytes(b'video')
    (samples / 'demo.json').write_text(json.dumps(dict(title='Demo', fps=20, d=1.5, fy=910)))
    (samples / 'missing.json').write_text(json.dumps(dict(title='Missing', fps=20, d=1.5, fy=910)))
    monkeypatch.setattr(web, 'SAMPLES', samples)
    entries = client.get('/api/samples').json()
    assert len(entries) == 1 and entries[0]['id'] == 'demo' and entries[0]['fy'] == 910
    response = client.post('/api/samples/demo/run')
    assert response.status_code == 200
    run_id = response.json()['run_id']
    assert client.started[0][2:6] == (20.0, 1.5, 910.0, True)
    assert (web.JOB.runs / run_id / 'input.mp4').read_bytes() == b'video'
    assert client.delete(f'/api/runs/{run_id}').status_code == 200
    assert (samples / 'demo.mp4').read_bytes() == b'video'
    assert client.post('/api/samples/missing/run').status_code == 404


def test_sample_run_copies_when_hard_links_are_unavailable(client, monkeypatch, tmp_path):
    samples = tmp_path / 'samples'
    samples.mkdir()
    (samples / 'demo.mp4').write_bytes(b'video')
    (samples / 'demo.json').write_text(json.dumps(dict(title='Demo', fps=20, d=1.5, fy=910)))
    monkeypatch.setattr(web, 'SAMPLES', samples)

    def unavailable(*args):
        raise OSError('different filesystem')

    monkeypatch.setattr(web.os, 'link', unavailable)
    response = client.post('/api/samples/demo/run?rt=false')
    assert response.status_code == 200
    assert client.started[0][4:6] == (910.0, False)
    assert (web.JOB.runs / response.json()['run_id'] / 'input.mp4').read_bytes() == b'video'


@pytest.mark.parametrize('field,value', [('fps', 0), ('fps', float('nan')), ('d', -1), ('fy', 0)])
def test_sample_metadata_rejects_invalid_camera_parameters(field, value):
    from pydantic import ValidationError

    from src.roadwatch.schemas import SampleVideo

    data = dict(id='demo', title='Demo', fps=20, d=1.5)
    data[field] = value
    with pytest.raises(ValidationError):
        SampleVideo.model_validate(data)


GPS_CSV = 't,speed_mps\n' + ''.join(f'{t},{20 + t % 3}\n' for t in range(30))


def test_gps_log_upload_is_checked_and_used_by_a_run(client):
    r = client.post('/api/gps?name=drive.csv', content=GPS_CSV.encode())
    assert r.status_code == 200 and r.json()['fixes'] == 30 and r.json()['duration_s'] == 29.
    gps_id = r.json()['gps_id']
    q = f'name=a.mp4&fps=30&d=1.2&lens=fov&hfov=120&fisheye=true&gps={gps_id}&gps_offset=2.5&auto_focal=true' \
        '&crop=10,0,1900,1080&pitch=false'
    assert client.post('/api/runs?' + q, content=b'\0' * 100).status_code == 200
    opts = client.started[0][6]
    assert (opts.lens, opts.hfov_deg, opts.fisheye, opts.gps_offset, opts.auto_focal, opts.crop, opts.use_pitch) == \
        ('fov', 120., True, 2.5, True, (10, 0, 1900, 1080), False)
    assert opts.gps.parent == client.started[0][1].parent and opts.gps.read_text() == GPS_CSV   # kept with the run
    assert client.post('/api/runs?' + q, content=b'\0' * 100).status_code == 404   # a GPS log is used once


@pytest.mark.parametrize('name, body, code', [('drive.exe', GPS_CSV, 415), ('drive.csv', 'a,b\n1,2\n', 400),
                                               ('drive.gpx', '<gpx></gpx>', 400)])
def test_gps_log_upload_rejects_bad_files(client, name, body, code):
    assert client.post(f'/api/gps?name={name}', content=body.encode()).status_code == code


@pytest.mark.parametrize('query', ['crop=1,2,3', 'crop=x', 'lens=zoom', 'gps=nothex', 'hfov=200', 'f_mm=0'])
def test_run_options_are_validated(client, query):
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910&' + query, content=b'\0' * 10).status_code in (404, 422)
    assert not client.started


def test_preview_rate_is_comma_preview_every(client):
    client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'\0' * 10)
    client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910&preview_every=5', content=b'\0' * 10)
    assert [s[6].preview_every for s in client.started] == [2, 5]
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910&preview_every=11', content=b'\0' * 10).status_code == 422


def test_lab_run_can_warp_the_wide_input(lab_client):
    assert lab_client.post('/api/lab/segments/3/run?wide=warp').status_code == 200
    assert lab_client.lab_started[0][-1] == 'warp'
    assert lab_client.post('/api/lab/segments/3/run?wide=fisheye').status_code == 422


def test_run_results_include_the_comma_csv_and_calibration(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5&fy=910', content=b'\0' * 10).json()['run_id']
    folder = web.JOB.runs / run_id
    (folder / 'lead_distance.csv').write_text('time_s\n0.0\n')
    (folder / 'calibration.json').write_text('{}')
    assert client.get(f'/api/runs/{run_id}/files/lead_distance.csv').text == 'time_s\n0.0\n'
    assert client.get(f'/api/runs/{run_id}/files/calibration.json').json() == {}


@pytest.fixture
def lab_client(client, tmp_path, monkeypatch):
    from src.roadwatch import lab
    root, cache = tmp_path / 'k19', tmp_path / 'labcache'
    (root / '3').mkdir(parents=True)
    (root / '3' / 'video.mp4').write_bytes(b'\0')
    (cache / '3').mkdir(parents=True)
    (cache / '3' / 'result.json').write_text(json.dumps(dict(segment='3', frames=1, fps=20., bumper_m=1.52, fy_px=910.,
        use_log=True, rpy_deg=[0, 1, 0], created_unix=0., t_s=[0.], lead_x_m=[30.], lead_y_m=[.1], lead_prob=[.9],
        lead_std_m=[1.], gap_kalman_m=[None], ego_model_mps=[20.], ego_log_mps=[20.5], radar_m=[28.6])))
    (cache / '3' / 'annotated.mp4').write_bytes(b'mp4')
    monkeypatch.setattr(web, 'LAB', lab.Lab(root, cache))
    started = []
    monkeypatch.setattr(web.LAB, '_run', lambda *a: started.append(a))
    client.lab_started = started
    return client


def test_lab_lists_segments_and_serves_cached_results(lab_client):
    segs = lab_client.get('/api/lab/segments').json()
    assert [(s['id'], s['cached']) for s in segs] == [('3', True)]
    res = lab_client.get('/api/lab/segments/3/result').json()
    assert res['radar_m'] == [28.6] and res['gap_kalman_m'] == [None] and res['bumper_m'] == 1.52
    assert res['curv_gt'] == res['curv_yaw'] == res['curv_drawn'] == []   # a result cached before the curvature columns
    assert lab_client.get('/api/lab/segments/3/video').content == b'mp4'


def test_lab_run_starts_once_and_rejects_bad_ids(lab_client):
    r = lab_client.post('/api/lab/segments/3/run?bumper=1.52&fy=910&log=false')
    assert r.status_code == 200 and r.json()['state'] == 'running'
    assert lab_client.lab_started[0][1:] == (1.52, 910., False, 'dup')   # comma app.py default: duplicated wide input
    assert lab_client.post('/api/lab/segments/3/run').status_code == 409          # one at a time
    assert lab_client.get('/api/lab/status').json()['segment'] == '3'
    assert lab_client.post('/api/lab/segments/nope/run').status_code == 404
    assert lab_client.get('/api/lab/segments/..%2F3/result').status_code == 404


def test_lab_stop_signals_the_running_segment(lab_client):
    assert lab_client.post('/api/lab/stop').json() == {'state': 'stopping'}   # nothing running: harmless
    lab_client.post('/api/lab/segments/3/run')
    assert not web.LAB.stop.is_set()
    assert lab_client.post('/api/lab/stop').json() == {'state': 'stopping'}
    assert web.LAB.stop.is_set()


def test_phone_offer_starts_a_live_run(client, monkeypatch):
    got, started = {}, []

    async def fake_offer(sdp, source, speed):
        got.update(sdp=sdp, source=source, speed=speed)
        return 'v=0 answer'
    monkeypatch.setattr(web.PHONE, 'offer', fake_offer)
    monkeypatch.setattr(web.PHONE, 'follow', lambda alive: got.update(alive=alive))
    monkeypatch.setattr(web.PHONE, 'follow_overlay', lambda run_id, alive, latest: got.update(
        overlay_run_id=run_id, overlay_alive=alive, overlay_latest=latest))
    monkeypatch.setattr(web.JOB, 'start', lambda *a, **kw: started.append((a, kw)))
    r = client.post('/api/phone/offer', json={'type': 'offer', 'sdp': 'v=0 m=video', 'd': 1.6, 'f_mm': 26})
    assert r.status_code == 200 and r.json()['type'] == 'answer' and r.json()['sdp'] == 'v=0 answer'
    (run_id, src, fps, d, fy, rt), kw = started[0]
    assert run_id == r.json()['run_id'] and src is got['source'] and (fps, d, fy, rt) == (20., 1.6, None, False)
    assert got['overlay_run_id'] == run_id and got['overlay_alive']()
    opts = kw['opts']
    assert opts.speed is got['speed'] and (opts.lens, opts.f_mm, opts.crop, opts.auto_focal) == ('mm', 26., 'full', False)
    monkeypatch.setattr(web.JOB, 'status', {'state': 'running', 'run_id': run_id})
    assert got['alive']()
    monkeypatch.setattr(web.JOB, 'status', {'state': 'stopped', 'run_id': run_id})
    assert not got['alive']()


@pytest.mark.parametrize('body', [
    {'type': 'offer', 'sdp': 'v=0', 'd': 1.6},                            # no focal length
    {'type': 'offer', 'sdp': 'v=0', 'd': 9, 'f_mm': 26},                  # camera 9 m behind the bumper
    {'type': 'answer', 'sdp': 'v=0', 'd': 1.6, 'f_mm': 26},
])
def test_phone_offer_checks_its_settings(client, body):
    assert client.post('/api/phone/offer', json=body).status_code == 422


def test_phone_page_is_served(client):
    r = client.get('/phone')
    assert r.status_code == 200 and 'getUserMedia' in client.get('/ui/phone.js').text and 'phone.js' in r.text


def test_phone_frames_and_gps_over_a_websocket(client, monkeypatch):
    """When WebRTC cannot get through (4G, VPN): JPEG frames and GPS fixes on the page's own HTTPS connection."""
    import cv2
    import numpy as np
    started = []

    def fake_start(*a, **kw):   # as Job.start: the new run is 'loading' at once
        started.append((a, kw))
        web.JOB.status = {'state': 'loading', 'run_id': a[0]}
    monkeypatch.setattr(web.JOB, 'start', fake_start)
    monkeypatch.setattr(web.JOB, 'status', {'state': 'idle'})
    with client.websocket_connect('/api/phone/ws?d=1.6&f_mm=26') as w:
        run_id = w.receive_json()['run_id']
        (rid, src, fps, d, fy, rt), kw = started[0]
        assert rid == run_id and (fps, d, fy, rt) == (20., 1.6, None, False) and kw['opts'].f_mm == 26.
        jpeg = cv2.imencode('.jpg', np.full((360, 640, 3), 90, np.uint8))[1].tobytes()
        w.send_bytes(jpeg)
        assert w.receive_json() == {'ack': 1}   # the page sends the next frame only after this: no queue builds up
        assert src.received == 1 and src.size == (640, 360)
        w.send_text(json.dumps(dict(speed=20., lat=10., lon=106., acc=5.)))
        w.send_bytes(b'not a jpeg')
        assert w.receive_json() == {'ack': 2}   # a bad frame is skipped, the stream goes on
        assert src.received == 1 and kw['opts'].speed.count == 1
        web.JOB.overlay = (run_id, 7, {'lane': None, 'lead': {'u': .5, 'v': .6, 'dist_m': 30., 'close': False}})
        assert w.receive_json() == {'overlay': {'frame': 7, 'lane': None, 'lead': {'u': .5, 'v': .6, 'dist_m': 30., 'close': False}}}
    assert src.closed


def test_phone_websocket_checks_its_settings(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e, client.websocket_connect('/api/phone/ws?d=1.6') as w:
        w.receive_json()
    assert e.value.code == 1008


def test_phone_websocket_closes_when_the_run_is_stopped(client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    monkeypatch.setattr(web.JOB, 'start', lambda *a, **kw: setattr(web.JOB, 'status', {'state': 'loading', 'run_id': a[0]}))
    monkeypatch.setattr(web.JOB, 'status', {'state': 'idle'})
    with client.websocket_connect('/api/phone/ws?d=1.6&f_mm=26') as w:
        run_id = w.receive_json()['run_id']
        web.JOB.status = {'state': 'stopped', 'run_id': run_id}   # POST /api/stop, the run saved
        with pytest.raises(WebSocketDisconnect):
            w.receive_json()


def test_bench_page_and_its_runtime_files(client, tmp_path, monkeypatch):
    """/bench: runs gr14VinAI in the phone's browser (onnxruntime-web, WebGPU); files come from models/ (not in git)."""
    (tmp_path / 'ort-web').mkdir()
    (tmp_path / 'ort-web' / 'ort.webgpu.min.js').write_text('var ort = {};')
    (tmp_path / 'ort-web' / 'ort-wasm-simd-threaded.asyncify.wasm').write_bytes(b'\0asm')
    (tmp_path / 'gr14VinAI.onnx').write_bytes(b'onnx')
    monkeypatch.setattr(web, 'ORT_WEB', tmp_path / 'ort-web')
    monkeypatch.setattr(web, 'MODEL_FILE', tmp_path / 'gr14VinAI.onnx')
    r = client.get('/bench')
    assert r.status_code == 200 and 'bench.js' in r.text
    assert "'wasm-unsafe-eval'" in r.headers['content-security-policy']                 # WebAssembly, only here
    assert "'wasm-unsafe-eval'" in client.get('/phone').headers['content-security-policy']   # runs the model on the phone
    assert "'wasm-unsafe-eval'" not in client.get('/app').headers['content-security-policy']
    js = client.get('/ortweb/ort.webgpu.min.js')
    assert js.status_code == 200 and js.headers['content-type'].startswith('text/javascript')
    assert client.get('/ortweb/ort-wasm-simd-threaded.asyncify.wasm').headers['content-type'] == 'application/wasm'
    assert client.get('/ortweb/gr14VinAI.onnx').content == b'onnx'
    (tmp_path / 'gr14VinAI.fp32.onnx').write_bytes(b'fp32')   # for WebGPU devices without f16 shaders
    assert client.get('/ortweb/gr14VinAI.fp32.onnx').content == b'fp32'
    (tmp_path / 'gr14VinAI.mixed.onnx').write_bytes(b'mixed')   # f16, L2 norm in f32
    assert client.get('/ortweb/gr14VinAI.mixed.onnx').content == b'mixed'
    assert client.get('/ortweb/../gr14VinAI.onnx').status_code == 404
    assert client.get('/ortweb/secret.txt').status_code == 404


def test_bench_results_are_logged(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger='roadwatch.web'):
        assert client.post('/api/bench/result', json={'ep': 'webgpu', 'p50_ms': 12.5}).json() == {'logged': True}
    assert any('bench result' in r.message and '"p50_ms": 12.5' in r.message for r in caplog.records)
    assert json.loads((web.JOB.runs / 'bench.jsonl').read_text().splitlines()[-1])['p50_ms'] == 12.5
    assert client.post('/api/bench/result', content=b'x' * 70000).status_code == 413
