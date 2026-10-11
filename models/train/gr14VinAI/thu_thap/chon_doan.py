"""Buoc 1: quet cac chunk Comma2k19 da giai nen, do tung doan (1 phut), roi tu chon cac doan theo chi tieu.

    python chon_doan.py <thu_muc_chua_cac_Chunk> [<thu_muc_khac> ...] [--da-co nhiemvu_drives_da_co.txt] [--giu goi_du_lieu/raw/danh_sach.csv]

--giu: da dong goi mot dot roi, nay tai them chunk. Cac doan trong goi cu duoc giu nguyen va tinh vao chi tieu;
danh_sach.csv chi gom cac doan chon THEM (dua cho dong_goi.py, no se noi tiep vao goi cu).
--mo-lai: file liet ke cac doan cu (Chunk_X/<chuyen>/<so>) cua nhung chuyen di chi nam trong tap train. Cac chuyen do duoc phep
lay them doan (doan moi se vao tap train cung chuyen di); doan cu van tinh vao gioi han moi chuyen di.

Ghi ra, ngay trong thu muc hien tai:
    tat_ca_doan.csv   moi doan quet duoc va so do cua no
    danh_sach.csv     cac doan duoc chon (dau vao cua dong_goi.py)
va in ra o nao con thieu so voi chi tieu.

Moi doan duoc do bang dung quy tac radar cua du an (file preprocess_dataset.py di kem): xe phia truoc la vat the radar
gan nhat, lech ngang khong qua 1,5 m, cach khong qua 100 m.
"""
import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from preprocess_dataset import label_frame, load_arrays, select_frames

sys.stdout.reconfigure(encoding="utf-8")

# Chi tieu: so doan can thu, theo (thoi diem, khoang cach dien hinh toi xe phia truoc).
# Dat ra tu nhung o ma 100 doan ban dau con thieu; xem docs/dataset_summary.md.
CHI_TIEU = {
    ("ngay", "20-40"): 15, ("ngay", "40-60"): 5, ("ngay", "60-80"): 5, ("ngay", "80-100"): 15, ("ngay", "0-20"): 10,
    ("chang_vang", "20-40"): 6, ("chang_vang", "40-60"): 6, ("chang_vang", "60-80"): 4, ("chang_vang", "80-100"): 6, ("chang_vang", "khong_xe"): 3,
    ("dem", "20-40"): 14, ("dem", "40-60"): 12, ("dem", "60-80"): 8, ("dem", "80-100"): 14, ("dem", "0-20"): 5,
}
MOI_CHUYEN, CACH_NHAU = 3, 3  # toi da 3 doan moi chuyen di, cach nhau it nhat 3 phut
# Sau khi chon theo chi tieu: lay them moi doan co it nhat XA_IT_NHAT trong 120 frame lay mau la xe o 80-100 m (khoang dang it frame nhat
# trong du lieu), doan nhieu frame xa nhat lay truoc, toi da XA_MOI_CHUYEN doan moi chuyen di, cho phep hai doan lien nhau.
XA_IT_NHAT, XA_MOI_CHUYEN = 10, 6
# Sau do lay them toi da GAN_THEM doan co it nhat GAN_IT_NHAT/120 frame la xe o 20-40 m (khoang it frame thu hai), doan dem va chang vang truoc.
GAN_THEM, GAN_IT_NHAT = 20, 40
XE_THU_HAI = "b0c9d2329ad1606b"  # chiec xe dang it du lieu (Chunk_1, Chunk_2): uu tien cho cac o ban dem

CHUYEN = re.compile(r"(Chunk_\d+)[\\/]([0-9a-f]{16})[|_]([0-9]{4}-[0-9]{2}-[0-9]{2}--[0-9]{2}-[0-9]{2}-[0-9]{2})[\\/]([0-9]+)$")


def mat_troi(thu_muc):
    """Goc cao cua mat troi (do) luc doan duoc quay, va gio dia phuong. Tinh tu dong ho GPS va vi tri ghi trong du lieu,
    vi gio trong ten thu muc khong dang tin: mot so chuyen di ghi gio UTC, lech 7 tieng so voi gio California."""
    tuan, giay = np.load(thu_muc / "global_pose/frame_gps_times")[0]
    utc = datetime(1980, 1, 6) + timedelta(weeks=float(tuan), seconds=float(giay) - 18)  # GPS di truoc UTC 18 giay
    x, y, z = np.load(thu_muc / "global_pose/frame_positions")[0]
    kinh, vi = np.degrees(np.arctan2(y, x)), np.arctan2(z, np.hypot(x, y) * (1 - 0.00669438))
    n = utc.timetuple().tm_yday
    b = 2 * np.pi * (n - 81) / 364
    lech = 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)  # phuong trinh thoi gian, phut
    nghieng = np.radians(-23.44) * np.cos(2 * np.pi * (n + 10) / 365)
    gio_mt = utc.hour + utc.minute / 60 + utc.second / 3600 + kinh / 15 + lech / 60
    goc = np.degrees(np.arcsin(np.sin(vi) * np.sin(nghieng) + np.cos(vi) * np.cos(nghieng) * np.cos(np.radians(15 * (gio_mt - 12)))))
    return float(goc), utc - timedelta(hours=7 if (3, 11) <= (utc.month, utc.day) < (11, 4) else 8)  # gio dong ho California nam 2018


