"""Mọi hình của báo cáo, vẽ từ log và file kết quả thật. Không có số nào được gõ tay vào đây.

    python report/scripts/make_figures.py          # tất cả các hình -> report/figures/*.png (dpi 200)
    python report/scripts/make_figures.py 05 06    # chỉ các hình có tên bắt đầu bằng 05 hoặc 06

Đọc:  data/prepared_dataset_v2 (nhãn, manifest), data/cache_v2 (frame đã cắt), data/raw (pose để tìm điểm tụ),
      results/ (log train, benchmark.json, evidence.json, balance.json), eval/ (số đã ghi lại của các vòng trước),
      model/gr14VinAI.pt và .json.
Ghi:  report/figures/*.png, results/report/preds_{val,test}.npz (dự đoán từng frame, tính một lần từ checkpoint),
      results/report/figure_stats.json (các con số đọc ra từ hình, để viết nhận xét).
"""
import csv
import json
import locale
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.patches import Patch, Rectangle
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import common  # noqa: E402
from common import DATA, FOCAL, MODEL_CX, MODEL_CY, RAW  # noqa: E402

FIG, OUT, RES = ROOT / "report" / "figures", ROOT / "results" / "report", ROOT / "results"
CACHE = ROOT / "data" / f"cache{common.SET}"
RANGES = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
BANDS = [f"{lo}–{hi} m" for lo, hi in RANGES]
CAR_WIDTH_M = 1.8  # bề rộng xe giả định khi đổi khoảng cách ra số pixel; radar không đo bề rộng
TARGETS = {}  # mục tiêu ban đầu, ví dụ {"mae_m": 3.0, "f1": 0.9}: có thì hình 00 vẽ thêm đường mục tiêu
STATS = {}

# Bảng màu: ba màu đầu đã kiểm tra phân biệt được với người mù màu (validate_palette.js --pairs all); xám = mốc so sánh
BLUE, ORANGE, AQUA, YELLOW, VIOLET, MAGENTA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e87ba4", "#e34948"
GRAY, INK, INK2, GRID, SURFACE = "#8a8984", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SPLIT = {"train": BLUE, "val": ORANGE, "test": AQUA}
LIGHT = {"ngay": YELLOW, "dem": VIOLET, "chang_vang": MAGENTA}
LIGHT_NAME = {"ngay": "ngày", "dem": "đêm", "chang_vang": "chạng vạng"}
SEQ = LinearSegmentedColormap.from_list("blue", [SURFACE, "#cde2fb", "#6da7ec", BLUE, "#0d366b"])

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold", "figure.titlesize": 11,
    "figure.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": INK2,
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "legend.frameon": False,
    "lines.linewidth": 2, "figure.constrained_layout.use": True})
for _name in ("vi_VN.UTF-8", "vi-VN", "Vietnamese_Vietnam"):  # dấu phẩy thập phân trên trục, như trong bài viết
    try:
        locale.setlocale(locale.LC_NUMERIC, _name)
        plt.rcParams["axes.formatter.use_locale"] = True
        break
    except locale.Error:
        pass


def vn(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


def th(n):
    """Số nguyên với dấu chấm ngăn hàng nghìn."""
    return f"{int(n):,}".replace(",", ".")


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


# ---------------------------------------------------------------- dữ liệu dùng chung

_memo = {}


def segs():
    if "segs" not in _memo:
        _memo["segs"] = {r["scb_id"]: r for r in read_csv(DATA / "manifests/segments.csv")}
    return _memo["segs"]


def truth(split):
    """Các frame mà model được chấm, đúng thứ tự của common.labelled: nhãn radar với hành lang bám theo đường."""
    if split not in _memo:
        rows, seg = common.labelled(split), segs()
        num = lambda k: np.array([float(r[k] or "nan") for r in rows])
        _memo[split] = dict(
            rows=rows, has=np.array([r["has_target"] == "1" for r in rows]), dist=num("distance_m"), y=num("y_rel_m"), lane=num("lane_left_m"),
            scb=np.array([r["scb_id"] for r in rows]), night=np.array([seg[r["scb_id"]]["time_of_day"] == "dem" for r in rows]),
            added=np.array([seg[r["scb_id"]]["origin"] == "added" for r in rows]))
    return _memo[split]


def predictions(split):
    """Đáp án của checkpoint trên từng frame được chấm: xác suất có xe, khoảng cách, tâm làn, và vector 512 số của thân chung."""
    file = OUT / f"preds_{split}.npz"
    if not file.exists():
        import torch
        import train_distance as g
        torch.set_num_threads(6)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        net, feats = g.load_net(dev), []
        net.net.trunk.register_forward_hook(lambda m, i, o: feats.append(o[:len(o) // 2].float().cpu().numpy()))  # nửa đầu của batch là ảnh gốc
        x = np.load(g.CACHE / f"{split}_x.npy", mmap_mode="r")
        keep = np.flatnonzero(np.load(g.CACHE / f"{split}_c.npy")[:, 0] >= 0)
        assert len(keep) == len(truth(split)["rows"]), "cache không khớp với nhãn"
        prob, dist, lane = [], [], []
        with torch.no_grad():
            for i in range(0, len(keep), 64):
                logit, d, extra = net(torch.from_numpy(x[keep[i:i + 64]]).to(dev).float())
                prob.append(torch.sigmoid(logit[:, 0]).cpu().numpy())
                dist.append((d[:, 0] * g.MAX_M).clamp(0, g.MAX_M).cpu().numpy())
                lane.append((extra["path"].cpu() * g.PATH_UNIT).numpy())
                print(f"\r  {split}: {min(i + 64, len(keep))}/{len(keep)} frame", end="", flush=True)
        print()
        OUT.mkdir(parents=True, exist_ok=True)
        np.savez(file, prob=np.concatenate(prob), dist=np.concatenate(dist), lane=np.concatenate(lane), feat=np.concatenate(feats))
    return np.load(file)


def threshold():
    return read_json(ROOT / "model/gr14VinAI.json")["has_target_threshold"]


def scores(has, dist, prob, pred, t):
    det, err = prob > t, np.abs(pred[has] - dist[has])
    tp, fp, fn = (det & has).sum(), (det & ~has).sum(), (~det & has).sum()
    return dict(n=int(len(has)), targets=int(has.sum()), precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), f1=2 * tp / max(2 * tp + fp + fn, 1),
                mae=err.mean() if len(err) else np.nan, median=np.median(err) if len(err) else np.nan)


def check_predictions():
    """Dự đoán tính lại ở đây phải cho đúng các số của results/benchmark/benchmark.json; nếu không thì các hình mục 06 không đáng tin."""
    from train import best_threshold
    v, pv, t, p, bench = truth("val"), predictions("val"), truth("test"), predictions("test"), read_json(RES / "benchmark/benchmark.json")
    assert abs(best_threshold(pv["prob"], v["has"]) - threshold()) < 0.011, "ngưỡng chọn lại trên validation khác ngưỡng trong model/gr14VinAI.json"
    s = scores(t["has"], t["dist"], p["prob"], p["dist"], threshold())
    for mine, theirs in ((s["mae"], "mae_m"), (s["median"], "median_m"), (s["precision"], "precision"), (s["recall"], "recall"), (s["f1"], "f1")):
        assert abs(mine - bench["test"][theirs]) < 0.02, f"{theirs}: tính lại {mine:.3f}, benchmark.json {bench['test'][theirs]}"
    STATS["test_recomputed"] = {k: round(float(x), 3) for k, x in s.items()}
    sv = scores(v["has"], v["dist"], pv["prob"], pv["dist"], threshold())
    STATS["val_recomputed"] = {k: round(float(x), 3) for k, x in sv.items()}
    print(f"  khớp benchmark.json: test MAE {s['mae']:.2f} m, trung vị {s['median']:.2f} m, P {s['precision']:.3f} R {s['recall']:.3f} F1 {s['f1']:.3f}")


def frame_png(row):
    return Image.open(DATA / row["image_path"]).convert("RGB")


def crop(row):
    """Cửa sổ 512x256 quanh điểm tụ mà mạng nhìn thấy, cắt từ ảnh PNG gốc như common.read_yuv_frames cắt từ video."""
    scb = row["scb_id"]
    if ("vp", scb) not in _memo:
        _memo["vp", scb] = common.vanishing_point(RAW / scb)
    vx, vy = _memo["vp", scb]
    x0, y0 = 2 * round((vx - MODEL_CX) / 2), 2 * round((vy - MODEL_CY) / 2)
    return frame_png(row).crop((x0, y0, x0 + 512, y0 + 256)), (x0, y0, vx, vy)


def show(ax, img, title=None, **kw):
    ax.imshow(img, **kw)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, fontsize=7.5, fontweight="normal", pad=3)


def parse_train_log(path):
    """epoch -> train loss, val loss, val MAE, val accuracy, sai số tâm làn ở 60/100 m, có được lưu làm checkpoint không."""
    pat = re.compile(r"epoch\s+(\d+)\s+train loss ([\d.]+)\s+val loss ([\d.]+)\s+on raw labels ([\d.]+)\s+val MAE\s+([\d.]+) m\s+val has_target acc ([\d.]+)"
                     r"\s+\(training objective ([\d.]+)\)(?:\s+lane off by ([\d.]+) m at 60 m, ([\d.]+) m at 100 m)?(\s+\*)?")
    rows = [m.groups() for m in map(pat.match, Path(path).read_text(encoding="utf-8").splitlines()) if m]
    cols = ("epoch", "train", "val", "raw", "mae", "acc", "objective", "lane60", "lane100")
    out = {c: np.array([float(r[i]) if r[i] else np.nan for r in rows]) for i, c in enumerate(cols)}
    out["saved"] = np.array([bool(r[9]) for r in rows])
    return out


def parse_val_compare(path):
    """Các dòng 'all' của val_compare.log: tên checkpoint -> ngưỡng, MAE, trung vị, F1 trên cùng 3.424 frame validation."""
    out, name = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if m := re.match(r"(\S+)\.pt: validation (\d+) frames, threshold ([\d.]+)", line):
            name, out[m[1]] = m[1], {"frames": int(m[2]), "threshold": float(m[3])}
        elif m := re.match(r"\s+all\s+n=\s*\d+\s+MAE\s+([\d.]+)\s+median\s+([\d.]+)\s+RMSE\s+([\d.]+)\s+P ([\d.]+)\s+R ([\d.]+)\s+F1 ([\d.]+)", line):
            out[name] |= dict(zip(("mae", "median", "rmse", "precision", "recall", "f1"), map(float, m.groups())))
    return out


def band_of(dist):
    return np.clip(np.ceil(dist / 20) - 1, 0, 4).astype(int)


# ---------------------------------------------------------------- 00 tổng quan

def f00_main_results():
    e = read_json(RES / "eval/evidence.json")["full_test"]
    names, vals = ["Đoán trung vị\n(không nhìn ảnh)", "Hình học\n(bbox + pinhole)", "gr14VinAI"], list(e.values())
    assert list(e)[2] == "gr14VinAI"
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 2.9), sharey=True)
    for ax, key, nd, title, label in ((axes[0], "mae_m", 2, "Sai số khoảng cách (thấp hơn là tốt hơn)", "MAE trên các frame hệ thống và radar cùng thấy xe (m)"),
                                      (axes[1], "f1", 3, "Phát hiện xe cùng làn (cao hơn là tốt hơn)", "F1 của has_target")):
        bars = ax.barh(names, [v[key] for v in vals], color=[GRAY, GRAY, BLUE], height=0.55)
        ax.bar_label(bars, [vn(v[key], nd) for v in vals], padding=3)
        if key in TARGETS:
            ax.axvline(TARGETS[key], color=INK, ls="--", lw=1)
            ax.text(TARGETS[key], 2.45, f" mục tiêu {vn(TARGETS[key], nd)}", fontsize=8, va="bottom")
        ax.set(title=title, xlabel=label, xlim=(0, max(v[key] for v in vals) * 1.15))
        ax.grid(axis="y", visible=False)
    axes[0].invert_yaxis()
    fig.suptitle("Kết quả chính trên tập test (34 video, 3.778 frame) so với hai mốc so sánh")
    save(fig, "00_main_results")
    STATS["00_main_results"] = e


