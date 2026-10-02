"""BT-B behaviour from spec §3.3–3.7 and failure modes F1–F17. Times in ms, speed 90 km/h => 70 m band."""

import random
from pathlib import Path

import pytest
import yaml

from src.roadwatch.contracts.config import RwConfig
from src.roadwatch.contracts.streams import AlertDecision, AudioPlan, DecisionTrace
from src.roadwatch.decision.arbiter import AudioArbiter
from src.roadwatch.decision.stage import DecisionStage
from tests.roadwatch import make_fixtures
from tests.roadwatch.decision_harness import MS, Harness, make_config
from tests.roadwatch.factories import config_dict

REPO = Path(__file__).parents[2]

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


def _random_stream(seed: int) -> Harness:
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
        h.meas(
            t,
            d=rng.uniform(20, 90),
            ttc=ttc,
            obs=obs,
            ttc_status=rng.choice(["ok", "ok", "unreliable"]),
            mount=rng.choice(["ok", "ok", "ok", "unknown", "suspect"]),
            basis=rng.choice(["fixed_roi", "lane_markings"]),
            lead_id=rng.choice([1, 1, 1, 2]),
        )
        h.tick(t)
    return h


def test_guardrail_property_on_random_streams():
    """Whenever cap_ttc is on and TTC is ok and <= threshold, B is ACTIVE; every IDLE->ACTIVE step alerts."""
    thr = make_config().ttc.ttc_emergency_s
    for seed in range(40):
        h = _random_stream(seed)
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


def test_guardrail_property_no_dangerous_frame_leaves_its_episode_unheard():
    """3.7 (b): at every frame that meets the three conditions, the episode has an Emergency command that
    started or is still waiting in the arbiter (the one issued at this very frame counts)."""
    thr = make_config().ttc.ttc_emergency_s
    for seed in range(40):
        h = _random_stream(seed)
        meas = {inp.seq: m for inp, m in h.journal if inp.kind == "measurement"}
        outcome: dict[str, str] = {}  # alert_id -> last audio_plan outcome; no record yet means still waiting
        commands: dict[str, list[str]] = {}  # episode_id -> its Emergency commands
        episode = None
        for r in h.out:  # records are in emission order; the trace closes each input
            if isinstance(r, AlertDecision) and r.arbiter == "B" and r.kind == "emergency":
                episode = r.episode_id
                commands.setdefault(episode, []).append(r.alert_id)
            elif isinstance(r, AudioPlan) and r.arbiter == "B":
                outcome[r.alert_id] = r.outcome
            elif isinstance(r, DecisionTrace) and r.arbiter == "B" and r.input_seq in meas:
                m = meas[r.input_seq]
                if r.cap_ttc == "on" and m.ttc_s.usable and m.ttc_s.value <= thr:
                    states = [outcome.get(a, "waiting") for a in commands.get(episode, [])]
                    assert "started" in states or "waiting" in states, (seed, r.input_seq, states)


# --- guardrail while an episode continues: scenarios S1-S7 of spec 3.7 (OQ-B12, option b) ---------
# Emergency lasts 1200 ms, threshold 1.8 s, T_clear_e 1500 ms, T_hold 1000 ms, max_cmd_age 1500 ms.


def _emergencies(h: Harness) -> list[tuple[float, str]]:
    return [(a.t_trigger_ns / MS, a.episode_id) for a in h.alerts(kind="emergency")]


def test_s1_new_episode_alerts_at_the_frame_that_meets_the_three_conditions():
    h = Harness()
    h.run(0, 2000, ttc_of_t=lambda t: 1.5 if t == 1000 else None)
    assert _emergencies(h) == [(1000, "e1")]
    assert h.alerts(kind="emergency")[0].trigger.source == "frame"
    assert h.plans() == [("B-0", "started", 1000)]


def test_s2_episode_that_stays_dangerous_alerts_only_once():
    h = Harness()
    h.run(0, 4000, ttc_of_t=lambda t: 1.5 if 1000 <= t <= 3000 else None)  # 20 more frames below threshold
    assert _emergencies(h) == [(1000, "e1")]


def test_s3_short_clearing_then_danger_again_is_the_same_heard_episode():
    h = Harness()
    h.run(0, 3000, ttc_of_t=lambda t: {1000: 1.5, 1400: 1.5}.get(t, 3.0 if 1100 <= t <= 1300 else None))
    assert _emergencies(h) == [(1000, "e1")]  # 300 ms above the threshold is shorter than T_clear_e


