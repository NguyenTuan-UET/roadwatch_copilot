# Worklog — Team P-014 (RoadWatch Copilot)

> Ghi lại công việc đã làm theo ngày: ai làm gì, kết quả gì.
>
> **Đây là nhật ký, không phải bảng tiến độ.** Cột "Trạng thái" chỉ là ảnh chụp tại ngày ghi. Trạng thái hiện hành, việc còn lại và bước tiếp theo nằm ở [docs/plan/README.md](docs/plan/README.md), mục 4. Cột "Thời gian" để "—" khi không đo.

---

## 2026-09-29

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Claude Code) | WP-P1: soạn bộ tài liệu v1.1 cho nhóm 4 người. Bỏ đề xuất LLM agent theo ADR-12; phân công mới; sơ đồ kiến trúc và sơ đồ phối hợp; quy tắc code, quy tắc tài liệu, quy tắc theo dõi tiến độ | 🟡 chờ PO duyệt | `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/architecture_diagram.md`, `docs/development/`, `docs/plan/`, spec (các phần [v1.1]). **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1: thêm checklist ba nhóm (bàn giao, kiểm thử và kiểm chứng, review và nghiệm thu) cho cả 49 task; plan chỉ còn giữ trạng thái tổng và liên kết | 🟡 chờ PO duyệt | `docs/plan/phan-viec/*.md`, `docs/plan/README.md` (mục 0, 4.3), `AGENTS.md`, code-rules, docs-rules. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1: xử lý 7 phát hiện review. Sửa luật fail-safe, luật bằng chứng AC, giữ kín `test_small` và `test_final`, phụ thuộc WP-P7, nhãn `test_final`. Hai đề xuất hành vi chờ PO: guardrail khi đợt tiếp diễn (OQ-B12), chạy thử cấu hình đề xuất (OQ-B13) | 🟡 chờ PO duyệt | Spec (3.5, 3.7, 3.10, 4.4, 6.2, 10.1, D-8), `AGENTS.md`, code-rules, docs-rules, `docs/architecture_diagram.md`, `docs/plan/`. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1, WP-P2: PO duyệt bộ tài liệu v1.1 và chốt 19 quyết định; hạn nộp MVP 04/10/2026, nén lịch còn N0…N5; OQ-B12 chọn (b), OQ-B13 duyệt; máy demo là laptop của Cương. OQ-A6: sinh lại file Word từ ba file requirements | 🟡 chờ ba reviewer xác nhận | Spec (header, 3.5, 3.7, 3.10, ADR-13, 10, 11.5, 12), `docs/plan/`, `README.md`, `docs/architecture_diagram.md`, `.gitignore`, `docs/requirements/tai_lieu_viet_bao_cao.docx`. **Chưa commit** | — |

**Tổng kết ngày:**
- Bộ tài liệu đã sẵn sàng cho review; danh sách quyết định chờ PO ở `docs/plan/review-v1.1.md`, mục 5.
- Code sản phẩm vẫn tạm dừng.

---

## 2026-09-28

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Claude Code) | Thiết kế kiến trúc và hợp đồng dữ liệu RoadWatch | Spec v1.0 được PO duyệt | `docs/specs/roadwatch-architecture.md`, commit 3f76f09 | — |
| Cương (dùng Claude Code) | Code nền T1–T7 theo kế hoạch ban đầu: contracts, BT-B, kho cấu hình và HITL, source, BT-A, runtime, `rerun-B` và đánh giá | Đã có code và unit test, **chưa nghiệm thu** | Commit 348a6b4…9ba15a3; 104 unit test qua | — |
| Cương (dùng Claude Code) | WP-C2: bắt đầu CLI, viết test trước | 🟡 | `tests/roadwatch/test_cli.py`, **chưa commit** | — |

**Tổng kết ngày:** PO dừng việc viết code để ưu tiên hoàn thiện kiến trúc và tài liệu cho cả nhóm cùng triển khai.

---

<!-- Mỗi phiên làm việc: thêm một block ngày ở trên cùng. Trạng thái hiện hành luôn cập nhật ở docs/plan/README.md, mục 4 và 4.3. -->
