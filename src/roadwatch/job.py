"""One demo run: video -> BT-A pipeline -> BT-B decision, frame by frame, in a background thread.

Workflow (states): idle -> loading -> running -> done | stopped | failed. Reliability rules:
* a frame that raises is counted and skipped (no alert from it); MAX_BAD_FRAMES in a row fails the run;
* fy unknown: start on a guess, learn fy in the background, switch when known; distance alerts stay off until then,
  the TTC alert does not (TTC barely depends on fy);
* heartbeat.json in the runs folder is rewritten every second; /health reports a run whose last frame is older
  than HANG_S as hung;
* each run has its own folder runs/demo/<run_id>/ (input, annotated video, decision log, run.json); only the
  newest KEEP_RUNS are kept (privacy: uploaded dashcam video is not stored forever).
"""
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from . import decide
from .__main__ import LEARN_FRAMES, LEARN_SKIP
from .calibration import learn_fy
from .hud import draw
from .model import MODEL_HZ, Supercombo, decode
from .pipeline import Pipeline

LEARN_WORKERS = 4      # parallel fy sweep sessions x 2 threads, beside the live 4-thread session
FY_GUESS_FRAC = 0.84   # middle of the learn_fy grid (0.4..1.28 x width); distance alerts stay off on it
MAX_BAD_FRAMES = 20    # consecutive frames that raise before the run fails (1 s at 20 Hz)
HANG_S = 2.0           # runtime.hang_timeout_ms of the proposed configuration
KEEP_RUNS = int(os.environ.get('RW_KEEP_RUNS', 20))
RUNS = Path(os.environ.get('RW_RUNS_DIR', Path(__file__).resolve().parents[2] / 'runs/demo'))
log = logging.getLogger('roadwatch.job')


