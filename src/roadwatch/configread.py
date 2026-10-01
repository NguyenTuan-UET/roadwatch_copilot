"""Read side of the config store (spec §3.10, ADR-11): all the product path needs, and files only.

`load_active` reads active.json, versions/ and approvals/ and refuses anything unapproved or tampered (F23).
No SQLite, no lock, nothing written: the HITL commands are in configstore.py, which runtime never imports
(code-rules 3).
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from .contracts.config import ActivePointer, Approval, RwConfig


class ConfigError(RuntimeError):
    """Runtime must refuse to start (F23)."""


def load_version(root: Path, sha: str) -> RwConfig:
    path = Path(root) / "versions" / f"{sha}.yaml"
    try:
        cfg = RwConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, ValidationError, yaml.YAMLError) as e:
        raise ConfigError(f"config version {sha[:12]} unreadable or invalid: {e}") from e
    if cfg.sha256() != sha:
        raise ConfigError(f"config version {sha[:12]}: content hash does not match file name")
    return cfg


def load_approval(root: Path, approval_id: str) -> Approval:
    path = Path(root) / "approvals" / f"{approval_id}.json"
    try:
        appr = Approval.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as e:
        raise ConfigError(f"approval {approval_id[:12]} missing or invalid: {e}") from e
    if appr.approval_id != approval_id:
        raise ConfigError("approval file name does not match its approval_id")
    return appr


def read_pointer(root: Path) -> ActivePointer | None:
    path = Path(root) / "active.json"
    if not path.exists():
        return None
    return ActivePointer.model_validate_json(path.read_text(encoding="utf-8"))


def load_active(root: Path) -> tuple[RwConfig, Approval, ActivePointer]:
    try:
        ptr = read_pointer(root)
    except ValidationError as e:
        raise ConfigError(f"active pointer invalid: {e}") from e
    if ptr is None:
        raise ConfigError("no active config (active.json missing)")
    cfg = load_version(root, ptr.config_sha256)
    appr = load_approval(root, ptr.approval_id)
    if appr.config_sha256 != ptr.config_sha256:
        raise ConfigError("approval is for another config than the active pointer")
    return cfg, appr, ptr
