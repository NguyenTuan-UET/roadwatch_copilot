"""Draw a HUD on a BGR frame, ported from comma_ai/lead_distance/overlay.py (copied, not imported:
it is another repo): ego-lane carpet, lead chevron on the lane surface under the lead, distance panel (top left),
calibration box (top right); no horizon line. Differences: any camera (cam_k) instead of the EON one;
the fallback lane around the planned path is raised by the camera height (the plan starts at the camera, z = 0),
the planned path is predicted here (the pruned model has no plan head): from the car it eases into the ego-lane
centre and follows the road, or follows the ego motion without lane lines (pipeline.predicted_path), and the
lighter centre band follows it, and the panel also shows TTC."""
from functools import cache

import cv2
import numpy as np
from g01T014VinAI.common.transformations.camera import view_frame_from_device_frame
from g01T014VinAI.common.transformations.orientation import rot_from_euler
from g01T014VinAI.selfdrive.modeld.constants import ModelConstants
from PIL import Image, ImageDraw, ImageFont

from .pipeline import EDGE_CLIP_STD, LANE_BAND, LANE_WIDTH, path_reach, predicted_path, widen_lane

X_IDXS = np.array(ModelConstants.X_IDXS)
LANE_BGR = np.array([150, 172, 64], np.float32)     # teal carpet
PATH_BGR = np.array([232, 248, 225], np.float32)    # near-white centre band along the predicted path
EDGE_BGR = (170, 235, 90)                           # bright teal border lines
LEAD_BGR = (0, 210, 255)                            # yellow chevron
CLOSE_BGR = (40, 40, 230)                           # red when time gap < CLOSE_HEADWAY_S
CLOSE_HEADWAY_S = 1.0
LANE_X_MIN, LANE_X_MAX = 2.0, 80.0                  # metres of ego lane drawn (from under the bonnet: down to the
                                                    # picture's bottom edge) when no lead
LANE_PROB = 0.4
FALLBACK_HALF_WIDTH = 1.75                          # m, used when lane lines are not confident
LANE_MAX_WIDTH = 6.0                                # m per lane: a road edge farther than this is not the border
EDGE_STD_MAX = 1.5                                  # m: a road edge less certain than this (near the car) is not a
                                                    # border; up to pipeline.EDGE_CLIP_STD it still bounds the lane
LANE_MIN_WIDTH = 1.5                                # m: a lane squeezed by a road edge keeps this width
EDGE_NEAR_X = 5.0                                   # m: where a road edge is checked to be next to the car's lane
GRID = np.arange(LANE_X_MIN, LANE_X_MAX + .5, 1.0)  # x of the lane geometry before it is cut at the lead (1 m apart)
LANE_PROB_OFF = 0.25                                # a lane line that was confident stays so down to this (hysteresis)
MEDIAN_TICKS = 3                                    # the lane is the median of this many ticks, then eased (no twitching)
FIT_DEGREE = 3                                      # borders and path are drawn as smooth polynomials in x
TURN_AWAY = 1.0                                     # a border or path steeper than 45 deg (turning away behind a
                                                    # bend, or jumping): the carpet stops a grid step before
LANE_END_MIN = 10.0                                 # m: the carpet is never cut shorter than this
LANE_EMA = 0.25                                     # per model tick: the drawn lane eases to the new one (~0.2 s)
END_EMA = 0.2                                       # same for the carpet's far end (collapse to a lead / expand)
LAT_EMA = 0.35                                      # same for the chevron's lateral place
FONT_DIR = '/usr/share/fonts/truetype/dejavu/'        # DejaVu has the Vietnamese glyphs


def project(cam_k, rpy, pts):
    """Calibrated device-frame points (x forward, y right, z down; origin at camera) -> pixels."""
    uvw = cam_k @ view_frame_from_device_frame @ rot_from_euler(rpy) @ np.asarray(pts, float).T
    with np.errstate(divide='ignore', invalid='ignore'):
        return (uvw[:2] / uvw[2]).T, uvw[2] > 0


SUB_BITS = 4
SUB = 1 << SUB_BITS   # sub-pixel precision of what is drawn: 1/16 px (integer vertices make a moving border shimmer)


