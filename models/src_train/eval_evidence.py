"""Build the final evaluation report (eval/final_evaluation_report.md) from measurements only.

    python src/eval_evidence.py            # score and write the report
    python src/eval_evidence.py rebuild    # also redraw the golden set

eval/inputs/golden.jsonl  300 real test cases (150 on, 75 off, 75 edge), written once from the radar labels
human_baseline/           30 golden cases for people to answer: anh/01.jpg.. (random order), vi_du/ (4 worked examples from other
                          cases), phieu_tra_loi.csv (blank sheet); each filled sheet comes back as tra_loi/<name>.csv and is scored
                          against the radar labels. eval/human_baseline_key.csv says which golden case each image is
eval/inputs/user_feedback.csv    one row per user review; synthetic rows are kept as backlog and excluded from real-user scoring
eval/inputs/out_of_scope.csv     the team's field cases from outside the model's scope (rain, a phone camera), answered by the app on the phone
eval/results/geometry_predictions.csv   from `python src/geometry.py`; the geometric competitor, scored once present
Whatever has not been measured yet is printed as "CHƯA CÓ", never as a number.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np

import train as g
from common import CAM_H, DATA, EVAL, H, LEFT_OUT, RAW, ROOT, TRAIN, W, labelled, onnx_session, read_yuv_frames, run_pair, train_median, vanishing_point

OUT, INPUTS, SRC = EVAL / "results", EVAL / "inputs", Path(__file__).parent.name
GOLDEN, FEEDBACK = INPUTS / "golden.jsonl", INPUTS / "user_feedback.csv"
SHEET, SHEET_KEY = TRAIN / "human_baseline", TRAIN / "human_baseline" / "human_baseline_key.csv"  # current human-baseline evidence folder
SHEET_SIZE = {"on": 15, "off": 8, "edge": 7}
OUTSIDE = INPUTS / "out_of_scope.csv"
OUTSIDE_COLUMNS = "id,group,source,true_has_target,true_distance_m,how_measured,app_has_target,app_distance_m"
FEEDBACK_SCORES = {"score_expectation": "Đạt mong đợi", "score_reuse": "Dùng lại", "score_recommend": "Giới thiệu"}  # each 1-5, given by the user
REPORT = EVAL / "final_evaluation_report.md"
ROUNDS = INPUTS / "model_iteration_history.json"  # recorded numbers of earlier rounds, for the before/after table
LABEL_CHANGE = INPUTS / "label_rule_comparison.json"  # recorded: the previous and final model under both label definitions
CURRENT_ROUND = ("bỏ 24 video chạng vạng khỏi train, validation và test (quá ít để train và để chấm); lúc train lấy mẫu cân bằng theo "
                 "(ngày, đêm) x khoảng cách, để frame hiếm (dưới 20 m, 80-100 m, ban đêm) được chọn thường xuyên hơn. Kiến trúc và nhãn giữ như vòng 6. "
                 "Train hai lần (seed 1 và 2), chọn seed 2 trên validation.")
GOLDEN_SIZE = {"on": 150, "off": 75, "edge": 75}
TOL = 0.15  # a distance passes when it is within 15 % of the radar distance
K = 5  # pass@k / pass^k over the labelled frame and its 2 neighbours on each side (0.25 s of video)
# name -> folder holding the benchmark.json with its validation threshold
MODELS = {"gr14VinAI": ROOT / "results" / "benchmark"}


def onnx_file(folder):
    """The model is not kept in this folder: model/gr14VinAI.onnx when it has been put there, else the project's train/model/."""
    return next((f for f in (TRAIN / "model" / "gr14VinAI.onnx", ROOT / "train" / "model" / "gr14VinAI.onnx") if f.exists()), TRAIN / "model" / "gr14VinAI.onnx")


def build_golden():
    rows = labelled("test")
    off_lane = lambda r: abs(float(r["y_rel_m"]) - float(r["lane_left_m"]))  # metres from the centre of the lane
    kind = lambda r: "off" if r["has_target"] != "1" else ("edge" if float(r["distance_m"]) < 35 or float(r["distance_m"]) > 92
                                                             or off_lane(r) >= 1.3 else "on")
    pool = {}  # (type, scb) -> rows in random order
    for n in np.random.RandomState(0).permutation(len(rows)):
        pool.setdefault((kind(rows[n]), rows[n]["scb_id"]), []).append(rows[n])
    cases = []
    for k, quota in GOLDEN_SIZE.items():
        queues = [q for (kk, _), q in sorted(pool.items()) if kk == k]
        picked = []
        while len(picked) < quota and any(queues):  # one case per video in turn, so no video dominates
            picked += [q.pop() for q in queues if q][:quota - len(picked)]
        for r in picked:
            has = r["has_target"] == "1"
            cases.append({"id": f"{k}-{sum(c['type'] == k for c in cases) + 1:03d}", "type": k,
                          "scb_id": r["scb_id"], "frame_index": int(r["frame_index"]), "image_path": r["image_path"],
                          "has_target": has, "distance_m": round(float(r["distance_m"]), 2) if has else None,
                          "y_rel_m": round(float(r["y_rel_m"]), 2) if has else None,
                          "lane_left_m": round(float(r["lane_left_m"]), 2) if has else None,
                          "source": f"radar label, {DATA.relative_to(ROOT).as_posix()}/labels" + ("_curved" if "curve" in g.RECIPE else "") + "/test.csv"})
    EVAL.mkdir(exist_ok=True)
    GOLDEN.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in sorted(cases, key=lambda c: c["id"])), encoding="utf-8")
    if not FEEDBACK.exists():
        FEEDBACK.write_text("user,date," + ",".join(FEEDBACK_SCORES) + ",quote,fix_made,fix_date,team_reading\n", encoding="utf-8")


