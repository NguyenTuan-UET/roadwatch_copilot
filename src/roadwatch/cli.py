"""
# TASK: WP-C2 · Unified CLI
- Owner: Cương (PO / Lead + R-C)
- Trạng thái: Hoàn thành lõi CLI cho WP-C2 (test_cli.py XANH); chờ Tuấn review.
- Chức năng đã xong: hitl (init, propose, report, approve, activate, rollback, recover, status), schema export,
  dispatch run/rerun-b/eval/perf; `run --proposed` (D-8) nên `hitl report` làm được cả đường `[A]`, `[A, live]`;
  `check-run` (AC-M1) và `compare` (AC-M10) cho WP-P8. Cấu hình v0 khởi tạo bằng chính `hitl` (OQ-B3, PO 30/09).
- Còn thiếu của BT-C: đóng băng contracts v1.0 (WP-P4) và tích hợp demo (WP-P8); WP-C3 đã có fixture, chờ Khánh review.

Chạy: `python -m src.roadwatch.cli <lệnh> --help`. Trạng thái chuẩn của task nằm ở docs/plan/README.md, mục 4.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from . import configstore as cs
from . import evaluate
from .contracts.config import RwConfig
from .contracts.streams import STREAMS, AlertDecision, EventLabel, SessionManifest, check_streams
from .rerun import compare_stream, load_manifest, load_run_config, normalized, rerun_b
from .runtime import RunInputs, _git, machine_fingerprint, run
from .source import file_sha256

SCHEMAS = (*STREAMS.values(), RwConfig)
_ALWAYS = (
    "frames.jsonl",
    "measurements.jsonl",
    "decision_inputs.jsonl",
    "decisions.jsonl",
    "events.jsonl",
    "run_stats.json",
)
# Files every run of a mode has (spec 4.4, 5.3). speed, alerts and audio_* may be absent: no GPS, nothing said.
REQUIRED = {"replay": _ALWAYS, "live": (*_ALWAYS, "perf.jsonl", "heartbeat.json"), "rerun-B": ("decisions.jsonl",)}


def current_env(dataset: Path, cfg: RwConfig) -> cs.Env:
    """What a report/approval binds to (ADR-11), read from this checkout and machine now."""
    commit = _git("rev-parse", "HEAD")
    if not commit:
        raise cs.HitlError("cannot read the git commit; HITL reports must be bound to a commit")
    try:
        import onnxruntime

        ort_version = onnxruntime.__version__
    except ImportError:
        ort_version = None
    model = Path(cfg.detector.model_path)
    return cs.Env(
        code_commit=commit,
        code_dirty=bool(_git("status", "--porcelain", "--untracked-files=no")),
        dataset_manifest_sha256=file_sha256(dataset),
        model_sha256=file_sha256(model) if model.exists() else None,
        ort_version=ort_version,
        machine_fingerprint=machine_fingerprint(),
    )


def _load_config(path: str) -> RwConfig:
    return RwConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _refuse_test_split(dataset: Path) -> None:
    """D-11: the HITL flow never uses test_* data (spec 3.10)."""
    # ponytail: no DatasetManifest contract yet, so any `split: test_*` in the file refuses; use the model once
    # WP-D4 defines it. A missing file is refused later by current_env (it must be hashed).
    text = dataset.read_text(encoding="utf-8") if dataset.exists() else ""
    bad = sorted(set(re.findall(r"\bsplit\"?\s*:\s*\"?(test_\w+)", text)))
    if bad:
        raise cs.HitlError(f"dataset uses split {', '.join(bad)}; HITL works on dev data only (D-11)")


def _b_alert_counts(run_dir: Path) -> dict[str, int]:
    return dict(Counter(a.kind for a in evaluate._read(run_dir, "alerts", AlertDecision) if a.arbiter == "B"))


def _impact(runs: list[Path], cfg: RwConfig) -> dict:
    """Path [B]: rerun-B every dev run with the proposed config; B alerts per kind, before and after."""
    per_run = []
    for run_dir in runs:
        if load_run_config(run_dir).affected_by_change(cfg) - {"B"}:
            raise cs.HitlError(f"{run_dir.name} was made with another A config; replay it with the active config")
        out, _ = rerun_b(run_dir, cfg)
        per_run.append(
            {
                "run_id": run_dir.name,
                "rerun_id": out.name,
                "alerts_B_before": _b_alert_counts(run_dir),
                "alerts_B": _b_alert_counts(out),
            }
        )
    return {"per_run": per_run}


def _trial_metrics(runs: list[Path], pid: str, cfg: RwConfig, env: cs.Env) -> tuple[dict, bool]:
    """Paths [A] and [A, live]: only `run --proposed` runs of this very proposal and config count (3.10)."""
    if not runs:
        raise cs.HitlError("change touches A: its report needs `run --proposed` trial runs on dev (spec 3.10)")
    per_run, live = [], False
    for run_dir in runs:
        m = load_manifest(run_dir)
        if m.proposal_id != pid or m.config_sha256 != cfg.sha256():
            raise cs.HitlError(f"{run_dir.name} is not a --proposed run of proposal {pid} with its config")
        if m.mode == "live":
            if m.machine_fingerprint != env.machine_fingerprint:
                raise cs.HitlError(f"{run_dir.name}: the live check was made on another machine")
            live = True
        per_run.append(
            {"run_id": run_dir.name, "mode": m.mode, "session_id": m.session_id, "alerts_B": _b_alert_counts(run_dir)}
        )
    return {"per_run": per_run}, live


# --- handlers ---------------------------------------------------------------------------------


def _hitl(a) -> int:
    root = Path(a.root)
    if a.cmd == "init":
        cs.init_store(root, a.approvers)
    elif a.cmd == "propose":
        print(cs.propose(root, _load_config(a.config), a.by))
    elif a.cmd == "report":
        _refuse_test_split(Path(a.dataset))
        cfg = cs.proposal_config(root, a.proposal)
        env = current_env(Path(a.dataset), cfg)
        ptr = cs.read_pointer(root)
        runs = [Path(r) for r in a.runs]
        if ptr and cfg.affected_by_change(cs.load_version(root, ptr.config_sha256)) - {"B"}:
            metrics, live = _trial_metrics(runs, a.proposal, cfg, env)
        else:
            metrics, live = _impact(runs, cfg), False
        sha = cs.make_report(root, a.proposal, env, metrics, live=live)
        report = json.loads((root / "reports" / f"{sha}.json").read_text(encoding="utf-8"))
        print(json.dumps({**report, "sha": sha}, indent=2))
    elif a.cmd == "approve":
        print(cs.approve(root, a.proposal, a.report, a.by).approval_id)
    elif a.cmd == "activate":
        cfg = cs.load_version(root, cs.load_approval(root, a.approval).config_sha256)
        print(cs.activate(root, a.approval, a.by, current_env(Path(a.dataset), cfg)).model_dump_json(indent=2))
    elif a.cmd == "rollback":
        print(cs.rollback(root, a.approval, a.by).model_dump_json(indent=2))
    elif a.cmd == "recover":
        print(json.dumps(cs.recover(root)))
    elif a.cmd == "status":
        ptr = cs.read_pointer(root)
        print(ptr.model_dump_json(indent=2) if ptr else "null")
    return 0


def _run(a) -> int:
    path, root = Path(a.session), Path(a.root)
    session = SessionManifest.model_validate_json(path.read_text(encoding="utf-8"))
    inp = RunInputs(
        video=path.parent / session.video_file,  # relative paths in a manifest are relative to the manifest
        session=session,
        gps_csv=path.parent / session.gps_file if session.gps_file else None,
        config_root=root,
        out_root=Path(a.out),
        mode=a.mode,
        driver_mode=a.driver_mode,
        active_arbiter=a.arbiter,
        proposed=(a.proposed, cs.proposal_config(root, a.proposed).sha256()) if a.proposed else None,
    )
    ledger = Path(a.test_ledger)
    try:
        run_dir = run(inp)
    except Exception as e:  # a failed attempt on a test split is evidence too (5.5); then fail as before
        evaluate.log_test_run(ledger, None, session, error=f"{type(e).__name__}: {e}")
        raise
    evaluate.log_test_run(ledger, load_manifest(run_dir), session)
    print(run_dir)
    return 0


def _rerun(a) -> int:
    cfg = _load_config(a.config) if a.config else None
    ledger = Path(a.test_ledger)
    rows = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    if cfg is not None and load_manifest(Path(a.run)).run_id in {json.loads(x)["run_id"] for x in rows}:
        # spec 5.5: test splits only see the approved, active config; its own config still reruns (AC-M10)
        raise cs.HitlError(f"{a.run} is a run on a test_* split ({ledger}): B is tuned with rerun-B on dev only")
    out, ok = rerun_b(Path(a.run), cfg, verify=a.verify, out_root=Path(a.out) if a.out else None)
    print(out)
    if ok is not None:
        print("verify: pass" if ok else "verify: FAIL (see verify.json)")
    return 1 if ok is False else 0


def _eval(a) -> int:
    lines = Path(a.labels).read_text(encoding="utf-8").splitlines()
    labels = [EventLabel.model_validate_json(x) for x in lines if x.strip()]
    runs = [Path(r) for r in a.runs]
    if not a.sessions:
        if len(runs) != 1:
            raise cs.HitlError("several runs are a dataset: give their session manifests with --sessions (spec 5.1)")
        report = evaluate.evaluate_run(runs[0], labels, a.lead_max_s, a.max_late_s, a.tau)
    else:
        if a.max_sync_uncertainty_ms is None:  # no default: the 0.5 s of spec 5.1 is still a proposal
            raise cs.HitlError("--sessions needs --max-sync-uncertainty-ms")
        found = [SessionManifest.model_validate_json(Path(p).read_text(encoding="utf-8")) for p in a.sessions]
        sessions = {s.session_id: s for s in found}
        missing = sorted({load_manifest(r).session_id for r in runs} - set(sessions))
        if missing:
            raise cs.HitlError(f"no session manifest given for {', '.join(missing)}")
        pairs = [(r, sessions[load_manifest(r).session_id]) for r in runs]
        report = evaluate.evaluate_dataset(pairs, labels, a.lead_max_s, a.max_late_s, a.tau, a.max_sync_uncertainty_ms)
    report["labels_sha256"] = file_sha256(a.labels)  # the label version these figures were scored against (5.5)
    print(json.dumps(report, indent=2))
    return 0


def _perf(a) -> int:
    print(json.dumps(evaluate.latency_report([Path(r) for r in a.runs], a.arbiter), indent=2))
    return 0


def _schema(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for model in SCHEMAS:
        (out / f"{model.SCHEMA}.json").write_text(json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
    print(out)
    return 0


def _check_run(a) -> int:
    """AC-M1: each run has the files of its mode (5.3), no lost records, valid and linked streams (4.6, D-7)."""
    failed = 0
    for run_dir in map(Path, a.runs):
        try:
            m = load_manifest(run_dir)
            missing = [f for f in REQUIRED[m.mode] if not (run_dir / f).exists()]
            if missing:
                raise ValueError(f"missing {', '.join(missing)} for a {m.mode} run (spec 5.3)")
            if "log_incomplete" in m.flags:
                raise ValueError("flag log_incomplete: the logger lost records (spec 3.8)")
            lines = {p.stem: p.read_text(encoding="utf-8").splitlines() for p in run_dir.glob("*.jsonl")}
            counts = {name: len(recs) for name, recs in check_streams(lines).items()}
            print(f"OK   {run_dir.name} mode={m.mode} flags={m.flags} {counts}")
        except (ValueError, OSError) as e:
            failed += 1
            print(f"FAIL {run_dir.name}: {e}")
    return 1 if failed else 0


def _compare(a) -> int:
    """AC-M10 (spec 5.4): two runs compared stream by stream on normalized business data."""
    result = {s: compare_stream(normalized(Path(a.run_a), s), normalized(Path(a.run_b), s)) for s in a.streams}
    print(json.dumps(result, indent=2))
    return 0 if all(r["first_difference"] is None for r in result.values()) else 1


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="roadwatch", description="RoadWatch Copilot CLI (BT-C)")
    sub = p.add_subparsers(dest="group", required=True)

    r = sub.add_parser("run", help="replay or live with the active, approved config")
    r.add_argument("--session", required=True, help="session manifest JSON")
    r.add_argument("--root", required=True, help="config store (configs/)")
    r.add_argument("--out", default="runs")
    r.add_argument("--mode", choices=("replay", "live"), default="replay")
    r.add_argument("--driver-mode", choices=("experienced", "novice"), default="experienced")
    r.add_argument("--arbiter", choices=("B", "baseline"), default="B", help="arbiter that drives the speaker (live)")
    r.add_argument("--proposed", metavar="PROPOSAL_ID", help="trial run for `hitl report` (3.10); activates nothing")
    r.add_argument("--test-ledger", default="eval/test_runs.jsonl", help="where runs on test_* splits are recorded")
    r.set_defaults(func=_run)

    rb = sub.add_parser("rerun-b", help="replay a run's decision journal through B")
    rb.add_argument("run")
    rb.add_argument("--config", help="YAML config to try; default: the run's own config")
    rb.add_argument("--verify", action="store_true", help="compare with the source run (spec 5.4)")
    rb.add_argument("--out")
    rb.add_argument("--test-ledger", default="eval/test_runs.jsonl", help="runs listed there take no other config")
    rb.set_defaults(func=_rerun)

    ev = sub.add_parser("eval", help="match B and baseline alerts to labels (spec 5.2)")
    ev.add_argument("runs", nargs="+", help="one run, or several with --sessions for the dataset report")
    ev.add_argument("--labels", required=True, help="EventLabel JSONL")
    ev.add_argument("--lead-max-s", type=float, required=True)  # OQ-A3: no default until decided
    ev.add_argument("--max-late-s", type=float, required=True)
    ev.add_argument("--tau", type=float, required=True)
    ev.add_argument("--sessions", nargs="*", default=[], help="session manifests of the runs (spec 5.1)")
    ev.add_argument("--max-sync-uncertainty-ms", type=float, help="sessions above it leave the main metrics")
    ev.set_defaults(func=_eval)

    pf = sub.add_parser("perf", help="L_alert per arbiter from live runs (spec 5.6)")
    pf.add_argument("runs", nargs="+")
    pf.add_argument("--arbiter", choices=("B", "baseline"), default="B")
    pf.set_defaults(func=_perf)

    sc = sub.add_parser("schema", help="write one JSON Schema file per contract")
    sc.add_argument("--out", required=True)
    sc.set_defaults(func=_schema)

    ck = sub.add_parser("check-run", help="AC-M1: every stream present, valid and linked")
    ck.add_argument("runs", nargs="+")
    ck.set_defaults(func=_check_run)

    cp = sub.add_parser("compare", help="AC-M10: two runs on normalized business data (spec 5.4)")
    cp.add_argument("run_a")
    cp.add_argument("run_b")
    cp.add_argument("--streams", nargs="+", default=["measurements"])
    cp.set_defaults(func=_compare)

    store = argparse.ArgumentParser(add_help=False)
    store.add_argument("--root", required=True, help="config store (configs/)")
    h = sub.add_parser("hitl", help="propose -> report -> approve (someone else) -> activate / rollback")
    h.set_defaults(func=_hitl)
    hs = h.add_subparsers(dest="cmd", required=True)
    hs.add_parser("init", parents=[store]).add_argument("--approvers", nargs="+", required=True)
    pr = hs.add_parser("propose", parents=[store])
    pr.add_argument("--config", required=True)
    pr.add_argument("--by", required=True)
    rp = hs.add_parser("report", parents=[store])
    rp.add_argument("--proposal", required=True)
    rp.add_argument("--runs", nargs="*", default=[], help="dev runs: plain for a B change, --proposed for A")
    rp.add_argument("--dataset", required=True, help="dataset manifest")
    ap = hs.add_parser("approve", parents=[store])
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--by", required=True)
    ac = hs.add_parser("activate", parents=[store])
    ac.add_argument("--approval", required=True)
    ac.add_argument("--by", required=True)
    ac.add_argument("--dataset", required=True, help="dataset manifest")
    rl = hs.add_parser("rollback", parents=[store])
    rl.add_argument("--approval", required=True)
    rl.add_argument("--by", required=True)
    hs.add_parser("recover", parents=[store])
    hs.add_parser("status", parents=[store])
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (cs.HitlError, cs.ConfigError, ValidationError, yaml.YAMLError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2  # refused; nothing was changed


if __name__ == "__main__":
    sys.exit(main())
