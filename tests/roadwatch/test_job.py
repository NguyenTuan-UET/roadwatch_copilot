import os
import time

from src.roadwatch import job


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
