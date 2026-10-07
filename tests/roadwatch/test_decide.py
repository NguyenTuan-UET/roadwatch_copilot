from src.roadwatch.decide import GRACE_S, Decider, legal_gap

DT = 0.05


def test_legal_gap_follows_tt38_bands():
    assert legal_gap(50) is None and legal_gap(60) == 35 and legal_gap(80) == 55 and legal_gap(90) == 70
    assert legal_gap(110) == 100


def test_closing_gap_gives_info_then_warning():
    b, said = Decider(), []
    for i in range(400):   # 90 m closing at 3 m/s, 90 km/h (threshold 70 m)
        r = b.step(i * DT, max(40.0, 90 - 3 * i * DT), 25.0, None, True)
        said += [r.say] if r.say else []
    assert said[:2] == ['info', 'warning']


def test_cut_in_is_silent_during_grace():
    b = Decider()
    for i in range(100):
        b.step(i * DT, 80.0, 25.0, None, True)
    first = next(i * DT for i in range(100, 400) if b.step(i * DT, 35.0, 25.0, None, True).say == 'warning')
    assert first >= 5 + GRACE_S - DT


def test_emergency_fires_at_once_once_per_episode_even_in_congestion():
    b = Decider()
    assert b.step(0, 10.0, 10.0, 1.0, True).say == 'emergency'
    assert b.step(DT, 10.0, 10.0, 1.0, True).say is None


def test_no_distance_alert_before_calibration_but_emergency_still_fires():
    b = Decider()
    assert all(b.step(i * DT, 20.0, 25.0, None, False).say is None for i in range(200))
    assert b.step(10.0, 20.0, 25.0, 1.0, False).say == 'emergency'


def test_congestion_turns_distance_alerts_off():
    b = Decider()
    assert all(b.step(i * DT, 10.0, 40 / 3.6, None, True).say is None for i in range(400))
