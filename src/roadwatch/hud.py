"""Draw lane lines, the lead vehicle and the status panel on a BGR frame."""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from g01T014VinAI.common.transformations.camera import view_frame_from_device_frame
from g01T014VinAI.common.transformations.orientation import rot_from_euler
from g01T014VinAI.selfdrive.modeld.constants import ModelConstants

from .pipeline import Result

X_IDXS = np.array(ModelConstants.X_IDXS)


def project(cam_k, rpy, pts):
    """Calibrated device-frame points (x forward, y right, z down; origin at camera) -> pixels."""
    uvw = cam_k @ view_frame_from_device_frame @ rot_from_euler(rpy) @ np.asarray(pts, float).T
    with np.errstate(divide='ignore', invalid='ignore'):
        return (uvw[:2] / uvw[2]).T, uvw[2] > 0


def draw(frame, cam_k, r, fy):
    p = r.outputs
    max_x = min(80.0, p['lead'][0, 0, 0, 0]) if r.gap_m is not None else 80.0   # stop lines at the lead vehicle
    for i, prob in enumerate(p['lane_lines_prob'][0, 1::2]):
        if prob > 0.5:
            line = p['lane_lines'][0, i]
            px, ok = project(cam_k, r.rpy, np.c_[X_IDXS, line[:, 0], line[:, 1]])
            cv2.polylines(frame, [px[ok & (X_IDXS < max_x)].astype(np.int32)], False, (0, 255, 0), 2)
    if r.gap_m is not None:
        x, y = p['lead'][0, 0, 0, :2]
        road_z = np.interp(x, X_IDXS, p['lane_lines'][0, 1, :, 1])
        px, ok = project(cam_k, r.rpy, [[x, y, road_z]])
        if ok[0]:
            (u0, v0), half_w, box_h = px[0], int(0.9 * cam_k[0, 0] / x), int(1.5 * cam_k[1, 1] / x)
            col = (0, 0, 255) if r.ttc_s is not None and r.ttc_s < 3 else (0, 200, 255)
            cv2.rectangle(frame, (int(u0) - half_w, int(v0) - box_h), (int(u0) + half_w, int(v0)), col, 3)
    lead = (f'gap {r.gap_m:5.1f} m  lead {r.lead_speed_mps * 3.6:5.1f} km/h' if r.gap_m is not None
            else 'no lead')
    lines = [f'{r.status}  fy={fy:.0f}px  h={r.height_m:.2f}m  pitch={np.degrees(r.rpy[1]):+.2f}'
             f'  yaw={np.degrees(r.rpy[2]):+.2f} deg',
             f'ego {r.ego_speed_mps * 3.6:5.1f} km/h  p={r.lead_prob:.2f}  {lead}'
             + (f'  TTC {r.ttc_s:4.1f} s' if r.ttc_s is not None else '')]
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 70), (0, 0, 0), -1)
    for i, t in enumerate(lines):
        cv2.putText(frame, t, (10, 28 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
    return draw_measurement_panel(frame, r.gap_m, distance_sigma(r), r.ego_speed_mps * 3.6)


def distance_sigma(result: Result) -> float | None:
    """Predicted 1-sigma lead distance uncertainty, absent when unavailable."""
    stds = result.outputs.get('lead_stds')
    if result.gap_m is None or stds is None:
        return None
    value = float(stds[0, 0, 0, 0])
    return value if np.isfinite(value) and value >= 0 else None


@lru_cache(maxsize=1)
def _panel_labels() -> np.ndarray:
    # Raster labels keep Vietnamese accents without adding a font dependency to runtime.
    path = Path(__file__).with_name('assets') / 'hud-labels.png'
    labels = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if labels is None:
        raise FileNotFoundError(f'HUD labels missing: {path}')
    return labels


def draw_measurement_panel(frame: np.ndarray, gap_m: float | None, sigma_m: float | None,
                           ego_kmh: float, radar_m: float | None = None,
                           delta_m: float | None = None) -> np.ndarray:
    """Vietnamese measurement card; radar is only an optional offline reference."""
    labels = _panel_labels()
    width, height = labels.shape[1], labels.shape[0]
    scale = min(1.0, (frame.shape[1] - 20) / width, (frame.shape[0] - 100) / height)
    if scale <= 0:
        return frame
    card = labels[:, :, :3].copy()
    number = lambda value: '--' if value is None else f'{value:.1f}'  # noqa: E731
    cv2.putText(card, number(gap_m) + ' m', (14, 57), cv2.FONT_HERSHEY_SIMPLEX, 1.25, (120, 220, 225), 2)
    values = [number(sigma_m) + ' m', number(radar_m) + ' m',
              ('--' if delta_m is None else f'{delta_m:+.1f}') + ' m', f'{ego_kmh:.0f} km/h']
    for baseline, text in zip((84, 111, 138, 166), values):
        cv2.putText(card, text, (355, baseline), cv2.FONT_HERSHEY_SIMPLEX, .65, (245, 245, 245), 1)
    width, height = max(1, int(width * scale)), max(1, int(height * scale))
    card = cv2.resize(card, (width, height), interpolation=cv2.INTER_AREA)
    x, y = frame.shape[1] - width - 10, 90
    roi = frame[y:y + height, x:x + width]
    cv2.addWeighted(roi, .12, card, .88, 0, dst=roi)
    return frame
