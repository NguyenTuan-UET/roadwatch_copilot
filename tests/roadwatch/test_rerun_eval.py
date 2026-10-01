"""rerun-B (spec 5.3-5.4), label matching and metrics (5.2, 5.5), latency report (5.6)."""

import json
from pathlib import Path

import pytest
import yaml

from scripts.roadwatch import sweep_b
from src.roadwatch import configstore as cs
from src.roadwatch.cli import main
from src.roadwatch.contracts.streams import EventLabel, LabelTarget, SessionManifest
from src.roadwatch.evaluate import (
    AlertView,
    evaluate_dataset,
    evaluate_run,
    exclusion_reasons,
    identities_at_key_frames,
    latency_report,
    match,
    miss_breakdown,
)
from src.roadwatch.rerun import compare_stream, load_manifest, load_run_config, rerun_b
from src.roadwatch.runtime import run
from src.roadwatch.source import file_sha256
from tests.roadwatch.decision_harness import Harness
from tests.roadwatch.factories import lead_ok, measurement
from tests.roadwatch.test_runtime import fake_detector, setup, small_config  # noqa: F401 - pytest fixture reuse


def _label(eid, t0, t1, typ="tailgating", expect="must_alert", level="warning", target=True, cause=None, clip="s1"):
    return EventLabel(
        event_id=eid,
        clip_id=clip,
        t_start_s=t0,
        t_end_s=t1,
        type=typ,
        expect=expect,
        min_level=level if expect == "must_alert" else None,
        cause=cause if typ == "collision_risk" else None,
        target=LabelTarget(key_frame_idx=0, bbox_px=(0, 0, 1, 1)) if target else None,
    )


def _alert(aid, kind, t, identity=1):
    return AlertView(alert_id=aid, kind=kind, t_s=t, identity=identity)


IDS = {"E1": 1, "E2": 1, "C1": 1, "X1": None}


