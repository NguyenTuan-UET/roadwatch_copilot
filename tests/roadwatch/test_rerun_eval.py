"""rerun-B (spec 5.3-5.4), label matching and metrics (5.2, 5.5), latency report (5.6)."""

import json

import pytest

from src.roadwatch.contracts.streams import EventLabel, LabelTarget
from src.roadwatch.evaluate import AlertView, latency_report, match
from src.roadwatch.rerun import load_run_config, rerun_b
from src.roadwatch.runtime import run
from tests.roadwatch.test_runtime import setup  # noqa: F401 - pytest fixture reuse


def _label(eid, t0, t1, typ="tailgating", expect="must_alert", level="warning", target=True, cause=None):
    return EventLabel(
        event_id=eid,
        clip_id="s1",
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
