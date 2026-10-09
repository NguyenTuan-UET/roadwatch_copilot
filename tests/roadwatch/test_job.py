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

    def __init__(self, w, h, fy, d, model):
        self.K, self.coverage, self.n = np.eye(3), 1.0, 0
        self.cal = type('Cal', (), {'resets': 0})()

    def step(self, y, u, v):
        self.n += 1
        if self.n in self.fail:
            raise RuntimeError('bad frame')
        return Result('calibrated', np.zeros(3), 1.3, 25.0, 0.99, 30.0, 25.0, None, {})


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
