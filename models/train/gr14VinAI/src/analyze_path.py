"""How the road bends in this data, and what a corridor that follows the car's own path would change in the labels.

    python src/analyze_path.py     # -> results/path_analysis.json, results/path_analysis.png

The dataset calls a vehicle "same lane" when it is within 1.5 m of the car's straight axis. Here the axis is replaced by
the path the car really drove in the next seconds (from global_pose), and the same radar rule is applied around it.
"""
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import DATA, RAW, ROOT, future_path
from preprocess_dataset import load_arrays

LANE, RANGE = 1.5, 100.0  # the dataset's rule


def offset_at(ahead, left, d):
    """Sideways position of the path at d metres ahead, per frame (NaN when the path seen does not reach that far)."""
    out = np.full(len(ahead), np.nan)
    for i in range(len(ahead)):
        a = ahead[i]
        ok = np.isfinite(a)
        if ok.any() and a[ok][-1] >= d:
            out[i] = np.interp(d, np.concatenate([[0], a[ok]]), np.concatenate([[0], left[i][ok]]))
    return out


def objects(t, times, values, delta=0.05):
    lo, hi = np.searchsorted(times, t - delta, "left"), np.searchsorted(times, t + delta, "right")
    near = {}
    for i in range(lo, hi):
        if (k := values[i, 5]) not in near or abs(times[i] - t) < abs(times[near[k]] - t):
            near[k] = i
    rows = values[list(near.values())] if near else np.zeros((0, 7))
    return rows[np.isfinite(rows[:, :2]).all(1) & (rows[:, 0] > 0) & ~np.isclose(rows[:, 0], 258.6375, rtol=0, atol=1e-4)]