def test_s4_command_cancelled_in_the_pending_slot_is_issued_again_on_resume():
    h = Harness()
    h.run(0, 1500, ttc_of_t=lambda t: 1.5 if t == 1000 else None, lead_id=1)  # B-0 plays 1000..2200
    h.run(1500, 1600, ttc_of_t=lambda t: 1.5, lead_id=2)  # k: new lead, B-1 waits behind B-0
    h.run(1600, 1900, obs="unavailable")  # k+1: cap_ttc off, B-1 cancelled, episode in HOLD_E
    h.run(1900, 3000, ttc_of_t=lambda t: 1.5 if t <= 2300 else None, lead_id=2)  # m: inside T_hold, same lead
    assert _emergencies(h) == [(1000, "e1"), (1500, "e2"), (1900, "e2")]
    assert h.plans() == [("B-0", "started", 1000), ("B-1", "cancelled", 1600), ("B-2", "started", 2200)]


def test_s5_heard_episode_resumed_from_hold_is_not_issued_again():
    h = Harness()
    h.run(0, 1100, ttc_of_t=lambda t: 1.5 if t == 1000 else None)
    h.run(1100, 1500, obs="unavailable")  # 400 ms of invalid data, shorter than T_hold
    h.run(1500, 3000, ttc_of_t=lambda t: 1.5 if t == 1500 else None)
    assert _emergencies(h) == [(1000, "e1")]


def test_s6_new_lead_starts_a_new_episode_and_alerts():
    h = Harness()
    h.run(0, 2500, ttc_of_t=lambda t: 1.5 if t >= 1000 else None, lead_id=1)
    h.run(2500, 3500, ttc_of_t=lambda t: 1.5, lead_id=2)  # not a likely_id_switch: another identity
    assert _emergencies(h) == [(1000, "e1"), (2500, "e2")]
    assert h.plans() == [("B-0", "started", 1000), ("B-1", "started", 2500)]


def test_s7_command_expired_in_the_pending_slot_is_issued_again_while_still_active():
    h = Harness(make_config(audio={"max_cmd_age_ms": 500}))
    h.run(0, 1500, ttc_of_t=lambda t: 1.5 if t == 1000 else None, lead_id=1)  # B-0 plays 1000..2200
    h.run(1500, 3000, ttc_of_t=lambda t: 1.5 if t <= 2600 else None, lead_id=2)  # B-1 waits 700 ms > 500 ms
    assert _emergencies(h) == [(1000, "e1"), (1500, "e2"), (2200, "e2")]
    assert h.plans() == [("B-0", "started", 1000), ("B-1", "expired", 2200), ("B-2", "started", 2200)]


# --- HOLD while an episode is clearing (3.5; OQ-A5, PO 01/10): time without data never prolongs the silence ---
# A HOLD neither erases nor stops the clearing count. Before, every recovery restarted it, so data that dropped
# out more often than once per T_clear_e kept a heard episode open for ever and the next danger stayed silent.

NO_TTC = dict(ttc_of_t=lambda t: 1.0, ttc_status="unreliable")  # the camera sees fine, only the TTC is unusable


def test_hold_e_while_clearing_neither_erases_nor_stops_the_clearing_time():
    h = Harness()
    h.run(0, 2000, ttc_of_t=lambda t: 1.5 if t == 1000 else None)  # clear since 1100
    h.run(2000, 2300, obs="unavailable")
    h.run(2300, 4000)
    assert _trace(h, 2300).emergency_state == "CLEARING_E"  # 1200 ms since 1100: not over yet
    assert _trace(h, 2500).emergency_state == "CLEARING_E"
    assert _trace(h, 2600).emergency_state == "IDLE"  # 1100 + T_clear_e, as if the data had never dropped


def test_danger_after_a_hold_that_outlasted_the_clearing_time_is_a_new_episode():
    h = Harness()
    h.run(0, 2000, ttc_of_t=lambda t: 1.5 if t == 1000 else None)  # heard at 1000, clear since 1100
    h.run(2000, 2700, **NO_TTC)
    h.run(2700, 3000, ttc_of_t=lambda t: 1.5)  # 1600 ms after the first clear frame
    assert _emergencies(h) == [(1000, "e1"), (2700, "e2")]
    assert "cleared_in_hold" in _trace(h, 2700).why


def test_danger_back_before_the_clearing_time_is_over_is_the_same_heard_episode_even_across_a_hold():
    h = Harness()
    h.run(0, 1500, ttc_of_t=lambda t: 1.5 if t == 1000 else None)  # clear since 1100
    h.run(1500, 2000, **NO_TTC)
    h.run(2000, 3000, ttc_of_t=lambda t: 1.5 if t == 2000 else None)  # 900 ms after the first clear frame
    assert _emergencies(h) == [(1000, "e1")]


def test_hold_from_active_starts_the_clearing_time_at_the_recovery_not_at_an_earlier_clearing():
    h = Harness()
    h.run(0, 1500, ttc_of_t=lambda t: 1.5 if t in (1000, 1400) else None)  # cleared 1100-1300, danger again at 1400
    h.run(1500, 1800, **NO_TTC)  # HOLD_E from ACTIVE
    h.run(1800, 2700)  # clearing counts from 1800; the count of 1100 belongs to the past
    h.run(2700, 2800, ttc_of_t=lambda t: 1.5)
    assert _emergencies(h) == [(1000, "e1")]  # 900 ms after the recovery: still the heard episode