# ---------------------------------------------------------------- 01 thu thập

def f01_samples_by_source():
    seg = list(segs().values())
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.3), width_ratios=[1, 1.9])
    groups = [("original", "100 video ban đầu"), ("added", "254 video thêm sau")]
    bottom = np.zeros(2)
    for tod in ("ngay", "dem", "chang_vang"):
        n = np.array([sum(r["origin"] == o and r["time_of_day"] == tod for r in seg) for o, _ in groups])
        bars = axes[0].bar([g[1] for g in groups], n, bottom=bottom, color=LIGHT[tod], label=LIGHT_NAME[tod], width=0.55, edgecolor=SURFACE, linewidth=1.5)
        axes[0].bar_label(bars, n, label_type="center", fontsize=8, color="white" if tod == "dem" else INK)
        bottom += n
        STATS.setdefault("01_by_source", {})[tod] = n.tolist()
    axes[0].set(title="Theo đợt thu thập và thời điểm quay", ylabel="Số video (mỗi video 1 phút)")
    axes[0].legend(title="Thời điểm", fontsize=8)
    axes[0].grid(axis="x", visible=False)
    chunks = [f"Chunk_{i}" for i in range(1, 11)]
    bottom = np.zeros(10)
    for (o, name), colour in zip(groups, (GRAY, BLUE)):
        n = np.array([sum(r["origin"] == o and r["path"].split("/")[0] == c for r in seg) for c in chunks])
        axes[1].bar([c[6:] for c in chunks], n, bottom=bottom, color=colour, label=name, width=0.65, edgecolor=SURFACE, linewidth=1.5)
        bottom += n
        STATS["01_by_source"][o + "_by_chunk"] = n.tolist()
    for i, total in enumerate(bottom):
        axes[1].text(i, total + 1, int(total), ha="center", fontsize=8)
    axes[1].set(title="Theo chunk của Comma2k19", xlabel="Chunk", ylabel="Số video")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="x", visible=False)
    fig.suptitle("Số lượng mẫu theo nguồn: 354 video một phút của Comma2k19")
    save(fig, "01_samples_by_source")


def f01_sample_grid():
    t, rng = truth("train"), np.random.default_rng(0)
    fig, axes = plt.subplots(4, 4, figsize=(10, 7.6))
    kinds = [("Ngày, có xe cùng làn", ~t["night"] & t["has"]), ("Ngày, không có xe cùng làn", ~t["night"] & ~t["has"]),
             ("Đêm, có xe cùng làn", t["night"] & t["has"]), ("Đêm, không có xe cùng làn", t["night"] & ~t["has"])]
    for row, (name, mask) in zip(axes, kinds):
        videos = rng.permutation(np.unique(t["scb"][mask]))[:4]  # mỗi ảnh một video khác nhau
        for ax, scb in zip(row, videos):
            i = rng.choice(np.flatnonzero(mask & (t["scb"] == scb)))
            r = t["rows"][i]
            what = f"radar: {vn(t['dist'][i], 1)} m" if t["has"][i] else "radar: không có xe"
            show(ax, frame_png(r).resize((582, 437)), f"{scb}, frame {r['frame_index']} | {what}")
        row[0].set_ylabel(name.replace(", ", ",\n"), fontsize=8.5, color=INK, fontweight="bold")
    fig.suptitle("Ảnh mẫu của tập train theo thời điểm quay và nhãn has_target (ảnh gốc 1164×874)")
    save(fig, "01_sample_grid")


# ---------------------------------------------------------------- 02 khám phá

def f02_label_distribution():
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), width_ratios=[1, 1.35, 1])
    splits, names = ("train", "val", "test"), ("Train", "Validation", "Test")
    has = np.array([truth(s)["has"].mean() for s in splits])
    n = [len(truth(s)["has"]) for s in splits]
    b1 = axes[0].bar(names, has * 100, color=BLUE, width=0.55, label="có xe cùng làn", edgecolor=SURFACE, linewidth=1.5)
    b0 = axes[0].bar(names, (1 - has) * 100, bottom=has * 100, color=GRAY, width=0.55, label="không có xe", edgecolor=SURFACE, linewidth=1.5)
    axes[0].bar_label(b1, [f"{vn(h * 100, 1)}%" for h in has], label_type="center", color="white", fontsize=8)
    axes[0].bar_label(b0, [f"{vn((1 - h) * 100, 1)}%" for h in has], label_type="center", color="white", fontsize=8)
    axes[0].set(title="Nhãn has_target theo tập", ylabel="Tỉ lệ frame có nhãn (%)", ylim=(0, 100))
    axes[0].set_xticks(range(3), [f"{a}\n{th(b)}\nframe" for a, b in zip(names, n)])
    axes[0].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2)
    axes[0].grid(axis="x", visible=False)
    t = truth("train")
    counts = np.bincount(band_of(t["dist"][t["has"]]), minlength=5)
    bars = axes[1].bar(BANDS, counts, color=BLUE, width=0.6)
    axes[1].bar_label(bars, [f"{th(c)}\n({vn(c / counts.sum() * 100, 1)}%)" for c in counts], fontsize=8, padding=2)
    axes[1].set(title="Train: frame có xe theo vùng khoảng cách", xlabel="Khoảng cách radar tới xe cùng làn", ylabel="Số frame có nhãn", ylim=(0, counts.max() * 1.22))
    axes[1].grid(axis="x", visible=False)
    night = np.array([truth(s)["night"].mean() for s in splits])
    b = axes[2].bar(names, (1 - night) * 100, color=YELLOW, width=0.55, label="ngày", edgecolor=SURFACE, linewidth=1.5)
    c = axes[2].bar(names, night * 100, bottom=(1 - night) * 100, color=VIOLET, width=0.55, label="đêm", edgecolor=SURFACE, linewidth=1.5)
    axes[2].bar_label(b, [f"{vn((1 - x) * 100, 1)}%" for x in night], label_type="center", fontsize=8)
    axes[2].bar_label(c, [f"{vn(x * 100, 1)}%" for x in night], label_type="center", color="white", fontsize=8)
    axes[2].set(title="Thời điểm quay theo tập", ylabel="Tỉ lệ frame có nhãn (%)", ylim=(0, 100))
    axes[2].legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    axes[2].grid(axis="x", visible=False)
    fig.suptitle("Phân bố nhãn: nhãn bám theo đường, các video ngày và đêm được dùng")
    save(fig, "02_label_distribution")
    STATS["02_label_distribution"] = {"frames": dict(zip(splits, n)), "has_share": has.round(4).tolist(), "night_share": night.round(4).tolist(), "train_band_counts": counts.tolist()}


