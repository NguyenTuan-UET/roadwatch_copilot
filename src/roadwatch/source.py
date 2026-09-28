"""Source (spec §3.1, §3.3, ADR-06): frames on the process_hz schedule by PTS, GPS mapped to session time."""

import csv
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from .contracts.base import Q
from .contracts.streams import FrameMeta, SessionManifest, SpeedSample

MS = 1_000_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def video_frames(path: str | Path, process_hz: float, run_id: str,
                 video_sha256: str) -> Iterator[tuple[int, FrameMeta, np.ndarray | None]]:
    """Yield (s_n, meta, image). At each s_n take the latest frame with PTS <= s_n (causal).

    A schedule point with no new frame is skipped (gap/tick rules handle it); the end of the video
    yields one placeholder (spec F1) so downstream sees a known absence, then the stream stops.
    ponytail: PTS from OpenCV CAP_PROP_POS_MSEC; switch to PyAV if a camera's VFR timestamps prove unreliable.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise OSError(f"cannot open video {path}")
    period_ns = int(round(1e9 / process_hz))
    idx = -1

    def read():
        nonlocal idx
        ok, img = cap.read()
        if not ok:
            return None
        idx += 1
        return idx, int(round(cap.get(cv2.CAP_PROP_POS_MSEC) * MS)), img

    try:
        peek, last, emitted_idx, seq, n = read(), None, None, 0, 0
        pts0 = peek[1] if peek else 0
        while True:
            s_n = n * period_ns
            while peek is not None and peek[1] - pts0 <= s_n:
                last, peek = peek, read()
            if last is not None and last[0] != emitted_idx:
                i, pts, img = last
                yield s_n, FrameMeta(run_id=run_id, seq=seq, t_ns=pts - pts0, sched_n=n, status="ok", frame_idx=i,
                                     pts_ns=pts, video_sha256=video_sha256), img
                emitted_idx, seq = i, seq + 1
            elif peek is None:
                yield s_n, FrameMeta(run_id=run_id, seq=seq, t_ns=s_n, sched_n=n, status="unavailable",
                                     reasons=["end_of_video"], video_sha256=video_sha256), None
                return
            n += 1
    finally:
        cap.release()


def _utc_ns(text: str) -> int:
    dt = datetime.fromisoformat(text.strip())
    if dt.tzinfo is None:
        raise ValueError(f"GPS time without timezone: {text!r}")
    d = dt - _EPOCH
    return (d.days * 86_400 + d.seconds) * 1_000_000_000 + d.microseconds * 1000


def read_gps(path: str | Path, manifest: SessionManifest, run_id: str) -> list[SpeedSample]:
    """Normalised CSV: time_utc (ISO-8601 + zone), speed_mps, optional recv_time_utc, speed_accuracy_mps."""
    if manifest.recv_time_basis == "modeled" and manifest.recv_delay_ms is None:
        raise ValueError("recv_time_basis=modeled needs a measured recv_delay_ms (ADR-06)")
    start = manifest.video_start_utc_guess_ns + int(round(manifest.gps_offset_ms * MS))
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh)):
            t_fix = _utc_ns(row["time_utc"]) - start
            if manifest.recv_time_basis == "logged":
                t_recv = _utc_ns(row["recv_time_utc"]) - start
            else:
                t_recv = t_fix + int(round(manifest.recv_delay_ms * MS))
            acc = row.get("speed_accuracy_mps") or None
            speed = Q.ok(float(row["speed_mps"]), sigma=float(acc) if acc else None)
            rows.append((t_recv, t_fix, line_no, speed))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [SpeedSample(run_id=run_id, seq=i, t_ns=t_recv, gps_idx=line_no, t_fix_ns=t_fix, t_recv_ns=t_recv,
                        t_recv_basis=manifest.recv_time_basis, speed_mps=speed, source=manifest.speed_source,
                        session_id=manifest.session_id) for i, (t_recv, t_fix, line_no, speed) in enumerate(rows)]
