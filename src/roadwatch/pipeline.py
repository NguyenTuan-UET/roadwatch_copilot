"""Per-tick pipeline: warp -> gr14VinAI -> calibration feedback -> same-lane lead -> filtered gap and TTC.

Ported from comma_ai/lead_distance/realtime_lead.py (LeadEstimator; copied, not imported): the model's "now"
lead hypothesis is the same-lane lead once the camera angles have settled, p >= LEAD_PROB, |y| <= MAX_LAT_M
from the ego-lane centre at the lead's distance and x > 0; it is smoothed by a constant-velocity Kalman filter that bridges drop-outs
up to 0.5 s. The reported sigma is the model's own std (the Kalman std is over-confident: 56 % vs 93 % 2-sigma
coverage on comma2k19). The ego speed is the GPS speed once the GPS log is synced (gps.GpsRef), else the
model's rescaled to the tick; smoothed (EMA). Optionally the focal length follows the GPS speed (FocalFromSpeed).
Every tick is logged as a row of realtime_lead's CSV. RoadWatch adds the camera height, the model-frame
coverage check and TTC, and follows the lane: the ego-lane centre is the middle of the model's two ego lane
lines when both are confident, else the path the ego motion predicts (curvature = yaw rate / speed from the
model's pose, smoothed; an arc for PATH_REACH_S, then straight on: path_offset), so on a curve the lead is looked for where the lane goes, not straight
ahead of the camera.
"""
from dataclasses import dataclass

import numpy as np
from g01T014VinAI.selfdrive.modeld.constants import ModelConstants

from .calibration import AutoCalib, FocalFromSpeed, intrinsics
from .model import MODEL_DT, Gr14VinAI, coverage, pack_frame, warp_matrices
from .temporal import MotionEstimator

MIN_COVERAGE = 0.95    # below this the model sees replicated borders, not the scene
LEAD_PROB = 0.5        # same-lane lead: p >= LEAD_PROB and |y| <= MAX_LAT_M (realtime_lead MIN_PROB, MAX_LAT)
MAX_LAT_M = 2.0
LANE_WIDTH = 3.5       # m, a missing lane border is this far from the other one (hud) and a widened lane has 2
LANE_BAND = 0.27       # half width of the light band along the path, as a fraction of the lane width
BAND_MARGIN = 0.3      # m: the lane reaches this far beyond a path that leaves it (widen_lane)
NEAR_FROM_YAW = True   # the path near the car is the yaw arc, the plan only adds the far bend (ego_offset)
WIDEN_LEAD = True      # the lead window covers both lanes when the car runs between them
LANE_PROB = 0.4        # both ego lane lines at least this probable: they give the lane centre (as the HUD draws)
CURV_EMA = 0.08        # ego path curvature smoothing per tick (~0.6 s at 20 Hz: a brief steering movement barely bends it)
CURV_MAX = 0.1         # 1/m (10 m radius: a turn at a crossroads), and at most A_LAT_MAX sideways (curvature_max)
A_LAT_MAX = 4.0        # m/s^2
CURV_MIN_SPEED = 2.0   # m/s: below this the yaw rate is divided by this speed (a standing car's yaw noise)
STRADDLE_X_M = 5.0     # the car's place among the lane lines is read this far ahead
HEADING_MAX = 0.6      # rad (~35 deg): the drawn path turns at most this much, then goes straight on
PLAN_MIN_M = 5.0       # the model's plan is the ego path when it reaches at least this far ahead
EDGE_CLIP_STD = 3.0    # m: a road edge at least this certain (near the car) keeps the path and the lane on the road
EDGE_MARGIN_M = 0.9    # the path keeps this far inside a road edge (half a car)
STRADDLE_ON_M, STRADDLE_OFF_M = 0.6, 0.9   # a lane line this close: the car drives on it, until it is this far
PATH_REACH_S = 1.5     # the curvature is carried this long ahead; beyond, the path goes on along its tangent
PATH_REACH_MIN_M = 15.
X_IDXS = np.array(ModelConstants.X_IDXS)
EGO_EMA = 0.15         # ego speed smoothing per tick
TTC_MAX_S = 10.0
PREDICT_S = 1.0        # horizon of the predicted gap
CSV_HEADER = ('time_s,lead_dist_raw_m,lead_dist_std_m,lead_dist_filtered_m,lead_dist_bumper_m,lead_lat_m,lead_prob,'
              'ego_speed_model_mps,ego_speed_gps_mps,focal_px,calib_roll_deg,calib_pitch_deg,calib_yaw_deg,calib_settled')


