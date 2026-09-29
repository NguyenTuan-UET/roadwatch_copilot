"""Runtime smoke tests (spec §3.1-3.3, §5.3-5.4, AC-M1, AC-M10, F23) on a synthetic clip with a scripted detector."""

import json

import cv2
import numpy as np
import pytest

from src.roadwatch import configstore as cs
from src.roadwatch.contracts.base import check_stream, normalize, read_record
from src.roadwatch.contracts.streams import AlertDecision, DecisionInput, FrameMeta, Measurement, SessionManifest
from src.roadwatch.runtime import RunInputs, run
from tests.roadwatch.decision_harness import make_config

W, H = 320, 180
START_NS = 1_758_000_000_000_000_000


def small_config():
    return make_config(
        camera={"fx_px": 166.7, "fy_px": 166.7, "cx_px": 160.0, "cy_px": 90.0, "width_px": W, "height_px": H},
        mount={"y_horizon_px": 90.0},
    )


def fake_detector(img):
    """A car sitting in the ego lane, bottom edge at y=100 -> about 20 m: below the 70 m band at 90 km/h."""
    return np.array([[140.0, 60.0, 180.0, 100.0, 0.9, 2.0]], np.float32)


@pytest.fixture
def setup(tmp_path):
    rng = np.random.default_rng(3)
    bg = rng.integers(30, 220, (H, W, 3), dtype=np.uint8)
    video = tmp_path / "clip.avi"
    w = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (W, H))
    for _ in range(120):  # 4 s
        w.write(bg)
    w.release()
    gps = tmp_path / "gps.csv"
    lines = ["time_utc,speed_mps,recv_time_utc"]
    for s in range(6):
        lines.append(f"2025-09-16T05:20:0{s}.000Z,25.0,2025-09-16T05:20:0{s}.100Z")
    gps.write_text("\n".join(lines) + "\n", encoding="utf-8")
    session = SessionManifest(
        session_id="s1",
        video_file=str(video),
        video_sha256="x",
        gps_file=str(gps),
        gps_sha256="y",
        video_start_utc_guess_ns=START_NS,
        gps_offset_ms=0.0,
        gps_offset_uncertainty_ms=None,
        sync_method="test",
        recv_time_basis="logged",
        speed_source="gps",
        mount_checklist={"by": "tester", "at": "2026-09-28"},
        split="dev",
    )
    store = tmp_path / "configs"
    cs.init_store(store, approvers=["po"])
    env = cs.Env(
        code_commit="c1",
        code_dirty=False,
        dataset_manifest_sha256="d",
        model_sha256="m",
        ort_version="1",
        machine_fingerprint=None,
    )
    pid = cs.propose(store, small_config(), "eng")
    appr = cs.approve(store, pid, cs.make_report(store, pid, env, {}, live=False), "po")
    cs.activate(store, appr.approval_id, "po", env)
    return RunInputs(
        video=video,
        session=session,
        gps_csv=gps,
        config_root=store,
        out_root=tmp_path / "runs",
        mode="replay",
        detector=fake_detector,
    )


def _read(run_dir, name, model):
    return [read_record(line, model) for line in (run_dir / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]


def test_replay_writes_valid_streams_and_a_manifest(setup):
    run_dir = run(setup)
    frames = _read(run_dir, "frames", FrameMeta)
    meas = _read(run_dir, "measurements", Measurement)
    journal = _read(run_dir, "decision_inputs", DecisionInput)
    check_stream(frames)
    check_stream(meas)
    check_stream(journal, time_attr="t_consumed_ns")
    assert len(meas) == len(frames) and frames[-1].reasons == ["end_of_video"]
    assert {j.kind for j in journal} == {"measurement", "speed", "event", "tick"}
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "replay" and manifest["threads"] == 4 and manifest["approval_id"]
    warnings = [a for a in _read(run_dir, "alerts", AlertDecision) if a.arbiter == "B" and a.kind == "warning"]
    assert len(warnings) == 1  # 20 m at 90 km/h, confirmed once


def test_replay_is_reproducible_on_business_data(setup):
    a, b = run(setup), run(setup)
    for name in ("measurements", "decision_inputs", "decisions", "alerts", "audio_plan"):
        rows_a = [normalize(json.loads(x)) for x in (a / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]
        rows_b = [normalize(json.loads(x)) for x in (b / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert rows_a == rows_b, name


def test_runtime_refuses_to_start_without_an_approved_active_config(setup, tmp_path):
    empty = tmp_path / "empty"
    cs.init_store(empty, approvers=["po"])
    setup.config_root = empty
    with pytest.raises(cs.ConfigError):
        run(setup)


def test_live_run_paces_records_perf_and_plays_audio(setup):
    played = []
    setup.mode, setup.play = "live", played.append
    run_dir = run(setup)
    perf = [json.loads(x) for x in (run_dir / "perf.jsonl").read_text(encoding="utf-8").splitlines()]
    assert perf and all(p["t_decision_mono_ns"] >= p["t_arrive_mono_ns"] for p in perf)
    events = [json.loads(x) for x in (run_dir / "audio_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["outcome"] for e in events] == ["started"] and played == ["warning"]
    heartbeat = json.loads((run_dir / "heartbeat.json").read_text(encoding="utf-8"))
    assert set(heartbeat["threads"]) >= {"source", "perception", "decision"}


def test_live_perception_crash_is_detected_and_announced(setup):
    calls = {"n": 0}

    def crashing(img):
        calls["n"] += 1
        if calls["n"] > 5:
            raise RuntimeError("detector crashed")
        return fake_detector(img)

    played = []
    setup.mode, setup.play, setup.detector = "live", played.append, crashing
    run_dir = run(setup)
    events = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["kind"] == "system_fault" and e["detail"]["thread"] == "perception" for e in events)
    assert played == ["system_off"]  # announced at once, no debounce (spec 3.4)