def f02_feature_histograms():
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.1))
    for s, name in (("train", "Train"), ("val", "Validation"), ("test", "Test")):
        t = truth(s)
        axes[0].hist(t["dist"][t["has"]], bins=np.arange(0, 101, 5), density=True, histtype="step", color=SPLIT[s], lw=2, label=name)
    axes[0].set(title="Khoảng cách tới xe cùng làn", xlabel="Khoảng cách radar (m)", ylabel="Mật độ (1/m)")
    axes[0].legend(fontsize=8)
    t = truth("train")
    off = (t["y"] - t["lane"])[t["has"]]
    axes[1].hist(off, bins=np.arange(-1.5, 1.51, 0.1), color=BLUE)
    for x in (-1.2, 1.2):
        axes[1].axvline(x, color=ORANGE, ls="--", lw=1.2)
    edge = (np.abs(off) >= 1.2).mean()
    axes[1].text(0.03, 0.95, f"{vn(edge * 100, 1)}% cách mép\nhành lang\nkhông quá 0,3 m", transform=axes[1].transAxes, va="top", fontsize=8)
    axes[1].set(title="Train: xe lệch bao xa khỏi tâm làn", xlabel="Lệch ngang so với tâm làn (m, dương = trái)", ylabel="Số frame có nhãn")
    lane = np.abs(t["lane"][t["has"]])
    axes[2].hist(lane, bins=np.arange(0, 8.01, 0.25), color=BLUE)
    axes[2].axvline(1.5, color=ORANGE, ls="--", lw=1.2)
    beyond = (lane > 1.5).mean()
    axes[2].text(0.97, 0.95, f"{vn(beyond * 100, 1)}% số xe nằm ở chỗ tâm làn\nđã rời trục thẳng quá 1,5 m", transform=axes[2].transAxes, ha="right", va="top", fontsize=8)
    axes[2].set(title="Train: làn cong bao nhiêu tại chỗ xe", xlabel="|Tâm làn − trục thẳng| tại khoảng cách của xe (m)", ylabel="Số frame có nhãn", yscale="log")
    fig.suptitle("Phân bố giá trị của nhãn (frame có xe cùng làn)")
    save(fig, "02_feature_histograms")
    STATS["02_feature_histograms"] = {"train_share_within_0.3m_of_lane_edge": round(float(edge), 4), "train_share_lane_off_axis_over_1.5m": round(float(beyond), 4),
                                      "train_distance_percentiles": {p: round(float(np.percentile(t["dist"][t["has"]], p)), 1) for p in (5, 25, 50, 75, 95)}}


def f02_target_position_size():
    t = truth("train")
    d, y = t["dist"][t["has"]], t["y"][t["has"]]
    u, v = common.project(d, y)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.3), width_ratios=[1.5, 1])
    h, _, _ = np.histogram2d(v, u, bins=[np.arange(0, 257, 4), np.arange(0, 513, 4)])
    im = axes[0].imshow(np.where(h > 0, h, np.nan), extent=(0, 512, 256, 0), cmap=SEQ, aspect="equal", norm=LogNorm(1, h.max()))
    axes[0].add_patch(Rectangle((128, 0), 256, 128, fill=False, ec=ORANGE, lw=1.5))
    axes[0].text(132, 124, "vùng fovea 256×128 px", color=ORANGE, fontsize=8, va="bottom")
    inside = ((u >= 128) & (u < 384) & (v >= 0) & (v < 128)).mean()
    box = [np.percentile(u, 1), np.percentile(u, 99), np.percentile(v, 1), np.percentile(v, 99)]
    axes[0].set(title="Điểm chạm đường của xe, chiếu từ radar lên ảnh", xlabel="Cột trong cửa sổ 512×256 (px)", ylabel="Hàng (px)")
    axes[0].grid(False)
    fig.colorbar(im, ax=axes[0], label="Số frame trong ô 4×4 px (thang log)", shrink=0.8)
    width = FOCAL * CAR_WIDTH_M / (d + common.RADAR_TO_CAMERA)
    axes[1].hist(width, bins=np.arange(0, 121, 4), color=BLUE)
    for x, name in ((8, "ô của fovea: 8 px"), (64, "ô của luồng toàn cảnh: 64 px")):
        axes[1].axvline(x, color=ORANGE, ls="--", lw=1.2)
        axes[1].text(x + 2, axes[1].get_ylim()[1] * 0.93, name, color=ORANGE, fontsize=8, rotation=90, va="top")
    axes[1].set(title=f"Bề rộng xe trong ảnh (giả định xe rộng {vn(CAR_WIDTH_M, 1)} m)", xlabel="Bề rộng ước tính (px)", ylabel="Số frame có nhãn")
    fig.suptitle("Xe cùng làn nằm ở đâu và to bao nhiêu trong ảnh (train, 19.971 frame có xe)")
    save(fig, "02_target_position_size")
    STATS["02_target_position_size"] = {"share_inside_fovea": round(float(inside), 4), "u_1_99_v_1_99_px": [round(float(b)) for b in box],
                                        "width_px_percentiles": {p: round(float(np.percentile(width, p)), 1) for p in (5, 50, 95)}}


def f02_tsne_embedding():
    from sklearn.manifold import TSNE
    t, p = truth("test"), predictions("test")
    xy = TSNE(n_components=2, init="pca", perplexity=30, random_state=0).fit_transform(p["feat"])
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6))
    kw = dict(s=3, linewidths=0)
    axes[0].scatter(*xy[~t["has"]].T, color=GRAY, label="không có xe", **kw)
    axes[0].scatter(*xy[t["has"]].T, color=BLUE, label="có xe cùng làn", **kw)
    axes[0].set_title("Theo nhãn has_target")
    axes[1].scatter(*xy[~t["has"]].T, color=GRID, **kw)
    sc = axes[1].scatter(*xy[t["has"]].T, c=t["dist"][t["has"]], cmap=SEQ, vmin=0, vmax=100, **kw)
    fig.colorbar(sc, ax=axes[1], label="Khoảng cách radar (m)", shrink=0.8)
    axes[1].set_title("Theo khoảng cách (xám: không có xe)")
    axes[2].scatter(*xy[~t["night"]].T, color=YELLOW, label="ngày", **kw)
    axes[2].scatter(*xy[t["night"]].T, color=VIOLET, label="đêm", **kw)
    axes[2].set_title("Theo thời điểm quay")
    for ax in axes:
        ax.set(xlabel="t-SNE 1", ylabel="t-SNE 2", xticks=[], yticks=[])
        ax.grid(False)
    for ax in (axes[0], axes[2]):
        ax.legend(fontsize=8, markerscale=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    fig.suptitle("t-SNE của vector 512 chiều ở thân chung của model đã train, trên 3.778 frame test")
    save(fig, "02_tsne_embedding")


def lane_edges(path, side):
    """Mép hành lang (tâm làn + side mét) chiếu lên cửa sổ 512x256; path: tâm làn ở 10, 20, ..., 130 m."""
    d = np.linspace(14, 100, 60)
    return common.project(d, np.interp(d, np.arange(0, 131, 10), np.concatenate([[0], path])) + side)


def f02_label_noise_examples():
    scbs = read_json(DATA / "manifests/split_manifest.json")["splits"]["train"]
    dense = np.load(CACHE / "dense_c.npy", mmap_mode="r")
    starts = np.flatnonzero(np.asarray(dense[:, 3]) == 1)
    assert len(starts) == len(scbs)
    start, seg = dict(zip(scbs, starts)), segs()
    straight, curved = read_csv(DATA / "labels/train.csv"), read_csv(DATA / "labels_curved/train.csv")
    cands = {"gain": [], "lose": []}
    for s, c in zip(straight, curved):
        if c["label_quality"] != "good" or seg[s["scb_id"]]["time_of_day"] != "ngay" or s["has_target"] == c["has_target"]:
            continue
        kind = "gain" if c["has_target"] == "1" else "lose"
        d = float(c["distance_m"] if kind == "gain" else s["distance_m"])
        if 45 <= d <= 85:
            path = np.asarray(dense[start[s["scb_id"]] + int(s["frame_index"]), 4:17])
            bend = abs(np.interp(d, np.arange(0, 131, 10), np.concatenate([[0], path])))
            if 2.5 <= bend <= 4.5:
                cands[kind].append((abs(bend - 3.5), s, c, path, d))
    fig, axes = plt.subplots(2, 3, figsize=(11, 4.4))
    titles = {"gain": "Hành lang thẳng: không có xe. Bám theo đường: có xe ở {} m", "lose": "Hành lang thẳng: có xe ở {} m. Bám theo đường: xe đó ở làn bên"}
    for row, kind in zip(axes, ("gain", "lose")):
        seen = set()
        picks = [c for c in sorted(cands[kind], key=lambda c: (c[0], c[1]["scb_id"], int(c[1]["frame_index"]))) if not (c[1]["scb_id"] in seen or seen.add(c[1]["scb_id"]))][:3]
        for ax, (_, s, c, path, d) in zip(row, picks):
            img, _ = crop(s)
            show(ax, img, f"{s['scb_id']}, frame {s['frame_index']}\n" + titles[kind].format(vn(d, 0)))
            for side in (-1.5, 1.5):
                ax.plot(*common.project(np.linspace(14, 100, 60), np.full(60, side)), color=ORANGE, ls="--", lw=1.1)
                ax.plot(*lane_edges(path, side), color=BLUE, lw=1.3)
            y = float(c["y_rel_m"] if kind == "gain" else s["y_rel_m"])
            ax.scatter(*common.project(d, y), s=90, facecolors="none", edgecolors="white", linewidths=1.6)
            ax.set(xlim=(0, 512), ylim=(256, 0))
    axes[0, 0].plot([], [], color=ORANGE, ls="--", lw=1.1, label="hành lang thẳng ±1,5 m quanh trục xe")
    axes[0, 0].plot([], [], color=BLUE, lw=1.3, label="hành lang bám theo đường xe mình sẽ đi")
    axes[0, 0].scatter([], [], s=50, facecolors="none", edgecolors=INK2, linewidths=1.4, label="vật thể radar được nói tới")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=3, fontsize=8)
    fig.suptitle("Ví dụ nhãn sai do định nghĩa: trên đoạn cong, hành lang thẳng chọn nhầm hoặc bỏ sót xe (train, ban ngày)")
    save(fig, "02_label_noise_examples")
    STATS["02_label_noise_examples"] = {"day_train_frames_45_85m_on_a_2.5_4.5m_bend_gaining_a_target": len(cands["gain"]), "losing_their_target": len(cands["lose"])}