@dataclass
class Result:
    status: str              # 'calibrating k/40' | 'calibrated' | 'unreliable: <why>'
    rpy: np.ndarray          # angles used for the warp
    height_m: float
    ego_speed_mps: float     # model speed rescaled to the tick, smoothed
    lead_prob: float
    gap_m: float | None      # filtered camera->lead minus d_cam_bumper; None when no lead is tracked
    lead_speed_mps: float | None
    ttc_s: float | None
    outputs: dict            # parsed gr14VinAI outputs (lane_lines, lead, ...)
    gap_std_m: float | None = None    # model std of the lead distance
    lead_lat_m: float | None = None   # lateral offset of the lead, + = right
    rpy_est: np.ndarray | None = None  # estimated roll, pitch, yaw
    lead_x_m: float | None = None     # filtered camera->lead distance (HUD chevron)
    lead_raw_m: float | None = None   # model's camera->lead distance on this tick when it is the same-lane lead
    gps_speed_mps: float | None = None   # GPS speed at this tick; None without a synced GPS log
    fy_px: float | None = None        # focal length in use
    gap_pred_m: float | None = None   # gap PREDICT_S ahead from the distance history; None without enough history
    model_speed_mps: float | None = None   # ego speed estimated from the images alone (model), smoothed like ego
    curvature: float | None = None    # 1/m of the path the ego motion predicts, + = turning right
    lane_ref: str | None = None       # where the ego-lane centre came from: 'lane_lines' | 'both_lanes' | 'ego_path'
    straddle: int | None = None       # lane line the car drives on (1 left, 2 right), or None


def curvature_max(speed):
    """Largest believable ego curvature at this speed: CURV_MAX, and at most A_LAT_MAX sideways."""
    return min(CURV_MAX, A_LAT_MAX / max(speed, 1e-3) ** 2)


def straddle(outputs, prev=None):
    """Lane line the car drives on (1 = left, 2 = right of the camera), or None: a confident line within
    STRADDLE_ON_M of the camera axis STRADDLE_X_M ahead; it stays so until STRADDLE_OFF_M away (no flicker).
    The ego lane is then both lanes beside that line."""
    lanes, prob = outputs.get('lane_lines'), outputs.get('lane_lines_prob')
    if lanes is None or prob is None:
        return None
    near = {k: abs(float(np.interp(STRADDLE_X_M, X_IDXS, lanes[0, k, :, 0])))
            for k in (1, 2) if prob[0, 1::2][k] >= LANE_PROB}
    if prev in near and near[prev] <= STRADDLE_OFF_M:
        return prev
    on = [k for k, d in near.items() if d < STRADDLE_ON_M]
    return min(on, key=near.get) if on else None


def path_reach(speed):
    """Metres ahead over which the ego curvature is carried (path_offset)."""
    return max(PATH_REACH_MIN_M, speed * PATH_REACH_S)


def path_offset(curvature, x, reach):
    """Lateral offset (+ = right) at distance x of the path the ego motion predicts: the arc curvature * x^2 / 2 up
    to reach metres (and at most until it has turned HEADING_MAX), then straight on along its tangent, so a
    steering movement is not carried out to 80 m."""
    x = np.asarray(x, float)
    if curvature:
        reach = min(reach, HEADING_MAX / abs(curvature))
    xa = np.minimum(x, reach)
    return curvature * xa * (x - xa / 2)


