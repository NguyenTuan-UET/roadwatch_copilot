# AGENTS.md: làm việc trong repo RoadWatch Copilot

Áp dụng cho người và mọi công cụ AI: Claude Code, Codex, Cursor, Gemini CLI, Antigravity, Copilot. `CLAUDE.md` chỉ trỏ tới file này.

**Chỉ dẫn hiện tại của người dùng được ưu tiên hơn file này.** Nếu chỉ dẫn đó khác với quy tắc ở đây hay với spec: nói rõ khác ở đâu và ảnh hưởng gì, rồi làm theo người dùng.

## 1. Phạm vi sản phẩm và ranh giới không được phá

RoadWatch Copilot là trợ lý kèm lái cho tài xế mới trên cao tốc.
- Luồng chính: camera → **BT-A** (CV: khoảng cách, TTC) → **BT-B** (luật và máy trạng thái quyết định cảnh báo) → câu tiếng Việt thu sẵn.
- **BT-C** lo cấu hình có HITL, log và kiểm chứng.
- Chạy offline trên CPU laptop (ONNX Runtime FP32, 4 thread).
- Bản nộp MVP vào cuối tuần 1; tuần 2–4 là phần mở rộng.

**Không được phá** (chi tiết ở spec):
1. **Chỉ cảnh báo.** Không điều khiển xe, không đọc dữ liệu xe (NG1).
2. **Không dùng LLM, LangGraph, RAG hay vector database** trong sản phẩm (ADR-12, NG12).
3. **Đường nóng tất định.** `join`, B, baseline và bộ phân xử audio là hàm thuần: không mạng, không đọc giờ hệ thống, thời gian lấy từ bản ghi (spec 2, 3.3).
4. **Ranh giới.** A và B không import lẫn nhau. Runtime không phụ thuộc công cụ C, web UI hay SQLite ([code-rules](docs/development/code-rules.md), mục 3).
5. **Guardrail Khẩn cấp.** Khi đủ cả ba điều kiện `cap_ttc = on`, TTC `status = ok` và `TTC ≤ ttc_emergency_s`, phát ngay khi bắt đầu đợt hoặc khi cần phát lại theo spec 3.7. Trong cùng đợt, không phát lại nếu đã có lệnh `started` hoặc đang chờ. Không tham số nào được chặn hay hoãn trường hợp bắt buộc phát. Thiếu một điều kiện thì không phát: đó là fail-safe, không phải vi phạm guardrail.
6. **Fail-safe theo từng năng lực.** `cap_distance` và `cap_ttc` độc lập; mỗi năng lực chỉ tắt theo đúng dòng của bảng nguyên nhân ở spec 3.4, không có luật chung kiểu "dữ liệu lỗi thì tắt mọi cảnh báo". Ví dụ:
   - tốc độ `lost` chỉ tắt `cap_distance`; `cap_ttc` không bị ảnh hưởng, vì TTC không dùng tốc độ;
   - tốc độ `stale` không đổi năng lực nào và không sinh câu báo trạng thái; chỉ khung đó không có ngưỡng khoảng cách;
   - một khung đơn lẻ không hợp lệ không đổi năng lực: khung đó không sinh cảnh báo, và đợt có thể sang `HOLD`.

   Câu báo trạng thái đi theo tổ hợp năng lực thực tế, sau debounce `T_notify`; riêng `system_fault` báo ngay.
7. **HITL.** Mọi thay đổi cấu hình đi qua `configstore`: đề xuất → báo cáo → người khác duyệt → kích hoạt.
   - Công cụ AI **không** chạy `approve`, `activate` hay `rollback` trên kho cấu hình thật.
   - Trong test thì dùng kho tạm và được chạy đủ vòng ([code-rules](docs/development/code-rules.md), mục 6).
8. **Hợp đồng dữ liệu.** Thiếu dữ liệu thì ghi `null` kèm `status`, không bao giờ ghi 0. Đổi schema theo [code-rules](docs/development/code-rules.md), mục 9.
9. **Không bịa** số đo thực địa, ngưỡng, hạn nộp hay phê duyệt.

## 2. Nguồn chuẩn