# ---------------------------------------------------------------- 03 tiền xử lý

def f03_before_after_preprocess():
    t = truth("train")
    i = np.flatnonzero(t["has"] & ~t["night"] & (t["dist"] > 45) & (t["dist"] < 55) & (np.abs(t["y"] - t["lane"]) < 0.3))[0]
    r, full = t["rows"][i], frame_png(t["rows"][i])
    win, (x0, y0, vx, vy) = crop(r)
    fig = plt.figure(figsize=(11, 5.2))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.15, 1])
    ax = fig.add_subplot(grid[:, 0])
    show(ax, full, f"(a) Frame gốc 1164×874 ({r['scb_id']}, frame {r['frame_index']}, xe ở {vn(t['dist'][i], 1)} m)")
    ax.add_patch(Rectangle((x0, y0), 512, 256, fill=False, ec=BLUE, lw=1.8))
    ax.add_patch(Rectangle((x0 + 128, y0), 256, 128, fill=False, ec=ORANGE, lw=1.4))
    ax.plot(vx, vy, "+", color="white", ms=10, mew=1.8)
    ax.text(x0, y0 + 262, "cửa sổ 512×256 quanh điểm tụ (+)", color=BLUE, fontsize=8, va="top")
    ax = fig.add_subplot(grid[0, 1])
    show(ax, win, "(b) Luồng toàn cảnh: cửa sổ 512×256, đưa vào mạng ở nửa độ phân giải (256×128)")
    ax.add_patch(Rectangle((128, 0), 256, 127, fill=False, ec=ORANGE, lw=1.4))
    ax = fig.add_subplot(grid[1, 1])
    show(ax, win.crop((128, 0, 384, 128)), "(c) Luồng fovea: 256×128 px giữa ảnh, giữ đủ độ phân giải gốc")
    fig.suptitle("Trước và sau tiền xử lý: từ frame camera tới hai vùng mà mạng nhìn")
    save(fig, "03_before_after_preprocess")
    STATS["03_before_after_preprocess"] = {"scb": r["scb_id"], "frame": r["frame_index"], "distance_m": round(float(t["dist"][i]), 1)}


def f03_augmentation_grid():
    import torch
    import torch.nn.functional as F
    import train_distance as g
    c, x = np.load(CACHE / "val_c.npy"), np.load(CACHE / "val_x.npy", mmap_mode="r")
    light = [segs()[r["scb_id"]]["time_of_day"] for r in read_csv(DATA / "labels/val.csv")]
    i = next(k for k in range(len(c)) if c[k, 0] > 0 and 45 < c[k, 1] < 60 and abs(c[k, 2]) < 0.5 and light[k] == "ngay")
    d, frame = float(c[i, 1]), torch.from_numpy(np.array(x[i:i + 1])).float()
    luma = lambda t: F.pixel_shuffle(t[:, [6, 8, 7, 9]], 2)[0, 0].numpy()  # frame hiện tại, ghép 4 kênh Y lại thành ảnh đủ nét
    zoom = lambda s: g.magnify(frame, torch.tensor([s]))
    bright = frame.clone()
    bright[:, g.LUMA] = (bright[:, g.LUMA] * 1.2).clamp(0, 255)
    shifted = F.pad(frame, (2, 2, 2, 2), mode="replicate")[:, :, 4:132, 4:260]
    panels = [("Gốc: nhãn " + vn(d, 1) + " m", frame), (f"Thu nhỏ 0,8 lần: nhãn thành {vn(d / 0.8, 1)} m", zoom(0.8)),
              (f"Phóng 1,3 lần: nhãn thành {vn(d / 1.3, 1)} m", zoom(1.3)), ("Lật gương: khoảng cách giữ nguyên, lệch ngang đổi dấu", frame.flip(-1)[:, g.MIRROR]),
              ("Dịch 4 px sang trái và lên trên: nhãn giữ nguyên", shifted), ("Độ sáng ×1,2 (khoảng dùng: 0,8–1,2): nhãn giữ nguyên", bright)]
    fig, axes = plt.subplots(2, 3, figsize=(11, 4.3))
    for ax, (title, img) in zip(axes.flat, panels):
        show(ax, luma(img), title, cmap="gray", vmin=0, vmax=255)
    fig.suptitle("Các phép augmentation trên cùng một frame (kênh độ sáng của cửa sổ 512×256)")
    save(fig, "03_augmentation_grid")


def f03_split_distribution():
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.2), width_ratios=[1.6, 1])
    splits, names, w = ("train", "val", "test"), ("Train", "Validation", "Test"), 0.26
    out = {}
    for k, (s, name) in enumerate(zip(splits, names)):
        t = truth(s)
        share = np.bincount(band_of(t["dist"][t["has"]]), minlength=5) / t["has"].sum() * 100
        axes[0].bar(np.arange(5) + (k - 1) * w, share, w * 0.92, color=SPLIT[s], label=name)
        other = [t["has"].mean() * 100, t["night"].mean() * 100, t["added"].mean() * 100]
        bars = axes[1].bar(np.arange(3) + (k - 1) * w, other, w * 0.92, color=SPLIT[s], label=name)
        axes[1].bar_label(bars, [vn(o, 0) for o in other], fontsize=7, padding=1)
        out[s] = {"band_share_pct": share.round(1).tolist(), "has_pct": round(other[0], 1), "night_pct": round(other[1], 1), "added_pct": round(other[2], 1)}
    axes[0].set(title="Frame có xe theo vùng khoảng cách", ylabel="Tỉ lệ trong các frame có xe của tập (%)", xlabel="Khoảng cách radar")
    axes[0].set_xticks(range(5), BANDS)
    axes[1].set(title="Ba tỉ lệ khác", ylabel="Tỉ lệ frame có nhãn của tập (%)", ylim=(0, 100))
    axes[1].set_xticks(range(3), ["có xe\ncùng làn", "quay\nban đêm", "từ video\nthêm sau"])
    for ax in axes:
        ax.legend(fontsize=8)
        ax.grid(axis="x", visible=False)
    fig.suptitle("Phân bố nhãn trong từng tập sau khi chia theo video và chuyến đi")
    save(fig, "03_split_distribution")
    STATS["03_split_distribution"] = out


