"""Live runtime (spec §3.1, §3.2, §3.8): paced threads, bounded queues that drop-and-record, supervisor, audio sink.

Live never blocks the hot path: full queues drop the oldest item and log it. It is not reproducible by design;
its logs still reproduce B exactly through rerun-B (spec 5.4).
"""

import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .configread import ConfigError
from .contracts.base import Record
from .contracts.config import RwConfig
from .contracts.streams import AlertDecision, AudioPlan, Measurement, SpeedSample
from .decision.stage import DecisionStage
from .perception import Perception
from .runtime import MS, Events, Journal, RunInputs, RunWriter, audio_event
from .source import video_frames

DONE = object()
WATCHED = ("source", "perception", "decision")


def default_play(phrase_dir: str) -> Callable[[str], None]:
    """The speaker of this machine: winsound on Windows, `aplay` (ALSA) on Linux. No backend, no run (D-1)."""
    if sys.platform == "win32":
        import winsound  # stdlib; async play replaces whatever is playing (= preemption)

        def play(phrase_id: str) -> None:
            winsound.PlaySound(
                str(Path(phrase_dir) / f"{phrase_id}.wav"),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )

        return play
    aplay = shutil.which("aplay") if sys.platform.startswith("linux") else None
    if aplay is None:
        raise ConfigError(
            f"no audio backend on {sys.platform}: live plays WAV through winsound (Windows) or aplay "
            "(Linux, package alsa-utils); run with a stand-in sink (`--audio simulated`) to go without a speaker"
        )
    playing: list[subprocess.Popen] = []

    # TODO(integration): written on Windows; play one phrase on the Linux demo machine before trusting it.
    def play(phrase_id: str) -> None:
        for p in playing:  # a new phrase replaces the one being played (= preemption, like SND_ASYNC)
            p.terminate()
        playing[:] = [subprocess.Popen([aplay, "-q", str(Path(phrase_dir) / f"{phrase_id}.wav")])]

    return play


def _put_drop_oldest(q: queue.Queue, item, on_drop: Callable) -> None:
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                on_drop(q.get_nowait())
            except queue.Empty:
                pass