def test_isolated_usable_frames_do_not_keep_a_heard_episode_open():
    """Worst case for the count: never two usable frames in a row."""
    h = Harness()
    h.run(0, 1100, ttc_of_t=lambda t: 1.5 if t == 1000 else None)
    for t0 in range(1100, 30100, 1000):
        h.run(t0, t0 + 100)  # one usable frame, no danger
        h.run(t0 + 100, t0 + 1000, **NO_TTC)  # shorter than T_hold
    h.run(30100, 30200, ttc_of_t=lambda t: 1.5)
    assert _emergencies(h) == [(1000, "e1"), (30100, "e2")]


def test_oq_a5_danger_long_after_the_last_one_is_a_new_episode_despite_short_data_blips():
    """One invalid frame per second, for a minute: the danger at the end is not merged into the heard episode."""
    h = Harness()
    h.run(0, 2000, ttc_of_t=lambda t: 1.5 if t == 1000 else None)
    for t0 in range(2000, 61000, 1000):
        h.run(t0, t0 + 100, obs="unavailable")
        h.run(t0 + 100, t0 + 1000)
    h.run(61000, 62000, ttc_of_t=lambda t: 1.5 if t == 61500 else None)
    assert _emergencies(h) == [(1000, "e1"), (61500, "e2")]


def test_hold_while_clearing_neither_erases_nor_stops_the_clearing_time():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)  # warned at 1500
    h.run(3000, 4000, d_of_t=lambda t: 80.0)  # above threshold + h: clearing since 3000
    h.run(4000, 4300, obs="unavailable")
    h.run(4300, 6000, d_of_t=lambda t: 80.0)
    assert _trace(h, 4300).distance_state == "CLEARING" and _trace(h, 4900).distance_state == "CLEARING"
    assert _trace(h, 5000).distance_state == "IDLE"  # 3000 + T_clear, as if the data had never dropped


def test_hold_from_alerted_starts_the_clearing_time_at_the_recovery_not_at_an_earlier_clearing():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)  # warned at 1500
    h.run(3000, 3500, d_of_t=lambda t: 80.0)  # clearing since 3000 ...
    h.run(3500, 4000, d_of_t=lambda t: 60.0)  # ... back below the threshold: ALERTED again
    h.run(4000, 4300, obs="unavailable")  # HOLD from ALERTED
    h.run(4300, 5500, d_of_t=lambda t: 80.0)  # clearing counts from 4300
    assert _trace(h, 5400).distance_state == "CLEARING"  # 3000 + T_clear would have been 5000


def test_tailgating_after_a_hold_that_outlasted_the_clearing_time_is_a_new_episode():
    h = Harness(make_config(dispatch={"cooldown_ms": 0}))
    h.run(0, 3000, d_of_t=lambda t: 60.0)  # warned at 1500
    h.run(3000, 4500, d_of_t=lambda t: 80.0)  # clearing since 3000
    h.run(4500, 5200, d_of_t=lambda t: 60.0, d_status="unreliable")
    h.run(5200, 8000, d_of_t=lambda t: 60.0)  # 2200 ms after the first clear frame
    assert _hazards(h, "warning") == [(1500, "d1"), (6700, "d2")]  # confirmed again from 5200
    assert "cleared_in_hold" in _trace(h, 5200).why


def test_oq_a5_tailgating_long_after_the_last_one_is_a_new_episode_despite_short_data_blips():
    """Same for the distance episode: the same lead tailgating again 58 s later gets its second warning, at
    62500 as with clean data (new episode, T_confirm, cooldown long over)."""
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0)  # warned at 1500
    for t0 in range(3000, 61000, 1000):
        h.run(t0, t0 + 100, obs="unavailable")
        h.run(t0 + 100, t0 + 1000, d_of_t=lambda t: 80.0)  # above threshold + h
    h.run(61000, 64000, d_of_t=lambda t: 60.0)
    assert _hazards(h, "warning") == [(1500, "d1"), (62500, "d2")]


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


def test_time_in_hold_does_not_count_towards_t_confirm():
    h = Harness()
    h.run(0, 1000)
    h.run(1000, 2000, d_of_t=lambda t: 60.0)  # PENDING since 1000
    h.run(2000, 2500, obs="unavailable")  # 500 ms in HOLD
    h.run(2500, 4000, d_of_t=lambda t: 60.0)
    assert [t for t, _ in _hazards(h, "warning")] == [3000]  # 1000 + T_confirm + the 500 ms held


