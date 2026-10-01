import numpy as np
import pytest

from roadwatch.config import EvidenceConfig, RiskConfig, TrackerConfig
from roadwatch.perception.lanes import LaneState
from roadwatch.perception.speed_digits import SignReading
from roadwatch.risk import CorridorEstimator, EvidenceGate, RiskEngine, SignArbiter
from roadwatch.tracking import TrackedObject, estimate_kinematics

H, W = 720, 1280
FPS = 30.0
TCFG = TrackerConfig()


def track(tid, cls, boxes, t_end):
    """TrackedObject whose observed boxes are `boxes` (oldest first) ending at t_end."""
    n = len(boxes)
    hist = np.array([[t_end - (n - 1 - i) / FPS, *b] for i, b in enumerate(boxes)], float)
    kin = estimate_kinematics(hist, (H, W), TCFG.kin_window_s, TCFG.kin_min_points,
                              TCFG.kin_min_span_s, TCFG.border_margin_px)
    return TrackedObject(tid, tuple(boxes[-1]), cls, 0.9, True, n / FPS, 0, kin, hist)


def box_at(cx, bottom, size):
    return (cx - size / 2, bottom - size, cx + size / 2, bottom)


def drive(engine, make_tracks, seconds=1.5, **kw):
    """Run the engine for `seconds`; make_tracks(i, ts) -> tracks. Returns all results."""
    out = []
    for i in range(int(seconds * FPS)):
        ts = i / FPS
        out.append(engine.update(ts, (H, W), make_tracks(i, ts), **kw))
    return out


# -- evidence -------------------------------------------------------------------
def test_evidence_gate_needs_sustained_condition_and_holds():
    cfg = EvidenceConfig()
    g = EvidenceGate(cfg)
    levels = [g.update(i / FPS, 2) for i in range(15)]
    first = levels.index(2)
    assert 0.3 <= first / FPS <= 0.4  # confirm_s
    # A single-frame blip never confirms.
    g2 = EvidenceGate(cfg)
    assert max(g2.update(i / FPS, 2 if i == 5 else 0) for i in range(30)) == 0
    # Once active it is held for hold_s even if the condition vanishes.
    t0 = 15 / FPS
    held = [g.update(t0 + i / FPS, 0) for i in range(1, 60)]
    assert held[0] == 2
    off = held.index(0) + 1
    assert off / FPS >= cfg.release_s
    assert g.idle or held[-1] == 0


def test_evidence_gate_escalates_without_waiting_for_release():
    g = EvidenceGate(EvidenceConfig())
    for i in range(15):
        g.update(i / FPS, 1)
    assert g.level == 1
    lv = [g.update((15 + i) / FPS, 2) for i in range(15)]
    assert lv[-1] == 2


# -- corridor -------------------------------------------------------------------
def lane_state(left, right, quality=0.9, offset=0.0, rows=(0.7, 0.8, 0.9)):
    ys = [int(round(f * H)) for f in rows]
    return LaneState(list(left), list(right), offset, 1.0, quality, 0.3, ys)


def test_corridor_from_lane_learns_horizon():
    est = CorridorEstimator(RiskConfig())
    # Borders converging at (640, 360): x = 640 -+ k (y - 360).
    ys = [504, 576, 648]
    left = [640 - 1.5 * (y - 360) for y in ys]
    right = [640 + 1.5 * (y - 360) for y in ys]
    c = est.from_lane(lane_state(left, right), (H, W))
    assert c.source == "lane"
    assert c.horizon_y == pytest.approx(360, abs=1)
    assert c.lateral(640, 600) == pytest.approx(0.0)
    xl, xr = c.bounds(600)
    assert c.lateral(xr, 600) == pytest.approx(0.5)
    assert c.depth(H) == 1.0 and c.depth(360) == pytest.approx(0.0, abs=1e-9)
    assert c.bounds(300) is None


def test_default_corridor_is_centred():
    c = CorridorEstimator(RiskConfig()).default((H, W))
    assert c.source == "default"
    xl, xr = c.bounds(H)
    assert (xl + xr) / 2 == pytest.approx(W / 2)
    assert xr - xl == pytest.approx(2 * 0.3 * W)


# -- rules ----------------------------------------------------------------------
def closing_car(i, ts, tid=1, cls="car", cx=640.0, T=1.5):
    """A car in the ego path approaching at constant speed: contact at ts = T (+1 s history)."""
    boxes = []
    for k in range(20):
        t = ts - (19 - k) / FPS
        size = 60.0 / max(T + 1.0 - (t + 1.0), 0.05) * 0.5
        size = min(size, 400)
        boxes.append(box_at(cx, 400 + size, size))
    return track(tid, cls, boxes, ts)


