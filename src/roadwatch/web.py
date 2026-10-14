"""Local demo server (FastAPI): upload a dashcam video, watch BT-A, BT-B and BT-C live.

    python -m src.roadwatch.web            then open http://127.0.0.1:8765  (API docs: /docs)

Settings come from the environment (.env.example): RW_HOST (default 127.0.0.1: the machine only), RW_PORT,
RW_USER / RW_PASSWORD (initial engineer account), RW_ACCOUNTS_DB (SQLite accounts), RW_COOKIE_SECURE (HTTPS cookies),
RW_RUNS_DIR, RW_KEEP_RUNS, RW_MAX_UPLOAD_MB, RW_RTC_ICE_SERVERS. Inference runs locally;
WebRTC sends the annotated preview to the authenticated browser. One run at a time.
"""
import asyncio
import base64
import hmac
import json
import logging
import os
import re
import shutil
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import decide
from . import gps as gpslib
from . import schemas as api
from .authstore import AuthStore
from .job import Job, Options
from .lab import Lab, segment_dir
from .model import MODEL_HZ
from .phone import FrameSource, LiveGps
from .radar import load_radar
from .webrtc import PhoneReceiver, WebRtcPreview

PHRASES = Path(__file__).resolve().parents[2] / 'models/phrases-demo'   # draft WAVs (OQ-B5)
UI = Path(__file__).with_name('ui')                                                 # web app and cockpit entry, served at /ui/
APP_PAGE = (UI / 'index.html').read_text(encoding='utf-8')                         # web app at /app
COCKPIT_PAGE = (UI / 'cockpit.html').read_text(encoding='utf-8')                   # entry at /: cockpit, the V leads to /app
PHONE_PAGE = (UI / 'phone.html').read_text(encoding='utf-8')                       # live measuring from a phone at /phone
BENCH_PAGE = (UI / 'bench.html').read_text(encoding='utf-8')                       # gr14VinAI in the phone's browser at /bench
ORT_WEB = Path(__file__).resolve().parents[2] / 'models/ort-web'   # onnxruntime-web dist files, kept out of git like the model
ORT_FILE = re.compile(r'^(ort\.webgpu\.min\.js|ort-wasm-simd-threaded(\.asyncify|\.jsep)?\.(mjs|wasm)|reference\.json)$')   # .jsep: onnxruntime-web 1.20.1
ORT_VERSION = re.compile(r'^\d+\.\d+\.\d+$')   # models/ort-web/<version>/: the onnxruntime-web the phone page runs
ORT_TYPES = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.wasm': 'application/wasm', '.json': 'application/json'}
PAGE = Path(__file__).with_name('web.html').read_text(encoding='utf-8')            # engineer view
JUDGE_PAGE = Path(__file__).with_name('judge.html').read_text(encoding='utf-8')    # earlier guided view for judges
SAMPLES = Path(os.environ.get('RW_SAMPLES_DIR', Path(__file__).resolve().parents[2] / 'runs/samples'))
SAMPLE_ID = re.compile(r'^[a-z0-9_-]{1,40}$')
USER, PASSWORD = os.environ.get('RW_USER', 'roadwatch'), os.environ.get('RW_PASSWORD', '')   # set before exposing
MAX_UPLOAD = int(os.environ.get('RW_MAX_UPLOAD_MB', 2048)) << 20
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.avi', '.hevc', '.h264', '.webm'}
RUN_ID = re.compile(r'^[0-9a-f]{12}$')
RUN_FILES = {'annotated.mp4': 'video/mp4', 'decisions.json': 'application/json', 'run.json': 'application/json',
             'lead_distance.csv': 'text/csv', 'calibration.json': 'application/json', 'gps.csv': 'text/csv'}
GPS_EXT = {'.gpx', '.nmea', '.txt', '.log', '.csv'}   # comma_ai upload page
MAX_GPS = 20 << 20
RADAR_EXT = {'.csv'}
CROP = r'^(auto|full|\d+,\d+,\d+,\d+)$'
SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                               "img-src 'self' blob: data:; media-src 'self' blob:; frame-ancestors 'none'",
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
}



