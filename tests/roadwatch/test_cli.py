"""Command line (python -m src.roadwatch): options and pre-pass of comma_ai realtime_lead.py."""
import subprocess

import numpy as np
import pytest

from src.roadwatch import __main__ as cli
from src.roadwatch import gps as gpslib
from src.roadwatch.calibration import AutoCalib


class FakeModel:
    """Ego at `v` m/s per model tick, driving straight; road and camera level."""
    def __init__(self, v=12.):
        self.v, self.steps = v, 0

    def reset(self):
        pass

    def step(self, _):
        self.steps += 1
        return dict(pose=np.array([[self.v, 0, 0, 0, 0, 0]]), road_transform=np.array([[0, 0, 1.3, 0, 0, 0]]),
                    road_transform_stds=np.zeros((1, 6)))


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'v.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=gray:s=320x240:r=20:d=6', str(path)], check=True)
    return path


def test_prepass_settles_the_angles(video):
    m, cal = FakeModel(), AutoCalib()
    fy, cal = cli.prepass(m, video, (0, 0, 320, 240), 20., 300., cal, 2.)
    assert fy == 300. and cal.settled and m.steps == 41   # 2 s at 20 Hz (frames 0..40), one pass


def test_prepass_fits_the_focal_length_to_the_gps_speed(video):
    """The model reads 12 m/s where the GPS says 10: the assumed fy is 1.2x too short."""
    gps = gpslib.GpsRef(np.arange(0., 10.), np.full(10, 10.), 0.)
    fy, _ = cli.prepass(FakeModel(), video, (0, 0, 320, 240), 20., 300., AutoCalib(), 5., gps=gps, fit_focal=True,
                        max_iter=1)   # the fake model does not react to fy: one pass
    assert fy == pytest.approx(300 / 1.2)


def test_crop_option_like_realtime_lead():
    assert cli._crop('auto') == 'auto' and cli._crop('none') == 'full' and cli._crop('0,10,320,200') == (0, 10, 320, 200)
