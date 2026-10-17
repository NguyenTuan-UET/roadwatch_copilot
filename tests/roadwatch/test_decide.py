"""BT-B by docs/warning_to_do.md: distance only (no TTC), early reminder, short sounds when urgent, repeats that follow
how the gap evolves. The checks below are the test list of that plan, step 1."""
import pytest

from src.roadwatch.decide import Decider, legal_gap, thresholds

DT = 0.05


def says(dec, t0, t1, gap, kmh, dt=DT, calibrated=True, ok=True):
    """Run dec from t0 to t1; gap is a number, None (no lead) or a function of t. Returns [(t, kind spoken)]."""
    out = []
    for i in range(round((t1 - t0) / dt)):
        t = t0 + i * dt
        d = dec.step(t, gap(t) if callable(gap) else gap, kmh / 3.6, calibrated, ok)
        if d.say:
            out.append((round(t, 2), d.say))
    return out


def test_legal_gap_follows_tt38_bands():
    assert legal_gap(50) is None and legal_gap(60) == 35 and legal_gap(80) == 55 and legal_gap(90) == 70
    assert legal_gap(110) == 100


def test_thresholds_match_the_plan_examples():
    def near(kmh, early, warn, short):
        e, w, s = thresholds(kmh)
        assert (e is None if early is None else e == pytest.approx(early, abs=0.1)), kmh
        assert (w, s) == pytest.approx((warn, short), abs=0.1), kmh
    near(50, 41.7, 27.8, 13.9)          # 3 s / 2 s of own travel
    near(80, 69.9, 55.0, 27.5)          # legal gap + 15 % + 0.3 s latency
    near(100, 88.8, 70.0, 35.0)
    near(110, None, 61.1, 30.6)         # early zone beyond the 100 m the model measures: chime on sight
    assert thresholds(3) is None and thresholds(12) is None   # standing still, crawling: silent for now


def test_standing_or_crawling_close_behind_a_car_says_nothing():
    assert says(Decider(), 0, 60, 4.0, 0) == []
    assert says(Decider(), 0, 60, 6.0, 12) == []


def test_closing_in_at_50_kmh_goes_up_one_level_at_a_time():
    spoken = [k for _, k in says(Decider(), 0, 25, lambda t: max(8.0, 60 - 3 * t), 50)]
    rank = {'info': 1, 'warning': 2, 'emergency': 3}
    assert list(dict.fromkeys(spoken)) == ['info', 'warning', 'emergency']
    assert [rank[k] for k in spoken] == sorted(rank[k] for k in spoken)   # never back to a lower level while closing


def test_lead_appearing_very_close_beeps_without_grace():
    dec = Decider()
    assert says(dec, 0, 2, None, 50) == []
    t, kind = says(dec, 2, 6, 10.0, 50)[0]
    assert kind == 'emergency' and t - 2 <= 0.5 + 1e-9   # only the 0.5 s lead confirmation, no 4 s cut-in grace


def test_high_speed_chimes_once_per_lead_even_after_a_short_loss():
    dec = Decider()
    out = says(dec, 0, 5, 95.0, 110) + says(dec, 5, 6, None, 110) + says(dec, 6, 11, 95.0, 110)
    out += says(dec, 11, 16, None, 110) + says(dec, 16, 20, 95.0, 110)   # lost 5 s: a new lead, a new chime
    assert out == [(0.5, 'chime'), (16.5, 'chime')]


def test_high_speed_lead_first_seen_far_too_close_beeps_instead_of_chiming():
    assert says(Decider(), 0, 2, 25.0, 110) == [(0.5, 'emergency')]


def test_staying_too_close_repeats_after_3_s_then_every_10_s():
    out = says(Decider(), 0, 25, 20.0, 50)
    assert [k for _, k in out] == ['warning'] * 4
    assert [t for t, _ in out] == pytest.approx([0.5, 3.5, 13.5, 23.5], abs=0.06)


def test_no_repeat_while_the_gap_is_opening():
    assert says(Decider(), 0, 15, lambda t: 16 + t, 50) == [(0.5, 'warning')]


def test_gap_falling_fast_escalates_at_once():
    out = says(Decider(), 0, 6, lambda t: 40.0 if t < 2 else 40 - 6 * (t - 2), 50)
    assert out[0] == (0.5, 'info')
    t_e = next(t for t, k in out if k == 'emergency')
    assert t_e - 2 < 2.0                                       # well before the 3 s repeat, before the warning gap
    assert 'warning' not in [k for t, k in out if t < t_e]


def test_one_jumping_frame_keeps_the_episode():
    out = says(Decider(), 0, 4, lambda t: 60.0 if abs(t - 2) < 1e-6 else 20.0, 50)
    assert out == [(0.5, 'warning'), (3.5, 'warning')]         # the repeat schedule, not a new episode at 2.55 s


def test_episode_ends_after_3_s_clear_of_the_early_zone():
    dec = Decider()
    out = says(dec, 0, 1, 20.0, 50) + says(dec, 1, 4.5, 50.0, 50) + says(dec, 4.5, 6, 20.0, 50)
    assert out == [(0.5, 'warning'), (5.0, 'warning')]


def first_says(dt):
    out = says(Decider(), 0, 20, lambda t: 90 - 3 * t, 80, dt=dt)
    return {k: next(t for t, s in out if s == k) for k in ('info', 'warning')}


def test_when_it_speaks_does_not_depend_on_the_frame_rate():
    """12 fps (phone GPU) speaks when 20 fps does: confirmations and the gap rate run on the frame clock."""
    slow, fast = first_says(1 / 12), first_says(DT)
    assert all(abs(slow[k] - fast[k]) < 0.2 for k in fast)


def test_silent_before_calibration_or_on_unreliable_frames():
    assert says(Decider(), 0, 10, 10.0, 50, calibrated=False) == []
    assert says(Decider(), 0, 10, 10.0, 50, ok=False) == []
