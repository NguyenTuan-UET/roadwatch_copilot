"""Regenerate the valid run fixtures after a contract change (spec 4.6, code-rules 9, WP-C3).

`python -m tests.roadwatch.make_fixtures` writes fixtures/valid/{replay,live}/ from the synthetic clip of
test_runtime.py. The invalid fixtures are small hand-edited folders: fix those by hand when a schema changes.
"""

import shutil
import tempfile
from pathlib import Path

from src.roadwatch.runtime import run
from tests.roadwatch.test_runtime import make_inputs

VALID = Path(__file__).parent / "fixtures" / "valid"


def main() -> None:
    inp = make_inputs(Path(tempfile.mkdtemp()))
    inp.play = lambda phrase: None  # live mode without a speaker
    for mode in ("replay", "live"):
        inp.mode = mode
        shutil.rmtree(VALID / mode, ignore_errors=True)
        shutil.copytree(run(inp), VALID / mode)


if __name__ == "__main__":
    main()
