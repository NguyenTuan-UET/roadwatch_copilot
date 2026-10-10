"""Draw an openpilot-style HUD on a BGR frame, ported from comma_ai/lead_distance/overlay.py (copied, not imported:
it is another repo): ego-lane carpet, lead chevron on the lane surface under the lead, distance panel (top left),
calibration box (top right) and the estimated horizon. Differences: any camera (cam_k) instead of the EON one;
the fallback lane around the planned path is raised by the camera height (the plan starts at the camera, z = 0),
and the panel also shows TTC."""
from functools import cache

import cv2
import numpy as np
from g01T014VinAI.common.transformations.camera import view_frame_from_device_frame
from g01T014VinAI.common.transformations.orientation import rot_from_euler
from g01T014VinAI.selfdrive.modeld.constants import ModelConstants
from PIL import Image, ImageDraw, ImageFont

X_IDXS = np.array(ModelConstants.X_IDXS)
LANE_BGR = np.array([70, 205, 60], np.float32)      # green carpet
PATH_BGR = np.array([150, 235, 140], np.float32)    # lighter centre band
EDGE_BGR = (90, 235, 80)
LEAD_BGR = (0, 210, 255)                            # yellow chevron
CLOSE_BGR = (40, 40, 230)                           # red when time gap < CLOSE_HEADWAY_S
HORIZON_BGR = (0, 200, 255)
CLOSE_HEADWAY_S = 1.0
LANE_X_MIN, LANE_X_MAX = 6.0, 80.0                  # metres of ego lane drawn when no lead
LANE_PROB = 0.4
FALLBACK_HALF_WIDTH = 1.75                          # m, used when lane lines are not confident
FONT_DIR = '/usr/share/fonts/truetype/dejavu/'        # DejaVu has the Vietnamese glyphs


def project(cam_k, rpy, pts):
    """Calibrated device-frame points (x forward, y right, z down; origin at camera) -> pixels."""
    uvw = cam_k @ view_frame_from_device_frame @ rot_from_euler(rpy) @ np.asarray(pts, float).T
    with np.errstate(divide='ignore', invalid='ignore'):
        return (uvw[:2] / uvw[2]).T, uvw[2] > 0


def _blend_strips(img, left_px, right_px, color, alpha_near, alpha_far):
    """Fill the band between two projected polylines, fading out with distance (only its bounding box is blended)."""
    h, w = img.shape[:2]
    pts = np.vstack([left_px, right_px])
    x0, y0 = np.clip(np.floor(pts.min(axis=0)).astype(int) - 2, 0, [w, h])
    x1, y1 = np.clip(np.ceil(pts.max(axis=0)).astype(int) + 2, 0, [w, h])
    if x1 <= x0 or y1 <= y0:
        return
    mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    n = len(left_px) - 1
    off = np.array([x0, y0])
    for j in range(n):
        quad = (np.array([left_px[j], left_px[j + 1], right_px[j + 1], right_px[j]]) - off).astype(np.int32)
        a = alpha_near + (alpha_far - alpha_near) * j / max(n - 1, 1)
        cv2.fillPoly(mask, [quad], int(round(a * 255)), lineType=cv2.LINE_AA)
    roi = img[y0:y1, x0:x1]
    m = mask[..., None].astype(np.float32) * (1 / 255)
    roi[:] = (roi * (1 - m) + color * m).astype(np.uint8)


def ego_lane_borders(lanes, lane_prob, plan_pos, x_end, height):
    """Left/right ego-lane border (y, z) sampled on a fine x grid in front of the car. Without confident lane
    lines: a nominal lane around the planned path (plan_pos: x, y, z from the camera, so + camera height to be
    on the road), or on the camera axis when the model has no plan head."""
    xs = np.linspace(LANE_X_MIN, max(LANE_X_MIN + 1, x_end), 40)
    if min(lane_prob) >= LANE_PROB:
        yl, yr = (np.interp(xs, X_IDXS, lanes[k, :, 0]) for k in (1, 2))
        zl, zr = (np.interp(xs, X_IDXS, lanes[k, :, 1]) for k in (1, 2))
        return xs, (yl, zl), (yr, zr)
    if plan_pos is None:
        yc, zc = np.zeros_like(xs), np.full_like(xs, height)
    else:
        yc = np.interp(xs, plan_pos[:, 0], plan_pos[:, 1])
        zc = np.interp(xs, plan_pos[:, 0], plan_pos[:, 2]) + height
    return xs, (yc - FALLBACK_HALF_WIDTH, zc), (yc + FALLBACK_HALF_WIDTH, zc)


