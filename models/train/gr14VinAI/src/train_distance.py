"""Train, evaluate and export gr14VinAI (the network itself is in distance_model.py).

    python src/train_distance.py prepare   # labelled frames of all splits -> data/cache/{train,val,test}_{x,y}.npy       (once)
    python src/train_distance.py dense     # every frame of the training videos, labelled by the same radar rule
                                  #   -> data/cache/dense_{x,y}.npy, about 19 GB                                   (once)
    python src/train_distance.py radar     # what the radar saw around every train and validation frame -> data/cache/*_r.npy   (once)
    python src/train_distance.py curve     # labels whose corridor follows the road -> data/cache/*_c.npy, labels_curved/*.csv           (once)
    python src/train_distance.py train     # -> model/gr14VinAI.pt (best validation epoch)
    python src/train_distance.py eval      # metrics on the test split
    python src/train_distance.py export    # -> model/gr14VinAI.onnx and model/gr14VinAI.json
    python src/train_distance.py videos    # the .onnx on every frame of the test videos -> results/gr14vinai/preds_*.csv

Everything runs on the videos of dataset "_v2" (common.SET). `train` on its own repeats the recipe of the model in model/:
GR14_RECIPE=zoom+curve+balance, GR14_SEED=2. Recipes are words joined by "+" (GR14_RECIPE=dataset is the plain recipe of the first rounds):
    radar   labels from the radar objects instead of the dataset's own (docs/label_processing.md)
    zoom    magnify each frame about the vanishing point, labels follow exactly
    sides   half the frames get the left and right quarters of another frame
    small   context stream at half its width
    curve   "same lane" follows the road instead of the straight axis: labels from `curve`, and a head that says where the lane goes
    balance draw rare kinds of frames more often (night; vehicles under 20 m and beyond 80 m): common.balance_weights
    soft    with curve: near the 100 m limit and the lane edge the has_target label is soft instead of 0 or 1 (curved_soft)
GR14_SEED picks another random seed; GR14_CKPT=<file.pt> keeps an experiment from touching model/gr14VinAI.pt.
"""
import copy
import csv
import json
import math
import os
import queue
import sys
import threading
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from distance_model import BINS, CELL, FOVEA, LANE, MAX_M, MIRROR, PATH_AT, PATH_UNIT, Deploy, Gr14VinAI, Mirrored
from common import (DATA, FOCAL, LEFT_OUT, MODEL_CY, RAW, RECIPE, ROOT, SET, balance_weights, future_path, onnx_session, print_metrics, project,
                    read_yuv_frames, time_of_day, train_median, vanishing_point)

CACHE = ROOT / "data" / f"cache{SET}"  # model-ready frames cut from the videos by `prepare` and `dense`
WORK = ROOT / "results" / "gr14vinai"
BASELINE = ROOT / "results" / "baseline"  # the reference model's predictions, compared against when present
ONNX = ROOT / "model" / "gr14VinAI.onnx"
CKPT = Path(os.environ.get("GR14_CKPT", ONNX.with_suffix(".pt")))  # PyTorch weights of the best validation epoch
assert RECIPE <= {"radar", "zoom", "sides", "small", "curve", "balance", "soft"}, RECIPE
SEED = int(os.environ.get("GR14_SEED", 2))
SLOTS = 8  # radar objects kept per frame
PATH_KNOTS = np.arange(10.0, 131.0, 10.0)  # metres ahead at which the lane path of every frame is stored

# ---------------------------------------------------------------- data

def prepare():
    """Cut every labelled frame and the frame before it out of the videos, in the network's input layout."""
    from concurrent.futures import ThreadPoolExecutor
    CACHE.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        rows = list(csv.DictReader(open(DATA / "labels" / f"{split}.csv", encoding="utf-8")))
        wanted = {}  # scb -> {frame_index: row number}
        for n, r in enumerate(rows):
            wanted.setdefault(r["scb_id"], {})[int(r["frame_index"])] = n
        if SET and split == "train":  # training reads dense_x.npy; of these rows only the labels are used
            wanted = {}
        x = np.lib.format.open_memmap(CACHE / f"{split}_x.npy", "w+", np.uint8, (len(rows) if wanted else 0, 12, 128, 256))

        def load(scb):
            prev, i = None, -1
            for i, frame in enumerate(read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb))):
                if i in wanted[scb]:
                    x[wanted[scb][i]] = np.concatenate([frame if prev is None else prev, frame])
                prev = frame
            assert i >= max(wanted[scb]), f"{scb}: video ended at frame {i}, labels go to {max(wanted[scb])}"

        with ThreadPoolExecutor(4) as pool:
            list(pool.map(load, wanted))
        x.flush()
        has = [r["has_target"] == "1" for r in rows]
        np.save(CACHE / f"{split}_y.npy", np.array([[h, float(r["distance_m"]) if h else 0] for h, r in zip(has, rows)], np.float32))
        print(f"{split}: {len(rows)} samples from {len(wanted)} SCBs, {sum(has)} with target", flush=True)


