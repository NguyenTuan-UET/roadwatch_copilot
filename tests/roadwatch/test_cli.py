"""AC-M9: the HITL loop through the CLI (propose -> report -> approve by another person -> activate -> rollback)."""

import json

import yaml

from src.roadwatch import configstore as cs
from src.roadwatch.cli import main
from src.roadwatch.runtime import run
from tests.roadwatch.test_runtime import setup  # noqa: F401 - fixture reuse


def test_hitl_round_trip_through_the_cli(setup, tmp_path, monkeypatch, capsys):  # noqa: F811
    store = setup.config_root
    env = cs.Env(code_commit="c1", code_dirty=False, dataset_manifest_sha256="d", model_sha256="m", ort_version="1",
                 machine_fingerprint=None)
    monkeypatch.setattr("src.roadwatch.cli.current_env", lambda *a, **k: env)
    dev_run = run(setup)
    cfg, first_approval, _ = cs.load_active(store)
    proposed = cfg.model_dump(mode="json")
    proposed["dispatch"]["t_confirm_ms"] = 2500
    path = tmp_path / "proposed.yaml"
    path.write_text(yaml.safe_dump(proposed), encoding="utf-8")

    assert main(["hitl", "propose", "--root", str(store), "--config", str(path), "--by", "eng"]) == 0
    pid = capsys.readouterr().out.strip().splitlines()[-1]
    assert main(["hitl", "report", "--root", str(store), "--proposal", pid, "--runs", str(dev_run),
                 "--dataset", str(tmp_path / "none.json")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == "rerun-B" and report["metrics"]["per_run"][0]["alerts_B"]["warning"] == 1
    assert main(["hitl", "approve", "--root", str(store), "--proposal", pid, "--report", report["sha"],
                 "--by", "eng"]) == 2  # self-approval refused, non-zero exit
    capsys.readouterr()
    assert main(["hitl", "approve", "--root", str(store), "--proposal", pid, "--report", report["sha"],
                 "--by", "po"]) == 0
    approval_id = capsys.readouterr().out.strip().splitlines()[-1]
    assert main(["hitl", "activate", "--root", str(store), "--approval", approval_id, "--by", "po",
                 "--dataset", str(tmp_path / "none.json")]) == 0
    assert cs.load_active(store)[0].dispatch.t_confirm_ms == 2500
    assert main(["hitl", "rollback", "--root", str(store), "--approval", first_approval.approval_id, "--by", "po"]) == 0
    assert cs.load_active(store)[0].dispatch.t_confirm_ms == 1500


def test_schema_export_writes_one_file_per_contract(tmp_path):
    assert main(["schema", "--out", str(tmp_path)]) == 0
    names = {p.stem for p in tmp_path.glob("*.json")}
    assert {"rw.measurement", "rw.decision_input", "rw.alert", "rw.config"} <= names
