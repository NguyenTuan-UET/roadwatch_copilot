"""Automatic camera calibration from supercombo itself; the only user input is d_cam_bumper.

* fy      : learned by sweeping fy and keeping the warp the model is most confident with
            (lowest pose and road_transform std). A wrong fy feeds the model images unlike its
            training data, and its uncertainty rises.
* pitch/yaw: supercombo pose -> openpilot calibrationd gates and decaying blocks.
* height  : supercombo road_transform.
"""
import numpy as np
from openpilot.common.transformations.orientation import euler_from_rot, rot_from_euler

from .model import pack_frame, warp_maps

# calibrationd constants (pinned commit)
MIN_SPEED = 15 * 0.44704
MAX_YAW_RATE = np.radians(2)
MAX_VEL_ANGLE_STD = np.radians(.25)
MAX_HEIGHT_STD = np.exp(-3.5)
BLOCK_SIZE, INPUTS_NEEDED, INPUTS_WANTED = 100, 5, 50
PITCH_LIMITS = (-0.09074112085129739, 0.17)
YAW_LIMITS = (-0.06912048084718224, 0.06912048084718235)
MAX_YAW_SPREAD, MAX_PITCH_SPREAD = np.radians(2), np.radians(4)
# Phones are re-mounted every trip; openpilot's spread limits (fixed mounts) miss 1-2 deg changes.
REMOUNT_RAD, REMOUNT_BLOCKS = 0.010, 2


def intrinsics(fy, w, h):
    return np.array([[fy, 0, w / 2], [0, fy, h / 2], [0, 0, 1.]])


class BlockCalibration:
    """calibrationd.Calibrator.handle_cam_odom without messaging/persistence.

    Observations are residuals w.r.t. the warp in use (`warp_rpy`), composed back to absolute rpy.
    Speed comes from pose (no carState). Re-mount detection (blocks reset, `resets` counts them):
    calibrationd's spread limits, or REMOUNT_BLOCKS consecutive blocks off the estimate by > REMOUNT_RAD.
    """
    def __init__(self, warp_rpy=None):
        self.warp_rpy = np.zeros(3) if warp_rpy is None else np.asarray(warp_rpy, float)
        self.rpy = self.warp_rpy.copy()
        self.resets = self.off_blocks = 0
        self._clear()

    def _clear(self):
        self.blocks = np.zeros((INPUTS_WANTED, 3))
        self.idx = self.block_idx = self.valid_blocks = 0

    @property
    def calibrated(self):
        return self.valid_blocks >= INPUTS_NEEDED

    def _valid(self):
        return list(range(self.block_idx)) + list(range(min(self.valid_blocks, self.block_idx + 1), self.valid_blocks))

    def update(self, pose, pose_std, road_std):
        """Feed one frame of parsed model output. Returns True if the frame was accepted."""
        fast = pose[0] > MIN_SPEED
        straight = abs(pose[5]) < MAX_YAW_RATE
        certain = np.arctan2(pose_std[1], pose[0]) < MAX_VEL_ANGLE_STD and road_std[2] < MAX_HEIGHT_STD
        if not (fast and straight and (certain or not self.calibrated)):
            return False
        observed = np.array([0., -np.arctan2(pose[2], pose[0]), np.arctan2(pose[1], pose[0])])
        new = euler_from_rot(rot_from_euler(self.warp_rpy) @ rot_from_euler(observed))
        new[1] = np.clip(new[1], PITCH_LIMITS[0] - .005, PITCH_LIMITS[1] + .005)
        new[2] = np.clip(new[2], YAW_LIMITS[0] - .005, YAW_LIMITS[1] + .005)
        self.blocks[self.block_idx] = (self.idx * self.blocks[self.block_idx] + (BLOCK_SIZE - self.idx) * new) / BLOCK_SIZE
        self.idx = (self.idx + 1) % BLOCK_SIZE
        if self.idx == 0:
            self.block_idx += 1
            self.valid_blocks = max(self.block_idx, self.valid_blocks)
            self.block_idx %= INPUTS_WANTED
            valid = self.blocks[self._valid()]
            spread = valid.max(0) - valid.min(0)
            newest = self.blocks[(self.block_idx - 1) % INPUTS_WANTED]
            self.off_blocks = self.off_blocks + 1 if np.abs(newest - self.rpy)[1:].max() > REMOUNT_RAD else 0
            if self.calibrated and (spread[2] > MAX_YAW_SPREAD or spread[1] > MAX_PITCH_SPREAD
                                    or self.off_blocks >= REMOUNT_BLOCKS):
                last = self.blocks[(self.block_idx - 1) % INPUTS_WANTED].copy()
                self._clear()
                self.resets += 1
                self.off_blocks = 0
                self.rpy = last          # restart from the newest block (new mount)
                return True
        valid = self._valid()
        if valid:
            self.rpy = self.blocks[valid].mean(0)
        return True


def learn_fy(frames, w, h, model, grid=None, progress=None):
    """Coarse then fine sweep of fy on decoded (y, u, v) frames of a moving vehicle.

    Returns (best_fy, table). `progress(fy, frame)` is called for every frame tried (UI preview). Needs ~10 s of driving; frames should not be the first frames of the
    clip only if the car is stationary there.
    """
    grid = np.arange(0.5, 1.61, 0.1) * w * 0.8 if grid is None else grid
    coarse, table = _sweep(frames, w, h, model, grid, progress)
    speed = float(np.median([r['speed_mps'] for r in table]))
    if speed < MIN_SPEED:   # nearly stationary: model confidence barely depends on fy, the sweep would guess
        raise ValueError(f'xe chạy quá chậm để học fy ({speed * 3.6:.0f} km/h < {MIN_SPEED * 3.6:.0f} km/h); nhập fy')
    fine, fine_table = _sweep(frames, w, h, model, coarse * np.arange(0.92, 1.081, 0.02), progress)
    return fine, table + fine_table


def _sweep(frames, w, h, model, fys, progress=None):
    table = []
    for fy in fys:
        maps = warp_maps(intrinsics(fy, w, h), np.zeros(3), w, h)
        model.reset()
        s = []
        for y, u, v in frames:
            if progress:
                progress(fy, (y, u, v))
            p = model.step(pack_frame(y, u, v, maps))
            s.append([p['pose_stds'][0, :3].mean(), p['road_transform_stds'][0, :3].mean(), p['pose'][0, 0]])
        pose_std, road_std, speed = np.array(s[len(s) // 4:]).mean(0)   # skip temporal-state warm-up
        table.append(dict(fy=float(fy), pose_std=float(pose_std), road_std=float(road_std), speed_mps=float(speed),
                          score=float(np.log(pose_std) + np.log(road_std))))
    return min(table, key=lambda r: r['score'])['fy'], table
