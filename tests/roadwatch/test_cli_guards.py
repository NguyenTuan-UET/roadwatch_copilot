"""WP-C2 guards around the HITL CLI (D-8, D-11, OQ-B3) and the run check used for AC-M1 (WP-P8)."""

import json

import yaml

from src.roadwatch import configstore as cs
from src.roadwatch.cli import main
from src.roadwatch.runtime import machine_fingerprint, run
from tests.roadwatch.test_runtime import fake_detector, setup, small_config  # noqa: F401 - fixture reuse

ENV = cs.Env(
    code_commit="c1",
    code_dirty=False,
    dataset_manifest_sha256="d",
    model_sha256="m",
    ort_version="1",
    machine_fingerprint=None,
)


def _propose(store, tmp_path, capsys, section, key, value):
    cfg = cs.load_active(store)[0].model_dump(mode="json")
    cfg[section][key] = value
    path = tmp_path / f"{section}-{key}-{value}.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert main(["hitl", "propose", "--root", str(store), "--config", str(path), "--by", "eng"]) == 0
    return capsys.readouterr().out.strip().splitlines()[-1]


def _dataset(tmp_path, split):
    path = tmp_path / f"dataset-{split}.json"
    path.write_text(json.dumps({"sessions": [{"session_id": "s1", "split": split}]}), encoding="utf-8")
    return str(path)


def _report(store, pid, dataset, *runs):
    return main(["hitl", "report", "--root", str(store), "--proposal", pid, "--dataset", dataset, "--runs", *runs])


def test_report_refuses_a_test_split(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: ENV)
    pid = _propose(setup.config_root, tmp_path, capsys, "dispatch", "t_confirm_ms", 2500)
    assert _report(setup.config_root, pid, _dataset(tmp_path, "test_small")) == 2
    assert "test_small" in capsys.readouterr().err
    assert len(list((setup.config_root / "reports").glob("*.json"))) == 1  # only the first config's report


def test_report_on_a_change_to_a_needs_trial_runs_of_that_very_proposal(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: ENV)
    monkeypatch.setattr("src.roadwatch.runtime._make_detector", lambda cfg: fake_detector)
    store, dev = setup.config_root, _dataset(tmp_path, "dev")
    session = tmp_path / "session.json"
    session.write_text(setup.session.model_dump_json(), encoding="utf-8")
    p1 = _propose(store, tmp_path, capsys, "mount", "y_horizon_px", 91.0)
    p2 = _propose(store, tmp_path, capsys, "mount", "y_horizon_px", 92.0)
    assert _report(store, p1, dev) == 2 and "--proposed" in capsys.readouterr().err
    out = str(tmp_path / "runs")
    assert main(["run", "--session", str(session), "--root", str(store), "--out", out, "--proposed", p1]) == 0
    trial = capsys.readouterr().out.strip().splitlines()[-1]
    assert _report(store, p2, dev, trial) == 2  # a trial run of another proposal
    assert _report(store, p1, dev, str(run(setup))) == 2  # a plain run with the active config
    capsys.readouterr()
    assert _report(store, p1, dev, trial) == 0
    assert json.loads(capsys.readouterr().out)["path"] == "replay"


def test_first_config_goes_through_the_cli_without_a_bootstrap_script(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: ENV)
    store, dev, v0 = tmp_path / "configs", _dataset(tmp_path, "dev"), tmp_path / "v0.yaml"
    v0.write_text(yaml.safe_dump(small_config().model_dump(mode="json")), encoding="utf-8")
    assert main(["hitl", "init", "--root", str(store), "--approvers", "po", "eng"]) == 0
    assert main(["hitl", "propose", "--root", str(store), "--config", str(v0), "--by", "eng"]) == 0
    pid = capsys.readouterr().out.strip().splitlines()[-1]
    assert _report(store, pid, dev) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == "bootstrap"
    approve = ["hitl", "approve", "--root", str(store), "--proposal", pid, "--report", report["sha"], "--by"]
    assert main([*approve, "eng"]) == 2  # an approver still cannot approve their own proposal
    capsys.readouterr()
    assert main([*approve, "po"]) == 0
    approval_id = capsys.readouterr().out.strip().splitlines()[-1]
    assert (
        main(["hitl", "activate", "--root", str(store), "--approval", approval_id, "--by", "po", "--dataset", dev]) == 0
    )
    assert cs.load_active(store)[1].approval_id == approval_id


def test_check_run_accepts_a_real_run_and_catches_a_lost_trace(setup, capsys):  # noqa: F811
    run_dir = run(setup)
    assert main(["check-run", str(run_dir)]) == 0
    decisions = run_dir / "decisions.jsonl"
    decisions.write_text("\n".join(decisions.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    assert main(["check-run", str(run_dir)]) == 1
    assert "0 traces" in capsys.readouterr().out


def _manifest(run_dir):
    return json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))


def test_next_run_carries_the_new_approval_and_rollback_brings_the_old_one_back(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: ENV)
    store, dev = setup.config_root, _dataset(tmp_path, "dev")
    first = cs.load_active(store)[1].approval_id
    pid = _propose(store, tmp_path, capsys, "dispatch", "t_confirm_ms", 2500)
    assert _report(store, pid, dev, str(run(setup))) == 0
    sha = json.loads(capsys.readouterr().out)["sha"]
    assert main(["hitl", "approve", "--root", str(store), "--proposal", pid, "--report", sha, "--by", "po"]) == 0
    new = capsys.readouterr().out.strip().splitlines()[-1]
    assert main(["hitl", "activate", "--root", str(store), "--approval", new, "--by", "po", "--dataset", dev]) == 0
    assert _manifest(run(setup))["approval_id"] == new  # AC-M9: the next run is bound to the new approval
    assert main(["hitl", "rollback", "--root", str(store), "--approval", first, "--by", "po"]) == 0
    assert _manifest(run(setup))["approval_id"] == first


def test_report_on_a_live_section_needs_a_live_trial_from_this_machine(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    here = cs.Env(**{**ENV.__dict__, "machine_fingerprint": machine_fingerprint()})
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: here)
    store, dev = setup.config_root, _dataset(tmp_path, "dev")
    pid = _propose(store, tmp_path, capsys, "runtime", "q_log", 20000)  # runtime: [A, live]
    setup.proposed, setup.play = (pid, cs.proposal_config(store, pid).sha256()), (lambda phrase: None)
    replay = str(run(setup))
    setup.mode = "live"
    live = str(run(setup))
    assert _report(store, pid, dev, replay) == 2 and "live check" in capsys.readouterr().err
    elsewhere = cs.Env(**{**ENV.__dict__, "machine_fingerprint": "another-pc"})
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: elsewhere)
    assert _report(store, pid, dev, replay, live) == 2 and "another machine" in capsys.readouterr().err
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: here)
    assert _report(store, pid, dev, replay, live) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == "replay+live" and report["machine_fingerprint"] == machine_fingerprint()