def f03_balance_before_after():
    b = read_json(RES / "balance.json")
    names, g = list(b["groups"]), list(b["groups"].values())
    filmed, balanced = np.array([x["share_as_filmed"] for x in g]) * 100, np.array([x["share_balanced"] for x in g]) * 100
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    y = np.arange(len(names))
    ax.barh(y - 0.2, filmed, 0.38, color=GRAY, label="như quay (lấy đều mọi frame)")
    bars = ax.barh(y + 0.2, balanced, 0.38, color=BLUE, label="lấy mẫu cân bằng (tỉ lệ với căn bậc hai kích thước nhóm)")
    ax.bar_label(bars, [f"{vn(a, 1)} → {vn(c, 1)}%" for a, c in zip(filmed, balanced)], fontsize=7.5, padding=3)
    ax.set_yticks(y, [f"{n}  ({th(x['frames'])} frame)" for n, x in zip(names, g)])
    ax.invert_yaxis()
    ax.set(xlabel="Phần của nhóm trong một epoch (%)", xlim=(0, filmed.max() * 1.22),
           title=f"Phân bố 12 nhóm frame train trước và sau khi lấy mẫu cân bằng ({th(b['usable_training_frames'])} frame dùng được)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="y", visible=False)
    save(fig, "03_balance_before_after")
    night = [sum(v[6:]) for v in (filmed, balanced)]
    STATS["03_balance_before_after"] = {"night_pct_before_after": [round(float(n), 1) for n in night], "under_20m_pct_before_after": [round(float(v[1] + v[7]), 1) for v in (filmed, balanced)],
                                        "80_100m_pct_before_after": [round(float(v[5] + v[11]), 1) for v in (filmed, balanced)]}


# ---------------------------------------------------------------- 04 kiến trúc

def macs(net):
    """Số phép nhân-cộng của các lớp conv và FC cho một ảnh [1,12,128,256], một lần nhìn (không lật gương)."""
    import torch
    import torch.nn as nn
    total = [0]

    def count(m, i, o):
        total[0] += o.numel() * (m.kernel_size[0] * m.kernel_size[1] * m.in_channels // m.groups if isinstance(m, nn.Conv2d) else m.in_features)

    hooks = [m.register_forward_hook(count) for m in net.modules() if isinstance(m, (nn.Conv2d, nn.Linear))]
    with torch.no_grad():
        net.eval()(torch.zeros(1, 12, 128, 256))
    for h in hooks:
        h.remove()
    return total[0]


def f04_params_flops():
    from distance_model import Gr14VinAI
    rounds = read_json(ROOT / "eval/rounds.json")
    built = [("Hai luồng, luồng toàn cảnh rộng một nửa\n(thử nghiệm `small`)", Gr14VinAI(context=32)), ("Hai luồng (vòng 3–5)", Gr14VinAI()),
             ("Hai luồng + đầu đường đi\n(model cuối)", Gr14VinAI(curve=True))]
    n = lambda net: sum(p.numel() for p in net.parameters())
    assert n(built[1][1]) == rounds[2]["cost"]["parameters"] and n(built[2][1]) == read_json(RES / "benchmark/benchmark.json")["cost"]["parameters"]
    names = ["Vòng 1: 12 khối MBConv", "Vòng 2: 23 khối MBConv"] + [b[0] for b in built]
    params = [rounds[0]["cost"]["parameters"], rounds[1]["cost"]["parameters"]] + [n(b[1]) for b in built]
    gmacs = [None, None] + [macs(b[1]) / 1e9 for b in built]
    colours = [GRAY, GRAY, GRAY, GRAY, BLUE]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.4), width_ratios=[1, 1, 1.05])
    bars = axes[0].barh(names, np.array(params) / 1e6, color=colours, height=0.6)
    axes[0].bar_label(bars, [vn(p / 1e6, 2) for p in params], padding=3)
    axes[0].set(title="Số tham số", xlabel="Triệu tham số", xlim=(0, max(params) / 1e6 * 1.18))
    bars = axes[1].barh(names, [m or 0 for m in gmacs], color=colours, height=0.6)
    axes[1].bar_label(bars, [vn(m, 2) if m else "không còn code để đo" for m in gmacs], padding=3, fontsize=8)
    axes[1].set(title="Phép nhân-cộng cho một lần nhìn", xlabel="GMACs (conv + FC), đầu vào 12×128×256", xlim=(0, max(m or 0 for m in gmacs) * 1.3))
    axes[1].set_yticklabels([])
    final = built[2][1]
    parts = {"Luồng toàn cảnh": final.context, "Luồng fovea": final.fovea, "Thân chung (FC 512)": final.trunk, "Tóm tắt cảnh (FC 256)": final.scene, "FiLM": final.film,
             "Đầu đường đi": final.path, "Ba đầu ra + attention": [final.has_target, final.distance, final.sideways, final.where]}
    sizes = {k: sum(n(m) for m in (v if isinstance(v, list) else [v])) for k, v in parts.items()}
    assert sum(sizes.values()) == n(final)
    bars = axes[2].barh(list(sizes), np.array(list(sizes.values())) / 1e6, color=BLUE, height=0.6)
    axes[2].bar_label(bars, [f"{vn(s / 1e6, 2)} ({vn(s / n(final) * 100, 1)}%)" for s in sizes.values()], padding=3, fontsize=8)
    axes[2].set(title="Model cuối: tham số theo thành phần", xlabel="Triệu tham số", xlim=(0, max(sizes.values()) / 1e6 * 1.35))
    for ax in axes:
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
    fig.suptitle("So sánh các mô hình ứng viên về kích thước và chi phí tính toán")
    save(fig, "04_params_flops")
    STATS["04_params_flops"] = {"names": [x.replace("\n", " ") for x in names], "params": params, "gmacs_one_look": [m and round(m, 3) for m in gmacs], "final_by_part": sizes}


# ---------------------------------------------------------------- 05 huấn luyện

def f05_loss_curves():
    log = parse_train_log(RES / "gr14vinai/train.log")
    best = int(log["epoch"][log["saved"]][-1])
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.plot(log["epoch"], log["train"], color=BLUE, label="train loss (frame đã augment, trọng số đang train)")
    ax.plot(log["epoch"], log["val"], color=ORANGE, label="val loss (3.424 frame validation, trọng số trung bình EMA)")
    ax.scatter(log["epoch"][log["saved"]], log["val"][log["saved"]], s=14, color=ORANGE, zorder=3)
    ax.axvline(best, color=INK2, ls=":", lw=1.2)
    ax.annotate(f"checkpoint được chọn: epoch {best}\nval loss {vn(log['val'][best - 1], 3)}, train loss {vn(log['train'][best - 1], 3)}", (best, log["val"][best - 1]),
                xytext=(best - 11, 0.9), fontsize=8, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set(title="Train loss và val loss theo epoch (model trong model/, seed 2)", xlabel="Epoch (mỗi epoch 20.000 frame)", ylabel="Loss (BCE has_target + 10 × Huber khoảng cách)",
           yscale="log", xlim=(1, 32.5))
    ax.legend(fontsize=8)
    save(fig, "05_loss_curves")
    STATS["05_loss_curves"] = {"best_epoch": best, "epochs_that_improved": log["epoch"][log["saved"]].astype(int).tolist(), "train_final": float(log["train"][-1]),
                               "val_final": float(log["val"][-1]), "val_min": float(log["val"].min()), "val_epoch_13_to_24": [float(log["val"][12]), float(log["val"][23])]}


def f05_metric_curves():
    log = parse_train_log(RES / "gr14vinai/train.log")
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.1))
    axes[0].plot(log["epoch"], log["mae"], color=BLUE)
    axes[0].set(title="Val MAE khoảng cách", ylabel="MAE (m)", ylim=(0, 9))
    axes[0].annotate(f"{vn(log['mae'][-1])} m", (32, log["mae"][-1]), xytext=(26, log["mae"][-1] + 1.2), fontsize=8)
    axes[1].plot(log["epoch"], log["acc"], color=BLUE)
    axes[1].set(title="Val accuracy của has_target (ngưỡng 0,5)", ylabel="Accuracy", ylim=(0.7, 1))
    axes[1].annotate(vn(log["acc"][-1], 3), (32, log["acc"][-1]), xytext=(27, log["acc"][-1] - 0.04), fontsize=8)
    axes[2].plot(log["epoch"], log["lane60"], color=BLUE, label="ở 60 m")
    axes[2].plot(log["epoch"], log["lane100"], color=ORANGE, label="ở 100 m")
    axes[2].set(title="Sai số trung vị của đầu đường đi", ylabel="|Tâm làn đoán − đường xe đã đi| (m)", ylim=(0, 2))
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.set(xlabel="Epoch", xlim=(1, 32.5))
    fig.suptitle("Các metric trên validation theo epoch (chạy mạng một lần, chưa lấy trung bình với ảnh lật gương)")
    save(fig, "05_metric_curves")
    STATS["05_metric_curves"] = {k: [float(log[k][e - 1]) for e in (1, 5, 10, 20, 32)] for k in ("mae", "acc", "lane60", "lane100")}