def test_pending_episode_resumed_at_or_above_the_threshold_goes_idle():
    h = Harness()
    h.run(0, 1000, d_of_t=lambda t: 60.0)
    h.run(1000, 1300, obs="unavailable")
    h.run(1300, 4000, d_of_t=lambda t: 70.0 if t == 1300 else 60.0)
    assert _trace(h, 1300).distance_state == "IDLE"
    assert [t for t, _ in _hazards(h, "warning")] == [2900]  # counted again from 1400, not from 0


def test_another_lead_after_hold_starts_a_new_episode():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0, lead_id=1)
    h.run(3000, 3400, obs="unavailable")
    h.run(3400, 6000, d_of_t=lambda t: 60.0, lead_id=2)
    assert _hazards(h, "warning") == [(1500, "d1"), (4900, "d2")]


def test_clearing_shorter_than_t_clear_returns_to_the_same_episode_silently():
    h = Harness()
    h.run(0, 6000, d_of_t=lambda t: 80.0 if 3000 <= t < 4000 else 60.0)  # 1 s above threshold + h
    assert _trace(h, 3000).distance_state == "CLEARING" and _trace(h, 4000).distance_state == "ALERTED"
    assert _hazards(h, "warning") == [(1500, "d1")]


def test_cleared_episode_warns_the_same_lead_again_only_after_the_cooldown():
    def d(t):
        return 80.0 if 3000 <= t <= 5000 or 7000 <= t <= 10000 else 60.0

    h = Harness()
    h.run(0, 12000, d_of_t=d)
    assert _trace(h, 4900).distance_state == "CLEARING" and _trace(h, 5000).distance_state == "IDLE"  # T_clear
    second = _trace(h, 6600)  # new episode confirmed 5.1 s after the first warning: inside the 10 s cooldown
    assert second.distance_state == "ALERTED" and "cooldown" in second.why
    assert _hazards(h, "warning") == [(1500, "d1"), (11600, "d3")]


def test_clearing_must_stay_above_threshold_plus_h_for_the_whole_t_clear():
    """I-12: a sample back inside [threshold, threshold + h] restarts the T_clear count."""
    h = Harness()
    h.run(0, 7000, d_of_t=lambda t: 60.0 if t < 3000 else (72.0 if t == 4000 else 80.0))
    assert _trace(h, 5000).distance_state == "CLEARING"  # 3000 + T_clear without the restart
    assert _trace(h, 5900).distance_state == "CLEARING" and _trace(h, 6000).distance_state == "IDLE"


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


def test_speed_sample_received_after_the_frame_time_is_not_used_for_that_frame():
    """3.3 information cutoff: a sample counts for frame k only if it was consumed earlier and t_recv <= t_k."""
    h = Harness()
    h.speed(0, 90)
    h.speed(1050, 110)  # consumed before the late frame below, but received after its t_k
    old = h.meas(1000, consumed_ms=1100)
    new = h.meas(1100, consumed_ms=1100)
    used = {tr.input_seq: (tr.speed_used.gps_idx, tr.threshold_m.value) for tr in h.traces()}
    assert used[old.seq] == (0, 70.0)  # 90 km/h band
    assert used[new.seq] == (1, 100.0)  # 110 km/h band


def test_speed_outside_legal_bands_has_no_distance_threshold():
    h = Harness()
    h.run(0, 4000, d_of_t=lambda t: 10.0, kmh=40.0)
    assert h.alerts(kind="warning") == []
    assert h.traces()[-1].threshold_m.status == "not_applicable"


# TT 38/2024/TT-BGTVT, Điều 11 khoản 1: V = 60 -> 35 m; 60 < V <= 80 -> 55; 80 < V <= 100 -> 70; 100 < V <= 120 -> 100.
# Khoản 2 gives no figure below 60 km/h. Copied by hand from the legal text, not from the code or the config.
ARTICLE_11 = [(60.0, 60.0, 35.0), (60.0, 80.0, 55.0), (80.0, 100.0, 70.0), (100.0, 120.0, 100.0)]


@pytest.mark.parametrize(
    "kmh, want_m",
    [(59.9, None), (60, 35), (60.1, 55), (80, 55), (80.1, 70), (100, 70), (100.1, 100), (120, 100), (120.1, None)],
)
def test_legal_band_includes_its_upper_speed_as_article_11_says(kmh, want_m):
    bands = [dict(v_min_kmh=lo, v_max_kmh=hi, min_distance_m=d) for lo, hi, d in ARTICLE_11]
    h = Harness(make_config(legal_table={"bands": bands}))
    h.speed(0, kmh)  # arrives in m/s like a GPS sample
    inp = h.meas(0)
    thr = next(tr for tr in h.traces() if tr.input_seq == inp.seq).threshold_m
    assert thr.value == want_m
    assert thr.status == ("ok" if want_m else "not_applicable")