def plan_offset(outputs, x):
    """Lateral offset at distances x of the model's own trajectory (policy plan head: it weighs the road and the
    car's motion), turning at most HEADING_MAX from straight ahead and continued straight past its last point; None
    without a plan or when it reaches less than PLAN_MIN_M ahead (standing still)."""
    plan = outputs.get('plan')
    if plan is None:
        return None
    px, py = plan[0, :, 0], plan[0, :, 1]
    keep = np.r_[True, np.diff(px) > 0.05] & (px >= np.maximum.accumulate(px))   # the part that heads forward
    px, py = px[keep], py[keep]
    if len(px) < 3 or px[-1] < PLAN_MIN_M:
        return None
    x, k = np.asarray(x, float), np.tan(HEADING_MAX)
    slopes = np.clip(np.diff(py) / np.diff(px), -k, k)       # a U-turn runs sideways: followed at <= HEADING_MAX
    py = py[0] + np.r_[0., np.cumsum(slopes * np.diff(px))]
    return np.where(x <= px[-1], np.interp(x, px, py), py[-1] + slopes[-1] * (x - px[-1]))


def road_bounds(outputs, x):
    """(left, right) y of the road edges at distances x that are certain enough to bound the path and the lane
    (near-car std <= EDGE_CLIP_STD), None for a side that is not."""
    edges, stds = outputs.get('road_edges'), outputs.get('road_edges_stds')
    if edges is None or stds is None:
        return None, None
    return tuple(np.interp(x, X_IDXS, edges[0, k, :, 0]) if stds[0, k, 0, 0] <= EDGE_CLIP_STD else None
                 for k in (0, 1))


def _on_road(outputs, x, y):
    """y kept EDGE_MARGIN_M inside the known road edges (the middle of the road where they are closer)."""
    left, right = road_bounds(outputs, x)
    if left is None and right is None:
        return y
    lo = -np.inf if left is None else left + EDGE_MARGIN_M
    hi = np.inf if right is None else right - EDGE_MARGIN_M
    if left is not None and right is not None:   # a road narrower than the two margins: its middle
        mid = (lo + hi) / 2
        lo, hi = np.minimum(lo, mid), np.maximum(hi, mid)
    return np.clip(y, lo, hi)


def ego_offset(outputs, curvature, x, reach):
    """Lateral offset at distances x of where the ego motion leads. With confident lane lines it is the model's plan.
    Without them (a tight turn on a street with no lines: the lane test's worst case) near the car it is the arc of the
    measured yaw (path_offset: it follows the real curvature best); from `reach` on it goes on along that heading
    and adds how the model's plan bends away from its own tangent there (the road ahead), so a turn is not carried
    on blindly and a bend the car has not started yet still shows. Without a plan: the yaw path alone."""
    y = path_offset(curvature, x, reach)
    if not NEAR_FROM_YAW or lane_lines_center(outputs, 20.) is not None:   # with lane lines the plan follows the road
        plan = plan_offset(outputs, x)
        return y if plan is None else plan
    if plan_offset(outputs, 0.) is None:
        return y
    x = np.asarray(x, float)
    xr = min(reach, HEADING_MAX / abs(curvature)) if curvature else reach
    p0, p1, p2 = (float(plan_offset(outputs, v)) for v in (xr - .5, xr, xr + .5))
    bend = plan_offset(outputs, x) - p1 - (p2 - p0) * (x - xr)   # the plan's deviation from its tangent at xr
    return y + np.where(x > xr, bend, 0.)


CURV_FIT_X = np.linspace(5, 40, 15)   # m, where a path is turned into a curvature (Lab, scripts/roadwatch/eval_lane_test.py)


def fit_curvature(y):
    """Curvature of the path y(x) over CURV_FIT_X: k = 2 c2 of the parabola c0 + c1 x + c2 x^2 (a lateral shift or a
    heading error of the camera does not count as curvature); + = right."""
    return float(2 * np.polyfit(CURV_FIT_X, y, 2)[0])


