# Phân Hệ Đặc Tả Hệ Thống (Specification Hub) — TrafficEye Edge

> **Trọng tâm phát triển:** Spec-Driven Development (Phát triển theo Đặc tả).  
> **Nguyên tắc vàng:** Không bao giờ code khi chưa có bản đặc tả hoàn chỉnh. Mọi module, API và logic đều phải có ID quy chiếu và tiêu chí nghiệm thu (Acceptance Criteria - AC).

---

## 1. Bản Đồ Điều Hướng Đặc Tả (Hub & Spoke Router)

| File con | Bước SDLC | Nội dung chính | Trạng thái |
|---|:---:|---|:---:|
| [01-tong-quan-pham-vi.md](01-tong-quan-pham-vi.md) | Bước 1 | Mục tiêu bài toán, phạm vi MVP/CP1/CP2, phân vai người dùng (Operator, Supervisor, Admin) | 🟡 Duyệt M0 |
| [02-yeu-cau-chuc-nang-edge.md](02-yeu-cau-chuc-nang-edge.md) | Bước 1 | Yêu cầu chức năng Edge: YOLO Detection (FR-DET), ByteTrack (FR-TRK), Đếm xe (FR-DEN), Pha đèn (FR-LGT) | 🟡 Duyệt M0 |
| [03-yeu-cau-chuc-nang-system.md](03-yeu-cau-chuc-nang-system.md) | Bước 1 | Yêu cầu chức năng Hệ thống: Ingest API (FR-ING), Duyệt vi phạm 2 bước HITL (FR-HITL), Web UI (FR-UI), Agent LangGraph (FR-AGT) | 🟡 Duyệt M0 |
| [04-luat-vi-pham-state-machine.md](04-luat-vi-pham-state-machine.md) | Bước 4 | Máy trạng thái 3 luật vi phạm (vượt đèn, sai làn, ngược chiều), logic cắt clip bằng chứng 3-5s, bảo vệ riêng tư (Privacy blur), OCR biển số | 🟡 Chốt M0 |
| [05-false-positives-loc-nhieu.md](05-false-positives-loc-nhieu.md) | Bước 4 | 22 kịch bản chống bắt nhầm (A1–E5): rung camera, bóng đổ, che khuất, bóng đèn phản chiếu, xe ưu tiên rẽ | ✅ Đã duyệt |
| [06-hop-dong-du-lieu-schemas.md](06-hop-dong-du-lieu-schemas.md) | Bước 4 | Schemas cấu hình nút giao YAML (`configs/scenes/*.yaml`), Schema sự kiện JSON Edge-to-Hub, Manifest gói bằng chứng | 🟡 Chốt M0 |
| [07-hop-dong-api-va-giao-tiep.md](07-hop-dong-api-va-giao-tiep.md) | Bước 4 | REST API specs (FastAPI endpoints), SSE real-time stream cho Operator, Kênh điều khiển hai chiều MQTT (Desired State) | 🟡 Chốt M0 |
| [08-dor-dod-checkpoints.md](08-dor-dod-checkpoints.md) | Bước QD/7 | Definition of Ready (DoR), Definition of Done (DoD), Tiêu chí nghiệm thu Checkpoint CP1/CP2 và 11 quyết định kỹ thuật từ PO (Q1–Q11) | ✅ Đã duyệt |

---

## 2. Quy Tắc Quản Trị Đặc Tả

1. **Mọi yêu cầu phải có ID:** `FR-xxx` hoặc `NFR-xxx`. Mỗi task thực thi (`TASK-xxx`) trong `docs/plan/` bắt buộc phải dẫn chiếu ngược về ít nhất 1 ID yêu cầu.
2. **Quy trình thay đổi đặc tả (Change Request):** 
   * Không tự ý sửa đổi hợp đồng API hay Schema đã chốt.
   * Nếu có mâu thuẫn hoặc cải tiến: Lập đề xuất $\rightarrow$ Lead Architect duyệt $\rightarrow$ Nâng phiên bản spec $\rightarrow$ Mới được sửa code.
3. **Liên kết kiến trúc & kiểm thử:**
   * Kiến trúc kỹ thuật và giải thích lựa chọn: xem [docs/arch/](../arch/README.md).
   * Tiêu chuẩn kiểm thử và đo lường Wilson 95%: xem [docs/eval/](../eval/README.md).
   * Phân công và theo dõi tiến độ công việc: xem [docs/plan/](../plan/README.md).
