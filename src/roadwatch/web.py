"""Local demo server (FastAPI): upload a dashcam video, watch BT-A, BT-B and BT-C live.

    python -m src.roadwatch.web            then open http://127.0.0.1:8765  (API docs: /docs)

Settings come from the environment (.env.example): RW_HOST (default 127.0.0.1: the machine only), RW_PORT,
RW_RUNS_DIR, RW_KEEP_RUNS, RW_MAX_UPLOAD_MB. One run at a time. No data leaves the machine.
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from . import decide
from . import schemas as api
from .job import Job

PHRASES = Path(__file__).resolve().parents[2] / 'models/phrases-demo'   # draft WAVs (OQ-B5)
PAGE = Path(__file__).with_name('web.html').read_text(encoding='utf-8')
MAX_UPLOAD = int(os.environ.get('RW_MAX_UPLOAD_MB', 2048)) << 20
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.avi', '.hevc', '.h264', '.webm'}
RUN_ID = re.compile(r'^[0-9a-f]{12}$')
RUN_FILES = {'annotated.mp4': 'video/mp4', 'decisions.json': 'application/json', 'run.json': 'application/json'}
SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                               "img-src 'self' blob: data:; media-src 'self' blob:; frame-ancestors 'none'",
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
}

logging.basicConfig(level=os.environ.get('RW_LOG_LEVEL', 'INFO'),
                    format='{"t":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger('roadwatch.web')
app = FastAPI(title='RoadWatch Copilot demo API', version=api.API_VERSION,
              description='BT-A đo khoảng cách, BT-B quyết định cảnh báo, BT-C vận hành và kiểm chứng. Chỉ cảnh báo, '
                          'chạy offline.')
JOB = Job()


ERRORS = {c: {'model': api.Error} for c in (400, 404, 409, 413, 415)}


@app.middleware('http')
async def security_headers(request: Request, call_next):
    t = time.perf_counter()
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if not request.url.path.startswith(('/api/events', '/api/stream')):
        log.info('%s %s %d %.1fms', request.method, request.url.path, response.status_code,
                 1000 * (time.perf_counter() - t))
    return response


@app.get('/', response_class=HTMLResponse, include_in_schema=False)
def page():
    return PAGE


@app.get('/health', response_model=api.Health)
def health():
    """Liveness for Docker/CI; `degraded` when a running job has not produced a frame for 2 s."""
    return {**JOB.health(), 'model': (Path(__file__).resolve().parents[2] / 'models/gr14VinAI.onnx').exists()}


@app.get('/api/config', response_model=api.BtBConfig)
def config():
    """BT-B parameters in use (provisional values of config/proposals/v0.yaml; changes go through HITL)."""
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
        while not await request.is_disconnected():
            with JOB.lock:
                st = JOB.status
            if st is not last:
                last = st
                yield 'event: status\ndata: ' + api.LiveStatus(**st).model_dump_json() + '\n\n'
            await asyncio.sleep(0.005)
    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})


@app.get('/api/stream')
async def stream(request: Request):
    """Annotated frames as MJPEG."""
    async def gen():
        last = None
        while not await request.is_disconnected():
            jpeg = JOB.jpeg
            if jpeg is not None and jpeg is not last:
                last = jpeg
                yield b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpeg) + jpeg + b'\r\n'
            await asyncio.sleep(0.02)
    return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=f')


@app.get('/api/phrases/{kind}', responses={200: {'content': {'audio/wav': {}}}, 404: {'model': api.Error}})
def phrase(kind: api.Level):
    if not (PHRASES / f'{kind.value}.wav').is_file():
        raise HTTPException(404, 'không có câu này')
    return FileResponse(PHRASES / f'{kind.value}.wav', media_type='audio/wav')


@app.post('/api/runs', response_model=api.RunStarted, responses=ERRORS,
          openapi_extra={'requestBody': {'required': True, 'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}})
async def create_run(request: Request, name: str = Query(..., max_length=200),
                     fps: float = Query(..., gt=0, le=240), d: float = Query(..., ge=0, le=5),
                     fy: float | None = Query(None, gt=0, le=10000), rt: bool = True):
    """Upload a video as the raw request body (not multipart) and start a run on it at once.

    `fps`: true capture rate; `d`: camera to front bumper (m); `fy`: focal length (px), empty = learn it;
    `rt`: pace to real time (20 Hz) instead of as fast as possible."""
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(415, f'chỉ nhận video {sorted(VIDEO_EXT)}')
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
    JOB.start(run_id, video, fps, d, fy, rt, name=Path(name).name)
    log.info('run %s uploaded: %s, %.1f MB', run_id, Path(name).name, size / 2**20)
    return api.RunStarted(run_id=run_id, state='loading')


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
        out.append(api.RunInfo(**info))
    return out


def _run_dir(run_id):
    if not RUN_ID.match(run_id) or not (JOB.runs / run_id / 'run.json').exists():
        raise HTTPException(404, 'không có lần chạy này')
    return JOB.runs / run_id


@app.get('/api/runs/{run_id}/files/{name}', responses={200: {'content': {'video/mp4': {}, 'application/json': {}}}, 404: {'model': api.Error}})
def run_file(run_id: str, name: str):
    """Annotated video (byte ranges, so <video> can seek), decision log or run metadata."""
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