def test_fcw_warns_for_a_closing_lead_vehicle():
    eng = RiskEngine(RiskConfig())
    res = drive(eng, lambda i, ts: [closing_car(i, ts)], seconds=1.0)
    levels = [r.level for r in res]
    assert "warning" in levels
    ev = next(e for r in res for e in r.events if e.kind == "fcw")
    assert ev.track_id == 1 and ev.evidence["tau_s"] is not None and "(est.)" in ev.label
    assert res[-1].track_levels.get(1) in ("caution", "warning")


def test_fcw_quiet_for_a_steady_lead_vehicle():
    eng = RiskEngine(RiskConfig())
    steady = lambda i, ts: [track(1, "car", [box_at(640, 560, 120)] * 20, ts)]
    assert all(not r.events for r in drive(eng, steady, seconds=1.5))


def test_fcw_ignores_vehicles_outside_the_corridor():
    eng = RiskEngine(RiskConfig())
    res = drive(eng, lambda i, ts: [closing_car(i, ts, cx=80)], seconds=1.0)
    assert not any(e.kind == "fcw" for r in res for e in r.events)


def test_vru_riders_are_not_pedestrians():
    tracks = [track(1, "motorcycle", [box_at(640, 700, 150)] * 10, 1.0),
              track(2, "person", [(590, 480, 690, 640)] * 10, 1.0),
              track(3, "person", [box_at(1000, 700, 150)] * 10, 1.0)]
    assert RiskEngine._riders(tracks, 0.3) == {2}


def test_vru_near_in_path_is_a_caution_even_without_closing():
    eng = RiskEngine(RiskConfig())
    near = lambda i, ts: [track(7, "person", [box_at(640, 690, 200)] * 20, ts)]
    res = drive(eng, near, seconds=1.0)
    assert res[-1].events and res[-1].events[0].kind == "vru"
    assert res[-1].events[0].level == "caution" and res[-1].events[0].track_id == 7


def lateral_car(ts, speed_px_s, start_x, cls="car", bottom=600, size=150):
    boxes = [box_at(start_x + speed_px_s * (ts - (19 - k) / FPS), bottom, size) for k in range(20)]
    return track(3, cls, boxes, ts)


def test_cut_in_from_the_adjacent_lane():
    eng = RiskEngine(RiskConfig())
    # Corridor at y=600 (default, horizon 360): x in [~352, ~928], width ~576 px.
    # Car centre starts at 1150 (box edge ~1075, gap ~0.26 lane widths) and moves left at
    # ~0.35 lane widths/s -> enters in ~0.7 s.
    res = drive(eng, lambda i, ts: [lateral_car(ts, -200, 1150 - 0 * ts)], seconds=0.8)
    kinds = {e.kind for r in res for e in r.events}
    assert kinds == {"cut_in"}


def test_crossing_vehicle_is_cross_traffic():
    eng = RiskEngine(RiskConfig())
    res = drive(eng, lambda i, ts: [lateral_car(ts, -700, 1250)], seconds=0.8)
    kinds = {e.kind for r in res for e in r.events}
    assert "cross" in kinds and "cut_in" not in kinds


def test_vehicle_moving_away_from_the_corridor_is_quiet():
    eng = RiskEngine(RiskConfig())
    res = drive(eng, lambda i, ts: [lateral_car(ts, +200, 1100)], seconds=1.0)
    assert not any(r.events for r in res)


# -- LDW ------------------------------------------------------------------------
def test_ldw_warns_on_outward_drift_with_a_good_lane():
    eng = RiskEngine(RiskConfig())
    ys = [504, 576, 648]
    left = [640 - 1.5 * (y - 360) for y in ys]
    right = [640 + 1.5 * (y - 360) for y in ys]
    res = []
    for i in range(60):
        ts = i / FPS
        lane = lane_state(left, right, offset=0.1 + 0.3 * ts)
        res.append(eng.update(ts, (H, W), [], lane=lane, lane_seq=i, lane_age_s=0.0))
    ldw = [e for r in res for e in r.events if e.kind == "ldw"]
    assert ldw and ldw[-1].evidence["side"] == "right" and res[-1].level == "warning"
    assert res[-1].lane_used and res[-1].corridor.source == "lane"


def test_ldw_gated_by_lane_quality_and_freshness():
    for quality, age in ((0.3, 0.0), (0.9, 2.0)):
        eng = RiskEngine(RiskConfig())
        ys = [504, 576, 648]
        left = [640 - 1.5 * (y - 360) for y in ys]
        right = [640 + 1.5 * (y - 360) for y in ys]
        res = [eng.update(i / FPS, (H, W), [],
                          lane=lane_state(left, right, quality=quality, offset=0.1 + 0.3 * i / FPS),
                          lane_seq=i, lane_age_s=age) for i in range(60)]
        assert not any(r.events for r in res)
        assert res[-1].corridor.source == "default"