| Nội dung | Nguồn chuẩn |
|---|---|
| Bài toán, phạm vi, lộ trình 4 tuần, nội dung bản nộp MVP | [docs/requirements/](docs/requirements/) (lộ trình ở file 1, mục 10) |
| Tham số lắp đặt, khảo sát thực địa KS-1…KS-6 | [Requirements file 3](docs/requirements/RoadWatch_Copilot_3_Cau_hinh_lap_dat.md) |
| Kiến trúc, ADR, tiêu chí nghiệm thu AC-*, câu hỏi mở OQ-*, tình huống lỗi | [Spec](docs/specs/roadwatch-architecture.md) |
| Hợp đồng dữ liệu | Spec mục 4. Code trong `src/roadwatch/contracts/` phải khớp (package này chưa có trên `main`: spec 12.4) |
| API của server demo (`/api/…`) | Model Pydantic trong `src/roadwatch/schemas.py`; mô tả ở [docs/specs/roadwatch-api.md](docs/specs/roadwatch-api.md) |
| Vận hành và triển khai server demo | [docs/roadwatch-operations.md](docs/roadwatch-operations.md) |
| Quy tắc code và lệnh kiểm tra | [docs/development/code-rules.md](docs/development/code-rules.md) |
| Quy tắc tài liệu và sơ đồ | [docs/development/docs-rules.md](docs/development/docs-rules.md) |
| Sơ đồ: bản trực quan, **không phải** nguồn chuẩn | [docs/architecture_diagram.md](docs/architecture_diagram.md) |

- Nội dung mang nhãn phiên bản đang chờ duyệt (ví dụ `[v1.1]`) chỉ là **đề xuất**: không code theo khi PO chưa duyệt.
- Metadata đầu tài liệu theo [docs-rules](docs/development/docs-rules.md), mục 7: `status` là trạng thái tài liệu, không phải trạng thái triển khai; `archived` chỉ dùng làm lịch sử. Khi đọc một phần spec, lấy luật có hiệu lực cùng ngoại lệ trong mục đó; không dùng phương án cũ trong biên bản làm yêu cầu mới.
- Hợp đồng: đọc spec mục 4 và D-x ở mục 12.3, 12.4. `Measurement` 2.0.0 (spec 4.2) chưa có model Pydantic; bảng ở spec là nguồn duy nhất.

## 3. Điều hướng theo loại task

| Loại task | Đọc | Vùng code | Kiểm tra |
|---|---|---|---|
| BT-A (WP-A*) | Spec 2, 3.1, 3.9, 4.2, 5.7, 12.2 (I-20…I-25) | `src/roadwatch/model.py`, `calibration.py`, `pipeline.py`, `hud.py`, `vendor/` | `tests/roadwatch/test_pipeline.py` |
| BT-B (WP-B*) | Spec 3.3–3.7, 4.3, 4.4, 5.2, 6; requirements file 2 (mục BT-B) | Bản rút gọn `src/roadwatch/decide.py` (spec D-21). Chưa có trên `main`: `src/roadwatch/decision/` | `tests/roadwatch/test_decide.py`. Đi cùng `decision/`: `test_decision.py`, gồm test thuộc tính guardrail |
| Runtime, nguồn dữ liệu (WP-P8, WP-A12) | Spec 2, 3.1–3.3, 3.8, 5.3, 5.4 | Luồng chạy của bản demo: `src/roadwatch/job.py`, `__main__.py`. Chưa có trên `main`: `source.py`, `runtime.py`, `live.py` | `tests/roadwatch/test_job.py`. Đi cùng runtime: `test_source.py`, `test_runtime.py` |
| Cấu hình, HITL, CLI (WP-P3, WP-C2) | Spec 3.10, 4.5 | `config/proposals/v0.yaml`. Chưa có trên `main`: `configread.py`, `configstore.py`, `cli.py` | Đi cùng code: `test_configstore.py`, `test_cli.py`; chỉ dùng kho tạm |
| Đánh giá, `rerun-B` (WP-B8, WP-C4, WP-D6, WP-D12) | Spec 5; requirements file 1, mục 8 | Đánh giá BT-A: `scripts/roadwatch/evaluate.py`. Chưa có trên `main`: `rerun.py`, `evaluate.py` của package | Đi cùng code: `test_rerun_eval.py`; dữ liệu thật theo spec mục 5 |
| Hợp đồng dữ liệu (WP-C3, WP-P4) | Toàn bộ spec mục 4; code-rules mục 9 | Chưa có trên `main`: `src/roadwatch/contracts/` và mọi nơi dùng | Đi cùng code: `test_contracts.py` và toàn bộ test RoadWatch |
| Dữ liệu thực địa, gán nhãn (WP-D*) | Spec 5.1, 5.2; requirements file 3, mục 4 | `data/`, không commit | Theo spec 5.1, 5.2 |
| CI, dependency, Docker (WP-C1, WP-C5) | Code-rules mục 7, 8 | `.github/workflows/`, file dependency | CI xanh |
| Web UI và API demo (WP-C6, WP-C7, WP-C10) | Spec 11.5, 3.10; [docs/specs/roadwatch-api.md](docs/specs/roadwatch-api.md) | `src/roadwatch/web.py`, `schemas.py`, `openapi.json`, `ui/`, `web.html`, `judge.html` | `tests/roadwatch/test_web.py`; kiểm `openapi.json` bằng lệnh ở code-rules mục 8 |
| Tài liệu, sơ đồ | Docs-rules | `docs/` (trừ `docs/guide/`), `README.md`, `ARCHITECTURE.md` | Liên kết, ID, render Mermaid, `git diff --check` |

