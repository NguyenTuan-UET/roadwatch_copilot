"""Evaluation (spec 5.2, 5.5, 5.6): label matching, B-vs-baseline metrics at the audio_plan level, latency.

Matching rule: compatible hazard type, same object, inside the time window; each alert goes to at most one
event (uncaught-at-this-level first, then severity, t_start, event_id); every alert is exactly one of
first_match / repeated / unmatched. Recall counts every must_alert event, degraded misses included.
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .contracts.base import read_record
from .contracts.streams import (
    AlertDecision,
    AudioEvent,
    AudioPlan,
    DecisionInput,
    DecisionTrace,
    EventLabel,
    FrameMeta,
    Measurement,
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

    @property
    def recall(self) -> float | None:
        return len(self.caught) / len(self.must_alert) if self.must_alert else None


def _window(e: EventLabel, lead_max_s: float, max_late_s: float) -> tuple[float, float]:
    end = e.t_start_s + max_late_s if e.type == "collision_risk" else e.t_end_s
    return e.t_start_s - lead_max_s, end


def match(alerts: list[AlertView], labels: list[EventLabel], identity_at_key: dict[str, int | None],
          lead_max_s: float, max_late_s: float) -> MatchResult:
    r = MatchResult(must_alert={e.event_id for e in labels if e.expect == "must_alert"})
    levels_seen: dict[str, set[str]] = {}
    for a in sorted(alerts, key=lambda x: (x.t_s, x.alert_id)):
        hazard = HAZARD_OF[a.kind]
        timed = [e for e in labels if e.expect == "must_alert" and e.type == hazard
                 and _window(e, lead_max_s, max_late_s)[0] <= a.t_s <= _window(e, lead_max_s, max_late_s)[1]]
        same_obj = [e for e in timed if e.target is None or identity_at_key.get(e.event_id) == a.identity]
        if not same_obj:
            r.groups[a.alert_id] = "unmatched"
            if timed:
                r.object_unresolved.add(a.alert_id)
            continue
        ev = min(same_obj, key=lambda e: (a.kind in levels_seen.get(e.event_id, set()), SEVERITY[e.type],
                                          e.t_start_s, e.event_id))
        seen = levels_seen.setdefault(ev.event_id, set())
        r.groups[a.alert_id] = "repeated" if a.kind in seen else "first_match"
        seen.add(a.kind)
        r.assigned[a.alert_id] = ev.event_id
        if LEVEL[a.kind] >= LEVEL[ev.min_level]:
            r.caught.add(ev.event_id)
    return r


# --- reading runs -------------------------------------------------------------------------------

def _read(run_dir: Path, name: str, model) -> list:
    path = Path(run_dir) / f"{name}.jsonl"
    return [read_record(x, model) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def _trigger_measurements(run_dir: Path) -> tuple[dict[int, Measurement], list[DecisionInput]]:
    meas = {m.seq: m for m in _read(run_dir, "measurements", Measurement)}
    return meas, _read(run_dir, "decision_inputs", DecisionInput)


def alert_views(run_dir: Path, arbiter: str) -> list[AlertView]:
    meas, journal = _trigger_measurements(run_dir)
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
        ok = m is not None and m.lead.status == "ok" and iou(np.array(m.lead.bbox_px), np.array(e.target.bbox_px)) >= tau
        out[e.event_id] = m.lead.identity_id if ok else None
    return out


def _degraded_misses(run_dir: Path, labels: list[EventLabel], caught: set[str]) -> dict[str, int]:
    """Why were missed events missed? Capability off during the event (by reason) vs fully capable."""
    traces = [t for t in _read(run_dir, "decisions", DecisionTrace) if t.arbiter == "B"]
    out: dict[str, int] = {}
    for e in labels:
        if e.expect != "must_alert" or e.event_id in caught:
            continue
        cap = "cap_ttc" if e.type == "collision_risk" else "cap_distance"
        inside = [t for t in traces if e.t_start_s <= t.t_ns / 1e9 <= e.t_end_s]
        off = [t for t in inside if getattr(t, cap) == "off"]
        key = "missed_while_capable" if not off else "missed_while_degraded"
        out[key] = out.get(key, 0) + 1
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


def evaluate_run(run_dir: Path, labels: list[EventLabel], lead_max_s: float, max_late_s: float, tau: float) -> dict:
    ids = identities_at_key_frames(run_dir, labels, tau)
    frames = _read(run_dir, "frames", FrameMeta)
    hours = max((frames[-1].t_ns if frames else 0) / 3.6e12, 1e-9)
    report: dict = {"run_id": Path(run_dir).name, "hours": hours, "events_must_alert":
                    sum(e.expect == "must_alert" for e in labels)}
    for arb in ("B", "baseline"):
        views = alert_views(run_dir, arb)
        r = match(views, labels, ids, lead_max_s, max_late_s)
        groups = list(r.groups.values())
        statuses = [a for a in _read(run_dir, "alerts", AlertDecision) if a.arbiter == arb and a.cls == "status"]
        report[arb] = {"unmatched": groups.count("unmatched"), "repeated": groups.count("repeated"),
                       "first_match": groups.count("first_match"), "recall": r.recall,
                       "caught": sorted(r.caught), "object_unresolved": len(r.object_unresolved),
                       "alerts_per_hour": len(views) / hours, "status_msgs_per_hour": len(statuses) / hours,
                       "decided_hazards": sum(1 for a in _read(run_dir, "alerts", AlertDecision)
                                              if a.arbiter == arb and a.cls == "hazard")}
        if arb == "B":
            report[arb]["misses"] = _degraded_misses(run_dir, labels, r.caught)
            report[arb]["perceived_delay_ms"] = {k: {"n": len(v), "p50": _pct(v, 50), "p95": _pct(v, 95)}
                                                 for k, v in _perceived_delays(run_dir).items()}
    return report


# --- latency (5.6): the product is B; baseline is reported separately, never pooled ----------------

def latency_report(run_dirs: list[Path], arbiter: str) -> dict:
    if arbiter not in ("B", "baseline"):
        raise ValueError("latency is reported per arbiter (B or baseline), never pooled")
    samples, per_frame, violations = [], [], 0
    for run_dir in run_dirs:
        manifest = load_manifest(run_dir)
        if manifest.mode != "live" or manifest.active_arbiter != arbiter:
            continue
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
    return {"arbiter": arbiter, "n": n, "p50_ms": _pct(samples, 50),
            "p95_ms": p95 if p95 is not None or not samples else None, "dropped_stale": violations, "verdict": verdict,
            "per_frame": {"n": len(per_frame), "p50_ms": _pct(per_frame, 50), "p95_ms": _pct(per_frame, 95)}}
