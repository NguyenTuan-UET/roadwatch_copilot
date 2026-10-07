"""Local demo UI: upload a video, watch the annotated stream and the calibration/lead panel live.

    python -m src.roadwatch.web [--port 8765]      then open http://127.0.0.1:8765

Standard library HTTP server, one job at a time, binds to localhost only. Outputs go to runs/demo/.
"""
import argparse
import json
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from . import decide
from .__main__ import LEARN_FRAMES, LEARN_SKIP
from .calibration import learn_fy
from .hud import draw
from .model import MODEL_HZ, Supercombo, decode
from .pipeline import Pipeline

RUNS = Path(__file__).resolve().parents[2] / 'runs/demo'
PHRASES = Path(__file__).resolve().parents[2] / 'models/phrases-demo'   # draft WAVs (OQ-B5)
PAGE = (Path(__file__).with_name('web.html')).read_text(encoding='utf-8')


class Job:
    """The single running job; the HTTP handlers only read `status` and `jpeg`."""
    def __init__(self):
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.status = {'state': 'idle'}
        self.jpeg = None
        self.model = None

    def start(self, video, fps, d_bumper, fy, realtime):
        self.stop.set()
        if self.thread:
            self.thread.join()
        self.stop.clear()
        self.thread = threading.Thread(target=self._run, args=(video, fps, d_bumper, fy, realtime), daemon=True)
        self.thread.start()

    def _preview(self, frame, w, h, banner=None):
        """Publish a JPEG for /stream. `frame` is BGR, or (y, u, v) planes."""
        if isinstance(frame, tuple):
            frame = cv2.cvtColor(np.concatenate([p.ravel() for p in frame]).reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_I420)
        img = cv2.resize(frame, (960, 960 * h // w))
        if banner:
            cv2.rectangle(img, (0, 0), (960, 40), (0, 0, 0), -1)
            cv2.putText(img, banner, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 255, 255), 2)
        self.jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()

    def _set(self, **kw):
        with self.lock:
            self.status = {**self.status, **kw}

    def _run(self, video, fps, d_bumper, fy, realtime):
        try:
            self.status = {'state': 'đang nạp model'}
            self.model = self.model or Supercombo()
            cap = cv2.VideoCapture(str(video))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if not w or w % 2 or h % 2:
                raise ValueError(f'không đọc được khung có kích thước chẵn ({w}x{h})')
            if not fy:
                self._set(state='đang học fy (~1 phút)')
                frames = list(decode(video, w, h, LEARN_SKIP + LEARN_FRAMES, fps))[LEARN_SKIP:]
                if len(frames) < LEARN_FRAMES // 2:
                    raise ValueError('video quá ngắn để học fy; nhập fy')
                n = [0]

                def preview(fy_try, f):  # show the frames being tried, every 4th, with the candidate fy
                    n[0] += 1
                    if n[0] % 4 == 0:
                        self._preview(f, w, h, f'Dang hoc fy: thu fy = {fy_try:.0f} px')
                    if self.stop.is_set():
                        raise InterruptedError
                fy, _ = learn_fy(frames, w, h, self.model, progress=preview)
            pipe = Pipeline(w, h, fy, d_bumper, self.model)
            out = video.with_suffix('.roadwatch.mp4')
            # H.264 so the browser can play it; ffmpeg is already required for decoding.
            writer = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}',
                                       '-r', str(MODEL_HZ), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast',
                                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)], stdin=subprocess.PIPE)
            log, t0, all_ms = [], time.perf_counter(), []
            dec, events, hist = decide.Decider(), [], []
            prev_raw, onsets, said = set(), dict.fromkeys(decide.RANK, 0), dict.fromkeys(decide.RANK, 0)
            for i, (y, u, v) in enumerate(decode(video, w, h, fps=fps)):
                if self.stop.is_set():
                    break
                t = time.perf_counter()
                r = pipe.step(y, u, v)
                ts = i / MODEL_HZ
                d = dec.step(ts, r.gap_m, r.ego_speed_mps, r.ttc_s, r.status == 'calibrated',
                             not r.status.startswith('unreliable'))
                ms = 1000 * (time.perf_counter() - t)
                all_ms.append(ms)
                for k in d.raw - prev_raw:   # baseline without dispatch: speak at every raw onset
                    onsets[k] += 1
                prev_raw = d.raw
                if d.say:
                    said[d.say] += 1
                    events.append(dict(t_s=round(ts, 2), kind=d.say, text=decide.PHRASES[d.say], reason=d.reason))
                hist.append([round(ts, 2), r.gap_m and round(r.gap_m, 1), d.threshold_m, r.ttc_s and round(r.ttc_s, 2)])
                del hist[:-600]
                frame = draw(cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                                          cv2.COLOR_YUV2BGR_I420), pipe.K, r, fy)
                writer.stdin.write(frame.tobytes())
                self._preview(frame, w, h)
                rec = dict(t_s=i / MODEL_HZ, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                           ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s,
                           level=d.level, say=d.say, reason=d.reason)
                log.append(rec)
                rnd = lambda x, n=1: None if x is None else round(float(x), n)  # noqa: E731
                self._set(state='đang chạy', status=r.status, frame=i, fy=round(fy), ms=rnd(ms),
                          pitch_deg=rnd(np.degrees(r.rpy[1]), 2), yaw_deg=rnd(np.degrees(r.rpy[2]), 2),
                          height_m=rnd(r.height_m, 2), ego_kmh=rnd(r.ego_speed_mps * 3.6), lead_prob=rnd(r.lead_prob, 2),
                          gap_m=rnd(r.gap_m), lead_kmh=rnd(r.lead_speed_mps * 3.6 if r.lead_speed_mps else None),
                          ttc_s=rnd(r.ttc_s), resets=pipe.cal.resets, level=d.level, say=d.say, reason=d.reason,
                          threshold_m=d.threshold_m, coverage=round(pipe.coverage, 3),
                          p50=rnd(np.percentile(all_ms, 50)), p95=rnd(np.percentile(all_ms, 95)),
                          fps=rnd((i + 1) / (time.perf_counter() - t0)),
                          events=events[-30:], hist=list(hist), onsets=dict(onsets), said=dict(said))
                if realtime:
                    time.sleep(max(0.0, t0 + (i + 1) / MODEL_HZ - time.perf_counter()))
            writer.stdin.close()
            writer.wait()
            js = out.with_suffix('.json')
            js.write_text(json.dumps(dict(fy=fy, d_cam_bumper_m=d_bumper, events=events, onsets=onsets, said=said,
                                          frames=log), indent=1, default=float))
            self._set(state='đã dừng' if self.stop.is_set() else 'xong', out=out.name, json=js.name)
        except InterruptedError:
            self._set(state='đã dừng')
        except Exception as e:  # shown in the panel; the server keeps running
            self._set(state='lỗi', error=str(e))


