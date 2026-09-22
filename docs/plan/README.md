# Phân Hệ Kế Hoạch & Quản Trị Công Việc (Planning Hub) — TrafficEye Edge

> **Bước SDLC:** Bước 5 — Implementation & Task Tracking.  
> **Nguyên tắc quản trị:** Phân tách file theo dõi công việc độc lập cho từng thành viên để tránh xung đột mã nguồn (Merge Conflicts) trên Git. Toàn bộ task sử dụng checkbox `[ ]` / `[x]` kèm bằng chứng nghiệm thu (Commit ID / Test Output / Đường dẫn file).

---

## 1. Bản Đồ Điều Hướng Kế Hoạch (Hub & Spoke Router)

| Thư mục / File con | Chủ đề | Nội dung chính | Trạng thái |
|---|---|---|:---:|
| [01-lo-trinh-timeline.md](01-lo-trinh-timeline.md) | Lộ trình tổng thể | Mốc M0 (24/09), M1 (27/09), CP1 (14/10), CP2 (23/10), M5 Final; Đường găng & Danh sách cắt | 🟡 Đang chạy |
| [02-danh-muc-work-packages.md](02-danh-muc-work-packages.md) | Danh mục gói việc | Bảng 56 gói việc (WP-01 đến WP-56) phân theo tuần và ma trận phân vai TV1 - TV4 | 🟡 Đang chạy |
| [m1-skeleton/](m1-skeleton/README.md) | Chi tiết Mốc M1 | Kế hoạch chi tiết 22 task kỹ thuật (TASK-001 -> TASK-022) của mốc Khung đầu-cuối | 🟡 Chạy tuần 1 |
| [phan-viec/](phan-viec/README.md) | Theo dõi cá nhân | File checkbox và nhật ký nghiệm thu độc lập của 4 thành viên | 🟢 Cập nhật liên tục |

---

## 2. Nguyên Tắc Cập Nhật Tiến Độ & DoD
1. **Quy tắc Checkbox:** Chỉ được đánh dấu `[x]` khi task đã vượt qua kiểm thử tự động (Unit Test / Test command được quy định trong task card).
2. **Quy tắc Bằng chứng (Evidence):** Cạnh mỗi checkbox `[x]`, bắt buộc bổ sung bằng chứng nghiệm thu:
   - Commit ID: `[x] TASK-002: Hoàn thành hình học vạch đếm (Commit: a1b2c3d)`
   - Test Output: `Validate: pytest tests/test_edge/test_geometry.py -v -> 4 passed`
3. **Không sửa file người khác:** Mỗi thành viên chỉ chỉnh sửa file trong `phan-viec/<tên_mình>.md`.
