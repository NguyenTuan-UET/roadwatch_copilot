# Đánh giá BT-A: hiệu chuẩn tự động + supercombo

Sinh bởi `python -m scripts.roadwatch.evaluate` ngày 07/10/2026. Model SHA-256 `65a08adc…`. Dữ liệu: comma calib_challenge, comma2k19 Example_1 (không phải dữ liệu Việt Nam).

## 1. Hiệu chuẩn (comma calib_challenge)

| Video | `fy` học được (thật 910) | Sai số `fy` | Pitch MAE (mrad) | Yaw MAE (mrad) | Hội tụ (s) |
|---|---|---|---|---|---|
| 0 | 931 | +2.3% | 0.93 | 2.99 | 29.6 |
| 1 | 913 | +0.3% | 1.05 | 1.83 | 24.9 |
| 2 | 1211 | +33.0% | — | — | — |
| 3 | 1117 | +22.8% | — | — | — |
| 4 | 1186 | +30.4% | — | — | — |
| 5 | 894 | -1.8% | — | — | 25.4 |
| 6 | 950 | +4.4% | — | — | 25.2 |
| 7 | 855 | -6.1% | — | — | 27.4 |
| 8 | 894 | -1.8% | — | — | 25.4 |
| 9 | 838 | -7.9% | — | — | 25.3 |

Sai số `fy`: trung bình tuyệt đối 11.1%, lớn nhất 33.0% trên 10 video. Pitch/yaw tính trên khung đã `calibrated` và có nhãn.

## 2. Khoảng cách và tốc độ (comma2k19 Example_1, radar + CAN)

`fy` học được: 913 px (thật 910). Khung đã `calibrated`: 58%.

- **Tốc độ xe mình** (model so với CAN, khung đã hiệu chuẩn): MAE 1.3 km/h, tốc độ CAN trung bình 60 km/h.
- **Phát hiện xe trước** (khung đã hiệu chuẩn): radar có xe trong làn ở 100% khung; model báo xe (p ≥ 0,5) ở 100%. Khi cả hai cùng có, cùng một xe (lệch < max(5 m, 25%) và < 1,5 m ngang) ở 100% khung.
- Radar có xe nhưng model không báo: 0 khung; model báo nhưng radar không có xe trong làn: 0 khung.

| Dải radar (m) | Số khung | Sai số trung bình (m) | MAE (m) | MAE (%) |
|---|---|---|---|---|
| 0–20 | 0 | chưa kiểm chứng | | |
| 20–40 | 660 | -2.35 | 2.38 | 6.8 |
| 40–60 | 40 | -1.76 | 1.76 | 4.3 |
| 60–… | 0 | chưa kiểm chứng | | |

Sai số tính trên các khung mà model và radar chọn cùng một xe; khung chọn khác xe được đếm riêng ở trên. Gốc tọa độ: khoảng cách model − 1,52 m (camera sau radar) so với khoảng cách radar.

## 3. TTC khi `fy` sai (OQ-A16)

| `fy` dùng | Khoảng cách trung vị so với `fy` đúng | TTC: sai khác trung vị | Khung có TTC ở cả hai |
|---|---|---|---|
| 0.8 × (730) | -20.8% | 12.9% | 35 |
| 1.2 × (1095) | +11.2% | 11.9% | 31 |

Pipeline chỉ báo TTC khi hai xe áp sát và TTC < 10 s, nên số khung có TTC có thể ít.

## 4. Phát hiện lắp lại camera (video 0 rồi video 1)

- Phát hiện sau 10.2 s; hiệu chuẩn lại xong sau 35.1 s; 1 lần reset.
- Pitch/yaw 10 s cuối: MAE 1.6 / 3.1 mrad.

## 5. Hiệu năng

Warp + model + giải mã đầu ra + hiệu chuẩn: trung vị 14.2 ms/khung, P95 17.9 ms (ONNX Runtime CPU, 4 thread). Tổng thời gian đánh giá 16 phút.
