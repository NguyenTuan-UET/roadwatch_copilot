"""Build the Evaluation Evidence Report (docs/evaluation_evidence.md) from measurements only.

    python src/eval_evidence.py            # score and write the report
    python src/eval_evidence.py rebuild    # also redraw the golden set (and reset the human-baseline sheet)

eval/golden.jsonl         300 real test cases (150 on, 75 off, 75 edge), written once from the radar labels
eval/human_baseline.csv   10 of those cases for people to fill in; scored once filled
eval/user_feedback.csv    one row per real user; shown in the report once filled
results/eval/geometry_preds.csv   from `python src/geometry.py`; the geometric competitor, scored once present
Whatever has not been measured yet is printed as "CHƯA CÓ", never as a number.
"""
import csv
import json
import sys

import numpy as np

import train_distance as g
from common import DATA, RAW, ROOT, labelled, onnx_session, read_yuv_frames, train_median, vanishing_point

EVAL, OUT = ROOT / "eval", ROOT / "results" / "eval"
GOLDEN, HUMAN, FEEDBACK = EVAL / "golden.jsonl", EVAL / "human_baseline.csv", EVAL / "user_feedback.csv"
ROUNDS = EVAL / "rounds.json"  # recorded numbers of earlier rounds, for the before/after table
LABEL_CHANGE = EVAL / "label_change.json"  # recorded: the previous and the final model on the new test videos, under both label definitions
CURRENT_ROUND = ("bỏ 24 video chạng vạng khỏi train, validation và test (quá ít để train và để chấm); lúc train lấy mẫu cân bằng theo "
                 "(ngày, đêm) x khoảng cách, để frame hiếm (dưới 20 m, 80-100 m, ban đêm) được chọn thường xuyên hơn. Kiến trúc và nhãn giữ như vòng 6. "
                 "Train hai lần (seed 1 và 2), chọn seed 2 trên validation.")
GOLDEN_SIZE = {"on": 150, "off": 75, "edge": 75}
TOL = 0.15  # a distance passes when it is within 15 % of the radar distance
K = 5  # pass@k / pass^k over the labelled frame and its 2 neighbours on each side (0.25 s of video)
# name -> folder holding the benchmark.json with its validation threshold. The last entry is the current model;
# put an earlier round before it to get the before/after table.
MODELS = {"gr14VinAI": ROOT / "results" / "benchmark"}


def onnx_file(folder):
    """The current model has one ONNX, in model/; an earlier round keeps its own next to its benchmark.json."""
    own = folder / "gr14VinAI.onnx"
    return own if own.exists() else ROOT / "model" / "gr14VinAI.onnx"


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
    with open(HUMAN, "w", newline="", encoding="utf-8") as f:  # 5 on, 3 off, 2 edge for the human baseline
        w = csv.writer(f)
        w.writerow(["id", "image_path", "rater", "human_has_target", "human_distance_m"])
        pick = {"on": 5, "off": 3, "edge": 2}
        w.writerows([c["id"], (DATA / c["image_path"]).resolve().relative_to(ROOT).as_posix(), "", "", ""] for c in sorted(cases, key=lambda c: c["id"])
                    if int(c["id"].split("-")[1]) <= pick[c["type"]])
    if not FEEDBACK.exists():
        FEEDBACK.write_text("user,date,score_1_to_5,quote,fix_made\n", encoding="utf-8")