def test_each_alert_lands_in_exactly_one_group():
    labels = [_label("E1", 10, 20)]
    alerts = [_alert("a", "warning", 9), _alert("b", "warning", 12), _alert("c", "warning", 40)]
    r = match(alerts, labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.groups == {"a": "first_match", "b": "repeated", "c": "unmatched"}
    assert r.caught == {"E1"} and r.recall == 1.0


def test_level_below_min_level_matches_but_does_not_catch():
    labels = [_label("E1", 10, 20, level="warning")]
    r = match([_alert("a", "info", 11)], labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.groups == {"a": "first_match"} and r.caught == set() and r.recall == 0.0


def test_collision_risk_window_closes_after_max_late():
    labels = [_label("C1", 10, 30, typ="collision_risk", level="emergency", cause="lead_hard_brake")]
    r = match([_alert("late", "emergency", 12)], labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.groups == {"late": "unmatched"} and r.recall == 0.0


def test_wrong_hazard_type_or_object_does_not_match():
    labels = [_label("E1", 10, 20)]
    r = match([_alert("e", "emergency", 12), _alert("o", "warning", 12, identity=9)], labels, IDS, 5, 1)
    assert r.groups == {"e": "unmatched", "o": "unmatched"} and r.object_unresolved == {"o"}


def test_overlapping_events_prefer_uncaught_then_severity():
    labels = [
        _label("E1", 10, 20),
        _label("E2", 12, 22),
        _label("C1", 11, 30, typ="collision_risk", level="emergency", cause="unknown"),
    ]
    alerts = [_alert("w1", "warning", 13), _alert("w2", "warning", 14), _alert("em", "emergency", 11.5)]
    r = match(alerts, labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.assigned == {"w1": "E1", "w2": "E2", "em": "C1"} and r.recall == 1.0


def test_exempt_context_alert_is_unmatched_unless_a_must_alert_event_covers_it():
    labels = [_label("X1", 0, 30, typ="congestion", expect="exempt", target=False), _label("E1", 10, 20)]
    r = match([_alert("in_exempt", "warning", 2), _alert("both", "warning", 11)], labels, IDS, 5, 1)
    assert r.groups == {"in_exempt": "unmatched", "both": "first_match"}


# --- rules of spec 5.2 and report items of 5.5 that had no test (WP-B8) ---------------------------


def test_alert_is_matched_from_lead_max_before_the_event_and_not_earlier():
    labels = [_label("E1", 10, 20)]
    alerts = [_alert("early", "warning", 4.9), _alert("edge", "warning", 5.0)]
    r = match(alerts, labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.groups == {"early": "unmatched", "edge": "first_match"}


def test_event_without_a_target_matches_whatever_the_lead_is():
    labels = [_label("E1", 10, 20, target=False)]
    r = match([_alert("a", "warning", 12, identity=42)], labels, {}, lead_max_s=5, max_late_s=1)
    assert r.groups == {"a": "first_match"} and r.object_unresolved == set()


def test_equal_candidates_go_to_the_smaller_event_id():
    labels = [_label("E2", 10, 20), _label("E1", 10, 22)]
    r = match([_alert("a", "warning", 12)], labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.assigned == {"a": "E1"}


def test_lead_time_is_how_long_before_the_event_start_its_first_alert_began():
    labels = [_label("E1", 10, 20), _label("E2", 30, 40)]
    alerts = [_alert("early", "warning", 9), _alert("again", "warning", 12), _alert("late", "warning", 30.5)]
    r = match(alerts, labels, IDS, lead_max_s=5, max_late_s=1)
    assert r.lead_s == {"early": 1.0, "late": -0.5}  # first matches only; negative = after the event began


def test_label_target_is_resolved_by_iou_with_the_lead_box_at_the_key_frame(tmp_path):
    lead = lead_ok(identity_id=5, bbox_px=(100.0, 100.0, 200.0, 200.0))
    recs = [measurement(seq=i, t_ns=i * 100, sched_n=i, frame_idx=i * 3, lead=lead) for i in range(2)]
    (tmp_path / "measurements.jsonl").write_text("".join(r.to_json() + "\n" for r in recs), encoding="utf-8")

    def label(eid, frame, box):
        return _label(eid, 0, 1).model_copy(update={"target": LabelTarget(key_frame_idx=frame, bbox_px=box)})

    labels = [
        label("near", 0, (110, 110, 210, 210)),  # IoU 8100 / 11900 = 0.68
        label("far", 3, (180, 180, 280, 280)),  # IoU 400 / 19600 = 0.02
        label("gone", 7, (100, 100, 200, 200)),  # no measurement for that frame
        _label("any", 0, 1, target=False),  # no target: nothing to resolve
    ]
    assert identities_at_key_frames(tmp_path, labels, tau=0.5) == {"near": 5, "far": None, "gone": None}
    assert identities_at_key_frames(tmp_path, labels, tau=0.7)["near"] is None


def test_missed_events_are_split_into_capable_and_degraded_by_reason(tmp_path):
    """5.2: recall counts every must_alert event; the breakdown says why the missed ones were missed."""
    h = Harness()
    h.run(0, 2000)
    h.run(2000, 4000, obs="unavailable")
    h.run(4000, 7000)
    (tmp_path / "decisions.jsonl").write_text("".join(t.to_json() + "\n" for t in h.traces()), encoding="utf-8")
    labels = [
        _label("blind", 2.5, 3.5, target=False),
        _label("seen", 5.0, 6.0, typ="collision_risk", level="emergency", cause="unknown", target=False),
        _label("caught", 2.5, 3.5, target=False),
    ]
    assert miss_breakdown(tmp_path, labels, caught={"caught"}) == {
        "missed_while_capable": 1,
        "missed_while_degraded": 1,
        "degraded_reasons": {"observation_unavailable": 1},
    }


def test_run_report_says_where_b_and_baseline_differ_and_counts_alerts_in_congestion(setup):  # noqa: F811
    src = run(setup)  # the baseline speaks at 0.1 s, B at 1.6 s (after T_confirm)
    labels = [
        _label("E1", 0.0, 0.5, target=False),
        _label("X1", 1.0, 3.0, typ="congestion", expect="exempt", target=False),
    ]
    rep = evaluate_run(src, labels, lead_max_s=0, max_late_s=1, tau=0.5)
    assert rep["baseline"]["caught"] == ["E1"] and rep["B"]["caught"] == []
    assert rep["events_differ"] == ["E1"]
    assert (rep["B"]["unmatched"], rep["B"]["in_congestion"]) == (1, 1)
    assert (rep["baseline"]["unmatched"], rep["baseline"]["in_congestion"]) == (0, 0)
    assert rep["B"]["plan_outcomes"] == {"started": 1, "preempted": 0, "cancelled": 0, "expired": 0}
    assert rep["B"]["lead_time_s"] == {"n": 0, "p50": None, "min": None, "max": None}
    assert rep["baseline"]["lead_time_s"] == {"n": 1, "p50": -0.1, "min": -0.1, "max": -0.1}


# --- sessions left out of the main metrics, and the ledger of test runs (spec 5.1, 5.5; WP-C4, D-9) ---


def _session(**kw) -> SessionManifest:
    base = dict(
        session_id="s1",
        video_file="clip.avi",
        video_sha256="x",
        gps_file="gps.csv",
        gps_sha256="y",
        video_start_utc_guess_ns=0,
        gps_offset_ms=0.0,
        gps_offset_uncertainty_ms=200.0,
        sync_method="test",
        recv_time_basis="logged",
        speed_source="gps",
        split="dev",
    )
    return SessionManifest(**{**base, **kw})


@pytest.mark.parametrize(
    "fields, want",
    [
        ({}, []),
        ({"gps_offset_uncertainty_ms": 500.0}, []),  # at the target: still in
        ({"gps_offset_uncertainty_ms": None}, ["sync_uncertainty_unknown"]),  # null is not "0 ms"
        ({"gps_offset_uncertainty_ms": 800.0}, ["sync_uncertainty_above_target"]),
        ({"speed_source": "simulated"}, ["speed_simulated"]),
        ({"gps_offset_uncertainty_ms": None, "speed_source": "simulated"}, ["sync_uncertainty_unknown", "speed_simulated"]),
    ],
)
def test_sessions_with_poor_sync_or_simulated_speed_are_named_for_exclusion(fields, want):
    assert exclusion_reasons(_session(**fields), max_sync_uncertainty_ms=500) == want


def test_dataset_report_keeps_excluded_sessions_out_of_the_main_metrics_but_reports_them(setup, tmp_path, capsys):  # noqa: F811
    s1 = setup.session  # its gps_offset_uncertainty_ms was never measured: null
    s2 = s1.model_copy(update={"session_id": "s2", "gps_offset_uncertainty_ms": 200.0})
    poor = run(setup)
    setup.session = s2
    good = run(setup)
    labels = [_label("E1", 0.0, 3.0, target=False, clip="s1"), _label("E2", 0.0, 3.0, target=False, clip="s2")]
    labels.append(_label("E3", 0.0, 3.0, target=False, clip="s3"))  # a clip_id no run was made from, e.g. a typo
    rep = evaluate_dataset([(poor, s1), (good, s2)], labels, lead_max_s=0, max_late_s=1, tau=0.5, max_sync_uncertainty_ms=500)
    assert rep["labels_without_run"] == ["s3"]  # such labels count nowhere: the report has to say so
    assert [r["session_id"] for r in rep["per_run"]] == ["s2"]
    assert [(r["session_id"], r["excluded"]) for r in rep["excluded"]] == [("s1", ["sync_uncertainty_unknown"])]
    assert rep["excluded"][0]["B"]["first_match"] == 1  # still evaluated, only kept apart
    main_ = rep["main"]
    assert (main_["runs"], main_["events_must_alert"]) == (1, 1)
    assert (main_["B"]["first_match"], main_["B"]["unmatched"], main_["B"]["recall"]) == (1, 0, 1.0)
    assert main_["unmatched_reduction"] is None  # the baseline has no unmatched alert to reduce

    files = {}
    for name, session in (("s1", s1), ("s2", s2)):
        files[name] = tmp_path / f"{name}.json"
        files[name].write_text(session.model_dump_json(), encoding="utf-8")
    label_file = tmp_path / "labels.jsonl"
    label_file.write_text("".join(e.model_dump_json() + "\n" for e in labels), encoding="utf-8")
    args = ["eval", str(poor), str(good), "--labels", str(label_file), "--lead-max-s", "0", "--max-late-s", "1"]
    args += ["--tau", "0.5", "--sessions", str(files["s1"]), str(files["s2"]), "--max-sync-uncertainty-ms", "500"]
    capsys.readouterr()
    assert main(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out.pop("labels_sha256") == file_sha256(label_file)  # the label version the figures were scored against
    assert out == json.loads(json.dumps(rep))


def test_cli_run_records_every_run_on_a_test_split_in_the_ledger(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    monkeypatch.setattr("src.roadwatch.runtime._make_detector", lambda cfg: fake_detector)
    ledger = tmp_path / "eval" / "test_runs.jsonl"

    def cli_run(split):
        path = tmp_path / f"{split}.json"
        path.write_text(setup.session.model_copy(update={"split": split}).model_dump_json(), encoding="utf-8")
        args = ["run", "--session", str(path), "--root", str(setup.config_root), "--out", str(tmp_path / "runs")]
        assert main([*args, "--test-ledger", str(ledger)]) == 0
        return Path(capsys.readouterr().out.strip().splitlines()[-1]).name

    cli_run("dev")
    assert not ledger.exists()  # dev runs are not test evidence
    first, second = cli_run("test_small"), cli_run("test_small")
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
    assert [(r["run_id"], r["split"], r["session_id"]) for r in rows] == [
        (first, "test_small", "s1"),
        (second, "test_small", "s1"),  # a second run cannot hide: the report must publish both
    ]
    assert rows[0]["config_sha256"] and rows[0]["approval_id"] and rows[0]["mode"] == "replay"
    assert rows[0]["error"] is None

    def broken(cfg):
        raise RuntimeError("model file unreadable")

    monkeypatch.setattr("src.roadwatch.runtime._make_detector", broken)
    with pytest.raises(RuntimeError):
        cli_run("test_small")
    failed = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])  # a failed attempt is recorded too
    assert (failed["run_id"], failed["split"], failed["session_id"]) == (None, "test_small", "s1")
    assert failed["error"] == "RuntimeError: model file unreadable"


def test_cli_rerun_b_refuses_another_config_on_a_run_recorded_as_a_test_run(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    """5.5: B is tuned with rerun-B on dev only. A test run is still rerun with its own config (AC-M10)."""
    monkeypatch.setattr("src.roadwatch.runtime._make_detector", lambda cfg: fake_detector)
    ledger = ["--test-ledger", str(tmp_path / "eval" / "test_runs.jsonl")]
    runs = {}
    for split in ("dev", "test_small"):
        path = tmp_path / f"{split}.json"
        path.write_text(setup.session.model_copy(update={"split": split}).model_dump_json(), encoding="utf-8")
        args = ["run", "--session", str(path), "--root", str(setup.config_root), "--out", str(tmp_path / "runs")]
        assert main([*args, *ledger]) == 0
        runs[split] = capsys.readouterr().out.strip().splitlines()[-1]
    cfg = load_run_config(Path(runs["dev"]))
    slower = cfg.model_copy(update={"dispatch": cfg.dispatch.model_copy(update={"t_confirm_ms": 3000})})
    tried = tmp_path / "slower.yaml"
    tried.write_text(yaml.safe_dump(slower.model_dump(mode="json")), encoding="utf-8")
    assert main(["rerun-b", runs["dev"], "--config", str(tried), *ledger]) == 0
    capsys.readouterr()
    assert main(["rerun-b", runs["test_small"], "--config", str(tried), *ledger]) == 2
    assert "dev only" in capsys.readouterr().err
    assert main(["rerun-b", runs["test_small"], "--verify", *ledger]) == 0


# --- rerun-B ------------------------------------------------------------------------------------


def test_rerun_b_reproduces_a_replay_run_exactly(setup):  # noqa: F811
    src = run(setup)
    _, same = rerun_b(src, verify=True)
    assert same is True


def test_rerun_b_with_changed_b_config_differs_and_says_where(setup):  # noqa: F811
    src = run(setup)
    cfg = load_run_config(src)
    slower = cfg.model_copy(update={"dispatch": cfg.dispatch.model_copy(update={"t_confirm_ms": 3000})})
    out_dir, same = rerun_b(src, cfg=slower, verify=True)
    assert same is False
    assert json.loads((out_dir / "run_manifest.json").read_text(encoding="utf-8"))["source_run_id"] == src.name


def test_rerun_b_output_is_scored_against_labels_with_the_inputs_of_its_source_run(setup):  # noqa: F811
    """WP-B3 tunes B with rerun-B: a rerun folder holds only B's outputs (5.3), the frames and measurements
    needed for matching are those of the run it was made from."""
    src = run(setup)  # B warns at 1.6 s
    cfg = load_run_config(src)
    slower = cfg.model_copy(update={"dispatch": cfg.dispatch.model_copy(update={"t_confirm_ms": 3000})})
    rerun, _ = rerun_b(src, cfg=slower)  # B warns at 3.1 s
    labels = [_label("E1", 0.0, 2.0, target=False)]
    before = evaluate_run(src, labels, lead_max_s=0, max_late_s=1, tau=0.5)
    after = evaluate_run(rerun, labels, lead_max_s=0, max_late_s=1, tau=0.5)
    assert (before["B"]["caught"], before["B"]["unmatched"]) == (["E1"], 0)
    assert (after["B"]["caught"], after["B"]["unmatched"]) == ([], 1)
    assert after["baseline"]["caught"] == ["E1"] and after["hours"] == before["hours"]


def test_run_report_carries_the_hashes_its_figures_are_tied_to(setup):  # noqa: F811
    """5.5 step 5: config, code, model, ONNX Runtime, contracts and input hashes travel with every figure; a
    rerun-B result is tied to the config it was rerun with, not to the one of its source run."""
    src = run(setup)
    cfg, m = load_run_config(src), load_manifest(src)
    slower = cfg.model_copy(update={"dispatch": cfg.dispatch.model_copy(update={"t_confirm_ms": 3000})})
    rerun, _ = rerun_b(src, cfg=slower)
    before = evaluate_run(src, [], lead_max_s=0, max_late_s=1, tau=0.5)["provenance"]
    after = evaluate_run(rerun, [], lead_max_s=0, max_late_s=1, tau=0.5)["provenance"]
    assert before == {
        "config_sha256": cfg.sha256(),
        "approval_id": m.approval_id,
        "code_commit": m.code_commit,
        "code_dirty": m.code_dirty,
        "model_sha256": m.model_sha256,
        "ort_version": m.ort_version,
        "contracts_version": m.contracts_version,
        "inputs": m.inputs,
    }
    assert after == {**before, "config_sha256": slower.sha256(), "approval_id": "proposed"}


def test_sweep_b_scores_every_parameter_value_on_dev_runs_and_leaves_no_rerun_behind(setup, tmp_path, capsys):  # noqa: F811
    """WP-B3: sweep B parameters with rerun-B, on dev only (spec 5.5), without re-running the detector."""
    src = run(setup)  # B warns at 1.6 s with T_confirm 1500 ms
    session = setup.session.model_copy(update={"gps_offset_uncertainty_ms": 200.0})
    labels = [_label("E1", 0.0, 2.0, target=False)]
    grid = sweep_b.parse_grid(["dispatch.t_confirm_ms=1500,3000"])
    assert grid == {"dispatch.t_confirm_ms": [1500, 3000]}
    rows = list(
        sweep_b.sweep([(src, session)], labels, grid, lead_max_s=0, max_late_s=1, tau=0.5, max_sync_uncertainty_ms=500)
    )
    assert [(r["set"], r["B"]["recall"], r["B"]["unmatched"]) for r in rows] == [
        ({"dispatch.t_confirm_ms": 1500}, 1.0, 0),
        ({"dispatch.t_confirm_ms": 3000}, 0.0, 1),  # the warning comes at 3.1 s, after the event
    ]
    assert [r["baseline"]["recall"] for r in rows] == [1.0, 1.0]  # the baseline has no such parameter
    assert [p.name for p in src.parent.iterdir()] == [src.name]

    session_file, label_file = tmp_path / "s1.json", tmp_path / "labels.jsonl"
    session_file.write_text(session.model_dump_json(), encoding="utf-8")
    label_file.write_text(labels[0].model_dump_json(), encoding="utf-8")
    args = ["--runs", str(src), "--sessions", str(session_file), "--labels", str(label_file), "--tau", "0.5"]
    args += ["--lead-max-s", "0", "--max-late-s", "1", "--max-sync-uncertainty-ms", "500"]
    capsys.readouterr()
    assert sweep_b.main([*args, "--set", "dispatch.t_confirm_ms=1500,3000"]) == 0
    assert [json.loads(x) for x in capsys.readouterr().out.splitlines()] == rows


def test_sweep_b_refuses_test_sessions_and_parameters_that_need_a_replay():
    params = dict(lead_max_s=0, max_late_s=1, tau=0.5, max_sync_uncertainty_ms=500)
    with pytest.raises(ValueError, match="test_small"):
        list(sweep_b.sweep([(Path("unused"), _session(split="test_small"))], [], {"dispatch.h_m": [5.0]}, **params))
    with pytest.raises(ValueError, match="runtime"):
        list(sweep_b.sweep([(Path("unused"), _session())], [], {"runtime.tick_period_ms": [50]}, **params))


def test_rerun_b_reproduces_a_live_run(setup):  # noqa: F811
    setup.mode, setup.play = "live", lambda phrase: None
    src = run(setup)
    assert rerun_b(src, verify=True)[1] is True


# --- latency report (5.6): B only, fewer than 200 samples is not a pass ---------------------------


def test_latency_report_is_inconclusive_below_200_samples(setup):  # noqa: F811
    setup.mode, setup.play = "live", lambda phrase: None
    rep = latency_report([run(setup)], arbiter="B")
    assert rep["n"] == 1 and rep["verdict"] == "inconclusive" and rep["p95_ms"] is not None
    assert rep["per_frame"]["n"] > 10


def test_latency_report_rejects_mixing_arbiters():
    with pytest.raises(ValueError):
        latency_report([], arbiter="both")


def test_compare_reports_first_difference_largest_numeric_gap_and_status_changes():  # spec 5.4
    a = [{"seq": 0, "distance_m": {"value": 40.0, "status": "ok"}}, {"seq": 1, "lead": {"bbox_px": [1, 2, 3, 4]}}]
    b = [{"seq": 0, "distance_m": {"value": 40.5, "status": "ok"}}, {"seq": 1, "lead": {"bbox_px": [1, 2, 3, 6]}}]
    assert compare_stream(a, a) == {
        "records": [2, 2],
        "first_difference": None,
        "max_abs_diff": {},
        "status_changes": 0,
    }
    r = compare_stream(a, b)
    assert r["first_difference"] == "record 0: fields ['distance_m']"
    assert r["max_abs_diff"] == {"distance_m.value": 0.5, "lead.bbox_px": 2}
    b[0]["distance_m"] = {"value": None, "status": "unavailable"}
    assert compare_stream(a, b)["status_changes"] == 1


def test_a_proposed_config_trial_never_counts_as_evidence(setup):  # noqa: F811 - spec 3.10, OQ-B13
    setup.mode, setup.play = "live", (lambda phrase: None)
    plain = run(setup)
    setup.proposed = (cs.propose(setup.config_root, small_config(), "eng"), small_config().sha256())
    trial = run(setup)
    assert latency_report([plain, trial], "B")["n"] == latency_report([plain], "B")["n"] > 0
    assert "proposed_config" in evaluate_run(trial, [], lead_max_s=1, max_late_s=1, tau=0.5)["flags"]