def f05_lr_schedule():
    import torch
    epochs, steps = 32, math.ceil(20000 / 48)  # như train(): epochs=32, batch=48, per_epoch=20000, lr=1e-3, pct_start=0.1
    opt = torch.optim.AdamW([torch.nn.Parameter(torch.zeros(1))], 1e-3, weight_decay=0.05)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 1e-3, epochs=epochs, steps_per_epoch=steps, pct_start=0.1)
    lr = []
    for _ in range(epochs * steps):
        lr.append(opt.param_groups[0]["lr"])
        opt.step()
        sched.step()
    lr = np.array(lr)
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(np.arange(len(lr)) / steps, lr * 1e3, color=BLUE)
    peak = lr.argmax() / steps
    ax.annotate(f"đỉnh 1,0×10⁻³ sau {vn(peak, 1)} epoch", (peak, 1), xytext=(5, 0.35), fontsize=8, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.set(title=f"Learning rate theo OneCycleLR ({epochs} epoch × {steps} bước, tính lại từ cấu hình trong src/train_distance.py)", xlabel="Epoch", ylabel="Learning rate (×10⁻³)", xlim=(0, 32))
    save(fig, "05_lr_schedule")
    STATS["05_lr_schedule"] = {"steps_per_epoch": steps, "start_lr": float(lr[0]), "peak_epoch": round(float(peak), 2), "end_lr": float(lr[-1])}


RUNS = [("zoom+curve, seed 0 (vòng 6: train có chạng vạng, validation còn 2 video chạng vạng)", "v2/train_zoom_curve.log", GRAY, ":"),
        ("zoom+curve+balance, seed 1", "v3/train_balance_s1.log", BLUE, "--"), ("zoom+curve+balance, seed 2 (được chọn)", "v3/train_balance_s2.log", BLUE, "-"),
        ("zoom+curve+balance+soft, seed 1", "v4/train_soft_s1.log", ORANGE, "--"), ("zoom+curve+balance+soft, seed 2", "v4/train_soft_s2.log", ORANGE, "-")]


def f05_runs_comparison():
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.7))
    out = {}
    for name, file, colour, ls in RUNS:
        log = parse_train_log(RES / file)
        for ax, key in zip(axes, ("val", "mae")):
            ax.plot(log["epoch"], log[key], color=colour, ls=ls, lw=1.6, label=name)
        out[name] = {"val_loss_last": float(log["val"][-1]), "val_mae_last": float(log["mae"][-1]), "train_loss_last": float(log["train"][-1]), "best_epoch": int(log["epoch"][log["saved"]][-1])}
    axes[0].set(title="Val loss", xlabel="Epoch", ylabel="Val loss (nhãn của chính cách train đó)", xlim=(8, 32.5), ylim=(0.22, 0.45))
    axes[1].set(title="Val MAE", xlabel="Epoch", ylabel="Val MAE (m)", xlim=(8, 32.5), ylim=(2.1, 3.3))
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=2, fontsize=8)
    fig.suptitle("Năm lần train cùng kiến trúc và cùng hyperparameter, khác cách train và seed (từ epoch 8)")
    save(fig, "05_runs_comparison")
    STATS["05_runs_comparison"] = out


# ---------------------------------------------------------------- 06 đánh giá

def f06_confusion_matrix():
    t, p = truth("test"), predictions("test")
    det = p["prob"] > threshold()
    m = np.array([[(~t["has"] & ~det).sum(), (~t["has"] & det).sum()], [(t["has"] & ~det).sum(), (t["has"] & det).sum()]])
    share = m / m.sum(1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4.6, 3.8))
    im = ax.imshow(share, cmap=SEQ, vmin=0, vmax=1)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{vn(share[i, j] * 100, 1)}%\n({th(m[i, j])} frame)", ha="center", va="center", color="white" if share[i, j] > 0.5 else INK, fontsize=10)
    ax.set_xticks(range(2), ["không có xe", "có xe"])
    ax.set_yticks(range(2), ["không có xe", "có xe"])
    ax.set(xlabel=f"Model trả lời (ngưỡng {vn(threshold())})", ylabel="Nhãn radar", title="Confusion matrix của has_target trên tập test\n(chuẩn hóa theo hàng)")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Tỉ lệ trong hàng", shrink=0.8)
    save(fig, "06_confusion_matrix")
    STATS["06_confusion_matrix"] = {"tn_fp_fn_tp": m.ravel().tolist(), "row_share": share.round(4).tolist()}


def f06_pr_roc():
    from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve
    t, p, th = truth("test"), predictions("test"), threshold()
    s = scores(t["has"], t["dist"], p["prob"], p["dist"], th)
    prec, rec, _ = precision_recall_curve(t["has"], p["prob"])
    fpr, tpr, _ = roc_curve(t["has"], p["prob"])
    ap, auc = average_precision_score(t["has"], p["prob"]), roc_auc_score(t["has"], p["prob"])
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.7))
    axes[0].plot(rec, prec, color=BLUE)
    axes[0].axhline(t["has"].mean(), color=GRAY, ls="--", lw=1)
    axes[0].text(0.52, t["has"].mean() + 0.006, f"luôn trả lời có xe: precision {vn(t['has'].mean(), 3)}", color=INK2, fontsize=8)
    axes[0].scatter([s["recall"]], [s["precision"]], s=45, color=ORANGE, zorder=3)
    axes[0].annotate(f"ngưỡng {vn(th)}: P {vn(s['precision'], 3)}, R {vn(s['recall'], 3)}", (s["recall"], s["precision"]), xytext=(0.56, 0.86), fontsize=8, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    axes[0].set(title=f"Precision–Recall (AP = {vn(ap, 3)})", xlabel="Recall", ylabel="Precision", xlim=(0.5, 1.005), ylim=(0.55, 1.005))
    fp_rate = ((p["prob"] > th) & ~t["has"]).sum() / (~t["has"]).sum()
    axes[1].plot(fpr, tpr, color=BLUE)
    axes[1].plot([0, 1], [0, 1], color=GRAY, ls="--", lw=1)
    axes[1].scatter([fp_rate], [s["recall"]], s=45, color=ORANGE, zorder=3)
    axes[1].annotate(f"ngưỡng {vn(th)}: báo nhầm {vn(fp_rate * 100, 1)}%\nsố frame không có xe", (fp_rate, s["recall"]), xytext=(0.3, 0.7), fontsize=8, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    axes[1].set(title=f"ROC (AUC = {vn(auc, 3)})", xlabel="Tỉ lệ báo nhầm (false positive rate)", ylabel="Recall (true positive rate)", xlim=(-0.01, 1), ylim=(0, 1.01))
    fig.suptitle("Đầu ra has_target trên tập test: ngưỡng 0,40 được chọn trên validation, không phải trên các đường này")
    save(fig, "06_pr_roc")
    STATS["06_pr_roc"] = {"ap": round(float(ap), 4), "auc": round(float(auc), 4), "fpr_at_threshold": round(float(fp_rate), 4)}


def f06_pred_vs_true():
    t, p = truth("test"), predictions("test")
    d, pred = t["dist"][t["has"]], p["dist"][t["has"]]
    err = pred - d
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), width_ratios=[1, 1.1])
    axes[0].fill_between([0, 100], [-5, 95], [5, 105], color=BLUE, alpha=0.12, lw=0, label="lệch không quá 5 m")
    axes[0].plot([0, 100], [0, 100], color=INK2, lw=1)
    axes[0].scatter(d, pred, s=4, color=BLUE, alpha=0.35, linewidths=0)
    axes[0].set(title="Khoảng cách model đoán so với radar", xlabel="Khoảng cách radar (m)", ylabel="Khoảng cách model đoán (m)", xlim=(0, 100), ylim=(0, 100), aspect="equal")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[1].hist(np.clip(err, -30, 30), bins=np.arange(-30, 30.5, 1), color=BLUE)
    axes[1].axvline(0, color=INK2, lw=1)
    axes[1].set(title="Sai số có dấu (âm = model đoán gần hơn radar)", xlabel="Model − radar (m), cắt ở ±30 m", ylabel="Số frame (thang log)", yscale="log")
    axes[1].text(0.03, 0.95, f"trung vị {vn(np.median(err))} m\n{vn((np.abs(err) > 10).mean() * 100, 1)}% lệch quá 10 m\n{vn((err > 10).mean() * 100, 1)}% đoán xa hơn quá 10 m", transform=axes[1].transAxes, va="top", fontsize=8)
    fig.suptitle("Sai số khoảng cách trên 2.226 frame test có xe cùng làn (kể cả frame model báo không có xe)")
    save(fig, "06_pred_vs_true")
    STATS["06_pred_vs_true"] = {"signed_median": round(float(np.median(err)), 2), "signed_mean": round(float(err.mean()), 2), "share_over_10m": round(float((np.abs(err) > 10).mean()), 4),
                                "share_too_far_over_10m": round(float((err > 10).mean()), 4), "share_too_near_over_10m": round(float((err < -10).mean()), 4), "corr": round(float(np.corrcoef(d, pred)[0, 1]), 3)}