def test_v0_proposal_part_b_is_a_valid_config_and_carries_article_11():
    """WP-B1: the committed template passes the config validator once its A sections (TODO values) are filled."""
    proposal = yaml.safe_load((REPO / "config" / "proposals" / "v0.yaml").read_text(encoding="utf-8"))
    assert set(proposal) >= {"legal_table", "ttc", "dispatch", "speed", "status_msgs", "audio"}
    filled = {name: config_dict()[name] for name in ("camera", "mount", "detector", "perception")}
    cfg = RwConfig.model_validate({**proposal, **filled})
    assert [(b.v_min_kmh, b.v_max_kmh, b.min_distance_m) for b in cfg.legal_table.bands] == ARTICLE_11
    assert "38/2024" in cfg.legal_table.legal_ref and "Điều 11" in cfg.legal_table.legal_ref


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


def test_low_processing_rate_turns_only_the_collision_warning_off():
    """3.4, F18: below min_ttc_rate_hz (6 Hz) cap_ttc goes off and cap_distance stays; fail-safe, so no Emergency."""
    h = Harness()
    h.run(0, 2000)  # 10 Hz
    for t in range(2000, 5200, 100):  # then 5 frames per second
        if t % 1000 == 0:
            h.speed(t, 90)
        if t % 200 == 0:
            h.meas(t, ttc=1.5 if t == 5000 else None)
        h.tick(t)
    caps = {inp.t_ns // MS: (tr.cap_distance, tr.cap_ttc) for (inp, _), tr in zip(h.journal, _traces_by_input(h))}
    assert caps[2800] == ("on", "on")  # the last second still holds 6 frames
    assert caps[3000] == ("on", "off")  # 5 frames in the last second
    assert h.alerts(kind="emergency") == []
    assert [(a.kind, a.t_trigger_ns / MS) for a in h.alerts() if a.cls == "status"] == [("cap_ttc_off", 5000)]


def _trace(h: Harness, t_ms: float, kind: str = "measurement") -> DecisionTrace:
    """B's trace of the input of this kind at this time."""
    seq = next(inp.seq for inp, _ in h.journal if inp.kind == kind and inp.t_ns == t_ms * MS)
    return next(tr for tr in h.traces() if tr.input_seq == seq)


def test_emergency_episode_does_not_survive_a_measurement_gap_longer_than_t_hold():
    """3.5: missing data holds the episode (found at ticks, 3.3); past T_hold it is closed, so the same lead
    being dangerous again after the gap is a new episode and alerts."""
    h = Harness()
    h.run(0, 1100, ttc_of_t=lambda t: 1.5 if t == 1000 else None)  # last measurement at 1000 ms
    for t in range(1100, 4000, 100):
        h.tick(t)
    assert _trace(h, 2000, "tick").emergency_state == "ACTIVE"  # gap is exactly max_measurement_gap: not yet
    assert _trace(h, 2100, "tick").emergency_state == "HOLD_E"  # cap_ttc off since this tick
    assert _trace(h, 3100, "tick").emergency_state == "HOLD_E"
    assert _trace(h, 3200, "tick").emergency_state == "SUSPENDED_E"  # 1100 ms in HOLD_E > T_hold
    # frames come back at 4000; cap_ttc needs 6 frames in the last second again (min_ttc_rate_hz), so from 4500
    h.run(4000, 5500, ttc_of_t=lambda t: 1.5 if t == 4600 else None)
    assert _emergencies(h) == [(1000, "e1"), (4600, "e2")]


def test_distance_episode_does_not_survive_a_measurement_gap_longer_than_t_hold():
    h = Harness(make_config(dispatch={"cooldown_ms": 0}))
    h.run(0, 3000, d_of_t=lambda t: 60.0)  # warned at 1500 ms, last measurement at 2900 ms
    for t in range(3000, 6000, 100):
        h.tick(t)
    assert _trace(h, 4000, "tick").distance_state == "HOLD"  # gap found: 1100 ms since the last measurement
    assert _trace(h, 5100, "tick").distance_state == "SUSPENDED"
    h.run(6000, 8000, d_of_t=lambda t: 60.0)
    assert [a.t_trigger_ns / MS for a in h.alerts(kind="warning")] == [1500, 7500]  # a new episode confirms again


def test_system_fault_holds_the_episodes_even_when_no_measurement_follows():
    h = Harness()
    h.run(0, 1100, ttc_of_t=lambda t: 1.5 if t == 1000 else None)
    inp = h.event(1100, "system_fault")
    assert next(tr for tr in h.traces() if tr.input_seq == inp.seq).emergency_state == "HOLD_E"
    for t in range(1100, 2400, 100):
        h.tick(t)
    assert _trace(h, 2200, "tick").emergency_state == "SUSPENDED_E"


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


def test_reminder_repeats_while_degraded_once_remind_interval_is_set():
    """3.4: remind_interval stays null in the MVP (no reminder at all); when set, one reminder per interval."""
    h = Harness(make_config(status_msgs={"remind_interval_ms": 3000}))
    h.run(0, 1000)
    h.run(1000, 9500, obs="unavailable")
    assert _status(h) == [("system_off", 3000), ("reminder", 6000), ("reminder", 9000)]


# --- failure situations of spec 6 as fixture folders (WP-B9, AC-M7) ----------------------------------
# Each folder holds what B consumed (journal + payload streams, checked like any writer's output on load).
# The scripts that wrote them are in make_fixtures.py; the expected behaviour below is derived by hand from
# spec 3.3-3.7 and table 6.1 with the test config: T_confirm 1500, T_hold 1000, T_notify 2000 (ms), 70 m band.

SCENARIOS = Path(__file__).parent / "fixtures" / "scenarios"


def _scenario(name: str) -> Harness:
    return Harness.load(SCENARIOS / name)


def _hazards(h: Harness, kind: str, arbiter: str = "B") -> list[tuple[float, str | None]]:
    return [(a.t_trigger_ns / MS, a.episode_id) for a in h.alerts(arbiter, kind)]


def _status(h: Harness) -> list[tuple[str, float]]:
    return [(a.kind, a.t_trigger_ns / MS) for a in h.alerts() if a.cls == "status"]


def _caps(tr: DecisionTrace) -> tuple[str, str]:
    return tr.cap_distance, tr.cap_ttc


def test_scenario_fixtures_are_what_the_generator_writes(tmp_path, monkeypatch):
    """A contract or script change must be followed by `python -m tests.roadwatch.make_fixtures scenarios`."""
    monkeypatch.setattr(make_fixtures, "SCENARIOS", tmp_path)
    make_fixtures.scenarios()

    def files(root):
        return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file()}

    assert files(tmp_path) == files(SCENARIOS)


