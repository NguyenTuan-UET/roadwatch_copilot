# Kiến trúc Hệ thống — Phần 1: 11 Phân Hệ & Luồng Dữ Liệu Đầu-Cuối
> Nguồn: Tổng hợp từ Báo cáo kỹ thuật TrafficEye Edge và docs/architecture_diagram.md
> Tuân thủ SDLC Bước 2: System Architecture. Độ dài chuẩn: 150 - 250 dòng.

---

## 1. Sơ Đồ Khối Tổng Thể Hệ Thống

```text
+------------------------------------------------------------------------------------+
|                                 EDGE CAMERA BOX                                    |
|                                                                                    |
| [PH1: Video Source] ---> [PH2: Vision Pipeline] ---> [PH3: Counting & Density]    |
| (RTSP / Video Stream)   (YOLOv8/v11 + ByteTrack)    (Virtual Line + ROI Polygon)   |
|                                     |                                              |
|                                     v                                              |
|                           [PH4: Traffic Light]                                     |
|                          (HSV / Patch Classifier)                                  |
|                                     |                                              |
|                                     v                                              |
|                         [PH5: Violation Rule Engine]                               |
|                     (Vượt đèn đỏ, Sai làn, Ngược chiều)                            |
|                                     |                                              |
|                                     v                                              |
|                      [PH6: Evidence & Privacy Packager]                            |
|                   (Clip 3-5s, Blur mặt, OCR, JSON Manifest)                        |
|                                     |                                              |
|                                     v                                              |
|                          [PH7: Edge SQLite Outbox]                                 |
|                     (Lưu trữ cục bộ offline >= 72h)                                |
+------------------------------------------------------------------------------------+
                                      |
                           HTTPS (mTLS) / JSON Event
                                      v
+------------------------------------------------------------------------------------+
|                                 CENTRAL PLATFORM                                   |
|                                                                                    |
|                      [PH8: FastAPI Ingest & Receiver]                              |
|                   (Xác thực Token, Ingest Event & Evidence)                        |
|                                     |                                              |
|                                     +-----------------------+                      |
|                                     v                       v                      |
|                          [PH9: PostgreSQL DB]    [PH10: Operator Dashboard]        |
|                         (Lưu trữ giao thông,     (Giao diện duyệt 2 bước HITL,     |
|                          vi phạm, nhật ký)        Bản đồ lưu lượng real-time)      |
|                                     ^                       ^                      |
|                                     |                       |                      |
|                                     +--- [PH11: Copilot] ---+                      |
|                                       (LangGraph Agent tra cứu)                    |
+------------------------------------------------------------------------------------+
```

---

## 2. Chi Tiết Trách Nhiệm 11 Phân Hệ (PH1 - PH11)

### PH1: Video Source & Frame Preprocessing
* Đọc luồng video RTSP từ camera giao thông (hoặc file video giả lập môi trường thử nghiệm).
* Quản lý bộ đệm vòng (ring buffer) 30 khung hình gần nhất để trích xuất bằng chứng trước thời điểm vi phạm.

### PH2: Edge Vision Pipeline (Detection & Tracking)
* **Detection:** Sử dụng mô hình YOLOv8n / YOLOv11n (hoặc TensorRT INT8) phát hiện 5 lớp phương tiện: `car`, `motorcycle`, `bus`, `truck`, `pedestrian`.
* **Tracking:** Thuật toán ByteTrack gán ID duy nhất và duy trì quỹ đạo chuyển động (trajectory) của từng phương tiện qua các khung hình.

### PH3: Traffic State & Counting
* Đếm lưu lượng xe theo từng làn thông qua vạch đếm ảo (Virtual Counting Line).
* Tính toán mật độ xe (Level of Service - LOS), tốc độ trung bình và cảnh báo tắc nghẽn giao lộ.

### PH4: Traffic Light Recognition
* Phân vùng hộp đèn giao thông (Bounding Box) và phân loại màu đèn (Đỏ, Vàng, Xanh) theo thời gian thực bằng thuật toán phân tích màu HSV kết hợp bộ lọc thời gian chống nháy.

### PH5: Violation Rule Engine (Động cơ Phân tích Vi phạm)
* Máy trạng thái hữu hạn (Finite State Machine) kiểm tra 3 luật vi phạm giao thông cốt lõi:
  1. *Vượt đèn đỏ:* Xe vượt qua vạch dừng khi pha đèn đỏ đang có hiệu lực.
  2. *Đi sai làn:* Xe di chuyển trên làn không đúng quy định phân làn (rẽ trái ở làn đi thẳng, xe máy đi làn ô tô).
  3. *Đi ngược chiều:* Vector quỹ đạo xe chuyển động ngược hướng vector chuẩn của làn đường.

### PH6: Evidence & Privacy Packager
* Cắt ghép đoạn video ngắn 3–5 giây (2s trước vi phạm và 1–3s sau vi phạm).
* Tự động che mờ (blur) khuôn mặt người điều khiển và người đi bộ để tuân thủ Nghị định 13/2023/NĐ-CP.
* Trích xuất ảnh crop biển số và đọc ký tự (OCR). Đóng gói manifest JSON và nén thành gói ZIP.

### PH7: Edge Storage & Outbox Worker
* Ghi dữ liệu sự kiện và gói bằng chứng vào SQLite cục bộ theo mô hình Transactional Outbox.
* Worker chạy nền định kỳ đẩy dữ liệu về trung tâm qua HTTPS; tự động retry khi kết nối mạng phục hồi.

### PH8: FastAPI Ingest & Receiver
* Endpoint tiếp nhận dữ liệu tại trung tâm, kiểm tra xác thực định danh thiết bị (mTLS/API Key).
* Xác thực tính toàn vẹn của payload và lưu tạm file bằng chứng vào MinIO / Local Storage.

### PH9: Central Database
* Hệ quản trị PostgreSQL (kèm TimescaleDB nếu cần) lưu trữ chuỗi thời gian sự kiện xe chạy, danh sách hồ sơ vi phạm và nhật ký audit log.

### PH10: Operator Dashboard (Human-in-the-Loop)
* Giao diện Web (Next.js / Vite) hiển thị danh sách hồ sơ vi phạm chờ thẩm định.
* Quy trình thẩm duyệt 2 bước (Reviewer -> Approver) trước khi ký số biên bản phạt nguội.

### PH11: AI Copilot Agent (LangGraph)
* Trợ lý ảo sử dụng LangGraph hỗ trợ điều hành viên tra cứu sự cố bằng ngôn ngữ tự nhiên: "Tìm tất cả xe tải đi sai làn tại nút giao Giải Phóng lúc 8h sáng".
