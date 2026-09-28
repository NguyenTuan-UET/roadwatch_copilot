"""Source (spec §3.1, §3.3, ADR-06): frame schedule by PTS, placeholders, GPS time mapping."""

import cv2
import numpy as np
import pytest

from src.roadwatch.contracts.streams import SessionManifest
from src.roadwatch.source import read_gps, video_frames

MS = 1_000_000


def _video(path, n=90, fps=30.0):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (64, 48))
    for i in range(n):
        img = np.full((48, 64, 3), i % 255, np.uint8)
        w.write(img)
    w.release()
    return path


def test_schedule_takes_latest_frame_not_after_schedule_point(tmp_path):
    frames = list(video_frames(_video(tmp_path / "v.avi"), process_hz=10.0, run_id="r", video_sha256="v"))
    real = [(s, m) for s, m, img in frames if m.status == "ok"]
    assert len(real) == 31  # schedule points 0..3000 ms; frame 89 (2967 ms) is new at s=3000
    for s_n, meta in real:
        assert meta.t_ns <= s_n and s_n - meta.t_ns < 34 * MS  # causal, within one frame period
    assert [m.frame_idx for _, m in real[:4]] == [0, 3, 6, 9]
    assert [m.seq for _, m, _ in frames] == list(range(len(frames)))


def test_end_of_video_emits_one_placeholder(tmp_path):
    frames = list(video_frames(_video(tmp_path / "v.avi", n=12), process_hz=10.0, run_id="r", video_sha256="v"))
    last_s, last, img = frames[-1]
    assert last.status == "unavailable" and last.frame_idx is None and img is None
    assert last.reasons == ["end_of_video"] and last.t_ns == last_s
    assert sum(m.status == "unavailable" for _, m, _ in frames) == 1


def _manifest(**kw):
    base = dict(session_id="s1", video_file="v.avi", video_sha256="v", gps_file="g.csv", gps_sha256="g",
                video_start_utc_guess_ns=1_758_000_000_000 * MS, gps_offset_ms=250.0, gps_offset_uncertainty_ms=None,
                sync_method="drive_off", recv_time_basis="logged", speed_source="gps", split="dev")
    return SessionManifest(**{**base, **kw})


def test_gps_times_are_mapped_to_the_session_clock_with_logged_receive_time(tmp_path):
    csv = tmp_path / "g.csv"
    csv.write_text("time_utc,speed_mps,recv_time_utc\n"
                   "2025-09-16T05:20:00.250Z,25.0,2025-09-16T05:20:00.450Z\n"
                   "2025-09-16T05:20:01.250Z,24.5,2025-09-16T05:20:01.400Z\n", encoding="utf-8")
    start = 1_758_000_000_000 * MS  # 2025-09-16T05:20:00Z
    s = read_gps(csv, _manifest(video_start_utc_guess_ns=start), run_id="r")
    assert [x.t_fix_ns for x in s] == [0, 1000 * MS]  # 250 ms offset moves the video start
    assert [x.t_recv_ns for x in s] == [200 * MS, 1150 * MS] and s[0].t_recv_basis == "logged"
    assert s[1].speed_mps.value == 24.5 and s[0].source == "gps"


def test_gps_modeled_receive_time_needs_a_measured_delay(tmp_path):
    csv = tmp_path / "g.csv"
    csv.write_text("time_utc,speed_mps\n2025-09-16T05:20:00.250Z,25.0\n", encoding="utf-8")
    start = 1_758_000_000_000 * MS
    with pytest.raises(ValueError, match="recv_delay_ms"):
        read_gps(csv, _manifest(video_start_utc_guess_ns=start, recv_time_basis="modeled"), run_id="r")
    s = read_gps(csv, _manifest(video_start_utc_guess_ns=start, recv_time_basis="modeled", recv_delay_ms=300.0),
                 run_id="r")
    assert s[0].t_recv_ns - s[0].t_fix_ns == 300 * MS and s[0].t_recv_basis == "modeled"
