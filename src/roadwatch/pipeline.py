"""Per-frame pipeline: warp -> supercombo -> calibration feedback -> lead gap and TTC."""
from dataclasses import dataclass

import numpy as np

from .calibration import BlockCalibration, intrinsics
from .model import Supercombo, coverage, pack_frame, warp_maps

REWARP_RAD = 0.002     # rebuild the warp when calibration moves more than this
MIN_COVERAGE = 0.95    # below this the model sees replicated borders, not the scene
LEAD_PROB = 0.5
TTC_MAX_S = 10.0


@dataclass
class Result:
    status: str              # 'calibrating k/5' | 'calibrated' | 'unreliable: <why>'
    rpy: np.ndarray
    height_m: float
    ego_speed_mps: float
    lead_prob: float
    gap_m: float | None      # camera->lead minus d_cam_bumper; None when no confident lead
    lead_speed_mps: float | None
    ttc_s: float | None
    outputs: dict            # parsed supercombo outputs (lane_lines, lead, ...)


class Pipeline:
    def __init__(self, w, h, fy, d_cam_bumper, model=None):
        self.w, self.h, self.d_cam_bumper = w, h, d_cam_bumper
        self.K = intrinsics(fy, w, h)
        self.model = model or Supercombo()
        self.model.reset()
        self.cal = BlockCalibration()
        self.rpy = np.zeros(3)
        self._rewarp(self.rpy)
        self.heights = []

    def _rewarp(self, rpy):
        self.rpy = np.asarray(rpy, float).copy()
        self.maps = warp_maps(self.K, self.rpy, self.w, self.h)
        self.coverage = coverage(self.maps, self.w, self.h)
        self.cal.warp_rpy = self.rpy

    def step(self, y, u, v):
        p = self.model.step(pack_frame(y, u, v, self.maps))
        self.cal.update(p['pose'][0], p['pose_stds'][0], p['road_transform_stds'][0])
        self.heights.append(float(p['road_transform'][0, 2]))
        if self.cal.valid_blocks and np.abs(self.cal.rpy - self.rpy).max() > REWARP_RAD:
            self._rewarp(self.cal.rpy)

        ego = float(p['pose'][0, 0])
        x, _, v_lead, _ = (float(t) for t in p['lead'][0, 0, 0])
        prob = float(p['lead_prob'][0, 0])
        gap = ttc = v_out = None
        if prob >= LEAD_PROB:
            gap, v_out = x - self.d_cam_bumper, v_lead
            closing = ego - v_lead
            if closing > 0.5 and gap / closing < TTC_MAX_S:
                ttc = gap / closing
        if self.coverage < MIN_COVERAGE:
            status = f'unreliable: coverage {self.coverage:.0%}'
        elif self.cal.calibrated:
            status = 'calibrated'
        else:
            status = f'calibrating {self.cal.valid_blocks}/5'
        return Result(status, self.rpy.copy(), float(np.median(self.heights)), ego, prob, gap, v_out, ttc, p)