def test_f1_placeholder_frames_turn_everything_off_then_close_the_episode():
    h = _scenario("f01_placeholder_frames")
    assert _hazards(h, "warning") == [(1500, "d1")]
    assert _caps(_trace(h, 2000)) == ("off", "off")  # at the first placeholder, before any announcement
    assert _trace(h, 2000).distance_state == "HOLD"
    assert _trace(h, 3100).distance_state == "SUSPENDED"  # 1100 ms without valid data > T_hold
    assert _trace(h, 4500).distance_state == "PENDING"  # data back: a new episode starts from IDLE
    assert _caps(_trace(h, 4500)) == ("on", "off")  # cap_ttc needs 6 frames in the last second again ...
    assert _caps(_trace(h, 5000)) == ("on", "on")  # ... which it has from here
    assert _status(h) == [("system_off", 4000), ("recovery", 7000)]  # T_notify after each change, once each
    assert _trace(h, 6000).distance_state == "ALERTED" and "cooldown" in _trace(h, 6000).why  # same lead, < 10 s
    assert h.plans() == [("B-0", "started", 1500), ("B-1", "started", 4000), ("B-2", "started", 7000)]


def test_f2_dropped_frames_hold_the_episode_only_once_the_gap_rule_fires():
    h = _scenario("f02_dropped_frames")
    assert _trace(h, 3200, "tick").distance_state == "ALERTED"  # 0.4 s gap: nothing changes
    assert _caps(_trace(h, 4900, "tick")) == ("on", "on")  # 1000 ms since the last frame: not a gap yet
    gap = _trace(h, 5000, "tick")
    assert _caps(gap) == ("off", "off") and "measurement_gap" in gap.why and gap.distance_state == "HOLD"
    back = _trace(h, 5500)  # inside T_hold: same episode; cap_ttc waits for 6 frames per second again
    assert back.distance_state == "ALERTED" and _caps(back) == ("on", "off") and "low_rate" in back.why
    assert _caps(_trace(h, 6000)) == ("on", "on")
    assert _hazards(h, "warning") == [(1500, "d1")] and _status(h) == []  # both blips are shorter than T_notify


def test_f3_f19_hang_turns_everything_off_and_the_fault_is_announced_at_once():
    h = _scenario("f03_f19_hang_then_fault")
    assert _hazards(h, "emergency") == [(1000, "e1")]
    assert _caps(_trace(h, 2000, "tick")) == ("on", "on") and _trace(h, 2000, "tick").emergency_state == "ACTIVE"
    assert _caps(_trace(h, 2100, "tick")) == ("off", "off") and _trace(h, 2100, "tick").emergency_state == "HOLD_E"
    assert _trace(h, 3200, "tick").emergency_state == "SUSPENDED_E"
    status = [a for a in h.alerts() if a.cls == "status"]
    assert [(a.kind, a.t_trigger_ns / MS, a.trigger.source) for a in status] == [("system_off", 3100, "event")]
    assert {"measurement_gap", "system_fault"} <= set(h.traces()[-1].why)


