"""API of the demo server; the model never runs (Job.start is replaced)."""
import json

import pytest
from fastapi.testclient import TestClient

from src.roadwatch import web


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web.JOB, 'runs', tmp_path)
    started = []

    def fake_start(run_id, video, fps, d, fy, rt, name=None):
        started.append((run_id, video, fps, d, fy, rt))
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


def test_upload_starts_a_run_and_lists_it(client):
    r = client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'\0' * 1000)
    assert r.status_code == 200
    run_id = r.json()['run_id']
    assert client.started[0][2:5] == (20.0, 1.5, None)
    assert [(x['run_id'], x['video']) for x in client.get('/api/runs').json()] == [(run_id, 'a.mp4')]


@pytest.mark.parametrize('query, code', [
    ('name=a.exe&fps=20&d=1.5', 415),       # not a video
    ('name=a.mp4&fps=0&d=1.5', 422),        # fps must be > 0
    ('name=a.mp4&fps=20&d=-1', 422),        # camera->bumper must be >= 0
    ('name=a.mp4&fps=20&d=1.5&fy=-3', 422),
])
def test_upload_rejects_bad_input(client, query, code):
    assert client.post('/api/runs?' + query, content=b'\0' * 10).status_code == code
    assert not client.started


def test_upload_rejects_empty_and_oversized(client, monkeypatch):
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'').status_code == 400
    monkeypatch.setattr(web, 'MAX_UPLOAD', 100)
    assert client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'\0' * 1000).status_code == 413
    assert not client.started and not list(web.JOB.runs.iterdir())


def test_files_cannot_escape_the_run_folder(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'x').json()['run_id']
    assert client.get(f'/api/runs/{run_id}/files/run.json').status_code == 200
    assert client.get(f'/api/runs/{run_id}/files/input.mp4').status_code == 404      # uploads are not served back
    assert client.get('/api/runs/..%2F..%2Fetc/files/run.json').status_code == 404
    assert client.get('/api/phrases/..%2Fx').status_code == 404
    assert client.get('/api/phrases/beep').status_code == 422       # only the three alert levels


def test_delete_run_erases_the_upload(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'x').json()['run_id']
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
    cal = dict(status='calibrated', calibrated=True, fy_px=913, fy_state='đã học', pitch_deg=3.5, yaw_deg=0.8,
               height_m=1.35, coverage=1.0, remounts=0)
    counts = dict(info=0, warning=1, emergency=0)
    LiveStatus.model_validate(dict(
        state='running', run_id='5ec77ceab6a9',
        measure=dict(frame=10, t_s=0.5, ego_kmh=66.0, ttc_s=None, lead=lead, calibration=cal),
        decision=dict(level='warning', say=None, reason='x', threshold_m=55.0, latency_us=7),
        ops=dict(fps=20.0, bad_frames=0, latency=dict(last_ms=14.0, p50_ms=14.2, p95_ms=18.5),
                 raw_onsets=counts, said=counts),
        sample=dict(t_s=0.5, gap_m=42.3, threshold_m=55.0, ttc_s=None), events=[]))


def test_openapi_document_is_up_to_date():
    from scripts.roadwatch.export_api_schema import OUT, document
    assert OUT.read_text(encoding='utf-8') == document(), 'run python -m scripts.roadwatch.export_api_schema'


def test_password_protects_everything_but_health(client, monkeypatch):
    import base64
    monkeypatch.setattr(web, 'PASSWORD', 's3cret')
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