class Job:
    """The single running job; HTTP handlers only read `status` and `jpeg`."""

    def __init__(self, runs=RUNS):
        self.runs = Path(runs)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.status = {'state': 'idle'}
        self.jpeg = None
        self.model = None
        self.last_frame_at = None
        self.history = []   # chart samples of the current run (schemas.Sample), last 600

    def start(self, run_id, video, fps, d_bumper, fy, realtime, name=None):
        self.stop.set()
        if self.thread:
            self.thread.join()
        self.stop.clear()
        self.prune()
        self.status, self.jpeg, self.last_frame_at = {'state': 'loading', 'run_id': run_id}, None, None
        self.history = []
        self.thread = threading.Thread(target=self._run, args=(run_id, video, fps, d_bumper, fy, realtime, name), daemon=True)
        self.thread.start()

    def health(self):
        with self.lock:
            st = self.status.get('state')
        hung = st == 'running' and self.last_frame_at is not None and time.monotonic() - self.last_frame_at > HANG_S
        return {'status': 'degraded' if hung else 'ok', 'job': st, 'hung': hung}

    def prune(self):
        """Keep the newest KEEP_RUNS run folders."""
        runs = sorted((p for p in self.runs.glob('*') if (p / 'run.json').exists()), key=lambda p: p.stat().st_mtime)
        for p in runs[:-KEEP_RUNS] if KEEP_RUNS > 0 else runs:
            shutil.rmtree(p, ignore_errors=True)
            log.info('pruned run %s', p.name)

    def _set(self, **kw):
        with self.lock:
            self.status = {**self.status, **kw}

    def _heartbeat(self, frame):
        now = time.time()
        if now - getattr(self, '_hb', 0) >= 1:
            self._hb = now
            tmp = self.runs / 'heartbeat.json.tmp'
            tmp.write_text(json.dumps({'t_unix': now, 'state': self.status.get('state'), 'frame': frame,
                                       'run_id': self.status.get('run_id')}))
            os.replace(tmp, self.runs / 'heartbeat.json')

    def _preview(self, frame, w, h):
        img = cv2.resize(frame, (960, 960 * h // w))
        self.jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()

    def _learn(self, learn, w, h):
        def stop(*_):
            if self.stop.is_set():
                raise InterruptedError
        try:
            learn['fy'] = learn_fy(learn['frames'], w, h, [Supercombo(threads=2) for _ in range(LEARN_WORKERS)],
                                   progress=stop)[0]
            log.info('fy learned: %.0f px', learn['fy'])
        except InterruptedError:
            pass
        except ValueError as e:   # stays on the guess; distance alerts stay off
            learn['error'] = str(e)
            log.warning('fy not learned: %s', e)

    def _run(self, run_id, video, fps, d_bumper, fy, realtime, name=None):
        folder = video.parent
        meta = dict(run_id=run_id, video=name or video.name, fps=fps, d_cam_bumper_m=d_bumper, fy_given=fy,
                    started_unix=time.time())
        (folder / 'run.json').write_text(json.dumps(meta, indent=1))
        writer = None
        try:
            self.model = self.model or Supercombo()
            cap = cv2.VideoCapture(str(video))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if not w or w % 2 or h % 2:
                raise ValueError(f'không đọc được video hoặc kích thước khung không chẵn ({w}x{h})')
            auto_fy = not fy
            learn = None if fy else {'frames': [], 'fy': None, 'error': None}
            fy = fy or FY_GUESS_FRAC * w
            pipe = Pipeline(w, h, fy, d_bumper, self.model)
            out = folder / 'annotated.mp4'
            # H.264 so the browser can play it; ffmpeg is already required for decoding.
            writer = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}',
                                       '-r', str(MODEL_HZ), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast',
                                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)], stdin=subprocess.PIPE)
            frames, t0, all_ms, bad, bad_total = [], time.perf_counter(), [], 0, 0
            dec, events = decide.Decider(), []
            self.history = []
            prev_raw, onsets, said = set(), dict.fromkeys(decide.RANK, 0), dict.fromkeys(decide.RANK, 0)
            log.info('run %s started: %s %dx%d fps=%s fy=%s', run_id, video.name, w, h, fps, 'auto' if auto_fy else fy)
            for i, (y, u, v) in enumerate(decode(video, w, h, fps=fps)):
                if self.stop.is_set():
                    break
                t = time.perf_counter()
                if learn is not None:
                    if LEARN_SKIP <= i < LEARN_SKIP + LEARN_FRAMES:
                        learn['frames'].append((y, u, v))
                    if i == LEARN_SKIP + LEARN_FRAMES:
                        threading.Thread(target=self._learn, args=(learn, w, h), daemon=True).start()
                    if learn['fy']:
                        fy, learn = learn['fy'], None
                        pipe.set_fy(fy)
                bgr = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                                   cv2.COLOR_YUV2BGR_I420)
                try:
                    r = pipe.step(y, u, v)
                except Exception:   # one bad frame: no measurement, no alert from it
                    bad, bad_total = bad + 1, bad_total + 1
                    log.exception('frame %d failed (%d in a row)', i, bad)
                    if bad >= MAX_BAD_FRAMES:
                        raise RuntimeError(f'{bad} khung lỗi liên tiếp') from None
                    writer.stdin.write(bgr.tobytes())
                    continue
                bad = 0
                tb = time.perf_counter()
                ts = i / MODEL_HZ
                d = dec.step(ts, r.gap_m, r.ego_speed_mps, r.ttc_s, r.status == 'calibrated' and learn is None,
                             not r.status.startswith('unreliable'))
                ms, b_us = 1000 * (time.perf_counter() - t), 1e6 * (time.perf_counter() - tb)
                all_ms.append(ms)
                for k in d.raw - prev_raw:   # baseline without dispatch: speak at every raw onset
                    onsets[k] += 1
                prev_raw = d.raw
                if d.say:
                    said[d.say] += 1
                    events.append(dict(t_s=round(ts, 2), kind=d.say, text=decide.PHRASES[d.say], reason=d.reason))
                rnd = lambda x, n=1: None if x is None else round(float(x), n)  # noqa: E731
                sample = dict(t_s=round(ts, 2), gap_m=rnd(r.gap_m), threshold_m=d.threshold_m, ttc_s=rnd(r.ttc_s, 2))
                self.history.append(sample)
                del self.history[:-600]
                frame = draw(bgr, pipe.K, r, fy)
                writer.stdin.write(frame.tobytes())
                self._preview(frame, w, h)
                frames.append(dict(t_s=ts, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                                   ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s,
                                   level=d.level, say=d.say, reason=d.reason))
                self.last_frame_at = time.monotonic()
                fy_state = ('nhập tay' if not auto_fy else 'đã học' if learn is None else
                            f"lỗi: {learn['error']}" if learn['error'] else
                            f'đang học nền (tạm {fy:.0f})' if len(learn['frames']) >= LEARN_FRAMES else
                            f"gom khung {len(learn['frames'])}/{LEARN_FRAMES} (tạm {fy:.0f})")
                self._set(  # shape: schemas.LiveStatus
                    state='running',
                    measure=dict(frame=i, t_s=round(ts, 2), ego_kmh=rnd(r.ego_speed_mps * 3.6), ttc_s=rnd(r.ttc_s),
                                 lead=dict(prob=rnd(r.lead_prob, 2), gap_m=rnd(r.gap_m),
                                           speed_kmh=rnd(r.lead_speed_mps * 3.6 if r.gap_m is not None else None)),
                                 calibration=dict(status=r.status, calibrated=r.status == 'calibrated' and learn is None,
                                                  fy_px=round(fy), fy_state=fy_state, pitch_deg=rnd(np.degrees(r.rpy[1]), 2),
                                                  yaw_deg=rnd(np.degrees(r.rpy[2]), 2), height_m=rnd(r.height_m, 2),
                                                  coverage=round(pipe.coverage, 3), remounts=pipe.cal.resets)),
                    decision=dict(level=d.level, say=d.say, reason=d.reason, threshold_m=d.threshold_m,
                                  latency_us=round(b_us)),
                    ops=dict(fps=rnd((i + 1) / (time.perf_counter() - t0)), bad_frames=bad_total,
                             latency=dict(last_ms=rnd(ms), p50_ms=rnd(np.percentile(all_ms, 50)),
                                          p95_ms=rnd(np.percentile(all_ms, 95))),
                             raw_onsets=dict(onsets), said=dict(said)),
                    sample=sample, events=events[-30:])
                self._heartbeat(i)
                if realtime:
                    time.sleep(max(0.0, t0 + (i + 1) / MODEL_HZ - time.perf_counter()))
            writer.stdin.close()
            if writer.wait():
                raise RuntimeError(f'ffmpeg ghi video lỗi (mã {writer.returncode})')
            summary = dict(fy=fy, frames=len(frames), bad_frames=bad_total, onsets=onsets, said=said,
                           p50_ms=np.percentile(all_ms, 50) if all_ms else None,
                           p95_ms=np.percentile(all_ms, 95) if all_ms else None)
            (folder / 'decisions.json').write_text(json.dumps(dict(summary=summary, events=events, frames=frames),
                                                              indent=1, default=float))
            state = 'stopped' if self.stop.is_set() else 'done'
            (folder / 'run.json').write_text(json.dumps({**meta, **summary, 'state': state}, indent=1, default=float))
            base = f'/api/runs/{run_id}/files/'
            self._set(state=state, outputs=dict(video_url=base + 'annotated.mp4', log_url=base + 'decisions.json'))
            log.info('run %s %s: %d frames, %d bad, said %s', run_id, state, len(frames), bad_total, said)
        except InterruptedError:
            self._set(state='stopped')
        except Exception as e:  # shown in the panel; the server keeps running
            log.exception('run %s failed', run_id)
            (folder / 'run.json').write_text(json.dumps({**meta, 'state': 'failed', 'error': str(e)}, indent=1))
            self._set(state='failed', error=str(e))
        finally:
            if writer and writer.poll() is None:
                writer.kill()
            self._hb = 0
            self._heartbeat(-1)