def path_curvature(outputs, curvature, speed, on_line=None):
    """Curvature (1/m, + = right) of the path BT-A draws (predicted_path), or None without the ego motion."""
    if curvature is None:
        return None
    return fit_curvature(predicted_path(outputs, curvature, CURV_FIT_X, path_reach(speed), on_line))


def lane_lines_center(outputs, x, on_line=None):
    """y at distances x of the line the car drives on (on_line, from straddle), else of the middle of the two ego
    lane lines when both are confident, else None."""
    lanes, prob = outputs.get('lane_lines'), outputs.get('lane_lines_prob')
    if lanes is None or prob is None:
        return None
    if on_line is not None:
        return np.interp(x, X_IDXS, lanes[0, on_line, :, 0])
    if min(prob[0, 1::2][1:3]) < LANE_PROB:
        return None
    return (np.interp(x, X_IDXS, lanes[0, 1, :, 0]) + np.interp(x, X_IDXS, lanes[0, 2, :, 0])) / 2


def widen_lane(yl, yr, yc, hw):
    """Borders of the lane (yl, yr) widened to cover a path at yc whose light band (half width hw) would touch a
    lane line, BAND_MARGIN beyond it, at most two lanes wide: the car runs between two lanes. Works on numbers and
    arrays; returns (yl, yr, hw) with hw unchanged (the band keeps the width of one lane)."""
    yl = np.maximum(np.minimum(yl, yc - hw - BAND_MARGIN), yr - 2 * LANE_WIDTH)
    yr = np.minimum(np.maximum(yr, yc + hw + BAND_MARGIN), yl + 2 * LANE_WIDTH)
    return yl, yr, hw


def lane_center(outputs, curvature, x, reach, on_line=None):
    """(y of the ego-lane centre at distance x, + = right; half width of the window around it for a lead; where it
    came from: 'lane_lines' | 'both_lanes' | 'ego_path'). From the lane lines (lane_lines_center); when the car runs
    between two lanes (the model's path over a lane line: widen_lane) the centre and window are those of the two
    lanes; else the path the ego motion predicts."""
    c = lane_lines_center(outputs, x, on_line)
    if c is None:
        return float(_on_road(outputs, x, ego_offset(outputs, curvature, x, reach))), MAX_LAT_M, 'ego_path'
    plan = plan_offset(outputs, x) if on_line is None and WIDEN_LEAD else None   # the yaw path lags on a curve: not used
    if plan is not None:
        yl, yr = lane_lines_center(outputs, x, 1), lane_lines_center(outputs, x, 2)
        wl, wr, _ = widen_lane(yl, yr, _on_road(outputs, x, plan), LANE_BAND * (yr - yl))
        if wl < yl - 1e-6 or wr > yr + 1e-6:
            return float((wl + wr) / 2), float((wr - wl) / 2 + .2), 'both_lanes'
    return float(c), MAX_LAT_M, 'lane_lines'


def predicted_path(outputs, curvature, x, reach, on_line=None):
    """Lateral offset (+ = right) at distances x of where the car will drive: it follows the road. From the car
    (the ego path) it eases into the ego-lane centre (lane_lines_center) by `reach` metres (smoothstep), then
    follows it; without lane lines, the ego path (ego_offset) alone. Always kept on the road (road_bounds)."""
    ego = ego_offset(outputs, curvature, x, reach)
    c = lane_lines_center(outputs, x, on_line)
    if c is not None:
        w = np.clip(np.asarray(x, float) / reach, 0., 1.)
        ego = ego + w * w * (3 - 2 * w) * (c - ego)
    return _on_road(outputs, x, ego)


