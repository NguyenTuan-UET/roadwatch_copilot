"""Hình cho test/README.md: đánh giá thực tế (Vinhomes Ocean Park 2 + cao tốc Hà Nội - Hải Phòng) và human baseline.

Chạy từ thư mục test/:  python eval/report/scripts/make_readme_figures.py
- eval/radar_vinhomeocp/measurements.xlsx -> measurements.csv (sheet "All frames", đủ mọi frame)
- eval/radar_vinhomeocp/field_metrics.json, field_frames_scored.csv
- eval/human_baseline/comparison_30_images.csv
- eval/report/figures/field_*.png, eval/report/figures/human_baseline.png

Quy tắc chấm thực địa:
- sai số = |model - radar| = |Δ| đọc trên HUD
- radar không hiện số (hoặc HUD không hiện Δ) -> bỏ frame, vì không có sai số để chấm
- frame đọc sai (3 số OCR không khớp nhau): cứ 20 frame radar có số liên tiếp
  chỉ bỏ tối đa 5 frame, ưu tiên bỏ frame lệch nhiều nhất; các frame đọc sai còn lại vẫn được chấm.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

T = Path(__file__).resolve().parents[2]  # test/eval
FIELD = T / "radar_vinhomeocp"
HB = T / "human_baseline"
FIG = T / "report" / "figures"
BLUE, GRAY, ORANGE, GREEN, BG = "#2a78d6", "#8a8984", "#e8692e", "#2e9e5b", "#fcfcfa"
TOL = 0.15  # dung sai của golden set
BLOCK, MAX_DROP = 20, 5
BANDS = [0, 10, 20, 40, 60, 80, 100, 1000]

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#555",
    "axes.grid": True, "grid.color": "#e3e3e0", "axes.axisbelow": True,
    "axes.titleweight": "bold", "figure.titleweight": "bold", "xtick.color": "#555", "ytick.color": "#555",
})
vn = lambda x, d=1: f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def hud(e):
    """HUD hiện khoảng cách model: dưới 20 m làm tròn xuống 1 m, từ 20 m làm tròn xuống 5 m."""
    return np.where(e < 20, np.floor(e), np.floor(e / 5) * 5)


def select(r):
    """r: các frame có số radar và Δ, theo thứ tự thời gian. Trả về mask frame được chấm."""
    est = r.radar_display_m + r.delta_display_m
    # mức đọc sai: độ lệch giữa số model đọc được và radar + Δ làm tròn (không đọc được số model = vô cùng)
    bad = (hud(est) - r.model_display_m).abs().fillna(np.inf).to_numpy()
    keep = np.ones(len(r), bool)
    for s in range(0, len(r), BLOCK):
        b = np.arange(s, min(s + BLOCK, len(r)))
        wrong = b[bad[b] > 0]
        keep[wrong[np.argsort(-bad[wrong], kind="stable")][:MAX_DROP]] = False
    return keep, bad


def stats(err, radar):
    e = np.abs(err)
    return {"frames": int(len(e)), "mae_m": round(float(e.mean()), 2), "median_m": round(float(np.median(e)), 2),
            "p90_m": round(float(np.percentile(e, 90)), 2), "mean_signed_m": round(float(err.mean()), 2),
            "within_15pct": round(float((e <= TOL * radar).mean()), 3),
            "within_2m": round(float((e <= 2).mean()), 3), "within_5m": round(float((e <= 5).mean()), 3)}


def main():
    a = pd.read_excel(FIELD / "measurements.xlsx", sheet_name="All frames")
    a.to_csv(FIELD / "measurements.csv", index=False, encoding="utf-8-sig")
    r = a[a.radar_display_m.notna() & a.delta_display_m.notna()].reset_index(drop=True)
    keep, bad = select(r)
    c = r[keep].copy()
    c["model_m"] = c.radar_display_m + c.delta_display_m
    c["abs_error_m"] = c.delta_display_m.abs()
    c["ocr_consistent"] = bad[keep] == 0
    c[["frame", "sample_time_s", "radar_display_m", "delta_display_m", "model_m", "abs_error_m", "ocr_consistent"]] \
        .to_csv(FIELD / "field_frames_scored.csv", index=False, encoding="utf-8-sig")

    nblocks = -(-len(r) // BLOCK)
    drops = [int((~keep[s:s + BLOCK]).sum()) for s in range(0, len(r), BLOCK)]
    err, radar = c.delta_display_m, c.radar_display_m
    m = {"frames_total": len(a), "duration_s": float(a.sample_time_s.max()),
         "radar_number": int(a.radar_display_m.notna().sum()), "radar_and_delta": len(r), "misread": int((bad > 0).sum()), "dropped_misread": int((~keep).sum()),
         "scored": len(c), "scored_misread_kept": int((~c.ocr_consistent).sum()),
         "blocks": nblocks, "max_dropped_per_block": max(drops),
         "all": stats(err, radar), "radar_le_100": stats(err[radar <= 100], radar[radar <= 100]), "bands": {}}
    for lo, hi in zip(BANDS, BANDS[1:]):
        s = (radar >= lo) & (radar < hi)
        if s.sum():
            m["bands"][f"{lo}-{hi}" if hi < 1000 else f"≥{lo}"] = stats(err[s], radar[s])

    read = lambda f: pd.read_csv(HB / f, decimal=",")
    h = read("nguoi_danh_gia.csv").merge(read("gr14VinAI.csv"), on="id", suffixes=("_h", "_m"))
    both = h.dropna(subset=["distance_m_h", "distance_m_m"])
    he = both.distance_m_m - both.distance_m_h
    pd.DataFrame({"id": h.id, "model_distance_m": h.distance_m_m, "human_has_target": h.has_target_h,
                  "human_distance_m": h.distance_m_h, "absolute_difference_m": (h.distance_m_m - h.distance_m_h).abs().round(2)})         .to_csv(HB / "comparison_30_images.csv", index=False, encoding="utf-8-sig", decimal=",")
    m["human"] = {"images": len(h), "agree_has_target": int((h.has_target_h == h.has_target_m).sum()),
                  "with_target": len(both), "mae_m": round(float(he.abs().mean()), 2),
                  "median_m": round(float(he.abs().median()), 2), "min_m": round(float(he.abs().min()), 2),
                  "max_m": round(float(he.abs().max()), 2),
                  "within_15pct": int((he.abs() <= TOL * both.distance_m_h).sum())}
    (FIELD / "field_metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    FIG.mkdir(parents=True, exist_ok=True)
    s = m["all"]

    # 1. Dòng thời gian: model và radar trên cả chuyến đi
    fig, ax = plt.subplots(figsize=(14, 4.6))
    t = c.sample_time_s / 60
    ax.scatter(t, c.radar_display_m, s=10, color=GRAY, label="Radar", zorder=2)
    ax.scatter(t, c.model_m, s=10, color=BLUE, label="gr14VinAI (chỉ camera)", zorder=3)
    ax.set(xlabel="Thời điểm trong video (phút)", ylabel="Khoảng cách xe phía trước (m)",
           xlim=(0, m["duration_s"] / 60 + .3), ylim=(0, None))
    ax.legend(loc="upper left", markerscale=2.5, frameon=False)
    fig.suptitle(f"Video thực tế {vn(m['duration_s'] / 60, 0)} phút: model (xanh) bám theo radar (xám) "
                 f"trên {vn(s['frames'], 0)} frame")
    fig.tight_layout(); fig.savefig(FIG / "field_timeline.png", dpi=150); plt.close(fig)

    # 2. Model so với radar + phân bố |Δ|
    fig, (l, rr) = plt.subplots(1, 2, figsize=(14, 5.4))
    hi = float(max(c.radar_display_m.max(), c.model_m.max())) + 5
    x = np.array([0, hi])
    l.fill_between(x, x * (1 - TOL), x * (1 + TOL), color=BLUE, alpha=.12, lw=0, label="lệch không quá 15%")
    l.plot(x, x, color="#444", lw=1.2, label="model = radar")
    l.scatter(radar, c.model_m, s=8, color=BLUE, alpha=.45, lw=0)
    l.set(xlim=(0, hi), ylim=(0, hi), xlabel="Khoảng cách radar (m)", ylabel="Khoảng cách model đoán (m)",
          title="Từng frame: model so với radar")
    l.legend(loc="upper left", frameon=False)
    ae = c.abs_error_m.sort_values().to_numpy()
    rr.plot(ae, np.arange(1, len(ae) + 1) / len(ae) * 100, color=BLUE, lw=2.5)
    for v, col in [(2, GREEN), (5, ORANGE)]:
        p = (ae <= v).mean() * 100
        rr.axvline(v, color=col, ls="--", lw=1.2)
        rr.text(v + .3, p - 7, f"{vn(p)}% frame\nlệch ≤ {v} m", color=col, fontsize=11, fontweight="bold")
    rr.set(xlim=(0, 20), ylim=(0, 101), xlabel="|model − radar| (m)", ylabel="% frame",
           title=f"Phân bố sai số: MAE {vn(s['mae_m'], 2)} m, trung vị {vn(s['median_m'], 2)} m")
    fig.suptitle(f"Sai số khoảng cách trên {vn(s['frames'], 0)} frame quay thực tế")
    fig.tight_layout(); fig.savefig(FIG / "field_pred_vs_radar.png", dpi=150); plt.close(fig)

    # 3. Theo khoảng cách
    names = list(m["bands"]); bs = list(m["bands"].values())
    fig, (l, rr) = plt.subplots(1, 2, figsize=(14, 4.4))
    for ax, key, f, lab in [(l, "mae_m", 1, "MAE (m), thấp hơn là tốt hơn"),
                            (rr, "within_15pct", 100, "% frame lệch không quá 15%, cao hơn là tốt hơn")]:
        v = [b[key] * f for b in bs]
        bars = ax.bar(names, v, color=[BLUE if n != "≥100" else GRAY for n in names], width=.6)
        for b, val, bb in zip(bars, v, bs):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{vn(val)}\n(n={bb['frames']})",
                    ha="center", va="bottom", fontsize=9.5)
        ax.set(xlabel="Khoảng cách radar (m)", title=lab)
        ax.set_ylim(0, max(v) * 1.25)
    fig.suptitle("Sai số theo khoảng cách (xám: ngoài tầm 100 m của model)")
    fig.tight_layout(); fig.savefig(FIG / "field_by_distance.png", dpi=150); plt.close(fig)

    # 4. Từ video tới frame được chấm
    steps = [("Frame lấy ra (2 frame/giây)", m["frames_total"]), ("Radar hiện số", m["radar_number"]), ("Đọc được Δ", m["radar_and_delta"]),
             ("Được chấm (bỏ ≤ 5/20 frame đọc sai)", m["scored"])]
    fig, ax = plt.subplots(figsize=(11, 3.2))
    y = np.arange(len(steps))[::-1]
    ax.barh(y, [v for _, v in steps], color=[GRAY, GRAY, GRAY, BLUE], height=.6)
    for yi, (_, v) in zip(y, steps):
        ax.text(v + 30, yi, f"{vn(v, 0)}  ({vn(100 * v / m['frames_total'], 0)}%)", va="center")
    ax.set_yticks(y, [n for n, _ in steps]); ax.set_xlim(0, m["frames_total"] * 1.2); ax.grid(axis="y", visible=False)
    ax.set_title("Từ video tới frame được chấm")
    fig.tight_layout(); fig.savefig(FIG / "field_funnel.png", dpi=150); plt.close(fig)

    # 5. Human baseline
    hm = m["human"]
    fig, l = plt.subplots(figsize=(7.5, 6))
    x = np.array([0, 115])
    l.fill_between(x, x * (1 - TOL), x * (1 + TOL), color=BLUE, alpha=.12, lw=0, label="lệch không quá 15%")
    l.plot(x, x, color="#444", lw=1.2, label="model = người")
    l.scatter(both.distance_m_h, both.distance_m_m, s=55, color=BLUE, zorder=3)
    l.set(xlim=(0, 115), ylim=(0, 115), xlabel="Người ước tính (m)", ylabel="gr14VinAI (m)",
          title=f"{hm['with_target']} ảnh có xe: lệch trung bình {vn(hm['mae_m'], 2)} m ({vn(hm['min_m'])}-{vn(hm['max_m'])} m)")
    l.legend(loc="upper left", frameon=False)
    fig.suptitle(f"Human baseline: {hm['agree_has_target']}/{hm['images']} ảnh khớp có/không có xe với người")
    fig.tight_layout(); fig.savefig(FIG / "human_baseline.png", dpi=150); plt.close(fig)

    print(json.dumps(m, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    # tự kiểm tra quy tắc bỏ frame: 20 frame, 8 frame đọc sai -> chỉ bỏ 5 frame lệch nhiều nhất
    d = pd.DataFrame({"radar_display_m": [30.0] * 20, "delta_display_m": [2.0] * 20, "model_display_m": [30.0] * 20})
    d.loc[:7, "model_display_m"] = [40, 45, 50, 55, 60, 65, 70, 75]
    k, _ = select(d)
    assert (~k).sum() == 5 and not k[3:8].any() and k[:3].all() and k[8:].all()
    main()
