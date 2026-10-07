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
    assert r.status_code == 200 and r.json()['status'] in ('ok', 'degraded')
    assert r.headers['x-frame-options'] == 'DENY' and 'default-src' in r.headers['content-security-policy']


def test_config_exposes_bt_b_parameters(client):
    c = client.get('/api/config').json()
    assert c['ttc_emergency_s'] == 1.8 and c['phrases']['warning']


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


def test_delete_run_erases_the_upload(client):
    run_id = client.post('/api/runs?name=a.mp4&fps=20&d=1.5', content=b'x').json()['run_id']
    assert client.delete(f'/api/runs/{run_id}').status_code == 200
    assert not (web.JOB.runs / run_id).exists() and client.get('/api/runs').json() == []
    assert client.delete(f'/api/runs/{run_id}').status_code == 404
