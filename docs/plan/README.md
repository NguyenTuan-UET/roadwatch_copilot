---
doc_id: "RW-PLAN"
doc_type: "plan"
version: "1.1"
status: "approved"
approved_by: "PO"
approved_on: "2026-09-29"
approval_ref: "review-v1.1.md"
authority_for: ["tasks", "task_status", "implementation_status"]
---

# Kế hoạch triển khai RoadWatch Copilot (4 người)

> **Trạng thái: PO duyệt 29/09/2026**, cùng spec v1.1. Code sản phẩm được mở lại. Quyết định của PO: [review-v1.1.md](review-v1.1.md), mục 5. **Hạn nộp MVP: CN 04/10/2026.**

- **File này là nguồn chuẩn cho:** danh mục task (ID, owner, reviewer, phụ thuộc, hạn), **trạng thái tổng** của từng task, và tình trạng code. Đây là bảng tiến độ duy nhất: file phân việc chỉ giữ checklist chi tiết; `WORKLOG.md` chỉ là nhật ký.
- **Nguồn chuẩn của các nội dung khác:** [AGENTS.md](../../AGENTS.md), mục 2.
- **Điều kiện xong, cách kiểm chứng và checklist chi tiết của từng task:** file phân việc của owner (mục 1).
- **Sơ đồ phối hợp, phụ thuộc và đường găng:** [so-do.md](so-do.md). Sơ đồ vẽ theo bảng ở mục 4; nếu khác nhau thì bảng thắng.

## 0. Ký hiệu và luật trạng thái

**Trạng thái:**
- ⬜ chưa bắt đầu.
- 🟡 đang làm, hoặc đã có code hay tài liệu nhưng reviewer chưa kiểm chứng.
- ✅ reviewer đã kiểm đúng theo mục "Kiểm chứng" của task và đánh dấu nhóm "Review và nghiệm thu" trong checklist, kèm bằng chứng.
- ⛔ đang chờ một quyết định (ghi mã OQ).

**Có file hoặc test qua chưa phải là xong.** Mỗi tiêu chí AC-* đạt bằng đúng loại bằng chứng mà spec mục 7 ghi cho nó ([code-rules](../development/code-rules.md), mục 10): có AC chỉ cần pytest trên fixture (AC-M2), có AC cần chạy trên máy demo hoặc trên dữ liệu thực địa (AC-M1, M5, M6). Chỉ reviewer được đổi trạng thái sang ✅, và reviewer luôn khác owner.

**Theo dõi tiến độ trong lúc làm** (người hay AI đều vậy):
1. **Trước khi sửa code hay tài liệu**, xác định ID task và file phân việc chứa task đó. Dùng ID task để nối code, checklist và bằng chứng: đặt ID trong tên nhánh, commit và PR. Không tạo file Markdown riêng cho từng file code.
2. **Checklist chi tiết** nằm dưới từng task trong `phan-viec/<người>.md`, gồm ba nhóm:
   - bàn giao, ghi đường dẫn cụ thể;
   - kiểm thử và kiểm chứng;
   - review và nghiệm thu.

   Mỗi mục là một sản phẩm kiểm chứng được, không phải một thao tác vụn.
3. **Cập nhật ngay** khi xong một file hay một bước, không chờ cuối phiên:
   - Đánh dấu `[x]`, rồi ghi bằng chứng sau dấu `→`: ngày, lệnh và kết quả, commit hoặc link. Nếu chưa commit thì ghi rõ "chưa commit".
   - Mục còn dở vẫn để `[ ]`, và ghi "còn thiếu: …; tiếp theo: …" đủ cụ thể để người hoặc AI khác làm tiếp.
4. **Khi sửa lại phần đã xong**, mở lại các checkbox bị ảnh hưởng (`[ ]`), ghi lý do, rồi kiểm chứng lại.
5. **File này chỉ giữ trạng thái tổng**, không chép checklist:
   - cột TT ở mục 4.1 và 4.2;
   - với mỗi task khác ⬜, một dòng ở mục 4.3 gồm ngày cập nhật, tình hình tóm tắt một dòng, blocker, commit/PR, và liên kết tới checklist.
6. **Xong một file không phải là xong task.** Task giữ 🟡 cho tới khi đạt đủ "Xong khi" và reviewer đã đánh dấu nhóm "Review và nghiệm thu". Chỉ reviewer được chuyển sang ✅.
7. **Cùng một commit hoặc PR:** code, cập nhật checklist, và dòng ở mục 4.3.
8. **Cuối phiên:** kiểm lại dòng ở mục 4.3, rồi thêm dòng hoạt động vào `WORKLOG.md`. WORKLOG không thay cho bảng tiến độ.

**Hạn:**
- N0 là ngày PO duyệt bộ tài liệu. Hạn nộp là 04/10/2026 (OQ-A7), nên tuần 1 chỉ có N0…N5:

  | N0 | N1 | N2 | N3 | N4 | N5 |
  |---|---|---|---|---|---|
  | T3 29/09 | T4 30/09 | T5 01/10 | T6 02/10 | T7 03/10 | CN 04/10: **nộp MVP** |

- Ngày 29/09, PO chốt nén lịch từ N0…N7 xuống N0…N5. Không còn ngày dự phòng; N4, N5 rơi vào cuối tuần. Trễ thì cắt theo mục 5.
- Đây là **hạn nội bộ**, PO sửa được.

