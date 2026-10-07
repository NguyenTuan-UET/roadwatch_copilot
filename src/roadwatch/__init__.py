"""RoadWatch: dashcam -> auto-calibration -> openpilot supercombo -> lane lines and lead-vehicle gap.

Warning-only research pipeline (no vehicle control), CPU, offline.
Vendored openpilot code (MIT, roadwatch/vendor/LICENSE.openpilot) is pinned to commaai/openpilot
c933446486e6923c8468a979b6fab890b46f5cdb and imported as the top-level package `g01T014VinAI` (renamed from `openpilot`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
