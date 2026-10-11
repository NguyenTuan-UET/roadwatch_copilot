"""Video-only WebRTC preview; separate from perception, decisions and recorded outputs."""
import asyncio
import time
import uuid
from fractions import Fraction

import cv2
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame
from fastapi import HTTPException

from . import schemas as api
from .job import Job


class PreviewTrack(VideoStreamTrack):
    def __init__(self, job: Job, run_id: str) -> None:
        super().__init__()
        self.job, self.run_id = job, run_id
        self.last = None
        self.started = time.monotonic()
        self.sent_at = self.started - 1

    async def recv(self) -> VideoFrame:
        while self.readyState == 'live':
            status, preview = self.job.status, self.job.preview
            if status.get('run_id') != self.run_id:
                break
            now = time.monotonic()
            if preview is not None and preview[0] == self.run_id and preview[1] != self.last and now - self.sent_at >= 1 / 30:
                _, self.last, bgr = preview
                h, w = bgr.shape[:2]
                if w > 640:
                    bgr = cv2.resize(bgr, (640, max(2, (640 * h // w) // 2 * 2)))
                frame = VideoFrame.from_ndarray(bgr, format='bgr24')
                frame.pts = int((now - self.started) * 90000)
                frame.time_base = Fraction(1, 90000)
                self.sent_at = now
                return frame
            if status.get('state') not in ('loading', 'running'):
                break
            await asyncio.sleep(0.005)
        self.stop()
        raise MediaStreamError


class WebRtcPreview:
    def __init__(self, job: Job, config: api.RtcConfig) -> None:
        self.job, self.config = job, config
        self.peers: dict[str, RTCPeerConnection] = {}
        self.timeouts: dict[str, asyncio.TimerHandle] = {}

    async def offer(self, offer: api.RtcOffer) -> api.RtcAnswer:
        if self.job.status.get('run_id') != offer.run_id or self.job.status.get('state') not in ('loading', 'running'):
            raise HTTPException(409, 'lần chạy không còn phát trực tiếp')
        if len(self.peers) >= 4:
            raise HTTPException(503, 'đã đủ 4 người xem trực tiếp; hãy thử lại sau')
        config = RTCConfiguration(iceServers=[RTCIceServer(**s.model_dump(exclude_none=True)) for s in self.config.ice_servers])
        pc = RTCPeerConnection(config)
        peer_id = uuid.uuid4().hex
        self.peers[peer_id] = pc
        track = PreviewTrack(self.job, offer.run_id)

        @pc.on('connectionstatechange')
        async def state_changed() -> None:
            if pc.connectionState == 'connected':
                timer = self.timeouts.pop(peer_id, None)
                if timer:
                    timer.cancel()
            elif pc.connectionState in ('failed', 'closed'):
                await self.close(peer_id)

        @track.on('ended')
        def track_ended() -> None:
            asyncio.create_task(self.close(peer_id))

        self.timeouts[peer_id] = asyncio.get_running_loop().call_later(30, lambda: asyncio.create_task(self.close(peer_id)))
        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=offer.sdp, type=offer.type))
            if not any(t.kind == 'video' and t.direction in ('sendrecv', 'recvonly') for t in pc.getTransceivers()):
                raise ValueError('offer must request receiving video')
            pc.addTrack(track)
            await asyncio.wait_for(pc.setLocalDescription(await pc.createAnswer()), timeout=15)
            return api.RtcAnswer(peer_id=peer_id, sdp=pc.localDescription.sdp, type='answer')
        except (ValueError, AssertionError) as exc:
            await self.close(peer_id)
            raise HTTPException(400, 'WebRTC offer không hợp lệ') from exc
        except TimeoutError as exc:
            await self.close(peer_id)
            raise HTTPException(504, 'không lấy được địa chỉ WebRTC; kiểm tra STUN/TURN') from exc
        except BaseException:
            # Release sockets on cancellation or unexpected negotiation errors, then propagate.
            await self.close(peer_id)
            raise

    async def close(self, peer_id: str) -> None:
        timer = self.timeouts.pop(peer_id, None)
        if timer:
            timer.cancel()
        pc = self.peers.pop(peer_id, None)
        if pc:
            await pc.close()

    async def close_all(self) -> None:
        await asyncio.gather(*(self.close(key) for key in list(self.peers)))