def draw_lane(img, cam_k, rpy, borders):
    """Green carpet between the ego-lane borders, up to the lead (or 80 m), fading with distance."""
    xs, (yl, zl), (yr, zr) = borders

    def proj(y, z):
        return project(cam_k, rpy, np.c_[xs, y, z])[0]
    lp, rp = proj(yl, zl), proj(yr, zr)
    h, w = img.shape[:2]
    if not (np.isfinite(lp).all() and np.isfinite(rp).all()) or np.abs(np.r_[lp, rp]).max() > 4 * max(h, w):
        return
    _blend_strips(img, lp, rp, LANE_BGR, 0.38, 0.08)
    yc, zc, hw = (yl + yr) / 2, (zl + zr) / 2, (yr - yl) * 0.2   # lighter centre band (~40% of lane width)
    _blend_strips(img, proj(yc - hw, zc), proj(yc + hw, zc), PATH_BGR, 0.3, 0.05)
    for px in (lp, rp):
        cv2.polylines(img, [px.astype(np.int32)], False, EDGE_BGR, max(2, round(3 * w / 1164)), cv2.LINE_AA)


def draw_chevron(img, u, v, dist, color):
    sz = float(np.clip(25 * 30 / (dist / 3 + 30), 15, 30)) * 1.4 * img.shape[1] / 1164
    tri = np.array([[u, v - sz * 0.35], [u + sz * 1.1, v + sz * 0.65], [u - sz * 1.1, v + sz * 0.65]], np.int32)
    glow = np.array([[u, v - sz * 0.6], [u + sz * 1.45, v + sz * 0.85], [u - sz * 1.45, v + sz * 0.85]], np.int32)
    layer = img.copy()
    cv2.fillPoly(layer, [glow], (40, 40, 40), cv2.LINE_AA)
    cv2.addWeighted(layer, 0.45, img, 0.55, 0, dst=img)
    cv2.fillPoly(img, [tri], color, cv2.LINE_AA)


def draw_horizon(img, cam_k, rpy):
    """Road-plane directions at infinity for the estimated angles: should lie on the real horizon."""
    far = 1e5
    (a, b), ok = project(cam_k, rpy, [[far, -far / 2, 0.], [far, far / 2, 0.]])
    if not ok.all():
        return
    slope = (b[1] - a[1]) / (b[0] - a[0])
    w = img.shape[1]
    p0, p1 = (0, int(a[1] - slope * a[0])), (w, int(a[1] + slope * (w - a[0])))
    s, t = w / 1164, max(1, round(2 * w / 1164))
    cv2.line(img, p0, p1, HORIZON_BGR, t, cv2.LINE_AA)
    cv2.putText(img, 'horizon', (int(10 * s), p0[1] - int(8 * s)), cv2.FONT_HERSHEY_SIMPLEX, 0.7 * s, HORIZON_BGR, t,
                cv2.LINE_AA)


@cache
def _font(size: int, bold: bool = True):
    try:
        return ImageFont.truetype(FONT_DIR + ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)
    except OSError:
        return ImageFont.load_default(size)


