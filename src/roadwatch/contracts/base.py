"""Shared contract types (spec §4.0): strict writer models, the Q quantity, stream envelope, readers."""

import hashlib
import json
import logging
from typing import Any, ClassVar, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

log = logging.getLogger(__name__)

Status = Literal["ok", "not_applicable", "unavailable", "unreliable"]


class Strict(BaseModel):
    """Writers never emit unknown fields; NaN/inf are rejected at construction, not turned into null."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True, populate_by_name=True)


class Q(Strict):
    """A measured quantity; the unit lives in the field name (distance_m, ttc_s, ...)."""

    value: float | None = None
    status: Status
    sigma: float | None = Field(default=None, ge=0)
    reasons: list[str] = []

    @model_validator(mode="after")
    def _rules(self):
        if self.status == "ok" and self.value is None:
            raise ValueError("status ok requires a value")
        if self.status in ("not_applicable", "unavailable") and self.value is not None:
            raise ValueError(f"status {self.status} requires value=null (never 0)")
        if self.status != "ok" and not self.reasons:
            raise ValueError("non-ok status requires reasons")
        return self

    @classmethod
    def ok(cls, value: float, sigma: float | None = None) -> "Q":
        return cls(value=value, status="ok", sigma=sigma)

    @classmethod
    def missing(cls, status: Status, *reasons: str, value: float | None = None) -> "Q":
        return cls(value=value, status=status, reasons=list(reasons))

    @property
    def usable(self) -> bool:
        return self.status == "ok"


class Record(Strict):
    """Envelope of every stream record. seq counts records of one stream in one run."""

    SCHEMA: ClassVar[str] = ""
    VERSION: ClassVar[str] = "0.1.0"

    schema_name: str = Field(alias="schema")
    schema_version: str
    run_id: str
    seq: int = Field(ge=0)
    t_ns: int
    clock: Literal["session"] = "session"

    @model_validator(mode="before")
    @classmethod
    def _fill_schema(cls, data: Any):
        if isinstance(data, dict):
            data = dict(data)
            data.setdefault("schema", cls.SCHEMA)
            data.setdefault("schema_version", cls.VERSION)
        return data

    @model_validator(mode="after")
    def _check_schema(self):
        if self.schema_name != self.SCHEMA:
            raise ValueError(f"schema {self.schema_name!r} is not {self.SCHEMA!r}")
        return self

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def _major(version: str) -> str:
    return version.split(".", 1)[0]


def _pop(data: Any, loc: tuple) -> None:
    for key in loc[:-1]:
        data = data[key]
    data.pop(loc[-1], None)


_warned: set[tuple[str, tuple]] = set()


R = TypeVar("R", bound=Record)


def read_record(line: str | dict, model: type[R], strict: bool = False) -> R:
    """Reader side of 4.0: refuse another MAJOR; ignore (and log once) unknown fields of the same MAJOR.

    strict=True checks a writer's output instead (fixtures, run checks): an unknown field is an error (4.6).
    """
    data = json.loads(line) if isinstance(line, str) else dict(line)
    version = str(data.get("schema_version", ""))
    if _major(version) != _major(model.VERSION):
        raise ValueError(f"{model.SCHEMA}: MAJOR mismatch, got {version!r}, reader is {model.VERSION}")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        errors = e.errors()
        extras = [tuple(err["loc"]) for err in errors if err["type"] == "extra_forbidden"]
        if strict or not extras or len(extras) != len(errors):
            raise
        for loc in extras:
            _pop(data, loc)
            if (model.SCHEMA, loc) not in _warned:
                _warned.add((model.SCHEMA, loc))
                log.warning("%s: ignoring unknown field %s (schema %s)", model.SCHEMA, ".".join(map(str, loc)), version)
        return model.model_validate(data)


def check_stream(records: list[Record], time_attr: str | None = "t_ns") -> None:
    """seq must start at 0 and step by 1 (a gap = lost record); time (time_attr) must not go back."""
    for i, rec in enumerate(records):
        if rec.seq != i:
            raise ValueError(f"{rec.SCHEMA}: seq gap, expected {i} got {rec.seq}")
        if time_attr and i and getattr(rec, time_attr) < getattr(records[i - 1], time_attr):
            raise ValueError(f"{rec.SCHEMA}: {time_attr} goes back at seq {rec.seq}")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_hex(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


_VOLATILE = ("run_id", "output_latency_ms")


def normalize(obj: Any) -> Any:
    """Business content only (5.4): drop run identity and monotonic/device timings, recursively."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items() if k not in _VOLATILE and not k.endswith("_mono_ns")}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj
