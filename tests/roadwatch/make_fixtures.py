"""Regenerate the generated fixtures after a contract change (spec 4.6, code-rules 9, WP-C3, WP-B9).

`python -m tests.roadwatch.make_fixtures`            everything below
`python -m tests.roadwatch.make_fixtures runs`       fixtures/valid/{replay,live}/ from the clip of test_runtime.py
`python -m tests.roadwatch.make_fixtures scenarios`  fixtures/scenarios/<name>/: what B consumes in a failure
                                                     situation of spec 6 (F1-F18), built by the scripts below

The invalid fixtures are small hand-edited folders: fix those by hand when a schema changes.
What B must do with each scenario is asserted in test_decision.py, not stored here.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from tests.roadwatch.decision_harness import Harness, make_config

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "valid"
SCENARIOS = FIXTURES / "scenarios"


def runs() -> None:
    from src.roadwatch.runtime import run  # imported here: the scenarios need neither the runtime nor OpenCV
    from tests.roadwatch.test_runtime import make_inputs

    inp = make_inputs(Path(tempfile.mkdtemp()))
    inp.play = lambda phrase: None  # live mode without a speaker
    for mode in ("replay", "live"):
        inp.mode = mode
        shutil.rmtree(VALID / mode, ignore_errors=True)
        shutil.copytree(run(inp), VALID / mode)


# --- scenarios: 10 Hz frames, a tick after each frame time, GPS at 1 Hz and 90 km/h (70 m band) unless said ----


def _near(t):
    return 60.0  # below the 70 m threshold


def f01_placeholder_frames(h: Harness) -> None:
    h.run(0, 2000, d_of_t=_near)
    h.run(2000, 4500, obs="unavailable")  # the source knows there is no frame: placeholder records
    h.run(4500, 7300, d_of_t=_near)


def f02_dropped_frames(h: Harness) -> None:
    h.run(0, 3000, d_of_t=_near)
    h.speed(3000, 90)
    for t in (3000, 3100, 3200):  # short burst: three frames dropped
        h.event(t, "frame_dropped", reasons=("overload",), sched_n=t // 100)
        h.tick(t)
    h.run(3300, 4000, d_of_t=_near)
    for t in range(4000, 5500, 100):  # long burst: 1.5 s without a measurement
        if t % 1000 == 0:
            h.speed(t, 90)
        h.event(t, "frame_dropped", reasons=("overload",), sched_n=t // 100)
        h.tick(t)
    h.run(5500, 6500, d_of_t=_near)


def f03_f19_hang_then_fault(h: Harness) -> None:
    h.run(0, 1100, ttc_of_t=lambda t: 1.5 if t == 1000 else None)  # the last measurement is at 1000 ms
    for t in range(1100, 4500, 100):  # perception hangs: only ticks arrive, then the supervisor reports it
        if t % 1000 == 0:
            h.speed(t, 90)
        if t == 3100:
            h.event(t, "system_fault", reasons=("perception_hung",), thread="perception")
        h.tick(t)


def f04_late_measurements(h: Harness) -> None:
    h.run(0, 3000, d_of_t=_near)
    h.speed(3000, 90, consumed_ms=4000)
    for t in range(3000, 4000, 100):  # decision stalls until 4000 ms, then consumes its backlog in order
        h.meas(t, d=60.0, ttc=1.5 if t == 3200 else None, consumed_ms=4000)
        h.tick(t, consumed_ms=4000)
    h.run(4000, 5000, d_of_t=_near)


def f07_f08_speed_stale_then_lost(h: Harness) -> None:
    for t in range(0, 8400, 100):
        if t in (0, 1000):
            h.speed(t, 90)
        if t == 2000:  # the GPS queue was full: this sample never reaches B, and none follows
            h.event(t, "speed_dropped", reasons=("queue_full",), gps_idx=2)
        h.meas(t, d=60.0, ttc=1.2 if t == 7000 else None)
        h.tick(t)


def f10_mount_suspect(h: Harness) -> None:
    h.run(0, 1600, d_of_t=_near)
    h.run(1600, 4000, d_of_t=_near, mount="suspect", ttc_of_t=lambda t: 1.5 if t == 2500 else None)
    h.run(
        4000, 6300, d_of_t=_near, mount="suspect", basis="lane_markings", ttc_of_t=lambda t: 1.5 if t == 5000 else None
    )


def f11_mount_unknown(h: Harness) -> None:
    h.run(0, 4500, d_of_t=_near, mount="unknown")  # trusted for trust_window after the checklist, then not
    h.run(4500, 6800, d_of_t=_near, mount="ok")


def f11_mount_unknown_no_checklist(h: Harness) -> None:
    h.run(0, 2500, d_of_t=_near, mount="unknown")


def f12_mount_flapping(h: Harness) -> None:
    for k in range(3):  # three suspect periods inside the flap window latch the check
        h.run(600 * k, 600 * k + 300, mount="suspect")
        h.run(600 * k + 300, 600 * k + 600, mount="ok")
    h.run(1800, 3500, mount="ok")
    h.event(3500, "mount_rechecked", reasons=("operator",))
    h.run(3500, 5800, mount="ok")


def f13_cut_in(h: Harness) -> None:
    h.run(0, 500, lead_id=1)
    h.run(500, 2500, d_of_t=lambda t: 35.0, lead_id=2, change="entered_from_right", change_t_ms=500)
    h.run(2500, 3000, lead_id=1, change="previous_lead_left", change_t_ms=2500)
    h.run(3000, 4000, d_of_t=lambda t: 35.0, lead_id=3, change="entered_from_left", change_t_ms=3000)  # 1 s only
    h.run(4000, 4500, lead_id=1, change="previous_lead_left", change_t_ms=4000)


def f14_id_switch(h: Harness) -> None:
    h.run(0, 3000, d_of_t=_near, lead_id=1, track_id=7)
    h.run(3000, 4000, d_of_t=_near, lead_id=1, track_id=9, change="likely_id_switch", change_t_ms=3000)
    h.run(4000, 4400, obs="unreliable")  # too dark for 400 ms, the track is lost meanwhile
    h.run(4400, 6000, d_of_t=_near, lead_id=1, track_id=11, change="likely_id_switch", change_t_ms=4400)
    h.run(6000, 8000, d_of_t=_near, lead_id=12, track_id=12, change="unknown", change_t_ms=6000)  # A missed it


def f15_low_ttc_causes(h: Harness) -> None:
    brake = {900: 2.6, 1000: 2.2, 1100: 1.7, 1200: 2.0, 1300: 2.5}
    for t in range(0, 3000, 100):  # lead 1 brakes hard; TTC is not valid for its first frames
        if t % 1000 == 0:
            h.speed(t, 90)
        if 500 <= t <= 800:
            h.meas(t, lead_id=1, ttc=1.5, ttc_status="unreliable")
        else:
            h.meas(t, lead_id=1, ttc=brake.get(t))
        h.tick(t)
    slower = {3000: 4.0, 3100: 3.6, 3200: 3.2, 3300: 2.8, 3400: 2.4, 3500: 2.0, 3600: 1.6}
    h.run(3000, 5500, lead_id=2, ttc_of_t=slower.get, change="previous_lead_left", change_t_ms=3000)  # closing in
    h.run(5500, 6000, lead_id=3, ttc_of_t={5500: 1.2}.get, change="appeared_ahead", change_t_ms=5500)  # queue tail


def f16_cut_in_then_low_ttc(h: Harness) -> None:
    h.run(0, 1000, lead_id=1)
    for t in range(1000, 3500, 100):  # cut-in 20 m ahead; its TTC becomes valid at 1300 ms
        if t % 1000 == 0:
            h.speed(t, 90)
        ttc = dict(ttc=1.4, ttc_status="unreliable") if t <= 1200 else dict(ttc=1.4 if t == 1300 else None)
        h.meas(t, d=20.0, lead_id=2, change="entered_from_left", change_t_ms=1000, **ttc)
        h.tick(t)


def f17_speed_outside_table(h: Harness) -> None:
    h.run(0, 4000, d_of_t=lambda t: 10.0, ttc_of_t=lambda t: 1.5 if t == 3000 else None, kmh=40.0)


def f18_overload_low_rate(h: Harness) -> None:
    h.run(0, 1000)
    for t in range(1000, 4200, 100):  # overload: every other frame is dropped, 5 frames per second remain
        if t % 1000 == 0:
            h.speed(t, 90)
        if t % 200 == 0:
            h.meas(t, d=60.0, ttc=1.5 if t == 3000 else None)
        else:
            h.event(t, "frame_dropped", reasons=("overload",), sched_n=t // 100)
        h.tick(t)
    h.run(4200, 6600, d_of_t=_near)


# name -> (rows of spec 6.1, what the streams describe, harness options)
SCENARIO_LIST = {
    f01_placeholder_frames: ("F1", "Frames known to be missing: placeholder measurements for 2.5 s", {}),
    f02_dropped_frames: ("F2", "Frames dropped under overload: a 0.4 s gap, then a 1.6 s gap", {}),
    f03_f19_hang_then_fault: ("F3, F19", "Perception hangs: only ticks arrive, then system_fault", {}),
    f04_late_measurements: ("F4", "Measurements consumed up to 1 s late after a stall of decision", {}),
    f07_f08_speed_stale_then_lost: ("F7a, F7b, F8", "A GPS sample is dropped and none follows", {}),
    f10_mount_suspect: ("F10", "Camera knocked during the trip: mount_check suspect", {}),
    f11_mount_unknown: (
        "F11",
        "mount_check unknown past the trust window (2 s here)",
        {"config": {"perception": {"mount_trust_window_ms": 2000}}},
    ),
    f11_mount_unknown_no_checklist: ("F11", "mount_check unknown and no mount checklist", {"checklist": False}),
    f12_mount_flapping: ("F12", "Mount check flaps three times, stays latched until rechecked", {}),
    f13_cut_in: ("F13", "Cut-ins: one that stays below the threshold, one that leaves after 1 s", {}),
    f14_id_switch: ("F14", "Track id changes for the same vehicle; A recognises two of three switches", {}),
    f15_low_ttc_causes: ("F15", "Low TTC from a hard brake, a slower lead and a queue tail", {}),
    f16_cut_in_then_low_ttc: ("F16", "Close cut-in whose TTC is low as soon as it is valid", {}),
    f17_speed_outside_table: ("F17", "40 km/h: outside the legal table (out of MVP scope)", {}),
    f18_overload_low_rate: ("F18", "CPU overload: 5 frames per second for 3 s", {}),
}


def scenarios() -> None:
    shutil.rmtree(SCENARIOS, ignore_errors=True)
    for script, (spec, describes, opts) in SCENARIO_LIST.items():
        config, checklist = opts.get("config", {}), opts.get("checklist", True)
        h = Harness(make_config(**config), checklist=checklist)
        script(h)
        h.dump(
            SCENARIOS / script.__name__,
            spec=spec,
            describes=describes,
            config=config,
            mount_checklist=checklist,
            driver_mode="experienced",
        )


def main() -> None:
    for name in sys.argv[1:] or ("runs", "scenarios"):
        {"runs": runs, "scenarios": scenarios}[name]()


if __name__ == "__main__":
    main()