def _stroke(img, px, color, width):
    """A smooth anti-aliased line through the float pixel points px, sub-pixel precise, round joints."""
    pts = np.round(np.asarray(px, float) * SUB).astype(np.int32)
    cv2.polylines(img, [pts], False, color, width, cv2.LINE_AA, shift=SUB_BITS)


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
        quad = np.round((np.array([left_px[j], left_px[j + 1], right_px[j + 1], right_px[j]]) - off) * SUB).astype(np.int32)
        a = alpha_near + (alpha_far - alpha_near) * j / max(n - 1, 1)
        cv2.fillPoly(mask, [quad], int(round(a * 255)), lineType=cv2.LINE_AA, shift=SUB_BITS)
    roi = img[y0:y1, x0:x1]
    on = mask > 0   # only the lane's own pixels (its bounding box is mostly outside it); integers, not floats
    a = mask[on].astype(np.uint16)[:, None]
    px = roi[on].astype(np.uint16)
    c = np.asarray(color, np.float32).round().astype(np.uint16)
    roi[on] = ((px * (255 - a) + c * a + 127) // 255).astype(np.uint8)


def ego_lane_borders(lanes, lane_prob, plan_pos, x_end, height, edges=None, edge_stds=None, pair=(1, 2), n=40):
    """Left/right ego-lane border (y, z) sampled on a fine x grid in front of the car. Each side on its own: the
    lane line (pair: line indices, (0, 2) or (1, 3) when the car drives on a line; lane_prob: their probabilities)
    when confident, else the road edge on that side when the model is sure of it and it is next to the car's lane
    (within a lane width of the path EDGE_NEAR_X ahead; not the kerb across a two-way street; at most
    LANE_MAX_WIDTH per lane from the other border), else a lane width from the other border. With neither: a nominal lane around the
    planned path (plan_pos: x, y, z from the camera, so + camera height to be on the road), or on the camera axis
    without a path."""
    xs = np.linspace(LANE_X_MIN, max(LANE_X_MIN + 1, x_end), n)

    def at(curves, k):
        return np.interp(xs, X_IDXS, curves[k, :, 0]), np.interp(xs, X_IDXS, curves[k, :, 1])
    n = pair[1] - pair[0]   # lanes spanned
    y_car = 0. if plan_pos is None else float(np.interp(EDGE_NEAR_X, plan_pos[:, 0], plan_pos[:, 1]))

    def beside(e):   # a kerb next to the car's lane, not across the road
        return abs(float(np.interp(EDGE_NEAR_X, X_IDXS, edges[e, :, 0])) - y_car) <= LANE_WIDTH * n
    sides = []
    for prob, k, e in ((lane_prob[0], pair[0], 0), (lane_prob[1], pair[1], 1)):
        if prob >= LANE_PROB:
            sides.append((at(lanes, k), False))
        elif edges is not None and edge_stds[e, 0, 0] <= EDGE_STD_MAX and beside(e):
            sides.append((at(edges, e), True))
        else:
            sides.append((None, False))
    (left, l_edge), (right, r_edge) = sides
    if left is not None or right is not None:
        if left is None:
            left = (right[0] - LANE_WIDTH * n, right[1])
        elif right is None:
            right = (left[0] + LANE_WIDTH * n, left[1])
        cap = LANE_MAX_WIDTH * n
        if l_edge and r_edge:
            mid = (left[0] + right[0]) / 2
            left, right = (np.maximum(left[0], mid - cap / 2), left[1]), (np.minimum(right[0], mid + cap / 2), right[1])
        elif r_edge:
            right = (np.minimum(right[0], left[0] + cap), right[1])
        elif l_edge:
            left = (np.maximum(left[0], right[0] - cap), left[1])
    else:
        if plan_pos is None:
            yc, zc = np.zeros_like(xs), np.full_like(xs, height)
        else:
            yc = np.interp(xs, plan_pos[:, 0], plan_pos[:, 1])
            zc = np.interp(xs, plan_pos[:, 0], plan_pos[:, 2]) + height
        left, right = (yc - FALLBACK_HALF_WIDTH, zc), (yc + FALLBACK_HALF_WIDTH, zc)
    return xs, *_inside_road(xs, left, right, edges, edge_stds)


def _inside_road(xs, left, right, edges, edge_stds):
    """Borders cut at the road edges that are certain enough (pipeline.EDGE_CLIP_STD), keeping LANE_MIN_WIDTH:
    the carpet follows the kerb in a turn instead of running off the road."""
    if edges is None or edge_stds is None:
        return left, right
    yl, yr = left[0], right[0]
    if edge_stds[1, 0, 0] <= EDGE_CLIP_STD:
        yr = np.minimum(yr, np.interp(xs, X_IDXS, edges[1, :, 0]))
        yl = np.minimum(yl, yr - LANE_MIN_WIDTH)
    if edge_stds[0, 0, 0] <= EDGE_CLIP_STD:
        yl = np.maximum(yl, np.interp(xs, X_IDXS, edges[0, :, 0]))
        yr = np.maximum(yr, yl + LANE_MIN_WIDTH)
    return (yl, left[1]), (yr, right[1])


def ego_path(outputs, curvature, speed, on_line=None):
    """Where the car will drive (pipeline.predicted_path), as plan points (x, y, z from the camera), or None
    without ego motion."""
    if curvature is None:
        return None
    reach = path_reach(speed if np.isfinite(speed) else 0.)
    return np.c_[X_IDXS, predicted_path(outputs, curvature, X_IDXS, reach, on_line), np.zeros_like(X_IDXS)]


def _first_on_picture(lp, rp, w, h):
    """Index of the first near-to-far sample from which both projected borders stay finite and within 4 picture
    sizes (a narrow lens throws the first metres far off the picture; only those are dropped), or None when fewer
    than 2 samples are left."""
    ok = np.isfinite(lp).all(axis=1) & np.isfinite(rp).all(axis=1) & \
        (np.abs(np.c_[lp, rp]).max(axis=1) <= 4 * max(w, h))
    bad = np.flatnonzero(~ok)
    i0 = 0 if not len(bad) else bad[-1] + 1
    return i0 if len(ok) - i0 >= 2 else None


def draw_lane(img, cam_k, rpy, borders, band=None):
    """Teal carpet between the ego-lane borders, from the bottom of the picture up to the lead (or 80 m), fading
    with distance; the near-white band (y centre, z, half width; default: the lane centre) along the predicted
    path; thin bright border lines on top."""
    xs, (yl, zl), (yr, zr) = borders

    def proj(y, z):
        return project(cam_k, rpy, np.c_[xs, y, z])[0]
    lp, rp = proj(yl, zl), proj(yr, zr)
    h, w = img.shape[:2]
    i0 = _first_on_picture(lp, rp, w, h)
    if i0 is None:
        return
    lp, rp = lp[i0:], rp[i0:]
    _blend_strips(img, lp, rp, LANE_BGR, 0.42, 0.22)
    yc, zc, hw = band if band is not None else ((yl + yr) / 2, (zl + zr) / 2, (yr - yl) * 0.27)
    bl, br = proj(yc - hw, zc)[i0:], proj(yc + hw, zc)[i0:]
    if _first_on_picture(bl, br, w, h) == 0:
        _blend_strips(img, bl, br, PATH_BGR, 0.55, 0.2)
    for px in (lp, rp):
        _stroke(img, px, EDGE_BGR, max(2, round(3 * w / 1164)))


def draw_chevron(img, u, v, dist, color):
    sz = float(np.clip(25 * 30 / (dist / 3 + 30), 15, 30)) * 1.4 * img.shape[1] / 1164
    tri = np.array([[u, v - sz * 0.35], [u + sz * 1.1, v + sz * 0.65], [u - sz * 1.1, v + sz * 0.65]], np.int32)
    glow = np.array([[u, v - sz * 0.6], [u + sz * 1.45, v + sz * 0.85], [u - sz * 1.45, v + sz * 0.85]], np.int32)
    # the shadow is blended only around the chevron (copying and blending the whole frame cost ~15 ms at 1080p)
    h, w = img.shape[:2]
    x0, y0 = np.clip(glow.min(axis=0) - 2, 0, [w, h])
    x1, y1 = np.clip(glow.max(axis=0) + 3, 0, [w, h])
    if x1 > x0 and y1 > y0:
        roi = img[y0:y1, x0:x1]
        layer = roi.copy()
        cv2.fillPoly(layer, [glow - [x0, y0]], (40, 40, 40), cv2.LINE_AA)
        cv2.addWeighted(layer, 0.45, roi, 0.55, 0, dst=roi)
    cv2.fillPoly(img, [tri], color, cv2.LINE_AA)


@cache
def _font(size: int, bold: bool = True):
    try:
        return ImageFont.truetype(FONT_DIR + ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)
    except OSError:
        return ImageFont.load_default(size)


def draw_panel(img, gap, gap_std, v_ego, ttc, close, note=None, radar_ref=None):
    """Top-left rounded panel: big distance from the bumper with its uncertainty, ego speed, TTC (+ note below). With
    radar_ref (the Lab: the radar's distance, NaN when there is none) the panel is centred and has a third line in amber,
    'Radar 23.0 m · Δ -2.2 m' (Δ = our distance - radar; 'Radar _' without a track), between the distance and the speed."""
    h, w = img.shape[:2]
    s = max(w, h) / 1164
    lab = radar_ref is not None
    x0, y0, pw, ph = int(18 * s), int(18 * s), int(330 * s), int((172 if lab else 150) * s)
    # only the top-left region is composited (PIL on the full frame costs several ms)
    roi = img[:min(h, y0 + ph + int(45 * s)), :min(w, max(x0 + pw + int(10 * s), int(560 * s)))]
    pil = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)).convert('RGBA')
    layer = Image.new('RGBA', pil.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=int(18 * s), fill=(25, 25, 25, 185))
    big, small = _font(int(78 * s)), _font(int(30 * s))
    red, white = (255, 90, 80, 255), (235, 235, 235, 255)

    def centred(text, font, y, fill):
        d.text((x0 + (pw - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
    if gap is None:
        d.text((x0 + 22 * s, y0 + 10 * s), '--', font=big, fill=(200, 200, 200, 255))
        d.text((x0 + 120 * s, y0 + 50 * s), 'Không có xe', font=_font(int(24 * s), False), fill=(200, 200, 200, 255))
    else:
        txt = f'{gap:.0f}'
        unit = ' m' + (f' ± {max(gap_std, 0.5):.0f}' if gap_std is not None else '')
        left = x0 + 22 * s
        if lab:   # the number and its unit as one centred group
            left = x0 + (pw - d.textlength(txt, font=big) - 8 * s - d.textlength(unit, font=small)) / 2
        d.text((left, y0 + 6 * s), txt, font=big, fill=red if close else (120, 240, 110, 255))
        d.text((left + d.textlength(txt, font=big) + 8 * s, y0 + 46 * s), unit.lstrip(), font=small, fill=white)
    if lab:
        amber, font = (255, 200, 80, 255), _font(int(22 * s))
        if np.isfinite(radar_ref):
            delta = f' · Δ {gap - radar_ref:+.1f} m' if gap is not None else ''
            centred(f'Radar {radar_ref:.1f} m{delta}', font, y0 + 100 * s, amber)
        else:
            centred('Radar _', font, y0 + 100 * s, amber)
    y_speed = (132 if lab else 102) * s
    if v_ego is not None and np.isfinite(v_ego):
        text = f'{v_ego * 3.6:.0f} km/h'
        if lab:
            centred(text, small, y0 + y_speed, white)
        else:
            d.text((x0 + 26 * s, y0 + y_speed), text, font=small, fill=white)
    if ttc is not None:
        d.text((x0 + 170 * s, y0 + y_speed), f'TTC {ttc:.1f} s', font=small, fill=red if close else white)
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


def _drawable_end(*curves):
    """x a grid step before the first of the curves (on GRID) turns more than TURN_AWAY from straight ahead or
    jumps (the model's sparse points smear a break over a step): past a bend the model's kerb runs sideways behind
    walls; LANE_X_MAX when none does (at least LANE_END_MIN)."""
    slopes = np.abs(np.diff(np.vstack(curves), axis=1)) / np.diff(GRID)
    bad = np.flatnonzero((slopes > TURN_AWAY).any(axis=0))
    return LANE_X_MAX if not len(bad) else max(LANE_END_MIN, float(GRID[max(bad[0] - 1, 0)]))


def _fit(y, end=LANE_X_MAX):
    """y sampled on GRID as a smooth polynomial in x (no kinks from the model's sparse points, no zigzag), fitted
    on the drawable part up to `end` only, and continued straight on along its tangent past it (no hook when the
    carpet grows)."""
    m = GRID <= end + 1e-9
    c = np.polyfit(GRID[m], y[m], min(FIT_DEGREE, int(m.sum()) - 1))
    out, far = np.polyval(c, GRID), ~m
    out[far] = np.polyval(c, end) + np.polyval(np.polyder(c), end) * (GRID[far] - end)
    return out


def lane_geometry(r, held=None):
    """The ego lane of a pipeline Result on GRID, as smooth curves: {yl, zl, yr, zr: borders, yc: centre of the
    light band (the predicted path, else the lane centre), end: x where the carpet stops (the lead, or where the
    road turns away out of sight (_drawable_end), else LANE_X_MAX), lat: the lead's lateral offset or None, held: which
    of the 4 lane lines count as confident}. `held`: the same flags of the previous tick (hysteresis: a confident line
    stays so while its probability is >= LANE_PROB_OFF, so a line hovering around LANE_PROB does not switch sources)."""
    p = r.outputs
    has = r.gap_m is not None
    path = ego_path(p, r.curvature, r.ego_speed_mps, r.straddle)
    plan_pos = path   # the model's plan (when kept) eased into the lane and kept on the road: predicted_path
    pair = {None: (1, 2), 1: (0, 2), 2: (1, 3)}[r.straddle]
    edges, stds = (p['road_edges'][0], p['road_edges_stds'][0]) if 'road_edges' in p else (None, None)
    prob = p['lane_lines_prob'][0, 1::2]
    if held is not None:
        prob = np.where(np.asarray(held) & (prob >= LANE_PROB_OFF), np.maximum(prob, LANE_PROB), prob)
    _, (yl, zl), (yr, zr) = ego_lane_borders(p['lane_lines'][0], prob[list(pair)], plan_pos, LANE_X_MAX, r.height_m,
                                             edges, stds, pair, len(GRID))
    yc = (yl + yr) / 2 if path is None else np.interp(GRID, path[:, 0], path[:, 1])
    # the path runs outside the lane: the car is between two lanes, so the carpet reaches over to cover it (at most
    # two lanes wide) instead of squeezing the path in; the light band keeps the width of one lane
    yl, yr, hw = widen_lane(yl, yr, yc, LANE_BAND * (yr - yl))
    end = _drawable_end(yl, yr, yc)
    g = {k: _fit(v, end) for k, v in dict(yl=yl, zl=zl, yr=yr, zr=zr, yc=yc, hw=hw).items()}
    return dict(g, end=min(float(r.lead_x_m), end) if has else end, lat=float(r.lead_lat_m) if has else None,
                held=prob >= LANE_PROB)


class LaneSmoother:
    """One per run: the drawn lane is the median of the last MEDIAN_TICKS ticks (a one-frame glitch of a border does not
    show) eased to (exponential smoothing on GRID) instead of jumping, so the carpet widens, narrows, collapses to a new
    lead and expands when it leaves over a few ticks; a lane line keeps counting as confident down to LANE_PROB_OFF."""

    CURVES = ('yl', 'zl', 'yr', 'zr', 'yc', 'hw')

    def __init__(self):
        self.geom, self.held, self.recent = None, None, []

    def update(self, r):
        """Call once per model tick; returns the smoothed geometry (lane_geometry's dict)."""
        g = lane_geometry(r, self.held)
        self.held = g.pop('held')
        self.recent = (self.recent + [g])[-MEDIAN_TICKS:]
        m = {k: np.median([x[k] for x in self.recent], axis=0) for k in self.CURVES}
        m['end'] = float(np.median([x['end'] for x in self.recent]))
        if self.geom is None:
            self.geom = dict(m, lat=g['lat'])
            return dict(self.geom)
        s = self.geom
        for k in self.CURVES:
            s[k] = s[k] + LANE_EMA * (m[k] - s[k])
        s['end'] += END_EMA * (m['end'] - s['end'])
        s['lat'] = g['lat'] if g['lat'] is None or s['lat'] is None else s['lat'] + LAT_EMA * (g['lat'] - s['lat'])
        return dict(s)


def _layout(cam_k, r, w, h, lane=None):
    """(ego-lane borders, light band (y centre, z, half width), lead chevron (u, v, distance) or None when off the
    picture, close) of a pipeline Result; lane: a LaneSmoother whose eased geometry is drawn instead."""
    g = lane.geom if lane is not None and lane.geom is not None else lane_geometry(r)
    has = r.gap_m is not None
    close = bool(has and np.isfinite(r.ego_speed_mps) and r.ego_speed_mps > 1
                 and r.gap_m / r.ego_speed_mps < CLOSE_HEADWAY_S)
    xs = np.linspace(LANE_X_MIN, max(LANE_X_MIN + 1, g['end']), 40)
    yl, zl, yr, zr, yc = (np.interp(xs, GRID, g[k]) for k in ('yl', 'zl', 'yr', 'zr', 'yc'))
    borders = xs, (yl, zl), (yr, zr)
    hw = np.interp(xs, GRID, g['hw'])   # ~55 % of a single lane width, also when the carpet spans two lanes
    band = np.clip(yc, yl + hw, yr - hw), (zl + zr) / 2, hw
    lead = None
    if has:
        x, lat = r.lead_x_m, r.lead_lat_m if g['lat'] is None else g['lat']   # filtered, like realtime_lead
        z = float(np.interp(x, xs, (zl + zr) / 2))   # lane surface under the lead, like the carpet's far edge
        ((u, v),), ok = project(cam_k, r.rpy, [[x, lat, z]])
        if ok[0] and 0 <= u < w and 0 <= v < h:
            lead = (float(u), float(v), float(x))
    return borders, band, lead, close


def overlay(cam_k, r, w, h, lane=None):
    """What the HUD draws, as fractions of the w x h picture, for a page that draws it on its own live camera
    (the phone page): {lane, path: {left, right: [[u, v], ...] near to far} or None, lead: {u, v, dist_m, close}
    or None}; path is the light band along the predicted path; lane: a LaneSmoother (eased geometry)."""
    borders, (yc, zc, hw), lead, close = _layout(cam_k, r, w, h, lane)
    xs, (yl, zl), (yr, zr) = borders

    def band(left, right):
        lp, rp = (project(cam_k, r.rpy, np.c_[xs, y, z])[0] for y, z in (left, right))
        i0 = _first_on_picture(lp, rp, w, h)
        if i0 is None:
            return None
        return {k: (px[i0:][::2] / [w, h]).round(4).tolist() for k, px in (('left', lp), ('right', rp))}
    path = None if r.curvature is None else band((yc - hw, zc), (yc + hw, zc))   # no ego motion: no path
    return dict(lane=band((yl, zl), (yr, zr)), path=path, lead=None if lead is None else dict(u=round(lead[0] / w, 4), v=round(lead[1] / h, 4),
                                                              dist_m=round(lead[2], 1), close=close))


def draw(frame, cam_k, r, fy, note=None, gps_line=None, use_pitch=True, radar_ref=None, debug=True, lane=None):
    """lane: a LaneSmoother (the eased lane is drawn). note: shown under the panel once the angles have settled
    (GPS sync / focal fit); gps_line: GPS state
    in the calibration box, as comma realtime_lead renders them. radar_ref and debug=False: comma lead_distance
    app.py (overlay.draw_frame), which shows the radar distance and has no calibration box."""
    est = r.rpy if r.rpy_est is None else r.rpy_est
    borders, band, lead, close = _layout(cam_k, r, frame.shape[1], frame.shape[0], lane)
    draw_lane(frame, cam_k, r.rpy, borders, band)
    if lead is not None:
        draw_chevron(frame, *lead, CLOSE_BGR if close else LEAD_BGR)
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
