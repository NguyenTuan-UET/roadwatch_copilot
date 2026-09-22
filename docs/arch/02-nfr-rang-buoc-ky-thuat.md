# Kiến trúc Hệ thống — Phần 2: Yêu Cầu Phi Chức Năng (NFR) & Ràng Buộc Kỹ Thuật
> Nguồn: Tách từ Báo cáo kỹ thuật TrafficEye Edge (Mục 12 - 17) và Mục 5 Spec.
> Tuân thủ SDLC Bước 2: Non-Functional Requirements (NFR). Độ dài chuẩn: 150 - 250 dòng.

---

## 1. Ma Trận Chỉ Số NFR Định Lượng

| Nhóm | Mã NFR | Chỉ số đo lường | Mục tiêu bắt buộc | Phương pháp kiểm chứng |
|---|---|---|---|---|
| **Hiệu năng Edge** | NFR-PERF-1 | Tốc độ xử lý video tại Edge Box | >= 15 FPS (1080p stream) | `scripts/benchmark_fps.py` đo 10.000 frames |
| **Độ trễ** | NFR-LAT-1 | End-to-end Latency (Event -> Hub) | < 1.0 giây qua mạng 4G | Timestamp diff giữa Edge tạo và Hub nhận |
| **Độ chính xác** | NFR-ACC-1 | Precision phát hiện vi phạm | >= 95.0% (Wilson 95% CI) | Đánh giá trên tập test chuẩn 500 ca vi phạm |
| **Băng thông** | NFR-NET-1 | Dung lượng data 4G / camera / ngày | < 50 MB/ngày | Giám sát `iftop` / Docker network stats |
| **Độ sẵn sàng** | NFR-REL-1 | Vận hành Offline khi mất mạng | Lưu trữ cục bộ >= 72 giờ | Thử nghiệm ngắt mạng 72h và gửi bù thành công |
| **Bảo mật** | NFR-SEC-1 | Xác thực kênh truyền & chống giả mạo | HTTPS / mTLS, API Key, SHA-256 | Kiểm toán lỗ hổng OWASP API Top 10 |
| **Riêng tư** | NFR-PRV-1 | Bảo vệ dữ liệu cá nhân (Nghị định 13) | Blur 100% khuôn mặt người | Kiểm tra thị giác trên 200 clip bằng chứng |

---

## 2. Chi Tiết Các Ràng Buộc Kỹ Thuật

### 2.1. Ràng buộc phần cứng và tài nguyên Edge (NFR-PERF-1)
* Thiết bị mục tiêu: Jetson Orin Nano / Xavier NX hoặc Mini PC tương đương (CPU 4-8 cores, 8GB RAM).
* Mức chiếm dụng tài nguyên tối đa khi chạy pipeline toàn tải:
  - CPU Utilization: <= 75%.
  - RAM Consumption: <= 4.5 GB.
  - Nhiệt độ chip: <= 70 độ C trong điều kiện ngoài trời nhiệt đới (40 độ C).
* Tối ưu hóa mô hình: Bắt buộc xuất YOLO sang định dạng TensorRT INT8 hoặc ONNX Runtime để đạt tốc độ xử lý >= 15 FPS mà không bị nghẽn CPU.

### 2.2. Cơ chế chịu lỗi khi mất mạng (Offline Resilience - NFR-REL-1)
* Khi mất mạng 4G: Edge Box chuyển sang chế độ `OFFLINE_AUTONOMOUS`. Mọi sự kiện phát hiện, đếm xe và video bằng chứng vẫn được ghi liên tục vào database SQLite cục bộ.
* Giới hạn dung lượng lưu trữ: Phân vùng SQLite được cấp tối đa 16GB disk (đủ chứa xấp xỉ 500 gói bằng chứng vi phạm và dữ liệu đếm xe trong 72 giờ).
* Khi mạng kết nối trở lại: Outbox Worker tự động chuyển sang chế độ `REPLAYING`, gửi bù tuần tự theo thứ tự thời gian cũ nhất trước (FIFO) kèm giới hạn tốc độ truyền (Rate Limiting) để tránh làm nghẽn băng thông của luồng trực tiếp.

### 2.3. Quy định bảo vệ dữ liệu và quyền riêng tư (NFR-PRV-1)
* Tuân thủ triệt để Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân:
  - Toàn bộ khuôn mặt của người điều khiển xe máy, người ngồi trong xe ô tô và người đi bộ trong bán kính quan sát phải được làm mờ (Gaussian Blur / Pixelation) ngay tại Edge Box trước khi gói bằng chứng được mã hóa gửi đi.
  - Tuyệt đối không lưu trữ video thô liên tục (No Continuous Raw Video Storage) tại Edge Box cũng như Central Hub; chỉ lưu trữ đoạn video 3–5 giây chứa hành vi vi phạm được xác nhận.

### 2.4. Tiêu chuẩn an toàn bảo mật kênh truyền (NFR-SEC-1)
* Toàn bộ luồng truyền dữ liệu giữa Edge và Central sử dụng giao thức HTTPS với chứng chỉ SSL/TLS 1.3.
* Mỗi Edge Box sở hữu một cặp khóa RSA/ECC riêng biệt và Client Certificate để thiết lập kênh xác thực hai chiều mTLS.
* Gói bằng chứng vi phạm được gắn mã băm SHA-256 (Hash Digest) kèm chữ ký số của Edge Box để ngăn chặn mọi hành vi chỉnh sửa hoặc làm giả bằng chứng khi truyền qua mạng công cộng.
