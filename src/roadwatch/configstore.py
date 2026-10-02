"""Config store, HITL side (spec §3.10, ADR-11): tools of C only, never imported by runtime.

propose -> make_report -> approve (other person) -> activate/rollback, all mutations under an OS-level
exclusive lock; the commit point of an activation is the atomic replace of active.json.
The read side (`load_active` and friends, files only) lives in configread.py and is re-exported here, so a
tool has one module for the whole store.
"""

import json
import os
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from .configread import ConfigError, load_active, load_approval, load_version, read_pointer  # noqa: F401 - re-export
from .contracts.base import canonical_json, sha256_hex
from .contracts.config import ActivePointer, Approval, RwConfig


class HitlError(RuntimeError):
    """A HITL command was refused; nothing was changed."""


@dataclass
class Env:
    """What an approval is bound to (ADR-11): the code, data and machine the report was made on."""

    code_commit: str
    code_dirty: bool
    dataset_manifest_sha256: str
    model_sha256: str | None
    ort_version: str | None
    machine_fingerprint: str | None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


# --- HITL side --------------------------------------------------------------------------------


class FileLock:
    """Exclusive OS lock; the OS releases it if the process dies, so a crash never leaves it held."""

    def __init__(self, path: Path, timeout_s: float = 10.0):
        self.path, self.timeout_s, self.fh = Path(path), timeout_s, None

    def _try(self) -> bool:
        try:
            if os.name == "nt":
                import msvcrt

                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def __enter__(self):
        self.fh = open(self.path, "a+")  # noqa: SIM115 - held for the lock's lifetime
        deadline = time.monotonic() + self.timeout_s
        while not self._try():
            if time.monotonic() >= deadline:
                self.fh.close()
                raise HitlError(f"HITL store busy (lock {self.path.name} held by another command)")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        if os.name == "nt":
            import msvcrt

            self.fh.seek(0)
            msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        self.fh.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, config_sha TEXT, proposer TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS reports (sha TEXT PRIMARY KEY, proposal_id TEXT, path TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS approvals (approval_id TEXT PRIMARY KEY, proposal_id TEXT, config_sha TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS activations (activation_id TEXT PRIMARY KEY, approval_id TEXT, from_activation_id TEXT,
    to_config_sha TEXT, actor TEXT, at TEXT, state TEXT CHECK (state IN ('pending','committed','aborted')), kind TEXT);
CREATE TABLE IF NOT EXISTS audit (at TEXT, actor TEXT, action TEXT, detail TEXT);
"""


@contextmanager
def hitl_session(root: Path) -> Iterator[sqlite3.Connection]:
    """Every mutating HITL command runs entirely inside the lock; statements autocommit unless BEGIN is used."""
    root = Path(root)
    with FileLock(root / ".hitl.lock"):
        con = sqlite3.connect(root / "hitl.sqlite", isolation_level=None)
        try:
            yield con
        finally:
            con.close()


def init_store(root: Path, approvers: list[str]) -> None:
    root = Path(root)
    for sub in ("versions", "approvals", "reports"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "roles.json").write_text(json.dumps({"approvers": approvers}, indent=2), encoding="utf-8")
    with hitl_session(root) as con:
        con.executescript(_SCHEMA)


def _audit(con, actor: str, action: str, detail: str) -> None:
    con.execute("INSERT INTO audit VALUES (?, ?, ?, ?)", (_now(), actor, action, detail))


def _approvers(root: Path) -> set[str]:
    return set(json.loads((Path(root) / "roles.json").read_text(encoding="utf-8"))["approvers"])


def propose(root: Path, cfg: RwConfig, proposer: str) -> str:
    root, sha = Path(root), cfg.sha256()
    path = root / "versions" / f"{sha}.yaml"
    with hitl_session(root) as con:
        if not path.exists():  # versions are immutable; same content => same file
            path.write_text(
                yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=True, allow_unicode=True), encoding="utf-8"
            )
        pid = uuid.uuid4().hex
        con.execute("INSERT INTO proposals VALUES (?, ?, ?, ?)", (pid, sha, proposer, _now()))
        _audit(con, proposer, "propose", sha)
    return pid


def _proposal(con, pid: str) -> tuple[str, str]:
    row = con.execute("SELECT config_sha, proposer FROM proposals WHERE id = ?", (pid,)).fetchone()
    if row is None:
        raise HitlError(f"unknown proposal {pid}")
    return row


def proposal_config(root: Path, pid: str) -> RwConfig:
    """Read-only lookup of a proposal's config: no lock, nothing written (spec 3.10: CLI resolves proposal_id)."""
    root = Path(root)
    con = sqlite3.connect(f"{(root / 'hitl.sqlite').as_uri()}?mode=ro", uri=True)
    try:
        config_sha, _ = _proposal(con, pid)
    finally:
        con.close()
    return load_version(root, config_sha)


def make_report(root: Path, pid: str, env: Env, metrics: dict, live: bool) -> str:
    """Records an impact report against the *current* active config (report --rebase = call again)."""
    root = Path(root)
    if env.code_dirty:
        raise HitlError("working tree is dirty; reports must be bound to a clean commit")
    with hitl_session(root) as con:
        config_sha, _ = _proposal(con, pid)
        ptr = read_pointer(root)
        cfg = load_version(root, config_sha)
        if ptr is None:
            path, affected = "bootstrap", set()
        else:
            affected = cfg.affected_by_change(load_version(root, ptr.config_sha256))
            if "live" in affected and not live:
                raise HitlError("change touches runtime/detector: a live check on the demo machine is required")
            path = "replay+live" if live else ("replay" if "A" in affected else "rerun-B")
        report = {
            "proposal_id": pid,
            "config_sha256": config_sha,
            "base_config_sha256": ptr.config_sha256 if ptr else "",
            "path": path,
            "affects": sorted(affected),
            "dataset_manifest_sha256": env.dataset_manifest_sha256,
            "code_commit": env.code_commit,
            "model_sha256": env.model_sha256,
            "ort_version": env.ort_version,
            "machine_fingerprint": env.machine_fingerprint if live else None,
            "metrics": metrics,
            "created_at": _now(),
        }
        text = canonical_json(report)
        sha = sha256_hex(text)
        (root / "reports" / f"{sha}.json").write_text(text, encoding="utf-8")
        con.execute("INSERT INTO reports VALUES (?, ?, ?, ?)", (sha, pid, path, report["created_at"]))
        _audit(con, "tool", "report", f"{pid} {path} {sha}")
    return sha


def approve(root: Path, pid: str, report_sha: str, approver: str) -> Approval:
    root = Path(root)
    if approver not in _approvers(root):
        raise HitlError(f"{approver!r} is not an approver")
    with hitl_session(root) as con:
        config_sha, proposer = _proposal(con, pid)
        row = con.execute("SELECT proposal_id FROM reports WHERE sha = ?", (report_sha,)).fetchone()
        if row is None or row[0] != pid:
            raise HitlError("report does not belong to this proposal")
        rep = json.loads((root / "reports" / f"{report_sha}.json").read_text(encoding="utf-8"))
        try:
            appr = Approval.create(
                config_sha256=config_sha,
                proposer=proposer,
                approver=approver,
                approved_at=_now(),
                report_sha256=report_sha,
                base_config_sha256=rep["base_config_sha256"],
                dataset_manifest_sha256=rep["dataset_manifest_sha256"],
                code_commit=rep["code_commit"],
                model_sha256=rep["model_sha256"],
                ort_version=rep["ort_version"],
                machine_fingerprint=rep["machine_fingerprint"],
            )
        except ValidationError as e:
            raise HitlError(f"approval refused: {e.errors()[0]['msg']}") from e
        (root / "approvals" / f"{appr.approval_id}.json").write_text(appr.model_dump_json(indent=2), encoding="utf-8")
        con.execute("INSERT INTO approvals VALUES (?, ?, ?, ?)", (appr.approval_id, pid, config_sha, appr.approved_at))
        _audit(con, approver, "approve", appr.approval_id)
    return appr


def _check_env(appr: Approval, env: Env) -> None:
    if env.code_dirty:
        raise HitlError("working tree is dirty")
    for field in ("code_commit", "dataset_manifest_sha256", "model_sha256", "ort_version"):
        if getattr(appr, field) != getattr(env, field):
            raise HitlError(f"{field} differs from the approved report; make a new report")
    if appr.machine_fingerprint is not None and appr.machine_fingerprint != env.machine_fingerprint:
        raise HitlError("live check was made on another machine")


def _write_pointer(root: Path, ptr: ActivePointer) -> None:
    tmp = Path(root) / "active.json.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(ptr.model_dump_json(indent=2))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, Path(root) / "active.json")  # commit point


def _mark_committed(con, activation_id: str) -> None:
    con.execute("UPDATE activations SET state = 'committed' WHERE activation_id = ?", (activation_id,))


def _recover(con, root: Path) -> dict[str, int]:
    counts = {"aborted": 0, "committed": 0}
    rows = con.execute("SELECT activation_id, from_activation_id FROM activations WHERE state = 'pending'").fetchall()
    ptr = read_pointer(root)
    current = ptr.activation_id if ptr else ""
    for act_id, from_id in rows:
        if current == act_id:
            _mark_committed(con, act_id)
            counts["committed"] += 1
        elif current == from_id:
            con.execute("UPDATE activations SET state = 'aborted' WHERE activation_id = ?", (act_id,))
            counts["aborted"] += 1
        else:
            raise HitlError(
                "inconsistent activation state: pointer matches neither side of a pending activation; "
                "all HITL commands are locked until fixed by hand"
            )
    return counts


def recover(root: Path) -> dict[str, int]:
    with hitl_session(root) as con:
        return _recover(con, Path(root))


def _switch(con, root: Path, appr: Approval, ptr: ActivePointer | None, actor: str, kind: str) -> ActivePointer:
    act_id = uuid.uuid4().hex
    con.execute("BEGIN IMMEDIATE")
    if con.execute("SELECT 1 FROM activations WHERE state = 'pending'").fetchone():
        con.execute("ROLLBACK")
        raise HitlError("another activation is pending; run recover")
    con.execute(
        "INSERT INTO activations VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
        (act_id, appr.approval_id, ptr.activation_id if ptr else "", appr.config_sha256, actor, _now(), kind),
    )
    con.execute("COMMIT")
    new = ActivePointer(config_sha256=appr.config_sha256, approval_id=appr.approval_id, activation_id=act_id)
    _write_pointer(root, new)
    _mark_committed(con, act_id)
    _audit(con, actor, kind, f"{appr.approval_id} as {act_id}")
    return new


def _load_approval_for_hitl(root: Path, approval_id: str) -> Approval:
    try:
        return load_approval(root, approval_id)
    except ConfigError as e:
        raise HitlError(str(e)) from e


def activate(root: Path, approval_id: str, actor: str, env: Env) -> ActivePointer:
    root = Path(root)
    with hitl_session(root) as con:
        _recover(con, root)
        appr = _load_approval_for_hitl(root, approval_id)
        ptr = read_pointer(root)
        if appr.base_config_sha256 != (ptr.config_sha256 if ptr else ""):
            raise HitlError("active config changed since this report was made; run report --rebase and re-approve")
        _check_env(appr, env)
        return _switch(con, root, appr, ptr, actor, "activate")


def rollback(root: Path, approval_id: str, actor: str) -> ActivePointer:
    """Emergency path: re-activate a previously active approval; approver only; no new report needed."""
    root = Path(root)
    if actor not in _approvers(root):
        raise HitlError(f"{actor!r} is not an approver")
    with hitl_session(root) as con:
        _recover(con, root)
        seen = con.execute(
            "SELECT 1 FROM activations WHERE approval_id = ? AND state = 'committed'", (approval_id,)
        ).fetchone()
        if not seen:
            raise HitlError("rollback target was never active")
        return _switch(con, root, _load_approval_for_hitl(root, approval_id), read_pointer(root), actor, "rollback")
