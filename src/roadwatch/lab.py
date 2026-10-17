"""Lab page: run BT-A on a comma2k19 segment and compare its lead distance with the car's radar and its speed with
the car's CAN log, like comma_ai/lead_distance/app.py (data readers copied from lead_distance.py, not imported).

A segment folder holds video.mp4 (20 Hz, 1164x874), global_pose/frame_times, processed_log/CAN/radar (t, value:
distance, lateral offset, ...) and processed_log/CAN/speed (t, value). The radar is mounted at the front of the car,
so the model distance is compared minus the camera -> radar offset (`bumper`, RADAR_TO_CAMERA = 1.52 m).
Results are cached per segment (result.json + annotated.mp4); the page re-gates the raw lead per threshold itself.
Segments are read from RW_LAB_DIR (default data/comma2k19, not committed); results go to RW_LAB_CACHE.

As app.py (lead_distance.process_segment): the model's wide input is the narrow one duplicated by default (`wide`,
comma2k19 has only the narrow camera); the camera angles are estimated over the first CALIB_FRAMES frames and only
the yaw is applied, fixed for the whole run; the annotated video shows the raw "now" lead gated by lead_mask
(default thresholds), the radar distance under the panel and no calibration box.
"""
import csv
import json
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from .calibration import AutoCalib, intrinsics
from .hud import LaneSmoother, draw
from .model import Gr14VinAI, decode, pack_frame, video_size, warp_matrices
from .pipeline import Pipeline, path_curvature

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get('RW_LAB_DIR', REPO / 'data/comma2k19'))
CACHE = Path(os.environ.get('RW_LAB_CACHE', REPO / 'runs/lab'))
SEGMENT_ID = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
FPS = 20.0                # comma2k19 video
RADAR_TO_CAMERA = 1.52    # m
RADAR_LAT_M = 1.6         # radar track counted as the lead within this lateral offset (comma load_radar_reference)
CALIB_FRAMES = 300        # pre-pass for the camera angles (comma process_segment calib_frames)
WARMUP = 20               # model frames before its outputs are used (recurrent state)
log = logging.getLogger('roadwatch.lab')


def segment_dir(root, seg_id):
    """Folder of a segment; KeyError for an unknown id or one that would leave the root."""
    if not SEGMENT_ID.match(seg_id) or seg_id in ('.', '..'):
        raise KeyError(seg_id)
    path = Path(root) / seg_id
    if not (path / 'video.mp4').is_file() or path.resolve().parent != Path(root).resolve():
        raise KeyError(seg_id)
    return path


def segments(root=ROOT, cache=CACHE):
    out = []
    for p in sorted(Path(root).iterdir()) if Path(root).is_dir() else []:
        if not (p / 'video.mp4').is_file() or not SEGMENT_ID.match(p.name):
            continue
        ft = p / 'global_pose/frame_times'
        out.append(dict(id=p.name, has_radar=_npy(p / 'processed_log/CAN/radar/t').exists(),
                        has_speed=_npy(p / 'processed_log/CAN/speed/t').exists() or _has_gt_speed(p),
                        frames=len(np.load(_npy(ft))) if _npy(ft).exists() else None,
                        cached=(Path(cache) / p.name / 'result.json').exists()))
    return out


def _npy(path):
    """comma2k19 stores arrays as numpy files without the .npy suffix."""
    return path if path.exists() else path.with_suffix('.npy')


def _load(path):
    return np.load(_npy(path))


def radar_reference(seg):
    """Rough ground truth per video frame: nearest radar track within +-1.6 m laterally (NaN when none)."""
    d = seg / 'processed_log/CAN/radar'
    ft = _load(seg / 'global_pose/frame_times')
    if not _npy(d / 't').exists():
        return np.full(len(ft), np.nan)
    t, v = _load(d / 't'), _load(d / 'value')
    with np.errstate(invalid='ignore'):
        ok = (np.abs(v[:, 1]) < RADAR_LAT_M) & (v[:, 0] > 1) & (v[:, 0] < 200)
    out = np.full(len(ft), np.nan)
    for i, tf in enumerate(ft):
        m = ok & (np.abs(t - tf) < 0.03)
        if m.any():
            out[i] = v[m, 0].min()
    return out


def curvature_reference(seg, total):
    """Real curvature per frame in 1/km (+ = left) from the segment's gt.csv (comma2k19_lane_test: frame, curvature in
    1/m), NaN where there is none."""
    out = np.full(total, np.nan)
    gt = seg / 'gt.csv'
    if gt.is_file():
        for row in csv.DictReader(gt.open(encoding='utf-8')):
            if int(row['frame']) < total:
                out[int(row['frame'])] = 1000 * float(row['curvature'])
    return out


