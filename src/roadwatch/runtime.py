"""Runtime (spec §3.1-3.3, §3.8, §5.3): replay (sequential, canonical order, never drops) and live (threads).

Both feed the same pure DecisionStage and write the same JSONL streams to runs/<run_id>/.
"""

import json
import math
import os
import platform
import subprocess
import sys
import threading
import uuid
import wave
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

import numpy as np

from . import configread
from .contracts.base import Q, Record, sha256_hex
from .contracts.config import ActivePointer, Approval, Audio, RwConfig
from .contracts.streams import (
    AlertDecision,
    AlertKind,
    AudioEvent,
    AudioPlan,
    DecisionInput,
    DecisionTrace,
    FrameMeta,
    Measurement,
    RunManifest,
    SessionManifest,
    SpeedSample,
    StreamRef,
    SystemEvent,
)
from .decision.stage import DecisionStage
from .perception import Perception
from .source import file_sha256, read_gps, video_frames

MS = 1_000_000
CONTRACTS_VERSION = "0.2.0"  # 0.2: RunManifest.proposal_id (MINOR), approval_id null on trial runs (3.10)
_STREAM_OF = {
    FrameMeta: "frames",
    SpeedSample: "speed",
    Measurement: "measurements",
    DecisionInput: "decision_inputs",
    DecisionTrace: "decisions",
    AlertDecision: "alerts",
    AudioPlan: "audio_plan",
    AudioEvent: "audio_events",
    SystemEvent: "events",
}


@dataclass
class RunInputs:
    video: Path
    session: SessionManifest
    gps_csv: Path | None
    config_root: Path
    out_root: Path
    mode: str = "replay"  # replay | live
    detector: Callable[[np.ndarray], np.ndarray] | None = None  # None -> ONNX model from the config
    driver_mode: str = "experienced"
    play: Callable[[str], None] | None = None  # live audio; None -> winsound on Windows
    active_arbiter: str = "B"  # which arbiter drives the speaker in live mode
    proposed: tuple[str, str] | None = None  # (proposal_id, config_sha256), resolved by the CLI: trial run (3.10)


class RunWriter:
    """One JSONL file per stream. Thread-safe; in live mode it is only called from the logger thread."""

    def __init__(self, run_dir: Path):
        self.dir = run_dir
        self.files: dict[str, object] = {}
        self.lock = threading.Lock()

    def write(self, stream: str, line: str) -> None:
        with self.lock:
            fh = self.files.get(stream)
            if fh is None:
                fh = self.files[stream] = open(self.dir / f"{stream}.jsonl", "w", encoding="utf-8")  # noqa: SIM115
            fh.write(line + "\n")

    def record(self, rec: Record) -> None:
        self.write(_STREAM_OF[type(rec)], rec.to_json())

    def close(self) -> None:
        with self.lock:
            for fh in self.files.values():
                fh.close()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def machine_fingerprint() -> str:
    u = platform.uname()
    return sha256_hex("|".join([u.node, u.system, u.release, u.machine, platform.processor(), str(os.cpu_count())]))[
        :16
    ]


def _manifest(
    inp: RunInputs, run_id: str, cfg: RwConfig, appr: Approval | None, ptr: ActivePointer | None
) -> RunManifest:
    commit = _git("rev-parse", "HEAD") or "unknown"
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    flags = []
    if appr is None:
        flags.append("proposed_config")  # spec 3.10: impact-report input only, never acceptance evidence
    elif commit != appr.code_commit:
        flags.append("unapproved_code")  # spec 3.10: runs on other code are not acceptance evidence
    if dirty:
        flags.append("dirty_tree")
    try:
        import onnxruntime

        ort_version = onnxruntime.__version__
    except ImportError:
        ort_version = None
    inputs = {"video_sha256": file_sha256(inp.video)}
    if inp.gps_csv:
        inputs["gps_sha256"] = file_sha256(inp.gps_csv)
    inputs["session_manifest_sha256"] = sha256_hex(inp.session.model_dump_json())
    return RunManifest(
        run_id=run_id,
        mode=inp.mode,
        created_utc=datetime.now(UTC).isoformat(),
        inputs=inputs,
        config_sha256=cfg.sha256(),
        approval_id=ptr.approval_id if ptr else None,
        activation_id=ptr.activation_id if ptr else None,
        proposal_id=inp.proposed[0] if inp.proposed else None,
        code_commit=commit,
        code_dirty=dirty,
        model_sha256=None if inp.detector else cfg.detector.model_sha256,
        ort_version=ort_version,
        python_version=sys.version.split()[0],
        os=platform.platform(),
        cpu=platform.processor() or platform.machine(),
        threads=4,
        machine_fingerprint=machine_fingerprint(),
        process_hz=cfg.runtime.process_hz,
        driver_mode=inp.driver_mode,
        session_id=inp.session.session_id,
        mount_checklist=inp.session.mount_checklist is not None,
        active_arbiter=inp.active_arbiter,
        contracts_version=CONTRACTS_VERSION,
        flags=flags + ([] if inp.detector is None else ["scripted_detector"]),
    )


