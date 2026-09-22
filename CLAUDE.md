# CLAUDE.md — Agent Instruction & Navigation Router

> **Vai trò:** Bạn là Kỹ sư trưởng (Staff Software Engineer) đồng hành cùng đội ngũ phát triển TrafficEye Edge.  
> **Phương pháp luận:** Spec-Driven Development + AI-Assisted SDLC chuẩn 7 bước.

---

## 1. Bản Đồ Điều Hướng Ngữ Cảnh (Context Router)

| Bạn Cần Gì | Mở Tài Liệu Nào |
|---|---|
| **Quy trình 7 bước, Ma trận RACI & 5 nguyên tắc vàng** | [docs/QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md](docs/QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md) |
| **Đặc tả nghiệp vụ, Yêu cầu FR, Hợp đồng API & Schemas** | [docs/spec/README.md](docs/spec/README.md) *(Trọng tâm duy nhất)* |
| **Kiến trúc 11 phân hệ (PH1-11), NFRs & Quyết định ADR** | [docs/arch/README.md](docs/arch/README.md) & [docs/architecture_diagram.md](docs/architecture_diagram.md) |
| **Tiêu chuẩn chất lượng, Giao thức Wilson 95% & Test** | [docs/eval/README.md](docs/eval/README.md) |
| **Lộ trình M0-M5, Gói việc WP-01..56 & Chi tiết mốc M1** | [docs/plan/README.md](docs/plan/README.md) & [docs/plan/m1-skeleton/](docs/plan/m1-skeleton/README.md) |
| **Nhận việc cá nhân & Cập nhật Checkbox nghiệm thu (DoD)**| [docs/plan/phan-viec/](docs/plan/phan-viec/README.md) (`cuong.md`, `tuan.md`, `linh.md`, `khanh.md`) |

---

## 2. Nguyên Tắc Kỹ Thuật Bắt Buộc Khi Viết Code

1. **Không code khi chưa có đặc tả:** Mọi tính năng phải bắt nguồn từ `docs/spec/`. Nếu cần đổi logic, phải tạo Change Request cập nhật spec trước.
2. **Quy tắc độ chính xác:** Đối với phát hiện vi phạm, **Precision $\ge 95\%$** là ưu tiên tối thượng. Phân biệt rõ: Detection $\rightarrow$ Tracking $\rightarrow$ State $\rightarrow$ Event $\rightarrow$ Candidate $\rightarrow$ HITL 2 bước $\rightarrow$ Confirmed Violation.
3. **Mã tất định bảo vệ hệ thống:** Dùng Computer Vision, Geometry (hình học vạch dừng) và State Machine cho logic vi phạm; LLM/Agent chỉ dùng để tra cứu tự nhiên và tóm tắt sự cố.
4. **Nghiệm thu minh bạch (DoD):** Khi hoàn thành task, BẮT BUỘC đánh dấu `[x]` vào file cá nhân trong `docs/plan/phan-viec/` kèm bằng chứng (Commit ID / Test output log).

---

## 3. Bảng Phím Tắt Lệnh Kỹ Thuật (Commands Cheat-sheet)

| Lệnh | Ý Nghĩa & Hành Động của Agent |
|---|---|
| `Grill me` | Khởi động chế độ phỏng vấn / phản biện kỹ thuật sâu từng khía cạnh kiến trúc. |
| `/brainstorm <vấn đề>` | Khám phá giải pháp, đánh đổi công nghệ trước khi chốt kiến trúc. |
| `/design <module>` | Soạn thảo bản đặc tả kỹ thuật chi tiết vào `docs/spec/` trước khi lập trình. |
| `/review-design` | Rà soát rủi ro kiến trúc, nợ kỹ thuật và nguy cơ báo giả (False Positives). |
| `/write-plan` | Tách nhỏ nhiệm vụ thành các task kỹ thuật 2–5 phút vào `docs/plan/`. |
| `/implement TASK-xxx` | Thực thi mã nguồn theo hợp đồng đặc tả và các bước DoD đã định. |
| `/test TASK-xxx` | Chạy bộ kiểm thử tự động, xác minh số đo và cập nhật bằng chứng nghiệm thu `[x]`. |
| `/debug <lỗi>` | Phân tích nguyên nhân gốc rễ (Root Cause Analysis) bài bản trước khi sửa code. |
