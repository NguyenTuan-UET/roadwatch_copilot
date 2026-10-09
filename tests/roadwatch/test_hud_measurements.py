from types import SimpleNamespace

import numpy as np
import pytest

from src.roadwatch.hud import distance_sigma, draw_measurement_panel
from src.roadwatch.schemas import Lead


def test_uncertainty_is_absent_without_a_lead_or_finite_model_std():
    r = SimpleNamespace(gap_m=27.0, outputs={'lead_stds': np.array([[[[2.0]]]])})
    assert distance_sigma(r) == 2.0
    r.gap_m = None
    assert distance_sigma(r) is None
    r.gap_m = 27.0
    r.outputs['lead_stds'][0, 0, 0, 0] = np.nan
    assert distance_sigma(r) is None
    r.outputs = {}
    assert distance_sigma(r) is None


def test_reference_and_uncertainty_are_optional_and_not_zero_filled():
    lead = Lead(prob=0.9, gap_m=27, speed_kmh=36)
    assert lead.sigma_m is None and lead.radar_m is None and lead.delta_m is None
    reference = Lead(prob=0.9, gap_m=27, speed_kmh=36, sigma_m=2, radar_m=27.4, delta_m=-0.4)
    assert reference.delta_m == -0.4
    with pytest.raises(ValueError):
        Lead(prob=0.9, gap_m=27, speed_kmh=36, sigma_m=float('nan'))


def test_measurement_card_fits_small_video_frames():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    assert draw_measurement_panel(frame, 27, 2, 36, 27.4, -0.4) is frame
    assert np.any(frame[90:])