def test_f4_late_measurements_cannot_alert_and_do_not_change_capabilities():
    h = _scenario("f04_late_measurements")
    late = _trace(h, 3000)
    assert late.measurement_age_ms == 1000 and "stale_measurement" in late.why
    assert late.distance_state == "HOLD" and _caps(late) == ("on", "on")
    assert _hazards(h, "emergency") == []  # TTC 1.5 s arrived 800 ms old
    usable = _trace(h, 3500)  # exactly max_measurement_age: valid again, inside T_hold
    assert usable.measurement_age_ms == 500 and usable.distance_state == "ALERTED"
    assert _hazards(h, "warning") == [(1500, "d1")] and _status(h) == []


def test_f7_f8_stale_speed_is_silent_and_lost_speed_turns_only_distance_off():
    h = _scenario("f07_f08_speed_stale_then_lost")
    fresh, stale = _trace(h, 2500), _trace(h, 2600)
    assert fresh.speed_used.status == "fresh" and fresh.threshold_m.value == 70.0
    assert fresh.headway_s.value == pytest.approx(2.4)  # 60 m at 25 m/s
    assert stale.speed_used.status == "stale" and stale.speed_used.age_ms == 1600
    assert (stale.threshold_m.status, stale.threshold_m.reasons) == ("unreliable", ["speed_stale"])
    assert stale.headway_s.status == "unavailable"
    assert stale.distance_state == "HOLD" and _caps(stale) == ("on", "on")  # F7a: capabilities do not change
    assert _trace(h, 3700).distance_state == "SUSPENDED"
    lost = _trace(h, 6100)
    assert lost.speed_used.status == "lost" and _caps(lost) == ("off", "on")  # F7b
    assert _hazards(h, "emergency") == [(7000, "e1")]  # TTC does not use speed
    assert _hazards(h, "warning") == [(1500, "d1")]
    assert _status(h) == [("cap_distance_off", 8100)]  # nothing was said while the speed was only stale
    assert h.plans() == [("B-0", "started", 1500), ("B-1", "started", 7000), ("B-2", "started", 8200)]


def test_f10_mount_suspect_stops_distance_and_ttc_needs_a_lane_marking_lead():
    h = _scenario("f10_mount_suspect")
    assert _caps(_trace(h, 1600)) == ("off", "off")  # lead chosen by the fixed ROI
    assert _caps(_trace(h, 4000)) == ("off", "on")  # lead chosen from lane markings
    assert _hazards(h, "warning") == [(1500, "d1")]
    assert _hazards(h, "emergency") == [(5000, "e1")]  # the TTC of 1.5 s at 2500 ms was not trusted
    assert _status(h) == [("system_off", 3600), ("cap_distance_off", 6000)]
    assert h.plans() == [
        ("B-0", "started", 1500),
        ("B-1", "started", 3600),
        ("B-1", "preempted", 5000),  # Emergency interrupts the status phrase
        ("B-2", "started", 5000),
        ("B-3", "started", 6200),  # the status phrase waits for the Emergency phrase to end
    ]


def test_f11_unknown_mount_is_trusted_only_inside_the_trust_window():
    h = _scenario("f11_mount_unknown")
    assert _caps(_trace(h, 2000)) == ("on", "on")
    expired = _trace(h, 2100)
    assert _caps(expired) == ("off", "off") and "mount_unverified" in expired.why
    assert _hazards(h, "warning") == [(1500, "d1")]
    assert _status(h) == [("system_off", 4100), ("recovery", 6500)]


def test_f11_unknown_mount_without_a_checklist_never_warns_about_distance():
    h = _scenario("f11_mount_unknown_no_checklist")
    assert _caps(_trace(h, 0)) == ("off", "off")
    assert _hazards(h, "warning") == [] and _status(h) == [("system_off", 2000)]


def test_f12_flapping_mount_stays_latched_until_rechecked():
    h = _scenario("f12_mount_flapping")
    latched = _trace(h, 1500)  # mount_check says ok again, the latch does not
    assert _caps(latched) == ("off", "off") and "mount_latched" in latched.why
    assert _caps(_trace(h, 3400)) == ("off", "off")
    assert _caps(_trace(h, 3500)) == ("on", "on")  # right after mount_rechecked
    assert _status(h) == [("system_off", 3200), ("recovery", 5500)]


def test_f13_cut_in_has_no_grace_period_yet_but_keeps_the_confirmation_time():
    h = _scenario("f13_cut_in")
    assert _hazards(h, "warning") == [(2000, "d1")]  # T_confirm after the cut-in at 500 ms; the 1 s one is ignored
    assert [t for t, _ in _hazards(h, "warning", "baseline")] == [500, 3000]  # the baseline speaks at both