class SpeedLog:
    """The car's CAN speed on the video time axis, used by the pipeline like a synced GPS log (gps.GpsRef)."""
    synced, low_confidence, offset, corr = True, False, 0.0, np.nan

    def __init__(self, seg):
        self.t0 = float(_load(seg / 'global_pose/frame_times')[0])
        self.t = _load(seg / 'processed_log/CAN/speed/t')
        self.v = _load(seg / 'processed_log/CAN/speed/value').ravel()

    def observe(self, pts, v_model):
        pass

    def __call__(self, pts):
        return float(np.interp(self.t0 + pts, self.t, self.v, left=np.nan, right=np.nan))


class GtSpeed:
    """The car's real speed from the segment's gt.csv (comma2k19_lane_test: speed_m_s per frame, from global_pose), for a
    segment without a CAN log; same interface as SpeedLog."""
    synced, low_confidence, offset, corr = True, False, 0.0, np.nan

    def __init__(self, seg):
        rows = list(csv.DictReader((seg / 'gt.csv').open(encoding='utf-8')))
        self.t = np.array([int(r['frame']) / FPS for r in rows])
        self.v = np.array([float(r['speed_m_s']) for r in rows])

    def observe(self, pts, v_model):
        pass

    def __call__(self, pts):
        return float(np.interp(pts, self.t, self.v, left=np.nan, right=np.nan))


def speed_log(seg):
    """The segment's speed log: CAN, else gt.csv's speed_m_s, else None."""
    if _npy(seg / 'processed_log/CAN/speed/t').exists():
        return SpeedLog(seg)
    return GtSpeed(seg) if _has_gt_speed(seg) else None


def _has_gt_speed(seg):
    gt = seg / 'gt.csv'
    return gt.is_file() and 'speed_m_s' in gt.open(encoding='utf-8').readline()


class LeadGate:
    """lead_mask one frame at a time (it only looks back), so the annotated video can use it while it runs."""

    def __init__(self, min_prob=0.5, max_lat=2.0, warmup=WARMUP, exit_ratio=0.5, hold=8):
        self.min_prob, self.max_lat, self.warmup, self.exit_ratio, self.hold = min_prob, max_lat, warmup, exit_ratio, hold
        self.on, self.miss = False, 0

    def __call__(self, i, x, y, p):
        ok = x > 0 and i >= self.warmup
        enter = ok and p >= self.min_prob and abs(y) <= self.max_lat
        stay = ok and p >= self.min_prob * self.exit_ratio and abs(y) <= self.max_lat * 1.25
        if enter or (self.on and stay):
            self.on, self.miss = True, 0
        elif self.on:
            self.miss += 1
            self.on = self.miss <= self.hold
        return self.on


def lead_mask(lead_x, lead_y, lead_prob, min_prob=0.5, max_lat=2.0, warmup=WARMUP, exit_ratio=0.5, hold=8):
    """Same-lane lead presence per frame with hysteresis (comma lead_distance.lead_mask; the page has a JS copy).

    A lead is acquired at p >= min_prob; once tracked it is kept while p >= exit_ratio * min_prob and
    |y| <= 1.25 * max_lat, and short drop-outs (<= `hold` frames) are bridged."""
    gate = LeadGate(min_prob, max_lat, warmup, exit_ratio, hold)
    return np.array([gate(i, *a) for i, a in enumerate(zip(lead_x, lead_y, lead_prob, strict=True))], bool)


def estimate_calibration(video, w, h, fy, model, wide='dup', n_frames=CALIB_FRAMES, progress=None, stop=None, live=None):
    """Camera angles over the first frames (comma lead_distance.estimate_calibration): AutoCalib with roll and pitch
    left out of the warp, since on comma2k19 correcting pitch made the distances worse vs radar while yaw fixes the
    sideways offset of the lead and lane. Returns (applied: 0, 0, yaw; estimated: roll, pitch, yaw), zeros when the
    angles did not settle. `live(jpeg, est_deg, settled)` gets every decoded frame and the angles estimated so far."""
    k, cal = intrinsics(fy, w, h), AutoCalib(use_pitch=False, use_roll=False)
    warps = warp_matrices(k, cal.rpy, w, wide)
    model.reset()
    for i, (y, u, v) in enumerate(decode(video, w, h, n_frames, FPS)):
        if stop is not None and stop.is_set():
            raise InterruptedError
        p = model.step(pack_frame(y, u, v, warps))
        if i >= WARMUP and cal.update(p['pose'][0], p['road_transform'][0], p['road_transform_stds'][0]):
            cal.warp_rpy = cal.rpy
            warps = warp_matrices(k, cal.rpy, w, wide)
        if progress:
            progress(i + 1)
        if live:
            bgr = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_I420)
            live(cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes(),
                 [round(float(a), 3) for a in np.degrees(cal.est)], bool(cal.settled))
    if not cal.settled:
        return np.zeros(3), np.zeros(3)
    return cal.rpy.copy(), cal.est.copy()


