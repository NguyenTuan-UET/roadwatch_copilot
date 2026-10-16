"""Geometric baseline: distance to the lead vehicle from a bounding box and the pinhole camera model, no learning.

    python src/geometry.py     # -> eval/results/geometry_predictions.csv for every labelled test frame

A vehicle standing on a flat road touches it at image row y_bottom. With the camera H metres above the road,
focal length f pixels and the horizon at row vp_y:      distance = f * H / (y_bottom - vp_y)
The lead is the nearest detected vehicle whose centre lies within 1.5 m of the lane centre, the same rule the
radar labels use. Vehicles are found with torchvision's COCO detector, whose weights are downloaded on first use.
"""
import csv
import sys

import numpy as np

from common import CAM_H, DATA, EVAL, FOCAL, RAW, ROOT, labelled, vanishing_point

LANE_HALF_M = 1.5  # lateral tolerance, as in the radar label rule
MAX_M = 100.0
MIN_M = 5.0  # the road closer than this is hidden by the car's own hood, which the detector reports as a "car" at 2 m
VEHICLES = {3, 4, 6, 8}  # COCO: car, motorcycle, bus, truck
OUT = EVAL / "results" / "geometry_predictions.csv"


def distance_from_box(box, vp):
    """box = (x1, y1, x2, y2) in pixels. None when the box bottom is not below the horizon."""
    drop = box[3] - vp[1]
    return FOCAL * CAM_H / drop if drop > 0 else None


def pick_lead(boxes, vp):
    """Distance to the nearest in-lane vehicle within MAX_M, or None when there is none."""
    best = None
    for box in boxes:
        d = distance_from_box(box, vp)
        if d is None or not MIN_M <= d <= MAX_M:
            continue
        lateral_m = ((box[0] + box[2]) / 2 - vp[0]) * d / FOCAL
        if abs(lateral_m) <= LANE_HALF_M and (best is None or d < best):
            best = d
    return best


def main():
    import torch
    from torchvision.io import read_image
    from torchvision.models.detection import FasterRCNN_MobileNet_V3_Large_FPN_Weights, fasterrcnn_mobilenet_v3_large_fpn
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    detector = fasterrcnn_mobilenet_v3_large_fpn(weights=FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT).to(dev).eval()
    rows = labelled("test")
    vps = {s: vanishing_point(RAW / s) for s in {r["scb_id"] for r in rows}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f, torch.no_grad():
        w = csv.writer(f)
        w.writerow(["scb_id", "frame_index", "has_target", "distance_m"])
        for r in rows:
            det = detector([read_image(str(DATA / r["image_path"])).to(dev) / 255])[0]
            keep = (det["scores"] >= 0.5) & torch.tensor([int(c) in VEHICLES for c in det["labels"]], dtype=torch.bool, device=dev)  # bool also when nothing is detected
            d = pick_lead(det["boxes"][keep].cpu().numpy(), vps[r["scb_id"]])
            w.writerow([r["scb_id"], r["frame_index"], int(d is not None), "" if d is None else f"{d:.2f}"])
    print(f"wrote {OUT}")


def demo():
    vp = (600.0, 400.0)
    assert np.isclose(distance_from_box((550, 380, 650, 400 + 910 * 1.22 / 50), vp), 50)  # bottom 22.2 px below horizon
    assert distance_from_box((550, 300, 650, 390), vp) is None  # above the horizon: not on the road
    near, far, side = (500, 300, 700, 400 + 910 * 1.22 / 20), (580, 380, 620, 400 + 910 * 1.22 / 60), (900, 380, 990, 400 + 910 * 1.22 / 30)
    assert np.isclose(pick_lead([far, side], vp), 60)  # the 30 m car is 9 m to the side: ignored
    assert np.isclose(pick_lead([far, near, side], vp), 20)
    assert pick_lead([side], vp) is None
    hood = (100, 600, 1100, 400 + 910 * 1.22 / 2.4)
    assert np.isclose(pick_lead([hood, far], vp), 60)  # the own hood must not hide the real lead
    print("geometry self-check passed")


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["check"] else main()
