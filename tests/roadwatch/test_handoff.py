"""Hand-over of B+C (WP-P8, WP-P3, WP-C11): the whole chain on the sample session, through the CLI, in a temporary store.

A's measurements + GPS -> B decisions -> audio plan and sink -> logs -> check-run, rerun-B, compare.
It is also the smoke test for another machine: `python -m pytest tests/roadwatch/test_handoff.py --confcutdir=tests/roadwatch`.
The store, the roles and the config here are test ones (code-rules 6); nothing touches a real `configs/`.
The input is a file read from disk: no camera and no stream from A is involved.
"""

import json
from pathlib import Path

import pytest

from src.roadwatch import configstore as cs
from src.roadwatch.cli import main
from src.roadwatch.contracts.base import CONTRACTS_VERSION, read_record
from src.roadwatch.contracts.streams import AlertDecision, AudioEvent, AudioPlan, DecisionTrace, Measurement
from tests.roadwatch import make_fixtures
from tests.roadwatch.decision_harness import make_config
from tests.roadwatch.test_cli_guards import ENV, _dataset, _manifest, _report

REPO = Path(__file__).parents[2]
SAMPLE = make_fixtures.HANDOFF
SESSION, MEASUREMENTS = str(SAMPLE / "session.json"), str(SAMPLE / "measurements.jsonl")
MVP_1_0_0 = str(SAMPLE / "measurements-mvp-1.0.0.jsonl")  # written before 1.1.0 and kept by hand: lead vehicle only
B_STREAMS = ["--streams", "decision_inputs", "decisions", "alerts", "audio_plan"]


@pytest.fixture
def store(tmp_path, monkeypatch, capsys):
    """A config store with the test config active, built with the HITL commands a person would type."""
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: ENV)
    root, dev, cfg = tmp_path / "configs", _dataset(tmp_path, "dev"), str(SAMPLE / "test-config.yaml")
    assert main(["hitl", "init", "--root", str(root), "--approvers", "po", "eng"]) == 0
    assert main(["hitl", "propose", "--root", str(root), "--config", cfg, "--by", "eng"]) == 0
    pid = capsys.readouterr().out.strip().splitlines()[-1]
    assert _report(root, pid, dev) == 0
    sha = json.loads(capsys.readouterr().out)["sha"]
    assert main(["hitl", "approve", "--root", str(root), "--proposal", pid, "--report", sha, "--by", "po"]) == 0
    approval = capsys.readouterr().out.strip().splitlines()[-1]
    assert main(["hitl", "activate", "--root", str(root), "--approval", approval, "--by", "po", "--dataset", dev]) == 0
    capsys.readouterr()
    return root


def _run(store, tmp_path, capsys, *extra, measurements=MEASUREMENTS, code=0) -> Path:
    out = tmp_path / "runs"
    args = ["run", "--session", SESSION, "--measurements", measurements, "--root", str(store), "--out", str(out)]
    assert main([*args, "--test-ledger", str(tmp_path / "ledger.jsonl"), *extra]) == code
    return Path(capsys.readouterr().out.strip().splitlines()[-1]) if code == 0 else out


def _records(run_dir, stream, model):
    return [read_record(x, model) for x in (run_dir / f"{stream}.jsonl").read_text(encoding="utf-8").splitlines()]


def test_sample_session_is_what_the_generator_writes(tmp_path, monkeypatch):
    """A contract change must be followed by `python -m tests.roadwatch.make_fixtures handoff`."""
    monkeypatch.setattr(make_fixtures, "HANDOFF", tmp_path)
    make_fixtures.handoff()
    for name in ("measurements.jsonl", "gps.csv", "session.json", "dataset.json", "test-config.yaml"):
        assert (tmp_path / name).read_text(encoding="utf-8") == (SAMPLE / name).read_text(encoding="utf-8"), name