def thoi_diem(goc):
    """dem: mat troi duoi chan troi hon 6 do (het hoang hon dan su); chang_vang: tu do den khi mat troi cao 6 do; con lai la ngay"""
    return "dem" if goc < -6 else "chang_vang" if goc < 6 else "ngay"


def do_doan(thu_muc):
    """so frame, toc do trung binh, ti le frame co xe phia truoc, khoang cach trung vi toi xe do, so frame (trong 120 frame lay mau) co xe o 20-40 m, 60-80 m va 80-100 m"""
    frames, times, values = load_arrays(thu_muc)
    toc_do = float(np.load(thu_muc / "processed_log/CAN/speed/value").mean())
    nhan = [label_frame(frames[i], times, values, 1.5, 100, 0.05) for i in select_frames(len(frames), 120)]
    d = np.array([n["distance_m"] for n in nhan if n["has_target"] == 1])
    co_radar = sum(n["has_target"] is not None for n in nhan)
    ti_le = len(d) / max(co_radar, 1)
    loai = "khong_xe" if ti_le < 0.3 or len(d) < 10 else next(f"{lo}-{lo + 20}" for lo in (0, 20, 40, 60, 80) if np.median(d) <= lo + 20)
    return len(frames), toc_do, ti_le, float(np.median(d)) if len(d) else "", loai, int(((d > 20) & (d <= 40)).sum()), int(((d > 60) & (d <= 80)).sum()), int((d > 80).sum())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("goc", type=Path, nargs="+")
    p.add_argument("--giu", type=Path)
    p.add_argument("--mo-lai", type=Path)
    p.add_argument("--da-co", type=Path, default=Path(__file__).with_name("nhiemvu_drives_da_co.txt"))
    a = p.parse_args()
    da_co = {line.strip().split("/", 1)[1] for line in a.da_co.read_text(encoding="utf-8").splitlines() if line.strip()}
    doan = []
    cu = [dong.strip() for dong in a.mo_lai.read_text(encoding="utf-8").splitlines() if dong.strip()] if a.mo_lai else []
    mo_lai = {dong.split("/")[1] for dong in cu}
    giu = [dict(r, chuyen=r["path"].split("/")[1], so=int(r["path"].split("/")[2])) for r in csv.DictReader(open(a.giu, encoding="utf-8"))] if a.giu else []
    for video in sorted(v for goc in a.goc for v in goc.rglob("video.hevc")):
        m = CHUYEN.search(str(video.parent))
        if not m:
            continue
        chunk, xe, gio, so = m.groups()
        chuyen = f"{xe}|{gio}"
        r = dict(path=f"{chunk}/{chuyen}/{so}", thu_muc=str(video.parent), chuyen=chuyen, so=int(so), xe=xe, trung=chuyen in da_co and chuyen not in mo_lai, loi="")
        try:
            goc, dia_phuong = mat_troi(video.parent)
            r.update(bat_dau=dia_phuong.strftime("%Y-%m-%d %H:%M"), mat_troi_do=round(goc, 1), thoi_diem=thoi_diem(goc))
            r["so_frame"], r["toc_do_mps"], r["ti_le_co_xe"], r["kc_trung_vi_m"], r["khoang_cach"], r["frame_20_40"], r["frame_60_80"], r["frame_80_100"] = do_doan(video.parent)
        except (OSError, ValueError) as e:
            r["loi"] = str(e)
            r.setdefault("thoi_diem", "")
        doan.append(r)
        print(f"{r['path']}: {r['loi'] or (r['thoi_diem'], r['khoang_cach'])}", flush=True)
    if not doan:
        sys.exit(f"Khong tim thay doan nao trong {a.goc}. Can cau truc Chunk_X/<ma xe>|<ngay--gio>/<so doan>/video.hevc (dau | co the la _ tren Windows).")
    cot = ["path", "bat_dau", "thoi_diem", "mat_troi_do", "khoang_cach", "kc_trung_vi_m", "frame_20_40", "frame_60_80", "frame_80_100", "ti_le_co_xe", "toc_do_mps", "so_frame", "xe", "trung", "loi", "thu_muc"]
    ghi = lambda ten, rows: csv.DictWriter(open(ten, "w", newline="", encoding="utf-8"), cot, extrasaction="ignore").writerows([dict(zip(cot, cot))] + rows)
    ghi("tat_ca_doan.csv", doan)

    dat = [r for r in doan if not r["loi"] and not r["trung"] and r["so_frame"] >= 1000 and r["toc_do_mps"] >= 15
           and r["path"] not in {g["path"] for g in giu} | set(cu)]
    chon, moi_chuyen = list(giu), {}
    for dong in cu:
        moi_chuyen.setdefault(dong.split("/")[1], []).append(int(dong.split("/")[2]))

    def lay(r, toi_da, cach=CACH_NHAU):
        da_lay = moi_chuyen.setdefault(r["chuyen"], [])
        if len(da_lay) < toi_da and all(abs(r["so"] - s) >= cach for s in da_lay):
            da_lay.append(r["so"])
            chon.append(r)

    for g in giu:
        moi_chuyen.setdefault(g["chuyen"], []).append(g["so"])
    for o in sorted(CHI_TIEU, key=lambda o: sum((r["thoi_diem"], r["khoang_cach"]) == o for r in dat)):  # o hiem nhat chon truoc
        ung_vien = sorted((r for r in dat if (r["thoi_diem"], r["khoang_cach"]) == o),
                          key=lambda r: (not (o[0] == "dem" and r["xe"] == XE_THU_HAI), len(moi_chuyen.get(r["chuyen"], [])), -r["ti_le_co_xe"]))
        for r in ung_vien:
            if sum(c["thoi_diem"] == o[0] and c["khoang_cach"] == o[1] for c in chon) >= CHI_TIEU[o]:
                break
            lay(r, MOI_CHUYEN)
    theo_chi_tieu = len(chon)
    da_chon = {r["path"] for r in chon}
    for r in sorted((r for r in dat if r["path"] not in da_chon and r["frame_80_100"] >= XA_IT_NHAT), key=lambda r: -r["frame_80_100"]):
        lay(r, XA_MOI_CHUYEN, 1)
    xa, da_chon = len(chon) - theo_chi_tieu, {r["path"] for r in chon}
    for r in sorted((r for r in dat if r["path"] not in da_chon and r["frame_20_40"] >= GAN_IT_NHAT), key=lambda r: (r["thoi_diem"] == "ngay", -r["frame_20_40"])):
        if len(chon) - theo_chi_tieu - xa < GAN_THEM:
            lay(r, XA_MOI_CHUYEN, 1)
    ghi("danh_sach.csv", sorted(chon[len(giu):], key=lambda r: r["path"]))

    kc = ["0-20", "20-40", "40-60", "60-80", "80-100", "khong_xe"]
    quet = Counter((r["thoi_diem"], r["khoang_cach"]) for r in dat)
    print("\nCac doan dung duoc trong nhung gi da quet (chua tinh gioi han moi chuyen di), theo thoi diem x khoang cach toi xe phia truoc (m):")
    print(f"{'':12s}" + "".join(f"{k:>10s}" for k in kc))
    for t in ("ngay", "chang_vang", "dem"):
        print(f"{t:12s}" + "".join(f"{quet[t, k]:10d}" for k in kc))
    co = Counter((r["thoi_diem"], r["khoang_cach"]) for r in chon)
    print(f"\nQuet {len(doan)} doan ({sum(r['trung'] for r in doan)} thuoc chuyen di da co, {sum(bool(r['loi']) for r in doan)} loi). Giu {len(giu)} doan da dong goi, chon them {len(chon) - len(giu)}; tong {len(chon)} doan tu {len({r['chuyen'] for r in chon})} chuyen di.")
    print(f"Trong so chon them: {xa} doan lay vi co nhieu frame xe o 80-100 m, {len(chon) - theo_chi_tieu - xa} doan vi nhieu frame o 20-40 m (ngoai chi tieu duoi day).")
    print(f"Doan dem tu xe thu hai: {sum(r['thoi_diem'] == 'dem' and r['xe'] == XE_THU_HAI for r in chon)} (can it nhat 15)")
    print(f"{'thoi diem':12s}{'khoang cach':13s}{'da chon':>8s}{'chi tieu':>9s}")
    for o, can in CHI_TIEU.items():
        print(f"{o[0]:12s}{o[1]:13s}{co[o]:8d}{can:9d}{'   <- con thieu ' + str(can - co[o]) if co[o] < can else ''}")
    print("\nDa ghi tat_ca_doan.csv va danh_sach.csv. Neu con o thieu: tai them chunk khac roi chay lai tren thu muc chua TAT CA cac chunk.")


if __name__ == "__main__":
    main()