def draw_panel(img, gap, gap_std, v_ego, ttc, close, note=None, radar_ref=None):
    """Top-left rounded panel: big distance from the bumper with its uncertainty, ego speed, TTC (+ note or the
    radar reference distance below)."""
    h, w = img.shape[:2]
    s = max(w, h) / 1164
    x0, y0, pw, ph = int(18 * s), int(18 * s), int(330 * s), int(150 * s)
    # only the top-left region is composited (PIL on the full frame costs several ms)
    roi = img[:min(h, y0 + ph + int(45 * s)), :min(w, max(x0 + pw + int(10 * s), int(560 * s)))]
    pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)).convert('RGBA')
    layer = Image.new('RGBA', pil.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=int(18 * s), fill=(25, 25, 25, 185))
    big, small = _font(int(78 * s)), _font(int(30 * s))
    red, white = (255, 90, 80, 255), (235, 235, 235, 255)
    if gap is None:
        d.text((x0 + 22 * s, y0 + 10 * s), '--', font=big, fill=(200, 200, 200, 255))
        d.text((x0 + 120 * s, y0 + 50 * s), 'Không có xe', font=_font(int(24 * s), False), fill=(200, 200, 200, 255))
    else:
        txt = f'{gap:.0f}'
        d.text((x0 + 22 * s, y0 + 6 * s), txt, font=big, fill=red if close else (120, 240, 110, 255))
        tx = x0 + 22 * s + d.textlength(txt, font=big) + 8 * s
        std = f' ± {max(gap_std, 0.5):.0f}' if gap_std is not None else ''
        d.text((tx, y0 + 46 * s), 'm' + std, font=small, fill=white)
    if v_ego is not None and np.isfinite(v_ego):
        d.text((x0 + 26 * s, y0 + 102 * s), f'{v_ego * 3.6:.0f} km/h', font=small, fill=white)
    if ttc is not None:
        d.text((x0 + 170 * s, y0 + 102 * s), f'TTC {ttc:.1f} s', font=small, fill=red if close else white)
    if radar_ref is not None and np.isfinite(radar_ref):
        d.text((x0 + 6 * s, y0 + ph + 8 * s), f'radar: {radar_ref:.1f} m', font=_font(int(20 * s), False),
               fill=(255, 200, 80, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    if note:
        d.text((x0 + 6 * s, y0 + ph + 8 * s), note, font=_font(int(20 * s), False),
               fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    out = Image.alpha_composite(pil, layer).convert('RGB')
    roi[:] = cv2.cvtColor(np.asarray(out), cv2.COLOR_RGB2BGR)


def draw_debug(img, lines):
    """Small top-right info box (calibration state)."""
    s = max(img.shape[1] / 1164, 0.6)
    fs, lh = 0.5 * s, int(20 * s)
    w = int(max(cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)[0][0] for t in lines) + 16)
    x0, y0 = img.shape[1] - w - int(12 * s), int(12 * s)
    roi = img[y0:y0 + lh * len(lines) + 10, max(x0, 0):x0 + w]
    roi[:] = (roi * 0.35).astype(np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(img, t, (x0 + 8, y0 + lh * (i + 1)), cv2.FONT_HERSHEY_SIMPLEX, fs, (235, 235, 235), 1, cv2.LINE_AA)


def draw(frame, cam_k, r, fy, note=None, gps_line=None, use_pitch=True, radar_ref=None, debug=True):
    """note: shown under the panel once the angles have settled (GPS sync / focal fit); gps_line: GPS state
    in the calibration box, as comma realtime_lead renders them. radar_ref and debug=False: comma lead_distance
    app.py (overlay.draw_frame), which shows the radar distance and has no calibration box."""
    p = r.outputs
    est = r.rpy if r.rpy_est is None else r.rpy_est
    draw_horizon(frame, cam_k, est)
    has = r.gap_m is not None
    x, lat = (r.lead_x_m, r.lead_lat_m) if has else (LANE_X_MAX, 0.)   # filtered, like realtime_lead
    close = has and np.isfinite(r.ego_speed_mps) and r.ego_speed_mps > 1 \
        and r.gap_m / r.ego_speed_mps < CLOSE_HEADWAY_S
    plan_pos = p['plan'][0, :, :3] if 'plan' in p else None   # absent from a model pruned before plan was kept
    borders = ego_lane_borders(p['lane_lines'][0], p['lane_lines_prob'][0, 1::2][1:3], plan_pos,
                               x, r.height_m)
    draw_lane(frame, cam_k, r.rpy, borders)
    if has:
        xs, (_, zl), (_, zr) = borders
        z = float(np.interp(x, xs, (zl + zr) / 2))   # lane surface under the lead, like the carpet's far edge
        ((u, v),), ok = project(cam_k, r.rpy, [[x, lat, z]])
        if ok[0] and 0 <= u < frame.shape[1] and 0 <= v < frame.shape[0]:
            draw_chevron(frame, u, v, x, CLOSE_BGR if close else LEAD_BGR)
    if debug:
        deg = np.degrees(est)
        hfov = np.degrees(2 * np.arctan(frame.shape[1] / 2 / cam_k[0, 0]))
        draw_debug(frame, [f'pitch {deg[1]:+.2f} yaw {deg[2]:+.2f} roll {deg[0]:+.2f} deg' + ('' if use_pitch else ' (pitch off)'),
                           f'f {fy:.0f}px  hfov {hfov:.0f} deg  {r.status.upper() if r.status == "calibrated" else r.status}',
                           *([gps_line] if gps_line else []),
                           f'h {r.height_m:.2f} m  lead p={r.lead_prob:.2f}'])
    if r.status.startswith('calibrating'):
        note = f'Đang hiệu chỉnh góc camera... {r.status.split()[-1]}'
    draw_panel(frame, r.gap_m, r.gap_std_m, r.ego_speed_mps, r.ttc_s, close, note, radar_ref)
    return frame
