import numpy as np
import pytest

from src.roadwatch.temporal import MIN_SAMPLES, MotionEstimator


def _feed(est, n, dt=.05, d0=40., rate=-3., noise=0., seed=0):
    rng = np.random.default_rng(seed)
    out = None
    for k in range(n):
        out = est.update(k * dt, d0 + rate * k * dt + rng.normal(0, noise), 1.)
    return out


def test_recovers_range_rate_from_a_noisy_distance_history():
    m = _feed(MotionEstimator(), 60, noise=.5)
    assert m.rate == pytest.approx(-3., abs=.6) and m.rate_std > 0
    assert m.dist == pytest.approx(40. - 3. * 59 * .05, abs=.5)


def test_a_cut_in_or_a_long_gap_restarts_the_history():
    est = MotionEstimator()
    _feed(est, 40)
    assert est.update(2.05, 10., 1.) is None          # 18 m jump: another vehicle
    est = MotionEstimator()
    _feed(est, 40)
    assert est.update(5., 30., 1.) is None            # 3 s without a lead: forget


def test_coasts_on_the_fitted_motion_through_a_short_drop_out():
    est = MotionEstimator()
    last = _feed(est, 40)                             # last sample at t = 1.95 s
    m = est.coast(2.15)
    assert m.dist == pytest.approx(last.dist - 3. * .2, abs=.05) and m.rate == pytest.approx(last.rate)
    assert est.coast(1.95 + .6) is None               # longer than MAX_GAP_S: no estimate
    assert MotionEstimator().coast(0.) is None


def test_weight_ramps_up_with_the_history():
    est = MotionEstimator()
    first = _feed(est, MIN_SAMPLES)
    assert 0 < first.weight < 1
    assert _feed(MotionEstimator(), 40).weight == 1.