def run_live(
    inp: RunInputs,
    cfg: RwConfig,
    run_id: str,
    gps: list[SpeedSample],
    stage: DecisionStage,
    perception: Perception,
    writer: RunWriter,
    run_dir: Path,
    play: Callable[[str], None],
    recorded: list[Measurement] | None = None,
) -> list[str]:
    rt = cfg.runtime
    tick_ns = rt.tick_period_ms * MS
    mono0 = time.monotonic_ns()

    def session_now() -> int:
        return time.monotonic_ns() - mono0

    events = Events(run_id)
    logq: queue.Queue = queue.Queue(maxsize=rt.q_log)
    overflow = threading.Event()
    frames_q: queue.Queue = queue.Queue(maxsize=1)
    meas_q: queue.Queue = queue.Queue(maxsize=rt.q_measure)
    speed_q: queue.Queue = queue.Queue(maxsize=rt.q_speed)
    event_q: queue.Queue = queue.Queue()
    sink_q: queue.Queue = queue.Queue()
    watched = ("source", "decision") if recorded else WATCHED
    heart = {name: time.monotonic_ns() for name in watched}
    finished: set[str] = set()
    stop = threading.Event()

    def log(item) -> None:
        try:
            logq.put_nowait(item)
        except queue.Full:
            overflow.set()  # never block the hot path; the run is flagged log_incomplete

    def event(kind: str, reasons: list[str], **detail) -> None:
        e = events.make(kind, session_now(), reasons, **detail)
        log(e)
        event_q.put(e)

    def wait_until(t_session: int) -> None:
        while not stop.is_set():
            left = t_session - session_now()
            if left <= 0:
                return
            time.sleep(min(left / 1e9, 0.05))

    def source() -> None:
        for s_n, meta, img in video_frames(inp.video, rt.process_hz, run_id, inp.session.video_sha256):
            wait_until(s_n)
            if stop.is_set():
                break
            heart["source"] = time.monotonic_ns()
            meta = meta.model_copy(update={"t_arrive_mono_ns": mono0 + (meta.t_ns if meta.status == "ok" else s_n)})
            log(meta)
            _put_drop_oldest(
                frames_q,
                (meta, img, time.monotonic_ns()),
                lambda old: event("frame_dropped", ["overload"], sched_n=old[0].sched_n),
            )
        # never block, even if perception is dead and the queue is full
        _put_drop_oldest(frames_q, DONE, lambda old: event("frame_dropped", ["end_of_run"], sched_n=old[0].sched_n))

    def hand_over() -> None:
        """A ran elsewhere: each of its measurements arrives at its own session time (takes the source's place)."""
        for m in recorded:
            wait_until(m.t_ns)
            if stop.is_set():
                break
            heart["source"] = time.monotonic_ns()
            log(m)
            _put_drop_oldest(
                meas_q, (m, None), lambda old: event("measurement_dropped", ["overload"], sched_n=old[0].sched_n)
            )
        meas_q.put(DONE)

    def gps_player() -> None:
        for s in gps:
            wait_until(s.t_recv_ns)
            if stop.is_set():
                break
            _put_drop_oldest(speed_q, s, lambda old: event("speed_dropped", ["queue_full"], gps_idx=old.gps_idx))

    def perceive() -> None:
        seq = 0
        while True:
            heart["perception"] = time.monotonic_ns()
            try:
                item = frames_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is DONE:
                meas_q.put(DONE)
                return
            meta, img, t_decoded = item
            t0 = time.monotonic_ns()
            if meta.status == "ok":
                m = perception.process(img, meta.t_ns, meta.sched_n, meta.frame_idx, run_id, seq)
            else:
                m = perception.placeholder(meta.t_ns, meta.sched_n, run_id, seq)
            seq += 1
            log(m)
            perf = {
                "sched_n": meta.sched_n,
                "frame_idx": meta.frame_idx,
                "t_arrive_mono_ns": meta.t_arrive_mono_ns,
                "t_decoded_mono_ns": t_decoded,
                "t_infer_start_mono_ns": t0,
                "t_measure_out_mono_ns": time.monotonic_ns(),
            }
            _put_drop_oldest(
                meas_q, (m, perf), lambda old: event("measurement_dropped", ["overload"], sched_n=old[0].sched_n)
            )

    alerts: dict[str, AlertDecision] = {}

    def emit(rec: Record) -> None:
        log(rec)
        if isinstance(rec, AlertDecision) and rec.arbiter == inp.active_arbiter:
            alerts[rec.alert_id] = rec
        elif isinstance(rec, AudioPlan) and rec.arbiter == inp.active_arbiter and rec.outcome == "started":
            sink_q.put(alerts[rec.alert_id])

    def decide() -> None:
        journal = Journal(stage, emit, run_id)
        next_tick = 0
        while True:
            heart["decision"] = time.monotonic_ns()
            while not event_q.empty():
                e = event_q.get_nowait()
                journal.feed("event", e.t_ns, session_now(), e)
            while not speed_q.empty():
                s = speed_q.get_nowait()
                log(s)
                journal.feed("speed", s.t_ns, session_now(), s)
            while next_tick <= session_now():
                journal.feed("tick", next_tick, session_now(), tick_n=next_tick // tick_ns)
                next_tick += tick_ns
            try:
                item = meas_q.get(timeout=tick_ns / 1e9)
            except queue.Empty:
                continue
            if item is DONE:
                return
            m, perf = item
            journal.feed("measurement", m.t_ns, session_now(), m)
            if perf is not None:  # no stage timing for a measurement that was handed over
                perf["t_decision_mono_ns"] = time.monotonic_ns()
                log(("perf", json.dumps(perf)))

    def sink() -> None:
        seq = 0
        while True:
            a = sink_q.get()
            if a is DONE:
                return
            now = session_now()
            if now > a.expires_t_ns:
                outcome, t_mono = "dropped_stale", time.monotonic_ns()  # counted as a latency violation
            else:
                t_mono = time.monotonic_ns()
                try:
                    play(a.phrase_id)
                    outcome = "started"
                except Exception as ex:  # noqa: BLE001 - any device error means no audio (F20)
                    outcome = "fault"
                    event("audio_fault", [type(ex).__name__])
            log(audio_event(run_id, seq, now, a.alert_id, outcome, t_mono))
            seq += 1

    def logger() -> None:
        while True:
            item = logq.get()
            if item is DONE:
                return
            if isinstance(item, tuple):
                writer.write(*item)
            else:
                writer.record(item)

    errors: dict[str, str] = {}

    def guarded(name: str, fn: Callable) -> Callable:
        def body():
            try:
                fn()
                finished.add(name)  # only a normal return counts; a crash leaves the thread dead and unfinished
            except Exception as ex:  # noqa: BLE001 - recorded for the supervisor's system_fault event
                errors[name] = f"{type(ex).__name__}: {ex}"

        return body

    start = events.make("run_start", 0)
    log(start)
    event_q.put(start)
    threads = {
        name: threading.Thread(target=guarded(name, fn), name=name, daemon=True)
        for name, fn in (
            *((("source", hand_over),) if recorded else (("source", source), ("perception", perceive))),
            ("gps", gps_player),
            ("decision", decide),
            ("sink", sink),
            ("logger", logger),
        )
    }
    for t in threads.values():
        t.start()

    faulted = drained = False
    last_hb = 0
    while threads["decision"].is_alive():  # supervisor (spec 3.8)
        time.sleep(0.1)
        now = time.monotonic_ns()
        for name in watched:
            dead = not threads[name].is_alive() and name not in finished
            hung = name not in finished and now - heart[name] > rt.hang_timeout_ms * MS
            if (dead or hung) and not faulted:
                faulted = True
                event("system_fault", [f"{name}_{'dead' if dead else 'hung'}"], thread=name, error=errors.get(name))
        source_over = "source" in finished or not threads["source"].is_alive()
        if faulted and source_over and not drained:  # a dead stage never sends DONE; end the recorded run
            drained = True
            stop.set()
            meas_q.put(DONE)
        if now - last_hb > 1_000 * MS:
            last_hb = now
            _heartbeat(run_dir, now, threads, stage)
    if "decision" not in finished:  # F19: decision died -> supervisor speaks directly if the sink still works
        log(events.make("system_fault", session_now(), ["decision_dead"], thread="decision"))
        try:
            play("system_off")
        except Exception:  # noqa: BLE001 - no audio left (F20); only logs remain
            log(events.make("audio_fault", session_now(), ["supervisor_play_failed"]))
    stop.set()
    stop_ev = events.make("run_stop", session_now())
    log(stop_ev)
    sink_q.put(DONE)
    threads["sink"].join(timeout=5)
    logq.put(DONE)
    threads["logger"].join(timeout=30)
    _heartbeat(run_dir, time.monotonic_ns(), threads, stage)
    return ["log_incomplete"] if overflow.is_set() else []


def _heartbeat(run_dir: Path, now: int, threads: dict, stage: DecisionStage) -> None:
    cap_d, cap_t = stage.caps.pair
    data = {
        "t_mono_ns": now,
        "threads": {n: t.is_alive() for n, t in threads.items()},
        "cap_distance": cap_d,
        "cap_ttc": cap_t,
    }
    tmp = run_dir / "heartbeat.json.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(run_dir / "heartbeat.json")