def run_models(cases):
    """Each model on the frames around every golden case: {model: {(scb, frame): (probability, metres)}}."""
    sessions = {name: onnx_session(onnx_file(folder)) for name, folder in MODELS.items()}
    preds = {name: {} for name in MODELS}
    for scb in sorted({c["scb_id"] for c in cases}):
        needed = {j for c in cases if c["scb_id"] == scb for j in range(c["frame_index"] - K // 2, c["frame_index"] + K // 2 + 1)}
        prev = None
        for j, frame in enumerate(read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb))):
            if j in needed:
                x = np.concatenate([frame if prev is None else prev, frame])
                for name, sess in sessions.items():
                    p, d = run_pair(sess, x)[:2]
                    preds[name][scb, j] = (p.item(), d.item())
            prev = frame
    return preds


def passed(case, has, dist):
    if not case["has_target"]:
        return not has
    return bool(has) and abs(dist - case["distance_m"]) <= TOL * case["distance_m"]


def score(cases, answer):
    """answer(case, frame) -> (reports a target?, metres) or None when the system has no answer for that frame."""
    centre = [answer(c, c["frame_index"]) for c in cases]
    if any(a is None for a in centre):
        return None
    ok = np.array([passed(c, *a) for c, a in zip(cases, centre)])
    tgt = np.array([c["has_target"] for c in cases])
    kind = np.array([c["type"] for c in cases])
    has = np.array([bool(a[0]) for a in centre])
    dist = np.array([a[1] if a[0] else np.nan for a in centre], float)
    true = np.array([c["distance_m"] or np.nan for c in cases], float)
    unsafe = tgt & (~has | (dist > true * (1 + TOL)))  # a missed vehicle, or one reported farther than it is
    out = {"pass": ok.mean(), **{f"pass_{k}": ok[kind == k].mean() if (kind == k).any() else None for k in ("on", "off", "edge")},
           "dung": ok[tgt].mean(), "du": has[tgt].mean(), "an_toan": 1 - unsafe.mean(),
           "mae_m": float(np.nanmean(np.abs(dist - true)[tgt & has])) if (tgt & has).any() else None}
    # the neighbours that exist: a case on the first or last frames of a video has fewer than K
    around = [[a for j in range(c["frame_index"] - K // 2, c["frame_index"] + K // 2 + 1) if (a := answer(c, j)) is not None] for c in cases]
    if all(len(frames) > 1 for frames in around):
        runs = [[passed(c, *a) for a in frames] for c, frames in zip(cases, around)]
        out |= {"pass_at_k": np.mean([any(r) for r in runs]), "pass_pow_k": np.mean([all(r) for r in runs])}
    return {k: None if v is None else round(float(v), 3) for k, v in out.items()}


MEDIAN, GEOMETRY = "Đoán trung vị (không nhìn ảnh)", "Hình học (bounding box + pinhole)"
NEAR = (10, 20)  # metres: the team counts a vehicle this close as outside the product's scope


def build_human_sheet(cases):
    """Draw, once, the 30 golden cases people answer: numbered images in random order, 4 worked examples from other cases, a blank sheet."""
    import cv2
    rng = np.random.RandomState(0)
    picked = [c for k, n in SHEET_SIZE.items() for c in rng.permutation([c for c in cases if c["type"] == k])[:n]]
    picked = list(rng.permutation(picked))
    rest = [c for c in cases if c not in picked]
    examples = [min((c for c in rest if c["has_target"]), key=lambda c: abs(c["distance_m"] - d)) for d in (20, 50, 85)] + [next(c for c in rest if not c["has_target"])]
    save = lambda c, f: cv2.imwrite(str(f), cv2.imread(str(DATA / c["image_path"])), [cv2.IMWRITE_JPEG_QUALITY, 92]) or sys.exit(f"cannot write {f}")
    for folder in ("anh", "vi_du", "tra_loi"):
        (SHEET / folder).mkdir(parents=True, exist_ok=True)
    for n, c in enumerate(picked, 1):
        save(c, SHEET / "anh" / f"{n:02d}.jpg")
    for c in examples:
        save(c, SHEET / "vi_du" / (f"co_xe_{c['distance_m']:.0f}m.jpg" if c["has_target"] else "khong_co_xe.jpg"))
    SHEET_KEY.write_text("anh,golden_id\n" + "".join(f"{n:02d},{c['id']}\n" for n, c in enumerate(picked, 1)), encoding="utf-8")
    (SHEET / "phieu_tra_loi.csv").write_text("anh,co_xe,khoang_cach_m,giay\n" + "".join(f"{n:02d},,,\n" for n in range(1, len(picked) + 1)), encoding="utf-8")


def sheet_cases(cases):
    by_id = {c["id"]: c for c in cases}
    return {int(r["anh"]): by_id[r["golden_id"]] for r in csv.DictReader(open(SHEET_KEY, encoding="utf-8"))}


def score_humans(cases):
    """Each filled sheet eval/human_baseline/tra_loi/<rater>.csv against the radar labels: {rater: (images answered, score, seconds per image)}.
    A sheet saved by Excel may use ; between columns and a decimal comma."""
    key, human = sheet_cases(cases), {}
    num = lambda v: float((v or "").strip().replace(",", ".") or "nan")
    for f in sorted((SHEET / "tra_loi").glob("*.csv")):
        text = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        rows = [r for r in csv.DictReader(text, delimiter=";" if ";" in text[0] else ",") if (r.get("co_xe") or "").strip()]
        mine = {key[int(r["anh"])]["id"]: (r["co_xe"].strip().lower() in ("1", "co", "có", "yes", "y", "x"), num(r["khoang_cach_m"])) for r in rows}
        if mine:
            seconds = np.nansum([num(r.get("giay")) for r in rows])  # per image, or the total written on one row
            human[f.stem] = (len(mine), score([c for c in key.values() if c["id"] in mine], lambda c, j: mine[c["id"]] if j == c["frame_index"] else None),
                             seconds / len(mine) if seconds else None)
    return human


def score_outside():
    """The team's own out-of-scope cases, answered by the app on the phone: {group: (cases, pass rate)} under the same rule as the golden set."""
    if not OUTSIDE.exists():
        OUTSIDE.write_text(OUTSIDE_COLUMNS + "\n", encoding="utf-8")
    groups = {}
    for r in csv.DictReader(open(OUTSIDE, encoding="utf-8-sig")):
        if (r["app_has_target"] or "").strip():
            case = {"has_target": r["true_has_target"].strip() == "1", "distance_m": float(r["true_distance_m"] or 0) or None}
            groups.setdefault(r["group"].strip(), []).append(passed(case, r["app_has_target"].strip() == "1", float(r["app_distance_m"] or "nan")))
    return {k: (len(v), float(np.mean(v))) for k, v in groups.items()}


def full_test(thresholds, median, geo_file):
    """Every system on all labelled test frames; distance error where the system and the radar both see a target."""
    rows = labelled("test")
    has = np.array([r["has_target"] == "1" for r in rows])
    true = np.array([float(r["distance_m"]) for r in rows])
    answers = {MEDIAN: (np.ones(len(rows), bool), np.full(len(rows), median))}
    if geo_file.exists():
        geo = list(csv.DictReader(open(geo_file)))
        assert [(r["scb_id"], r["frame_index"]) for r in geo] == [(r["scb_id"], r["frame_index"]) for r in rows], "geometry_predictions.csv is stale"
        answers[GEOMETRY] = (np.array([r["has_target"] == "1" for r in geo]), np.array([float(r["distance_m"] or "nan") for r in geo]))
    x = g.judged("test")[0]
    assert len(x) == len(rows)
    for name, folder in MODELS.items():
        sess = onnx_session(onnx_file(folder))
        out = np.array([run_pair(sess, x[i])[:2] for i in range(len(x))])
        answers[name] = (out[:, 0] > thresholds[name], out[:, 1])
    table = {}
    near = has & (true >= NEAR[0]) & (true < NEAR[1])  # closer than the range the product is meant for
    for name, (reports, dist) in answers.items():
        both = has & reports
        err, tp, fp, fn = np.abs(dist - true)[both], both.sum(), (reports & ~has).sum(), (has & ~reports).sum()
        table[name] = {"precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1), "f1": 2 * tp / max(2 * tp + fp + fn, 1),
                       "frames_both": int(tp), "mae_m": err.mean(), "median_m": np.median(err), "within_tol": (err <= TOL * true[both]).mean()}
        table[name] = {k: v if k == "frames_both" else round(float(v), 3) for k, v in table[name].items()}
        found, ok = near & reports, near & reports & (np.abs(dist - true) <= TOL * true)
        table[name]["near"] = {"frames": int(near.sum()), "videos": len({r["scb_id"] for r, n in zip(rows, near) if n}), "found": round(found.sum() / near.sum(), 3),
                               "pass": round(ok.sum() / near.sum(), 3), "mae_m": round(float(np.abs(dist - true)[found].mean()), 2) if found.any() else None}
    return table


def main():
    if not GOLDEN.exists() or sys.argv[1:] == ["rebuild"]:
        build_golden()
    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines()]
    OUT.mkdir(parents=True, exist_ok=True)
    thresholds = {n: json.loads((f / "benchmark.json").read_text(encoding="utf-8"))["threshold"] for n, f in MODELS.items()}
    run1, run2 = run_models(cases), run_models(cases)
    drift = max(abs(a - b) for n in MODELS for key in run1[n] for a, b in zip(run1[n][key], run2[n][key]))

    median = train_median()
    systems = {MEDIAN: lambda c, j: (True, median)}
    geo_file = OUT / "geometry_predictions.csv"
    if geo_file.exists():
        geo = {(r["scb_id"], int(r["frame_index"])): (r["has_target"] == "1", float(r["distance_m"] or "nan")) for r in csv.DictReader(open(geo_file))}
        systems[GEOMETRY] = lambda c, j: geo.get((c["scb_id"], j))
    for name in MODELS:
        systems[name] = lambda c, j, n=name: (lambda a: None if a is None else (a[0] > thresholds[n], a[1]))(run1[n].get((c["scb_id"], j)))
    scores = {name: score(cases, answer) for name, answer in systems.items()}
    rerun = {name: score(cases, lambda c, j, n=name: (lambda a: None if a is None else (a[0] > thresholds[n], a[1]))(run2[n].get((c["scb_id"], j))))
             for name in MODELS}

    if not SHEET_KEY.exists():
        build_human_sheet(cases)
    sheet = list(sheet_cases(cases).values())
    human, human_model, outside = score_humans(cases), score(sheet, systems[list(MODELS)[-1]]), score_outside()
    feedback = [r for r in csv.DictReader(open(FEEDBACK, encoding="utf-8"))
                if (r.get("quote") or "").strip() and r.get("feedback_type", "real_user") != "synthetic_expert_review"]
    bench = {n: json.loads((f / "benchmark.json").read_text(encoding="utf-8")) for n, f in MODELS.items()}
    full = full_test(thresholds, median, geo_file)

    evidence = {"tolerance": TOL, "k": K, "cases": {k: sum(c["type"] == k for c in cases) for k in ("on", "off", "edge")}, "scores": scores,
                "second_run": rerun, "max_output_difference_between_runs": drift, "human": {k: v[1] for k, v in human.items()},
                "model_on_human_cases": human_model, "out_of_scope": outside, "feedback_rows": len(feedback), "full_test": full}
    (OUT / "golden_dataset_metrics.json").write_text(json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")
    benchmark_exports = {"benchmark.json": "model_benchmark_metrics.json", "benchmark.md": "model_benchmark_report.md"}
    for source_name, output_name in benchmark_exports.items():
        shutil.copy(list(MODELS.values())[-1] / source_name, OUT / output_name)
    spec_md = spec(cases, bench[list(MODELS)[-1]], full[list(MODELS)[-1]], len(sheet), outside)
    (EVAL / "evaluation_protocol.md").write_text("\n".join(["# Evaluation protocol (4-tuple): gr14VinAI", "", f"Sinh bằng `python {SRC}/eval_evidence.py`.", "", *spec_md]), encoding="utf-8")
    (OUT / "deterministic_rerun_report.md").write_text("\n".join([
        "# Reproducibility: hai lần chạy trên toàn bộ golden dataset", "",
        f"Cùng model, cùng ngưỡng, cùng {len(cases)} case (mỗi case {K} frame), chạy hai lần liên tiếp bằng `python {SRC}/eval_evidence.py`.", "",
        "| Hệ thống | Đạt lần 1 | Đạt lần 2 | Case có kết quả đạt/không đạt giống nhau |", "|---|---:|---:|---:|",
        *[f"| {n} | {pct(scores[n]['pass'])} | {pct(rerun[n]['pass'])} | "
          f"{pct(np.mean([passed(c, a[0] > thresholds[n], a[1]) == passed(c, b[0] > thresholds[n], b[1]) for c in cases for a, b in [(run1[n][c['scb_id'], c['frame_index']], run2[n][c['scb_id'], c['frame_index']])]]))} |"
          for n in MODELS], "",
        f"Chênh lệch lớn nhất giữa hai lần chạy trên mọi đầu ra (xác suất có xe, khoảng cách): {drift:.6f}.", "",
        "Model là một mạng nơ-ron chạy tất định, không có bước lấy mẫu ngẫu nhiên, và người chấm là code so với nhãn radar, không phải LLM-judge; "
        f"vì vậy hai lần chạy cho cùng kết quả. Độ ổn định của sản phẩm theo thời gian được đo bằng pass^{K} trên {K} frame liên tiếp (mục 3 của báo cáo).", ""]), encoding="utf-8")
    REPORT.write_text(report(cases, scores, rerun, drift, human, feedback, bench[list(MODELS)[-1]], full, spec_md, human_model, len(sheet), outside), encoding="utf-8")
    print(json.dumps(scores, indent=1, ensure_ascii=False))


MISSING = "CHƯA CÓ"
pct = lambda v: MISSING if v is None else f"{v:.1%}"


def spec(cases, bench, full, sheet, outside):
    """The benchmark as request / environment / stopping criteria / scorer: eval/evaluation_protocol.md and section 1 of the report."""
    n = {k: sum(c["type"] == k for c in cases) for k in ("on", "off", "edge")}
    rows = labelled("test")
    videos, frames = {r["scb_id"] for r in rows}, f"{len(rows):,}".replace(",", ".")
    segments = list(csv.DictReader(open(DATA / "manifests/segments.csv", encoding="utf-8")))
    drive = lambda r: r["path"].rsplit("/", 1)[0]
    train_drives = {drive(r) for r in segments if r["split"] == "train" and r["time_of_day"] not in LEFT_OUT}
    shared = sum(r["scb_id"] in videos and drive(r) in train_drives for r in segments)
    cost, near = bench["cost"], full["near"]
    field = (f"`eval/inputs/out_of_scope.csv` hiện có {sum(k for k, _ in outside.values())} case thực địa." if outside else
             "`eval/inputs/out_of_scope.csv` hiện chưa có case thực địa nào, nên báo cáo này chưa có số đo nào từ iPhone hay từ đường Vin2.")
    return [
        "Sản phẩm là một model thị giác, không phải agent LLM. Bốn phần của khung được hiểu như sau: request = một case camera; "
        "environment = model, dữ liệu và máy chạy; stopping criteria = model được chạy bao nhiêu lần và trong bao lâu; scorer = cách chấm. "
        "Có hai lượt đo: trên bộ dữ liệu (máy tính, video Comma2k19) và thực địa (điện thoại, đường thật).", "",
        "### Request: đầu vào test là gì", "",
        "- Một case là một cặp frame liên tiếp (cách nhau 0,05 giây) từ camera trước của xe. Câu hỏi của mỗi case: phía trước có xe cùng làn trong 100 m không, "
        "nếu có thì cách bao nhiêu mét.",
        f"- Trên bộ dữ liệu: `eval/inputs/golden.jsonl`, {len(cases)} case từ {len(videos)} video lái xe thật của Comma2k19: {n['on']} on (có xe, 35-92 m, giữa làn), "
        f"{n['off']} off (không có xe cùng làn; câu trả lời đúng là \"không có xe\"), {n['edge']} edge (xe gần dưới 35 m, xa trên 92 m, hoặc sát mép làn). "
        "Không case nào do AI nghĩ ra; case được rút ngẫu nhiên (seed 0), lần lượt từng video.",
        f"- Bộ dữ liệu đại diện cho: đường cao tốc ở California, ban ngày và ban đêm, camera gắn cao {CAM_H:g} m. Chưa đại diện cho: chạng vạng "
        "(24 video bị loại khỏi train và test), trời mưa, camera khác, đường Việt Nam.",
        "- Thực địa (theo nhóm): video quay bằng iPhone 14 Pro Max trên đường Vin2, Khu đô thị Ocean Park, cùng câu hỏi như trên. " + field,
        f"- Ngoài phạm vi, theo nhóm xác định: xe gần {NEAR[0]}-{NEAR[1]} m, trời mưa, camera điện thoại. Xe gần {NEAR[0]}-{NEAR[1]} m được đo trên tập test "
        f"({near['frames']} frame từ {near['videos']} video); trời mưa và camera điện thoại lấy từ lượt thực địa.", "",
        "### Environment: chạy trong bối cảnh nào", "",
        f"- Model: `gr14VinAI.onnx` ({cost['parameters']:,} tham số, {cost['onnx_mb']} MB). Ngưỡng báo có xe {bench['threshold']:.2f} được chọn trên tập validation "
        "và giữ cố định khi chấm.",
        f"- Trên bộ dữ liệu: onnxruntime trên CPU, 4 luồng, mỗi lần một frame; {len(videos)} video test ({frames} frame có nhãn radar), không video nào nằm trong "
        f"tập train hay validation. {shared} video test thuộc cùng chuyến xe với một video train, vì 100 video ban đầu được chia theo đoạn chứ không theo chuyến.",
        "- Thực địa (theo nhóm): ứng dụng của nhóm chạy model trên iPhone 14 Pro Max, trên đường Vin2, Khu đô thị Ocean Park.",
        f"- Tiền xử lý: cắt cửa sổ {W} × {H} quanh điểm tụ của camera, đưa vào frame hiện tại và frame ngay trước. Model không nhớ gì giữa các case "
        "và không được dùng radar; radar chỉ dùng làm đáp án.", "",
        "### Stopping criteria: dừng khi nào", "",
        "- Mỗi case model chạy đúng một lần trên cặp frame và phải trả lời ngay: không lặp, không thử lại, không chọn đáp án tốt nhất trong nhiều lần.",
        f"- pass@{K} và pass^{K} dùng đúng {K} frame liên tiếp quanh case (0,25 giây), không hơn. Một lượt chấm kết thúc khi hết {len(cases)} case; "
        f"hệ thống nào thiếu đáp số dù chỉ ở một case thì cả dòng ghi {MISSING}.",
        f"- Ngân sách thời gian: camera quay 20 hình mỗi giây, nên mỗi frame có 50 ms. Đo trên máy tính: riêng model {cost['latency_ms']['median']} ms "
        f"(trung vị; 95% số lần dưới {cost['latency_ms']['p95']} ms), trong ngân sách; cả pipeline (giải mã video, cắt ảnh, model) trung bình "
        f"{cost['pipeline_ms_per_frame']} ms mỗi frame, vượt ngân sách. Thời gian mỗi frame trên iPhone 14 Pro Max: {MISSING} trong thư mục này.",
        "- Model, ngưỡng và bộ case được chốt trước khi chấm; không chỉnh gì sau khi xem kết quả.", "",
        "### Scorer: chấm thế nào", "",
        f"- Chấm bằng code (hàm `passed` trong `{SRC}/eval_evidence.py`), không dùng LLM-judge và không chấm bằng mắt. Đáp án luôn là số đo của radar, "
        "một cảm biến khác với camera và không liên quan tới model, nên bên chấm độc lập với bên trả lời.",
        "- Trên bộ dữ liệu: radar của xe thu dữ liệu Comma2k19. Thực địa (theo nhóm): radar của xe VinFast VF8, ghi ở cột `true_distance_m` của `eval/inputs/out_of_scope.csv`.",
        f"- Luật đạt, dùng cho cả hai lượt và cho người: case có xe thì phải báo có xe và khoảng cách lệch không quá {TOL:.0%} so với radar; "
        "case không có xe thì phải báo không có xe.",
        f"- Chỉ số: tỉ lệ đạt, đúng, đủ, an toàn (không bỏ sót xe, không báo xa hơn thực tế quá {TOL:.0%}), MAE, pass@{K}, pass^{K}; chạy hai lần để so "
        f"(`eval/results/deterministic_rerun_report.md`). Người được chấm trên {sheet} case của bộ golden.",
        "- Không áp dụng: citation và RAGAS, vì sản phẩm không truy xuất tài liệu.", ""]


def report(cases, scores, rerun, drift, human, feedback, bench, full, spec_md, human_model, sheet, outside):
    n = {k: sum(c["type"] == k for c in cases) for k in ("on", "off", "edge")}
    rows = labelled("test")
    videos, frames = len({r["scb_id"] for r in rows}), f"{len(rows):,}".replace(",", ".")
    curve = "curve" in g.RECIPE
    labels_file = f"{DATA.relative_to(ROOT).as_posix()}/labels{'_curved' if curve else ''}/test.csv"
    same_lane = ("xe gần nhất trong 100 m và cách tâm làn không quá 1,5 m; tâm làn bám theo đường đi thật của xe mình"
                 if curve else "xe gần nhất trong 100 m và lệch ngang không quá 1,5 m so với trục thẳng của xe mình")
    me = list(MODELS)[-1]
    shown = [k for k in scores if k != MEDIAN]  # the team compares the model with the geometric method and with people only
    mae = lambda s: MISSING if not s or s["mae_m"] is None else f"{s['mae_m']:.1f} m"
    cells = lambda s: f"{pct(s['pass'])} | {pct(s['dung'])} | {pct(s['du'])} | {pct(s['an_toan'])} | {mae(s)}"
    near = full[me]["near"]
    out = [
        "# Evaluation Evidence Report: gr14VinAI", "",
        f"Sinh bằng `python {SRC}/eval_evidence.py`. Mọi con số là số đo; phần chưa có dữ liệu ghi {MISSING}.", "",
        "Sản phẩm là một model thị giác: từ ảnh camera trả lời có xe cùng làn trong 100 m không và cách bao nhiêu mét. Nó không phải agent LLM hay RAG, "
        "nên việc chấm do code làm, so với radar; LLM-judge, citation và RAGAS không áp dụng.", "",
        "## 1. Benchmark spec (4-tuple)", "", *spec_md,
        "## 2. Golden dataset", "",
        f"- **File:** `eval/inputs/golden.jsonl`, {len(cases)} case: {n['on']} on, {n['off']} off, {n['edge']} edge (định nghĩa ở mục 1).",
        f"- **Nguồn:** frame của {videos} video test trong bộ Comma2k19, đáp án là nhãn radar (`{labels_file}`). Không có case nào do AI nghĩ ra.",
        f"- **Xe cùng làn:** {same_lane}.",
        f"- **Cách chọn:** ngẫu nhiên với seed 0 từ {frames} frame test, lần lượt từng video để không video nào áp đảo.", "",
        "## 3. Kết quả định lượng", "",
        f"| Hệ thống | Đạt | Đúng | Đủ | An toàn | MAE khi báo có xe | pass@{K} | pass^{K} |", "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {name} | {cells(scores[name])} | {pct(scores[name].get('pass_at_k'))} | {pct(scores[name].get('pass_pow_k'))} |" for name in shown], "",
        f"- **Đạt:** trên cả {len(cases)} case. **Đúng:** case có xe, báo có xe và khoảng cách trong dung sai {TOL:.0%}. **Đủ:** case có xe mà hệ thống phát hiện được. "
        "**An toàn:** không bỏ sót xe và không báo xa hơn thực tế quá dung sai.",
        f"- **pass@{K} / pass^{K}:** chạy trên {K} frame liên tiếp quanh mỗi case (0,25 giây); đạt ở ít nhất 1 frame / đạt ở cả {K} frame.",
        f"- **Theo loại case ({me}):** on {pct(scores[me]['pass_on'])}, off {pct(scores[me]['pass_off'])}, edge {pct(scores[me]['pass_edge'])}.",
        f"- **Reproducibility:** hai lần chạy đạt {pct(scores[me]['pass'])} và {pct(rerun[me]['pass'])}; chênh lệch lớn nhất trên mọi đầu ra {drift:.6f} "
        "(`eval/results/deterministic_rerun_report.md`).", "",
        "**Ngoài phạm vi (theo nhóm xác định):**", "",
        "| Nhóm | Số case | Đạt | Ghi chú |", "|---|---:|---:|---|",
        f"| Xe gần {NEAR[0]}-{NEAR[1]} m | {near['frames']} frame test, {near['videos']} video | {pct(near['pass'])} | phát hiện {pct(near['found'])}; "
        f"MAE khi báo có xe {near['mae_m']} m; nhãn radar của bộ dữ liệu |",
        *([f"| {k} | {count} | {pct(p)} | thực địa: ứng dụng trên điện thoại, so với radar xe VF8; `eval/inputs/out_of_scope.csv` |" for k, (count, p) in outside.items()]
          or [f"| Trời mưa, camera điện thoại (thực địa) | {MISSING} | {MISSING} | chờ dữ liệu trong `eval/inputs/out_of_scope.csv` |"]), "",
        "## 4. So sánh", "",
        f"### 4.1. Với phương pháp hình học (cả {frames} frame test)", "",
        "Phương pháp hình học không học từ dữ liệu: tìm khung xe bằng một detector có sẵn, rồi tính khoảng cách từ đáy khung bằng mô hình camera lỗ kim. "
        "Sai số khoảng cách tính trên các frame mà hệ thống và radar cùng thấy xe.", "",
        f"| Hệ thống | Precision | Recall | F1 | Frame cùng thấy xe | MAE | Trung vị | Lệch không quá {TOL:.0%} |", "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {name} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['frames_both']} | {s['mae_m']:.2f} m | {s['median_m']:.2f} m | {s['within_tol']:.1%} |"
          for name, s in full.items() if name != MEDIAN], "",
        f"### 4.2. Với con người ({sheet} case của bộ golden)", "",
        f"Người ngoài nhóm xem {sheet} ảnh rút từ bộ golden và trả lời có xe cùng làn phía trước không, cách bao nhiêu mét; chấm bằng luật ở mục 1. Họ được xem "
        "4 ảnh ví dụ có đáp án trước khi làm. Người xem một ảnh tĩnh; model xem hai frame liên tiếp. Cách thu: `eval/huongdanhumanbaseline.md`.", ""]
    if human:
        out += ["| Ai trả lời | Số ảnh | Đạt | Đúng | Đủ | An toàn | MAE khi báo có xe | Thời gian mỗi ảnh |", "|---|---:|---:|---:|---:|---:|---:|---:|",
                *[f"| {r} | {k} | {cells(s)} | {MISSING if sec is None else f'{sec:.0f} giây'} |" for r, (k, s, sec) in human.items()],
                f"| {me} | {sheet} | {cells(human_model)} | {bench['cost']['latency_ms']['median']} ms |", "",
                f"Số người: {len(human)}" + ("" if len(human) >= 2 else " (nên có ít nhất 2 người)") + ". Dòng của mỗi người chỉ tính trên các ảnh người đó trả lời; "
                f"dòng {me} tính trên cả {sheet} ảnh, thời gian là thời gian chạy mạng trên CPU cho một frame.", ""]
    else:
        out += [f"**{MISSING}.** Chưa có phiếu nào trong `eval/human_baseline/tra_loi/`. Trên cùng {sheet} case đó {me} đạt {pct(human_model['pass'])}.", ""]
    out += ["## 5. Feedback người dùng thật", ""]
    if feedback:
        cell = lambda r, key, empty: (r.get(key) or "").strip() or empty
        kinds = {}
        for r in feedback:
            kinds[cell(r, "team_reading", "chưa xếp")] = kinds.get(cell(r, "team_reading", "chưa xếp"), 0) + 1
        given = lambda key: [int(v) for r in feedback if (v := cell(r, key, "")) in {"1", "2", "3", "4", "5"}]
        mean = lambda key: f"{np.mean(given(key)):.1f} ({len(given(key))} người chấm)" if given(key) else MISSING
        fixes = sum(bool(cell(r, "fix_made", "")) for r in feedback)
        out += ["| Người dùng | Ngày | " + " | ".join(FEEDBACK_SCORES.values()) + " | Trích nguyên văn | Nhóm tự xếp loại | Đã sửa gì | Ngày sửa |",
                "|---|---|---:|---:|---:|---|---|---|---|",
                *[f"| {r['user']} | {cell(r, 'date', 'không ghi')} | " + " | ".join(cell(r, key, "không chấm") for key in FEEDBACK_SCORES) + f" | {r['quote']} | "
                  f"{cell(r, 'team_reading', 'chưa xếp')} | {cell(r, 'fix_made', 'chưa ghi')} | {cell(r, 'fix_date', '')} |" for r in feedback], "",
                f"Số người: {len(feedback)}" + ("" if len(feedback) >= 5 else " (tiêu chí yêu cầu ít nhất 5)") + ". Điểm trung bình do người dùng tự chấm, thang 1-5: "
                + "; ".join(f"{label.lower()} {mean(key)}" for key, label in FEEDBACK_SCORES.items()) + f". Phản hồi đã có việc sửa: {fixes} trên {len(feedback)}. "
                "Cột \"Nhóm tự xếp loại\" do nhóm tự xếp (" + ", ".join(f"{count} {k}" for k, count in kinds.items())
                + "), không phải điểm của người dùng. Cách thu: `eval/huongdanfeedback.md`.", ""]
    else:
        out += [f"**{MISSING}.** Điền `eval/inputs/user_feedback.csv`, cần ít nhất 5 người thật.", ""]
    rounds = json.loads(ROUNDS.read_text(encoding="utf-8"))
    row = lambda label, get, fmt: f"| {label} | " + " | ".join("chưa đo" if (v := get(r)) is None else fmt.format(v) for r in rounds) + " |"
    gold = lambda label, key: row(label, lambda r: r.get("golden", {}).get(key), "{:.1%}")
    before = json.loads(LABEL_CHANGE.read_text(encoding="utf-8"))["previous"]
    out += ["## 6. Before/after", "",
            "Vòng 1 đến vòng 5 được đo trên cùng 10 video test ban đầu, cùng nhãn và cùng bộ golden 300 case của 10 video đó, nên so trực tiếp được.", "",
            "| Chỉ số | " + " | ".join(r["name"] for r in rounds) + " |", "|---|" + "---:|" * len(rounds),
            row("Test: MAE", lambda r: r["test"]["mae_m"], "{:.2f} m"), row("Test: F1 có xe", lambda r: r["test"]["f1"], "{:.3f}"),
            gold("Golden: tỉ lệ đạt", "pass"), gold(f"Golden: pass^{K}", "pass_pow_k"), gold("Golden: an toàn", "an_toan"),
            row("Latency trung vị trên CPU", lambda r: r["cost"]["latency_ms"]["median"], "{} ms"), "",
            *[f"- **{r['name']}:** {r['what']}" for r in rounds], "",
            "Số của các vòng này được đo vào lúc đó và ghi lại trong `eval/inputs/model_iteration_history.json`; file model của chúng không còn, nên không chạy lại được.", "",
            "**Vòng 6 và vòng cuối.** Vòng 6 thêm 254 video và đổi định nghĩa \"cùng làn\" sang hành lang bám theo đường đi của xe. Tập test và nhãn đều đổi, "
            "nên hai vòng này không đặt chung bảng với vòng 1-5 (số đối chiếu theo cả hai định nghĩa nhãn: `eval/inputs/label_rule_comparison.json`). "
            f"Vòng cuối: {CURRENT_ROUND} Hai vòng được chấm trên cùng tập test hiện tại ({videos} video):", "",
            "| Model | MAE | F1 có xe |", "|---|---:|---:|",
            f"| {before['model']} | {before['all']['mae_m']:.2f} m | {before['all']['f1']:.3f} |",
            f"| **Vòng cuối** | **{bench['test']['mae_m']:.2f} m** | **{bench['test']['f1']:.3f}** |", "",
            before["note"] + " Chỉ số đầy đủ của vòng cuối: `eval/results/model_benchmark_report.md`.", "",
            "## Nguồn tham khảo", "",
            "- Dữ liệu: Comma2k19 của comma.ai, giấy phép MIT.",
            "- Kiến trúc: Kiến trúc hai luồng gr14VinAI do tác giả tự thiết kế và huấn luyện từ đầu (from scratch) trên tập dữ liệu của dự án, "
            "tích hợp luồng toàn cảnh ConvNeXt, luồng fovea độ nét cao, nhúng bản đồ hình học camera, spatial attention định hướng bởi radar và đầu ra phân phối khoảng cách.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    main()