Phần ghi "chưa có trên `main`" là engine MVP theo spec; code đó ở nhánh `feat/wp-p4-contracts-v1`. Hiện trạng `main` và khác biệt với spec: spec 12.4.

Lệnh chạy test và lint: [code-rules](docs/development/code-rules.md), mục 8.

## 4. Quy trình làm một task

Bảng task và checklist ở `docs/plan/` đã gỡ khỏi repo ngày 09/10/2026 vì không còn khớp code; việc cần làm do người dùng giao trực tiếp. Các bước:

0. **Đồng bộ đầu mỗi phiên, trước khi code hoặc sửa tài liệu.** Làm theo [code-rules](docs/development/code-rules.md), mục 11: kiểm tra nhánh và thay đổi chưa commit, fetch GitHub, đọc thay đổi mới trên nhánh tích hợp rồi cập nhật nhánh làm việc an toàn. Fetch không tự cập nhật file cục bộ. Đọc lại quy tắc và spec liên quan sau đồng bộ; không dùng trí nhớ từ phiên trước thay tài liệu mới. Nếu không fetch được hoặc chưa tích hợp được thay đổi liên quan, báo rõ và dừng phần triển khai phụ thuộc. **Chỉ push nhánh làm việc; không push trực tiếp vào `main` hoặc `master`.**
1. **Nhận việc, trước khi sửa bất cứ gì.** Chỉ làm việc người dùng giao hoặc chỉ định. Phạm vi chưa rõ thì hỏi trước.
2. **Kiểm phụ thuộc.** Nếu việc phụ thuộc một OQ chưa có câu trả lời (spec mục 10) thì dừng lại và báo.
3. **Thực hiện.**
   - Đọc tài liệu theo mục 3.
   - Code theo code-rules (TDD); tài liệu theo docs-rules.
   - Không làm ngoài phạm vi task.
   - Không tạo file Markdown riêng cho từng file code.
4. **Kiểm chứng.** Chạy các lệnh kiểm tra ở [code-rules](docs/development/code-rules.md), mục 8, và nêu rõ phần nào chưa kiểm được.
5. **Bàn giao.**
   - Mở PR theo code-rules mục 11; mô tả PR ghi đã kiểm chứng thế nào và còn thiếu gì.
   - Người viết không tự ghi việc đã xong hay đã nghiệm thu: reviewer xác nhận.
6. **Cuối phiên.** Thêm dòng hoạt động vào `WORKLOG.md`. Không tạo bảng trạng thái ở nơi khác.

## 5. Khi có mâu thuẫn

- **Báo rõ:**
  - nguồn nào nói gì (file và mục);
  - khác nhau ở đâu;
  - ảnh hưởng tới task hay AC nào;
  - đề xuất cách xử lý.
- **Thứ tự tin cậy** khi chưa ai quyết: requirements (phạm vi) và spec (kiến trúc) thắng sơ đồ và file này. Chỉ dẫn hiện tại của người dùng luôn thắng.
- **Không tự quyết thay PO:**
  - Không tự đổi phạm vi.
  - Không tự ghi "PO đã duyệt", "APPROVED", "DONE" hay ✅.
  - Điều cần quyết thì hỏi người dùng, hoặc ghi thành một Open Question.

## 6. AI log (được chấm điểm)

- Mở công cụ AI tại thư mục gốc của repo, để hook tự ghi prompt.
- Không gọi `scripts/log_*` cho các công cụ đã có hook. Với công cụ web thì làm theo `.agents/workflows/log.md`.
- Không sửa `.ai-log/` hay `scripts/log_*`. Không push bằng `--no-verify`.
