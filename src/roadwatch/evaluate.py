"""Evaluation (spec 5.2, 5.5, 5.6): label matching, B-vs-baseline metrics at the audio_plan level, latency.

Matching rule: compatible hazard type, same object, inside the time window; each alert goes to at most one
event (uncaught-at-this-level first, then severity, t_start, event_id); every alert is exactly one of
first_match / repeated / unmatched. Recall counts every must_alert event, degraded misses included.
Sessions with unknown or poor video-GPS sync, or simulated speed, stay out of the main metrics (5.1), and every
run on a test_* split is written to a ledger the report must publish in full (5.5).
"""

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .contracts.base import canonical_json, read_record
from .contracts.streams import (
    AlertDecision,
    AudioEvent,
    AudioPlan,
    DecisionInput,
    DecisionTrace,
    EventLabel,
    FrameMeta,
    Measurement,
    RunManifest,
    SessionManifest,
)
from .detect import iou
from .rerun import load_manifest

LEVEL = {"info": 0, "warning": 1, "emergency": 2}
HAZARD_OF = {"info": "tailgating", "warning": "tailgating", "emergency": "collision_risk"}
SEVERITY = {"collision_risk": 0, "tailgating": 1}


@dataclass(frozen=True)
class AlertView:
    alert_id: str
    kind: str  # info | warning | emergency
    t_s: float  # when the phrase started (audio_plan)
    identity: int | None  # lead identity at the trigger frame


@dataclass
class MatchResult:
    groups: dict[str, str] = field(default_factory=dict)
    assigned: dict[str, str] = field(default_factory=dict)
    caught: set[str] = field(default_factory=set)
    object_unresolved: set[str] = field(default_factory=set)
    must_alert: set[str] = field(default_factory=set)
    lead_s: dict[str, float] = field(default_factory=dict)  # first matches: event start minus alert start

    @property
    def recall(self) -> float | None:
        return len(self.caught) / len(self.must_alert) if self.must_alert else None


def _window(e: EventLabel, lead_max_s: float, max_late_s: float) -> tuple[float, float]:
    end = e.t_start_s + max_late_s if e.type == "collision_risk" else e.t_end_s
    return e.t_start_s - lead_max_s, end


def match(
    alerts: list[AlertView],
    labels: list[EventLabel],
    identity_at_key: dict[str, int | None],
    lead_max_s: float,
    max_late_s: float,
) -> MatchResult:
    r = MatchResult(must_alert={e.event_id for e in labels if e.expect == "must_alert"})
    levels_seen: dict[str, set[str]] = {}
    for a in sorted(alerts, key=lambda x: (x.t_s, x.alert_id)):
        hazard = HAZARD_OF[a.kind]
        timed = [
            e
            for e in labels
            if e.expect == "must_alert"
            and e.type == hazard
            and _window(e, lead_max_s, max_late_s)[0] <= a.t_s <= _window(e, lead_max_s, max_late_s)[1]
        ]
        same_obj = [e for e in timed if e.target is None or identity_at_key.get(e.event_id) == a.identity]
        if not same_obj:
            r.groups[a.alert_id] = "unmatched"
            if timed:
                r.object_unresolved.add(a.alert_id)
            continue
        ev = min(
            same_obj,
            key=lambda e: (a.kind in levels_seen.get(e.event_id, set()), SEVERITY[e.type], e.t_start_s, e.event_id),
        )
        seen = levels_seen.setdefault(ev.event_id, set())
        r.groups[a.alert_id] = "repeated" if a.kind in seen else "first_match"
        if a.kind not in seen:
            r.lead_s[a.alert_id] = ev.t_start_s - a.t_s
        seen.add(a.kind)
        r.assigned[a.alert_id] = ev.event_id
        if LEVEL[a.kind] >= LEVEL[ev.min_level]:
            r.caught.add(ev.event_id)
    return r


# --- reading runs -------------------------------------------------------------------------------


