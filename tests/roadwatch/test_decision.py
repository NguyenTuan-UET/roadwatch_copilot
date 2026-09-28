"""BT-B behaviour from spec §3.3–3.7 and failure modes F1–F17. Times in ms, speed 90 km/h => 70 m band."""

import random

from src.roadwatch.contracts.streams import AlertDecision
from src.roadwatch.decision.arbiter import AudioArbiter
from src.roadwatch.decision.stage import DecisionStage
from tests.roadwatch.decision_harness import MS, Harness, make_config

# --- distance episodes: anti-flicker mechanism of week 1 ------------------------------------

def test_short_dip_below_threshold_is_not_confirmed():
    h = Harness()
    h.run(0, 4000, d_of_t=lambda t: 60.0 if 1000 <= t < 2000 else 80.0)  # 1 s < T_confirm 1.5 s
    assert h.alerts(kind="warning") == []


def test_sustained_violation_warns_once_after_confirmation():
    h = Harness()
    h.run(0, 6000, d_of_t=lambda t: 60.0 if t >= 1000 else 80.0)
    warnings = h.alerts(kind="warning")
    assert len(warnings) == 1
    assert warnings[0].t_trigger_ns == 2500 * MS  # 1000 + T_confirm


def test_flicker_around_threshold_baseline_repeats_b_does_not():
    h = Harness()
    h.run(0, 10000, d_of_t=lambda t: 65.0 if (t // 100) % 2 == 0 else 72.0)
    assert len(h.alerts("baseline", "warning")) >= 40
    assert h.alerts("B", "warning") == []


# --- emergency episodes and the guardrail (3.7) ----------------------------------------------

def test_emergency_is_immediate_and_does_not_chatter():
    h = Harness()
    ttc = {1000: 1.5, 1100: 2.0, 1200: 1.6}
    h.run(0, 5000, ttc_of_t=lambda t: ttc.get(t, 3.0 if 1300 <= t < 3600 else (1.5 if t == 3600 else None)))
    em = h.alerts(kind="emergency")
    assert [a.t_trigger_ns for a in em] == [1000 * MS, 3600 * MS]
    assert em[0].trigger.source == "frame"


def test_emergency_is_not_blocked_by_distance_confirmation_or_cooldown():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 20.0, ttc_of_t=lambda t: 1.0 if t == 500 else None)
    assert [a.t_trigger_ns for a in h.alerts(kind="emergency")] == [500 * MS]


def test_guardrail_property_on_random_streams():
    """Whenever cap_ttc is on and TTC is ok and <= threshold, B is ACTIVE; every IDLE->ACTIVE step alerts."""
    thr = make_config().ttc.ttc_emergency_s
    for seed in range(40):
        rng = random.Random(seed)
        h = Harness()
        for i in range(150):
            t = i * 100
            if t % 1000 == 0:
                h.speed(t, 90)
            if rng.random() < 0.03:
                h.event(t, rng.choice(["mount_rechecked", "frame_dropped"]))
            obs = "ok" if rng.random() > 0.08 else "unavailable"
            ttc = rng.choice([None, rng.uniform(0.5, 4.0)])
            h.meas(t, d=rng.uniform(20, 90), ttc=ttc, obs=obs, ttc_status=rng.choice(["ok", "ok", "unreliable"]),
                   mount=rng.choice(["ok", "ok", "ok", "unknown", "suspect"]),
                   basis=rng.choice(["fixed_roi", "lane_markings"]), lead_id=rng.choice([1, 1, 1, 2]))
            h.tick(t)
        prev = "IDLE"
        emergencies = {a.trigger.input_seq for a in h.alerts(kind="emergency")}
        for (inp, m), tr in zip([j for j in h.journal], _traces_by_input(h)):
            if inp.kind != "measurement" or tr is None:
                continue
            holds = tr.cap_ttc == "on" and m.ttc_s.usable and m.ttc_s.value <= thr
            if holds:
                assert tr.emergency_state == "ACTIVE", (seed, inp.seq, tr.emergency_state)
            if tr.emergency_state == "ACTIVE" and prev in ("IDLE", "SUSPENDED_E"):
                assert inp.seq in emergencies, (seed, inp.seq)
            prev = tr.emergency_state


def _traces_by_input(h: Harness):
    by = {t.input_seq: t for t in h.traces("B")}
    return [by.get(inp.seq) for inp, _ in h.journal]


# --- HOLD: short loss keeps the episode, long loss closes it (3.5) ----------------------------

def test_short_data_loss_keeps_episode_without_realert_or_announcement():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)
    h.run(3000, 3500, obs="unavailable")
    h.run(3500, 6000, d_of_t=lambda t: 60.0)
    assert len(h.alerts(kind="warning")) == 1
    assert [a for a in h.alerts() if a.cls == "status"] == []


