"""WebRTC preview: real ICE negotiation, newest frame, and bounded peer lifetime."""
import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from fastapi import HTTPException

from src.roadwatch import schemas as api
from src.roadwatch.webrtc import PreviewTrack, WebRtcPreview

RUN = 'abc123abc123'


def test_track_sends_latest_frame_and_ends_when_run_changes():
    async def check():
        job = SimpleNamespace(status={'run_id': RUN, 'state': 'running'}, preview=None)
        track = PreviewTrack(job, RUN)
        task = asyncio.create_task(track.recv())
        await asyncio.sleep(0.02)
        assert not task.done()
        job.preview = (RUN, 10, np.full((240, 320, 3), 50, np.uint8))
        job.preview = (RUN, 20, np.full((240, 320, 3), 100, np.uint8))
        frame = await asyncio.wait_for(task, 1)
        assert frame.to_ndarray(format='bgr24').mean() == 100
        task = asyncio.create_task(track.recv())
        await asyncio.sleep(0.02)
        assert not task.done(), 'Do not resend an old frame while waiting for the producer'
        job.preview = (RUN, 21, np.full((720, 1280, 3), 150, np.uint8))
        second = await asyncio.wait_for(task, 1)
        assert second.pts > frame.pts
        assert (second.width, second.height) == (640, 360)
        job.status = {'run_id': 'other', 'state': 'running'}
        with pytest.raises(MediaStreamError):
            await track.recv()
    asyncio.run(check())


def test_real_peer_receives_video_and_close_releases_resources():
    async def check():
        job = SimpleNamespace(status={'run_id': RUN, 'state': 'running'},
                              preview=(RUN, 1, np.full((240, 320, 3), 100, np.uint8)))
        server = WebRtcPreview(job, api.RtcConfig(iceServers=[]))
        client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        client.addTransceiver('video', direction='recvonly')
        incoming = asyncio.get_running_loop().create_future()

        @client.on('track')
        def on_track(track):
            incoming.set_result(track)

        try:
            await client.setLocalDescription(await client.createOffer())
            answer = await server.offer(api.RtcOffer(run_id=RUN, sdp=client.localDescription.sdp, type='offer'))
            await client.setRemoteDescription(RTCSessionDescription(sdp=answer.sdp, type=answer.type))
            track = await asyncio.wait_for(incoming, 5)
            received = asyncio.create_task(track.recv())
            for i in range(2, 60):
                job.preview = (RUN, i, np.full((240, 320, 3), 100, np.uint8))
                await asyncio.sleep(0.02)
                if received.done():
                    break
            frame = await asyncio.wait_for(received, 5)
            assert (frame.width, frame.height) == (320, 240)
            assert frame.to_ndarray(format='bgr24').mean() > 90
            await server.close(answer.peer_id)
            assert not server.peers
            await server.close(answer.peer_id)  # disconnect is idempotent
        finally:
            await client.close()
            await server.close_all()
    asyncio.run(check())


def test_offer_contract_rejects_invalid_type_run_and_oversized_sdp():
    for values in ({'type': 'answer'}, {'run_id': '../run'}, {'sdp': 'x' * 65537}):
        with pytest.raises(ValueError):
            api.RtcOffer(**({'run_id': RUN, 'sdp': 'v=0', 'type': 'offer'} | values))


def test_invalid_offer_releases_peer_and_capacity_is_bounded():
    async def check():
        job = SimpleNamespace(status={'run_id': RUN, 'state': 'running'}, preview=None)
        server = WebRtcPreview(job, api.RtcConfig(iceServers=[]))
        offer = api.RtcOffer(run_id=RUN, sdp='v=0', type='offer')
        with pytest.raises(HTTPException) as error:
            await server.offer(offer)
        assert error.value.status_code == 400
        assert not server.peers and not server.timeouts
        server.peers = dict.fromkeys(('one', 'two', 'three', 'four'))
        with pytest.raises(HTTPException) as error:
            await server.offer(offer)
        assert error.value.status_code == 503
    asyncio.run(check())