def dense():
    """Every frame of the training videos with the label the dataset's own radar rule gives it: 10x the labelled frames."""
    from concurrent.futures import ThreadPoolExecutor
    from preprocess_dataset import label_frame, load_arrays
    manifest = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))
    rule, scbs = manifest["parameters"], manifest["splits"]["train"]
    arrays = {scb: load_arrays(RAW / scb) for scb in scbs}
    start = dict(zip(scbs, np.cumsum([0] + [len(arrays[scb][0]) for scb in scbs]).tolist()))
    total = sum(len(arrays[scb][0]) for scb in scbs)
    CACHE.mkdir(parents=True, exist_ok=True)
    x = np.lib.format.open_memmap(CACHE / "dense_x.npy", "w+", np.uint8, (total, 6, 128, 256))
    meta = np.zeros((total, 4), np.float32)  # has_target (-1: no usable radar), distance, sideways offset, first frame of its video

    def load(scb):
        frames, times, values = arrays[scb]
        n = 0
        for n, frame in enumerate(read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb)), 1):
            x[start[scb] + n - 1] = frame
        assert n == len(frames), f"{scb}: decoded {n} frames, frame_times has {len(frames)}"
        for i, t in enumerate(frames):
            lab = label_frame(t, times, values, rule["lane_y_meters"], rule["max_distance_meters"], rule["max_radar_delta_seconds"])
            has = lab["has_target"]
            meta[start[scb] + i] = (-1 if has is None else has, lab["distance_m"] if has else 0, lab["y_rel_m"] if has else 0, i == 0)

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(load, scbs))
    x.flush()
    for r in csv.DictReader(open(DATA / "labels/train.csv", encoding="utf-8")):  # the labelled frames must come out as in the CSV
        has, dist = meta[start[r["scb_id"]] + int(r["frame_index"]), :2]
        assert has == int(r["has_target"]) and (not has or abs(dist - float(r["distance_m"])) < 1e-3), f"label mismatch at {r['image_path']}"
    np.save(CACHE / "dense_y.npy", meta)
    print(f"dense: {total} frames from {len(scbs)} SCBs, {int((meta[:, 0] >= 0).sum())} usable, {int((meta[:, 0] > 0).sum())} with target")


def radar():
    """What the radar saw around every training and validation frame, beyond the one number the label keeps.

    The dataset's label is the nearest radar object inside a box: within 1.5 m of the car's axis, up to 100 m ahead.
    Kept here per frame: the moving objects up to 180 m ahead and 3.5 m to the side (metres ahead, metres left, nearest
    first), and a flag for a label no camera can learn: the "target" stands still on the road while we drive (a bridge
    or a sign that the radar reports) and no moving vehicle is in the box.
    -> data/cache/{dense,val}_r.npy [N, 1 + 2*SLOTS]: flag, then SLOTS x (ahead, left); 0 = empty slot"""
    from preprocess_dataset import load_arrays
    manifest = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))
    rule = manifest["parameters"]
    assert (rule["lane_y_meters"], rule["max_distance_meters"]) == (LANE, MAX_M)

    def objects(scb, frame_times):
        _, times, values = load_arrays(RAW / scb)
        speed_t, speed = np.load(RAW / scb / "processed_log/CAN/speed/t"), np.load(RAW / scb / "processed_log/CAN/speed/value")[:, 0]
        out, official = np.zeros((len(frame_times), 1 + 2 * SLOTS), np.float32), np.zeros((len(frame_times), 2), np.float32)
        for n, t in enumerate(frame_times):
            near = {}  # the dataset's matching: of every radar track, the update closest in time to the frame
            for i in range(np.searchsorted(times, t - rule["max_radar_delta_seconds"], "left"),
                           np.searchsorted(times, t + rule["max_radar_delta_seconds"], "right")):
                if (k := values[i, 5]) not in near or abs(times[i] - t) < abs(times[near[k]] - t):
                    near[k] = i
            rows = values[list(near.values())]
            rows = rows[np.isfinite(rows[:, :2]).all(1) & (rows[:, 0] > 0) & ~np.isclose(rows[:, 0], 258.6375, rtol=0, atol=1e-4)]
            rows = rows[np.argsort(rows[:, 0], kind="stable")]
            moving = np.abs(rows[:, 2] + np.interp(t, speed_t, speed)) >= 3  # m/s over the ground; every video is at speed
            box = (rows[:, 0] <= MAX_M) & (np.abs(rows[:, 1]) <= LANE)
            if box.any():
                official[n] = 1, rows[box][0, 0]
            out[n, 0] = box.any() and not (box & moving).any()
            keep = rows[moving & (rows[:, 0] <= 180) & (np.abs(rows[:, 1]) <= 3.5)][:SLOTS, :2]
            out[n, 1:1 + 2 * len(keep)] = keep.ravel()
        return out, official

    from concurrent.futures import ThreadPoolExecutor
    scbs = manifest["splits"]["train"]
    with ThreadPoolExecutor(4) as pool:
        parts = list(pool.map(lambda scb: objects(scb, load_arrays(RAW / scb)[0]), scbs))
    rich, official = (np.concatenate(a) for a in zip(*parts))
    meta = np.load(CACHE / "dense_y.npy")
    ok = meta[:, 0] >= 0  # the dataset's own label must come out of the same radar rows
    assert (official[ok, 0] == meta[ok, 0]).all() and np.allclose(official[ok, 1], meta[ok, 1], atol=1e-3), "radar matching differs from the dataset's"
    np.save(CACHE / "dense_r.npy", rich)

    rows = list(csv.DictReader(open(DATA / "labels/val.csv", encoding="utf-8")))
    val = np.zeros((len(rows), 1 + 2 * SLOTS), np.float32)
    for scb in dict.fromkeys(r["scb_id"] for r in rows):
        index = [n for n, r in enumerate(rows) if r["scb_id"] == scb]
        val[index], official = objects(scb, [float(rows[n]["frame_time"]) for n in index])
        assert (official[:, 0] == [int(rows[n]["has_target"]) for n in index]).all(), "radar matching differs from the dataset's"
    np.save(CACHE / "val_r.npy", val)
    for name, r, has in (("train", rich[ok], meta[ok, 0] > 0), ("val", val, np.array([r["has_target"] == "1" for r in rows]))):
        _, soft, seen, _, _ = lead(torch.from_numpy(r))
        print(f"{name}: {len(r)} frames | target frames whose target stands still: {r[has, 0].mean():.1%} | "
              f"no-target frames with a vehicle just outside the box: {seen[~has].float().mean():.1%} | "
              f"target frames the soft label puts under 0.9: {(soft[has & (r[:, 0] == 0)] < 0.9).float().mean():.1%}")


