"""Contract rules from spec §4 (ADR-08). Each test names the rule it guards."""

import json
import math

import pytest
from pydantic import ValidationError

from src.roadwatch.contracts.base import Q, canonical_json, check_stream, normalize, read_record
from src.roadwatch.contracts.config import Approval, RwConfig
from src.roadwatch.contracts.streams import (
    DecisionInput,
    FrameMeta,
    Lead,
    Measurement,
    MountCheck,
    Observation,
    SpeedSample,
)
from tests.roadwatch.factories import config_dict, lead_ok, measurement

# --- Q: null / status / sigma rules (4.0) ---------------------------------------------------


def test_q_ok_requires_value():
    with pytest.raises(ValidationError):
        Q(status="ok")


def test_q_missing_statuses_forbid_value():
    with pytest.raises(ValidationError):
        Q(value=0.0, status="unavailable", reasons=["no_frame"])  # 0 must never stand in for missing


def test_q_non_ok_requires_reason():
    with pytest.raises(ValidationError):
        Q(status="unreliable", value=12.0)


def test_q_rejects_nan_and_negative_sigma():
    with pytest.raises(ValidationError):
        Q(status="ok", value=math.nan)
    with pytest.raises(ValidationError):
        Q(status="ok", value=10.0, sigma=-1.0)


def test_q_unreliable_may_keep_value_for_analysis():
    assert Q(status="unreliable", value=55.0, reasons=["mount_suspect"]).value == 55.0


# --- null matrix (4.2) ---------------------------------------------------------------------


def test_no_lead_is_only_valid_when_observation_ok():
    with pytest.raises(ValidationError):
        measurement(
            observation=Observation(status="unreliable", reasons=["dark"]),
            lead=Lead(status="not_applicable", reasons=["no_vehicle"]),
            distance_m=Q.missing("unavailable", "no_lead"),
            ttc_s=Q.missing("unavailable", "no_lead"),
        )


def test_lead_identity_fields_must_be_null_without_lead():
    with pytest.raises(ValidationError):
        Lead(status="not_applicable", reasons=["no_vehicle"], track_id=3)


def test_placeholder_frame_has_null_index_and_unavailable_measurement():
    FrameMeta(
        run_id="r",
        seq=0,
        t_ns=100,
        sched_n=1,
        status="unavailable",
        reasons=["decode_error"],
        frame_idx=None,
        pts_ns=None,
        video_sha256="v",
    )
    with pytest.raises(ValidationError):  # placeholder cannot carry a frame index
        FrameMeta(
            run_id="r",
            seq=0,
            t_ns=100,
            sched_n=1,
            status="unavailable",
            reasons=["decode_error"],
            frame_idx=5,
            pts_ns=None,
            video_sha256="v",
        )
    with pytest.raises(ValidationError):  # no frame => observation cannot be ok
        measurement(frame_idx=None)


def test_distance_cannot_be_ok_without_lead():
    with pytest.raises(ValidationError):
        measurement(lead=Lead(status="not_applicable", reasons=["no_vehicle"]), distance_m=Q(status="ok", value=40.0))


def test_speed_sample_receive_not_before_fix():
    with pytest.raises(ValidationError):
        SpeedSample(
            run_id="r",
            seq=0,
            t_ns=5,
            gps_idx=0,
            t_fix_ns=10,
            t_recv_ns=5,
            t_recv_basis="logged",
            speed_mps=Q(status="ok", value=25.0),
            source="gps",
            session_id="s",
        )


def test_tick_input_has_no_ref():
    with pytest.raises(ValidationError):
        DecisionInput(
            run_id="r", seq=0, t_ns=0, kind="tick", ref={"stream": "measurements", "seq": 0}, tick_n=0, t_consumed_ns=0
        )


# --- unknown fields and versions (4.0, 4.6) --------------------------------------------------


def test_writer_rejects_unknown_field():
    with pytest.raises(ValidationError):
        MountCheck(state="ok", since_t_ns=0, surprise=1)


def test_reader_ignores_unknown_fields_of_same_major():
    data = json.loads(measurement().model_dump_json(by_alias=True))
    data["schema_version"] = "0.9.0"
    data["new_top"] = 1
    data["lead"]["new_nested"] = 2
    rec = read_record(json.dumps(data), Measurement)
    assert rec.lead.track_id == 7


def test_reader_refuses_other_major():
    data = json.loads(measurement().model_dump_json(by_alias=True))
    data["schema_version"] = "1.0.0"
    with pytest.raises(ValueError, match="MAJOR"):
        read_record(json.dumps(data), Measurement)


def test_json_schema_export():
    schema = Measurement.model_json_schema(by_alias=True)
    assert "distance_m" in schema["properties"]


# --- stream integrity and normalisation (4.0, 5.4) ------------------------------------------


def test_stream_seq_gap_is_detected():
    with pytest.raises(ValueError, match="seq"):
        check_stream([measurement(seq=0), measurement(seq=2)])


def test_stream_time_going_back_is_detected():
    with pytest.raises(ValueError, match="t_ns"):
        check_stream([measurement(seq=0, t_ns=200), measurement(seq=1, t_ns=100)])


def test_normalize_drops_run_identity_and_mono_times():
    a = json.loads(measurement().model_dump_json(by_alias=True))
    b = dict(a, run_id="other")
    a["t_arrive_mono_ns"] = 1
    assert normalize(a) == normalize(b)
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


# --- config guardrails (4.5, 3.7) ------------------------------------------------------------


def test_config_valid_fixture_loads():
    assert RwConfig.model_validate(config_dict()).ttc.ttc_emergency_s > 0


@pytest.mark.parametrize(
    "path,value",
    [
        (("ttc", "ttc_emergency_s"), 99.0),  # outside hard bound: cannot disable emergency indirectly
        (("dispatch", "t_hold_ms"), 10**7),  # HOLD cannot swallow episodes indefinitely
        (("legal_table", "legal_ref"), ""),  # legal table must cite its source
        (("dispatch", "novice_margin_m"), -5.0),  # cannot go below the legal table
    ],
)
def test_config_guardrails(path, value):
    data = config_dict()
    data[path[0]][path[1]] = value
    with pytest.raises(ValidationError):
        RwConfig.model_validate(data)


def test_config_has_no_vehicle_control_field():
    data = config_dict()
    data["actuation"] = {"brake": True}
    with pytest.raises(ValidationError):
        RwConfig.model_validate(data)


def test_approval_id_is_content_hash():
    a = Approval.create(
        config_sha256="c",
        proposer="p",
        approver="q",
        approved_at="2026-09-28T10:00:00Z",
        report_sha256="r",
        base_config_sha256="b",
        dataset_manifest_sha256="d",
        code_commit="x",
        model_sha256="m",
        ort_version="1",
        machine_fingerprint=None,
    )
    assert a.approval_id == a.expected_id()
    with pytest.raises(ValidationError):
        Approval.create(
            config_sha256="c",
            proposer="p",
            approver="p",
            approved_at="t",
            report_sha256="r",
            base_config_sha256="b",
            dataset_manifest_sha256="d",
            code_commit="x",
            model_sha256="m",
            ort_version="1",
            machine_fingerprint=None,
        )


def test_lead_ok_factory_is_valid():
    assert lead_ok().status == "ok"
