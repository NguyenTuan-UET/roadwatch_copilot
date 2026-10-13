import threading

import numpy as np
import pytest

from src.roadwatch import phone


def frame(w=64, h=48, val=0):
    return np.full((h * 3 // 2, w), val, np.uint8)   # yuv420p as av's to_ndarray gives it


def take(src, n, stop=None):
    out = []
    for planes, pts in src.frames(stop or threading.Event()):
        out.append((planes, pts))
        if len(out) == n:
            break
    return out


def test_frames_keep_only_the_newest_and_follow_the_session_clock():
    src = phone.FrameSource()
    src.push(frame(val=1), 1.00)
    src.push(frame(val=2), 1.03)   # not taken yet: replaced (live never queues old frames)
    (planes, pts), = take(src, 1)
    assert pts == 1.03 and planes[0][0, 0] == 2 and src.dropped == 1
    y, u, v = planes
    assert y.shape == (48, 64) and u.shape == v.shape == (24, 32)


def test_frames_are_handed_out_near_the_model_rate():
    src, got = phone.FrameSource(), []
    for k in range(61):   # a 30 fps phone for 2 s, the run keeping up
        src.push(frame(), k / 30)
        if (f := src.poll()) is not None:
            got.append(f[1])
    gaps = np.diff(got)
    assert 38 <= len(got) <= 42 and gaps.min() > .02 and abs(gaps.mean() - phone.MODEL_DT) < .005


def test_a_slow_run_takes_the_newest_frame_and_goes_on_from_there():
    src = phone.FrameSource()
    src.push(frame(), 0.)
    src.poll()
    for k in range(1, 30):   # the model was busy for 1 s
        src.push(frame(), k / 30)
    assert src.poll()[1] == 29 / 30 and src.dropped == 28
    src.push(frame(), 30 / 30)
    assert src.poll() is None   # 33 ms later: too early for the next tick
    src.push(frame(), 31 / 30)
    assert src.poll()[1] == 31 / 30


def test_a_frame_of_another_size_is_scaled_to_the_first():
    src = phone.FrameSource()
    src.push(frame(64, 48), 0.)
    take(src, 1)
    src.push(frame(32, 24, 9), .1)   # WebRTC lowered the resolution
    (planes, _), = take(src, 1)
    assert planes[0].shape == (48, 64)
    assert src.size == (64, 48)


def test_frames_end_when_closed_or_stopped():
    src = phone.FrameSource()
    src.close()
    assert take(src, 1) == []
    src, stop = phone.FrameSource(), threading.Event()
    stop.set()
    assert take(src, 1, stop) == []


def test_wait_size_gives_up_without_frames():
    src = phone.FrameSource()
    with pytest.raises(RuntimeError):
        src.wait_size(threading.Event(), timeout=.05)
    src.push(frame(66, 50), 0.)   # odd sizes made even (I420 planes are half-size)
    assert src.wait_size(threading.Event()) == (66, 50)


def test_live_gps_gives_the_newest_fresh_speed():
    gps = phone.LiveGps()
    assert np.isnan(gps(1.))
    gps.add(1., dict(speed=20., lat=10.0, lon=106.0, acc=5.))
    gps.add(2., dict(speed=22., lat=10.0002, lon=106.0, acc=5.))
    assert gps(2.5) == 22.
    assert np.isnan(gps(2. + phone.LiveGps.STALE_S + .1))   # stale: no speed, so no legal threshold
    assert gps.synced and not gps.low_confidence   # same clock as the frames: nothing to align


def test_live_gps_computes_the_speed_from_positions_when_the_phone_gives_none():
    gps = phone.LiveGps()
    gps.add(0., dict(speed=None, lat=10.0, lon=106.0, acc=5.))
    gps.add(1., dict(speed=None, lat=10.0002, lon=106.0, acc=5.))   # ~22 m north in 1 s
    assert gps(1.) == pytest.approx(22.2, abs=.3)


def test_live_gps_ignores_bad_fixes_and_is_saved(tmp_path):
    gps = phone.LiveGps()
    gps.add(0., dict(speed=-1., lat=10., lon=106., acc=5.))      # iOS: -1 = unknown
    gps.add(.5, dict(speed=25., lat=10., lon=106., acc=500.))    # too inaccurate
    gps.add(1., 'not a fix')
    assert np.isnan(gps(1.)) and gps.count == 0
    gps.add(2., dict(speed=25., lat=10., lon=106., acc=8.))
    gps.save(tmp_path / 'gps.csv')
    assert (tmp_path / 'gps.csv').read_text().splitlines() == ['t,speed_mps,lat,lon,accuracy_m', '2.000,25.000,10.0000000,106.0000000,8.0']