def curve():
    """Labels whose corridor follows the road. The dataset keeps a radar object when it is within 1.5 m of the car's straight
    axis; on a bend the lane leaves that axis (at 100 m by more than 1.5 m in half of all frames). Here an object is kept when

        | yRel - lane(dRel) | <= 1.5 m     and     0 < dRel <= 100 m

    where lane(d) is how far the lane lies to the left of the straight axis d metres ahead: the path the car itself drove in
    the next seconds, from global_pose. Nothing but the dataset's own recordings is used. A frame is left out (has_target -1)
    when the radar is missing, when the video ends before the car has driven the 100 m ahead (the last seconds of a video),
    or when its video was filmed at a time of day in common.LEFT_OUT.
    Beyond 100 m, where only magnified training frames look, the path is continued as an arc of the same curvature.

    -> data/cache/{dense,val,test}_c.npy [N, 4 + 13 + 3*SLOTS]: has_target, metres, yRel, first frame of its video;
       lane(d) at PATH_KNOTS; SLOTS moving radar objects x (metres ahead, yRel, yRel - lane), nearest first, 0 = empty slot
    -> data/prepared_dataset/labels_curved/{split}.csv for reading"""
    from preprocess_dataset import load_arrays
    manifest = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))
    rule = manifest["parameters"]
    assert (rule["lane_y_meters"], rule["max_distance_meters"]) == (LANE, MAX_M)
    knots = np.concatenate([[0], PATH_KNOTS])
    light = time_of_day()

    def frames_of(scb):
        frame_times, times, values = load_arrays(RAW / scb)
        speed_t, speed = np.load(RAW / scb / "processed_log/CAN/speed/t"), np.load(RAW / scb / "processed_log/CAN/speed/value")[:, 0]
        ahead, left, _ = future_path(scb, 160)  # 8 s: 100 m even at the slowest speeds in the data
        out, why = np.zeros((len(frame_times), 4 + len(PATH_KNOTS) + 3 * SLOTS), np.float32), []
        for i, t in enumerate(frame_times):
            a, l = ahead[i], left[i]
            ok = np.isfinite(a)
            reach = a[ok][-1] if ok.any() else 0.0
            out[i, 3] = i == 0
            if light.get(scb) in LEFT_OUT:
                out[i, 0] = -1
                why.append("left_out")
                continue
            if reach < MAX_M:
                out[i, 0] = -1
                why.append("path_too_short")
                continue
            path = np.interp(PATH_KNOTS, np.concatenate([[0], a[ok]]), np.concatenate([[0], l[ok]]))
            beyond = PATH_KNOTS > reach
            path[beyond] = np.interp(reach, np.concatenate([[0], a[ok]]), np.concatenate([[0], l[ok]])) * (PATH_KNOTS[beyond] / reach) ** 2
            out[i, 4:4 + len(PATH_KNOTS)] = path
            near = {}  # the dataset's matching: of every radar track, the update closest in time to the frame
            for k in range(np.searchsorted(times, t - rule["max_radar_delta_seconds"], "left"),
                           np.searchsorted(times, t + rule["max_radar_delta_seconds"], "right")):
                if (track := values[k, 5]) not in near or abs(times[k] - t) < abs(times[near[track]] - t):
                    near[track] = k
            rows = values[list(near.values())] if near else np.zeros((0, 7))
            rows = rows[np.isfinite(rows[:, :2]).all(1)]
            if not len(rows):
                out[i, 0] = -1
                why.append("no_radar")
                continue
            why.append("good")
            rows = rows[(rows[:, 0] > 0) & ~np.isclose(rows[:, 0], 258.6375, rtol=0, atol=1e-4)]
            rows = rows[np.argsort(rows[:, 0], kind="stable")]
            rel = rows[:, 1] - np.interp(rows[:, 0], knots, np.concatenate([[0], path]))
            inside = rows[(rows[:, 0] <= MAX_M) & (np.abs(rel) <= LANE)]
            if len(inside):
                out[i, :3] = 1, inside[0, 0], inside[0, 1]
            moving = np.abs(rows[:, 2] + np.interp(t, speed_t, speed)) >= 3  # m/s over the ground
            keep = np.column_stack([rows[:, 0], rows[:, 1], rel])[moving & (rows[:, 0] <= 180) & (np.abs(rel) <= 3.5)][:SLOTS]
            out[i, 4 + len(PATH_KNOTS):4 + len(PATH_KNOTS) + 3 * len(keep)] = keep.ravel()
        return out, why

    from concurrent.futures import ThreadPoolExecutor
    scbs = manifest["splits"]["train"]
    with ThreadPoolExecutor(4) as pool:
        parts = list(pool.map(frames_of, scbs))
    dense = np.concatenate([p[0] for p in parts])
    old = np.load(CACHE / "dense_y.npy")
    assert len(dense) == len(old) and (dense[:, 3] == old[:, 3]).all(), "frames do not line up with data/cache/dense_x.npy"
    np.save(CACHE / "dense_c.npy", dense)
    both = (dense[:, 0] >= 0) & (old[:, 0] >= 0)
    print(f"train, every frame: {len(dense)} frames, {int((dense[:, 0] >= 0).sum())} usable ({np.mean([w == 'path_too_short' for p in parts for w in p[1]]):.1%} at the end of a video), "
          f"{(dense[:, 0] > 0).sum() / (dense[:, 0] >= 0).sum():.1%} with a target | label differs from the straight corridor in "
          f"{((dense[both, 0] != old[both, 0]) | (np.abs(dense[both, 1] - old[both, 1]) > 0.5)).mean():.1%} of the frames usable in both")

    (DATA / "labels_curved").mkdir(exist_ok=True)
    for split in ("train", "val", "test"):
        rows = list(csv.DictReader(open(DATA / "labels" / f"{split}.csv", encoding="utf-8")))
        done = dict(zip(scbs, parts)) if split == "train" else {scb: frames_of(scb) for scb in dict.fromkeys(r["scb_id"] for r in rows)}
        labels = np.stack([done[r["scb_id"]][0][int(r["frame_index"])] for r in rows])
        why = [done[r["scb_id"]][1][int(r["frame_index"])] for r in rows]
        if split != "train":
            np.save(CACHE / f"{split}_c.npy", labels)
        with open(DATA / "labels_curved" / f"{split}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["scb_id", "frame_index", "label_quality", "has_target", "distance_m", "y_rel_m", "lane_left_m", "straight_corridor_has_target", "straight_corridor_distance_m"])
            for r, c, q in zip(rows, labels, why):
                has = c[0] > 0
                lane = np.interp(c[1], knots, np.concatenate([[0], c[4:4 + len(PATH_KNOTS)]])) if has else ""
                w.writerow([r["scb_id"], r["frame_index"], q, "" if c[0] < 0 else int(has), f"{c[1]:.4f}" if has else "", f"{c[2]:.4f}" if has else "",
                            f"{lane:.3f}" if has else "", r["has_target"], r["distance_m"] if r["has_target"] == "1" else ""])
        good = labels[:, 0] >= 0
        was = np.array([r["has_target"] == "1" for r in rows])
        print(f"{split}: {len(rows)} labelled frames, {int(good.sum())} usable ({np.mean([q == 'path_too_short' for q in why]):.1%} at the end of a video), {int((labels[:, 0] > 0).sum())} with a target "
              f"(straight corridor: {int(was.sum())}) | has_target differs in {(was[good] != (labels[good, 0] > 0)).mean():.1%} of the usable frames")


def load(split):
    return np.load(CACHE / f"{split}_x.npy", mmap_mode="r"), np.load(CACHE / f"{split}_y.npy")


def judged(split):
    """The frames and labels [has_target, metres] a model is scored on: the dataset's own, or for a `curve` model the usable
    frames of the labels whose corridor follows the road. Same frames, same order as common.labelled(split)."""
    x, y = load(split)
    if "curve" not in RECIPE:
        return x, y
    c = np.load(CACHE / f"{split}_c.npy")
    keep = np.flatnonzero(c[:, 0] >= 0)
    return x[keep], c[keep, :2]


def batches(x, y, size, dev, shuffle=False):
    order = np.random.permutation(len(x)) if shuffle else np.arange(len(x))
    for i in range(0, len(x), size):
        j = np.sort(order[i:i + size])  # sorted: sequential reads from the memory-mapped file
        yield torch.from_numpy(x[j]).to(dev).float(), torch.from_numpy(y[j]).to(dev)


def dense_batches(x, meta, rich, size, count, dev, weight=None):
    """`count` random labelled frames, each with the frame before it, the dataset's label (has_target, metres, metres left)
    and its radar objects; a background thread reads ahead from disk. weight: common.balance_weights, or None for "as filmed"."""
    picks = (np.random.choice(np.flatnonzero(meta[:, 0] >= 0), count, replace=False) if weight is None
             else np.random.choice(len(meta), count, replace=False, p=weight))
    ready = queue.Queue(maxsize=6)

    def reader():
        for i in range(0, count, size):
            j = np.sort(picks[i:i + size])
            before = j - (meta[j, 3] == 0)  # the first frame of a video is paired with itself
            ready.put((torch.from_numpy(np.concatenate([x[before], x[j]], 1)), torch.from_numpy(np.concatenate([meta[j, :3], rich[j]], 1))))
        ready.put(None)

    threading.Thread(target=reader, daemon=True).start()
    while (item := ready.get()) is not None:
        yield item[0].to(dev).float(), item[1].to(dev)


LUMA = [0, 1, 2, 3, 6, 7, 8, 9]


ZOOM = (0.8, 1.3) if "zoom" in RECIPE else None


def magnify(x, s):
    """Magnify each image about the vanishing point by its own factor s [B]. Through a pinhole camera that is exactly the
    picture of the same road with everything s times closer (same size, same sideways offset): labels follow as d / s."""
    weave = lambda p: F.pixel_shuffle(p[:, [0, 2, 1, 3]], 2)  # the 4 luma planes back into full-resolution pixels
    luma, chroma = torch.cat([weave(x[:, 0:4]), weave(x[:, 6:10])], 1), x[:, [4, 5, 10, 11]]
    theta = torch.zeros(len(x), 2, 3, device=x.device)
    theta[:, 0, 0] = theta[:, 1, 1] = 1 / s
    theta[:, 1, 2] = (2 * MODEL_CY / luma.shape[2] - 1) * (1 - 1 / s)  # the vanishing point stays put (it is centred sideways)
    resample = lambda img: F.grid_sample(img, F.affine_grid(theta, img.shape, align_corners=False), padding_mode="border", align_corners=False)
    luma, chroma = resample(luma), resample(chroma)
    planes = lambda y: F.pixel_unshuffle(y, 2)[:, [0, 2, 1, 3]]
    return torch.cat([planes(luma[:, :1]), chroma[:, :2], planes(luma[:, 1:]), chroma[:, 2:]], 1)


def augment(x):
    """Magnify, swap the sides, mirror, shift by up to 4 px, change brightness (the first two only in experiments).
    Returns the images and how they moved: (mirrored?, px right, px down, magnification)."""
    zoom = torch.ones(len(x), device=x.device)
    if ZOOM:
        zoom = torch.empty(len(x), device=x.device).uniform_(math.log(ZOOM[0]), math.log(ZOOM[1])).exp()
        zoom[torch.rand(len(x), device=x.device) < 0.25] = 1  # a quarter of the frames stay as filmed
        x = magnify(x, zoom)
    if "sides" in RECIPE:  # the lead is in the middle (99.8 %); with someone else's surroundings the scene cannot be memorised from them
        other = x[torch.randperm(len(x), device=x.device)]
        swap = (torch.rand(len(x), device=x.device) < 0.5)[:, None, None, None]
        outer = torch.ones(1, 1, 1, x.shape[3], dtype=torch.bool, device=x.device)
        outer[..., FOVEA[2]:FOVEA[3]] = False
        x = torch.where(swap & outer, other, x)
    flip = torch.rand(len(x), device=x.device) < 0.5
    x = torch.where(flip[:, None, None, None], x.flip(-1)[:, MIRROR], x)
    dy, dx = torch.randint(0, 5, (2,)).tolist()
    x = F.pad(x, (2, 2, 2, 2), mode="replicate")[:, :, dy:dy + 128, dx:dx + 256].clone()
    x[:, LUMA] = (x[:, LUMA] * torch.empty(len(x), 1, 1, 1, device=x.device).uniform_(0.8, 1.2)).clamp(0, 255)
    return x, (flip, 2 * (2 - dx), 2 * (2 - dy), zoom)


# ---------------------------------------------------------------- training

SHARP_M, SHARP_Y = 3.0, 0.12  # how sharply a camera can place a vehicle against the 100 m and the 1.5 m limit
FAR = BINS[-1].item()  # the furthest distance the head can say


def lead(radar, zoom=1.0):
    """What a camera can be expected to say about a frame, from its moving radar objects [B, 1 + 2*SLOTS] (see `radar`).

    The dataset's label flips at the edges of its box: a car at 99 m is a target, at 101 m it is not. No camera sees that
    cliff, so near the limits the has_target label is soft. And when no vehicle is in the box but one is just outside (up to
    130 m ahead or 1 m beyond the lane limit) that vehicle is still described, so the network learns both sides of the limits.
    Returns (label unusable, soft has_target, a vehicle to describe?, its metres ahead, its metres to the left)."""
    d, y = radar[:, 1::2] / zoom, radar[:, 2::2]
    real = d > 0
    score = torch.sigmoid((MAX_M - d) / SHARP_M) * torch.sigmoid((LANE - y.abs()) / SHARP_Y) * real
    outside = (d - MAX_M).clamp(min=0) / 30 + (y.abs() - LANE).clamp(min=0)  # 0 inside the box
    k = torch.where(real, outside * 1e3 + d, torch.inf).argmin(1, keepdim=True)  # inside the box: the nearest, as in the dataset
    pick = lambda t: t.gather(1, k)[:, 0]
    return radar[:, 0] > 0, score.amax(1), pick(real) & (pick(outside) <= 1), pick(d), pick(y)


def hard(y, radar=None, zoom=None):
    """The dataset's own label [B,2] (has_target, metres; training frames add metres to the left), in the form `criterion` takes.
    Magnified, the 100 m limit lies at 100 m x zoom of the scene as filmed: a target beyond it stops being one, and a
    vehicle the radar saw between the old limit and the new one becomes one (that needs the frame's radar objects)."""
    has, dist = y[:, 0] > 0, y[:, 1]
    side = y[:, 2] if y.shape[1] > 2 else torch.zeros_like(dist)
    if zoom is not None:
        dist = dist / zoom
        has = has & (dist <= MAX_M)
        d, left = radar[:, 1::2] / zoom[:, None], radar[:, 2::2]
        near, k = torch.where((d > 0) & (d <= MAX_M) & (left.abs() <= LANE), d, torch.inf).min(1)
        new = ~has & near.isfinite()
        has, dist, side = has | new, torch.where(new, near, dist) * (has | new), torch.where(new, left.gather(1, k[:, None])[:, 0], side)
    return torch.zeros(len(y), dtype=torch.bool, device=y.device), has.float(), has, dist, side


def curved(y, zoom):
    """The labels of `curve` for a batch [B, 3 + 13 + 3*SLOTS] (has_target, metres, yRel, lane path, radar objects), magnified:
    a target beyond 100 m x zoom stops being one, and a vehicle the radar saw in the lane beyond the old limit becomes one."""
    has, dist, side = y[:, 0] > 0, y[:, 1] / zoom, y[:, 2]
    has = has & (dist <= MAX_M)
    o = y[:, 3 + len(PATH_KNOTS):].reshape(len(y), SLOTS, 3)
    d = o[..., 0] / zoom[:, None]
    near, k = torch.where((o[..., 0] > 0) & (d <= MAX_M) & (o[..., 2].abs() <= LANE), d, torch.inf).min(1)
    new = ~has & near.isfinite()
    has = has | new
    return (torch.zeros(len(y), dtype=torch.bool, device=y.device), has.float(), has, torch.where(new, near, dist) * has,
            torch.where(new, o[..., 1].gather(1, k[:, None])[:, 0], side))


def curved_soft(y, zoom):
    """`curved` for the `soft` recipe: what a camera can be expected to say, as `lead` does for the straight corridor.
    The label of `curve` flips at 100 m and at 1.5 m from the lane centre; here it is soft there (0.5 exactly on a limit),
    and when no vehicle is in the lane but one is just outside (up to 130 m ahead or 1 m beyond the lane edge) that vehicle
    is still described. Away from the limits nothing changes: the label's own target, moving or standing, stays the answer."""
    own = torch.stack([y[:, 1], y[:, 2], y[:, 2] - lane_at(y[:, 3:3 + len(PATH_KNOTS)], y[:, 1:2])[:, 0]], 1) * (y[:, :1] > 0)
    o = torch.cat([own[:, None], y[:, 3 + len(PATH_KNOTS):].reshape(len(y), SLOTS, 3)], 1)  # the label's target, then the moving radar objects
    d, side, off = o[..., 0] / zoom[:, None], o[..., 1], o[..., 2].abs()  # metres ahead, yRel, metres from the lane centre
    real = o[..., 0] > 0
    score = torch.sigmoid((MAX_M - d) / SHARP_M) * torch.sigmoid((LANE - off) / SHARP_Y) * real
    outside = (d - MAX_M).clamp(min=0) / 30 + (off - LANE).clamp(min=0)  # 0 inside the corridor
    k = torch.where(real, (outside > 0) * 1e4 + outside * 1e3 + d, torch.inf).argmin(1, keepdim=True)  # the nearest inside, as in the label; else the nearest to the corridor
    pick = lambda t: t.gather(1, k)[:, 0]
    seen = pick(real) & (pick(outside) <= 1)
    return torch.zeros(len(y), dtype=torch.bool, device=y.device), score.amax(1), seen, pick(d) * seen, pick(side) * seen


def lane_at(path, d):
    """The stored lane path [B,13] (metres to the left at PATH_KNOTS) read at the distances d [B,K]; at 0 m it is 0."""
    full = F.pad(path, (1, 0))
    i = (d / 10).floor().clamp(0, len(PATH_KNOTS) - 1).long()
    part = (d / 10 - i).clamp(0, 1)
    return full.gather(1, i) * (1 - part) + full.gather(1, i + 1) * part


def path_loss(pred, y, moved, zoom):
    """Teach the path head where the lane goes, from the path the car really drove."""
    flip, right, _ = moved
    at = torch.tensor(PATH_AT, device=pred.device)[None]
    want = lane_at(y[:, 3:3 + len(PATH_KNOTS)], at * zoom[:, None])  # magnified, the road seen at d is the road filmed at d x zoom
    want = torch.where(flip[:, None], -want, want) - right * at / FOCAL  # mirrored; then everything moved `right` px to the right
    return F.smooth_l1_loss(pred, want / PATH_UNIT.to(pred.device), beta=0.05)


def criterion(logit, d, labels):
    """The score checkpoints are chosen by: classification on every usable frame, distance where there is a vehicle to describe."""
    unusable, soft, seen, dist, _ = labels
    loss = F.binary_cross_entropy_with_logits(logit[~unusable, 0], soft[~unusable])
    if seen.any():  # Huber: radar labels jump between vehicles now and then, don't let those dominate
        loss = loss + 10 * F.smooth_l1_loss(d[seen, 0], dist[seen].clamp(max=FAR) / MAX_M, beta=0.05)
    return loss


def train_loss(logit, d, extra, labels, moved):
    """`criterion` plus what only training frames can teach, all from the radar position of the vehicle described:
    the distance as a distribution over bins, the sideways offset, and where in the fovea the vehicle is."""
    flip, right, down = moved
    _, _, seen, dist, side = labels
    loss = criterion(logit, d, labels)
    if not seen.any():
        return loss
    dist, side = dist[seen], side[seen] * torch.where(flip[seen], -1.0, 1.0)  # a mirrored image swaps left and right
    centre = BINS.to(dist.device).log()
    soft = torch.softmax(-0.5 * ((centre[None] - dist.clamp(5, FAR)[:, None].log()) / (centre[1] - centre[0])) ** 2, 1)  # one bin wide
    loss = loss - (soft * extra["bins"][seen].float().log_softmax(1)).sum(1).mean()
    loss = loss + 0.5 * F.smooth_l1_loss(extra["sideways"][seen, 0].float(), side / 1.5, beta=0.1)
    u, v = project(dist, side)  # the radar position in the image: a soft target for the attention map
    (r0, r1, c0, c1), where = FOVEA, extra["where"][seen].float()
    h, w = 2 * (r1 - r0) // CELL, 2 * (c1 - c0) // CELL
    row, col = (v + down - 2 * r0) / CELL, (u + right - 2 * c0) / CELL
    inside = (row >= 0) & (row < h) & (col >= 0) & (col < w)
    if inside.any():
        rows = torch.arange(h, device=dist.device).float().repeat_interleave(w) + 0.5
        cols = torch.arange(w, device=dist.device).float().repeat(h) + 0.5
        target = torch.softmax(-0.5 * ((rows[None] - row[inside, None]) ** 2 + (cols[None] - col[inside, None]) ** 2), 1)  # 1 cell wide
        loss = loss - 0.5 * (target * where[inside].log_softmax(1)).sum(1).mean()
    return loss


@torch.no_grad()
def predict(net, x, y, dev, labels=hard):
    """Returns loss, has-target probability and distance in metres for every sample. y: the dataset's labels, or with
    labels=lead the radar objects, which scores the answers against what a camera can know."""
    net.eval()
    loss, prob, dist = 0.0, [], []
    for xb, yb in batches(x, y, 128, dev):
        logit, d = net(xb)[:2]
        loss += criterion(logit, d, labels(yb)).item() * len(xb)
        prob.append(torch.sigmoid(logit[:, 0]).cpu().numpy())
        dist.append((d[:, 0] * MAX_M).clamp(0, MAX_M).cpu().numpy())
    return loss / len(x), np.concatenate(prob), np.concatenate(dist)


def train(epochs=32, batch=48, per_epoch=20000, lr=1e-3):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cudnn.benchmark = True
    x = np.load(CACHE / "dense_x.npy", mmap_mode="r")
    if "curve" in RECIPE:  # labels of `curve`; validation on its usable frames
        both, cv = np.load(CACHE / "dense_c.npy"), np.load(CACHE / "val_c.npy")
        meta, rich, usable = both[:, :4], both[:, 4:], np.flatnonzero(cv[:, 0] >= 0)
        xv, yv, cv, rv = load("val")[0][usable], cv[usable, :2], cv[usable], None
    else:
        meta, rich = np.load(CACHE / "dense_y.npy"), np.load(CACHE / "dense_r.npy")
        (xv, yv), rv = load("val"), np.load(CACHE / "val_r.npy")
    weight = None
    if "balance" in RECIPE:
        scbs, light = json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))["splits"]["train"], time_of_day()
        video = np.cumsum(meta[:, 3]).astype(int) - 1  # meta[:, 3] marks the first frame of every video
        weight = balance_weights(meta, np.array([light[scb] == "dem" for scb in scbs])[video])[0]
    net = build().to(dev)
    average = copy.deepcopy(net)  # running average of the weights: steadier than the last step, this is what gets saved
    opt = torch.optim.AdamW(net.parameters(), lr, weight_decay=0.05)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, lr, epochs=epochs, steps_per_epoch=math.ceil(per_epoch / batch), pct_start=0.1)
    scaler = torch.amp.GradScaler(enabled=dev.type == "cuda")
    print(f"{sum(p.numel() for p in net.parameters()):,} parameters, training on {dev}, "
          f"{per_epoch} of {int((meta[:, 0] >= 0).sum())} labelled frames per epoch", flush=True)
    best, step = math.inf, 0
    for epoch in range(1, epochs + 1):
        net.train()
        total = objective = 0.0
        for xb, yb in dense_batches(x, meta, rich, batch, per_epoch, dev, weight):
            xb, (*moved, zoom) = augment(xb)
            labels = ((curved_soft if "soft" in RECIPE else curved)(yb, zoom) if "curve" in RECIPE else lead(yb[:, 3:], zoom[:, None]) if "radar" in RECIPE
                      else hard(yb[:, :3], yb[:, 3:], zoom if ZOOM else None))
            with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                logit, d, extra = net(xb)
            logit, d = logit.float(), d.float()
            loss = train_loss(logit, d, extra, labels, moved)
            if "curve" in RECIPE:
                loss = loss + path_loss(extra["path"].float(), yb, moved, zoom)
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5)
            scaler.step(opt)
            scaler.update()
            sched.step()
            step += 1
            keep = min(0.999, (1 + step) / (10 + step))
            with torch.no_grad():
                for a, p in zip(average.parameters(), net.parameters()):
                    a.lerp_(p, 1 - keep)
                for a, b in zip(average.buffers(), net.buffers()):
                    a.copy_(b)
                total += criterion(logit, d, labels).item() * len(xb)
            objective += loss.item() * len(xb)
        if "curve" in RECIPE:
            raw, prob, dist = predict(average, xv, yv, dev)
            val, lane = raw, path_error(average, xv, cv, dev)
        else:
            val, prob, dist = predict(average, xv, rv, dev, lead)  # scored against what a camera can know
            raw, lane = predict(average, xv, yv, dev)[0], ""  # and against the dataset's labels as they are
        has = yv[:, 0] > 0
        mae = np.abs(dist[has] - yv[has, 1]).mean()
        acc = ((prob > 0.5) == has).mean()
        score = val if "radar" in RECIPE else raw  # each recipe is judged by the labels it trains on
        saved = score < best
        if saved:  # the checkpoint is chosen on validation, never on test
            best = score
            torch.save(average.state_dict(), CKPT)
        print(f"epoch {epoch:3d}  train loss {total / per_epoch:.4f}  val loss {val:.4f}  on raw labels {raw:.4f}  val MAE {mae:5.2f} m  "
              f"val has_target acc {acc:.3f}  (training objective {objective / per_epoch:.3f}){lane}{'  *' if saved else ''}", flush=True)


