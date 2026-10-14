"""WebRTC: the annotated preview to the browser (WebRtcPreview), and a phone's camera and GPS in (PhoneReceiver).

The preview is video-only and separate from perception, decisions and recorded outputs."""
import asyncio
import json
import logging
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
from .phone import FrameSource, LiveGps

log = logging.getLogger('roadwatch.webrtc')


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


class PhoneReceiver:
    """The /phone page's back camera (WebRTC video) and GPS fixes (JSON on a data channel) for the one live run.

    Frames and fixes are stamped on the session clock when they arrive (seconds since the offer; spec 3.3, live)
    and handed to a phone.FrameSource and phone.LiveGps. When the phone hangs up, or never connects within
    CONNECT_S, the source is closed and the run ends. A new phone replaces the previous one."""
    CONNECT_S = 30.

    def __init__(self, config: api.RtcConfig, clock=time.monotonic) -> None:
        self.config, self.clock = config, clock
        self.pc: RTCPeerConnection | None = None
        self.source: FrameSource | None = None
        self.channel = None
        self.tasks: set[asyncio.Task] = set()

    async def offer(self, sdp: str, source: FrameSource, speed: LiveGps) -> str:
        """Answer the phone's offer (SDP); raises HTTPException 400 for an offer without video, 504 on ICE timeout."""
        await self.close()
        if 'm=video' not in sdp:
            source.close()
            raise HTTPException(400, 'WebRTC offer phải gửi video camera')
        pc = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(**s.model_dump(exclude_none=True))
                                                            for s in self.config.ice_servers]))
        self.pc, self.source, t0 = pc, source, self.clock()

        @pc.on('track')
        def on_track(track) -> None:
            if track.kind == 'video':
                self._spawn(self._pump(track, source, t0))

        @pc.on('datachannel')
        def on_channel(channel) -> None:
            self.channel = channel
            @channel.on('message')
            def on_message(msg) -> None:
                try:
                    speed.add(self.clock() - t0, json.loads(msg))
                except (TypeError, ValueError):
                    pass

        @pc.on('connectionstatechange')
        async def state_changed() -> None:
            if pc.connectionState in ('failed', 'closed'):
                source.close()

        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type='offer'))
            await asyncio.wait_for(pc.setLocalDescription(await pc.createAnswer()), timeout=15)
        except (ValueError, AssertionError) as exc:
            await self.close()
            raise HTTPException(400, 'WebRTC offer không hợp lệ') from exc
        except TimeoutError as exc:
            await self.close()
            raise HTTPException(504, 'không lấy được địa chỉ WebRTC; kiểm tra mạng') from exc
        self._spawn(self._connect_timeout(pc))
        return pc.localDescription.sdp

    def follow(self, alive) -> None:
        """In the background: hang up once alive() is false (the run was stopped, failed or replaced)."""
        self._spawn(self._watch(alive))

    def follow_overlay(self, run_id: str, alive, latest) -> None:
        """Send lane and lead geometry on the phone's existing WebRTC data channel."""
        self._spawn(self._push_overlay(run_id, alive, latest))

    async def _push_overlay(self, run_id: str, alive, latest) -> None:
        pc, last_frame = self.pc, None
        while pc is self.pc and pc is not None and alive():
            channel = self.channel
            if channel is not None and channel.readyState == 'open':
                overlay = latest()
                if overlay is not None and overlay[0] == run_id and overlay[1] != last_frame:
                    last_frame = overlay[1]
                    try:
                        channel.send(json.dumps({'frame': overlay[1], **overlay[2]}))
                    except Exception:  # the peer can close the channel between readyState and send
                        log.exception('phone overlay channel failed')
                        return
            await asyncio.sleep(.03)

    async def _watch(self, alive) -> None:
        pc = self.pc
        while pc is self.pc and pc is not None and alive():
            await asyncio.sleep(.5)
        if pc is self.pc:
            await self.close()

    async def close(self) -> None:
        pc, source, self.pc, self.source = self.pc, self.source, None, None
        self.channel = None
        if source is not None:
            source.close()
        if pc is not None:
            await pc.close()

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _pump(self, track, source: FrameSource, t0: float) -> None:
        try:
            while True:
                frame = await track.recv()
                source.push(frame.to_ndarray(format='yuv420p'), self.clock() - t0)
        except MediaStreamError:
            pass
        except Exception:   # a frame that cannot be read ends the stream, not the server
            log.exception('phone video stream failed')
        finally:
            source.close()

    async def _connect_timeout(self, pc) -> None:
        await asyncio.sleep(self.CONNECT_S)
        if pc is self.pc and pc.connectionState != 'connected':
            log.warning('phone did not connect within %.0f s', self.CONNECT_S)
            await self.close()
