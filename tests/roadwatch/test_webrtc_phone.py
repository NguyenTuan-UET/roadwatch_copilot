import asyncio
import json
from types import SimpleNamespace

import pytest
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from fastapi import HTTPException

from src.roadwatch import phone
from src.roadwatch import schemas as api
from src.roadwatch.webrtc import PhoneReceiver


def test_phone_overlay_is_sent_on_its_webrtc_channel_once_per_frame():
    class Channel:
        def __init__(self):
            self.readyState = 'open'
            self.sent = []
        def send(self, message):
            self.sent.append(json.loads(message))

    async def go():
        rx = PhoneReceiver(api.RtcConfig(iceServers=[]))
        rx.pc = SimpleNamespace(connectionState='connected')
        rx.channel = Channel()
        lane = {'left': [[.1, .2]], 'right': [[.9, .2]]}
        lead = {'u': .5, 'v': .6, 'dist_m': 20, 'close': False}
        frame = ['run1', 7, {'lane': lane, 'lead': lead}]
        rx.follow_overlay('run1', lambda: True, lambda: tuple(frame))
        assert await until(lambda: bool(rx.channel.sent), timeout=1)
        assert rx.channel.sent == [{'frame': 7, 'lane': lane, 'lead': lead}]
        await asyncio.sleep(.1)
        assert len(rx.channel.sent) == 1
        frame[1], frame[2] = 8, {'lane': lane, 'lead': None}
        assert await until(lambda: len(rx.channel.sent) == 2, timeout=1)
        assert rx.channel.sent[1] == {'frame': 8, 'lane': lane, 'lead': None}
        rx.pc = None
        await asyncio.gather(*rx.tasks)

    asyncio.run(go())


async def until(cond, timeout=10.):
    for _ in range(int(timeout / .05)):
        if cond():
            return True
        await asyncio.sleep(.05)
    return False


def test_the_phone_camera_and_gps_reach_the_run():
    """A stand-in phone (aiortc: test frames 640x480 + a data channel) over loopback."""
    async def go():
        rx = PhoneReceiver(api.RtcConfig(iceServers=[]))
        src, speed = phone.FrameSource(), phone.LiveGps()
        cam = RTCPeerConnection()
        cam.addTrack(VideoStreamTrack())
        ch = cam.createDataChannel('gps')
        ch.on('open', lambda: ch.send(json.dumps(dict(speed=20., lat=10., lon=106., acc=5.))))
        await cam.setLocalDescription(await cam.createOffer())
        answer = await rx.offer(cam.localDescription.sdp, src, speed)
        await cam.setRemoteDescription(RTCSessionDescription(answer, 'answer'))
        try:
            assert await until(lambda: src.received > 0 and speed.count > 0)
            assert src.size == (640, 480)
            (y, _, _), pts = src.poll()
            assert y.shape == (480, 640) and pts > 0 and speed(pts + .1) == 20.
        finally:
            await cam.close()
        assert await until(lambda: src.closed), 'the phone hung up: the run ends'
        await rx.close()
    asyncio.run(go())


def test_an_offer_without_video_is_refused():
    async def go():
        rx = PhoneReceiver(api.RtcConfig(iceServers=[]))
        pc = RTCPeerConnection()
        pc.createDataChannel('gps')
        await pc.setLocalDescription(await pc.createOffer())
        src = phone.FrameSource()
        with pytest.raises(HTTPException) as e:
            await rx.offer(pc.localDescription.sdp, src, phone.LiveGps())
        assert e.value.status_code == 400 and src.closed and rx.pc is None
        await pc.close()
    asyncio.run(go())


def test_a_new_phone_replaces_the_previous_one():
    async def go():
        rx = PhoneReceiver(api.RtcConfig(iceServers=[]))
        sources = []
        for _ in range(2):
            pc = RTCPeerConnection()
            pc.addTrack(VideoStreamTrack())
            await pc.setLocalDescription(await pc.createOffer())
            sources.append(phone.FrameSource())
            await rx.offer(pc.localDescription.sdp, sources[-1], phone.LiveGps())
            await pc.close()
        assert sources[0].closed and not sources[1].closed
        await rx.close()
        assert sources[1].closed
    asyncio.run(go())