@torch.no_grad()
def path_error(net, x, c, dev):
    """How far the path head is off on frames as filmed, in metres, at 60 m and at 100 m (median)."""
    net.eval()
    got = np.concatenate([(net(torch.from_numpy(x[i:i + 128]).to(dev).float())[2]["path"].float() * PATH_UNIT.to(dev)).cpu().numpy() for i in range(0, len(x), 128)])
    want = lane_at(torch.from_numpy(c[:, 4:4 + len(PATH_KNOTS)]), torch.tensor(PATH_AT)[None].expand(len(c), -1)).numpy()
    err = np.abs(got - want)
    return f"  lane off by {np.median(err[:, 2]):.2f} m at 60 m, {np.median(err[:, 4]):.2f} m at 100 m"


def build():
    return Gr14VinAI(context=32 if "small" in RECIPE else 64, curve="curve" in RECIPE)


def load_net(dev="cpu"):
    net = build().to(dev)
    net.load_state_dict(torch.load(CKPT, map_location=dev))
    return Mirrored(net).eval()  # the trained network answers from the image and its mirror image


def best_threshold(prob, has):
    """has_target threshold with the best F1, searched on validation."""
    f1 = lambda t: 2 * ((prob > t) & has).sum() / max(((prob > t).sum() + has.sum()), 1)
    return float(max(np.arange(0.05, 0.96, 0.01), key=f1))