def test_long_data_loss_closes_episode_and_announces():
    h = Harness(make_config(dispatch={"cooldown_ms": 0}))
    h.run(0, 3000, d_of_t=lambda t: 60.0)
    h.run(3000, 6000, obs="unavailable")
    h.run(6000, 10000, d_of_t=lambda t: 60.0)
    assert len(h.alerts(kind="warning")) == 2
    assert [a.kind for a in h.alerts() if a.cls == "status"] == ["system_off", "recovery"]


def test_resume_from_hold_reevaluates_instead_of_restoring():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)
    h.run(3000, 3300, obs="unavailable")
    inp = h.meas(3300, d=80.0)  # above threshold + h (75)
    tr = next(t for t in h.traces() if t.input_seq == inp.seq)
    assert tr.distance_state == "CLEARING"


def test_new_lead_identity_starts_new_episode():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0, lead_id=1)
    h.run(3000, 6000, d_of_t=lambda t: 60.0, lead_id=2)
    assert len(h.alerts(kind="warning")) == 2


def test_no_lead_ends_episode_without_hold():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)
    inp = h.meas(3000, lead_id=None)
    tr = next(t for t in h.traces() if t.input_seq == inp.seq)
    assert tr.distance_state == "IDLE" and tr.cap_distance == "on"


# --- speed freshness, legal table, measurement age (F7, F17, F4) ------------------------------

def test_stale_speed_holds_distance_and_lost_speed_disables_it_but_keeps_ttc():
    h = Harness()
    h.speed(0, 90)
    for t in range(0, 9000, 100):
        h.meas(t, d=60.0 if t >= 1000 else 80.0, ttc=1.2 if t == 8000 else None)
        h.tick(t)
    assert h.alerts(kind="warning") == []  # stale from 1600 ms, before confirmation at 2500 ms
    assert [a.t_trigger_ns for a in h.alerts(kind="emergency")] == [8000 * MS]
    last = h.traces()[-1]
    assert last.cap_distance == "off" and last.cap_ttc == "on" and last.speed_used.status == "lost"
    assert "cap_distance_off" in [a.kind for a in h.alerts()]


def test_speed_outside_legal_bands_has_no_distance_threshold():
    h = Harness()
    h.run(0, 4000, d_of_t=lambda t: 10.0, kmh=40.0)
    assert h.alerts(kind="warning") == []
    assert h.traces()[-1].threshold_m.status == "not_applicable"


def test_novice_margin_widens_threshold():
    h = Harness(make_config(dispatch={"novice_margin_m": 10.0}), driver_mode="novice")
    h.run(0, 4000, d_of_t=lambda t: 75.0)  # above 70 but below 70 + 10
    assert len(h.alerts(kind="warning")) == 1


def test_old_measurement_cannot_alert():
    h = Harness()
    for t in range(0, 4000, 100):
        if t % 1000 == 0:
            h.speed(t, 90)
        h.meas(t, d=60.0, ttc=1.0, consumed_ms=t + 600)  # age 600 ms > 500 ms
    assert h.alerts() == []
    assert "stale_measurement" in h.traces()[-1].why


def test_measurement_gap_found_by_ticks_turns_everything_off():
    h = Harness()
    h.run(0, 1000)
    for t in range(1000, 5000, 100):
        h.tick(t)
    last = h.traces()[-1]
    assert (last.cap_distance, last.cap_ttc) == ("off", "off")
    assert [a.kind for a in h.alerts() if a.cls == "status"] == ["system_off"]


# --- mount check capabilities (ADR-05, F10-F12) -----------------------------------------------

def test_mount_suspect_turns_distance_off_and_ttc_needs_lane_markings():
    h = Harness()
    h.run(0, 2000, mount="suspect", d_of_t=lambda t: 60.0, ttc_of_t=lambda t: 1.0 if t == 1000 else None)
    assert h.alerts(kind="warning") == [] and h.alerts(kind="emergency") == []
    h.run(2000, 3000, mount="suspect", basis="lane_markings", ttc_of_t=lambda t: 1.0 if t == 2500 else None)
    assert len(h.alerts(kind="emergency")) == 1


def test_unknown_mount_is_trusted_within_window_only_with_checklist():
    with_checklist = Harness(checklist=True)
    with_checklist.run(0, 3000, mount="unknown", d_of_t=lambda t: 60.0)
    assert len(with_checklist.alerts(kind="warning")) == 1
    without = Harness(checklist=False)
    without.run(0, 3000, mount="unknown", d_of_t=lambda t: 60.0)
    assert without.alerts(kind="warning") == []
    assert without.traces()[-1].cap_distance == "off"


