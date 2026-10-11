"""Shared pieces: project paths, the video-to-network input pipeline, ONNX runtime setup and the metrics."""
import csv
import os
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent  # project root; this file lives in src/
RAW = ROOT / "data" / "raw"  # scb*/ with video.hevc, global_pose/ and processed_log/
# The videos the model is trained and judged on: "_v2" = the original 100 and the 254 added later (merge_dataset.py);
# GR14_SET="" = the original 100 alone, as in the earlier rounds.
SET = os.environ.get("GR14_SET", "_v2")
RECIPE = set(os.environ.get("GR14_RECIPE", "zoom+curve+balance").split("+")) - {"", "dataset"}  # how the model is trained: see train_distance.py
LEFT_OUT = {"chang_vang"}  # times of day (manifests/segments.csv) the model is neither trained nor judged on: dusk has only 24 of the 354 videos
DATA = ROOT / "data" / f"prepared_dataset{SET}"

# The networks see a 512x256 window of the 1164x874 frame at the camera's own focal length (910 px), with
# the vanishing point at (256, 47.6): standard perspective crop centred on the vanishing point. So the warp is a
# crop positioned on each camera's vanishing point.
# ponytail: translation only, ignores roll and the perspective part of the mount rotation (fine for a
# few degrees); switch to a full warpPerspective with calibration rpy if mounts are more tilted.
FOCAL, CX, CY, W, H, MODEL_CX, MODEL_CY = 910, 582, 437, 512, 256, 256, 47.6
CAM_H, RADAR_TO_CAMERA = 1.22, 1.5  # camera height above the road; the radar sits about 1.5 m ahead of the camera


def project(dist, y_rel):
    """Where a vehicle's road contact point lands in the 512x256 network window (radar y is positive to the left)."""
    d = dist + RADAR_TO_CAMERA
    return MODEL_CX - FOCAL * y_rel / d, MODEL_CY + FOCAL * CAM_H / d


def vanishing_point(seg):
    """Where the direction of travel hits the image: median of velocity expressed in the camera frame."""
    w, x, y, z = np.load(seg / "global_pose/frame_orientations").T  # ECEF -> [forward, right, down]
    v = np.load(seg / "global_pose/frame_velocities")
    R = np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                  np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                  np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)
    local = np.einsum("nji,nj->ni", R, v)
    local = local[np.linalg.norm(v, axis=1) > 5]  # heading is meaningless when nearly stopped
    return (CX + FOCAL * float(np.median(local[:, 1] / local[:, 0])),
            CY + FOCAL * float(np.median(local[:, 2] / local[:, 0])))


def future_path(scb, AHEAD=120):
    """For every frame: the car's own positions over the next AHEAD frames (6 s), as (metres ahead, metres to the LEFT) of where
    it is heading now. NaN where the video ends first."""
    seg = RAW / scb
    w, x, y, z = np.load(seg / "global_pose/frame_orientations").T
    pos, vel = np.load(seg / "global_pose/frame_positions"), np.load(seg / "global_pose/frame_velocities")
    R = np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                  np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                  np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)
    n = len(pos)
    idx = np.minimum(np.arange(n)[:, None] + np.arange(1, AHEAD + 1)[None], n - 1)
    local = np.einsum("nji,nkj->nki", R, pos[idx] - pos[:, None])  # device frame: forward, right, down
    v = np.einsum("nji,nj->ni", R, vel)
    yaw = np.arctan(np.median(v[:, 1] / v[:, 0]))  # the device is not mounted exactly along the car: remove that angle
    ahead = local[..., 0] * np.cos(yaw) + local[..., 1] * np.sin(yaw)
    left = local[..., 0] * np.sin(yaw) - local[..., 1] * np.cos(yaw)
    beyond = np.arange(n)[:, None] + np.arange(1, AHEAD + 1)[None] > n - 1
    ahead[beyond], left[beyond] = np.nan, np.nan
    return ahead, left, np.linalg.norm(vel, axis=1)