def evaluate():
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = load_net(dev)
    (xv, yv), (xs, ys) = judged("val"), judged("test")
    threshold = best_threshold(predict(net, xv, yv, dev)[1], yv[:, 0] > 0)
    _, prob, dist = predict(net, xs, ys, dev)
    has = ys[:, 0] > 0
    median = train_median()
    print(f"median guess, always answering the train median {median:.1f} m: MAE {np.abs(ys[has, 1] - median).mean():.2f} m\n")
    print(f"gr14VinAI on the test split (threshold {threshold:.2f} chosen on validation)")
    print_metrics(has, ys[:, 1], prob, dist, threshold)
    return threshold


def to_onnx(path):
    """Write the checkpoint as ONNX and check on 32 real test frames that it answers the same as PyTorch."""
    import onnxruntime as ort
    try:
        import onnx  # noqa: F401
    except ImportError:  # torch imports it only to attach onnxscript functions, and this model has none
        from torch.onnx._internal import onnx_proto_utils
        onnx_proto_utils._add_onnxscript_fn = lambda proto, custom_opsets: proto
    model = Deploy(load_net()).eval()
    x = torch.from_numpy(load("test")[0][:32].copy()).float()
    with torch.no_grad():
        want = [t.numpy() for t in model(x)]
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, x[:1], str(path), input_names=["input_imgs"], output_names=["has_target", "distance_m", "lane_left_m"][:len(want)],
                      opset_version=17, dynamo=False)
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    got = [np.concatenate(o) for o in zip(*(sess.run(None, {"input_imgs": x[i:i + 1].numpy()}) for i in range(len(x))))]
    assert all(np.allclose(g, w, rtol=1e-3, atol=1e-3) for g, w in zip(got, want)), "ONNX output differs from PyTorch"


