"""Automatic camera calibration from gr14VinAI itself; the only user input is d_cam_bumper.

* fy      : learned by sweeping fy and keeping the warp the model is most confident with
            (lowest pose and road_transform std). A wrong fy feeds the model images unlike its
            training data, and its uncertainty rises.
* roll/pitch/yaw: AutoCalib (from comma_ai/lead_distance): road_transform on every frame + pose direction
            while driving straight, running mean then slow EMA. Roll, pitch and yaw are all applied to the
            warp, as comma_ai realtime_lead does by default.
* height  : gr14VinAI road_transform.
"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from g01T014VinAI.common.transformations.orientation import euler_from_rot, rot_from_euler

from .model import pack_frame, warp_matrices

MIN_SPEED = 15 * 0.44704   # learn_fy: below this the model's confidence barely depends on fy
LEARN_SKIP, LEARN_FRAMES = 100, 200   # learn_fy on model ticks LEARN_SKIP .. LEARN_SKIP + LEARN_FRAMES


def intrinsics(fy, w, h):
    return np.array([[fy, 0, w / 2], [0, fy, h / 2], [0, 0, 1.]])


class AutoCalib:
    """Camera mounting angles (device_from_calib roll, pitch, yaw), estimated online from two model outputs:

    * road_transform: camera -> road rotation, on every frame (also when stopped or turning);
    * pose: direction of the ego translation, only while driving straight and fast.

    Both are residuals w.r.t. the warp in use (`warp_rpy`), composed back to absolute angles and averaged
    (running mean, then a slow EMA so slopes and bumps average out; a re-mounted camera is followed within
    ~5 s instead of being detected). `rpy` is what the warp should use: the estimate masked by use_roll/use_pitch.
    """
    MIN_SPEED = 5.0                  # m/s, for pose observations
    MAX_YAW_RATE = np.radians(3)     # rad/s
    MAX_ROAD_STD = np.radians(1.5)   # road_transform rotation std accepted
    LIMIT = np.radians(20)
    SETTLED_SAMPLES = 40             # ~2 s of frames
    MIN_ALPHA = 0.01                 # EMA after the running mean: ~5 s time constant at 20 Hz
    resets = 0                       # no re-mount detection (the EMA follows a new mount)

    def __init__(self, rpy0=None, use_pitch=True, use_roll=True, use_road=True):
        self.est = np.zeros(3) if rpy0 is None else np.array(rpy0, float)
        self.mask = np.array([use_roll, use_pitch, True], float)
        self.use_road = use_road
        self.warp_rpy = self.rpy
        self.n = 0

    @property
    def rpy(self):
        """Angles to apply to the warp."""
        return self.est * self.mask

    @property
    def settled(self):
        return self.n >= self.SETTLED_SAMPLES

    def _fold(self, observed, axes):
        new = euler_from_rot(rot_from_euler(self.warp_rpy) @ rot_from_euler(observed))
        alpha = max(1 / (self.n + 2), self.MIN_ALPHA)
        self.est[axes] += alpha * (new[axes] - self.est[axes])
        self.est = np.clip(self.est, -self.LIMIT, self.LIMIT)

    def update(self, pose, road_transform=None, road_transform_std=None):
        """Feed one frame of parsed model output (pose: trans m/s + rot rad/s). Returns True if it was used."""
        used = False
        if self.use_road and road_transform is not None and \
                (road_transform_std is None or np.max(road_transform_std[3:]) < self.MAX_ROAD_STD):
            self._fold(np.asarray(road_transform[3:], float), [0, 1, 2])
            used = True
        trans, rot = pose[:3], pose[3:]
        if trans[0] >= self.MIN_SPEED and abs(rot[2]) <= self.MAX_YAW_RATE:
            self._fold(np.array([0., -np.arctan2(trans[2], trans[0]), np.arctan2(trans[1], trans[0])]), [1, 2])
            used = True
        self.n += used
        return used


class FocalFromSpeed:
    """Camera focal length from the ego speed (comma_ai lead_distance.py): with a wrong focal length the model's
    speed (and every distance) is off by the same factor (checked on comma2k19: speed ratio == focal ratio within
    ~3 %), so f_true = f_assumed / median(v_model / v_reference). The reference is GPS speed.

    Online schedule: a quick first correction after BATCH_FIRST samples (fixes a grossly wrong FOV within
    seconds), then refinements over BATCH samples (10 s) with a damped step, only when off by > SETTLED_REL.
    Samples right after a change are skipped because the model's speed lags a new image scale."""
    MIN_SPEED = 5.0                  # m/s
    BATCH_FIRST = 60                 # 3 s at 20 Hz
    BATCH = 200                      # 10 s at 20 Hz
    SETTLE = 40                      # samples skipped after a change
    DAMP = 0.7
    MAX_STEP = np.log(1.6)
    SETTLED_REL = 0.03

    def __init__(self, f0: float):
        self.f = float(f0)
        self.logs, self.updates, self.last_ratio = [], 0, np.nan
        self.settled = False
        self._skip = 0

    def update(self, v_model: float, v_ref: float) -> bool:
        """Feed one tick; returns True when the focal length changed."""
        if v_ref is None or not np.isfinite(v_ref) or v_ref < self.MIN_SPEED or v_model < 1.0:
            return False
        if self._skip > 0:
            self._skip -= 1
            return False
        self.logs.append(np.log(v_model / v_ref))
        if len(self.logs) < (self.BATCH_FIRST if self.updates == 0 else self.BATCH):
            return False
        r = float(np.median(self.logs))
        self.logs = []
        self.last_ratio = float(np.exp(r))
        first = self.updates == 0
        self.updates += 1
        if abs(r) < self.SETTLED_REL:
            self.settled = True
            return False
        self.f /= np.exp(np.clip(r if first else self.DAMP * r, -self.MAX_STEP, self.MAX_STEP))
        self._skip = self.SETTLE
        return True