**Thuật ngữ dùng chung:**

| Từ | Nghĩa |
|---|---|
| WP-xx | Task. Chữ cái sau `WP-` cho biết phần việc: P = lead/PO, A = BT-A, B = BT-B, C = BT-C, D = dữ liệu và đánh giá. Owner được ghi ở bảng mục 4 |
| AC-M / AC-F | Tiêu chí nghiệm thu của bản nộp MVP (tuần 1) và của phần mở rộng (tuần 4), spec mục 7 |
| OQ-B / M / A / E | Câu hỏi mở, spec mục 10: B chặn triển khai; M cần đo đầu tuần; A chặn nghiệm thu; E chặn phần mở rộng |
| I-x / D-x | Giả định code đang dùng / điểm code chưa khớp spec, spec mục 12 |
| T1…T8 | Các phần code đã viết theo kế hoạch ban đầu (mục 3) |
| `dev`, `test_small`, `test_final` | Các split dữ liệu, tách theo phiên quay (spec 5.1). `test_small` chỉ được chạy đúng một lần |
| HITL | Đổi cấu hình theo quy trình: đề xuất → báo cáo tác động → **người khác** duyệt → kích hoạt |

## 1. Người và vai trò

| Người | Vai trò (spec) | Phụ trách | File phân việc |
|---|---|---|---|
| Cương | PO/Lead + R-C | Kiến trúc, `contracts`, BT-C (cấu hình và HITL, runtime, log, `rerun-B`, CLI), tích hợp, deliverables | [cuong.md](phan-viec/cuong.md) |
| Khánh | R-B | BT-B (luật và máy trạng thái), câu cảnh báo, phương pháp đánh giá hành vi cảnh báo | [khanh.md](phan-viec/khanh.md) |
| Tuấn | R-A, hỗ trợ backend | BT-A (CV, khoảng cách, TTC). Backend: CI và bộ chuyển đổi GPS ở tuần 1; API cho web UI ở tuần 2–4 | [tuan.md](phan-viec/tuan.md) |
| Linh | R-D | Dữ liệu thực địa, gán nhãn, vận hành đánh giá, tổng hợp báo cáo. Web UI chỉ làm từ tuần 2; tuần 1 không có UI | [linh.md](phan-viec/linh.md) |

**Trách nhiệm với số liệu.** Linh tổng hợp `eval/results/report.md`. Mỗi mục trong báo cáo do owner phương pháp xác nhận:

| Mục báo cáo | Owner phương pháp |
|---|---|
| Khoảng cách | Tuấn |
| B so với baseline | Khánh |
| Hiệu năng | Tuấn; riêng `L_alert(B)`: Khánh |
| Tái lập | Cương |
| Phỏng vấn | Linh |

**HITL.** Người đề xuất và người duyệt một thay đổi cấu hình phải khác nhau. Danh sách người được duyệt: WP-P2.

Ai giao sản phẩm gì cho ai: [so-do.md](so-do.md), mục 1.

## 2. Mốc

| Mốc | Nội dung | Task |
|---|---|---|
| N0 | PO duyệt spec v1.1, AGENTS.md và kế hoạch này; mở lại việc viết code | WP-P1 |
| N1 | Đã chọn app GPS | WP-D2 |
| N2 | Có cấu hình khởi tạo đã được duyệt; runtime chạy được trên máy demo với model thật; có dữ liệu thực địa đầu tiên (video cao tốc + GPS + session manifest, KS-2…KS-5) | WP-P3, WP-A1, WP-D3, WP-A2 |
| N3 | Nhãn `test_small` đóng băng; replay bộ dev xong | WP-D4, WP-D12 |
| N5 = 04/10 | **Nộp MVP**; đóng băng `contracts` v1.0 | AC-M1…M12 |
| Tuần 2–4 | Phần mở rộng theo file 1, mục 10 | AC-F1…F5 |

**Đường găng của tuần 1:** WP-D1 → WP-D2 → WP-D3 → (WP-D4, WP-D12) → WP-B3 → WP-D6 → WP-P7 ([so-do.md](so-do.md), mục 2).
- Buổi quay (WP-D3) ở N2 (01/10), gán nhãn và replay ở N3. Nếu buổi quay trễ một ngày thì AC-M5 chỉ còn là "sơ bộ" hoặc "chưa kết luận" (mục 5).
- Nếu tuần 1 chỉ quay được một phiên thì chia split theo khối thời gian liền nhau (spec 5.1), và ghi đây là một giới hạn.

## 3. Hiện trạng code: đã có code, đã kiểm chứng, còn thiếu

Nhánh `feat/roadwatch-mvp`, 8 commit, commit cuối là 9ba15a3.
- **Code đã có trên remote** ở nhánh `cuongnh` (merge f25f575, 29/09), nên cả nhóm đọc được. `main` vẫn là template. PO chốt mở PR vào `main` sau WP-C1 (review-v1.1.md, mục 5, quyết định 2).
- **Kết quả kiểm tra ngày 29/09:**
  - 104 test xanh;
  - `ruff check` sạch trên phần đã commit;
  - `git diff --check` sạch.
