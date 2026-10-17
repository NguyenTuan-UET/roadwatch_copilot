"""RoadWatch: dashcam -> auto-calibration -> gr14VinAI -> lane lines and lead-vehicle gap.

Warning-only research pipeline (no vehicle control), CPU, offline.
Vendored code is imported as the top-level package `g01T014VinAI`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
