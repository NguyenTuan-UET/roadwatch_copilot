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

from .__main__ import LEARN_FRAMES, LEARN_SKIP
from .calibration import learn_fy
from .hud import draw
from .model import MODEL_HZ, Supercombo, decode
from .pipeline import Pipeline

RUNS = Path(__file__).resolve().parents[2] / 'runs/demo'
PAGE = '''<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>RoadWatch demo</title>
<style>body{font:14px system-ui;margin:16px;background:#111;color:#eee}img{max-width:100%;background:#000}
.row{display:flex;gap:16px;flex-wrap:wrap}.panel{min-width:280px}td{padding:2px 8px}input{width:90px}
a{color:#6cf}.warn{color:#f66}</style></head><body>
<h2>RoadWatch: tự hiệu chuẩn + supercombo</h2>
<p><input type="file" id="f" accept="video/*" style="width:auto"> fps lúc quay <input id="fps" value="30">
camera→cản (m) <input id="d" value="1.5"> fy px (trống = tự học) <input id="fy">
<label><input type="checkbox" id="rt" checked style="width:auto"> tốc độ thực</label>
<button onclick="run()">Chạy</button> <button onclick="fetch('/stop',{method:'POST'})">Dừng</button></p>
<div class="row"><div><img id="v" src="/stream"><video id="res" controls style="display:none;max-width:100%"></video></div>
<div class="panel"><table id="s"></table><p id="out"></p></div></div>
<script>
async function run(){const f=document.getElementById('f').files[0];if(!f){alert('Chọn video');return}
 const q=new URLSearchParams({name:f.name,fps:fps.value,d:d.value,fy:fy.value,rt:rt.checked?1:0});
 document.getElementById('out').textContent='Đang tải lên...';
 const r=await fetch('/run?'+q,{method:'POST',body:f});if(!r.ok)alert(await r.text());
 res.style.display='none';res.removeAttribute('src');v.style.display='';v.src='/stream?'+Date.now()}
const L={state:'Trạng thái',status:'Hiệu chuẩn',frame:'Khung',fy:'fy (px)',pitch_deg:'Pitch (°)',yaw_deg:'Yaw (°)',
 height_m:'Cao camera (m)',ego_kmh:'Xe mình (km/h)',lead_prob:'P xe trước',gap_m:'Khoảng cách (m)',
 lead_kmh:'Xe trước (km/h)',ttc_s:'TTC (s)',resets:'Lắp lại',ms:'ms/khung',error:'Lỗi'};
setInterval(async()=>{const s=await (await fetch('/status')).json();
 document.getElementById('s').innerHTML=Object.entries(L).filter(([k])=>k in s).map(([k,n])=>
  `<tr><td>${n}</td><td class="${k=='error'||(k=='ttc_s'&&s[k]!=null&&s[k]<3)?'warn':''}">${s[k]??'—'}</td></tr>`).join('');
 document.getElementById('out').innerHTML=s.out?`Tải: <a href="/file?p=${s.out}">video</a> · <a href="/file?p=${s.json}">JSON</a>`:'';
 if(s.out&&!res.src.endsWith(s.out)){v.style.display='none';res.src='/file?p='+s.out;res.style.display=''}},500)
</script></body></html>'''


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
            log, t0 = [], time.perf_counter()
            for i, (y, u, v) in enumerate(decode(video, w, h, fps=fps)):
                if self.stop.is_set():
                    break
                t = time.perf_counter()
                r = pipe.step(y, u, v)
                ms = 1000 * (time.perf_counter() - t)
                frame = draw(cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                                          cv2.COLOR_YUV2BGR_I420), pipe.K, r, fy)
                writer.stdin.write(frame.tobytes())
                self._preview(frame, w, h)
                rec = dict(t_s=i / MODEL_HZ, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                           ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s)
                log.append(rec)
                rnd = lambda x, n=1: None if x is None else round(float(x), n)  # noqa: E731
                self._set(state='đang chạy', status=r.status, frame=i, fy=round(fy), ms=rnd(ms),
                          pitch_deg=rnd(np.degrees(r.rpy[1]), 2), yaw_deg=rnd(np.degrees(r.rpy[2]), 2),
                          height_m=rnd(r.height_m, 2), ego_kmh=rnd(r.ego_speed_mps * 3.6), lead_prob=rnd(r.lead_prob, 2),
                          gap_m=rnd(r.gap_m), lead_kmh=rnd(r.lead_speed_mps * 3.6 if r.lead_speed_mps else None),
                          ttc_s=rnd(r.ttc_s), resets=pipe.cal.resets)
                if realtime:
                    time.sleep(max(0.0, t0 + (i + 1) / MODEL_HZ - time.perf_counter()))
            writer.stdin.close()
            writer.wait()
            js = out.with_suffix('.json')
            js.write_text(json.dumps(dict(fy=fy, d_cam_bumper_m=d_bumper, frames=log), indent=1, default=float))
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
                self._send(200, json.dumps(JOB.status).encode(), 'application/json')
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
