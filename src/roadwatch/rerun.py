"""rerun-B (spec 5.3-5.4): replay a run's decision journal through the pure stage, optionally verify.

The journal holds exactly what `decision` consumed, so the same config reproduces the source output; a
different B config yields the impact for HITL reports without re-running the detector.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .contracts.base import normalize, read_record
from .contracts.config import RwConfig
from .contracts.streams import DecisionInput, Measurement, RunManifest, SpeedSample, SystemEvent
from .decision.stage import DecisionStage
from .runtime import RunWriter

COMPARED = ("decisions", "alerts", "audio_plan")
_PAYLOAD = {"measurements": Measurement, "speed": SpeedSample, "events": SystemEvent}


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def load_run_config(run_dir: Path) -> RwConfig:
    (path,) = list((Path(run_dir) / "config").glob("*.yaml"))
    return RwConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_manifest(run_dir: Path) -> RunManifest:
    return RunManifest.model_validate_json((Path(run_dir) / "run_manifest.json").read_text(encoding="utf-8"))


def normalized(run_dir: Path, stream: str) -> list:
    return [normalize(json.loads(x)) for x in _lines(Path(run_dir) / f"{stream}.jsonl")]


def first_difference(a: list, b: list) -> str | None:
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            return f"record {i}: fields {keys}"
    return None if len(a) == len(b) else f"length {len(a)} != {len(b)}"


def rerun_b(
    run_dir: Path, cfg: RwConfig | None = None, verify: bool = False, out_root: Path | None = None
) -> tuple[Path, bool | None]:
    run_dir = Path(run_dir)
    src = load_manifest(run_dir)
    source_cfg = load_run_config(run_dir)
    cfg = cfg or source_cfg
    payloads = {
        name: {r.seq: r for r in (read_record(x, model) for x in _lines(run_dir / f"{name}.jsonl"))}
        for name, model in _PAYLOAD.items()
    }
    run_id = f"rerun-B-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    out_dir = Path(out_root or run_dir.parent) / run_id
    (out_dir / "config").mkdir(parents=True)
    (out_dir / "config" / f"{cfg.sha256()}.yaml").write_text(
        yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    stage = DecisionStage(cfg, run_id, mount_checklist=src.mount_checklist, driver_mode=src.driver_mode)
    writer = RunWriter(out_dir)
    try:
        for line in _lines(run_dir / "decision_inputs.jsonl"):
            inp = read_record(line, DecisionInput)
            payload = None if inp.ref is None else payloads[inp.ref.stream][inp.ref.seq]
            for rec in stage.consume(inp, payload):
                writer.record(rec)
    finally:
        writer.close()
    same_cfg = cfg.sha256() == source_cfg.sha256()
    manifest = src.model_copy(
        update={
            "run_id": run_id,
            "mode": "rerun-B",
            "created_utc": datetime.now(UTC).isoformat(),
            "source_run_id": src.run_id,
            "config_sha256": cfg.sha256(),
            "approval_id": src.approval_id if same_cfg else "proposed",
            "activation_id": src.activation_id if same_cfg else None,
        }
    )
    (out_dir / "run_manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    if not verify:
        return out_dir, None
    diffs = {s: first_difference(normalized(run_dir, s), normalized(out_dir, s)) for s in COMPARED}
    (out_dir / "verify.json").write_text(json.dumps(diffs, indent=2), encoding="utf-8")
    return out_dir, all(d is None for d in diffs.values())