def export():
    threshold = evaluate()
    to_onnx(ONNX)
    curve = "curve" in RECIPE
    ONNX.with_suffix(".json").write_text(json.dumps({
        "input_imgs": "[1,12,128,256] float32, raw 0..255: previous and current frame, each as 6 half-resolution YUV420 "
                      "planes of the 512x256 window around the vanishing point (see common.read_yuv_frames)",
        "has_target": "[1,1] probability that a same-lane target exists within 100 m"
                      + (" (same lane: within 1.5 m of the lane centre, which follows the road)" if curve else ""),
        "distance_m": "[1,1] metres, clamped to [0, 100]; only meaningful when has_target >= has_target_threshold",
        **({"lane_left_m": f"[1,{len(PATH_AT)}] metres the lane centre lies to the left of the straight axis, {', '.join(map(str, PATH_AT))} m ahead"} if curve else {}),
        "note": "every output is the average over the image and its mirror image, computed inside the model",
        "has_target_threshold": round(threshold, 2),
    }, indent=1), encoding="utf-8")
    print()
    print(f"wrote {ONNX} ({ONNX.stat().st_size / 2**20:.1f} MB); on 32 test frames it answers the same as PyTorch")


SMOOTH = 0.2  # weight of the newest frame in the running average: 0.2 lags about 0.2 s at 20 fps, 1 turns smoothing off