def main():
    split_of = {s: k for k, v in json.loads((DATA / "manifests/split_manifest.json").read_text(encoding="utf-8"))["splits"].items() for s in v}
    labelled = {}
    for split in ("train", "val", "test"):
        for r in csv.DictReader(open(DATA / f"labels/{split}.csv", encoding="utf-8")):
            labelled.setdefault(r["scb_id"], []).append(r)
    per_video, speed, off50, off100, kinds, at_target, dist, yrel = [], [], [], [], [], [], [], []
    for scb in sorted(split_of, key=lambda s: int(s[3:])):
        ahead, left, v = future_path(scb)
        o50, o100 = offset_at(ahead, left, 50), offset_at(ahead, left, 100)
        speed.append(v); off50.append(o50); off100.append(o100)
        per_video.append((scb, split_of[scb], float(np.mean(v)), float(np.nanmax(np.abs(o100))) if np.isfinite(o100).any() else np.nan,
                          float(np.nanmedian(o100)) if np.isfinite(o100).any() else np.nan))
        _, times, values = load_arrays(RAW / scb)
        for r in labelled[scb]:
            i, t = int(r["frame_index"]), float(r["frame_time"])
            rows = objects(t, times, values)
            a, l = ahead[i], left[i]
            ok = np.isfinite(a)
            reach = a[ok][-1] if ok.any() else 0
            straight = rows[(rows[:, 0] <= RANGE) & (np.abs(rows[:, 1]) <= LANE)]
            old = straight[straight[:, 0].argmin()] if len(straight) else None
            if old is not None:
                dist.append(old[0]); yrel.append(old[1])
            if reach < min(RANGE, rows[:, 0].max() if len(rows) else RANGE) and reach < RANGE:
                kinds.append((split_of[scb], "unknown"))  # the video ends before the path reaches the objects
                continue
            path = np.interp(rows[:, 0], np.concatenate([[0], a[ok]]), np.concatenate([[0], l[ok]]))
            curved = rows[(rows[:, 0] <= RANGE) & (np.abs(rows[:, 1] - path) <= LANE)]
            new = curved[curved[:, 0].argmin()] if len(curved) else None
            if old is not None:
                at_target.append(float(np.interp(old[0], np.concatenate([[0], a[ok]]), np.concatenate([[0], l[ok]]))))
            kind = ("no target, same" if old is None and new is None else "gains a target" if old is None else "loses its target" if new is None
                    else "same target" if old[5] == new[5] else "other target")
            kinds.append((split_of[scb], kind))
    speed, off50, off100 = np.concatenate(speed), np.concatenate(off50), np.concatenate(off100)
    at_target, dist, yrel = np.array(at_target), np.array(dist), np.array(yrel)
    ok100 = np.isfinite(off100)
    radius = 100 ** 2 / (2 * np.maximum(np.abs(off100[ok100]), 1e-6))  # of the arc that reaches the same sideways offset at 100 m
    bends = {"gần thẳng (R > 3000 m)": float((radius > 3000).mean()), "cong nhẹ (1000-3000 m)": float(((radius > 1000) & (radius <= 3000)).mean()),
             "cong vừa (500-1000 m)": float(((radius > 500) & (radius <= 1000)).mean()), "cong gắt (R < 500 m)": float((radius <= 500).mean())}
    names = ["same target", "no target, same", "loses its target", "gains a target", "other target", "unknown"]
    change = {s: {k: sum(1 for a, b in kinds if a == s and b == k) for k in names} for s in ("train", "val", "test")}
    known = [(a, b) for a, b in kinds if b != "unknown"]
    out = {"frames_with_pose": int(len(speed)), "speed_mps": {p: round(float(np.percentile(speed, p)), 1) for p in (1, 5, 50, 95, 99)},
           "share_slower_than_15mps": float((speed < 15).mean()),
           "path_offset_at_100m_m": {p: round(float(np.nanpercentile(np.abs(off100), p)), 2) for p in (50, 75, 90, 95, 99)},
           "share_path_leaves_straight_corridor": {"at 50 m": float((np.abs(off50[np.isfinite(off50)]) > LANE).mean()), "at 100 m": float((np.abs(off100[ok100]) > LANE).mean())},
           "share_path_one_lane_away_at_100m": float((np.abs(off100[ok100]) > 3.5).mean()),
           "bends_share_of_frames": bends, "left_vs_right": {"bends left": float((off100[ok100] > LANE).mean()), "bends right": float((off100[ok100] < -LANE).mean())},
           "videos": {"with a bend beyond 1.5 m at 100 m": int(sum(1 for v in per_video if v[3] > LANE)), "with a bend beyond 3.5 m": int(sum(1 for v in per_video if v[3] > 3.5)), "total": len(per_video)},
           "labels_if_the_corridor_follows_the_path": change,
           "share_of_labelled_frames_whose_label_changes": float(np.mean([b in ("loses its target", "gains a target", "other target") for a, b in known])),
           "path_offset_at_the_target_m": {p: round(float(np.percentile(np.abs(at_target), p)), 2) for p in (50, 90, 95, 99)}}
    (ROOT / "results" / "path_analysis.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))

    fig, ax = plt.subplots(2, 4, figsize=(21, 9.5))
    ax = ax.ravel()
    ax[0].hist(dist, bins=40, color="#3b6ea5"); ax[0].set_title("Khoảng cách tới xe phía trước (nhãn radar)"); ax[0].set_xlabel("m"); ax[0].set_ylabel("số frame có nhãn")
    ax[1].hist(yrel, bins=48, color="#3b6ea5"); ax[1].set_title("Độ lệch ngang của xe phía trước"); ax[1].set_xlabel("m (dương = bên trái)")
    ax[2].hist(speed * 3.6, bins=50, color="#5a9367"); ax[2].set_title("Tốc độ xe mình"); ax[2].set_xlabel("km/h"); ax[2].set_ylabel("số frame")
    ax[3].hist(np.clip(off100[ok100], -12, 12), bins=96, color="#5a9367"); ax[3].axvline(-LANE, color="k", ls="--"); ax[3].axvline(LANE, color="k", ls="--")
    ax[3].set_title("Đường đi lệch khỏi trục thẳng, ở 100 m phía trước"); ax[3].set_xlabel("m (dương = rẽ trái); nét đứt = mép hành lang 1,5 m"); ax[3].set_yscale("log")
    ax[4].bar(range(4), [v * 100 for v in bends.values()], color=["#5a9367", "#c9b24a", "#d98a3a", "#c0504d"]); ax[4].set_xticks(range(4)); ax[4].set_xticklabels([k.replace(" (", "\n(") for k in bends], fontsize=9)
    ax[4].set_title("Độ cong của đường (theo % số frame)"); ax[4].set_ylabel("%")
    for i, v in enumerate(bends.values()):
        ax[4].text(i, v * 100 + 1, f"{v:.1%}", ha="center")
    colour = {"train": "#3b6ea5", "val": "#d98a3a", "test": "#c0504d"}
    for s in colour:
        pts = [(v[2] * 3.6, min(v[3], 30)) for v in per_video if v[1] == s and np.isfinite(v[3])]
        ax[5].scatter(*zip(*pts), color=colour[s], label=s, s=28)
    ax[5].axhline(LANE, color="k", ls="--"); ax[5].axhline(3.5, color="k", ls=":"); ax[5].set_yscale("log"); ax[5].legend()
    ax[5].set_title("Mỗi chấm là một video: đoạn cong nhất của nó"); ax[5].set_xlabel("tốc độ trung bình (km/h)"); ax[5].set_ylabel("lệch lớn nhất ở 100 m (m)")
    vn = {"same target": "vẫn xe đó", "no target, same": "vẫn không có xe", "loses its target": "mất xe", "gains a target": "thêm xe", "other target": "đổi sang xe khác", "unknown": "không tính được"}
    total = {k: sum(change[s][k] for s in change) for k in names}
    ax[6].bar(range(6), [total[k] for k in names], color=["#5a9367", "#5a9367", "#c0504d", "#c0504d", "#c0504d", "#999999"]); ax[6].set_xticks(range(6)); ax[6].set_xticklabels([vn[k] for k in names], fontsize=8, rotation=20)
    ax[6].set_title("Nhãn đổi thế nào nếu hành lang uốn theo đường đi"); ax[6].set_ylabel("số frame có nhãn")
    for i, k in enumerate(names):
        ax[6].text(i, total[k] + 40, str(total[k]), ha="center")
    ax[7].hist(np.clip(np.abs(at_target), 0, 4), bins=60, color="#3b6ea5"); ax[7].axvline(0.3, color="k", ls="--"); ax[7].set_yscale("log")
    ax[7].set_title("Đường đi lệch khỏi trục thẳng, tại chỗ xe phía trước"); ax[7].set_xlabel("m (nét đứt = 0,3 m)")
    fig.suptitle("Phân bố dữ liệu của 100 đoạn SCB: khoảng cách, tốc độ, độ cong của đường", fontsize=15)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "path_analysis.png", dpi=110)


if __name__ == "__main__":
    main()
