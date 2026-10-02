---
doc_id: "RW-PLAN-INITIAL"
doc_type: "archive"
status: "archived"
authority_for: []
---

# RoadWatch Copilot MVP: kế hoạch triển khai (bản ngắn)

> **Lưu trữ, không cập nhật tiếp.** Việc viết code dừng ngày 28/09 theo quyết định của PO. Tình trạng các task T1–T8 (đã có code, đã kiểm chứng bằng gì, còn thiếu gì) và phân công hiện tại nằm ở [README.md](README.md), mục 3–4. Các mục ở đây **chưa** phải là đã nghiệm thu.
>
> Thực hiện trực tiếp trong phiên này, từng task một theo TDD. Mỗi task có test đi kèm và được commit riêng.

**Mục tiêu:** có phần mềm MVP chạy offline xuyên suốt A → B → audio cùng các công cụ C (`rerun-B`, đánh giá, HITL CLI). Phần mềm này làm được mọi việc của tiêu chí AC-M, **trừ những bước cần dữ liệu thực địa của nhóm**.

**Kiến trúc:** theo `docs/specs/roadwatch-architecture.md` (APPROVED). Runtime là một process nhiều thread. `join`, B, baseline và bộ phân xử audio là hàm thuần, nên cùng một code dùng cho `rerun-B`. Hợp đồng dữ liệu là Pydantic v2, ghi ra JSONL.

**Công nghệ:** Python ≥ 3.11 (code phải chạy được trên 3.11, hiện phát triển trên 3.13); numpy; opencv-python (đọc video, NMS, `phaseCorrelate`); onnxruntime; pydantic v2; pyyaml; `winsound` (thư viện chuẩn, dùng làm audio sink trên Windows); `sqlite3` (thư viện chuẩn, dùng cho HITL); piper-tts (chỉ để render câu nói, không chạy lúc runtime).

## Ràng buộc chung

- Chạy offline hoàn toàn; không gọi mạng lúc runtime.
- ONNX Runtime FP32, `intra_op_num_threads = 4`, `inter_op_num_threads = 1`.
- Không có hồ sơ xe; chỉ có một cấu hình lắp cố định (ADR-04).
- Không có trường nào điều khiển xe; B không đọc giờ hệ thống; runtime không đọc SQLite.
- Cấm dùng 0 thay dữ liệu thiếu; cấm NaN/∞; `sigma = null` khi chưa có phương pháp ước lượng.
- Code nằm trong `src/roadwatch/`, test trong `tests/roadwatch/`. Chạy test bằng `python -m pytest tests/roadwatch --confcutdir=tests/roadwatch`, vì `tests/conftest.py` của template cần các gói không liên quan.
- File model và dữ liệu không commit (`models/`, `data/`, `runs/`, `configs/` của máy chạy đều bị gitignore).

## Sơ đồ file

| File | Trách nhiệm |
|---|---|
| `src/roadwatch/contracts/base.py` | Kiểu `Q`, phần đầu chung của bản ghi, `Strict`/`Lenient`, hàm `normalize` |
| `src/roadwatch/contracts/streams.py` | `FrameMeta`, `SpeedSample`, `Measurement`, `DecisionInput`, `DecisionTrace`, `AlertDecision`, `AudioPlan`, `AudioEvent`, `SystemEvent`, `RunManifest`, `SessionManifest`, `EventLabel` |
| `src/roadwatch/contracts/config.py` | `RwConfig` (các mục có `affects`, biên cứng, validator), `Approval`, `ActivePointer` |
| `src/roadwatch/configstore.py` | Đọc và kiểm tra cấu hình active (dùng cho runtime); đề xuất, duyệt, kích hoạt, quay lui, phục hồi (khoá + compare-and-swap + SQLite, dùng cho HITL) |
| `src/roadwatch/source.py` | Lịch khung theo PTS, bản ghi giữ chỗ, đọc GPS (CSV) thành `SpeedSample` theo `t_fix`/`t_recv` |
| `src/roadwatch/detect.py` | Detector ONNX (xe), tracker hai tầng theo IoU |
| `src/roadwatch/perception.py` | BT-A: `observation`, chọn xe dẫn đầu (`fixed_roi`), danh tính, khoảng cách, TTC, `mount_check` |
| `src/roadwatch/decision.py` | `join`, năng lực, đợt khoảng cách/khẩn cấp (có `HOLD`), lời báo trạng thái, baseline, bộ phân xử audio. Mọi thứ là hàm thuần |
| `src/roadwatch/runtime.py` | Các thread, hàng đợi, tick, nhật ký đầu vào, supervisor, logger, audio sink, `run_manifest` |
| `src/roadwatch/rerun.py` | `rerun-B` và `--verify` trên dữ liệu đã chuẩn hoá |
| `src/roadwatch/evaluate.py` | Khớp nhãn (5.2), các chỉ số theo tầng, báo cáo hiệu năng |
| `src/roadwatch/cli.py` | Lệnh `roadwatch run \| rerun-b \| eval \| hitl …` |
| `scripts/export_detector.py`, `scripts/render_phrases.py` | Công cụ chuẩn bị: xuất model ONNX, render câu nói bằng Piper |

## Task

| # | Task | Sản phẩm và test | AC |
|---|---|---|---|
| T1 | Contracts và fixture | Các model ở 4.0–4.5; fixture hợp lệ và fixture sai (4.6); test: fixture sai bị từ chối, bảng giá trị `null`, `extra=forbid`, bên đọc bỏ qua trường lạ, xuất JSON Schema | M2 |
| T2 | Cấu hình và HITL CLI | `configstore` cùng CLI `hitl`; test: tự duyệt bị chặn, compare-and-swap, báo cáo cũ bị từ chối, `rollback`, phục hồi sau crash ở từng bước, runtime từ chối cấu hình chưa duyệt | M9 |
| T3 | `source` | Lịch "PTS lớn nhất ≤ `s_n`", bản ghi giữ chỗ, GPS với `t_fix`/`t_recv`/độ lệch; test trên video tổng hợp | M1 |
| T4 | `decision` | `join` và độ mới tốc độ; năng lực; các FSM kèm `HOLD` và luật tính lại khi phục hồi; guardrail; baseline; bộ phân xử; test theo kịch bản F1–F17 và test thuộc tính cho guardrail | M5, M7 |
| T5 | BT-A | Detector ONNX, tracker, hình học, TTC, `observation`, `mount_check`; test hình học và TTC trên số liệu tổng hợp; test `phaseCorrelate` với lệch giả lập | M6, M8 |
| T6 | Runtime | Live và replay, tick, nhật ký đầu vào, supervisor, audio sink; test smoke replay xuyên suốt với detector giả, hai lần replay cho ra dữ liệu chuẩn hoá giống nhau | M1, M10 |
| T7 | `rerun-B` và đánh giá | `--verify`; khớp nhãn và chia ba nhóm; recall toàn hệ thống; báo cáo hiệu năng; test trên fixture | M4, M5, M10 |
| T8 | Chuẩn bị model và câu nói; đo trên máy này | Xuất detector ONNX; render WAV; đo năng lực xử lý và latency theo từng khâu trên máy hiện tại | M3, M4 |

**Ngoài tầm của phiên này (cần nhóm làm):** KS-1…KS-6, quay video và GPS, gán nhãn `test_small`, chạy đánh giá chính thức, kiểm chứng khoảng cách, demo (AC-M5, M6, M8 phần dữ liệu thật, M11, M12).