class LeadTracker:
    """Constant-velocity Kalman filter on the lead distance (like openpilot's radard smooths leads)."""
    LOST_AFTER_S = 0.5

    def __init__(self, accel_std=3.0):
        self.q = accel_std ** 2
        self.x = None          # [distance, d(distance)/dt]
        self.lost_t = 0.

    def _restart(self, meas, r):
        self.x, self.P = np.array([meas, 0.]), np.diag([r, 25.])

    def update(self, dt, meas, meas_std):
        if meas is None:
            self.lost_t += dt
            if self.lost_t > self.LOST_AFTER_S:
                self.x = None
            return self.x
        self.lost_t = 0.
        r = max(meas_std, 0.5) ** 2
        if self.x is None:
            self._restart(meas, r)
            return self.x
        f = np.array([[1, dt], [0, 1]])
        self.x = f @ self.x
        self.P = f @ self.P @ f.T + self.q * np.array([[dt ** 4 / 4, dt ** 3 / 2], [dt ** 3 / 2, dt ** 2]])
        innov = meas - self.x[0]
        if abs(innov) > max(8., 0.3 * meas):  # a different vehicle (cut-in / cut-out): restart
            self._restart(meas, r)
            return self.x
        k = self.P[:, 0] / (self.P[0, 0] + r)
        self.x = self.x + k * innov
        self.P = self.P - np.outer(k, self.P[0])
        return self.x