def _make_detector(cfg: RwConfig):
    from .detect import OnnxDetector

    if file_sha256(cfg.detector.model_path) != cfg.detector.model_sha256:
        raise configread.ConfigError("detector model file hash differs from the approved config")
    d = cfg.detector
    return OnnxDetector(d.model_path, d.imgsz, d.score_thr, d.nms_iou, d.vehicle_class_ids, threads=4)


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as w:  # the wave module reads PCM only, which is also all winsound plays
        return math.ceil(w.getnframes() * 1000 / w.getframerate())


def check_phrases(audio: Audio) -> None:
    """Before really speaking (F23): every phrase has a PCM WAV that lasts what the config says.

    The pure arbiter plans with the durations in `audio.phrases` (3.6); a file of another length would be cut
    off by the next phrase or leave it waiting.
    """
    for phrase_id, want_ms in audio.phrases.items():
        path = Path(audio.phrase_dir) / f"{phrase_id}.wav"
        try:
            got_ms = wav_duration_ms(path)
        except (OSError, EOFError, wave.Error) as e:
            raise configread.ConfigError(f"phrase {phrase_id!r}: {path} is missing or not a PCM WAV ({e})") from e
        if got_ms != want_ms:
            raise configread.ConfigError(
                f"phrase {phrase_id!r}: {path} lasts {got_ms} ms, audio.phrases says {want_ms} ms"
            )


class Journal:
    """Feeds DecisionStage and records exactly what it consumed, in order (spec 3.3)."""

    def __init__(self, stage: DecisionStage, emit: Callable[[Record], None], run_id: str):
        self.stage, self.emit, self.run_id, self.seq = stage, emit, run_id, 0

    def feed(self, kind: str, t_ns: int, t_consumed: int, payload=None, tick_n: int | None = None) -> list[Record]:
        ref = (
            None
            if kind == "tick"
            else StreamRef(
                stream={"measurement": "measurements", "speed": "speed", "event": "events"}[kind], seq=payload.seq
            )
        )
        inp = DecisionInput(
            run_id=self.run_id, seq=self.seq, t_ns=t_ns, kind=kind, ref=ref, tick_n=tick_n, t_consumed_ns=t_consumed
        )
        self.seq += 1
        self.emit(inp)
        out = self.stage.consume(inp, payload)
        for r in out:
            self.emit(r)
        return out


class Events:
    def __init__(self, run_id: str):
        self.run_id, self.seq, self.lock = run_id, 0, threading.Lock()

    def make(self, kind: str, t_ns: int, reasons: list[str] | None = None, **detail) -> SystemEvent:
        with self.lock:
            e = SystemEvent(
                run_id=self.run_id, seq=self.seq, t_ns=t_ns, kind=kind, detail=detail, reasons=reasons or []
            )
            self.seq += 1
            return e


