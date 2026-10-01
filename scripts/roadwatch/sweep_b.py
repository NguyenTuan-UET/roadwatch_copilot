"""WP-B3: try B parameter values on dev runs with rerun-B and print the label-matched metrics of each.

    python -m scripts.roadwatch.sweep_b --runs runs/<a> runs/<b> --sessions <a>.json <b>.json \\
        --labels data/labels/dev.jsonl --lead-max-s <s> --max-late-s <s> --tau <iou> \\
        --max-sync-uncertainty-ms <ms> --set dispatch.t_confirm_ms=1000,1500,2000 --set dispatch.h_m=3,5

One JSON line per combination: the values set, then the main metrics of `evaluate_dataset` for B and the baseline.
Nothing is proposed or activated: write the chosen values to a file under config/proposals/ and go through
`hitl` (spec 3.10). Only sections that affect B alone can be swept (anything else needs a replay), and only
dev sessions (spec 5.5).
"""

import argparse
import itertools
import json
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import yaml

from src.roadwatch.contracts.config import RwConfig
from src.roadwatch.contracts.streams import EventLabel, SessionManifest
from src.roadwatch.evaluate import evaluate_dataset
from src.roadwatch.rerun import load_manifest, load_run_config, rerun_b

SHOWN = ("unmatched", "repeated", "first_match", "recall", "alerts_per_hour")


def parse_grid(specs: list[str]) -> dict[str, list]:
    """["dispatch.t_confirm_ms=1000,1500"] -> {"dispatch.t_confirm_ms": [1000, 1500]}"""
    grid = {}
    for spec in specs:
        key, values = spec.split("=", 1)
        grid[key] = [yaml.safe_load(v) for v in values.split(",")]
    return grid


def sweep(runs: list[tuple[Path, SessionManifest]], labels: list[EventLabel], grid: dict[str, list], **eval_params) -> Iterator[dict]:
    for _, session in runs:
        if session.split.startswith("test_"):
            raise ValueError(f"session {session.session_id} is {session.split}: B is tuned on dev only (spec 5.5)")
    for key in grid:
        section = key.split(".")[0]
        if RwConfig.AFFECTS.get(section) != ("B",):
            raise ValueError(f"{key}: section {section!r} does not affect B alone; such a change needs a replay")
    for values in itertools.product(*grid.values()):
        combo = dict(zip(grid, values, strict=True))
        reruns = []
        try:
            for run_dir, session in runs:
                data = load_run_config(run_dir).model_dump(mode="json")
                for key, value in combo.items():
                    section, name = key.split(".")
                    if name not in data[section]:
                        raise ValueError(f"unknown parameter {key}")
                    data[section][name] = value
                # rerun-B writes next to the source run, where evaluate finds the frames and measurements
                reruns.append((rerun_b(run_dir, RwConfig.model_validate(data))[0], session))
            result = evaluate_dataset(reruns, labels, **eval_params)["main"]
        finally:
            for rerun_dir, _ in reruns:
                shutil.rmtree(rerun_dir, ignore_errors=True)
        row = {"set": combo, "runs": result["runs"], "events_must_alert": result["events_must_alert"]}
        row.update({arb: {k: result[arb][k] for k in SHOWN} for arb in ("B", "baseline")})
        yield {**row, "unmatched_reduction": result["unmatched_reduction"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--runs", nargs="+", required=True, help="dev replay runs made with the active config")
    p.add_argument("--sessions", nargs="+", required=True, help="session manifests of those runs")
    p.add_argument("--labels", required=True, help="EventLabel JSONL (dev)")
    p.add_argument("--lead-max-s", type=float, required=True)
    p.add_argument("--max-late-s", type=float, required=True)
    p.add_argument("--tau", type=float, required=True)
    p.add_argument("--max-sync-uncertainty-ms", type=float, required=True)
    p.add_argument("--set", action="append", required=True, metavar="SECTION.KEY=V1,V2", dest="grid")
    a = p.parse_args(argv)
    found = [SessionManifest.model_validate_json(Path(s).read_text(encoding="utf-8")) for s in a.sessions]
    sessions = {s.session_id: s for s in found}
    runs = [(Path(r), sessions[load_manifest(Path(r)).session_id]) for r in a.runs]
    lines = Path(a.labels).read_text(encoding="utf-8").splitlines()
    labels = [EventLabel.model_validate_json(x) for x in lines if x.strip()]
    params = dict(
        lead_max_s=a.lead_max_s, max_late_s=a.max_late_s, tau=a.tau, max_sync_uncertainty_ms=a.max_sync_uncertainty_ms
    )
    for row in sweep(runs, labels, parse_grid(a.grid), **params):
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
