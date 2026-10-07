"""Draw lane lines, the lead vehicle and the status panel on a BGR frame."""
import cv2
import numpy as np
from g01T014VinAI.common.transformations.camera import view_frame_from_device_frame
from g01T014VinAI.common.transformations.orientation import rot_from_euler
from g01T014VinAI.selfdrive.modeld.constants import ModelConstants

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
    return frame