def test_mount_flapping_latches_until_rechecked():
    h = Harness()
    for k in range(3):
        h.run(k * 2000, k * 2000 + 1000, mount="suspect")
        h.run(k * 2000 + 1000, k * 2000 + 2000, mount="ok")
    assert h.traces()[-1].cap_distance == "off"
    h.event(6000, "mount_rechecked")
    h.run(6000, 7000, mount="ok")
    assert h.traces()[-1].cap_distance == "on"


def test_system_fault_is_announced_immediately():
    h = Harness()
    h.run(0, 1000)
    inp = h.event(1000, "system_fault")
    status = [a for a in h.alerts() if a.cls == "status"]
    assert [(a.kind, a.trigger.input_seq, a.trigger.source) for a in status] == [("system_off", inp.seq, "event")]


def test_blip_shorter_than_notify_debounce_is_silent_but_gated():
    h = Harness()
    h.run(0, 1000)
    inp = h.meas(1000, obs="unavailable")
    assert next(t for t in h.traces() if t.input_seq == inp.seq).cap_distance == "off"  # gated at once
    h.run(1100, 5000)
    assert [a for a in h.alerts() if a.cls == "status"] == []


# --- baseline and reproducibility --------------------------------------------------------------

def test_baseline_respects_invalid_data():
    h = Harness()
    h.run(0, 3000, obs="unavailable")
    assert h.alerts("baseline") == []


def test_same_journal_gives_identical_outputs():
    h = Harness()
    h.run(0, 6000, d_of_t=lambda t: 60.0 if (t // 700) % 2 else 80.0, ttc_of_t=lambda t: 1.4 if t == 3000 else None)
    again = DecisionStage(h.cfg, run_id="r", mount_checklist=True, driver_mode="experienced")
    out = [r for inp, payload in h.journal for r in again.consume(inp, payload)]
    import json

    from src.roadwatch.contracts.base import normalize
    assert [normalize(json.loads(r.to_json())) for r in out] == h.normalized()


# --- audio arbiter (3.6) ------------------------------------------------------------------------

def _alert(kind, cls, t_ms, n, epoch=0):
    return AlertDecision(run_id="r", seq=n, t_ns=int(t_ms * MS), alert_id=f"B-{n}", arbiter="B", cls=cls, kind=kind,
                         phrase_id=kind, trigger={"source": "frame", "input_seq": n}, t_trigger_ns=int(t_ms * MS),
                         t_decided_ns=int(t_ms * MS), capability_epoch=epoch, expires_t_ns=int((t_ms + 1500) * MS))


def _arb():
    return AudioArbiter(make_config().audio)


def test_emergency_preempts_playing_warning():
    a = _arb()
    out = a.submit(_alert("warning", "hazard", 0, 0), 0, epoch=0)
    out += a.submit(_alert("emergency", "hazard", 200, 1), 200 * MS, epoch=0)
    assert [(o.alert_id, o.outcome) for o in out] == [("B-0", "started"), ("B-0", "preempted"), ("B-1", "started")]


def test_status_message_waits_and_never_preempts():
    a = _arb()
    out = a.submit(_alert("info", "hazard", 0, 0), 0, epoch=0)  # info (5) ranks below system_off (3)
    out += a.submit(_alert("system_off", "status", 100, 1), 100 * MS, epoch=0)
    out += a.advance(1400 * MS, epoch=0)  # info lasts 1400 ms
    assert [(o.alert_id, o.outcome, o.t_ns) for o in out] == [
        ("B-0", "started", 0), ("B-1", "started", 1400 * MS)]


def test_pending_status_with_old_epoch_is_cancelled():
    a = _arb()
    a.submit(_alert("warning", "hazard", 0, 0), 0, epoch=0)
    a.submit(_alert("system_off", "status", 100, 1, epoch=0), 100 * MS, epoch=0)
    out = a.advance(1500 * MS, epoch=1)
    assert [(o.alert_id, o.outcome) for o in out] == [("B-1", "cancelled")]


def test_pending_command_expires():
    a = _arb()
    a.submit(_alert("system_off", "status", 0, 0), 0, epoch=0)  # plays 1800 ms
    a.submit(_alert("reminder", "status", 0, 1), 0, epoch=0)
    out = a.advance(1800 * MS, epoch=0)  # reminder is 1800 ms old > max_cmd_age 1500
    assert [(o.alert_id, o.outcome) for o in out] == [("B-1", "expired")]
