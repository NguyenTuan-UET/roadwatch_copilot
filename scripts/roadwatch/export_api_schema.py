"""Write the demo server's OpenAPI document for front-end developers; `--check` fails when it is stale.

    python -m scripts.roadwatch.export_api_schema [--check]
"""
import json
import sys
from pathlib import Path

from src.roadwatch import schemas
from src.roadwatch.web import app

OUT = Path(__file__).resolve().parents[2] / 'src/roadwatch/openapi.json'


def document():
    doc = app.openapi()
    # The SSE payload is not a response body FastAPI can see: publish LiveStatus explicitly.
    doc['components']['schemas']['LiveStatus'] = schemas.LiveStatus.model_json_schema(
        ref_template='#/components/schemas/{model}')
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + '\n'


if __name__ == '__main__':
    text = document()
    if '--check' in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding='utf-8') != text:
            sys.exit(f'{OUT.name} is stale: run python -m scripts.roadwatch.export_api_schema')
        print(f'{OUT.name} up to date')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding='utf-8')
        print(f'wrote {OUT}')
