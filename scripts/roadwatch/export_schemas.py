"""WP-P1: export current Pydantic shapes; this does not freeze or approve contracts."""

import argparse
import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from src.roadwatch.contracts.base import Q, Record
from src.roadwatch.contracts.config import ActivePointer, Approval, RwConfig
from src.roadwatch.contracts.streams import (
    AlertDecision,
    AudioEvent,
    AudioPlan,
    DecisionInput,
    DecisionTrace,
    EventLabel,
    FrameMeta,
    Measurement,
    RunManifest,
    SessionManifest,
    SpeedSample,
    SystemEvent,
)

OUTPUT = Path(__file__).resolve().parents[2] / "docs/specs/schemas/contracts.schema.json"
MODELS = (
    Q,
    FrameMeta,
    SpeedSample,
    Measurement,
    DecisionInput,
    DecisionTrace,
    AlertDecision,
    AudioPlan,
    AudioEvent,
    SystemEvent,
    RunManifest,
    SessionManifest,
    EventLabel,
    RwConfig,
    Approval,
    ActivePointer,
)


def render() -> str:
    refs, schema = models_json_schema([(model, "validation") for model in MODELS], by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "RoadWatch current implementation: contract shapes"
    schema["anyOf"] = [refs[(model, "validation")] for model in MODELS]
    schema["x-roadwatch"] = {
        "status": "implementation_snapshot",
        "stream_schema_version": Record.VERSION,
        "source": "src/roadwatch/contracts/",
        "semantics": "docs/specs/roadwatch-architecture.md, sections 4 and 12.3",
        "regenerate": "python -m scripts.roadwatch.export_schemas",
        "limitations": [
            "Not an approved or frozen v1.0 contract; known deviations remain in spec 12.3.",
            "model_validator, reader compatibility and cross-stream checks are not fully expressed in JSON Schema.",
            "Record input validators can fill schema/schema_version; writers emit these fields explicitly.",
        ],
    }
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed snapshot differs; do not write")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            print("Schema snapshot missing/stale. Run python -m scripts.roadwatch.export_schemas")
            return 1
        print("Schema snapshot matches Pydantic models.")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"Generated {OUTPUT.relative_to(OUTPUT.parents[3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