def _read(run_dir: Path, name: str, model) -> list:
    path = Path(run_dir) / f"{name}.jsonl"
    return [read_record(x, model) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def _inputs_dir(run_dir: Path) -> Path:
    """Where a run's frames, measurements and journal are: its own folder, or, for a rerun-B result (outputs
    only, spec 5.3), the folder of its source run, which rerun-B puts next to it."""
    m = load_manifest(run_dir)
    if m.mode != "rerun-B":
        return Path(run_dir)
    src = Path(run_dir).parent / str(m.source_run_id)
    if not src.is_dir():
        raise FileNotFoundError(f"{Path(run_dir).name} is a rerun-B result; its source run {m.source_run_id} must sit next to it")
    return src


def _trigger_measurements(run_dir: Path) -> tuple[dict[int, Measurement], list[DecisionInput]]:
    meas = {m.seq: m for m in _read(run_dir, "measurements", Measurement)}
    return meas, _read(run_dir, "decision_inputs", DecisionInput)


def alert_views(run_dir: Path, arbiter: str) -> list[AlertView]:
    meas, journal = _trigger_measurements(_inputs_dir(run_dir))
    alerts = {a.alert_id: a for a in _read(run_dir, "alerts", AlertDecision) if a.arbiter == arbiter}
    out = []
    for p in _read(run_dir, "audio_plan", AudioPlan):
        a = alerts.get(p.alert_id)
        if p.outcome != "started" or a is None or a.cls != "hazard":
            continue
        ident = None
        inp = journal[a.trigger.input_seq]
        if inp.kind == "measurement":
            ident = meas[inp.ref.seq].lead.identity_id
        out.append(AlertView(a.alert_id, a.kind, p.t_ns / 1e9, ident))
    return out


def identities_at_key_frames(run_dir: Path, labels: list[EventLabel], tau: float) -> dict[str, int | None]:
    by_frame = {m.frame_idx: m for m in _read(run_dir, "measurements", Measurement) if m.frame_idx is not None}
    out: dict[str, int | None] = {}
    for e in labels:
        if e.target is None:
            continue
        m = by_frame.get(e.target.key_frame_idx)
        ok = (
            m is not None and m.lead.status == "ok" and iou(np.array(m.lead.bbox_px), np.array(e.target.bbox_px)) >= tau
        )
        out[e.event_id] = m.lead.identity_id if ok else None
    return out


_CAP_REASONS = ("observation_", "mount_", "speed_lost", "measurement_gap", "system_fault", "low_rate")
_NEVER_OFF_FOR = {"cap_ttc": {"speed_lost"}, "cap_distance": {"low_rate"}}  # spec 3.4: not a cause for that one


def miss_breakdown(run_dir: Path, labels: list[EventLabel], caught: set[str]) -> dict:
    """Why were missed events missed (5.2)? Capability on during the whole event, or off at some point; an
    event missed while degraded counts once under every reason seen while its capability was off."""
    # ponytail: a trace carries the reasons of both capabilities in one `why` list; the ones that can never
    # switch this capability off are dropped. Split the reasons per capability in the trace if this gets vague.
    traces = [t for t in _read(run_dir, "decisions", DecisionTrace) if t.arbiter == "B"]
    out: dict = {"missed_while_capable": 0, "missed_while_degraded": 0, "degraded_reasons": {}}
    for e in labels:
        if e.expect != "must_alert" or e.event_id in caught:
            continue
        cap = "cap_ttc" if e.type == "collision_risk" else "cap_distance"
        off = [t for t in traces if e.t_start_s <= t.t_ns / 1e9 <= e.t_end_s and getattr(t, cap) == "off"]
        out["missed_while_degraded" if off else "missed_while_capable"] += 1
        reasons = {w for t in off for w in t.why if w.startswith(_CAP_REASONS)} - _NEVER_OFF_FOR[cap]
        for reason in sorted(reasons):
            out["degraded_reasons"][reason] = out["degraded_reasons"].get(reason, 0) + 1
    return out


def _perceived_delays(run_dir: Path) -> dict[str, list[float]]:
    """B hazard start minus the moment the raw (baseline) condition became true in that stretch."""
    traces = [t for t in _read(run_dir, "decisions", DecisionTrace) if t.arbiter == "baseline"]
    rises = {"warning": [], "emergency": []}
    prev = {"warning": "OK", "emergency": "OK"}
    for t in traces:
        for kind, state in (("warning", t.distance_state), ("emergency", t.emergency_state)):
            if state == "VIOLATING" and prev[kind] == "OK":
                rises[kind].append(t.t_ns)
            prev[kind] = state
    out = {"warning": [], "emergency": []}
    for a in alert_views(run_dir, "B"):
        if a.kind in rises:
            before = [r for r in rises[a.kind] if r <= a.t_s * 1e9]
            if before:
                out[a.kind].append((a.t_s * 1e9 - before[-1]) / 1e6)
    return out


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    v = float(np.percentile(np.array(xs, dtype=float), q))
    return None if math.isinf(v) else v


def _spread(xs: list[float]) -> dict:
    return {"n": len(xs), "p50": _pct(xs, 50), "min": min(xs, default=None), "max": max(xs, default=None)}


def _delay_stats(delays: dict[str, list[float]]) -> dict:
    return {k: {"n": len(v), "p50": _pct(v, 50), "p95": _pct(v, 95)} for k, v in delays.items()}


# spec 5.5 step 5: what a published figure is tied to, copied from the run manifest
_PROVENANCE = (
    "config_sha256",
    "approval_id",
    "code_commit",
    "code_dirty",
    "model_sha256",
    "ort_version",
    "contracts_version",
    "inputs",
)


def _evaluate(run_dir: Path, labels: list[EventLabel], lead_max_s: float, max_late_s: float, tau: float):
    """The report of one run, plus the raw samples a dataset report has to pool (lead times, perceived delays)."""
    ids = identities_at_key_frames(_inputs_dir(run_dir), labels, tau)
    frames = _read(_inputs_dir(run_dir), "frames", FrameMeta)
    hours = max((frames[-1].t_ns if frames else 0) / 3.6e12, 1e-9)
    manifest = load_manifest(run_dir)
    congestion = [e for e in labels if e.type == "congestion"]
    report: dict = {
        "run_id": Path(run_dir).name,
        "session_id": manifest.session_id,
        "flags": manifest.flags,  # proposed_config etc.: the report must leave such runs out (3.10)
        "provenance": {k: getattr(manifest, k) for k in _PROVENANCE},
        "hours": hours,
        "events_must_alert": sum(e.expect == "must_alert" for e in labels),
    }
    raw: dict = {"lead_s": {}, "delays": _perceived_delays(run_dir)}
    for arb in ("B", "baseline"):
        views = alert_views(run_dir, arb)
        r = match(views, labels, ids, lead_max_s, max_late_s)
        groups = list(r.groups.values())
        decided = {a.alert_id: a for a in _read(run_dir, "alerts", AlertDecision) if a.arbiter == arb}
        hazards = {k for k, a in decided.items() if a.cls == "hazard"}
        plan = Counter(p.outcome for p in _read(run_dir, "audio_plan", AudioPlan) if p.alert_id in hazards)
        raw["lead_s"][arb] = list(r.lead_s.values())
        report[arb] = {
            "unmatched": groups.count("unmatched"),
            "repeated": groups.count("repeated"),
            "first_match": groups.count("first_match"),
            "recall": r.recall,
            "caught": sorted(r.caught),
            "object_unresolved": len(r.object_unresolved),
            "alerts_started": len(views),
            "alerts_per_hour": len(views) / hours,
            "status_msgs_per_hour": (len(decided) - len(hazards)) / hours,
            "in_congestion": sum(any(e.t_start_s <= a.t_s <= e.t_end_s for e in congestion) for a in views),
            "lead_time_s": _spread(raw["lead_s"][arb]),
            "decided_hazards": len(hazards),  # decision layer; plan_outcomes says what the arbiter did with them
            "plan_outcomes": {k: plan[k] for k in ("started", "preempted", "cancelled", "expired")},
        }
        if arb == "B":
            report[arb]["misses"] = miss_breakdown(run_dir, labels, r.caught)
            report[arb]["perceived_delay_ms"] = _delay_stats(raw["delays"])
    report["events_differ"] = sorted(set(report["B"]["caught"]) ^ set(report["baseline"]["caught"]))
    return report, raw


def evaluate_run(run_dir: Path, labels: list[EventLabel], lead_max_s: float, max_late_s: float, tau: float) -> dict:
    return _evaluate(run_dir, labels, lead_max_s, max_late_s, tau)[0]


# --- dataset level (5.1, 5.5): which sessions count, and the ledger of test runs ---------------------

_SUMMED = ("unmatched", "repeated", "first_match", "object_unresolved", "alerts_started", "in_congestion", "decided_hazards")


def exclusion_reasons(session: SessionManifest, max_sync_uncertainty_ms: float) -> list[str]:
    """Spec 5.1: sessions kept out of the main metrics; they are still evaluated and reported apart."""
    reasons = []
    if session.gps_offset_uncertainty_ms is None:
        reasons.append("sync_uncertainty_unknown")
    elif session.gps_offset_uncertainty_ms > max_sync_uncertainty_ms:
        reasons.append("sync_uncertainty_above_target")
    if session.speed_source == "simulated":
        reasons.append("speed_simulated")
    return reasons


def evaluate_dataset(
    runs: list[tuple[Path, SessionManifest]],
    labels: list[EventLabel],
    lead_max_s: float,
    max_late_s: float,
    tau: float,
    max_sync_uncertainty_ms: float,
) -> dict:
    """Main metrics over the runs whose session qualifies (5.1); a label belongs to the run whose session_id is
    its clip_id. `max_sync_uncertainty_ms` is a parameter because the 0.5 s of spec 5.1 is still a proposal."""
    per_run, excluded, pooled = [], [], []
    for run_dir, session in runs:
        if load_manifest(run_dir).session_id != session.session_id:
            raise ValueError(f"{Path(run_dir).name} was not made from session {session.session_id}")
        mine = [e for e in labels if e.clip_id == session.session_id]
        report, raw = _evaluate(run_dir, mine, lead_max_s, max_late_s, tau)
        why = exclusion_reasons(session, max_sync_uncertainty_ms)
        report.update(split=session.split, excluded=why)
        if why:
            excluded.append(report)
        else:
            per_run.append(report)
            pooled.append(raw)
    hours = sum(r["hours"] for r in per_run)
    must = sum(r["events_must_alert"] for r in per_run)
    main: dict = {"runs": len(per_run), "hours": hours, "events_must_alert": must}
    for arb in ("B", "baseline"):
        total = {k: sum(r[arb][k] for r in per_run) for k in _SUMMED}
        caught = sum(len(r[arb]["caught"]) for r in per_run)
        leads = [x for raw in pooled for x in raw["lead_s"][arb]]
        main[arb] = {
            **total,
            "caught_events": caught,
            "recall": caught / must if must else None,
            "alerts_per_hour": total["alerts_started"] / hours if hours else None,
            "lead_time_s": _spread(leads),
        }
    misses = [r["B"]["misses"] for r in per_run]
    main["B"]["misses"] = {
        "missed_while_capable": sum(m["missed_while_capable"] for m in misses),
        "missed_while_degraded": sum(m["missed_while_degraded"] for m in misses),
        "degraded_reasons": dict(sum((Counter(m["degraded_reasons"]) for m in misses), Counter())),
    }
    main["B"]["perceived_delay_ms"] = _delay_stats(
        {kind: [x for raw in pooled for x in raw["delays"][kind]] for kind in ("warning", "emergency")}
    )
    base = main["baseline"]["unmatched"]
    main["unmatched_reduction"] = 1 - main["B"]["unmatched"] / base if base else None  # target 50 % (OQ-A1)
    params = dict(lead_max_s=lead_max_s, max_late_s=max_late_s, tau=tau, max_sync_uncertainty_ms=max_sync_uncertainty_ms)
    # a label whose clip_id matches no run counts nowhere (a typo would quietly shrink the event count)
    orphans = sorted({e.clip_id for e in labels} - {s.session_id for _, s in runs})
    return {"params": params, "main": main, "per_run": per_run, "excluded": excluded, "labels_without_run": orphans}


def log_test_run(ledger: Path, manifest: RunManifest | None, session: SessionManifest, error: str | None = None) -> None:
    """Spec 5.5: every run on a test_* split is appended; the report publishes them all, never the best one.

    An attempt that failed before finishing has no manifest: it is recorded with null fields and its error.
    """
    if not session.split.startswith("test_"):
        return
    row = {k: getattr(manifest, k, None) for k in _LEDGER_FIELDS}
    row.update(split=session.split, session_id=session.session_id, error=error)
    Path(ledger).parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(canonical_json(row) + "\n")


_LEDGER_FIELDS = (
    "run_id",
    "session_id",
    "mode",
    "created_utc",
    "config_sha256",
    "approval_id",
    "code_commit",
    "flags",
    "source_run_id",
)


# --- latency (5.6): the product is B; baseline is reported separately, never pooled ----------------


def latency_report(run_dirs: list[Path], arbiter: str) -> dict:
    if arbiter not in ("B", "baseline"):
        raise ValueError("latency is reported per arbiter (B or baseline), never pooled")
    samples, per_frame, violations = [], [], 0
    for run_dir in run_dirs:
        manifest = load_manifest(run_dir)
        if manifest.mode != "live" or manifest.active_arbiter != arbiter or "proposed_config" in manifest.flags:
            continue  # a trial of a proposed config is never acceptance evidence (spec 3.10)
        if "measurements_input" in manifest.flags:
            continue  # A ran elsewhere: no frame arrival was recorded, so L_alert is undefined for this run
        meas, journal = _trigger_measurements(run_dir)
        arrive = {f.sched_n: f.t_arrive_mono_ns for f in _read(run_dir, "frames", FrameMeta)}
        alerts = {a.alert_id: a for a in _read(run_dir, "alerts", AlertDecision) if a.arbiter == arbiter}
        for ev in _read(run_dir, "audio_events", AudioEvent):
            a = alerts.get(ev.alert_id)
            if a is None or a.cls != "hazard" or a.trigger.source != "frame":
                continue
            m = meas[journal[a.trigger.input_seq].ref.seq]
            if ev.outcome == "dropped_stale":
                violations += 1
                samples.append(math.inf)
            elif ev.outcome == "started":
                samples.append((ev.t_mono_ns - arrive[m.sched_n]) / 1e6)
        perf = Path(run_dir) / "perf.jsonl"
        if perf.exists():
            for line in perf.read_text(encoding="utf-8").splitlines():
                p = json.loads(line)
                per_frame.append((p["t_decision_mono_ns"] - p["t_arrive_mono_ns"]) / 1e6)
    p95 = _pct(samples, 95)
    n = len(samples)
    verdict = "inconclusive" if n < 200 else ("pass" if p95 is not None and p95 < 300 else "fail")
    return {
        "arbiter": arbiter,
        "n": n,
        "p50_ms": _pct(samples, 50),
        "p95_ms": p95 if p95 is not None or not samples else None,
        "dropped_stale": violations,
        "verdict": verdict,
        "per_frame": {"n": len(per_frame), "p50_ms": _pct(per_frame, 50), "p95_ms": _pct(per_frame, 95)},
    }
