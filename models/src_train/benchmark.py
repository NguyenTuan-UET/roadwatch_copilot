"""Measure every benchmark of gr14VinAI from the trained checkpoint model/gr14VinAI.pt.

    python src/benchmark.py     # -> results/benchmark/benchmark.md, benchmark.json; rewrites model/gr14VinAI.onnx

Nothing is read from earlier result files: the checkpoint is evaluated again, exported again, and run
again on the test videos, so the report can only contain what the trained network actually does.

  1. distance accuracy on the test split: MAE, median, RMSE, by distance range, by group of videos, per SCB
  2. has_target: precision, recall, F1 at the threshold chosen on validation
  3. cost: parameters, ONNX size, CPU latency (mean, median, p95, FPS), whole pipeline per frame
  4. steadiness on the test videos at 20 fps, raw and after smoothing
"""
import csv
import json
import platform
import time

import numpy as np
import onnxruntime as ort
import torch

import train as g
from common import DATA, RAW, ROOT, feed, labelled, onnx_session, read_yuv_frames, run_pair, train_median, vanishing_point

OUT = ROOT / "results" / "benchmark"
RANGES = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
DISTANCE = ("mae_m", "median_m", "rmse_m", "abs_rel", "within_5m", "within_10m")


def accuracy(has, dist, prob, pred, threshold):
    """has/dist: radar label per frame. prob/pred: the network's answer. Distance errors on radar-target frames."""
    err = np.abs(pred[has] - dist[has])
    det = prob > threshold
    tp, fp, fn = int((det & has).sum()), int((det & ~has).sum()), int((~det & has).sum())
    out = {"frames": len(has), "target_frames": int(has.sum()), "precision": tp / max(tp + fp, 1),
           "recall": tp / max(tp + fn, 1), "f1": 2 * tp / max(2 * tp + fp + fn, 1)}
    if len(err):
        out |= {"mae_m": err.mean(), "median_m": np.median(err), "rmse_m": np.sqrt((err ** 2).mean()),
                # distance is a number, not a class, so "how often is it right" needs a tolerance
                "abs_rel": (err / dist[has]).mean(), "within_5m": (err <= 5).mean(), "within_10m": (err <= 10).mean()}
    return {k: round(float(v), 3) if isinstance(v, (float, np.floating)) else v for k, v in out.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = g.load_net(dev)
    (xv, yv), (xs, ys) = g.judged("val"), g.judged("test")
    threshold = g.best_threshold(g.predict(net, xv, yv, dev)[1], yv[:, 0] > 0)  # chosen on validation only
    _, prob, pred = g.predict(net, xs, ys, dev)
    has, dist = ys[:, 0] > 0, ys[:, 1]
    scb_of = np.array([r["scb_id"] for r in labelled("test")])
    assert len(scb_of) == len(ys), "the cache does not match the labels of the test split"

    report = {"threshold": round(threshold, 2), "test": accuracy(has, dist, prob, pred, threshold)}
    guess = np.full_like(pred, train_median())  # a "model" that never looks at the image
    report["median_guess"] = {k: v for k, v in accuracy(has, dist, prob, guess, threshold).items() if k in DISTANCE}
    # precision and F1 need the no-target frames too, which belong to no distance range: keep recall only
    report["by_range"] = {f"{lo}-{hi} m": {k: v for k, v in accuracy(has & (dist > lo) & (dist <= hi), dist, prob, pred, threshold).items()
                                           if k not in ("precision", "f1", "frames")}
                          for lo, hi in RANGES if (has & (dist > lo) & (dist <= hi)).any()}
    if (DATA / "manifests/segments.csv").exists():  # which test videos are the original ones, and the time of day of each
        seg = {r["scb_id"]: r for r in csv.DictReader(open(DATA / "manifests/segments.csv", encoding="utf-8"))}
        origin, light = (np.array([seg[s][k] for s in scb_of]) for k in ("origin", "time_of_day"))
        groups = {"video test ban đầu": origin == "original", "video test thêm sau": origin == "added",
                  "ban ngày": light == "ngay", "chạng vạng": light == "chang_vang", "ban đêm": light == "dem"}
        report["by_group"] = {f"{len(set(scb_of[m]))} {name}": accuracy(has[m], dist[m], prob[m], pred[m], threshold) for name, m in groups.items() if m.any()}
    report["by_scb"] = {s: accuracy(has[scb_of == s], dist[scb_of == s], prob[scb_of == s], pred[scb_of == s], threshold)
                        for s in sorted(set(scb_of), key=lambda s: int(s[3:]))}

    # cost: the ONNX is exported again from the checkpoint, so model/ holds exactly the file that was measured
    onnx_path = g.ONNX
    g.to_onnx(onnx_path)
    sess = onnx_session(onnx_path)
    frame = feed(xs[0])
    for _ in range(50):
        sess.run(None, frame)
    ms = []
    for _ in range(500):
        t = time.perf_counter()
        sess.run(None, frame)
        ms.append((time.perf_counter() - t) * 1000)
    report["cost"] = {"parameters": sum(p.numel() for p in net.parameters()),
                      "onnx_mb": round(onnx_path.stat().st_size / 1e6, 2),
                      "latency_ms": {"mean": round(np.mean(ms), 2), "median": round(np.median(ms), 2), "p95": round(np.percentile(ms, 95), 2)},
                      "fps": round(1000 / np.median(ms))}

    # the network on every frame of the test videos: steadiness, and what a frame costs end to end
    runs, seconds, frames = {"raw": [], "smoothed": []}, 0.0, 0
    for scb in report["by_scb"]:
        t, prev, rows = time.perf_counter(), None, []
        for f in read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb)):
            p, d = run_pair(sess, np.concatenate([f if prev is None else prev, f]))[:2]
            rows.append((p.item(), d.item()))
            prev = f
        seconds, frames = seconds + time.perf_counter() - t, frames + len(rows)
        p, d = np.array(rows).T
        sp, sd = g.smooth(p, d, threshold)
        runs["raw"].append((p > threshold, d))
        runs["smoothed"].append((sp > threshold, sd))
    report["cost"]["pipeline_ms_per_frame"] = round(seconds / frames * 1000, 2)  # decode + crop + network
    report["steadiness"] = {}
    for name, parts in runs.items():
        change = np.concatenate([np.abs(np.diff(d))[on[1:] & on[:-1]] for on, d in parts])
        flips = sum(np.count_nonzero(on[1:] != on[:-1]) for on, _ in parts) / frames * 1200
        report["steadiness"][name] = {"change_m_mean": round(float(change.mean()), 2), "change_m_p95": round(float(np.percentile(change, 95)), 2),
                                      "target_flips_per_minute": round(flips, 1)}
    report["environment"] = {"cpu": platform.processor(), "onnxruntime_threads": 4, "onnxruntime": ort.__version__,
                             "torch": torch.__version__, "accuracy_device": str(dev), "video_frames": frames}

    (OUT / "benchmark.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (OUT / "benchmark.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


def markdown(r):
    t, c, s = r["test"], r["cost"], r["steadiness"]
    row = lambda name, a: f"| {name} | {a['target_frames']} | {a.get('mae_m', '-')} | {a.get('median_m', '-')} | {a.get('rmse_m', '-')} | {a['recall']} | {a.get('f1', '-')} |"
    lines = [
        "# Benchmark gr14VinAI", "",
        f"Đo lại từ checkpoint `model/gr14VinAI.pt` bằng `python src/benchmark.py`. Ngưỡng has_target {r['threshold']} chọn trên validation.", "",
        "## 1. Khoảng cách trên tập test", "",
        f"{t['frames']} frame có nhãn, {t['target_frames']} frame radar có target. Sai số tính trên frame có target.", "",
        "| | MAE (m) | Trung vị (m) | RMSE (m) | Sai số tương đối | Lệch không quá 5 m | Lệch không quá 10 m |", "|---|---:|---:|---:|---:|---:|---:|",
        *[f"| {name} | {a['mae_m']} | {a['median_m']} | {a['rmse_m']} | {a['abs_rel']:.1%} | {a['within_5m']:.1%} | {a['within_10m']:.1%} |"
          for name, a in [("Đoán trung vị của tập train", r["median_guess"]), ("gr14VinAI", t)]], "",
        "| Vùng / đoạn | Frame có target | MAE (m) | Trung vị (m) | RMSE (m) | Recall | F1 |", "|---|---:|---:|---:|---:|---:|---:|",
        *[row(k, a) for k, a in r["by_range"].items()], *[row(k, a) for k, a in r.get("by_group", {}).items()],
        *[row(k, a) for k, a in r["by_scb"].items()], "",
        "## 2. Phát hiện có xe (has_target)", "",
        "| Precision | Recall | F1 |", "|---:|---:|---:|", f"| {t['precision']} | {t['recall']} | {t['f1']} |", "",
        "## 3. Chi phí", "",
        "| Số tham số | File ONNX | Latency trung bình | Trung vị | p95 | FPS | Cả pipeline mỗi frame |", "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {c['parameters']:,} | {c['onnx_mb']} MB | {c['latency_ms']['mean']} ms | {c['latency_ms']['median']} ms | {c['latency_ms']['p95']} ms | {c['fps']} | {c['pipeline_ms_per_frame']} ms |", "",
        "Latency: onnxruntime trên CPU, 4 luồng, mỗi lần 1 frame, 500 lần sau 50 lần làm nóng. "
        "Cả pipeline = giải mã video + cắt ảnh + model, trung bình trên mọi frame của video test.", "",
        "## 4. Độ ổn định giữa hai frame liên tiếp (20 fps)", "",
        "| | Khoảng cách đổi trung bình (m) | 95% dưới (m) | Xe hiện/mất mỗi phút |", "|---|---:|---:|---:|",
        *[f"| {'Đầu ra thô' if k == 'raw' else 'Sau làm mượt'} | {v['change_m_mean']} | {v['change_m_p95']} | {v['target_flips_per_minute']} |" for k, v in s.items()], "",
        "## Môi trường đo", "", *[f"- {k}: {v}" for k, v in r["environment"].items()], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