def smooth(prob, dist, threshold):
    """Running average over time, applied after the network. It only sees two frames, so on its own it flickers."""
    prob, dist = prob.copy(), dist.copy()
    for i in range(1, len(prob)):
        prob[i] = SMOOTH * prob[i] + (1 - SMOOTH) * prob[i - 1]
        if prob[i] > threshold and prob[i - 1] > threshold:  # never average a distance with a no-target frame
            dist[i] = SMOOTH * dist[i] + (1 - SMOOTH) * dist[i - 1]
    return prob, dist


def videos():
    """Run the exported .onnx frame by frame over the test videos: predictions for the viewer, and how steady they are."""
    WORK.mkdir(parents=True, exist_ok=True)
    sess = onnx_session(ONNX)
    threshold = json.loads(ONNX.with_suffix(".json").read_text(encoding="utf-8"))["has_target_threshold"]
    scbs = sys.argv[2:] or json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))["splits"]["test"]
    runs = {"gr14VinAI raw": [], "gr14VinAI smoothed": [], "baseline": []}  # per video: (target reported?, distance)
    for scb in scbs:
        prev, rows = None, []
        for frame in read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb)):
            prob, dist = sess.run(None, {"input_imgs": np.concatenate([frame if prev is None else prev, frame])[None]})[:2]
            rows.append((prob.item(), dist.item()))
            prev = frame
        prob, dist = np.array(rows).T
        sprob, sdist = smooth(prob, dist, threshold)
        np.savetxt(WORK / f"preds_{scb}.csv", np.column_stack([prob, dist, sprob, sdist]), "%.4f", ",",
                   header="has_target,distance_m,has_target_smooth,distance_smooth_m", comments="")
        runs["gr14VinAI raw"].append((prob > threshold, dist))
        runs["gr14VinAI smoothed"].append((sprob > threshold, sdist))
        if (BASELINE / f"preds_{scb}.csv").exists():
            p, d = np.loadtxt(BASELINE / f"preds_{scb}.csv", delimiter=",", skiprows=1, usecols=(1, 2)).T
            runs["baseline"].append((p > 0.5, d))
        print(f"{scb}: {len(rows)} frames, target reported in {np.mean(sprob > threshold):.0%}", flush=True)
    print("steadiness from one frame to the next (20 fps):")
    for name, parts in runs.items():
        if parts:
            change = np.concatenate([np.abs(np.diff(d))[on[1:] & on[:-1]] for on, d in parts])
            flips = sum(np.count_nonzero(on[1:] != on[:-1]) for on, d in parts) / sum(len(d) for on, d in parts) * 1200
            print(f"  {name:18s} distance changes by {change.mean():.2f} m on average (95% under {np.percentile(change, 95):.2f} m), "
                  f"target appears/disappears {flips:.0f} times per minute")


if __name__ == "__main__":
    {"prepare": prepare, "dense": dense, "radar": radar, "curve": curve, "train": train, "eval": evaluate, "export": export, "videos": videos}[sys.argv[1]]()
