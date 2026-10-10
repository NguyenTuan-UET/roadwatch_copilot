"""What the training data looks like, measured on the train split only: the numbers the model design is based on.

    python src/analyze_data.py     # -> results/data_analysis.json
"""
import csv
import json

import numpy as np

from common import DATA, FOCAL, RADAR_TO_CAMERA, RAW, ROOT, project
from preprocess_dataset import label_frame, load_arrays


def main():
    rows = list(csv.DictReader(open(DATA / "labels/train.csv", encoding="utf-8")))
    has = np.array([r["has_target"] == "1" for r in rows])
    dist = np.array([float(r["distance_m"]) for r in rows])[has]
    yrel = np.array([float(r["y_rel_m"]) for r in rows if r["has_target"] == "1"])
    u, v = project(dist, yrel)
    width_px = FOCAL * 1.8 / (dist + RADAR_TO_CAMERA)
    out = {"labelled_frames": len(rows), "target_share": float(has.mean()),
           "distance_percentiles_m": {p: round(float(np.percentile(dist, p)), 1) for p in (1, 5, 25, 50, 75, 95, 99)},
           "distance_share": {k: round(float(((dist > lo) & (dist <= hi)).mean()), 3) for k, lo, hi in
                              [("0-20 m", 0, 20), ("20-40 m", 20, 40), ("40-70 m", 40, 70), ("70-100 m", 70, 100)]},
           "contact_point_window_px": {"u_1_99": [round(float(np.percentile(u, 1))), round(float(np.percentile(u, 99)))],
                                       "v_1_99": [round(float(np.percentile(v, 1))), round(float(np.percentile(v, 99)))]},
           "share_inside_fovea": float(((u >= 128) & (u < 384) & (v < 128)).mean()),  # top-centre 256x128 px of the window
           "car_width_px": {p: round(float(np.percentile(width_px, p)), 1) for p in (5, 50, 95)},
           "lateral_share_within_0.3m_of_lane_limit": float((np.abs(yrel) >= 1.2).mean())}

    # label stability between consecutive labelled frames (0.5 s apart) of one video
    flips = jumps = pairs = both = 0
    by_scb = {}
    for r in rows:
        by_scb.setdefault(r["scb_id"], []).append(r)
    for seq in by_scb.values():
        for a, b in zip(seq, seq[1:]):
            pairs += 1
            flips += a["has_target"] != b["has_target"]
            if a["has_target"] == b["has_target"] == "1":
                both += 1
                jumps += abs(float(a["distance_m"]) - float(b["distance_m"])) > 10
    out["label_flips_per_0.5s"] = flips / pairs
    out["distance_jumps_over_10m_per_0.5s"] = jumps / both

    # how many more labelled frames the same videos hold when every frame is labelled with the same radar rule
    params = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))["parameters"]
    dense = usable = 0
    for scb in list(by_scb)[:8]:  # 8 videos are enough for the ratio
        frames, times, values = load_arrays(RAW / scb)
        labels = [label_frame(t, times, values, params["lane_y_meters"], params["max_distance_meters"], params["max_radar_delta_seconds"]) for t in frames]
        dense += len(labels)
        usable += sum(lab["has_target"] is not None for lab in labels)
    out["frames_per_video"] = dense / 8
    out["labelled_per_video_now"] = len(rows) / len(by_scb)
    out["usable_share_when_every_frame_is_labelled"] = usable / dense

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "data_analysis.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
