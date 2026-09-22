# Phân Hệ Đo Lường & Đánh Giá Chất Lượng (Evaluation Hub) — TrafficEye Edge

> **Bước SDLC:** Bước QD (Quality Definition) & Bước 7 (System / E2E Verification).  
> **Nguyên tắc cốt lõi:** "Verify, Don't Trust" — Không bao giờ coi "code chạy được" là "hệ thống đúng". Mọi độ chính xác vi phạm phải có khoảng tin cậy thống kê bảo vệ.

---

## 1. Bản Đồ Điều Hướng Kiểm Thử & Đo Lường (Hub & Spoke Router)

| File con | Bước SDLC | Nội dung chính | Trạng thái |
|---|:---:|---|:---:|
| [01-chien-luoc-kiem-thu.md](01-chien-luoc-kiem-thu.md) | Bước QD | Chiến lược kiểm thử 4 cấp độ, chia tập Train/Val/Test, đóng băng model và quy trình gán nhãn | ✅ Đã duyệt |
| [02-giao-thuc-danh-gia-wilson.md](02-giao-thuc-danh-gia-wilson.md) | Bước QD/7 | Giao thức Wilson Score 95% Confidence Interval cho Precision $\ge 95\%$, tách nguồn lỗi theo tầng | ✅ Đã duyệt |
| [03-mau-bao-cao-nghiem-thu.md](03-mau-bao-cao-nghiem-thu.md) | Bước 7 | Biểu mẫu nghiệm thu chính thức: FPS, latency, Precision từng loại vi phạm (Vượt đèn, Sai làn, Ngược chiều) | ✅ Đã duyệt |

---

## 2. Quy Tắc Đánh Giá Định Lượng
* **Quy tắc Wilson 95%:** Báo cáo nghiệm thu bắt buộc phải trình bày dạng:
  $$\text{Precision} = \frac{TP}{TP + FP} \quad [L_{95\%}, U_{95\%}]$$
  với cận dưới $L_{95\%} \ge 90\%$ trên tập dữ liệu thử nghiệm độc lập.
* **Tách nguồn lỗi (Error Decomposition):** Khi phát hiện lỗi nhận diện sai, phải phân tách rõ nguyên nhân thuộc về: (1) YOLO False Positive, (2) ByteTrack ID Switch, (3) Lỗi nhận diện đèn tín hiệu, hay (4) Lỗi máy trạng thái hình học.