def f06_by_group():
    t, p, th = truth("test"), predictions("test"), threshold()
    bench = read_json(RES / "benchmark/benchmark.json")
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.4), width_ratios=[1.2, 1.2, 1, 1])
    band = [scores(t["has"] & (t["dist"] > lo) & (t["dist"] <= hi), t["dist"], p["prob"], p["dist"], th) for lo, hi in RANGES]
    for b, (name, ref) in zip(band, bench["by_range"].items()):
        assert abs(b["mae"] - ref["mae_m"]) < 0.03 and abs(b["recall"] - ref["recall"]) < 0.01, name
    x = [f"{lo}–{hi}\n(n={b['targets']})" for (lo, hi), b in zip(RANGES, band)]
    bars = axes[0].bar(x, [b["mae"] for b in band], color=BLUE, width=0.6, label="MAE")
    axes[0].bar_label(bars, [vn(b["mae"]) for b in band], fontsize=8, padding=2)
    axes[0].scatter(x, [b["median"] for b in band], color=ORANGE, zorder=3, s=28, label="trung vị")
    axes[0].set(title="Sai số theo vùng khoảng cách", xlabel="Khoảng cách radar (m)", ylabel="Sai số tuyệt đối (m)", ylim=(0, 4))
    axes[0].legend(fontsize=8, loc="upper left")
    bars = axes[1].bar(x, [b["recall"] for b in band], color=BLUE, width=0.6)
    axes[1].bar_label(bars, [vn(b["recall"], 3) for b in band], fontsize=8, padding=2)
    axes[1].set(title="Recall của has_target theo vùng", xlabel="Khoảng cách radar (m)", ylabel="Recall", ylim=(0.7, 1.02))
    groups = [("22 video\nngày", ~t["night"], YELLOW), ("12 video\nđêm", t["night"], VIOLET), ("9 video\nban đầu", ~t["added"], GRAY), ("25 video\nthêm sau", t["added"], BLUE)]
    g = [scores(t["has"][m], t["dist"][m], p["prob"][m], p["dist"][m], th) for _, m, _ in groups]
    for ax, key, nd, title, lim in ((axes[2], "mae", 2, "MAE theo nhóm video (m)", (0, 4)), (axes[3], "f1", 3, "F1 theo nhóm video", (0.85, 1))):
        bars = ax.bar([n for n, _, _ in groups], [s[key] for s in g], color=[c for _, _, c in groups], width=0.6)
        ax.bar_label(bars, [vn(s[key], nd) for s in g], fontsize=8, padding=2)
        ax.set(title=title, ylim=lim)
    for ax in axes:
        ax.grid(axis="x", visible=False)
    fig.suptitle("Kết quả trên tập test theo vùng khoảng cách, thời điểm quay và đợt thu thập")
    save(fig, "06_by_group")
    STATS["06_by_group"] = {"bands": [{k: round(float(v), 3) for k, v in b.items()} for b in band], "groups": {n.replace("\n", " "): {k: round(float(v), 3) for k, v in s.items()} for (n, _, _), s in zip(groups, g)}}


def f06_baselines():
    e = read_json(RES / "eval/evidence.json")
    names = ["Đoán trung vị", "Hình học (bbox + pinhole)", "gr14VinAI"]
    colours = [GRAY, ORANGE, BLUE]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.8))
    for ax, source, keys, labels, title in (
            (axes[0], e["full_test"], ("precision", "recall", "f1"), ("Precision", "Recall", "F1"), "has_target trên cả 3.778 frame test"),
            (axes[1], e["scores"], ("pass_on", "pass_off", "pass_edge", "pass"), ("on (150)\nxe rõ ràng", "off (75)\nkhông có xe", "edge (75)\nsát ngưỡng", "cả 300 case"), "Bộ 300 case từ tập test (đạt = lệch ≤ 15%, hoặc báo đúng không có xe)")):
        for k, (name, colour, s) in enumerate(zip(names, colours, source.values())):
            bars = ax.bar(np.arange(len(keys)) + (k - 1) * 0.27, [s[key] for key in keys], 0.25, color=colour, label=name)
            ax.bar_label(bars, [vn(s[key], 2) for key in keys], fontsize=7, padding=1)
        ax.set_xticks(range(len(keys)), labels)
        ax.set(title=title, ylim=(0, 1.12))
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Giá trị (0–1)")
    axes[1].set_ylabel("Tỉ lệ case đạt")
    fig.legend(*axes[1].get_legend_handles_labels(), loc="outside lower center", ncol=3, fontsize=8)
    fig.suptitle("So sánh với hai baseline trên cùng tập test và cùng nhãn bám theo đường")
    save(fig, "06_baselines")


def f06_ablation():
    change = read_json(ROOT / "eval/label_change.json")["rows"]
    v3, v4 = parse_val_compare(RES / "v3/val_compare.log"), parse_val_compare(RES / "v4/val_compare.log")
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.8), width_ratios=[1, 1])
    own = [r for r in change if "chính nó" in r["labels"]]
    names = ["Vòng 5: 80 video train,\nnhãn hành lang thẳng", "284 video train,\nnhãn hành lang thẳng", "Vòng 6: 284 video train,\nnhãn bám theo đường"]
    assert len(own) == 3 and own[0]["model"].startswith("Vòng 5") and "Vòng 6" in own[2]["model"]
    bars = axes[0].bar(names, [r["all"]["mae_m"] for r in own], color=[GRAY, GRAY, BLUE], width=0.55)
    axes[0].bar_label(bars, [f"MAE {vn(r['all']['mae_m'])} m\nF1 {vn(r['all']['f1'], 3)}" for r in own], fontsize=8, padding=2)
    axes[0].set(title="(a) Thêm dữ liệu và đổi định nghĩa nhãn: test 36 video,\nmỗi model chấm theo nhãn của chính nó (số ghi lại 08/10/2026)", ylabel="MAE trên tập test (m)", ylim=(0, 5.6))
    axes[0].grid(axis="x", visible=False)
    rows = [("Vòng 6: zoom+curve, train có chạng vạng (seed 0)", v3["gr14VinAI"]), ("+ bỏ chạng vạng, + lấy mẫu cân bằng (seed 1)", v3["balance_s1"]),
            ("+ bỏ chạng vạng, + lấy mẫu cân bằng (seed 2, được chọn)", v3["balance_s2"]), ("+ nhãn mềm ở sát ngưỡng (seed 1)", v4["soft_s1"]), ("+ nhãn mềm ở sát ngưỡng (seed 2)", v4["soft_s2"])]
    assert all(r["frames"] == 3424 for _, r in rows)
    for k, (name, r) in enumerate(rows):
        axes[1].plot([2.0, r["mae"]], [k, k], color=GRID, lw=1.5, zorder=1)
        axes[1].scatter(r["mae"], k, s=70, color=BLUE if r is v3["balance_s2"] else GRAY, zorder=3)
        axes[1].text(r["mae"] + 0.012, k, f"{vn(r['mae'])} m | F1 {vn(r['f1'], 3)}", va="center", fontsize=8)
    axes[1].set_yticks(range(len(rows)), [r[0] for r in rows])
    axes[1].invert_yaxis()
    axes[1].set(title="(b) Ba cách train trên cùng 3.424 frame validation\n(mỗi hàng là một lần train)", xlabel="Val MAE (m), chạy với ảnh lật gương", xlim=(2.0, 2.55))
    axes[1].grid(axis="y", visible=False)
    fig.suptitle("Ablation ở mức dữ liệu, nhãn và cách train (chưa có ablation từng thành phần kiến trúc)")
    save(fig, "06_ablation")
    STATS["06_ablation"] = {"test36_own_labels": [{"model": r["model"], **r["all"]} for r in own], "validation": {**v3, **v4}}


def f06_examples_grid():
    t, p, th = truth("test"), predictions("test"), threshold()
    det, err = p["prob"] > th, np.abs(p["dist"] - t["dist"])
    tp, used = t["has"] & det, set()

    def pick(mask, key, largest=True):
        """Frame có `key` lớn nhất (hoặc nhỏ nhất) trong mask, mỗi video chỉ lấy một lần."""
        for i in np.argsort(np.where(mask, -key if largest else key, np.inf)):
            if mask[i] and t["scb"][i] not in used:
                used.add(t["scb"][i])
                return i

    good = [("Đúng, xe gần", pick(tp & (t["dist"] < 30) & ~t["night"], err, False)), ("Đúng, xe xa", pick(tp & (t["dist"] > 85) & ~t["night"], err, False)),
            ("Đúng, ban đêm", pick(tp & t["night"] & (t["dist"] > 50), err, False)), ("Đúng, không có xe", pick(~t["has"] & ~det, p["prob"], False))]
    bad = [("Sai: bỏ sót xe", pick(t["has"] & ~det, p["prob"], False)), ("Sai: báo nhầm", pick(~t["has"] & det, p["prob"])),
           ("Sai: khoảng cách lệch nhiều nhất", pick(tp, np.nan_to_num(err))), ("Sai: bỏ sót ban đêm", pick(t["has"] & ~det & t["night"], p["prob"], False))]
    fig, axes = plt.subplots(2, 4, figsize=(13, 4.3))
    out = []
    for ax, (kind, i) in zip(axes.flat, good + bad):
        img, _ = crop(t["rows"][i])
        radar = f"radar {vn(t['dist'][i], 1)} m" if t["has"][i] else "radar: không có xe"
        model = f"model {vn(p['dist'][i], 1)} m" if det[i] else "model: không có xe"
        show(ax, img, f"{kind}\n{t['scb'][i]} f{t['rows'][i]['frame_index']} | {radar} | {model} | p = {vn(p['prob'][i])}")
        if t["has"][i]:
            ax.scatter(*common.project(t["dist"][i], t["y"][i]), s=110, facecolors="none", edgecolors="white", linewidths=1.5)
        ax.set(xlim=(0, 512), ylim=(256, 0))
        for s in ax.spines.values():
            s.set(visible=True, color=AQUA if kind.startswith("Đúng") else RED, linewidth=2.2)
        out.append({"kind": kind, "scb": str(t["scb"][i]), "frame": t["rows"][i]["frame_index"], "radar_m": None if not t["has"][i] else round(float(t["dist"][i]), 1),
                    "model_m": round(float(p["dist"][i]), 1), "prob": round(float(p["prob"][i]), 3), "night": bool(t["night"][i])})
    fig.suptitle(f"Ví dụ dự đoán trên tập test, kèm xác suất has_target p (ngưỡng {vn(th)}); vòng trắng = vị trí radar của xe cùng làn")
    save(fig, "06_examples_grid")
    STATS["06_examples_grid"] = out


