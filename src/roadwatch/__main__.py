"""python -m src.roadwatch VIDEO --fps 20 --d-cam-bumper 1.5 [lens] [--gps LOG] [--out out.mp4] [--show] ...

Like comma_ai realtime_lead.py: bars cropped (--crop), the model fed at a constant tick close to 20 Hz (every n-th frame,
or neighbouring frames blended to exact 20 Hz: --resample blend), every frame drawn with the latest result and written
at the video's frame rate. Lens: --fy (px), --focal-mm (35 mm-equivalent unless --sensor-width-mm), or --hfov
(+ --lens fisheye); one of them is required unless --learn-fy asks to learn fy from the video (RoadWatch). --gps gives the ego speed (+ --auto-focal);
--prepass calibrates on the first seconds before the run; --show opens a window paced to real time
(q / Esc quit, space pause; needs an OpenCV build with GUI). --limit counts video frames."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import gps as gpslib
from .calibration import LEARN_FRAMES, LEARN_SKIP, AutoCalib, FocalFromSpeed, intrinsics, learn_fy
from .hud import draw
from .job import FY_GUESS_FRAC, Options, _flags, _hud_text, camera_box, given_focal
from .model import Gr14VinAI, decode, model_ticks, pack_frame, resample_tick, tick, warp_matrices
from .pipeline import Pipeline

WARMUP = 20   # model ticks before its outputs are used (recurrent state)


def prepass(model, video, box, fps, fy, cal, seconds, resample='stride', wide='auto', gps=None, fit_focal=False,
            max_iter=4):
    """realtime_lead VideoLeadPipeline._prepass: learn the camera angles over the first `seconds`; with fit_focal,
    also sync the GPS log (first pass) and refit fy to the GPS speed, up to max_iter passes. Returns (fy, cal)."""
    w, h = box[2:]
    tick_dt, vel_scale = resample_tick(fps, resample)
    for it in range(max_iter if fit_focal else 1):
        k = intrinsics(fy, w, h)
        warps = warp_matrices(k, cal.rpy, w, wide)
        model.reset()
        ts, vs, n = [], [], 0
        frames = decode(video, w, h, int(seconds * fps) + 1, fps, box)
        for _, pts, _, ticks in model_ticks(frames, fps, tick_dt, resample == 'blend'):
            for planes in ticks:
                p = model.step(pack_frame(*planes, warps))
                pose = p['pose'][0] * vel_scale
                if n >= WARMUP:
                    if cal.update(pose, p['road_transform'][0], p['road_transform_stds'][0]):
                        cal.warp_rpy = cal.rpy
                        warps = warp_matrices(k, cal.rpy, w, wide)
                    ts.append(pts)
                    vs.append(float(pose[0]))
                n += 1
        if not fit_focal:
            break
        ts, vs = np.array(ts), np.array(vs)
        if it == 0 and not gps.synced:
            off, corr = gpslib.align_offset(gps.t, gps.v, ts, vs)
            gps.corr, gps.synced = corr, True
            if corr >= gpslib.GpsRef.MIN_CORR:
                gps.offset = off
            else:
                gps.low_confidence = True
        v_gps = gpslib.speed_at(gps.t, gps.v, ts, gps.offset)
        m = np.isfinite(v_gps) & (v_gps > FocalFromSpeed.MIN_SPEED) & (vs > 1)
        if m.sum() < 40:
            break
        ratio = float(np.median(vs[m] / v_gps[m]))
        fy /= np.clip(ratio, 1 / 1.6, 1.6)
        if abs(np.log(ratio)) < FocalFromSpeed.SETTLED_REL:
            break
    cal.n = max(cal.n, AutoCalib.SETTLED_SAMPLES)
    return float(fy), cal


def _crop(value):
    if value in ('auto', 'full', 'none'):
        return 'full' if value == 'none' else value
    return tuple(int(v) for v in value.split(','))


def main():
    ap = argparse.ArgumentParser(description='Dashcam -> auto-calibration -> gr14VinAI -> lead gap video.')
    ap.add_argument('video')
    ap.add_argument('--fps', type=float, required=True, help='true capture rate (container fps is often wrong)')
    ap.add_argument('--d-cam-bumper', '--bumper', type=float, required=True, help='camera to front bumper, metres')
    ap.add_argument('--fy', '--focal', type=float, help='focal length in px of the camera picture')
    ap.add_argument('--learn-fy', action='store_true', help='learn the focal length from the video (off by default)')
    ap.add_argument('--focal-mm', type=float, help='focal length in mm: 35 mm-equivalent (phones, e.g. 26), or the '
                                                    'real focal length when --sensor-width-mm is given')
    ap.add_argument('--sensor-width-mm', type=float, help='sensor long side in mm, for a real (not equivalent) --focal-mm')
    ap.add_argument('--hfov', type=float, help='horizontal field of view (deg) of the camera picture')
    ap.add_argument('--lens', choices=['pinhole', 'fisheye'], default='pinhole',
                    help='fisheye: wide-angle dashcam lens (equidistant model) for --hfov')
    ap.add_argument('--gps', type=Path, help='GPS log (GPX / NMEA / CSV): ego speed (+ --auto-focal)')
    ap.add_argument('--gps-offset', default='auto', help="'auto' or seconds: GPS time at video t=0, from the first fix")
    ap.add_argument('--auto-focal', action='store_true',
                    help='experimental: fit the focal length from the GPS speed instead of the lens settings')
    ap.add_argument('--crop', default='auto', help="'auto', 'none' or x,y,w,h of the camera picture")
    ap.add_argument('--no-pitch', action='store_true', help='estimate but do not apply the pitch angle')
    ap.add_argument('--wide', choices=['auto', 'dup', 'warp'], default='auto',
                    help='model wide-camera input: warp the same picture with the wide virtual camera, or duplicate')
    ap.add_argument('--resample', choices=['auto', 'stride', 'blend'], default='auto',
                    help='feed a non-20-fps video every n-th frame (auto; velocities rescaled) or blend neighbouring '
                         'frames to exact 20 Hz')
    ap.add_argument('--prepass', type=float, default=0.,
                    help='calibration pre-pass in seconds before the run (default 0 = calibrate online)')
    ap.add_argument('--out', help='annotated video (default: <video>.roadwatch.mp4)')
    ap.add_argument('--csv', type=Path, help='write per-model-tick results here (realtime_lead CSV)')
    ap.add_argument('--show', action='store_true', help='window paced to real time (q / Esc quit, space pause)')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    if a.show:
        try:
            cv2.namedWindow('lead distance', cv2.WINDOW_NORMAL)
        except cv2.error:
            ap.error('--show needs an OpenCV build with GUI (requirements.txt installs opencv-python-headless)')

    box = camera_box(a.video, _crop(a.crop))   # w, h = camera picture
    w, h = box[2:]
    stride, _, learn_scale = tick(a.fps)
    resample = 'stride' if a.resample == 'auto' else a.resample
    tick_dt, _ = resample_tick(a.fps, resample)
    use_pitch = not a.no_pitch
    out = Path(a.out or Path(a.video).with_suffix('.roadwatch.mp4'))
    model = Gr14VinAI()
    opts = Options(lens='learn' if a.learn_fy else 'fov' if a.hfov and not a.focal_mm else 'mm', f_mm=a.focal_mm,
                   sensor_mm=a.sensor_width_mm, hfov_deg=a.hfov, fisheye=a.lens == 'fisheye', gps=a.gps,
                   auto_focal=a.auto_focal, use_pitch=use_pitch)
    gps = gpslib.GpsRef(*gpslib.load_gps(a.gps), a.gps_offset if a.gps_offset == 'auto' else float(a.gps_offset)) \
        if a.gps else None
    fit_focal = a.auto_focal and gps is not None

    t0, table = time.perf_counter(), []
    try:
        fy, fy_how = given_focal(a.fy, opts, w, h)
    except ValueError as e:
        ap.error(str(e).replace('nhập tiêu cự pixel, tiêu cự mm hoặc góc nhìn ngang', 'give --fy, --focal-mm or --hfov or --learn-fy'))
    if fy is None and fit_focal:
        fy, fy_how = FY_GUESS_FRAC * w, 'GPS'
    elif fy is None:
        n = (LEARN_SKIP + LEARN_FRAMES) * stride
        frames = [f for i, f in enumerate(decode(a.video, w, h, n, a.fps, box)) if i % stride == 0][LEARN_SKIP:]
        fy, table = learn_fy(frames, w, h, model, vel_scale=learn_scale)
        fy_how = 'learned'
    cal = AutoCalib(use_pitch=use_pitch)
    if a.prepass > 0:
        fy, cal = prepass(model, a.video, box, a.fps, fy, cal, a.prepass, resample, a.wide, gps, fit_focal)
    print(f'fy={fy:.1f}px ({fy_how}, {time.perf_counter() - t0:.0f}s)', flush=True)

    focal = FocalFromSpeed(fy) if fit_focal else None
    if focal is not None and a.prepass > 0:
        focal.settled = True   # the pre-pass already fitted it; keep refining slowly
    pipe = Pipeline(w, h, fy, a.d_cam_bumper, model, tick_dt, v_ref=gps, focal=focal, use_pitch=use_pitch,
                    wide=a.wide, cal=cal)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*'mp4v'), a.fps, (w, h))
    log, ms, r, late = [], [], None, 0
    t_wall0 = time.perf_counter()
    frames = decode(a.video, w, h, a.limit, a.fps, box)
    for _, pts, (y, u, v), ticks in model_ticks(frames, a.fps, tick_dt, resample == 'blend'):
        for planes in ticks:   # every frame is drawn with the latest result
            t = time.perf_counter()
            r = pipe.step(*planes, pts)
            ms.append(1000 * (time.perf_counter() - t))
            log.append(dict(t_s=pts, status=r.status, pitch=r.rpy[1], yaw=r.rpy[2], height_m=r.height_m,
                            ego_mps=r.ego_speed_mps, lead_prob=r.lead_prob, gap_m=r.gap_m, ttc_s=r.ttc_s))
        frame = cv2.cvtColor(np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(h * 3 // 2, w),
                             cv2.COLOR_YUV2BGR_I420)
        if r is not None:
            frame = draw(frame, pipe.K, r, r.fy_px, *_hud_text(r, gps, focal, _flags(opts, gps, focal), use_pitch))
        writer.write(frame)
        if a.show:
            wait = t_wall0 + pts + 1 / a.fps - time.perf_counter()   # keep video time == wall time
            if wait > -2 / a.fps:   # skip showing frames we are already late for
                cv2.imshow('lead distance', frame)
            else:
                late += 1
            key = cv2.waitKey(max(1, int(wait * 1e3))) & 0xFF
            if key in (ord('q'), 27):
                break
            if key == ord(' '):
                t_pause = time.perf_counter()
                while (cv2.waitKey(50) & 0xFF) not in (ord(' '), ord('q'), 27):
                    pass
                t_wall0 += time.perf_counter() - t_pause
    writer.release()
    if a.show:
        cv2.destroyAllWindows()
    if a.csv:
        a.csv.parent.mkdir(parents=True, exist_ok=True)
        pipe.save_csv(a.csv)
    summary = dict(video=a.video, crop=box, ticks=len(log), tick_hz=1 / tick_dt, resample=resample, fy=float(pipe.K[0, 0]),
                   fy_how=fy_how, fy_sweep=table, final_rpy=pipe.rpy.tolist(), est_rpy=pipe.cal.est.tolist(),
                   height_m=log[-1]['height_m'] if log else None, calibration_resets=pipe.cal.resets,
                   coverage=pipe.coverage, gps_offset_s=gps.offset if gps is not None and gps.synced else None,
                   flags=_flags(opts, gps, focal), late_frames=late,
                   pipeline_ms_median=float(np.median(ms)) if ms else None,
                   pipeline_ms_p95=float(np.percentile(ms, 95)) if ms else None, out=str(out))
    out.with_suffix('.json').write_text(json.dumps(dict(summary=summary, frames=log), indent=1, default=float))
    print(json.dumps({k: v for k, v in summary.items() if k != 'fy_sweep'}, indent=1, default=float))


if __name__ == '__main__':
    main()
