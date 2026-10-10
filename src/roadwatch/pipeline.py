"""Per-tick pipeline: warp -> gr14VinAI -> calibration feedback -> same-lane lead -> filtered gap and TTC.

Ported from comma_ai/lead_distance/realtime_lead.py (LeadEstimator; copied, not imported): the model's "now"
lead hypothesis is the same-lane lead once the camera angles have settled, p >= LEAD_PROB, |y| <= MAX_LAT_M
from the camera axis and x > 0; it is smoothed by a constant-velocity Kalman filter that bridges drop-outs
up to 0.5 s. The reported sigma is the model's own std (the Kalman std is over-confident: 56 % vs 93 % 2-sigma
coverage on comma2k19). The ego speed is the GPS speed once the GPS log is synced (gps.GpsRef), else the
model's rescaled to the tick; smoothed (EMA). Optionally the focal length follows the GPS speed (FocalFromSpeed).
Every tick is logged as a row of realtime_lead's CSV. RoadWatch adds the camera height, the model-frame
coverage check and TTC.
"""
from dataclasses import dataclass

import numpy as np

from .calibration import AutoCalib, FocalFromSpeed, intrinsics
from .model import MODEL_DT, Gr14VinAI, coverage, pack_frame, warp_matrices

MIN_COVERAGE = 0.95    # below this the model sees replicated borders, not the scene
LEAD_PROB = 0.5        # same-lane lead: p >= LEAD_PROB and |y| <= MAX_LAT_M (realtime_lead MIN_PROB, MAX_LAT)
MAX_LAT_M = 2.0
EGO_EMA = 0.15         # ego speed smoothing per tick
TTC_MAX_S = 10.0
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
                 focal: FocalFromSpeed | None = None, use_pitch=True, wide='auto', rpy=None, rpy_est=None, cal=None):
        """w, h: size of the (cropped) camera picture; tick_dt: time between two model ticks (model.tick);
        v_ref: gps.GpsRef (or None); focal: fits fy to the GPS speed (needs v_ref); wide: 'auto', 'dup' or 'warp'
        (model.wide_mode). rpy: fixed camera angles for the whole run, no online calibration (comma lead_distance
        app.py: yaw from a pre-pass), rpy_est their full estimate for the HUD horizon; cal: an AutoCalib that has
        already learned (realtime_lead --prepass)."""
        self.w, self.h, self.d_cam_bumper, self.wide = w, h, d_cam_bumper, wide
        self.tick_dt, self.vel_scale = tick_dt, MODEL_DT / tick_dt
        self.K = intrinsics(fy, w, h)
        self.model = model or Gr14VinAI()
        self.model.reset()
        self.cal = cal or AutoCalib(use_pitch=use_pitch)
        self.fixed = rpy is not None
        self.fixed_est = np.asarray(rpy if rpy_est is None else rpy_est, float) if self.fixed else None
        self.tracker = LeadTracker()
        self.v_ref, self.focal = v_ref, focal
        self.rows, self.n = [], 0
        self._rewarp(rpy if self.fixed else self.cal.rpy)
        self.heights = []
        self.v_ego, self.gap_std, self.lat, self.v_lead = 0., None, None, None

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

        lx, ly, v_lead, _ = (float(t) for t in p['lead'][0, 0, 0])
        lstd, prob = float(p['lead_stds'][0, 0, 0, 0]), float(p['lead_prob'][0, 0])
        has = self.settled and prob >= LEAD_PROB and abs(ly) <= MAX_LAT_M and lx > 0
        xf = self.tracker.update(self.tick_dt, lx if has else None, lstd)
        if has:
            self.gap_std, self.lat, self.v_lead = lstd, ly, v_lead * self.vel_scale
        self.v_ego += EGO_EMA * ((v_gps if np.isfinite(v_gps) else float(pose[0])) - self.v_ego)
        dist = None if xf is None else float(xf[0])
        self.rows.append((pts, lx if has else np.nan, lstd, np.nan if dist is None else dist,
                          np.nan if dist is None else dist - self.d_cam_bumper, ly, prob, float(pose[0]), v_gps,
                          self.K[0, 0], *np.degrees(self.rpy), self.settled))
        gap = ttc = None
        if dist is not None:
            gap = dist - self.d_cam_bumper
            closing = self.v_ego - self.v_lead
            if closing > 0.5 and gap / closing < TTC_MAX_S:
                ttc = gap / closing
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
                      float(v_gps) if np.isfinite(v_gps) else None, float(self.K[0, 0]))

    def save_csv(self, path):
        """Per-tick log in realtime_lead's CSV format."""
        np.savetxt(path, np.array(self.rows, float).reshape(-1, len(CSV_HEADER.split(','))), delimiter=',',
                   fmt='%.3f', header=CSV_HEADER, comments='')