class JSONFormatter(logging.Formatter):
    """One JSON object per line on stdout (Docker, journald and log tools parse it)."""

    def format(self, record):
        entry = {'timestamp': datetime.now(UTC).isoformat(), 'level': record.levelname, 'logger': record.name,
                 'message': record.getMessage(), 'module': record.module, 'line': record.lineno}
        if record.exc_info and record.exc_info[0] is not None:
            entry['exception'] = {'type': record.exc_info[0].__name__, 'message': str(record.exc_info[1]),
                                  'trace': self.formatException(record.exc_info)}
        return json.dumps(entry, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
logging.basicConfig(level=os.environ.get('RW_LOG_LEVEL', 'INFO'), handlers=[_handler], force=True)
log = logging.getLogger('roadwatch.web')
JOB = Job()
ACCOUNTS_ENABLED = os.environ.get('RW_ACCOUNTS', '1') != '0'
ACCOUNTS = AuthStore(Path(os.environ.get('RW_ACCOUNTS_DB', JOB.runs / 'accounts.db')))
COOKIE_SECURE = os.environ.get('RW_COOKIE_SECURE', '0') == '1'
SESSION_COOKIE = 'rw_session'
RTC_SESSIONS: dict[str, str] = {}
LAB = Lab()
RTC = WebRtcPreview(JOB, api.RtcConfig(iceServers=json.loads(os.environ.get(
    'RW_RTC_ICE_SERVERS') or '[{"urls":["stun:stun.cloudflare.com:3478"]}]')))
PHONE = PhoneReceiver(RTC.config)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if ACCOUNTS_ENABLED and PASSWORD:
        await asyncio.to_thread(ACCOUNTS.bootstrap_engineer, USER, PASSWORD)
    async def expire_peers() -> None:
        while True:
            await asyncio.sleep(5)
            for peer_id, token in list(RTC_SESSIONS.items()):
                if peer_id not in RTC.peers or await asyncio.to_thread(ACCOUNTS.session_user, token) is None:
                    await RTC.close(peer_id)
                    RTC_SESSIONS.pop(peer_id, None)
    reaper = asyncio.create_task(expire_peers())
    try:
        yield
    finally:
        reaper.cancel()
        await asyncio.gather(reaper, return_exceptions=True)
        await RTC.close_all()
        await PHONE.close()
        RTC_SESSIONS.clear()


app = FastAPI(title='RoadWatch Copilot demo API', version=api.API_VERSION,
              lifespan=lifespan,
              description='BT-A đo khoảng cách, BT-B quyết định cảnh báo, BT-C vận hành và kiểm chứng. Chỉ cảnh báo, '
                          'chạy offline.')
app.mount('/ui', StaticFiles(directory=UI), name='ui')


ERRORS = {c: {'model': api.Error} for c in (400, 404, 409, 413, 415)}
ERRORS[413]['description'] = 'Content Too Large'  # Stable across Python versions' HTTPStatus wording.


@app.middleware('http')
async def security_headers(request: Request, call_next):
    t = time.perf_counter()
    path = request.url.path
    if ACCOUNTS_ENABLED:
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not _same_origin(request):
            return JSONResponse({'detail': 'Nguồn yêu cầu không hợp lệ'}, 403, SECURITY_HEADERS)
        request.state.account = await asyncio.to_thread(ACCOUNTS.session_user, request.cookies.get(SESSION_COOKIE, ''))
        public = path in ('/', '/login', '/register', '/api/auth/login', '/api/auth/register', '/api/auth/logout') or path.startswith(('/health', '/ui/'))
        if not public and request.state.account is None:
            response = (RedirectResponse('/login?next=' + path, 303) if path in ('/app', '/engineer', '/judge', '/phone', '/bench')
                        else JSONResponse({'detail': 'Cần đăng nhập'}, 401))
            response.headers.update(SECURITY_HEADERS)
            response.headers['Cache-Control'] = 'no-store'
            return response
        if (path == '/engineer' or path.startswith('/api/lab/')) and request.state.account.role != 'engineer':
            return JSONResponse({'detail': 'Chức năng dành cho kỹ sư'}, 403, SECURITY_HEADERS)
    elif PASSWORD and not path.startswith('/health') and not _authorized(request.headers.get('authorization', '')):
        response = JSONResponse({'detail': 'cần đăng nhập'}, 401, {'WWW-Authenticate': 'Basic realm="RoadWatch"'})
        response.headers.update(SECURITY_HEADERS)
        return response
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if path in ('/bench', '/phone'):   # gr14VinAI in the phone's browser: onnxruntime-web compiles WebAssembly
        response.headers['Content-Security-Policy'] = SECURITY_HEADERS['Content-Security-Policy'].replace(
            "script-src 'self'", "script-src 'self' 'wasm-unsafe-eval'")
    if path.startswith('/ortweb/') and response.status_code == 200:   # ~70 MB of runtime and model: cache on the phone
        response.headers['Cache-Control'] = 'private, max-age=604800'
    elif ACCOUNTS_ENABLED or response.headers.get('content-type', '').startswith('text/html') or request.url.path.startswith('/ui/'):
        response.headers['Cache-Control'] = 'no-store'
    if not request.url.path.startswith(('/api/events', '/api/stream')):
        log.info('%s %s %d %.1fms', request.method, request.url.path, response.status_code,
                 1000 * (time.perf_counter() - t))
    return response


def _same_origin(request: Request | WebSocket) -> bool:
    origin = request.headers.get('origin')
    try:
        parsed = urlsplit(origin) if origin else None
    except ValueError:
        return False
    return (request.headers.get('sec-fetch-site') != 'cross-site'
            and (parsed is None or (parsed.scheme in ('http', 'https')
                                    and parsed.netloc == request.headers.get('host'))))


@app.get('/login', response_class=HTMLResponse, include_in_schema=False)
@app.get('/register', response_class=HTMLResponse, include_in_schema=False)
def auth_page() -> str:
    return (UI / 'auth.html').read_text(encoding='utf-8')


def _session_response(account: api.Account, request: Request, status_code: int = 200) -> JSONResponse:
    ACCOUNTS.revoke(request.cookies.get(SESSION_COOKIE, ''))
    token = ACCOUNTS.create_session(account)
    response = JSONResponse(account.model_dump(), status_code)
    response.set_cookie(SESSION_COOKIE, token, max_age=ACCOUNTS.session_seconds, httponly=True,
                        secure=COOKIE_SECURE, samesite='lax')
    return response


@app.post('/api/auth/register', response_model=api.Account, status_code=201)
def register(credentials: api.Registration, request: Request) -> JSONResponse:
    if not ACCOUNTS_ENABLED:
        raise HTTPException(404, 'Tài khoản chưa được bật')
    try:
        account = ACCOUNTS.register(credentials.username, credentials.password, credentials.role)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _session_response(account, request, 201)


@app.post('/api/auth/login', response_model=api.Account)
def login(credentials: api.Credentials, request: Request) -> JSONResponse:
    if not ACCOUNTS_ENABLED:
        raise HTTPException(404, 'Tài khoản chưa được bật')
    try:
        account = ACCOUNTS.authenticate(credentials.username, credentials.password)
    except ValueError as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After': '300'}) from exc
    if account is None:
        raise HTTPException(401, 'Tên đăng nhập hoặc mật khẩu không đúng')
    return _session_response(account, request)


@app.get('/api/auth/me', response_model=api.Account)
def me(request: Request) -> api.Account:
    return request.state.account if ACCOUNTS_ENABLED else api.Account(username=USER, role='engineer')


@app.post('/api/auth/logout', response_model=api.LoggedOut)
async def logout(request: Request) -> JSONResponse:
    token = request.cookies.get(SESSION_COOKIE, '')
    if ACCOUNTS_ENABLED:
        await asyncio.to_thread(ACCOUNTS.revoke, token)
        for peer_id, owner in list(RTC_SESSIONS.items()):
            if owner == token:
                await RTC.close(peer_id)
                RTC_SESSIONS.pop(peer_id, None)
    response = JSONResponse({'logged_out': True})
    response.delete_cookie(SESSION_COOKIE, secure=COOKIE_SECURE, httponly=True, samesite='lax')
    return response


def _authorized(header):
    """HTTP Basic against RW_USER / RW_PASSWORD; the browser then sends it on fetch, SSE, <img> and <video>."""
    try:
        user, _, pw = base64.b64decode(header.removeprefix('Basic ')).decode().partition(':')
    except ValueError:
        return False
    return hmac.compare_digest(user.encode(), USER.encode()) & hmac.compare_digest(pw.encode(), PASSWORD.encode())


@app.get('/', response_class=HTMLResponse, include_in_schema=False)
def cockpit_page():
    return COCKPIT_PAGE


@app.get('/app', response_class=HTMLResponse, include_in_schema=False)
def app_page():
    return APP_PAGE


@app.get('/phone', response_class=HTMLResponse, include_in_schema=False)
def phone_page():
    return PHONE_PAGE


@app.get('/bench', response_class=HTMLResponse, include_in_schema=False)
def bench_page():
    return BENCH_PAGE


@app.get('/ortweb/{name}', include_in_schema=False)
def ort_web_file(name: str):
    """onnxruntime-web (WebGPU build) and gr14VinAI for /bench: only the listed files, from models/."""
    # .fp32: GPUs without f16 shaders; .mixed: f16 with the L2 norm in f32 (its sum of squares overflows f16 on WebGPU);
    # .capture: .mixed with float16 inputs and frame queue (all three: scripts/roadwatch/make_phone_models.py)
    if name in (MODEL_FILE.name, *(MODEL_FILE.stem + f'.{v}.onnx' for v in ('fp32', 'mixed', 'capture'))) \
            and (MODEL_FILE.parent / name).is_file():
        return FileResponse(MODEL_FILE.parent / name, media_type='application/octet-stream')
    if not ORT_FILE.match(name) or not (ORT_WEB / name).is_file():
        raise HTTPException(404, 'không có file này')
    return FileResponse(ORT_WEB / name, media_type=ORT_TYPES[Path(name).suffix])


@app.get('/ortweb/{version}/{name}', include_in_schema=False)
def ort_web_version_file(version: str, name: str):
    """onnxruntime-web 1.20.1 for /phone, in models/ort-web/<version>/ (a newer one in models/ort-web/ kills Safari tabs)."""
    if not ORT_VERSION.match(version) or not ORT_FILE.match(name) or not (ORT_WEB / version / name).is_file():
        raise HTTPException(404, 'không có file này')
    return FileResponse(ORT_WEB / version / name, media_type=ORT_TYPES[Path(name).suffix])


@app.post('/api/bench/result', include_in_schema=False)
async def bench_result(request: Request):
    """/bench sends its measurements here: server log and runs/<dir>/bench.jsonl (JSON, at most 64 KB)."""
    body = await request.body()
    if len(body) > 64 << 10:
        raise HTTPException(413, 'kết quả quá lớn')
    try:
        result = json.loads(body)
    except ValueError:
        raise HTTPException(400, 'cần JSON') from None
    line = json.dumps({'t_unix': round(time.time(), 1), **result} if isinstance(result, dict) else result, ensure_ascii=False)
    log.info('bench result %s', line)
    with open(JOB.runs / 'bench.jsonl', 'a', encoding='utf-8') as f:   # also kept next to the runs, to read later
        f.write(line + '\n')
    return {'logged': True}


@app.get('/judge', response_class=HTMLResponse, include_in_schema=False)
def judge_page():
    return JUDGE_PAGE


@app.get('/engineer', response_class=HTMLResponse, include_in_schema=False)
def page():
    return PAGE


MODEL_FILE = Path(__file__).resolve().parents[2] / 'models/gr14VinAI.onnx'


@app.get('/health', response_model=api.Health, responses={503: {'model': api.Health}})
def health():
    """Uptime monitoring: 503 when degraded (a running job produced no frame for 2 s, or no model)."""
    h = api.Health(**JOB.health(), model=MODEL_FILE.exists(), timestamp=datetime.now(UTC).isoformat())
    if not h.model:
        h.status = 'degraded'
    return JSONResponse(h.model_dump(mode='json'), 200 if h.status == 'ok' else 503)


@app.get('/health/live')
def live():
    """Liveness (Docker HEALTHCHECK): the process answers."""
    return {'status': 'alive'}


@app.get('/health/ready')
def ready():
    """Readiness: the model file is there, so a run can start."""
    ok = MODEL_FILE.exists()
    return JSONResponse({'status': 'ready' if ok else 'not ready', 'model': ok}, 200 if ok else 503)


@app.get('/api/config', response_model=api.BtBConfig)
def config():
    """BT-B parameters in use (provisional values, not tuned; changes go through HITL)."""
    return dict(legal_bands=[dict(v_min_kmh=a, v_max_kmh=b, min_gap_m=d) for a, b, d in decide.LEGAL],
                ttc_emergency_s=decide.TTC_EMERGENCY_S, h_ttc_s=decide.H_TTC_S,
                t_confirm_s=decide.T_CONFIRM_S, h_m=decide.H_M, t_clear_s=decide.T_CLEAR_S,
                cooldown_s=decide.COOLDOWN_S, grace_s=decide.GRACE_S, info_horizon_s=decide.INFO_HORIZON_S,
                phrases=decide.PHRASES)


@app.get('/api/status', response_model=api.LiveStatus)
def status():
    with JOB.lock:
        return JOB.status


@app.get('/api/history', response_model=api.History)
def history():
    with JOB.lock:
        return api.History(run_id=JOB.status.get('run_id'), samples=list(JOB.history))


@app.get('/api/events')
async def events(request: Request):
    """Server-Sent Events, `event: status`, `data`: one `LiveStatus` per processed frame (and on every state change)."""
    async def gen():
        last = None
        checked = time.monotonic()
        while not await request.is_disconnected():
            if ACCOUNTS_ENABLED and time.monotonic() - checked >= 5:
                checked = time.monotonic()
                if await asyncio.to_thread(ACCOUNTS.session_user, request.cookies.get(SESSION_COOKIE, '')) is None:
                    return
            with JOB.lock:
                st = JOB.status
            if st is not last:
                last = st
                yield 'event: status\ndata: ' + api.LiveStatus(**st).model_dump_json() + '\n\n'
            await asyncio.sleep(0.005)
    # cloudflared flushes per write only for a bare `text/event-stream` (no charset); otherwise it sends 64 KB blocks.
    r = StreamingResponse(gen(), headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})
    r.headers['Content-Type'] = 'text/event-stream'
    return r