def test_b_and_c_run_end_to_end_on_measurements_handed_over_by_a(store, tmp_path, capsys):
    run_dir = _run(store, tmp_path, capsys)
    manifest = _manifest(run_dir)
    assert manifest["mode"] == "replay" and manifest["approval_id"] and manifest["session_id"] == "handoff-sample"
    assert "measurements_input" in manifest["flags"] and manifest["model_sha256"] is None  # A's model is not ours
    assert set(manifest["inputs"]) == {"measurements_sha256", "gps_sha256", "session_manifest_sha256"}
    assert not (run_dir / "frames.jsonl").exists()  # C saw no video: it invents no frame records

    assert main(["check-run", str(run_dir)]) == 0  # every stream valid and linked (contracts, D-7)
    assert "OK" in capsys.readouterr().out

    b = [(a.kind, a.t_decided_ns / 1e9) for a in _records(run_dir, "alerts", AlertDecision) if a.arbiter == "B"]
    assert b == [
        ("warning", 4.5),  # below the 70 m band from 3.0 s, confirmed T_confirm later
        ("emergency", 7.0),  # TTC under the threshold: at once
        ("cap_distance_off", 19.1),  # last GPS sample at 12.1 s: lost at 17.1 s, announced T_notify later
        ("emergency", 20.0),  # speed is lost, the collision warning is not (fail-safe per capability)
        ("recovery", 23.1),  # GPS back at 21.1 s
    ]
    at_20 = [t for t in _records(run_dir, "decisions", DecisionTrace) if t.arbiter == "B" and t.t_ns == 20_000_000_000]
    assert (at_20[-1].cap_distance, at_20[-1].cap_ttc) == ("off", "on")
    plans = [
        (p.alert_id, p.outcome, p.t_ns / 1e9) for p in _records(run_dir, "audio_plan", AudioPlan) if p.arbiter == "B"
    ]
    # priority (3.6): the emergency starts in the very frame that raised it and cuts the lower status phrase
    assert ("B-2", "preempted", 20.0) in plans and ("B-3", "started", 20.0) in plans
    stats = json.loads((run_dir / "run_stats.json").read_text(encoding="utf-8"))
    assert stats["frames"]["read"] is None and stats["frames"]["processed"] == 270  # absent is null, never 0
    assert stats["audio"] == {"commands_issued": 5, "played_successfully": None, "dropped_stale": None}

    rerun = ["rerun-b", str(run_dir), "--verify", "--out", str(tmp_path / "reruns")]
    assert main([*rerun, "--test-ledger", str(tmp_path / "ledger.jsonl")]) == 0  # same journal, same config, same B
    assert "verify: pass" in capsys.readouterr().out
    again = _run(store, tmp_path, capsys)
    assert (
        main(["compare", str(run_dir), str(again), "--streams", "measurements", *B_STREAMS[1:]]) == 0
    )  # same input twice
    capsys.readouterr()


def test_people_and_the_lane_are_read_logged_and_replayed_but_b_says_nothing_about_them(store, tmp_path, capsys):
    """WP-C11: B has no rule for people or the lane yet (OQ-A13, OQ-A14), so none of this data may raise a warning.

    The sample holds what such rules would react to: a person inside the zone with a TTC under the emergency
    threshold, and a drift to 0.3 m of a lane line. The decisions must be those of the 1.0.0 file, which has neither.
    """
    lines = Path(MEASUREMENTS).read_text(encoding="utf-8").splitlines()
    sample = [read_record(x, Measurement, strict=True) for x in lines]
    people = [o for m in sample for o in m.risk_objects if o.kind == "person" and o.zone.inside]
    assert min(o.ttc_s.value for o in people) < make_config().ttc.ttc_emergency_s
    assert min(m.lane.right_m.value for m in sample if m.lane.right_m.usable) < 0.5
    assert {m.lane.status for m in sample} == {"ok", "unreliable"} and any(m.lane.t_ns < m.t_ns for m in sample)

    new = _run(store, tmp_path, capsys)
    logged = _records(new, "measurements", Measurement)
    assert [(m.risk_objects, m.lane) for m in logged] == [(m.risk_objects, m.lane) for m in sample]  # nothing lost
    assert main(["check-run", str(new)]) == 0
    assert main(["rerun-b", str(new), "--verify", "--out", str(tmp_path / "reruns")]) == 0

    old_lines = Path(MVP_1_0_0).read_text(encoding="utf-8").splitlines()
    assert {json.loads(x)["schema_version"] for x in old_lines} == {"1.0.0"} and "risk_objects" not in old_lines[0]
    old = _run(store, tmp_path, capsys, measurements=MVP_1_0_0)  # 4.6: a MINOR never breaks what was written before
    assert main(["check-run", str(old)]) == 0
    assert {m.schema_version for m in _records(old, "measurements", Measurement)} == {CONTRACTS_VERSION}  # C's log
    assert main(["compare", str(old), str(new), *B_STREAMS]) == 0  # same journal, traces, alerts and audio plan
    capsys.readouterr()


