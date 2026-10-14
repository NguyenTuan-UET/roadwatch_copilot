"""Radar log of a run: a CSV of the distance to the car ahead over video time (the Lab's radar reference, as a file)."""
import numpy as np
import pytest

from src.roadwatch.radar import RadarRef, load_radar


def _csv(tmp_path, text, name='radar.csv'):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_load_radar_reads_time_and_distance_and_keeps_gaps(tmp_path):
    t, d = load_radar(_csv(tmp_path, 't,radar_m\n0,50.0\n0.05,49.5\n0.10,\n0.15,nan\n0.20,48.7\n0.25,48.2\n'))
    assert list(t) == [0., .05, .10, .15, .20, .25]
    assert d[0] == 50. and d[1] == 49.5 and np.isnan(d[2]) and np.isnan(d[3]) and d[5] == 48.2   # no track = NaN, not 0


@pytest.mark.parametrize('header', ['t_s,distance_m', 'time,dist', 'time_s,d', 'T,RADAR_M'])
def test_load_radar_accepts_common_column_names(tmp_path, header):
    t, d = load_radar(_csv(tmp_path, header + '\n0,30\n1,31\n2,32\n'))
    assert list(d) == [30., 31., 32.]


@pytest.mark.parametrize('text', ['a,b\n1,2\n3,4\n5,6\n', 't,radar_m\n0,30\n1,31\n', 't,radar_m\n0,nan\n1,\n2,nan\n3,\n',
                                  't,radar_m\n0,-5\n1,0\n2,900\n3,1000\n'])
def test_load_radar_rejects_files_without_a_usable_distance(tmp_path, text):
    with pytest.raises(ValueError):
        load_radar(_csv(tmp_path, text))


def test_load_radar_sorts_by_time_and_drops_out_of_range_distances(tmp_path):
    t, d = load_radar(_csv(tmp_path, 't,radar_m\n2,32\n0,30\n1,999\n3,33\n4,34\n'))
    assert list(t) == [0., 1., 2., 3., 4.] and np.isnan(d[1]) and list(d[[0, 2, 3, 4]]) == [30., 32., 33., 34.]


def test_radar_ref_gives_the_nearest_sample_only_when_it_is_close():
    ref = RadarRef(np.array([0., .05, .10, 1.0]), np.array([50., 49., np.nan, 40.]))
    assert ref(0.) == 50. and ref(.06) == 49. and ref(.9) == 40.         # nearest within 0.15 s
    assert np.isnan(ref(.10)) and np.isnan(ref(.5)) and np.isnan(ref(-1.)) and np.isnan(ref(5.))   # NaN sample, gap, outside