# -- signs ----------------------------------------------------------------------
def reading(value, x=1000, y=200, size=40, det_conf=0.8, cls_conf=None, agree=None,
            group="speed_limit", code="127", cls=None):
    return SignReading((x, y, x + size, y + size), cls or f"127-toc-do-toi-da-{value}", det_conf,
                       value, cls_conf, "digit_classifier" if cls_conf is not None else
                       "detector_class", agree, code, group, "")


def feed(arb, per_result, n, start_seq=0, t0=0.0, dt=0.1):
    state = None
    for k in range(n):
        state = arb.update(t0 + k * dt, per_result(k), start_seq + k, (H, W))
    return state


def test_speed_limit_needs_confirmation_and_persists():
    arb = SignArbiter(RiskConfig())
    assert feed(arb, lambda k: [reading(50)], 2).speed_limit is None
    st = feed(arb, lambda k: [reading(50)], 1, start_seq=2, t0=0.2)
    assert st.speed_limit.value == 50 and [c.speed_value for c in st.new] == [50]
    # The sign passes: the limit stays.
    st = feed(arb, lambda k: [], 30, start_seq=3, t0=0.3)
    assert st.speed_limit.value == 50


def test_reused_sign_result_counts_once():
    arb = SignArbiter(RiskConfig())
    for i in range(10):  # same sign result (seq 0) on 10 frames
        st = arb.update(i / FPS, [reading(50)], 0, (H, W))
    assert st.speed_limit is None


def test_left_side_and_tiny_signs_are_not_relevant():
    arb = SignArbiter(RiskConfig())
    assert feed(arb, lambda k: [reading(50, x=100, y=400)], 5).speed_limit is None
    assert feed(arb, lambda k: [reading(50, size=8)], 5, start_seq=10).speed_limit is None
    # Overhead gantry on the left half is fine.
    assert feed(arb, lambda k: [reading(50, x=300, y=40)], 5, start_seq=20).speed_limit.value == 50


def test_speed_value_arbitration_prefers_confident_classifier_readings():
    arb = SignArbiter(RiskConfig())
    st = feed(arb, lambda k: [reading(60, cls_conf=0.95, agree=True, det_conf=0.9)] if k % 3
              else [reading(80, det_conf=0.5)], 9)
    assert st.speed_limit.value == 60


def test_close_conflict_keeps_the_limit_and_flags_ambiguity():
    arb = SignArbiter(RiskConfig())
    feed(arb, lambda k: [reading(50)], 4)
    st = feed(arb, lambda k: [reading(60)] if k % 2 else [reading(50)], 12, start_seq=4, t0=0.4)
    assert st.speed_limit.value == 50  # 60 never beats 50 by the margin
    arb2 = SignArbiter(RiskConfig())
    st = feed(arb2, lambda k: [reading(60), reading(40, x=900)], 6)
    assert st.speed_limit is None  # tie: nothing is set


def test_end_sign_clears_the_limit():
    arb = SignArbiter(RiskConfig())
    feed(arb, lambda k: [reading(50)], 4)
    end = SignReading((1000, 200, 1040, 240), "134-het-han-che-toc-do-toi-da", 0.8, None, None,
                      "detector_class", None, "134", "speed_limit_end", "")
    st = feed(arb, lambda k: [end], 4, start_seq=10, t0=3.0)
    assert st.speed_limit is None and any(c.code == "134" for c in st.recent)


def test_reset_clears_all_risk_state():
    eng = RiskEngine(RiskConfig())
    drive(eng, lambda i, ts: [closing_car(i, ts)], seconds=1.0)
    feed(eng.signs, lambda k: [reading(50)], 4)
    eng.reset()
    r = eng.update(0.0, (H, W), [])
    assert r.events == [] and r.speed_limit is None and r.corridor.source == "default"


def test_fcw_ignores_a_car_being_passed_in_the_next_lane():
    """Its box reaches into the corridor (visible side) but its centre is outside."""
    eng = RiskEngine(RiskConfig())
    # Default corridor at y=600: x in ~[352, 928]; box centre at 300, right edge ~390.
    res = drive(eng, lambda i, ts: [closing_car(i, ts, cx=300, T=1.2)], seconds=1.0)
    assert not any(e.kind == "fcw" for r in res for e in r.events)


def test_bike_alongside_entering_the_frame_is_not_a_cut_in():
    """Box cut by the right and bottom borders grows leftward as the bike comes into view:
    its centre moves toward the corridor, but nothing real is moving sideways."""
    eng = RiskEngine(RiskConfig())

    def alongside(i, ts):
        boxes = [(1250 - 150 * (ts - (19 - k) / FPS), 520, W, H) for k in range(20)]
        return [track(4, "motorcycle", boxes, ts)]

    assert not any(r.events for r in drive(eng, alongside, seconds=1.0))
