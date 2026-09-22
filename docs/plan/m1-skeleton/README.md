# Kế Hoạch Mốc M1 — Khung Đầu-Cuối (M1 Skeleton)
> Mục tiêu: Chứng minh tính khả thi của toàn bộ luồng dữ liệu Video -> YOLO/ByteTrack -> Đếm xe -> Outbox -> Ingest API -> Dashboard.
> Hạn hoàn thành: 27/09/2026.

## 1. Bản Đồ Module Thực Thi M1

| Module | Phụ trách | Các Task thực hiện | Hướng dẫn |
|---|:---:|---|:---:|
| **Pipeline Edge** | TV2 (Tuấn) / TV1 | TASK-002 đến TASK-007 (Hình học, LineCounter, Aggregator, YOLO/ByteTrack, CLI) | [pipeline-edge.md](pipeline-edge.md) |
| **Backend Central** | TV4 (Khánh) / TV2 | TASK-008 đến TASK-013 (SQLite Outbox, Sender HTTP, DB Schema, Ingest API, Docker) | [backend-central.md](backend-central.md) |
| **Dashboard UI** | TV3 (Linh) | TASK-014 đến TASK-016 (Khung Next.js, Trang số đếm lưu lượng, Alerts & CI) | [dashboard-ui.md](dashboard-ui.md) |
| **QA & Evaluation** | TV4 / Cả nhóm | TASK-017 đến TASK-022 (RTSP video mock, manifest data, evaluate.py, FPS bench, E2E test) | [qa-evaluation.md](qa-evaluation.md) |

---

## 2. Tiêu Chí Nghiệm Thu M1 (DoD)
* [ ] Pipeline Edge chạy mượt mà trên stream test đạt >= 15 FPS.
* [ ] Outbox SQLite lưu trữ sự kiện đếm xe và tự gửi lại khi khôi phục kết nối mạng.
* [ ] Central API nhận sự kiện, lưu vào PostgreSQL và hiển thị đúng trên Web Dashboard.
* [ ] Kiểm thử E2E tích hợp thông suốt 100% không báo lỗi.