class Pipeline:
    def __init__(self, w, h, fy, d_cam_bumper, model=None, tick_dt=MODEL_DT, v_ref=None,
                 focal: FocalFromSpeed | None = None, use_pitch=True, wide='auto', rpy=None, rpy_est=None, cal=None,
                 temporal=True):
        """w, h: size of the (cropped) camera picture; tick_dt: time between two model ticks (model.tick);
        v_ref: gps.GpsRef (or None); focal: fits fy to the GPS speed (needs v_ref); wide: 'auto', 'dup' or 'warp'
        (model.wide_mode). rpy: fixed camera angles for the whole run, no online calibration (comma lead_distance
        app.py: yaw from a pre-pass), rpy_est their full estimate for the HUD horizon; cal: an AutoCalib that has
        already learned (realtime_lead --prepass). temporal: take the gap from the distance history (temporal.py);
        False keeps the Kalman distance alone (ablation)."""
        self.w, self.h, self.d_cam_bumper, self.wide = w, h, d_cam_bumper, wide
        self.tick_dt, self.vel_scale = tick_dt, MODEL_DT / tick_dt
        self.K = intrinsics(fy, w, h)
        self.model = model or Gr14VinAI()
        self.model.reset()
        self.cal = cal or AutoCalib(use_pitch=use_pitch)
        self.fixed = rpy is not None
        self.fixed_est = np.asarray(rpy if rpy_est is None else rpy_est, float) if self.fixed else None
        self.tracker = LeadTracker()
        self.motion, self.temporal = MotionEstimator(), temporal
        self.v_ref, self.focal = v_ref, focal
        self.rows, self.n = [], 0
        self._rewarp(rpy if self.fixed else self.cal.rpy)
        self.heights = []
        self.v_ego, self.gap_std, self.lat, self.v_lead = 0., None, None, None
        self.v_model, self.curv, self.on_line = 0., 0., None

    def set_fy(self, fy):
        """Switch the focal length mid-run (fy learned in the background); the learned angles are kept."""
        self.K = intrinsics(fy, self.w, self.h)
        self._rewarp(self.rpy)

    def _rewarp(self, rpy):
        self.rpy = np.asarray(rpy, float).copy()
        self.warps = warp_matrices(self.K, self.rpy, self.w, self.wide)
        self.coverage = coverage(self.warps, self.w, self.h)
        self.cal.warp_rpy = self.rpy

    @property
    def settled(self):
        return self.fixed or self.cal.settled

    def step(self, y, u, v, pts=None):
        """pts: video time of the frame (default: ticks so far x tick_dt)."""
        pts = self.n * self.tick_dt if pts is None else pts
        self.n += 1
        p = self.model.step(pack_frame(y, u, v, self.warps))
        pose = p['pose'][0] * self.vel_scale
        if not self.fixed and self.cal.update(pose, p['road_transform'][0], p['road_transform_stds'][0]):
            self._rewarp(self.cal.rpy)
        self.heights.append(float(p['road_transform'][0, 2]))
        if self.v_ref is not None:
            self.v_ref.observe(pts, float(pose[0]))   # online GPS time sync
        v_gps = self.v_ref(pts) if self.v_ref is not None else np.nan
        if self.focal is not None and self.focal.update(float(pose[0]), v_gps):
            self.set_fy(self.focal.f)

        curv, k_max = float(pose[5]) / max(float(pose[0]), CURV_MIN_SPEED), curvature_max(float(pose[0]))
        self.curv += CURV_EMA * (float(np.clip(curv, -k_max, k_max)) - self.curv)
        self.on_line = straddle(p, self.on_line)
        lx, ly, v_lead, _ = (float(t) for t in p['lead'][0, 0, 0])
        lstd, prob = float(p['lead_stds'][0, 0, 0, 0]), float(p['lead_prob'][0, 0])
        center, half, lane_ref = lane_center(p, self.curv, lx, path_reach(self.v_ego), self.on_line)
        has = self.settled and prob >= LEAD_PROB and abs(ly - center) <= half and lx > 0
        xf = self.tracker.update(self.tick_dt, lx if has else None, lstd)
        mot = None   # previous frames -> distance and its trend; carried forward through a short drop-out
        if self.temporal:
            mot = self.motion.update(pts, lx, lstd) if has else self.motion.coast(pts)
        if has:
            self.gap_std, self.lat, self.v_lead = lstd, ly, v_lead * self.vel_scale
        self.v_ego += EGO_EMA * ((v_gps if np.isfinite(v_gps) else float(pose[0])) - self.v_ego)
        self.v_model += EGO_EMA * (float(pose[0]) - self.v_model)
        dist = None if xf is None else float(xf[0])
        if mot is not None and dist is not None:
            dist += mot.weight * (mot.dist - dist)   # temporal fit over the last frames, taking over from the Kalman
        self.rows.append((pts, lx if has else np.nan, lstd, np.nan if dist is None else dist,
                          np.nan if dist is None else dist - self.d_cam_bumper, ly, prob, float(pose[0]), v_gps,
                          self.K[0, 0], *np.degrees(self.rpy), self.settled))
        gap = ttc = gap_pred = None
        if dist is not None:
            gap = dist - self.d_cam_bumper
            closing = self.v_ego - self.v_lead
            if closing > 0.5 and gap / closing < TTC_MAX_S:
                ttc = gap / closing
            if mot is not None:
                gap_pred = max(0., mot.predict(PREDICT_S) - self.d_cam_bumper)
        if self.coverage < MIN_COVERAGE:
            status = f'unreliable: coverage {self.coverage:.0%}'
        elif self.settled:
            status = 'calibrated'
        else:
            status = f'calibrating {self.cal.n}/{AutoCalib.SETTLED_SAMPLES}'
        tracked = dist is not None
        return Result(status, self.rpy.copy(), float(np.median(self.heights)), self.v_ego, prob, gap,
                      self.v_lead if tracked else None, ttc, p, self.gap_std if tracked else None,
                      self.lat if tracked else None, (self.fixed_est if self.fixed else self.cal.est).copy(), dist,
                      lx if has else None,
                      float(v_gps) if np.isfinite(v_gps) else None, float(self.K[0, 0]), gap_pred, self.v_model,
                      self.curv, lane_ref, self.on_line)

    def save_csv(self, path):
        """Per-tick log in realtime_lead's CSV format."""
        np.savetxt(path, np.array(self.rows, float).reshape(-1, len(CSV_HEADER.split(','))), delimiter=',',
                   fmt='%.3f', header=CSV_HEADER, comments='')