def run_models(cases):
    """Each model on the frames around every golden case: {model: {(scb, frame): (probability, metres)}}."""
    sessions = {name: onnx_session(onnx_file(folder)) for name, folder in MODELS.items()}
    preds = {name: {} for name in MODELS}
    for scb in sorted({c["scb_id"] for c in cases}):
        needed = {j for c in cases if c["scb_id"] == scb for j in range(c["frame_index"] - K // 2, c["frame_index"] + K // 2 + 1)}
        prev = None
        for j, frame in enumerate(read_yuv_frames(RAW / scb / "video.hevc", vanishing_point(RAW / scb))):
            if j in needed:
                x = np.concatenate([frame if prev is None else prev, frame])[None]
                for name, sess in sessions.items():
                    p, d = sess.run(None, {"input_imgs": x})[:2]
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
    out = {"pass": ok.mean(), **{f"pass_{k}": ok[kind == k].mean() for k in ("on", "off", "edge")},
           "dung": ok[tgt].mean(), "du": has[tgt].mean(), "an_toan": 1 - unsafe.mean(),
           "mae_m": float(np.nanmean(np.abs(dist - true)[tgt & has])) if (tgt & has).any() else None}
    # the neighbours that exist: a case on the first or last frames of a video has fewer than K
    around = [[a for j in range(c["frame_index"] - K // 2, c["frame_index"] + K // 2 + 1) if (a := answer(c, j)) is not None] for c in cases]
    if all(len(frames) > 1 for frames in around):
        runs = [[passed(c, *a) for a in frames] for c, frames in zip(cases, around)]
        out |= {"pass_at_k": np.mean([any(r) for r in runs]), "pass_pow_k": np.mean([all(r) for r in runs])}
    return {k: None if v is None else round(float(v), 3) for k, v in out.items()}


GEOMETRY = "Hình học (bounding box + pinhole)"


def full_test(thresholds, median, geo_file):
    """Every system on all labelled test frames; distance error where the system and the radar both see a target."""
    rows = labelled("test")
    has = np.array([r["has_target"] == "1" for r in rows])
    true = np.array([float(r["distance_m"]) for r in rows])
    answers = {"Đoán trung vị (không nhìn ảnh)": (np.ones(len(rows), bool), np.full(len(rows), median))}
    if geo_file.exists():
        geo = list(csv.DictReader(open(geo_file)))
        assert [(r["scb_id"], r["frame_index"]) for r in geo] == [(r["scb_id"], r["frame_index"]) for r in rows], "geometry_preds.csv is stale"
        answers[GEOMETRY] = (np.array([r["has_target"] == "1" for r in geo]), np.array([float(r["distance_m"] or "nan") for r in geo]))
    x = g.judged("test")[0]
    assert len(x) == len(rows)
    for name, folder in MODELS.items():
        sess = onnx_session(onnx_file(folder))
        out = np.array([[o.item() for o in sess.run(None, {"input_imgs": x[i:i + 1].astype(np.float32)})[:2]] for i in range(len(x))])
        answers[name] = (out[:, 0] > thresholds[name], out[:, 1])
    table = {}
    for name, (reports, dist) in answers.items():
        both = has & reports
        err, tp, fp, fn = np.abs(dist - true)[both], both.sum(), (reports & ~has).sum(), (has & ~reports).sum()
        table[name] = {"precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1), "f1": 2 * tp / max(2 * tp + fp + fn, 1),
                       "frames_both": int(tp), "mae_m": err.mean(), "median_m": np.median(err), "within_tol": (err <= TOL * true[both]).mean()}
    return {n: {k: v if k == "frames_both" else round(float(v), 3) for k, v in t.items()} for n, t in table.items()}


def main():
    if not GOLDEN.exists() or sys.argv[1:] == ["rebuild"]:
        build_golden()
    cases = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines()]
    OUT.mkdir(parents=True, exist_ok=True)
    thresholds = {n: json.loads((f / "benchmark.json").read_text(encoding="utf-8"))["threshold"] for n, f in MODELS.items()}
    run1, run2 = run_models(cases), run_models(cases)
    drift = max(abs(a - b) for n in MODELS for key in run1[n] for a, b in zip(run1[n][key], run2[n][key]))

    median = train_median()
    systems = {"Đoán trung vị (không nhìn ảnh)": lambda c, j: (True, median)}
    geo_file = OUT / "geometry_preds.csv"
    if geo_file.exists():
        geo = {(r["scb_id"], int(r["frame_index"])): (r["has_target"] == "1", float(r["distance_m"] or "nan")) for r in csv.DictReader(open(geo_file))}
        systems[GEOMETRY] = lambda c, j: geo.get((c["scb_id"], j))
    for name in MODELS:
        systems[name] = lambda c, j, n=name: (lambda a: None if a is None else (a[0] > thresholds[n], a[1]))(run1[n].get((c["scb_id"], j)))
    scores = {name: score(cases, answer) for name, answer in systems.items()}
    rerun = {name: score(cases, lambda c, j, n=name: (lambda a: None if a is None else (a[0] > thresholds[n], a[1]))(run2[n].get((c["scb_id"], j))))
             for name in MODELS}

    by_id = {c["id"]: c for c in cases}
    human_rows = [r for r in csv.DictReader(open(HUMAN, encoding="utf-8")) if r["human_has_target"].strip()]
    human = {}
    for rater in sorted({r["rater"] for r in human_rows}):
        mine = {r["id"]: (r["human_has_target"].strip() in ("1", "yes", "có"), float(r["human_distance_m"] or "nan")) for r in human_rows if r["rater"] == rater}
        human[rater or "?"] = (len(mine), score([by_id[i] for i in mine], lambda c, j: mine[c["id"]] if j == c["frame_index"] else None))
    human_ids = [r["id"] for r in csv.DictReader(open(HUMAN, encoding="utf-8"))]
    same10 = {name: score([by_id[i] for i in dict.fromkeys(human_ids)], systems[name]) for name in MODELS}
    written = list(csv.DictReader(open(FEEDBACK, encoding="utf-8")))
    feedback = [r for r in written if (r.get("score_1_to_5") or "").strip() in {"1", "2", "3", "4", "5"}]  # a row counts when it has its score
    unreadable = len(written) - len(feedback)
    bench = {n: json.loads((f / "benchmark.json").read_text(encoding="utf-8")) for n, f in MODELS.items()}
    full = full_test(thresholds, median, geo_file)

    evidence = {"tolerance": TOL, "k": K, "cases": {k: sum(c["type"] == k for c in cases) for k in ("on", "off", "edge")}, "scores": scores,
                "second_run": rerun, "max_output_difference_between_runs": drift, "human": {k: v[1] for k, v in human.items()},
                "models_on_human_cases": same10, "feedback_rows": len(feedback), "full_test": full}
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "docs" / "evaluation_evidence.md").write_text(report(cases, scores, rerun, drift, human, same10, feedback, bench, full, geo_file.exists(), unreadable), encoding="utf-8")
    print(json.dumps(scores, indent=1, ensure_ascii=False))


MISSING = "CHƯA CÓ"
pct = lambda v: MISSING if v is None else f"{v:.1%}"


def report(cases, scores, rerun, drift, human, same10, feedback, bench, full, has_geometry, unreadable=0):
    n = {k: sum(c["type"] == k for c in cases) for k in ("on", "off", "edge")}
    rows = labelled("test")
    videos, frames = len({r["scb_id"] for r in rows}), f"{len(rows):,}".replace(",", ".")
    curve = "curve" in g.RECIPE
    labels_file = f"{DATA.relative_to(ROOT).as_posix()}/labels{'_curved' if curve else ''}/test.csv"
    same_lane = ("xe gần nhất trong 100 m và cách tâm làn không quá 1,5 m; tâm làn bám theo đường đi thật của xe mình (lấy từ `global_pose`), "
                 "nên ở đoạn cong hành lang cong theo đường" if curve else "xe gần nhất trong 100 m và lệch ngang không quá 1,5 m so với trục thẳng của xe mình")
    v1, v2 = (list(MODELS)[0] if len(MODELS) > 1 else None), list(MODELS)[-1]
    line = lambda name, s: (f"| {name} | {MISSING} | | | | | | |" if s is None else
                            f"| {name} | {pct(s['pass'])} | {pct(s['dung'])} | {pct(s['du'])} | {pct(s['an_toan'])} | "
                            f"{MISSING if s['mae_m'] is None else f'{s['mae_m']:.1f} m'} | {pct(s.get('pass_at_k'))} | {pct(s.get('pass_pow_k'))} |")
    t = lambda name, key, fmt="{:.2f} m": fmt.format(bench[name]["test"][key])
    out = [
        "# Evaluation Evidence Report: gr14VinAI", "",
        "Sinh bằng `python src/eval_evidence.py`. Mọi con số là số đo; phần chưa đo ghi rõ " + MISSING + ".", "",
        "Sản phẩm là một model thị giác (ảnh camera -> có xe cùng làn hay không, cách bao nhiêu mét), không phải agent LLM/RAG. "
        "Vì vậy các khái niệm của khung chấm được ánh xạ như sau: câu hỏi = một frame camera; câu trả lời = (có xe, khoảng cách); "
        "scorer = code-check so với nhãn radar (không dùng LLM-judge); citation và RAGAS không áp dụng vì không có truy xuất tài liệu.", "",
        "## 1. Benchmark spec (4-tuple)", "",
        "| Thành phần | Nội dung |", "|---|---|",
        "| Task | Từ 2 frame camera liên tiếp, trả lời có xe cùng làn trong 100 m không và khoảng cách tới xe đó |",
        f"| Dataset | `eval/golden.jsonl`: {len(cases)} case thật lấy từ {videos} video test, nhãn từ radar |",
        f"| Metric | Tỉ lệ case đạt; pass@{K} và pass^{K}; kèm đúng / đủ / an toàn |",
        f"| Ngưỡng đạt | Case có xe: model báo có xe và khoảng cách lệch không quá {TOL:.0%} so với radar. Case không có xe: model báo không có xe |", "",
        "Định nghĩa 4-tuple ở đây là cách hiểu (task, dataset, metric, ngưỡng); cần đối chiếu lại với bài tập 8.5.1.", "",
        "## 2. Golden dataset", "",
        f"- **Nguồn:** nhãn radar của bộ Comma2k19 trên tập test (`{labels_file}`), không có case nào do AI nghĩ ra.",
        f"- **Xe cùng làn:** {same_lane}.",
        f"- **Số case:** {n['on']} on (có xe, 35-92 m, giữa làn), {n['off']} off (không có xe cùng làn), {n['edge']} edge (xe gần dưới 35 m, xa trên 92 m, hoặc cách tâm làn từ 1,3 m trở lên).",
        f"- **Cách chọn:** ngẫu nhiên với seed 0 từ {frames} frame test, lấy lần lượt từ {videos} video để không video nào áp đảo, cố định trong file JSONL.",
        "- **File:** `eval/golden.jsonl`, mỗi dòng một case với đoạn video, frame, ảnh, nhãn và nguồn.", "",
        "## 3. Kết quả định lượng", "",
        f"| Hệ thống | Đạt | Đúng | Đủ | An toàn | MAE khi báo có xe | pass@{K} | pass^{K} |", "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[line(name, s) for name, s in scores.items()], "",
        f"- **Đạt:** tỉ lệ trên cả {len(cases)} case. **Đúng:** tỉ lệ case có xe mà model báo có xe và khoảng cách trong dung sai {TOL:.0%}. "
        "**Đủ:** tỉ lệ case có xe mà model phát hiện được. **An toàn:** tỉ lệ case model không bỏ sót xe và không báo xa hơn thực tế quá dung sai.",
        f"- **pass@{K} / pass^{K}:** model được chạy trên {K} frame liên tiếp quanh mỗi case (0,25 giây). pass@{K} = đạt ở ít nhất 1 frame; pass^{K} = đạt ở cả {K} frame.",
        "- **Citation:** không áp dụng.",
        f"- **Theo loại case ({v2}):** on {pct(scores[v2]['pass_on'])}, off {pct(scores[v2]['pass_off'])}, edge {pct(scores[v2]['pass_edge'])}.", "",
        "**Reproducibility (2 lần chạy):**", "",
        "| Hệ thống | Đạt lần 1 | Đạt lần 2 |", "|---|---:|---:|",
        *[f"| {name} | {pct(scores[name]['pass'])} | {pct(rerun[name]['pass'])} |" for name in MODELS], "",
        f"Chênh lệch lớn nhất giữa hai lần chạy trên mọi đầu ra: {drift:.6f}.", "",
        "## 4. So sánh", "",
        "### 4.1. Với đối thủ", "",
        "Bảng ở mục 3 đã gồm các đối thủ: đoán trung vị" + (", phương pháp hình học" if has_geometry else "") + (" và phiên bản trước của chính model. " if v1 else ". ")
        + ("" if has_geometry else f"**Phương pháp hình học: {MISSING}.** Code đã có (`src/geometry.py`); chạy `python src/geometry.py` rồi chạy lại script này để điền số."), "",
        f"Trên toàn bộ {frames} frame test. Sai số khoảng cách tính trên các frame mà hệ thống và radar cùng thấy xe "
        "(phương pháp hình học không có khoảng cách khi không tìm thấy xe, nên đây là cách so công bằng cho mọi hệ thống):", "",
        f"| Hệ thống | Precision | Recall | F1 | Frame cùng thấy xe | MAE | Trung vị | Lệch không quá {TOL:.0%} |", "|---|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {name} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['frames_both']} | {s['mae_m']:.2f} m | {s['median_m']:.2f} m | {s['within_tol']:.1%} |"
          for name, s in full.items()], "",
        "### 4.2. Với con người (10 case)", "",
    ]
    if human:
        out += ["| Người chấm | Số case | Đạt | MAE khi báo có xe |", "|---|---:|---:|---:|",
                *[f"| {r} | {k} | {pct(s['pass']) if s else MISSING} | {MISSING if not s or s['mae_m'] is None else f'{s['mae_m']:.1f} m'} |" for r, (k, s) in human.items()],
                *[f"| {name} (cùng 10 case) | 10 | {pct(s['pass'])} | {s['mae_m']:.1f} m |" for name, s in same10.items()], ""]
    else:
        out += [f"**{MISSING}.** File `eval/human_baseline.csv` có sẵn 10 case (5 on, 3 off, 2 edge). Mỗi người xem ảnh, điền `rater`, "
                "`human_has_target` (1/0) và `human_distance_m`, rồi chạy lại script. Trên cùng 10 case đó:", "",
                "| Hệ thống | Đạt |", "|---|---:|", *[f"| {name} | {pct(s['pass'])} |" for name, s in same10.items()], ""]
    out += ["## 5. Feedback người dùng thật", ""]
    if feedback:
        out += ["| Người dùng | Ngày | Điểm (1-5) | Trích nguyên văn | Đã sửa gì |", "|---|---|---:|---|---|",
                *[f"| {r['user']} | {r['date']} | {r['score_1_to_5']} | {r['quote']} | {r['fix_made']} |" for r in feedback], "",
                f"Số người: {len(feedback)}" + ("" if len(feedback) >= 5 else " (tiêu chí yêu cầu ít nhất 5)") + ".", ""]
    else:
        out += [f"**{MISSING}.** Điền `eval/user_feedback.csv` (mỗi người một dòng: user, date, score_1_to_5, quote, fix_made), cần ít nhất 5 người thật.", ""]
    if unreadable:
        out += [f"File `eval/user_feedback.csv` còn {unreadable} dòng chưa đúng định dạng (không có điểm 1-5 ở cột `score_1_to_5`) nên chưa được tính ở đây.", ""]
    out += ["## 6. Before/after", ""]
    if v1:
        out += [
            f"Vòng trước là {v1}, vòng cuối là {v2}: cùng dữ liệu và cùng cách chấm.", "",
            "| Chỉ số | Vòng trước | Vòng cuối |", "|---|---:|---:|",
            f"| Golden: tỉ lệ đạt | {pct(scores[v1]['pass'])} | {pct(scores[v2]['pass'])} |",
            f"| Golden: pass^{K} | {pct(scores[v1].get('pass_pow_k'))} | {pct(scores[v2].get('pass_pow_k'))} |",
            f"| Golden: an toàn | {pct(scores[v1]['an_toan'])} | {pct(scores[v2]['an_toan'])} |",
            f"| Test: MAE | {t(v1, 'mae_m')} | {t(v2, 'mae_m')} |",
            f"| Test: sai số trung vị | {t(v1, 'median_m')} | {t(v2, 'median_m')} |",
            f"| Test: lệch không quá 10 m | {t(v1, 'within_10m', '{:.1%}')} | {t(v2, 'within_10m', '{:.1%}')} |",
            f"| Test: recall có xe | {t(v1, 'recall', '{:.3f}')} | {t(v2, 'recall', '{:.3f}')} |",
            f"| Test: F1 có xe | {t(v1, 'f1', '{:.3f}')} | {t(v2, 'f1', '{:.3f}')} |", ""]
    elif ROUNDS.exists():  # earlier rounds whose models are gone: their recorded numbers, labelled as such
        new = bench[v2]
        rounds = json.loads(ROUNDS.read_text(encoding="utf-8"))
        row = lambda label, get, fmt: f"| {label} | " + " | ".join("chưa đo" if (v := get(r)) is None else fmt.format(v) for r in rounds) + " |"
        test = lambda label, key, fmt: row(label, lambda r: r["test"][key], fmt)
        gold = lambda label, key: row(label, lambda r: r.get("golden", {}).get(key), "{:.1%}")
        out += [
            "### 6.1. Các vòng trước", "",
            "Mọi vòng trong bảng này được đo trên 10 video test ban đầu, với nhãn hành lang thẳng của bộ dữ liệu và bộ golden 300 case lấy từ 10 video đó.", "",
            "| Chỉ số | " + " | ".join(r["name"] for r in rounds) + " |", "|---|" + "---:|" * len(rounds),
            test("Test: sai số trung bình (MAE)", "mae_m", "{:.2f} m"), test("Test: sai số trung vị", "median_m", "{:.2f} m"),
            test("Test: RMSE", "rmse_m", "{:.2f} m"), test("Test: sai số tương đối", "abs_rel", "{:.1%}"),
            test("Test: lệch không quá 5 m", "within_5m", "{:.1%}"), test("Test: lệch không quá 10 m", "within_10m", "{:.1%}"),
            test("Test: precision có xe", "precision", "{:.3f}"), test("Test: recall có xe", "recall", "{:.3f}"), test("Test: F1 có xe", "f1", "{:.3f}"),
            gold("Golden: tỉ lệ đạt", "pass"), gold("Golden: đúng", "dung"), gold("Golden: đủ", "du"), gold("Golden: an toàn", "an_toan"),
            gold(f"Golden: pass^{K}", "pass_pow_k"), gold("Golden: nhóm edge", "pass_edge"),
            row("Số tham số", lambda r: r["cost"]["parameters"], "{:,}"), row("File ONNX", lambda r: r["cost"]["onnx_mb"], "{} MB"),
            row("Latency trung vị trên CPU", lambda r: r["cost"]["latency_ms"]["median"], "{} ms"), "",
            "Mỗi vòng thay đổi gì:", "", *[f"- **{r['name']}:** {r['what']}" for r in rounds], "",
            "Số của các vòng này là số đã đo vào thời điểm đó và được ghi lại trong `eval/rounds.json`; file model của các vòng đó "
            "không còn trong thư mục nên không tái tạo lại được.", "",
            "### 6.2. Vòng 6: thêm dữ liệu và đổi định nghĩa \"cùng làn\"", "",
            "Vòng 6 thêm 254 video (train trên 284 video thay vì 80), tính \"cùng làn\" theo hành lang bám theo đường đi của xe thay cho hành lang thẳng, "
            "và thêm đầu dự đoán tâm làn. Nó đổi cả tập test (từ 10 lên 36 video) lẫn định nghĩa nhãn, nên không đặt chung bảng với các vòng trước được: "
            "hai định nghĩa nhãn cho đáp án khác nhau ở khoảng một phần năm số frame, nên model nào chấm theo nhãn kia cũng kém. "
            "Bảng dưới chấm các model trên cùng tập test 36 video, theo cả hai định nghĩa nhãn. Mỗi ô là MAE / F1 có xe.", ""]
        change = json.loads(LABEL_CHANGE.read_text(encoding="utf-8")) if LABEL_CHANGE.exists() else None
        cell = lambda a: f"{a['mae_m']:.2f} m / {a['f1']:.3f}"
        if change:
            out += ["| Model | Nhãn dùng để chấm | 10 video test ban đầu | 26 video test thêm sau | Cả 36 video |", "|---|---|---:|---:|---:|",
                    *[f"| {r['model']} | {r['labels']} | {cell(r['original'])} | {cell(r['added'])} | {cell(r['all'])} |" for r in change["rows"]], "",
                    change["note"], ""]
        out += ["### 6.3. Vòng cuối", "",
                f"**Vòng cuối ({new['cost']['parameters'] / 1e6:.2f} triệu tham số):** {CURRENT_ROUND}", ""]
        if change and "by_group" in new:
            first, second = (next((k, v) for k, v in new["by_group"].items() if k.endswith(name)) for name in ("video test ban đầu", "video test thêm sau"))
            before = change["previous"]
            out += [f"Vòng 6 và vòng cuối được chấm trên cùng tập test hiện tại ({videos} video, không có chạng vạng) và cùng nhãn bám theo đường, nên so trực tiếp được. "
                    "Mỗi ô là MAE / F1 có xe.", "",
                    f"| Model | {first[0]} | {second[0]} | Cả {videos} video |", "|---|---:|---:|---:|",
                    f"| {before['model']} | {cell(before['original'])} | {cell(before['added'])} | {cell(before['all'])} |",
                    f"| **Vòng cuối** | **{cell(first[1])}** | **{cell(second[1])}** | **{cell(new['test'])}** |", "",
                    before["note"], ""]
        out += [
            "| Vòng cuối: chỉ số khác | Giá trị |", "|---|---:|",
            f"| Test: sai số trung vị | {new['test']['median_m']:.2f} m |", f"| Test: RMSE | {new['test']['rmse_m']:.2f} m |",
            f"| Test: sai số tương đối | {new['test']['abs_rel']:.1%} |", f"| Test: lệch không quá 5 m | {new['test']['within_5m']:.1%} |",
            f"| Test: lệch không quá 10 m | {new['test']['within_10m']:.1%} |",
            f"| Test: precision / recall có xe | {new['test']['precision']:.3f} / {new['test']['recall']:.3f} |",
            f"| Golden ({len(cases)} case từ {videos} video): tỉ lệ đạt | {pct(scores[v2]['pass'])} |",
            f"| Golden: đúng / đủ / an toàn | {pct(scores[v2]['dung'])} / {pct(scores[v2]['du'])} / {pct(scores[v2]['an_toan'])} |",
            f"| Golden: pass^{K} | {pct(scores[v2].get('pass_pow_k'))} |", f"| Golden: nhóm edge | {pct(scores[v2]['pass_edge'])} |",
            f"| Số tham số | {new['cost']['parameters']:,} |", f"| File ONNX | {new['cost']['onnx_mb']} MB |",
            f"| Latency trung vị trên CPU | {new['cost']['latency_ms']['median']} ms |", "",
            "Bộ golden được lấy lại mỗi khi tập test hoặc định nghĩa nhãn đổi (vòng 6 và vòng cuối), nên tỉ lệ đạt trên golden không so trực tiếp được giữa các vòng đó"
            + (f"; vòng 6 đạt {change['previous']['golden_pass']:.1%} trên bộ golden của nó." if change else "."), ""]
    else:
        out += [f"**{MISSING}.** Thư mục chỉ còn kết quả của bản model hiện tại, nên không có vòng trước để so. Muốn có bảng này: giữ lại thư mục "
                "benchmark (file `gr14VinAI.onnx` và `benchmark.json`) của một vòng trước và thêm nó vào `MODELS` ở đầu `src/eval_evidence.py`.", ""]
    out += [
        "## Nguồn tham khảo", "",
        "- Dữ liệu: Comma2k19 của comma.ai, giấy phép MIT.",
        "- Kiến trúc: Kiến trúc hai luồng gr14VinAI do tác giả tự thiết kế và huấn luyện từ đầu (from scratch) trên tập dữ liệu của dự án, "
        "tích hợp luồng toàn cảnh ConvNeXt, luồng fovea độ nét cao, nhúng bản đồ hình học camera, spatial attention định hướng bởi radar và đầu ra phân phối khoảng cách.", ""]
    return "\n".join(out)


if __name__ == "__main__":
    main()