def read_yuv_frames(video, vp, focal=FOCAL, fps=None):
    """Yield each cropped frame as 6 half-resolution YUV420 planes [6,128,256]: the four pixel phases of Y, then U, V.

    vp and focal are in source pixels. Other cameras are rescaled to the 910 px focal length and
    resampled to 20 fps, the rate of the training videos (pass fps=20)."""
    s = FOCAL / focal
    x0, y0 = (2 * round((vp[0] * s - MODEL_CX) / 2), 2 * round((vp[1] * s - MODEL_CY) / 2))  # even, for yuv420
    vf = ([f"fps={fps}"] if fps else []) + ([f"scale=trunc(iw*{s}/2)*2:trunc(ih*{s}/2)*2"] if s != 1 else [])
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", ",".join(vf + [f"crop={W}:{H}:{x0}:{y0}"]),
           "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = W * H * 3 // 2
    while len(buf := proc.stdout.read(n)) == n:
        yuv = np.frombuffer(buf, np.uint8)
        y = yuv[:W * H].reshape(H, W)
        uv = yuv[W * H:].reshape(2, H // 2, W // 2)
        yield np.stack([y[0::2, 0::2], y[1::2, 0::2], y[0::2, 1::2], y[1::2, 1::2], uv[0], uv[1]]).astype(np.float32)
    proc.wait()


def labelled(split):
    """The labelled frames of a split as the model is judged on them: the rows of labels/{split}.csv. For a `curve` model
    "same lane" follows the road, so has_target, distance_m and y_rel_m are those of labels_curved/ (written by
    `train_distance.py curve`) and the frames that labelling leaves out are dropped. lane_left_m: how far the lane centre lies to
    the left of the straight axis at the target's distance (0 for the dataset's own labels)."""
    rows = list(csv.DictReader(open(DATA / f"labels/{split}.csv", encoding="utf-8")))
    if "curve" not in RECIPE:
        return [dict(r, lane_left_m="0") for r in rows]
    curved = list(csv.DictReader(open(DATA / f"labels_curved/{split}.csv", encoding="utf-8")))
    assert [(r["scb_id"], r["frame_index"]) for r in rows] == [(c["scb_id"], c["frame_index"]) for c in curved], "run train_distance.py curve again"
    return [dict(r, has_target=c["has_target"], distance_m=c["distance_m"] or "nan", y_rel_m=c["y_rel_m"], lane_left_m=c["lane_left_m"] or "0")
            for r, c in zip(rows, curved) if c["label_quality"] == "good"]


def time_of_day():
    """scb -> ngay / chang_vang / dem, for the datasets that record it."""
    file = DATA / "manifests/segments.csv"
    return {r["scb_id"]: r["time_of_day"] for r in csv.DictReader(open(file, encoding="utf-8"))} if file.exists() else {}


def balance_weights(meta, night):
    """How likely each training frame is drawn with the `balance` recipe. Frames are grouped by (day, night) x (no target,
    0-20, 20-40, 40-60, 60-80, 80-100 m); a group's share of an epoch is proportional to the square root of its size
    instead of its size, so the rare groups come up more often.
    meta [N, 2+]: has_target (-1 unusable), metres; night [N] bool. Returns probabilities [N] and the group of every frame."""
    # ponytail: the exponent 0.5 is a guess between "as filmed" (1) and "all groups equal" (0), which would repeat the 975
    # night frames under 20 m all epoch long; tune it on validation if it matters
    band = np.where(meta[:, 0] > 0, 1 + np.clip(np.ceil(meta[:, 1] / 20) - 1, 0, 4), 0).astype(int)
    group = band + 6 * night
    usable = meta[:, 0] >= 0
    size = np.bincount(group[usable], minlength=12)
    weight = np.where(usable, 1 / np.sqrt(np.maximum(size[group], 1)), 0.0)
    return weight / weight.sum(), group


def train_median():
    """Median target distance in the training split: the answer of a "model" that never looks at the image."""
    return float(np.median([float(r["distance_m"]) for r in labelled("train") if r["has_target"] == "1"]))


def onnx_session(path):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4  # measured: the default thread count is ~7x slower on this P/E-core CPU
    return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])


def print_metrics(has, dist, prob, pred, threshold=0.5):
    """has/dist: radar label per frame. prob/pred: the model's has-target probability and distance."""
    err = np.abs(pred[has] - dist[has])
    print(f"labelled frames {len(has)}  with target {has.sum()}")
    print(f"distance on radar-target frames: MAE {err.mean():.2f} m  median {np.median(err):.2f} m  "
          f"RMSE {np.sqrt((err ** 2).mean()):.2f} m  corr {np.corrcoef(pred[has], dist[has])[0, 1]:.3f}")
    for lo, hi in [(0, 20), (20, 40), (40, 100)]:
        m = (dist[has] > lo) & (dist[has] <= hi)
        if m.any():
            print(f"  ({lo},{hi}] m: n={m.sum():4d}  MAE {err[m].mean():.2f} m")
    det = prob > threshold
    tp, fp, fn = (det & has).sum(), (det & ~has).sum(), (~det & has).sum()
    print(f"has_target at prob>{threshold:.2f}: precision {tp / max(tp + fp, 1):.3f}  recall {tp / max(tp + fn, 1):.3f}  "
          f"F1 {2 * tp / max(2 * tp + fp + fn, 1):.3f}")
    both = has & det
    if both.any():
        e = np.abs(pred[both] - dist[both])
        print(f"distance where both agree a target exists: n={both.sum()}  MAE {e.mean():.2f} m  median {np.median(e):.2f} m")