def f06_confidence_distribution():
    t, p, thr = truth("test"), predictions("test"), threshold()
    bins = np.linspace(0, 1, 41)
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    ax.hist(p["prob"][~t["has"]], bins=bins, color=GRAY, alpha=0.85, label=f"nhãn radar: không có xe ({th((~t['has']).sum())} frame)")
    ax.hist(p["prob"][t["has"]], bins=bins, color=BLUE, alpha=0.75, label=f"nhãn radar: có xe ({th(t['has'].sum())} frame)")
    ax.axvline(thr, color=ORANGE, ls="--", lw=1.4)
    ax.text(thr + 0.01, 0.55, f"ngưỡng {vn(thr)}", color=ORANGE, fontsize=8, transform=ax.get_xaxis_transform())
    unsure = ((p["prob"] > 0.1) & (p["prob"] < 0.9)).mean()
    ax.set(title="Phân bố xác suất has_target trên tập test", xlabel="Xác suất has_target mà model trả về", ylabel="Số frame (thang log)", yscale="log", xlim=(0, 1))
    ax.legend(fontsize=8, loc="upper center")
    save(fig, "06_confidence_distribution")
    STATS["06_confidence_distribution"] = {"share_between_0.1_and_0.9": round(float(unsure), 4), "share_of_errors_between_0.1_and_0.9": round(float(((p["prob"] > 0.1) & (p["prob"] < 0.9))[(p["prob"] > thr) != t["has"]].mean()), 4),
                                           "positives_above_0.9": round(float((p["prob"][t["has"]] > 0.9).mean()), 4), "negatives_below_0.1": round(float((p["prob"][~t["has"]] < 0.1).mean()), 4)}


def f06_per_video():
    by, seg = read_json(RES / "benchmark/benchmark.json")["by_scb"], segs()
    rows = sorted(((s, v) for s, v in by.items() if "mae_m" in v), key=lambda r: r[1]["mae_m"])
    names = [f"{s} ({v['target_frames']})" for s, v in rows]
    colours = [LIGHT[seg[s]["time_of_day"]] for s, _ in rows]
    fig, axes = plt.subplots(1, 2, figsize=(10, 7), sharey=True)
    axes[0].barh(names, [v["mae_m"] for _, v in rows], color=colours, height=0.7)
    axes[0].axvline(read_json(RES / "benchmark/benchmark.json")["test"]["mae_m"], color=INK2, ls="--", lw=1)
    axes[0].set(title="MAE khoảng cách", xlabel="MAE (m); nét đứt = cả tập test", ylabel="Video test (số frame có xe)")
    axes[1].barh(names, [v["f1"] for _, v in rows], color=colours, height=0.7)
    axes[1].set(title="F1 của has_target", xlabel="F1", xlim=(0, 1.02))
    fig.legend(handles=[Patch(color=YELLOW, label="video quay ban ngày"), Patch(color=VIOLET, label="video quay ban đêm")], loc="outside lower center", ncol=2, fontsize=8)
    for ax in axes:
        ax.grid(axis="y", visible=False)
    fig.suptitle(f"Kết quả trên từng video test có xe cùng làn ({len(rows)} trong 34 video), xếp theo MAE")
    save(fig, "06_per_video")
    STATS["06_per_video"] = {"videos_without_target": [s for s, v in by.items() if "mae_m" not in v], "mae_over_4m": [s for s, v in rows if v["mae_m"] > 4], "f1_under_0.85": [s for s, v in rows if v["f1"] < 0.85]}


# ---------------------------------------------------------------- 07 triển khai

def f07_latency():
    c, decode = read_json(RES / "benchmark/benchmark.json")["cost"], read_json(RES / "benchmark/decode.json")["decode_and_crop_ms_per_frame"]
    names = ["Giải mã video + cắt ảnh\n(ffmpeg, đo trên 2 video)", "Model ONNX FP32, đo ngắn\n(500 lần, trung vị)", "Model ONNX FP32, đo ngắn\n(500 lần, P95)", "Cả pipeline, chạy liên tục\n(40.799 frame của 34 video)"]
    vals = [decode, c["latency_ms"]["median"], c["latency_ms"]["p95"], c["pipeline_ms_per_frame"]]
    fig, ax = plt.subplots(figsize=(8, 3.1))
    bars = ax.barh(names, vals, color=[GRAY, BLUE, BLUE, ORANGE], height=0.55)
    ax.bar_label(bars, [f"{vn(v)} ms" for v in vals], padding=3)
    ax.axvline(50, color=INK, ls="--", lw=1.2)
    ax.text(50.6, -0.42, "50 ms = 20 FPS của camera", fontsize=8, va="top")
    ax.invert_yaxis()
    ax.set(title="Thời gian xử lý mỗi frame trên CPU laptop (onnxruntime, 4 luồng, batch 1)", xlabel="Thời gian mỗi frame (ms)", xlim=(0, 66))
    ax.grid(axis="y", visible=False)
    save(fig, "07_latency")


def f07_accuracy_vs_speed():
    rounds, bench = read_json(ROOT / "eval/rounds.json"), read_json(RES / "benchmark/benchmark.json")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    x, y = [r["cost"]["latency_ms"]["median"] for r in rounds], [r["test"]["mae_m"] for r in rounds]
    ax.plot(x, y, color=GRAY, lw=1, zorder=1)
    ax.scatter(x, y, s=55, color=GRAY, zorder=3, label="vòng 1–5: 10 video test ban đầu, nhãn hành lang thẳng")
    for r, a, b in zip(rounds, x, y):
        ax.annotate(re.sub(r" \(.*", "", r["name"]) + f" ({vn(r['cost']['parameters'] / 1e6, 2)} triệu)", (a, b), xytext=(7, 4), textcoords="offset points", fontsize=8)
    ax.scatter([bench["cost"]["latency_ms"]["median"]], [bench["test"]["mae_m"]], s=75, facecolors="none", edgecolors=BLUE, linewidths=2, zorder=3,
               label="model cuối: 34 video test, nhãn bám theo đường (thước đo khác)")
    ax.annotate(f"Model cuối ({vn(bench['cost']['parameters'] / 1e6, 2)} triệu)", (bench["cost"]["latency_ms"]["median"], bench["test"]["mae_m"]), xytext=(7, -12), textcoords="offset points", fontsize=8)
    ax.axvline(50, color=INK, ls="--", lw=1)
    ax.text(50.6, 8.3, "50 ms = 20 FPS", fontsize=8)
    ax.set(title="Độ chính xác so với tốc độ qua các vòng (latency đo ngắn trên CPU, trung vị)", xlabel="Latency trung vị của file ONNX (ms)", ylabel="MAE trên tập test của vòng đó (m)", xlim=(0, 66), ylim=(0, 9))
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    save(fig, "07_accuracy_vs_speed")
    STATS["07_accuracy_vs_speed"] = {"rounds": [{"name": r["name"], "latency_ms": a, "mae_m": b} for r, a, b in zip(rounds, x, y)]}


if __name__ == "__main__":
    wanted = sys.argv[1:]
    figures = [f for name, f in sorted(globals().items()) if re.match(r"f\d\d_", name) and (not wanted or any(name[1:].startswith(w) for w in wanted))]
    if not wanted or any(w.startswith("06") for w in wanted):
        check_predictions()
    for f in figures:
        print(f.__name__)
        f()
    OUT.mkdir(parents=True, exist_ok=True)
    stats_file = OUT / "figure_stats.json"
    old = read_json(stats_file) if stats_file.exists() else {}
    stats_file.write_text(json.dumps({**old, **STATS}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
