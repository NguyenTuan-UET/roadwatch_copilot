"""Buoc 2: dong goi cac doan trong danh_sach.csv thanh dung cau truc du lieu cua du an.

    python dong_goi.py danh_sach.csv goi_du_lieu [--bat-dau 101]

Tao ra:
    goi_du_lieu/raw/scb101/ ... scbNNN/     moi doan mot thu muc: video.hevc, global_pose/, processed_log/CAN/
    goi_du_lieu/raw/scenario_index.csv      path (duong dan goc trong Comma2k19), sc_name (scb101 ...)
    goi_du_lieu/raw/danh_sach.csv           thoi diem, khoang cach, ghi chu cua tung doan

Danh so tu 101 vi du an da co scb1 ... scb100. Neu goi_du_lieu/raw da co san thi noi tiep so va ghi them vao 2 file csv. Chi sao chep, khong sua gi trong du lieu goc.
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BAT_BUOC = ["video.hevc", "global_pose/frame_times", "global_pose/frame_positions", "global_pose/frame_velocities", "global_pose/frame_orientations",
            "processed_log/CAN/radar/t", "processed_log/CAN/radar/value", "processed_log/CAN/speed/t", "processed_log/CAN/speed/value"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("danh_sach", type=Path)
    p.add_argument("dich", type=Path)
    p.add_argument("--bat-dau", type=int)
    a = p.parse_args()
    rows = list(csv.DictReader(open(a.danh_sach, encoding="utf-8")))
    raw = a.dich / "raw"
    da_dong = {r["path"] for r in csv.DictReader(open(raw / "scenario_index.csv", encoding="utf-8"))} if raw.exists() else set()
    bat_dau = a.bat_dau or max([100] + [int(d.name[3:]) for d in raw.glob("scb*")]) + 1
    if da_dong & {r["path"] for r in rows} or any((raw / f"scb{n}").exists() for n in range(bat_dau, bat_dau + len(rows))):
        sys.exit(f"{raw}: co doan trong danh sach da duoc dong goi, hoac trung so scb. Chua dong goi gi.")
    thieu = [(r["path"], f) for r in rows for f in BAT_BUOC if not (Path(r["thu_muc"]) / f).is_file()]
    if thieu:
        sys.exit("Thieu file bat buoc, chua dong goi gi:\n" + "\n".join(f"  {path}: {f}" for path, f in thieu))
    raw.mkdir(parents=True, exist_ok=True)
    for n, r in enumerate(rows, bat_dau):
        nguon, scb = Path(r["thu_muc"]), raw / f"scb{n}"
        shutil.copytree(nguon / "global_pose", scb / "global_pose")
        shutil.copy2(nguon / "video.hevc", scb / "video.hevc")
        for tin_hieu in sorted((nguon / "processed_log/CAN").iterdir()):  # radar, speed, steering_angle, wheel_speed ... tru log tho
            if tin_hieu.is_dir() and tin_hieu.name != "raw_can":
                shutil.copytree(tin_hieu, scb / "processed_log/CAN" / tin_hieu.name)
        r["sc_name"] = scb.name
        print(f"{scb.name} <- {r['path']}", flush=True)
    with open(raw / "scenario_index.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["path", "sc_name"]] * (not da_dong) + [[r["path"], r["sc_name"]] for r in rows])
    cot = ["sc_name", "path", "bat_dau", "thoi_diem", "khoang_cach", "kc_trung_vi_m", "ti_le_co_xe", "toc_do_mps", "so_frame", "xe", "ghi_chu"]
    with open(raw / "danh_sach.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cot, extrasaction="ignore")
        if not da_dong:
            w.writeheader()
        w.writerows(rows)
    print(f"\nXong: {len(rows)} doan trong {raw}. Tiep theo: chay preprocess_dataset.py va validate_dataset.py tren thu muc nay.")


if __name__ == "__main__":
    main()
