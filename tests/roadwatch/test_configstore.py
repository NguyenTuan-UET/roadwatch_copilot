"""Config store and HITL (spec §3.10, ADR-11, F23, F24)."""

import json
import os

import pytest

from src.roadwatch import configstore as cs
from src.roadwatch.contracts.config import RwConfig
from tests.roadwatch.factories import config_dict

ENV = cs.Env(
    code_commit="c1",
    code_dirty=False,
    dataset_manifest_sha256="d1",
    model_sha256="m1",
    ort_version="1.30",
    machine_fingerprint="pc1",
)


def _cfg(**dispatch) -> RwConfig:
    data = config_dict()
    data["dispatch"].update(dispatch)
    return RwConfig.model_validate(data)


def _approve(root, cfg, proposer="eng", approver="po", env=ENV, live=False):
    pid = cs.propose(root, cfg, proposer)
    report = cs.make_report(root, pid, env, metrics={"note": "test"}, live=live)
    return cs.approve(root, pid, report, approver)


@pytest.fixture
def root(tmp_path):
    cs.init_store(tmp_path, approvers=["po", "lead"])
    return tmp_path


def _activate_first(root):
    appr = _approve(root, _cfg())
    cs.activate(root, appr.approval_id, "po", ENV)
    return appr


def test_runtime_loads_the_approved_active_config(root):
    appr = _activate_first(root)
    cfg, loaded, ptr = cs.load_active(root)
    assert ptr.approval_id == appr.approval_id and cfg.sha256() == appr.config_sha256


def test_runtime_refuses_tampered_version(root):
    appr = _activate_first(root)
    path = root / "versions" / f"{appr.config_sha256}.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("t_confirm_ms: 1500", "t_confirm_ms: 1"), encoding="utf-8")
    with pytest.raises(cs.ConfigError, match="hash"):
        cs.load_active(root)


def test_runtime_refuses_missing_or_mismatched_approval(root):
    appr = _activate_first(root)
    (root / "approvals" / f"{appr.approval_id}.json").unlink()
    with pytest.raises(cs.ConfigError, match="approval"):
        cs.load_active(root)


def test_runtime_refuses_when_nothing_is_active(root):
    with pytest.raises(cs.ConfigError, match="active"):
        cs.load_active(root)


def test_self_approval_and_non_approver_are_rejected(root):
    with pytest.raises(cs.HitlError):
        _approve(root, _cfg(), proposer="po", approver="po")
    with pytest.raises(cs.HitlError, match="approver"):
        _approve(root, _cfg(), proposer="eng", approver="intern")


def test_report_made_before_another_activation_is_stale(root):
    _activate_first(root)
    late = _approve(root, _cfg(t_confirm_ms=1000))
    other = _approve(root, _cfg(t_confirm_ms=1200))
    cs.activate(root, other.approval_id, "po", ENV)
    with pytest.raises(cs.HitlError, match="rebase"):
        cs.activate(root, late.approval_id, "po", ENV)


def test_activation_requires_the_approved_code_and_a_clean_tree(root):
    appr = _approve(root, _cfg())
    with pytest.raises(cs.HitlError, match="code_commit"):
        cs.activate(root, appr.approval_id, "po", cs.Env(**{**ENV.__dict__, "code_commit": "c2"}))
    with pytest.raises(cs.HitlError, match="dirty"):
        cs.activate(root, appr.approval_id, "po", cs.Env(**{**ENV.__dict__, "code_dirty": True}))


def test_live_checked_change_is_bound_to_the_machine(root):
    _activate_first(root)
    data = config_dict()
    data["runtime"]["process_hz"] = 12.0
    appr = _approve(root, RwConfig.model_validate(data), live=True)
    assert appr.machine_fingerprint == "pc1"
    with pytest.raises(cs.HitlError, match="machine"):
        cs.activate(root, appr.approval_id, "po", cs.Env(**{**ENV.__dict__, "machine_fingerprint": "pc2"}))


def test_live_path_is_mandatory_for_runtime_sections(root):
    _activate_first(root)
    data = config_dict()
    data["runtime"]["process_hz"] = 12.0
    pid = cs.propose(root, RwConfig.model_validate(data), "eng")
    with pytest.raises(cs.HitlError, match="live"):
        cs.make_report(root, pid, ENV, metrics={}, live=False)


def test_rollback_reactivates_a_previous_approval(root):
    first = _activate_first(root)
    second = _approve(root, _cfg(t_confirm_ms=1000))
    cs.activate(root, second.approval_id, "po", ENV)
    cs.rollback(root, first.approval_id, "lead")
    assert cs.load_active(root)[2].approval_id == first.approval_id
    with pytest.raises(cs.HitlError, match="approver"):
        cs.rollback(root, second.approval_id, "eng")


def test_crash_before_commit_point_is_aborted_on_recovery(root, monkeypatch):
    first = _activate_first(root)
    second = _approve(root, _cfg(t_confirm_ms=1000))
    monkeypatch.setattr(cs.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("power cut")))
    with pytest.raises(OSError):
        cs.activate(root, second.approval_id, "po", ENV)
    monkeypatch.setattr(cs.os, "replace", os.replace)
    assert cs.recover(root) == {"aborted": 1, "committed": 0}
    assert cs.load_active(root)[2].approval_id == first.approval_id


def test_crash_after_commit_point_is_completed_on_recovery(root, monkeypatch):
    _activate_first(root)
    second = _approve(root, _cfg(t_confirm_ms=1000))
    monkeypatch.setattr(cs, "_mark_committed", lambda *a: (_ for _ in ()).throw(OSError("power cut")))
    with pytest.raises(OSError):
        cs.activate(root, second.approval_id, "po", ENV)
    monkeypatch.undo()
    assert cs.recover(root) == {"aborted": 0, "committed": 1}
    assert cs.load_active(root)[2].approval_id == second.approval_id


def test_inconsistent_pointer_locks_hitl(root):
    _activate_first(root)
    second = _approve(root, _cfg(t_confirm_ms=1000))
    with cs.hitl_session(root) as con:
        con.execute(
            "INSERT INTO activations VALUES ('x', ?, 'aaa', 'bbb', 'po', 't', 'pending', 'activate')",
            (second.approval_id,),
        )
    with pytest.raises(cs.HitlError, match="inconsistent"):
        cs.recover(root)


def test_lock_is_exclusive(root):
    with cs.FileLock(root / ".hitl.lock"):
        with pytest.raises(cs.HitlError, match="busy"):
            cs.FileLock(root / ".hitl.lock", timeout_s=0.2).__enter__()


def test_approval_files_are_immutable_and_distinct_per_approval(root):
    cfg = _cfg()
    a1 = _approve(root, cfg)
    a2 = _approve(root, cfg)
    assert a1.approval_id != a2.approval_id
    assert json.loads((root / "approvals" / f"{a1.approval_id}.json").read_text())["config_sha256"] == cfg.sha256()


def test_runtime_refuses_pointer_pairing_an_approval_with_another_config(root):
    first = _activate_first(root)
    other = _cfg(t_confirm_ms=1000)
    cs.propose(root, other, "eng")  # the version file exists but was never approved
    ptr = json.loads((root / "active.json").read_text())
    ptr["config_sha256"] = other.sha256()  # hand-edited pointer keeps the old approval
    (root / "active.json").write_text(json.dumps(ptr))
    assert first.config_sha256 != other.sha256()
    with pytest.raises(cs.ConfigError, match="another config"):
        cs.load_active(root)
