# Theo Dõi Tiến Độ Công Việc Từng Thành Viên — TrafficEye Edge

> **Mục tiêu:** Phân tách không gian làm việc độc lập giữa các kỹ sư để tránh xung đột mã nguồn (Merge Conflicts) trên Git và đảm bảo tính minh bạch về kết quả bàn giao (DoD).

---

## 1. Phân Vai & File Theo Dõi Cá Nhân

| Thành viên | Mã vai | Phân hệ phụ trách chính | File theo dõi |
|---|:---:|---|:---:|
| **Cường** | TV1 (Lead) | Edge Core Pipeline, Luật vi phạm & State Machine, Điều phối chung | [cuong.md](cuong.md) |
| **Tuấn** | TV2 | Edge Vision (YOLO + ByteTrack), Line Counting & Geometry | [tuan.md](tuan.md) |
| **Linh** | TV3 | Web Dashboard (Next.js/Vite), Trang số đếm, UX & Bản đồ lưu lượng | [linh.md](linh.md) |
| **Khánh** | TV4 | Backend Ingest API, SQLite Outbox, Database, QA & Đo lường Wilson | [khanh.md](khanh.md) |

---

## 2. Quy Định Cập Nhật Checkbox & Nghiệm Thu
* **Khi nhận việc:** Để trống `[ ]`.
* **Khi code xong nhưng chưa test:** Vẫn để trống `[ ]`.
* **Khi hoàn thành:** Đánh dấu `[x]` kèm bằng chứng nghiệm thu bắt buộc (Commit ID hoặc Test result log).
* **Tuyệt đối không:** Không xóa task hoặc chỉnh sửa file của thành viên khác.
