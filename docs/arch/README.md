# Phân Hệ Kiến Trúc Kỹ Thuật (Architecture Hub) — TrafficEye Edge

> **Bước SDLC:** Bước 2 — Technical Definition (Định nghĩa Kỹ thuật & Kiến trúc).  
> **Tài liệu nộp bài cốt lõi:** [architecture_diagram.md](../architecture_diagram.md) (Bản đồ 11 phân hệ và sơ đồ kiến trúc nộp bài bắt buộc).

---

## 1. Bản Đồ Điều Hướng Kiến Trúc (Hub & Spoke Router)

| File con | Chủ đề | Nội dung chính | Trạng thái |
|---|---|---|:---:|
| [01-kien-truc-11-phan-he.md](01-kien-truc-11-phan-he.md) | Phân tầng & Service | Chi tiết 11 phân hệ (PH1 đến PH11) từ Edge Vision đến Central Hub | ✅ Đã duyệt |
| [02-nfr-rang-buoc-ky-thuat.md](02-nfr-rang-buoc-ky-thuat.md) | NFRs & Constraints | Ràng buộc: FPS $\ge 15$, Latency $< 1$s, Băng thông 4G $< 50$MB, Bảo vệ riêng tư Nghị định 13 | ✅ Đã duyệt |
| [03-adr-quyet-dinh-cong-nghe.md](03-adr-quyet-dinh-cong-nghe.md) | ADR & Trade-offs | Bảng so sánh công nghệ và lý do chọn YOLO, ByteTrack, SQLite Outbox, FastAPI | ✅ Đã duyệt |
| [04-design-review-22-findings.md](04-design-review-22-findings.md) | Phản biện rủi ro | 22 phát hiện phản biện kiến trúc của Lead Architect và phương án khắc phục triệt để | ✅ Đã duyệt |

---

## 2. Nguyên Tắc Thiết Kế Cốt Lõi
* **Edge First:** Xử lý thị giác và lọc sự kiện ngay tại camera edge box; trung tâm chỉ nhận siêu dữ liệu JSON và clip vi phạm.
* **Deterministic Core:** Các luật vi phạm, hình học giao lộ, máy trạng thái pha đèn phải được giải quyết bằng mã tất định (Computer Vision, Geometry, Rule Engine), tuyệt đối không để LLM đoán mò.
* **Resilience (Khả năng chịu lỗi):** Sử dụng Transactional Outbox Pattern với SQLite tại Edge để đảm bảo không mất dữ liệu ngay cả khi mạng 4G ngắt kết nối kéo dài $\ge 72$ giờ.