JOB = Job()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype='text/plain; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/':
            self._send(200, PAGE.encode(), 'text/html; charset=utf-8')
        elif url.path == '/status':
            with JOB.lock:
                self._send(200, json.dumps(JOB.status, default=float).encode(), 'application/json')
        elif url.path == '/config':
            self._send(200, json.dumps(dict(
                legal=decide.LEGAL, ttc_emergency_s=decide.TTC_EMERGENCY_S, h_ttc_s=decide.H_TTC_S,
                t_confirm_s=decide.T_CONFIRM_S, h_m=decide.H_M, t_clear_s=decide.T_CLEAR_S,
                cooldown_s=decide.COOLDOWN_S, grace_s=decide.GRACE_S, info_horizon_s=decide.INFO_HORIZON_S,
                phrases=decide.PHRASES)).encode(), 'application/json')
        elif url.path == '/phrase':
            p = PHRASES / (Path(parse_qs(url.query).get('k', [''])[0]).name + '.wav')
            self._send(200, p.read_bytes(), 'audio/wav') if p.is_file() else self._send(404, b'not found')
        elif url.path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f')
            self.end_headers()
            last = None
            try:
                while True:
                    if JOB.jpeg is not None and JOB.jpeg is not last:
                        last = JOB.jpeg
                        self.wfile.write(b'--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(last)
                                         + last + b'\r\n')
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif url.path == '/file':
            p = (RUNS / Path(parse_qs(url.query).get('p', [''])[0]).name)   # name only: no path traversal
            if not p.is_file():
                return self._send(404, b'not found')
            data, ctype = p.read_bytes(), 'video/mp4' if p.suffix == '.mp4' else 'application/json'
            m = re.match(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
            if not m:   # browsers need byte ranges to seek in <video>
                return self._send(200, data, ctype)
            start, end = int(m[1]), int(m[2]) if m[2] else len(data) - 1
            self.send_response(206)
            self.send_header('Content-Type', ctype)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
            self.send_header('Content-Length', str(end - start + 1))
            self.end_headers()
            self.wfile.write(data[start:end + 1])
        else:
            self._send(404, b'not found')

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == '/stop':
            JOB.stop.set()
            return self._send(200, b'ok')
        if url.path != '/run':
            return self._send(404, b'not found')
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            fps, d_bumper = float(q['fps']), float(q['d'])
            fy = float(q['fy']) if q.get('fy') else None
            if fps <= 0 or d_bumper < 0 or (fy is not None and fy <= 0):
                raise ValueError
        except (KeyError, ValueError):
            return self._send(400, 'fps > 0, camera→cản ≥ 0, fy > 0 hoặc trống'.encode())
        RUNS.mkdir(parents=True, exist_ok=True)
        video = RUNS / Path(q.get('name', 'video.mp4')).name
        size = int(self.headers.get('Content-Length', 0))
        with open(video, 'wb') as f:
            while size > 0:
                chunk = self.rfile.read(min(size, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                size -= len(chunk)
        JOB.start(video, fps, d_bumper, fy, q.get('rt') == '1')
        self._send(200, b'started')

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    port = ap.parse_args().port
    print(f'http://127.0.0.1:{port}')
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