def test_f14_likely_id_switch_keeps_the_episode_and_a_missed_switch_warns_again():
    h = _scenario("f14_id_switch")
    assert _trace(h, 3000).distance_state == "ALERTED"  # new track id, same identity
    dark = _trace(h, 4000)  # observation unreliable turns both capabilities off, like unavailable (3.4)
    assert dark.distance_state == "HOLD" and _caps(dark) == ("off", "off") and "observation_unreliable" in dark.why
    assert _trace(h, 4400).distance_state == "ALERTED"  # same identity after 400 ms without observation
    assert _hazards(h, "warning") == [(1500, "d1"), (7500, "d2")]  # d2: A reported another identity (known limit)
    assert _status(h) == []


def test_f15_low_ttc_alerts_at_once_whatever_the_cause():
    h = _scenario("f15_low_ttc_causes")
    assert _hazards(h, "emergency") == [(1100, "e1"), (3600, "e2"), (5500, "e3")]  # never on unreliable TTC
    assert h.plans() == [("B-0", "started", 1100), ("B-1", "started", 3600), ("B-2", "started", 5500)]
    assert all(a.trigger.source == "frame" for a in h.alerts(kind="emergency"))


def test_f16_cut_in_does_not_delay_the_emergency():
    h = _scenario("f16_cut_in_then_low_ttc")
    assert _hazards(h, "emergency") == [(1300, "e1")]  # first frame with a valid TTC, 300 ms after the cut-in
    assert _hazards(h, "warning") == [(2500, "d1")]
    assert h.plans() == [("B-0", "started", 1300), ("B-1", "started", 2500)]


def test_f17_speed_outside_the_legal_table_only_stops_distance_warnings():
    h = _scenario("f17_speed_outside_table")
    tr = _trace(h, 3900)
    assert (tr.threshold_m.status, tr.threshold_m.reasons) == ("not_applicable", ["speed_outside_legal_table"])
    assert _caps(tr) == ("on", "on")  # out of scope, not a degradation: no status phrase
    assert _hazards(h, "warning") == [] and _hazards(h, "warning", "baseline") == [] and _status(h) == []
    assert _hazards(h, "emergency") == [(3000, "e1")]


def test_f18_overload_turns_only_the_collision_warning_off():
    h = _scenario("f18_overload_low_rate")
    assert _caps(_trace(h, 1800)) == ("on", "on")  # the last second still holds 6 frames
    slow = _trace(h, 2000)
    assert _caps(slow) == ("on", "off") and "low_rate" in slow.why  # 5 frames per second < min_ttc_rate_hz
    assert _hazards(h, "warning") == [(2600, "d1")]  # cap_distance is not affected
    assert _hazards(h, "emergency") == []  # TTC 1.5 s at 3000 ms: fail-safe
    assert _caps(_trace(h, 4200)) == ("on", "off") and _caps(_trace(h, 4300)) == ("on", "on")
    assert _status(h) == [("cap_ttc_off", 4000), ("recovery", 6300)]
    assert h.plans() == [("B-0", "started", 2600), ("B-1", "started", 4100), ("B-2", "started", 6300)]


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
    return AlertDecision(
        run_id="r",
        seq=n,
        t_ns=int(t_ms * MS),
        alert_id=f"B-{n}",
        arbiter="B",
        cls=cls,
        kind=kind,
        phrase_id=kind,
        trigger={"source": "frame", "input_seq": n},
        t_trigger_ns=int(t_ms * MS),
        t_decided_ns=int(t_ms * MS),
        capability_epoch=epoch,
        expires_t_ns=int((t_ms + 1500) * MS),
    )


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
    assert [(o.alert_id, o.outcome, o.t_ns) for o in out] == [("B-0", "started", 0), ("B-1", "started", 1400 * MS)]


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


def test_pending_slot_keeps_the_highest_priority_and_the_newer_of_equals():
    a = _arb()
    out = a.submit(_alert("emergency", "hazard", 0, 0), 0, epoch=0)  # plays 1200 ms
    out += a.submit(_alert("warning", "hazard", 100, 1), 100 * MS, epoch=0)  # waits
    out += a.submit(_alert("system_off", "status", 200, 2), 200 * MS, epoch=0)  # ranks below the waiting warning
    out += a.submit(_alert("warning", "hazard", 300, 3), 300 * MS, epoch=0)  # equal rank: the newer one stays
    out += a.advance(1200 * MS, epoch=0)
    assert [(o.alert_id, o.outcome, o.reasons) for o in out] == [
        ("B-0", "started", ()),
        ("B-2", "cancelled", ("lower_priority_than_pending",)),
        ("B-1", "cancelled", ("superseded",)),
        ("B-3", "started", ()),
    ]


def test_waiting_warning_is_cancelled_when_its_episode_stops_being_alerted():
    h = Harness()
    h.run(0, 3000, d_of_t=lambda t: 60.0 if t < 1600 else 80.0, ttc_of_t=lambda t: 1.5 if t == 1400 else None)
    # Emergency plays 1400..2600; the warning confirmed at 1500 waits behind it; the gap reopens at 1600
    assert h.plans() == [("B-0", "started", 1400), ("B-1", "cancelled", 1600)]