def _curvatures(r):
    """The ego yaw curvature and the drawn path's, in 1/km, + = left (the pipeline's + = right, flipped)."""
    drawn = path_curvature(r.outputs, r.curvature, r.ego_speed_mps, r.straddle)
    return dict(curv_yaw=None if r.curvature is None else -1000 * r.curvature,
                curv_drawn=None if drawn is None else -1000 * drawn)


def _num(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


COLUMNS = ('t_s', 'lead_x_m', 'lead_y_m', 'lead_prob', 'lead_std_m', 'gap_kalman_m', 'ego_model_mps', 'ego_log_mps',
           'radar_m', 'curv_gt', 'curv_yaw', 'curv_drawn')   # the last three: curvature in 1/km, + = left


def run(seg, cache=CACHE, model=None, bumper=RADAR_TO_CAMERA, fy=910.0, use_log=True, progress=None, stop=None,
        live=None, wide='dup', calib_frames=CALIB_FRAMES, calib_live=None):
    """BT-A over the whole segment -> cache/<id>/result.json (per frame) + annotated.mp4.
    `live(jpeg, cols)` gets every annotated frame and the columns so far (appended to in place) while it runs;
    `calib_live(jpeg, est_deg, settled)` gets every raw frame of the calibration pre-pass with the angles so far.
    `progress(done, total, calib)` counts the `calib` frames of the calibration pre-pass, then the segment's."""
    w, h = video_size(seg / 'video.mp4')
    radar = radar_reference(seg)
    total = len(radar)
    curv_gt = curvature_reference(seg, total)
    speed = speed_log(seg)
    model = model or Gr14VinAI()
    n_calib = min(calib_frames, total)
    rpy, rpy_est = estimate_calibration(seg / 'video.mp4', w, h, fy, model, wide, n_calib,
                                        progress and (lambda i: progress(i, n_calib + total, n_calib)), stop, live=calib_live) \
        if n_calib else (np.zeros(3), np.zeros(3))
    pipe = Pipeline(w, h, fy, bumper, model, v_ref=speed if use_log else None, wide=wide, rpy=rpy, rpy_est=rpy_est)
    gate, lane = LeadGate(), LaneSmoother()
    out = Path(cache) / seg.name
    out.mkdir(parents=True, exist_ok=True)
    part = out / 'annotated.part.mp4'
    writer = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}',
                               '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                               '-movflags', '+faststart', '-f', 'mp4', str(part)], stdin=subprocess.PIPE)
    cols = {k: [] for k in COLUMNS}
    if live:
        live(None, cols)
    try:
        for i, (y, u, v) in enumerate(decode(seg / 'video.mp4', w, h, fps=FPS)):
            if stop is not None and stop.is_set():
                raise InterruptedError
            t = i / FPS
            r = pipe.step(y, u, v, t)
            p = r.outputs
            x, ly = (float(a) for a in p['lead'][0, 0, 0, :2])
            prob, std = float(p['lead_prob'][0, 0]), float(p['lead_stds'][0, 0, 0, 0])
            pose = p.get('pose')
            row = dict(t_s=t, lead_x_m=x, lead_y_m=ly, lead_prob=prob, lead_std_m=std,
                       gap_kalman_m=r.gap_m if r.gap_m is not None else np.nan,
                       ego_model_mps=float(pose[0, 0]) if pose is not None else r.ego_speed_mps,
                       ego_log_mps=speed(t) if speed is not None else np.nan,
                       radar_m=radar[i] if i < total else np.nan, curv_gt=curv_gt[i] if i < total else np.nan,
                       **_curvatures(r))
            for k, val in row.items():
                cols[k].append(_num(val))
            bgr = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                               cv2.COLOR_YUV2BGR_I420)
            # app.py draw_frame: the raw lead, not the Kalman track; no TTC. Its gate is comma's (|y| <= 2 m from the camera
            # axis, so a car in our lane on a curve is dropped): the lead BT-A found by following the lane counts too
            has = gate(i, x, ly, prob) or (r.gap_m is not None and i >= WARMUP)   # not while the model warms up
            shown = replace(r, gap_m=x - bumper if has else None, lead_x_m=x, lead_lat_m=ly,
                            gap_std_m=std if has else None, ttc_s=None)
            lane.update(shown)   # the drawn lane eases between ticks instead of jumping
            shown = draw(bgr, pipe.K, shown, fy, radar_ref=row['radar_m'], debug=False, lane=lane)
            writer.stdin.write(shown.tobytes())
            if live:
                live(cv2.imencode('.jpg', shown, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes(), cols)
            if progress:
                progress(n_calib + i + 1, n_calib + total, n_calib)
        writer.stdin.close()
        if writer.wait():
            raise RuntimeError(f'ffmpeg ghi video lỗi (mã {writer.returncode})')
    finally:
        if writer.poll() is None:
            writer.kill()
    part.replace(out / 'annotated.mp4')
    res = dict(segment=seg.name, frames=len(cols['t_s']), fps=FPS, bumper_m=bumper, fy_px=fy, use_log=use_log,
               wide=wide, rpy_deg=np.degrees(rpy_est).round(2).tolist(),
               rpy_applied_deg=np.degrees(rpy).round(2).tolist(), created_unix=time.time(), **cols)
    tmp = out / 'result.json.tmp'
    tmp.write_text(json.dumps(res))
    tmp.replace(out / 'result.json')
    return res


class Lab:
    """One lab run at a time, in a background thread, beside the demo job."""

    def __init__(self, root=ROOT, cache=CACHE):
        self.root, self.cache = Path(root), Path(cache)
        self.lock, self.stop, self.thread, self.model = threading.Lock(), threading.Event(), None, None
        self.status = dict(state='idle', segment=None, done=0, total=0, calib_frames=0, calib_rpy_deg=None, calib_settled=False, error=None)
        self.jpeg, self.cols, self.seg_id = None, None, None   # newest annotated frame and columns of the running segment

    def segments(self):
        return segments(self.root, self.cache)

    def start(self, seg_id, bumper, fy, use_log, wide='dup'):
        seg = segment_dir(self.root, seg_id)
        with self.lock:
            if self.status['state'] == 'running':
                raise RuntimeError('đang chạy một segment khác')
            self.status = dict(state='running', segment=seg_id, done=0, total=0, calib_frames=0, calib_rpy_deg=None,
                               calib_settled=False, error=None)
        self.jpeg, self.cols, self.seg_id = None, None, seg_id
        self.stop.clear()
        self.thread = threading.Thread(target=self._run, args=(seg, bumper, fy, use_log, wide), daemon=True)
        self.thread.start()

    def _live(self, jpeg, cols):
        self.cols = cols
        if jpeg is not None:
            self.jpeg = jpeg

    def live(self, since=0):
        """Columns from frame `since` on, for the page's charts while a segment runs (only whole frames)."""
        cols, since = self.cols, max(0, since)
        n = min(len(c) for c in cols.values()) if cols else 0
        return dict(segment=self.seg_id, running=self.status['state'] == 'running', start=since, frames=n,
                    total=self.status['total'] - self.status.get('calib_frames', 0), fps=FPS,
                    **{k: (cols[k][since:n] if cols else []) for k in COLUMNS})

    def _calib_live(self, jpeg, est_deg, settled):
        self.jpeg = jpeg
        with self.lock:
            self.status.update(calib_rpy_deg=est_deg, calib_settled=settled)

    def _progress(self, done, total, calib=0):
        with self.lock:
            self.status.update(done=done, total=total, calib_frames=calib)

    def _run(self, seg, bumper, fy, use_log, wide='dup'):
        try:
            self.model = self.model or Gr14VinAI()
            self.model.reset()
            run(seg, self.cache, self.model, bumper, fy, use_log, self._progress, self.stop, self._live, wide, calib_live=self._calib_live)
            state, error = 'done', None
        except InterruptedError:
            state, error = 'stopped', None
        except Exception as e:   # shown on the page; the server keeps running
            log.exception('lab run on %s failed', seg.name)
            state, error = 'failed', str(e)
        with self.lock:
            self.status.update(state=state, error=error)