def test_measurements_that_break_the_contract_are_refused_before_anything_is_recorded(store, tmp_path, capsys):
    lines = Path(MEASUREMENTS).read_text(encoding="utf-8").splitlines()
    broken = json.loads(lines[1])
    broken["distance_m"] = {
        "value": 0.0,
        "status": "unavailable",
        "sigma": None,
        "reasons": ["no_lead"],
    }  # 0 for missing
    person_as_lead = json.loads(lines[152])  # the frame with the person: listing it under the lead's identity
    person_as_lead["risk_objects"][0]["identity_id"] = person_as_lead["lead"]["identity_id"]
    cases = {
        "zero_for_missing": [lines[0], json.dumps(broken)],
        "seq_gap": [lines[0], lines[2]],
        "lead_listed_twice": [*lines[:152], json.dumps(person_as_lead)],
    }
    for name, rows in cases.items():
        path = tmp_path / f"{name}.jsonl"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        out = _run(store, tmp_path, capsys, measurements=str(path), code=2)
        assert path.name in capsys.readouterr().err and not out.exists(), name


def test_live_with_simulated_audio_logs_the_sink_and_says_it_was_simulated(store, tmp_path, capsys):
    head = tmp_path / "first-6-s.jsonl"  # live runs in real time: keep the warning at 4.5 s, drop the rest
    first = Path(MEASUREMENTS).read_text(encoding="utf-8").splitlines()[:60]
    head.write_text("\n".join(first) + "\n", encoding="utf-8")
    run_dir = _run(store, tmp_path, capsys, "--mode", "live", "--audio", "simulated", measurements=str(head))
    manifest = _manifest(run_dir)
    assert manifest["mode"] == "live" and {"measurements_input", "simulated_audio"} <= set(manifest["flags"])
    assert main(["check-run", str(run_dir)]) == 0
    capsys.readouterr()
    (alert,) = [a for a in _records(run_dir, "alerts", AlertDecision) if a.arbiter == "B"]
    (event,) = _records(run_dir, "audio_events", AudioEvent)
    assert (alert.kind, event.alert_id, event.outcome) == ("warning", alert.alert_id, "started")
    stats = json.loads((run_dir / "run_stats.json").read_text(encoding="utf-8"))
    assert stats["audio"] == {"commands_issued": 1, "played_successfully": None, "dropped_stale": None}
    assert main(["rerun-b", str(run_dir), "--verify", "--out", str(tmp_path / "reruns")]) == 0  # live logs reproduce B
    capsys.readouterr()
    assert main(["perf", str(run_dir)]) == 0  # no frame arrival was recorded: the run gives no latency sample
    assert json.loads(capsys.readouterr().out)["n"] == 0


def test_live_with_the_speaker_refuses_to_start_without_the_phrase_library(store, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # the config's phrase_dir is relative: there is no WAV here
    out = _run(store, tmp_path, capsys, "--mode", "live", code=2)  # --audio speaker is the default: no silent run
    assert "phrase" in capsys.readouterr().err and not out.exists()


def test_the_config_template_is_refused_until_its_todo_values_are_filled(tmp_path, capsys):
    template = REPO / "config" / "proposals" / "v0.yaml"
    assert main(["hitl", "init", "--root", str(tmp_path / "configs"), "--approvers", "po", "eng"]) == 0
    propose = ["hitl", "propose", "--root", str(tmp_path / "configs"), "--config", str(template), "--by", "eng"]
    assert main(propose) == 2
    err = capsys.readouterr().err
    assert "camera.fx_px" in err and "detector.model_sha256" in err  # the error names what is still to be filled
    assert cs.read_pointer(tmp_path / "configs") is None