- **Test đỏ có chủ đích:** không còn. Từ 30/09, `tests/roadwatch/test_cli.py` đã xanh (WP-C2), nên chạy `pytest tests/roadwatch` không cần `--ignore` nữa: 133 passed, `ruff check src/ tests/` sạch.
- **Kết quả ngày 01/10:** 222 passed, không có test đỏ hay `xfail`; `ruff check src/ tests/ scripts/roadwatch` sạch. Hai test OQ-A5 từng để `xfail` đã xanh sau khi PO chọn thêm luật (spec 3.5 và 10.3).
- **Sau khi đồng bộ `main` (PR #3) và nâng `contracts` lên 1.0.0 (01/10, nhánh `feat/wp-p4-contracts-v1`):** 227 passed; `check_docs` và `export_schemas --check` đạt; `ruff check src/ tests/ scripts/roadwatch` sạch.
- **Kết quả ngày 02/10 (nhánh `feat/wp-p4-contracts-v1`, đã hợp `main` tại `f05eddd`):** 236 passed trên Python 3.13, và trên một venv mới Python 3.11 cài từ `requirements-roadwatch.txt`; `ruff check`, `check_docs`, `export_schemas --check` đạt. Mọi lần chạy đều trên Windows; chưa có lần nào trên Linux hay trên GitHub.
- **Sau khi thêm hợp đồng 1.1.0 và bộ WAV (02/10, cùng nhánh):** 242 passed trên Python 3.13 và trên một venv mới Python 3.11 cài từ `requirements-roadwatch.txt`; `ruff check`, `check_docs`, `export_schemas --check` đạt. `ruff format --check` còn báo 6 file, đều đã chưa định dạng từ `main`. Chạy tay job template sau khi sửa `ci.yml`: 5 passed. Mọi lần chạy đều trên Windows; hai workflow chưa chạy trên GitHub với các thay đổi này.

| Mã | Phần | Commit | Đã kiểm chứng bằng | Chưa kiểm chứng, còn thiếu | Task tiếp nhận |
|---|---|---|---|---|---|
| T1 | `contracts` v0.1 | 348a6b4 | 23 unit test: luật `Q`, bảng `null`, `extra=forbid`, `seq`, `normalize`, biên cứng của cấu hình | Từ 30/09 có fixture JSONL và kiểm tra liên luồng D-7 (WP-C3, chưa review); từ 01/10 `contracts` 1.0.0, thêm `audio.phrases_sha256` và `provisional_keys` cấp gốc (WP-P4, chưa review); từ 02/10 `contracts` 1.1.0 với `risk_objects` và `lane` (WP-C11, chưa review); chưa gắn thẻ `contracts-v1.0` | WP-C3, WP-P4 |
| T2 | Kho cấu hình + HITL (lõi) | 22f9da9 | 16 unit test: tự duyệt bị chặn, compare-and-swap, phục hồi sau crash, khoá | CLI đủ lệnh từ 30/09, gồm `--proposed` (D-8) và chặn `test_*` (D-11), chưa review; chưa chạy trọn vòng AC-M9 trên máy demo | WP-C2, WP-P3 |
| T3 | `source` | 2d6fbbd | 4 unit test trên video tổng hợp | GPS thật; bộ chuyển đổi (I-15) | WP-A12, WP-P8 |
| T4 | BT-B `decision/` | 439efd2 | 27 unit test, gồm test thuộc tính guardrail; đã thử cố ý làm hỏng luật an toàn để chắc test bắt được | Chưa ai ngoài người viết đọc lại; chưa chạy trên dữ liệu thật. Từ 01/10 (commit `1325e86`, chưa review): phương án (b) của OQ-B12, kịch bản S1–S7, fixture F1–F18, sửa D-14, D-15, I-16, và luật "`HOLD` khi đợt đang rời" theo quyết định OQ-A5; 85 test. I-12, I-13: có đề xuất, PO chưa quyết | WP-B0, WP-B9, WP-B3 |
| T5 | BT-A `detect.py`, `perception.py` | 3822f7c | 15 unit test trên số liệu tổng hợp | Model thật, clip thật, mọi ngưỡng (I-4…I-10); D-10 | WP-A0, WP-A1…A5 |
| T6 | Runtime replay/live | 53eebba | 5 test: replay với detector giả, tái lập, live bị crash | Máy demo, audio thật; `t_infer_end` (D-6); D-13 (runtime import cả module `configstore`) đã tách ngày 01/10 sang `configread.py`, commit `85c58ca`, chưa review. `--proposed` (D-8) có từ 30/09, chưa review | WP-P8, WP-A6, WP-C2 |
| T7 | `rerun-B`, khớp nhãn, latency | 9ba15a3 | 11 unit test trên fixture | Chưa chạy trên nhãn thật. Từ 01/10 (commit `87b0814`, chưa review): loại phiên GPS kém và sổ `test_runs.jsonl` (D-9), đủ mục báo cáo của spec 5.5 (D-18), công cụ quét `scripts/roadwatch/sweep_b.py`; 33 test | WP-B8, WP-C4 |
| T8 | Model ONNX, file WAV, số đo hiệu năng | — | — | Model ONNX và số đo hiệu năng: chưa làm. File WAV: từ 01/10 có script render (WP-B2, commit `85c58ca`); 02/10 đã render bộ nháp bằng Piper 1.8.0 trên máy phát triển (không commit; độ dài và hash ở `config/proposals/v0.yaml`) | WP-A1, WP-B2, WP-A6 |

Không task nào dưới đây viết lại T1–T7. Task tiếp nhận chỉ đọc, đối chiếu với spec, rồi sửa những chỗ lệch mà PO đã quyết (OQ-A10).

## 4. Danh mục task

### 4.1 Tuần 1 (bản nộp MVP)

| ID | Việc | Owner | Reviewer | Cần có | Hạn | TT |
|---|---|---|---|---|---|---|
| WP-P1 | Duyệt spec v1.1, AGENTS.md, kế hoạch; quyết I-x, D-x (OQ-A10) | Cương | Khánh, Tuấn, Linh (mỗi người đọc phần của mình) | — | N0 | 🟡 |
| WP-P2 | Danh sách người duyệt HITL; chọn máy demo (OQ-B6, OQ-B7) | Cương | Tuấn | WP-P1 | N0 | 🟡 |
| WP-A0 | Tiếp nhận code BT-A (T5) | Tuấn | Cương | WP-P1 | N1 | ⬜ |
| WP-B0 | Tiếp nhận code BT-B (T4); đề xuất cách xử lý I-12, I-13 | Khánh | Cương | WP-P1 | N1 | 🟡 |
| WP-B1 | Bảng pháp lý và tham số B cho cấu hình v0 (OQ-B2 phần B, OQ-B4) | Khánh | Cương | — | N1 | 🟡 |
| WP-C1 | Dependency và job CI cho RoadWatch | Tuấn | Cương | — | N1 | 🟡 |
| WP-D1 | KS-1 (xe, thiết bị quay); quy trình quay; checklist lắp đặt | Linh | Tuấn | — | N1 | ⬜ |
| WP-A1 | Xuất detector ONNX; đo ONNX Runtime 4 thread trên máy demo | Tuấn | Cương | WP-P2 | N2 | ⬜ |
| WP-B2 | Câu nói tiếng Việt (OQ-B5); render WAV | Khánh | Linh | WP-B1 | N2 | 🟡 |
| WP-P3 | Ghép cấu hình v0 và cho duyệt lần đầu (OQ-B3) | Cương | Khánh (người duyệt HITL) | WP-B1, WP-A1, WP-P2 | N2 | 🟡 |
| WP-D2 | Chọn app GPS (OQ-M4); file GPS mẫu; quy trình đo độ lệch và độ bất định đồng bộ, thử trên một lần ghi | Linh | Cương | WP-D1 | N1 | ⬜ |
| WP-C2 | CLI đầy đủ; `--proposed` cho replay và live (D-8); `run_stats`; chặn split `test_*` khi làm báo cáo (D-11) | Cương | Tuấn | WP-P2 (chỉ cho `hitl init`) | N2 | 🟡 |
| WP-A2 | Hiệu chỉnh camera (KS-5); chân trời và góc lắp (KS-4) | Tuấn | Cương | WP-D1, WP-P3 | N2 | ⬜ |
| WP-A12 | Bộ chuyển đổi file của app GPS sang CSV chuẩn (I-15) | Tuấn | Linh | WP-D2 | N2 | ⬜ |
| WP-D3 | Quay ≥ 2 phiên cao tốc; session manifest cho mỗi phiên; KS-2, KS-3; script kiểm phiên chỉ in metadata | Linh | Tuấn (phiên `dev`, ảnh KS), Cương (phiên `test_small`, chỉ metadata) | WP-D1, WP-D2 | N2 | ⬜ |
| WP-B8 | Phương pháp đánh giá hành vi cảnh báo; đề xuất τ, `lead_max`, `max_late` (OQ-A3) | Khánh | Cương | WP-B0 | N2 | 🟡 |
| WP-P6 | Chốt với mentor: OQ-A1, OQ-A2, OQ-A11 | Cương | Khánh | — | N2 | ⬜ |
| WP-D5 | KS-6: clip xe đứng yên ở khoảng cách đo bằng thước | Linh | Tuấn | WP-D1 | N3 | ⬜ |
| WP-A3 | Kiểm chứng kiểm tra lắp đặt; chốt ngưỡng trước khi thử (OQ-M3) | Tuấn | Cương | WP-D3, WP-D5 | N3 | ⬜ |
| WP-C3 | Fixture JSONL và kiểm tra liên luồng (D-7) | Cương | Khánh | — | N3 | 🟡 |
| WP-B9 | Fixture F1–F16 cho B; test OQ-A5; kịch bản guardrail S1–S7 (phần B của AC-M7) | Khánh | Cương | WP-B0 | N3 | 🟡 |
| WP-A4 | Tinh chỉnh perception trên clip dev (I-4, I-6, I-8, I-10) | Tuấn | Khánh | WP-D3, WP-A1, WP-A2 | N3 | ⬜ |
| WP-A5 | Kiểm chứng khoảng cách: hình học và đầu ra của A (AC-M6) | Tuấn | Cương | WP-D5, WP-A1, WP-A2 | N3 | ⬜ |
| WP-D4 | Hướng dẫn gán nhãn; gán nhãn `dev`, rồi `test_small`, đóng băng | Linh | Khánh (hướng dẫn và mẫu nhãn `dev`) | WP-D3, WP-B8 | N3 | ⬜ |
| WP-D12 | Chạy replay bộ `dev` với cấu hình active; giao các lần chạy cho WP-B3 | Linh | Tuấn | WP-D3, WP-A12, WP-A4 | N3 | ⬜ |
| WP-C4 | Loại phiên GPS kém; ghi `eval/test_runs.jsonl` (D-9) | Khánh | Linh | — | N3 | 🟡 |
| WP-B3 | Tinh chỉnh B bằng `rerun-B` trên `dev`; đề xuất HITL | Khánh | Cương (người duyệt HITL) | WP-D4, WP-D12, WP-B8 | N4 | 🟡 |
| WP-A6 | Throughput, latency; kiểm tra live F1 và F18 (AC-M3, M4, phần live của M7) | Tuấn | Khánh | WP-D3, WP-A12, WP-A1, WP-B2, WP-C2, WP-P3 | N4 | ⬜ |
| WP-P8 | Tích hợp đầu–cuối trên máy demo khi đã tắt mạng; kiểm tái lập (AC-M1, M10) | Cương | Tuấn | WP-D3, WP-A12, WP-A1, WP-B2, WP-P3 | N4 | 🟡 |
| WP-D6 | Chạy `test_small` đúng một lần; tổng hợp `eval/results/report.md` | Linh | Cương | WP-D4, WP-B3, WP-A5, WP-A6, WP-C4 | N5 | ⬜ |
| WP-P4 | Đóng băng `contracts` v1.0 (AC-M2) | Cương | Khánh, Tuấn | WP-C3, WP-B9 | N5 | 🟡 |
| WP-P7 | Danh sách giới hạn đã biết; buổi demo MVP (AC-M11, M12) | Cương | Linh | WP-D6, WP-P8, WP-P4, WP-B9, WP-A3, WP-A6, WP-C2 | N5 | ⬜ |
| WP-P5 | WORKLOG, JOURNAL tuần 1; README hoàn chỉnh, pitch deck, video demo ở tuần 2–4 (deliverables 2, 6, 7) | Cương (mỗi người tự ghi WORKLOG) | Linh (tuần 1), Khánh (deliverables tuần 2–4) | — | Liên tục, tuần 1–4 | 🟡 |
| WP-D7 | Phỏng vấn người mới lái, người mới đổi xe (chuẩn bị ở tuần 1) | Linh | Khánh | — | Tuần 1–2, không chặn MVP | ⬜ |

### 4.2 Tuần 2–4 (mở rộng)

| ID | Việc | Owner | Reviewer | Cần có | TT |
|---|---|---|---|---|---|
| WP-A7 | Lọc Kalman; `sigma_m` | Tuấn | Khánh | WP-A5 | ⬜ |
| WP-A8 | Vạch làn; `lead.basis = lane_markings`; `lateral_offset_m` | Tuấn | Cương | WP-A4 | ⬜ |
| WP-A9 | Bằng chứng chen làn (ADR-09) | Tuấn | Khánh | WP-A8 | ⬜ |
| WP-A10 | Kiểm chứng phạm vi áp dụng trên xe thử 2 (AC-F1); KITTI/DDAD nếu còn thời gian | Tuấn | Cương | WP-D10 | ⬜ |
| WP-A11 | ByteTrack đầy đủ, chỉ làm nếu lỗi đổi ID chiếm phần lớn sai số | Tuấn | Cương | WP-A4 | ⬜ |
| WP-B6 | Nhắc sớm theo xu hướng; ân hạn khi bị chen; ùn tắc; chế độ người mới (AC-F4) | Khánh | Cương | WP-A9 (cho ân hạn) | ⬜ |
| WP-B7 | Chốt `remind_interval` và ngưỡng `perceived_delay` sau thử nghe (OQ-A8) | Khánh | Linh | WP-D9 | ⬜ |
| WP-C5 | Docker, `.env.example`, logging (DevOps) | Cương | Tuấn | WP-C2 | ⬜ |
| WP-C10 | API FastAPI cho web UI; đăng nhập 2 vai trò | Tuấn | Cương | WP-C2 | ⬜ |
| WP-C11 | Hợp đồng và điểm nối cho Người và Làn: `contracts` 1.1.0, phiên mẫu đủ xe, người, làn (chuẩn bị ngay ở tuần 1 theo yêu cầu của PO ngày 02/10) | Cương | Khánh, Tuấn (đề xuất, như WP-P4; chờ PO xác nhận) | WP-P4 | 🟡 |
| WP-C6 | Màn hình kỹ sư: danh sách lần chạy, B so với baseline, trace, HITL (AC-F5) | Linh | Cương | WP-C10 | ⬜ |
| WP-C7 | Màn hình trạng thái cho tài xế, đọc `heartbeat.json` (AC-F5) | Linh | Khánh | WP-C10 | ⬜ |
| WP-C9 | Live URL, chỉ khi PO chọn deploy | Cương | Tuấn | OQ-E1 | ⛔ OQ-E1 |
| WP-D9 | Tổ chức thử nghe với người mới lái | Linh | Khánh | WP-B2 | ⬜ |
| WP-D10 | Quay các phiên cho `test_final` và cho xe thử 2; gán nhãn mù `test_final`, kiểm bằng `EventLabel`, đóng băng bằng hash | Linh | Tuấn (dữ liệu xe thử 2), Cương (`test_final`, chỉ metadata) | WP-D1, WP-D4 | ⬜ |
| WP-D11 | Đánh giá cuối và báo cáo cuối (deliverable 10), chấm trên nhãn `test_final` đã đóng băng | Linh | Cương | WP-D10 (nhãn `test_final` đã đóng băng) | ⬜ |

**ID đã bỏ:** WP-B4, WP-B5, WP-C8 và WP-D8. Đây là các task của Engineer Copilot, bị bỏ theo ADR-12. Các ID này không được dùng lại.

**Phần mở rộng Người và Làn** (PO nêu ngày 02/10/2026) gồm ba nhóm việc. Trạng thái của nhóm này không suy ra trạng thái của nhóm kia:
1. **Hoàn thiện MVP B+C:** WP-P3, WP-P4, WP-P8, WP-C1, WP-C2, WP-B2 (mục 4.3).
2. **Chuẩn bị hợp đồng và điểm nối cho tuần 2–4:** WP-C11. Chỉ gồm dữ liệu: A ghi gì; B và C đọc, kiểm, ghi log và chạy lại thế nào. Không có cảnh báo mới nào được bật.
3. **Nghiệp vụ chưa được PO quyết:** luật cảnh báo va chạm với người hoặc xe trong vùng rủi ro (OQ-A13), luật cảnh báo lệch làn (OQ-A14), phiên bản hợp đồng khi bật cảnh báo mới (OQ-A15), cách nối A (OQ-A12), văn bản câu nói (OQ-B5). Chưa có task cho: A xuất `risk_objects` và `lane`; luật của B; dữ liệu và nhãn cho hai loại cảnh báo này. PO giao task sau khi quyết.

### 4.3 Tiến độ các task không còn ⬜

Mỗi task một dòng. Chi tiết từng sản phẩm, bằng chứng và bước tiếp theo nằm ở checklist của task trong file phân việc.

| ID | Cập nhật | Tình hình | Blocker | Commit/PR | Checklist |
|---|---|---|---|---|---|
| WP-P1 | 01/10/2026 | PO duyệt bộ tài liệu v1.1 và chốt 19 quyết định; bổ sung quy tắc fetch đầu phiên và chỉ push nhánh task (chưa commit). Đã kiểm tra origin/main tại b6e560a; còn đồng bộ PR #3 sau khi xử lý việc dở. Review PR #3 phát hiện P2 trong kiểm ID task; xem checklist | Ba reviewer chưa ghi xác nhận vào `WORKLOG.md` | 8943c1c, 4ed1285 (nhánh `cuongnh`) | [cuong.md: WP-P1](phan-viec/cuong.md) |
| WP-P5 | 29/09/2026 | Đã ghi `WORKLOG.md` cho 28/09 và 29/09; `JOURNAL.md` tuần 1 chưa viết | — | 8943c1c, 4ed1285 | [cuong.md: WP-P5](phan-viec/cuong.md) |
| WP-P2 | 30/09/2026 | Đã chốt: máy demo là laptop của Khánh (PO đổi 30/09); cả bốn người là người duyệt (OQ-B6, OQ-B7) | Chưa tạo `roles.json` trên máy demo | 4ed1285 | [cuong.md: WP-P2](phan-viec/cuong.md) |
| WP-C2 | 02/10/2026 | Đủ mọi mục bàn giao: `cli.py` (thêm `check-run`, `compare`), D-8, D-11, `run_stats.json` (PO chốt nội dung 30/09); phần pytest của AC-M9 đạt. 01/10 (commit `85c58ca`): tách phần đọc cấu hình sang `configread.py`, runtime không còn nạp SQLite (D-13). 02/10: `run --measurements` và `--audio` cho bàn giao B+C (WP-P8) | Tuấn review; vòng AC-M9 trên máy demo cần `roles.json` (WP-P2) và cấu hình v0 (WP-P3) | Nhánh `feat/wp-c2-c3-cli-fixtures`; D-13 ở `85c58ca` | [cuong.md: WP-C2](phan-viec/cuong.md) |
| WP-C3 | 30/09/2026 | 2 fixture hợp lệ (replay, live) và 12 fixture sai phủ 9 schema luồng; `check_streams` kiểm liên luồng (D-7) | Khánh review; CI chưa chạy test RoadWatch (WP-C1) | Nhánh `feat/wp-c2-c3-cli-fixtures` | [cuong.md: WP-C3](phan-viec/cuong.md) |
| WP-P4 | 01/10/2026 | Đã đồng bộ `main` (PR #3). `contracts` ở 1.0.0 (PO quyết nâng ngay); thêm `audio.phrases_sha256` (D-16) và `provisional_keys` cấp gốc (D-17); spec 4.4, 4.5 sửa theo code (D-4, D-19); fixture và snapshot schema sinh lại; 227 test đạt | Khánh và Tuấn xác nhận code A, B đọc ghi được 1.0.0, rồi mới gắn thẻ `contracts-v1.0`. Code BT-A trên `origin/tuannq` chưa dùng `contracts`. PO xác nhận D-19. Từ 02/10 code đã ở 1.1.0 (WP-C11): gắn thẻ ở phiên bản nào là việc PO quyết (OQ-A15) | Nhánh `feat/wp-p4-contracts-v1` | [cuong.md: WP-P4](phan-viec/cuong.md) |
| WP-P3 | 02/10/2026 | `config/proposals/v0.yaml` là mẫu đủ mọi mục: phần B giữ nguyên; mục `audio` ghi độ dài và hash của bộ WAV nháp; giá trị do A cung cấp và đường dẫn theo máy là `null` kèm nhãn `TODO(A)`, `TODO(machine)`; `hitl propose` từ chối file chưa điền (có test). Cấu hình đầy đủ chỉ để chạy fixture nằm riêng ở `tests/roadwatch/fixtures/handoff/test-config.yaml` | Giá trị của A (WP-A1, WP-A4), số đo KS-2…KS-5, `roles.json` trên máy demo (WP-P2). Chưa có phê duyệt nào trên kho thật | `f30174b`, `b29ba35`, `6536665` | [cuong.md: WP-P3](phan-viec/cuong.md) |
| WP-P8 | 02/10/2026 | Làm phần không phụ thuộc dữ liệu thật, theo yêu cầu bàn giao B+C của PO ngày 02/10. **Code đã có và test bằng dữ liệu mẫu:** `run --measurements` nhận đầu ra A giao sẵn (đọc file; replay và live), `--audio speaker\|simulated`, phiên mẫu có đủ xe, người và làn, `tests/roadwatch/test_handoff.py`, hướng dẫn ở `README.md`. Trên máy phát triển, `live` với bộ WAV nháp gọi bộ phát `winsound` cho đủ năm cảnh báo, không lỗi. **Chưa kiểm chứng:** máy demo, A thật, người nghe xác nhận âm thanh, `aplay` trên Linux, chế độ máy bay. **Chưa đánh giá:** chất lượng trên dữ liệu thực địa | WP-D3, WP-A12, WP-A1, WP-P3 chưa xong; OQ-A12 (cách nối package A hiện có) | `f30174b`, `0e2df5a`, `e1c4cfb`, `b29ba35` | [cuong.md: WP-P8](phan-viec/cuong.md) |
| WP-C1 | 02/10/2026 | Cương làm thay theo yêu cầu của PO ngày 02/10: `requirements-roadwatch.txt`, `.github/workflows/roadwatch.yml`; `ci.yml` của template bỏ `tests/roadwatch` khỏi phần thu thập test. Chạy tay từng bước của hai job trên Windows, Python 3.11, venv mới: job RoadWatch đạt; job template đạt 5 test (trước khi sửa: 8 lỗi thu thập vì thiếu `cv2`) | Hai workflow chưa chạy trên GitHub với các thay đổi này (nhánh chưa push) và chưa chạy trên Linux. Người làm đang là reviewer theo bảng 4.1: cần reviewer khác | `f30174b`, `483d20f` | [tuan.md: WP-C1](phan-viec/tuan.md) |
| WP-C11 | 02/10/2026 | `contracts` 1.1.0: `Measurement.risk_objects` (xe khác và người: danh tính, loại, vùng rủi ro, khoảng cách, TTC) và `Measurement.lane` (`LaneState`), đều tuỳ chọn. B và runtime chưa đọc hai trường: dữ liệu được kiểm, ghi log, chạy lại được, và không sinh cảnh báo (test so với file 1.0.0). Thứ tự ưu tiên audio đề xuất ở spec 3.6 | Luật cảnh báo chờ PO: OQ-A13, OQ-A14, OQ-A15. Chưa có task cho A xuất hai trường này. R-A cần xác nhận đo được `left_m`, `right_m` theo mét. Reviewer đề xuất là Khánh và Tuấn, chờ PO xác nhận | `b29ba35` | [cuong.md: WP-C11](phan-viec/cuong.md) |
| WP-C9 | 29/09/2026 | Chưa làm | OQ-E1 | — | [cuong.md: WP-C9](phan-viec/cuong.md) |
| WP-B0 | 01/10/2026 | PO chỉ định Cương làm thay Khánh từ 01/10. Đã đọc lại code B và đối chiếu spec 3.3–3.7 với test; đề xuất cho I-12, I-13 và 9 điểm mới (I-16…I-19, D-14…D-18) ghi ở spec mục 12 | PO chưa chỉ định reviewer mới (bảng 4.1 đang ghi Cương); bảng đối chiếu chờ mở PR | `1325e86`, nhánh `feat/wp-b0-b9-c4-decision-eval` | [khanh.md: WP-B0](phan-viec/khanh.md) |
| WP-B1 | 01/10/2026 | Phần B của `config/proposals/v0.yaml` theo TT 38/2024, Điều 11; sửa cách tra bảng ở các biên tốc độ (I-16); đề xuất trả lời OQ-B4. Giá trị tạm của phần B nằm ở `provisional_keys` (D-17, PO quyết 01/10, làm ở WP-P4) | PO quyết OQ-B4 (dòng V = 60); reviewer đối chiếu văn bản gốc; chưa có reviewer mới | `1325e86` | [khanh.md: WP-B1](phan-viec/khanh.md) |
| WP-B2 | 02/10/2026 | Tám câu đã render bằng `piper-tts` 1.8.0 với giọng `vi_VN-vais1000-medium` (bộ nháp: văn bản chờ OQ-B5); độ dài và hash đo từ WAV, ghi ở `config/proposals/v0.yaml`; `MANIFEST.json` ghi nguồn và giấy phép; hai câu nháp cho Người đi bộ và Lệch làn nằm riêng ở `draft/`. Loa là `winsound` (Windows) hoặc `aplay` (Linux); không có bộ phát thì từ chối chạy. Trên máy phát triển bộ phát được gọi không lỗi cho cả tám câu | PO duyệt văn bản câu (OQ-B5). **Chưa có người nghe xác nhận.** `aplay` chưa thử trên Linux. WAV không nằm trong Git: bàn giao bằng gói zip | `85c58ca`, `f30174b`, `6536665` | [khanh.md: WP-B2](phan-viec/khanh.md) |
| WP-B8 | 01/10/2026 | OQ-A3: PO cho dùng τ 0,5; `lead_max` 3,0 s; `max_late` 2,0 s trên `dev` (01/10). `eval` có đủ mục của spec 5.5 và chấm được kết quả `rerun-B`; khung mục 6 của `eval/results/report.md` | Giá trị OQ-A3 cho `test_small` chưa chốt (cần số liệu `dev`); chưa có reviewer mới | `87b0814` | [khanh.md: WP-B8](phan-viec/khanh.md) |
| WP-B9 | 01/10/2026 | Phương án (b) của OQ-B12, kịch bản S1–S7, 15 fixture F1–F18; sửa D-14 và D-15. OQ-A5: test cho thấy luật cũ không có giới hạn trên; PO chọn thêm luật (01/10), đã sửa `episodes.py` và spec 3.5 | Chưa có reviewer mới | `1325e86` | [khanh.md: WP-B9](phan-viec/khanh.md) |
| WP-C4 | 01/10/2026 | `eval --sessions` loại phiên GPS kém và phiên tốc độ giả lập khỏi chỉ số chính; lệnh `run` ghi `eval/test_runs.jsonl`; `rerun-b` từ chối cấu hình khác trên lần chạy `test_*` | Linh review | `87b0814` | [khanh.md: WP-C4](phan-viec/khanh.md) |
| WP-B3 | 01/10/2026 | Mới có công cụ quét `scripts/roadwatch/sweep_b.py`; chưa quét gì | Chờ nhãn `dev` (WP-D4), lần chạy `dev` (WP-D12) và OQ-A3. Người duyệt HITL phải khác người đề xuất | `87b0814` (công cụ quét) | [khanh.md: WP-B3](phan-viec/khanh.md) |

## 5. Tải công việc tuần 1 (ước lượng thô, người-ngày)

| Người | Tổng tải | Gồm (cộng thêm ~1 cho review) | Nhận xét |
|---|---|---|---|
| Cương | ~7 | P1–P4, P6–P8: ~3,5 · C2, C3: ~2 · review: ~1,5 | **Cao nhất.** Đã chuyển WP-C1 và WP-A12 cho Tuấn, WP-C4 cho Khánh. README hoàn chỉnh, pitch và video dời sang tuần 2–4, vì file 1 mục 10 không đòi ở bản nộp MVP |
| Tuấn | ~6,5 | A0–A6, A12, C1 | Nặng ở N3–N5, khi có dữ liệu thực địa. N0–N2 còn trống nên nhận CI và bộ chuyển đổi GPS |
| Khánh | ~6,5 | B0–B3, B8, B9, C4 | Cân đối |
| Linh | ~6,5 | D1–D6, D12 | Đã dời phỏng vấn (WP-D7) sang tuần 1–2 và chuyển bộ chuyển đổi GPS cho Tuấn. Tuần 1 không có UI |

**Buổi thực địa** (WP-D3, WP-D5, WP-A2, WP-A3):
- Cần tối thiểu một người lái và một người thao tác thiết bị; người lái không đụng vào thiết bị.
- Linh điều phối buổi thực địa. Tuấn có mặt để làm KS-4 và thử làm lệch camera (WP-A3), cùng buổi với WP-D5.
- Người lái được xác định ở KS-1.

Cả nhóm đang ở sát giới hạn tải. Các số trên ước lượng cho 8 ngày (N0…N7). Lịch nay chỉ còn N0…N5, nên ai cũng vượt tải. Chỗ nào không kịp thì cắt theo thứ tự dưới đây, không kéo dài hạn.

**Thứ tự cắt khi trễ (PO duyệt 29/09).** Thứ tự này chỉ dùng những lối lùi mà spec đã cho phép:
1. WP-A3: tắt `mount_check` bằng cờ, ghi AC-M8 là "chưa đạt" (ADR-05).
2. WP-A6: nếu n < 200 thì AC-M4 ghi "chưa kết luận" (spec 5.6).
3. WP-A5: chỉ công bố các dải có mẫu; dải còn lại ghi "chưa kiểm chứng" (spec 5.7).
4. WP-D6: nếu có quá ít sự kiện thì AC-M5 ghi "sơ bộ" (spec 5.5).

Không cắt AC-M1, M2, M7, M9, M11, M12: đây là phần an toàn, hợp đồng dữ liệu và HITL.

## 6. Nhịp làm việc

- **Trong và sau mỗi phiên:** cập nhật checklist ngay khi xong từng mục; cập nhật TT và mục 4.3 theo luật ở mục 0; thêm dòng hoạt động vào `WORKLOG.md`. Trạng thái ✅ chỉ reviewer được đặt.
- **Mỗi tuần:** PO tổng hợp `JOURNAL.md`.
- **Nhánh, PR, review** theo [code-rules](../development/code-rules.md), mục 11. Thay đổi đụng tới `contracts` hoặc spec thì PO duyệt.
- **Khi đổi owner, reviewer hay phụ thuộc:** sửa bảng ở mục 4, rồi cập nhật [so-do.md](so-do.md) và sơ đồ trong file phân việc trong cùng commit.
- **Lịch sử:** file [2026-09-28-roadwatch-mvp-plan.md](2026-09-28-roadwatch-mvp-plan.md) là kế hoạch ban đầu dùng để viết T1–T8.