async def _ws_authorized(websocket: WebSocket) -> bool:
    """The HTTP middleware does not see WebSockets: session cookie and origin (or HTTP Basic) checked here."""
    if ACCOUNTS_ENABLED:
        account = await asyncio.to_thread(ACCOUNTS.session_user, websocket.cookies.get(SESSION_COOKIE, ''))
        return account is not None and _same_origin(websocket)
    return not PASSWORD or _authorized(websocket.headers.get('authorization', ''))


@app.websocket('/api/ws')
async def ws(websocket: WebSocket):
    """Same messages as /api/events (one `LiveStatus` JSON per processed frame) over a WebSocket.

    Use this through Cloudflare quick tunnels (trycloudflare.com), which buffer SSE for seconds but pass WebSockets.
    The HTTP middleware does not see WebSockets; check the session cookie and origin here too.
    """
    if not await _ws_authorized(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    last = None
    checked = time.monotonic()
    try:
        while True:
            if ACCOUNTS_ENABLED and time.monotonic() - checked >= 5:
                checked = time.monotonic()
                if await asyncio.to_thread(ACCOUNTS.session_user, websocket.cookies.get(SESSION_COOKIE, '')) is None:
                    await websocket.close(code=1008)
                    return
            with JOB.lock:
                st = JOB.status
            if st is not last:
                last = st
                await websocket.send_text(api.LiveStatus(**st).model_dump_json())
            await asyncio.sleep(0.005)
    except WebSocketDisconnect:
        pass


@app.get('/api/rtc', response_model=api.RtcConfig)
def rtc_config() -> api.RtcConfig:
    return RTC.config


@app.post('/api/rtc/offer', response_model=api.RtcAnswer)
async def rtc_offer(offer: api.RtcOffer, request: Request) -> api.RtcAnswer:
    answer = await RTC.offer(offer)
    if ACCOUNTS_ENABLED:
        token = request.cookies.get(SESSION_COOKIE, '')
        if await asyncio.to_thread(ACCOUNTS.session_user, token) is None:
            await RTC.close(answer.peer_id)
            raise HTTPException(401, 'Phiên đăng nhập đã kết thúc')
        for peer_id in list(RTC_SESSIONS):
            if peer_id not in RTC.peers:
                RTC_SESSIONS.pop(peer_id, None)
        RTC_SESSIONS[answer.peer_id] = token
    return answer


@app.delete('/api/rtc/{peer_id}', response_model=api.RtcClosed)
async def rtc_close(peer_id: str, request: Request) -> api.RtcClosed:
    if ACCOUNTS_ENABLED and RTC_SESSIONS.get(peer_id, request.cookies.get(SESSION_COOKIE, '')) != request.cookies.get(SESSION_COOKIE, ''):
        raise HTTPException(403, 'Kết nối thuộc phiên đăng nhập khác')
    await RTC.close(peer_id)
    RTC_SESSIONS.pop(peer_id, None)
    return api.RtcClosed(closed=True)


@app.post('/api/phone/offer', response_model=api.PhoneAnswer, responses=ERRORS)
async def phone_offer(offer: api.PhoneOffer) -> api.PhoneAnswer:
    """Start a live run from a phone (the /phone page): its back camera over WebRTC and its GPS fixes as JSON
    messages `{speed, lat, lon, acc}` on a data channel of the same connection; the run replaces any running one.

    Frames and fixes are stamped on arrival (session clock); the model takes the newest frame about every 50 ms.
    The run ends when the phone hangs up or on POST /api/stop, and is saved like an uploaded video (with gps.csv).
    Lens: `f_mm` (35 mm-equivalent) or `hfov`; `d`: camera to front bumper (m)."""
    source, speed = FrameSource(), LiveGps()
    sdp = await PHONE.offer(offer.sdp, source, speed)
    run_id = await _start_phone_run(offer, source, speed, 'webrtc')
    PHONE.follow(lambda: _phone_run_alive(run_id))
    PHONE.follow_overlay(run_id, lambda: _phone_run_alive(run_id), lambda: JOB.overlay)
    return api.PhoneAnswer(run_id=run_id, type='answer', sdp=sdp)


async def _start_phone_run(settings: api.PhoneSettings, source: FrameSource, speed: LiveGps, via: str) -> str:
    run_id = uuid.uuid4().hex[:12]
    opts = Options(lens='mm' if settings.f_mm else 'fov', f_mm=settings.f_mm, hfov_deg=settings.hfov, speed=speed,
                   auto_focal=settings.auto_focal, crop='full', use_pitch=settings.pitch)
    await asyncio.to_thread(JOB.start, run_id, source, float(MODEL_HZ), settings.d, None, False,
                            name='Điện thoại (trực tiếp)', opts=opts)
    log.info('run %s live from a phone (%s)', run_id, via)
    return run_id


def _phone_run_alive(run_id: str) -> bool:
    return JOB.status.get('run_id') == run_id and JOB.status.get('state') in ('loading', 'running')


@app.websocket('/api/phone/ws')
async def phone_ws(websocket: WebSocket):
    """Live run from a phone without WebRTC (4G, VPN, proxies that pass only HTTPS): query = PhoneSettings.

    Server -> phone: `{"run_id"}` once, `{"ack": n}` after each frame (the page limits the frames not yet
    acknowledged, so no queue builds up on a slow link), and `{"overlay": {frame, lane, lead}}` after each model
    tick: the ego lane and the lead as fractions of the picture (hud.overlay), drawn by the page on its live camera.
    Phone -> server: binary messages are JPEG frames of the
    back camera, text messages GPS fixes `{speed, lat, lon, acc}` as on the WebRTC data channel. Both are stamped
    on arrival (session clock). The run ends when the socket closes or on POST /api/stop (then the socket closes)."""
    try:
        settings = api.PhoneSettings(**dict(websocket.query_params))
    except ValueError:
        settings = None
    if settings is None or not await _ws_authorized(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    source, speed, t0 = FrameSource(), LiveGps(), time.monotonic()
    run_id = await _start_phone_run(settings, source, speed, 'websocket')
    frames = 0

    sending = asyncio.Lock()   # acks and overlays are sent from two tasks

    async def send(msg):
        async with sending:
            await websocket.send_json(msg)

    async def push():   # the newest lane and lead to the page; the run stopped or replaced: hang up
        last = None
        while _phone_run_alive(run_id):
            o = JOB.overlay
            if o is not None and o is not last and o[0] == run_id:
                last = o
                await send({'overlay': {'frame': o[1], **o[2]}})
            await asyncio.sleep(.03)
        await websocket.close()
    watcher = None
    try:
        await send({'run_id': run_id})
        watcher = asyncio.create_task(push())
        while True:
            msg = await websocket.receive()
            if msg['type'] == 'websocket.disconnect':
                break
            t = time.monotonic() - t0
            if msg.get('bytes') is not None:
                img = await asyncio.to_thread(_jpeg_to_i420, msg['bytes'])
                if img is not None:
                    source.push(img, t)
                frames += 1
                await send({'ack': frames})
            elif msg.get('text') is not None:
                try:
                    speed.add(t, json.loads(msg['text']))
                except ValueError:
                    pass
    except (WebSocketDisconnect, RuntimeError) as e:   # RuntimeError: sent after the watcher closed the socket
        why = f'disconnect {e.code}' if isinstance(e, WebSocketDisconnect) else 'run ended'
    else:
        why = 'phone closed'
    finally:
        if watcher is not None:
            watcher.cancel()
        source.close()
    log.info('run %s phone socket closed (%s): %d frames received, %d decoded, %d replaced before use',
             run_id, why, frames, source.received, source.dropped)


def _jpeg_to_i420(data: bytes):
    """JPEG bytes -> yuv420p array (h * 3 / 2, w) as phone.FrameSource takes it; None if not a picture."""
    import cv2
    import numpy as np
    bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    h, w = bgr.shape[:2]
    return cv2.cvtColor(bgr[:h // 2 * 2, :w // 2 * 2], cv2.COLOR_BGR2YUV_I420)


@app.get('/api/stream')
async def stream(request: Request):
    """Annotated frames as MJPEG (for tools; the web UI polls /api/frame: Chrome stops showing an MJPEG <img> after ~20 MB)."""
    async def gen():
        last = None
        checked = time.monotonic()
        while not await request.is_disconnected():
            if ACCOUNTS_ENABLED and time.monotonic() - checked >= 5:
                checked = time.monotonic()
                if await asyncio.to_thread(ACCOUNTS.session_user, request.cookies.get(SESSION_COOKIE, '')) is None:
                    return
            jpeg = JOB.jpeg
            if jpeg is not None and jpeg is not last:
                last = jpeg
                yield b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpeg) + jpeg + b'\r\n'
            await asyncio.sleep(0.02)
    return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=f')


@app.get('/api/frame', responses={200: {'content': {'image/jpeg': {}}}, 204: {'description': 'no frame yet'}})
def frame():
    """The latest annotated frame as one JPEG (204 before the first frame). For clients where /api/stream never
    arrives, e.g. behind proxies or port forwarding that buffer streamed responses: poll this instead."""
    jpeg = JOB.jpeg
    if jpeg is None:
        return Response(status_code=204)
    return Response(jpeg, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.get('/api/phrases/{kind}', responses={200: {'content': {'audio/wav': {}}}, 404: {'model': api.Error}})
def phrase(kind: api.Level):
    if not (PHRASES / f'{kind.value}.wav').is_file():
        raise HTTPException(404, 'không có câu này')
    return FileResponse(PHRASES / f'{kind.value}.wav', media_type='audio/wav')


@app.get('/api/samples', response_model=list[api.SampleVideo])
def samples():
    """Videos kept on the server, so a run starts with one click and no upload."""
    out = []
    for meta in sorted(SAMPLES.glob('*.json')):
        if SAMPLE_ID.match(meta.stem) and meta.with_suffix('.mp4').is_file():
            out.append(api.SampleVideo(id=meta.stem, **json.loads(meta.read_text(encoding='utf-8'))))
    return out


@app.post('/api/samples/{sample_id}/run', response_model=api.RunStarted, responses=ERRORS)
def run_sample(sample_id: str, rt: bool = True):
    """Start a run on a server-side sample video, in real time by default."""
    s = next((x for x in samples() if x.id == sample_id), None)
    if s is None:
        raise HTTPException(404, 'không có video mẫu này')
    run_id = uuid.uuid4().hex[:12]
    folder = JOB.runs / run_id
    folder.mkdir(parents=True)
    video = folder / 'input.mp4'
    try:
        os.link(SAMPLES / f'{s.id}.mp4', video)   # no copy; deleting the run keeps the sample
    except OSError:
        shutil.copyfile(SAMPLES / f'{s.id}.mp4', video)
    JOB.start(run_id, video, s.fps, s.d, s.fy, rt, name=s.title)
    log.info('run %s on sample %s', run_id, s.id)
    return api.RunStarted(run_id=run_id, state='loading')


@app.post('/api/gps', response_model=api.GpsUploaded, responses=ERRORS,
          openapi_extra={'requestBody': {'required': True, 'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}})
async def upload_gps(request: Request, name: str = Query(..., max_length=200)):
    """Upload a GPS log (GPX / NMEA / CSV, raw body) for the next run; it is parsed now so a bad file fails here.

    It gives the ego speed (and, with `auto_focal`, the focal length) as on the comma_ai upload page."""
    ext = Path(name).suffix.lower()
    if ext not in GPS_EXT:
        raise HTTPException(415, f'chỉ nhận log GPS {sorted(GPS_EXT)}')
    data = await request.body()
    if len(data) > MAX_GPS:
        raise HTTPException(413, f'log GPS lớn hơn {MAX_GPS >> 20} MB')
    gps_id = uuid.uuid4().hex[:12]
    path = JOB.runs / '_gps' / f'{gps_id}{ext}'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        t, _ = gpslib.load_gps(path)
    except Exception as e:   # malformed XML / CSV / no fixes
        path.unlink()
        raise HTTPException(400, f'không đọc được log GPS: {e}') from None
    return api.GpsUploaded(gps_id=gps_id, fixes=len(t), duration_s=round(float(t[-1]), 2))


@app.post('/api/radar', response_model=api.RadarUploaded, responses=ERRORS,
          openapi_extra={'requestBody': {'required': True, 'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}})
async def upload_radar(request: Request, name: str = Query(..., max_length=200)):
    """Upload a radar log (CSV, raw body) for the next run: the distance to the car ahead over video time (radar.py). It is
    parsed now so a bad file fails here. The run shows it beside the model's distance, as the Lab does."""
    ext = Path(name).suffix.lower()
    if ext not in RADAR_EXT:
        raise HTTPException(415, f'chỉ nhận log radar {sorted(RADAR_EXT)}')
    data = await request.body()
    if len(data) > MAX_GPS:
        raise HTTPException(413, f'log radar lớn hơn {MAX_GPS >> 20} MB')
    radar_id = uuid.uuid4().hex[:12]
    path = JOB.runs / '_radar' / f'{radar_id}{ext}'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        t, _ = load_radar(path)
    except Exception as e:   # no columns / no usable distance
        path.unlink()
        raise HTTPException(400, f'không đọc được log radar: {e}') from None
    return api.RadarUploaded(radar_id=radar_id, samples=len(t), duration_s=round(float(t[-1] - t[0]), 2))


@app.post('/api/runs', response_model=api.RunStarted, responses=ERRORS,
          openapi_extra={'requestBody': {'required': True, 'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}})
async def create_run(request: Request, name: str = Query(..., max_length=200),
                     fps: float = Query(..., gt=0, le=240), d: float = Query(..., ge=0, le=5),
                     fy: float | None = Query(None, gt=0, le=10000), rt: bool = True,
                     lens: Literal['learn', 'px', 'mm', 'fov'] = 'mm',
                     f_mm: float | None = Query(None, gt=0, le=300), sensor_mm: float | None = Query(None, gt=0, le=40),
                     hfov: float | None = Query(None, ge=20, le=170), fisheye: bool = False,
                     gps: str | None = Query(None, pattern=r'^[0-9a-f]{12}$'),
                     gps_offset: float | None = Query(None, ge=-600, le=3600), auto_focal: bool = False,
                     radar: str | None = Query(None, pattern=r'^[0-9a-f]{12}$'),
                     crop: str = Query('auto', pattern=CROP), pitch: bool = True,
                     preview_every: int = Query(2, ge=1, le=10)):
    """Upload a video as the raw request body (not multipart) and start a run on it at once.

    `fps`: true capture rate; `d`: camera to front bumper (m); `rt`: pace to real time instead of as fast as
    possible. Lens, as on the comma_ai upload page: `fy` (px), or `lens=mm` with `f_mm` (35 mm-equivalent unless
    `sensor_mm`, the sensor's long side), or `lens=fov` with `hfov` (deg, `fisheye` for a wide dashcam lens), or
    `lens=learn` (learned from the video, only when asked); by default (`lens=mm`) the focal length must be given.
    `gps`: id from POST /api/gps; `gps_offset`: GPS time at video t = 0 (s, empty = 0: the log is taken to start with the video, no sync);
    `radar`: id from POST /api/radar (distance to the car ahead over video time, shown beside the model's);
    `auto_focal`: fit the focal length to the GPS speed (experimental).
    `crop`: camera picture `auto` (letterbox bars removed), `full` or `x,y,w,h`; `pitch`: apply the pitch angle;
    `preview_every`: refresh the live frame (/api/frame, /api/stream) every N video frames (less CPU)."""
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(415, f'chỉ nhận video {sorted(VIDEO_EXT)}')
    if not fy and lens != 'learn' and not (f_mm if lens == 'mm' else hfov if lens == 'fov' else None):
        raise HTTPException(422, 'chưa có tiêu cự: nhập tiêu cự pixel, tiêu cự mm hoặc góc nhìn ngang')
    gps_src = None
    if gps:
        gps_src = next((p for p in (JOB.runs / '_gps').glob(f'{gps}.*') if p.suffix in GPS_EXT), None)
        if gps_src is None:
            raise HTTPException(404, 'không có log GPS này; tải lên lại')
    radar_src = None
    if radar:
        radar_src = next((p for p in (JOB.runs / '_radar').glob(f'{radar}.*') if p.suffix in RADAR_EXT), None)
        if radar_src is None:
            raise HTTPException(404, 'không có log radar này; tải lên lại')
    if int(request.headers.get('content-length') or 0) > MAX_UPLOAD:
        raise HTTPException(413, f'video lớn hơn {MAX_UPLOAD >> 20} MB')
    run_id = uuid.uuid4().hex[:12]
    folder = JOB.runs / run_id
    folder.mkdir(parents=True)
    video, size = folder / f'input{ext}', 0
    with open(video, 'wb') as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD:
                f.close()
                video.unlink()
                folder.rmdir()
                raise HTTPException(413, f'video lớn hơn {MAX_UPLOAD >> 20} MB')
            f.write(chunk)
    if not size:
        video.unlink()
        folder.rmdir()
        raise HTTPException(400, 'video rỗng')
    gps_path = None
    if gps_src is not None:   # moved into the run folder: deleted with the run
        gps_path = folder / f'gps{gps_src.suffix}'
        shutil.move(gps_src, gps_path)
    radar_path = None
    if radar_src is not None:   # moved into the run folder: deleted with the run
        radar_path = folder / f'radar{radar_src.suffix}'
        shutil.move(radar_src, radar_path)
    opts = Options(lens='px' if fy else lens, f_mm=f_mm, sensor_mm=sensor_mm, hfov_deg=hfov, fisheye=fisheye,
                   gps=gps_path, gps_offset=gps_offset, radar=radar_path, auto_focal=auto_focal,
                   crop=crop if crop in ('auto', 'full') else tuple(int(v) for v in crop.split(',')), use_pitch=pitch,
                   preview_every=preview_every)
    JOB.start(run_id, video, fps, d, fy, rt, name=Path(name).name, opts=opts)
    log.info('run %s uploaded: %s, %.1f MB, gps=%s', run_id, Path(name).name, size / 2**20, 'yes' if gps_path else 'no')
    return api.RunStarted(run_id=run_id, state='loading')


@app.get('/api/lab/segments', response_model=list[api.LabSegment])
def lab_segments():
    """comma2k19 segments on this machine (RW_LAB_DIR) for the lab page."""
    return LAB.segments()


def _lab_segment(seg_id):
    try:
        return segment_dir(LAB.root, seg_id)
    except KeyError:
        raise HTTPException(404, 'không có segment này') from None


@app.post('/api/lab/segments/{seg_id}/run', response_model=api.LabStatus, responses=ERRORS)
def lab_run(seg_id: str, bumper: float = Query(1.52, ge=0, le=5), fy: float = Query(910., gt=0, le=10000),
            log: bool = True, wide: Literal['dup', 'warp'] = 'dup'):
    """Run BT-A on the whole segment and save the result (replaces an earlier one). `bumper`: camera -> radar (m);
    `fy`: focal length (px; comma2k19: 910); `log`: use the car's CAN speed as the ego speed; `wide`: the model's
    wide-camera input, the narrow picture duplicated (comma2k19 has no wide camera; better vs radar) or warped.
    As comma lead_distance app.py: the camera angles are estimated over the first 300 frames, only the yaw applied."""
    _lab_segment(seg_id)
    try:
        LAB.start(seg_id, bumper, fy, log, wide)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None
    return LAB.status


@app.post('/api/lab/stop', response_model=api.Stopping)
def lab_stop():
    """Stop the running segment (state 'stopped'); the earlier saved result, if any, stays."""
    LAB.stop.set()
    return api.Stopping()


@app.get('/api/lab/status', response_model=api.LabStatus)
def lab_status():
    return LAB.status


@app.get('/api/lab/live', response_model=api.LabLive)
def lab_live(since: int = Query(0, ge=0)):
    """Per-frame values of the running segment so far (the page draws its charts from them while it runs)."""
    return LAB.live(since)


@app.get('/api/lab/frame', responses={200: {'content': {'image/jpeg': {}}}, 204: {'description': 'no frame yet'}})
def lab_frame():
    """The newest annotated frame of the running segment as one JPEG (204 before the first frame)."""
    jpeg = LAB.jpeg
    if jpeg is None:
        return Response(status_code=204)
    return Response(jpeg, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.get('/api/lab/segments/{seg_id}/result', response_model=api.LabResult, responses=ERRORS)
def lab_result(seg_id: str):
    path = LAB.cache / _lab_segment(seg_id).name / 'result.json'
    if not path.is_file():
        raise HTTPException(404, 'segment chưa chạy')
    return json.loads(path.read_text())


@app.get('/api/lab/segments/{seg_id}/video', responses={200: {'content': {'video/mp4': {}}}, 404: {'model': api.Error}})
def lab_video(seg_id: str):
    """Annotated video of the saved result (byte ranges, so <video> can seek)."""
    path = LAB.cache / _lab_segment(seg_id).name / 'annotated.mp4'
    if not path.is_file():
        raise HTTPException(404, 'segment chưa chạy')
    return FileResponse(path, media_type='video/mp4')


@app.post('/api/stop', response_model=api.Stopping)
def stop():
    JOB.stop.set()
    return api.Stopping()


@app.get('/api/runs', response_model=list[api.RunInfo])
def list_runs():
    out = []
    for p in sorted(JOB.runs.glob('*/run.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        info = {k: v for k, v in json.loads(p.read_text()).items() if k in api.RunInfo.model_fields}
        if info.get('state') in ('done', 'stopped'):
            base = f"/api/runs/{info['run_id']}/files/"
            info.update(video_url=base + 'annotated.mp4', log_url=base + 'decisions.json')
            if (p.parent / 'lead_distance.csv').exists():
                info.update(csv_url=base + 'lead_distance.csv', calibration_url=base + 'calibration.json')
        out.append(api.RunInfo(**info))
    return out


def _run_dir(run_id):
    if not RUN_ID.match(run_id) or not (JOB.runs / run_id / 'run.json').exists():
        raise HTTPException(404, 'không có lần chạy này')
    return JOB.runs / run_id


@app.get('/api/runs/{run_id}/files/{name}', responses={200: {'content': {'video/mp4': {}, 'application/json': {}}}, 404: {'model': api.Error}})
def run_file(run_id: str, name: str):
    """Annotated video (byte ranges, so <video> can seek), decision log, run metadata, per-tick CSV or calibration."""
    if name not in RUN_FILES or not (_run_dir(run_id) / name).is_file():
        raise HTTPException(404, 'không có file này')
    return FileResponse(JOB.runs / run_id / name, media_type=RUN_FILES[name])


@app.delete('/api/runs/{run_id}', response_model=api.Deleted, responses=ERRORS)
def delete_run(run_id: str):
    """Delete a run and its uploaded video (privacy: the driver can erase a recording)."""
    folder = _run_dir(run_id)
    with JOB.lock:
        if JOB.status.get('run_id') == run_id and JOB.status.get('state') in ('loading', 'running'):
            raise HTTPException(409, 'lần chạy đang chạy; dừng trước')
    for p in folder.iterdir():
        p.unlink()
    folder.rmdir()
    log.info('run %s deleted', run_id)
    return {'deleted': run_id}


if __name__ == '__main__':
    import uvicorn
    host, port = os.environ.get('RW_HOST', '127.0.0.1'), int(os.environ.get('RW_PORT', 8765))
    print(f'http://{host}:{port}')
    uvicorn.run(app, host=host, port=port, log_level='warning')