def run(inp: RunInputs) -> Path:
    if inp.proposed:  # trial run for an impact report: reads the version file only, activates nothing (3.10)
        if inp.session.split.startswith("test"):
            raise configread.ConfigError("runs with a proposed config are refused on test_* splits (spec 3.10)")
        cfg, appr, ptr = configread.load_version(inp.config_root, inp.proposed[1]), None, None
    else:
        cfg, appr, ptr = configread.load_active(inp.config_root)  # F23: refuse unapproved/tampered config
    if inp.mode == "live" and inp.play is None:  # about to speak for real: the configured phrases must be there
        check_phrases(cfg.audio)
    sha = cfg.sha256()
    run_id = f"{inp.mode}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    run_dir = Path(inp.out_root) / run_id
    run_dir.mkdir(parents=True)
    manifest = _manifest(inp, run_id, cfg, appr, ptr)
    (run_dir / "config").mkdir()
    (run_dir / "config" / f"{sha}.yaml").write_text(
        (Path(inp.config_root) / "versions" / f"{sha}.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    detector = inp.detector or _make_detector(cfg)
    gps = read_gps(inp.gps_csv, inp.session, run_id) if inp.gps_csv else []
    stage = DecisionStage(
        cfg, run_id, mount_checklist=inp.session.mount_checklist is not None, driver_mode=inp.driver_mode
    )
    perception = Perception(cfg, detector)
    writer = RunWriter(run_dir)
    try:
        if inp.mode == "replay":
            _replay(inp, cfg, run_id, gps, stage, perception, writer)
        else:
            from .live import run_live

            flags = run_live(inp, cfg, run_id, gps, stage, perception, writer, run_dir)
            manifest = manifest.model_copy(update={"flags": manifest.flags + flags})
    finally:
        writer.close()
        (run_dir / "run_manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        stats = run_stats(run_dir, inp.active_arbiter, live=inp.mode == "live")
        (run_dir / "run_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return run_dir


def _logged(run_dir: Path, stream: str) -> list[dict]:
    path = run_dir / f"{stream}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def run_stats(run_dir: Path, arbiter: str, live: bool) -> dict:
    """run_stats.json (spec 4.4, PO 30/09): counts read back from the logged streams after the run.

    Audio outcomes only exist live; in replay they are null, never 0.
    """
    events = Counter(e["kind"] for e in _logged(run_dir, "events"))
    stops = [e["t_ns"] for e in _logged(run_dir, "events") if e["kind"] == "run_stop"]
    read, processed = len(_logged(run_dir, "frames")), len(_logged(run_dir, "measurements"))
    alerts = Counter(a["kind"] for a in _logged(run_dir, "alerts") if a["arbiter"] == arbiter)
    played = Counter(e["outcome"] for e in _logged(run_dir, "audio_events"))
    return {
        "run_id": run_dir.name,
        "duration_s": stops[-1] / 1e9 if stops else None,
        "frames": {
            "read": read,
            "processed": processed,
            "dropped": events["frame_dropped"],
            "drop_ratio": events["frame_dropped"] / read if read else None,
        },
        "streams": {
            "measurements_count": processed,
            "measurements_dropped": events["measurement_dropped"],
            "speed_samples_count": len(_logged(run_dir, "speed")),
            "speed_dropped": events["speed_dropped"],
        },
        "decision": {
            "ticks_count": sum(i["kind"] == "tick" for i in _logged(run_dir, "decision_inputs")),
            "alerts_total": sum(alerts.values()),
            "alerts_by_kind": {kind: alerts[kind] for kind in get_args(AlertKind)},
        },
        "audio": {  # commands the arbiter handed to the speaker (audio_plan started), then what the speaker did
            "commands_issued": sum(
                p["arbiter"] == arbiter and p["outcome"] == "started" for p in _logged(run_dir, "audio_plan")
            ),
            "played_successfully": played["started"] if live else None,
            "dropped_stale": played["dropped_stale"] if live else None,
        },
    }


def _replay(
    inp: RunInputs,
    cfg: RwConfig,
    run_id: str,
    gps: list[SpeedSample],
    stage: DecisionStage,
    perception: Perception,
    writer: RunWriter,
) -> None:
    """Sequential and deterministic: canonical order speed -> event -> tick -> measurement (spec 3.3).

    ponytail: replay runs in one thread; threads add nothing when nothing may be dropped or paced.
    """
    events = Events(run_id)
    journal = Journal(stage, writer.record, run_id)
    tick_ns = cfg.runtime.tick_period_ms * MS
    gi, next_tick, m_seq = 0, 0, 0
    start = events.make("run_start", 0)
    writer.record(start)
    journal.feed("event", 0, 0, start)
    for s_n, meta, img in video_frames(inp.video, cfg.runtime.process_hz, run_id, inp.session.video_sha256):
        writer.record(meta)
        if meta.status == "ok":
            m = perception.process(img, meta.t_ns, meta.sched_n, meta.frame_idx, run_id, m_seq)
        else:
            m = perception.placeholder(meta.t_ns, meta.sched_n, run_id, m_seq)
        m_seq += 1
        writer.record(m)
        t_k = m.t_ns
        while True:  # merge by time; ties: speed before tick (measurement last)
            t_speed = gps[gi].t_recv_ns if gi < len(gps) else None
            if t_speed is not None and t_speed <= t_k and t_speed <= next_tick:
                writer.record(gps[gi])
                journal.feed("speed", t_speed, t_speed, gps[gi])
                gi += 1
            elif next_tick <= t_k:
                journal.feed("tick", next_tick, next_tick, tick_n=next_tick // tick_ns)
                next_tick += tick_ns
            else:
                break
        journal.feed("measurement", t_k, t_k, m)
    stop = events.make("run_stop", next_tick)
    writer.record(stop)
    journal.feed("event", stop.t_ns, stop.t_ns, stop)


def audio_event(run_id: str, seq: int, t_ns: int, alert_id: str, outcome: str, t_mono: int) -> AudioEvent:
    return AudioEvent(
        run_id=run_id,
        seq=seq,
        t_ns=t_ns,
        alert_id=alert_id,
        outcome=outcome,
        t_mono_ns=t_mono,
        output_latency_ms=Q.missing("unavailable", "not_reported_by_audio_api"),
    )
