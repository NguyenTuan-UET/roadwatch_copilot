"""One demo run: video -> BT-A pipeline -> BT-B decision, frame by frame, in a background thread.

Workflow (states): idle -> loading -> running -> done | stopped | failed. Reliability rules:
* like comma_ai realtime_lead.py: letterbox bars cropped, the model fed every n-th frame (tick close to 20 Hz),
  every frame drawn with the latest result and written at the video's frame rate;
* a model tick that raises is counted and skipped (no alert from it); MAX_BAD_FRAMES in a row fails the run;
* the focal length is given by hand by default (fy, mm or field of view), like comma_ai; with `auto_focal` and a GPS
  log it is refined from the GPS speed. Only when asked (`lens='learn'`) fy is unknown: start on a guess, learn fy in
  the background, switch when known. Distance alerts stay off until the focal length has settled, the TTC alert does
  not (TTC barely depends on fy);
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
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import decide
from . import gps as gpslib
from .calibration import LEARN_FRAMES, LEARN_SKIP, FocalFromSpeed, focal_px_from_hfov, focal_px_from_mm, learn_fy
from .hud import draw
from .model import Gr14VinAI, decode, detect_content_box, tick, video_size
from .pipeline import Pipeline

LEARN_WORKERS = 4      # parallel fy sweep sessions x 2 threads, beside the live 4-thread session
FY_GUESS_FRAC = 0.84   # middle of the learn_fy grid (0.4..1.28 x width); distance alerts stay off on it
MAX_BAD_FRAMES = 20    # consecutive model ticks that raise before the run fails (~1 s)
HANG_S = 2.0           # runtime.hang_timeout_ms of the proposed configuration
KEEP_RUNS = int(os.environ.get('RW_KEEP_RUNS', 20))
RUNS = Path(os.environ.get('RW_RUNS_DIR', Path(__file__).resolve().parents[2] / 'runs/demo'))
log = logging.getLogger('roadwatch.job')


@dataclass
class Options:
    """Run settings of comma_ai/lead_distance pages/Upload_video.py; the defaults are its defaults.

    lens: how the focal length is given when fy is not: 'mm' (f_mm, 35 mm-equivalent unless sensor_mm) or
    'fov' (hfov_deg of the camera picture, pinhole or fisheye) or 'learn' (RoadWatch: learned from the video, only
    when asked). The default is 'mm' and the value is typed in.
    gps: GPS log (GPX / NMEA / CSV) for the ego speed; gps_offset: GPS time at video t = 0, None = synced
    automatically; auto_focal: fit the focal length to the GPS speed (experimental, needs gps).
    crop: 'auto' (letterbox bars removed), 'full' or (x, y, w, h) of the camera picture.
    preview_every: the live preview frame is refreshed every N video frames (smaller = smoother, more CPU)."""
    lens: str = 'mm'
    f_mm: float | None = None
    sensor_mm: float | None = None
    hfov_deg: float | None = None
    fisheye: bool = False
    gps: Path | None = None
    gps_offset: float | None = None
    auto_focal: bool = False
    crop: str | tuple = 'auto'
    use_pitch: bool = True
    preview_every: int = 2


def camera_box(video, crop):
    """Camera picture (x, y, w, h) inside the video frame, even-sized and -placed (U, V planes are half-size)."""
    size = video_size(video)
    if size is None:
        raise ValueError('không đọc được video (codec không được hỗ trợ); hãy chuyển sang H.264')
    big_w, big_h = size
    if crop == 'auto':
        box = detect_content_box(video)
    elif crop == 'full':
        box = (0, 0, big_w, big_h)
    else:
        box = tuple(int(v) for v in crop)
        if len(box) != 4 or min(box) < 0 or box[0] + box[2] > big_w or box[1] + box[3] > big_h:
            raise ValueError(f'vùng ảnh {crop} nằm ngoài khung {big_w}x{big_h}')
    x, y = box[0] + box[0] % 2, box[1] + box[1] % 2
    w, h = (box[2] - (x - box[0])) // 2 * 2, (box[3] - (y - box[1])) // 2 * 2
    if w < 64 or h < 64:
        raise ValueError(f'vùng ảnh camera quá nhỏ ({w}x{h})')
    return x, y, w, h


def given_focal(fy, opts, w, h):
    """(focal px, how) from the user's lens settings, like comma's upload page; (None, None) = learn it (lens='learn');
    ValueError when none is given."""
    if fy:
        return fy, 'nhập tay'
    if opts.lens == 'mm' and opts.f_mm:
        return focal_px_from_mm(opts.f_mm, max(w, h), opts.sensor_mm), 'từ tiêu cự mm'
    if opts.lens == 'fov' and opts.hfov_deg:
        return focal_px_from_hfov(w, opts.hfov_deg, 'fisheye' if opts.fisheye else 'pinhole'), 'từ góc nhìn'
    if opts.lens == 'learn':
        return None, None
    raise ValueError('chưa có tiêu cự: nhập tiêu cự pixel, tiêu cự mm hoặc góc nhìn ngang')


class Job:
    """The single running job; HTTP handlers only read `status` and `jpeg`."""

    def __init__(self, runs=RUNS):
        self.runs = Path(runs)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.status = {'state': 'idle'}
        self.jpeg = None
        self.preview: tuple[str, int, np.ndarray] | None = None   # latest frame; WebRTC never queues old frames
        self.model = None
        self.last_frame_at = None
        self.history = []   # chart samples of the current run (schemas.Sample), last 600
        self.recover()

    def recover(self):
        """Runs left without a final state (the server stopped mid-run) are marked failed, so the history does not
        show them as running forever. Only called before this process starts a run; a run whose heartbeat is fresh
        belongs to another live server on the same folder and is left alone."""
        live = None
        try:
            hb = json.loads((self.runs / 'heartbeat.json').read_text())
            if hb.get('state') in ('loading', 'running') and time.time() - hb.get('t_unix', 0) < 5:
                live = hb.get('run_id')
        except (OSError, ValueError):
            pass
        for p in self.runs.glob('*/run.json'):
            try:
                meta = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if meta.get('state') is None and p.parent.name != live:
                p.write_text(json.dumps({**meta, 'state': 'failed', 'error': 'server tắt khi lần chạy chưa xong'}, indent=1))
                log.warning('run %s was interrupted; marked failed', p.parent.name)

    def start(self, run_id, video, fps, d_bumper, fy, realtime, name=None, opts=None):
        self.stop.set()
        if self.thread:
            self.thread.join()
        self.stop.clear()
        self.prune()
        self.status, self.jpeg, self.last_frame_at = {'state': 'loading', 'run_id': run_id}, None, None
        self.preview = None
        self.history = []
        self.thread = threading.Thread(target=self._run, args=(run_id, video, fps, d_bumper, fy, realtime, name, opts or Options()),
                                       daemon=True)
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

    def _learn(self, learn, w, h, vel_scale):
        def stop(*_):
            if self.stop.is_set():
                raise InterruptedError
        try:
            learn['fy'] = learn_fy(learn['frames'], w, h, [Gr14VinAI(threads=2) for _ in range(LEARN_WORKERS)],
                                   progress=stop, vel_scale=vel_scale)[0]
            log.info('fy learned: %.0f px', learn['fy'])
        except InterruptedError:
            pass
        except ValueError as e:   # stays on the guess; distance alerts stay off
            learn['error'] = str(e)
            log.warning('fy not learned: %s', e)

    def _run(self, run_id, video, fps, d_bumper, fy, realtime, name=None, opts=None):
        opts = opts or Options()
        folder = video.parent
        meta = dict(run_id=run_id, video=name or video.name, fps=fps, d_cam_bumper_m=d_bumper, fy_given=fy,
                    lens=opts.lens, gps=opts.gps.name if opts.gps else None, auto_focal=opts.auto_focal,
                    use_pitch=opts.use_pitch, started_unix=time.time())
        (folder / 'run.json').write_text(json.dumps(meta, indent=1))
        writer = None
        try:
            self.model = self.model or Gr14VinAI()
            box = camera_box(video, opts.crop)   # w, h = camera picture
            w, h = box[2:]
            stride, tick_dt, vel_scale = tick(fps)
            fy, fy_how = given_focal(fy, opts, w, h)
            gps = gpslib.GpsRef(*gpslib.load_gps(opts.gps), 'auto' if opts.gps_offset is None else opts.gps_offset) \
                if opts.gps else None
            focal = FocalFromSpeed(fy or FY_GUESS_FRAC * w) if opts.auto_focal and gps is not None else None
            learn = None if fy or focal else {'frames': [], 'fy': None, 'error': None}
            fy = fy or FY_GUESS_FRAC * w
            pipe = Pipeline(w, h, fy, d_bumper, self.model, tick_dt, v_ref=gps, focal=focal, use_pitch=opts.use_pitch)
            meta.update(crop=box, focal_px_start=fy)
            out = folder / 'annotated.mp4'
            # H.264 so the browser can play it; ffmpeg is already required for decoding.
            writer = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}',
                                       '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast',
                                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)], stdin=subprocess.PIPE)
            frames, t0, all_ms, bad, bad_total, r = [], time.perf_counter(), [], 0, 0, None
            hud_text = (None, None, opts.use_pitch)   # no top-right debug box on the video: angles and GPS state are on the web panel
            dec, events = decide.Decider(), []
            self.history = []
            prev_raw, onsets, said = set(), dict.fromkeys(decide.RANK, 0), dict.fromkeys(decide.RANK, 0)
            log.info('run %s started: %s %dx%d fps=%s fy=%s gps=%s', run_id, video.name, w, h, fps,
                     fy_how or 'auto', 'yes' if gps else 'no')
            for i, (y, u, v) in enumerate(decode(video, w, h, fps=fps, box=box)):
                if self.stop.is_set():
                    break
                bgr = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                                   cv2.COLOR_YUV2BGR_I420)
                if i % stride:   # between model ticks: draw the latest result
                    frame = bgr if r is None else draw(bgr, pipe.K, r, fy, *hud_text, debug=False)
                    writer.stdin.write(frame.tobytes())
                    self.preview = (run_id, i, frame)
                    if i % opts.preview_every == 0:
                        self._preview(frame, w, h)
                    if realtime:
                        time.sleep(max(0.0, t0 + (i + 1) / fps - time.perf_counter()))
                    continue
                t, k = time.perf_counter(), i // stride
                if learn is not None:
                    if LEARN_SKIP <= k < LEARN_SKIP + LEARN_FRAMES:
                        learn['frames'].append((y, u, v))
                    if k == LEARN_SKIP + LEARN_FRAMES:
                        threading.Thread(target=self._learn, args=(learn, w, h, vel_scale), daemon=True).start()
                    if learn['fy']:
                        fy, learn = learn['fy'], None
                        pipe.set_fy(fy)
                try:
                    r = pipe.step(y, u, v, i / fps)
                except Exception:   # one bad frame: no measurement, no alert from it
                    bad, bad_total = bad + 1, bad_total + 1
                    log.exception('frame %d failed (%d in a row)', i, bad)
                    if bad >= MAX_BAD_FRAMES:
                        raise RuntimeError(f'{bad} khung lỗi liên tiếp') from None
                    r = None
                    writer.stdin.write(bgr.tobytes())
                    continue
                bad = 0
                fy = r.fy_px   # follows the GPS focal fit
                tb = time.perf_counter()
                ts = i / fps
                calibrated = r.status == 'calibrated' and learn is None and (focal is None or focal.settled)
                d = dec.step(ts, r.gap_m, r.ego_speed_mps, r.ttc_s, calibrated, not r.status.startswith('unreliable'))
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
                flags = _flags(opts, gps, focal)
                hud_text = _hud_text(r, gps, focal, flags, opts.use_pitch)
                frame = draw(bgr, pipe.K, r, fy, *hud_text, debug=False)
                writer.stdin.write(frame.tobytes())
                self.preview = (run_id, i, frame)
                if i % opts.preview_every == 0:
                    self._preview(frame, w, h)
                frames.append(dict(t_s=ts, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                                   ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s,
                                   level=d.level, say=d.say, reason=d.reason))
                self.last_frame_at = time.monotonic()
                fy_state = (('theo GPS' if focal.settled else 'theo GPS: đang đồng bộ' if not gps.synced else
                             'theo GPS: đang hiệu chỉnh') if focal else fy_how if fy_how else
                            'đã học' if learn is None else
                            f"lỗi: {learn['error']}" if learn['error'] else
                            f'đang học nền (tạm {fy:.0f})' if len(learn['frames']) >= LEARN_FRAMES else
                            f"gom khung {len(learn['frames'])}/{LEARN_FRAMES} (tạm {fy:.0f})")
                self._set(  # shape: schemas.LiveStatus
                    state='running',
                    measure=dict(frame=i, t_s=round(ts, 2), ego_kmh=rnd(r.ego_speed_mps * 3.6), ttc_s=rnd(r.ttc_s),
                                 ego_source='gps' if r.gps_speed_mps is not None else 'model',
                                 gps=_gps_status(gps), lead_raw_m=rnd(None if r.lead_raw_m is None
                                                                      else r.lead_raw_m - d_bumper),
                                 lead=dict(prob=rnd(r.lead_prob, 2), gap_m=rnd(r.gap_m),
                                           speed_kmh=rnd(r.lead_speed_mps * 3.6 if r.gap_m is not None else None)),
                                 calibration=dict(status=r.status, calibrated=calibrated, flags=flags,
                                                  fy_px=round(fy), fy_state=fy_state, pitch_deg=rnd(np.degrees(r.rpy[1]), 2),
                                                  yaw_deg=rnd(np.degrees(r.rpy[2]), 2), height_m=rnd(r.height_m, 2),
                                                  coverage=round(pipe.coverage, 3), remounts=pipe.cal.resets)),
                    decision=dict(level=d.level, say=d.say, reason=d.reason, threshold_m=d.threshold_m,
                                  latency_us=round(b_us)),
                    ops=dict(fps=rnd((i + 1) / (time.perf_counter() - t0)), video_fps=fps, bad_frames=bad_total,
                             latency=dict(last_ms=rnd(ms), p50_ms=rnd(np.percentile(all_ms, 50)),
                                          p95_ms=rnd(np.percentile(all_ms, 95))),
                             raw_onsets=dict(onsets), said=dict(said)),
                    sample=sample, events=events[-30:])
                self._heartbeat(i)
                if realtime:
                    time.sleep(max(0.0, t0 + (i + 1) / fps - time.perf_counter()))
            writer.stdin.close()
            if writer.wait():
                raise RuntimeError(f'ffmpeg ghi video lỗi (mã {writer.returncode})')
            pipe.save_csv(folder / 'lead_distance.csv')
            big_w, big_h = video_size(video)
            calib = dict(info=f'video {big_w}x{big_h}@{fps:g}fps, camera crop x={box[0]} '
                              f'y={box[1]} {w}x{h}, f={pipe.K[0, 0]:.0f}px, model stride @ {1 / tick_dt:.0f} Hz, '
                              + (_gps_text(gps) if gps else 'no GPS'),
                         flags=_flags(opts, gps, focal), focal_px=float(pipe.K[0, 0]),
                         rpy_deg=np.degrees(pipe.cal.est).round(2).tolist(),
                         gps_offset_s=gps.offset if gps is not None and gps.synced else None,
                         gps_corr=None if gps is None or np.isnan(gps.corr) else gps.corr, bumper_m=d_bumper)
            (folder / 'calibration.json').write_text(json.dumps(calib, indent=1, ensure_ascii=False))
            summary = dict(fy=fy, frames=len(frames), bad_frames=bad_total, onsets=onsets, said=said,
                           p50_ms=np.percentile(all_ms, 50) if all_ms else None,
                           p95_ms=np.percentile(all_ms, 95) if all_ms else None)
            (folder / 'decisions.json').write_text(json.dumps(dict(summary=summary, events=events, frames=frames),
                                                              indent=1, default=float))
            state = 'stopped' if self.stop.is_set() else 'done'
            (folder / 'run.json').write_text(json.dumps({**meta, **summary, 'state': state}, indent=1, default=float))
            base = f'/api/runs/{run_id}/files/'
            self._set(state=state, outputs=dict(video_url=base + 'annotated.mp4', log_url=base + 'decisions.json',
                                                csv_url=base + 'lead_distance.csv',
                                                calibration_url=base + 'calibration.json'))
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


def _flags(opts, gps, focal):
    """comma realtime_lead VideoLeadPipeline.flags."""
    f = []
    if opts.auto_focal and gps is None:
        f.append('auto_focal_needs_gps')
    if gps is not None and gps.low_confidence:
        f.append('gps_sync_low_confidence')
    if focal is not None and not focal.settled:
        f.append('focal_calibrating')
    return f


def _gps_text(gps):
    return 'GPS syncing...' if not gps.synced else f'GPS sync {gps.offset:+.2f}s r={gps.corr:.2f}'


def _gps_status(gps):
    if gps is None:
        return dict(state='none', offset_s=None, corr=None)
    state = 'syncing' if not gps.synced else 'low_confidence' if gps.low_confidence else 'synced'
    return dict(state=state, offset_s=round(gps.offset, 2) if gps.synced else None,
                corr=None if np.isnan(gps.corr) else round(float(gps.corr), 3))


def _hud_text(r, gps, focal, flags, use_pitch):
    """(note under the panel, GPS line of the debug box, pitch applied) as comma realtime_lead renders them."""
    note = None
    if not r.status.startswith('calibrating'):
        if focal is not None and not gps.synced:
            note = 'Đang đồng bộ GPS (cần ~20 s xe chạy)...'
        elif focal is not None and not focal.settled:
            note = f'Đang hiệu chỉnh thang đo theo GPS... f={r.fy_px:.0f}px'
    line = (_gps_text(gps) if gps is not None else 'no GPS') + (f"  [{','.join(flags)}]" if flags else '')
    return note, line, use_pitch