EQUIV_WIDTH_MM = 34.6   # 35 mm-equivalent focal lengths are defined on the 43.3 mm diagonal; for the 4:3 sensors
                        # of phones / dashcams that is a 34.6 mm wide frame (36 mm for 3:2 cameras)


def focal_px_from_mm(f_mm, long_side_px, sensor_width_mm=None):
    """Focal length in pixels from a focal length in mm (comma_ai realtime_lead.py).

    sensor_width_mm=None: f_mm is the 35 mm-equivalent focal (what phones advertise, e.g. "26 mm").
    Otherwise f_mm is the real focal length and sensor_width_mm the sensor's long side.
    long_side_px: long side of the camera picture in the video (the picture fills the sensor width;
    not valid if the video was cropped / digitally zoomed / stabilised)."""
    return float(f_mm * long_side_px / (sensor_width_mm or EQUIV_WIDTH_MM))


def focal_px_from_hfov(width_px, hfov_deg, lens='pinhole'):
    """Focal length in pixels from the horizontal field of view of the camera picture. For a fisheye dashcam
    the equidistant model's focal length, which is what matters near the image centre where the lead is."""
    half = np.radians(hfov_deg) / 2
    return float((width_px / 2) / (half if lens == 'fisheye' else np.tan(half)))


def learn_fy(frames, w, h, model, grid=None, progress=None, vel_scale=1.0):
    """Coarse then fine sweep of fy on decoded (y, u, v) frames of a moving vehicle.

    Returns (best_fy, table). `progress(fy, frame)` is called for every frame tried (UI preview). Needs ~10 s of driving; frames should not be the first frames of the
    clip only if the car is stationary there.
    """
    grid = np.arange(0.5, 1.61, 0.1) * w * 0.8 if grid is None else np.asarray(grid)
    coarse, table = _sweep(frames, w, h, model, grid, progress)
    speed = float(np.median([r['speed_mps'] for r in table])) * vel_scale   # frames are model ticks
    if speed < MIN_SPEED:   # nearly stationary: model confidence barely depends on fy, the sweep would guess
        raise ValueError(f'xe chạy quá chậm để học fy ({speed * 3.6:.0f} km/h < {MIN_SPEED * 3.6:.0f} km/h); nhập fy')
    if len(grid) > 1 and coarse in (grid[0], grid[-1]):   # no minimum inside the grid: cuts, zoom, not one camera
        raise ValueError(f'không học được fy (tốt nhất ở biên dải dò, {coarse:.0f} px); nhập fy')
    fine, fine_table = _sweep(frames, w, h, model, coarse * np.arange(0.92, 1.081, 0.02), progress)
    return fine, table + fine_table


def _sweep(frames, w, h, model, fys, progress=None):
    """`model` may be a list of sessions: each takes every n-th fy in its own thread (ONNX Runtime frees the GIL)."""
    models = model if isinstance(model, list) else [model]
    with ThreadPoolExecutor(len(models)) as ex:
        parts = ex.map(lambda k: _sweep_one(frames, w, h, models[k], fys[k::len(models)], progress), range(len(models)))
        table = sorted((r for part in parts for r in part), key=lambda r: r['fy'])
    return min(table, key=lambda r: r['score'])['fy'], table


def _sweep_one(frames, w, h, model, fys, progress):
    table = []
    for fy in fys:
        warps = warp_matrices(intrinsics(fy, w, h), np.zeros(3), w)
        model.reset()
        s = []
        for y, u, v in frames:
            if progress:
                progress(fy, (y, u, v))
            p = model.step(pack_frame(y, u, v, warps))
            s.append([p['pose_stds'][0, :3].mean(), p['road_transform_stds'][0, :3].mean(), p['pose'][0, 0]])
        pose_std, road_std, speed = np.array(s[len(s) // 4:]).mean(0)   # skip temporal-state warm-up
        table.append(dict(fy=float(fy), pose_std=float(pose_std), road_std=float(road_std), speed_mps=float(speed),
                          score=float(np.log(pose_std) + np.log(road_std))))
    return table
