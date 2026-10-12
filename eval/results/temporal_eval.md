# Đánh giá Temporal Modeling cho khoảng cách (comma2k19)

Sinh bởi `python -m scripts.roadwatch.eval_temporal` ngày 12/10/2026. Hai cấu hình chạy trên cùng đầu ra model đã ghi: `temporal=False` (chỉ Kalman) và `temporal=True`. Sai số = khoảng cách pipeline − khoảng cách radar, trên khung có cả hai. Độ rung = độ lệch chuẩn của chênh lệch khoảng cách giữa hai khung liền nhau. Dữ liệu: 7 đoạn comma2k19 (không phải dữ liệu Việt Nam). Tham số của `temporal.py` (cửa sổ 2 s, chuyển dần qua 20 mẫu) được chọn bằng quét trên chính các đoạn này, nên số dưới đây lạc quan hơn trên dữ liệu mới.

## 1. Tổng hợp (khung có radar, Kalman và temporal cùng có)

| Cấu hình | Khung | Sai số TB (m) | MAE (m) | RMSE (m) | P90 \|sai số\| (m) | MAPE (%) | Độ rung (m/khung) |
|---|---|---|---|---|---|---|---|
| Kalman (không temporal) | 5183 | -5.43 | 6.95 | 13.76 | 16.43 | 9.7 | 0.779 |
| Temporal | 5183 | -5.31 | 6.74 | 13.65 | 16.07 | 9.3 | 0.698 |

## 2. Theo dải khoảng cách radar

| Dải (m) | Cấu hình | Khung | Sai số TB (m) | MAE (m) | RMSE (m) | P90 \|sai số\| (m) | MAPE (%) | Độ rung (m/khung) |
|---|---|---|---|---|---|---|---|---|
| 0–20 | Kalman | 181 | -1.55 | 1.55 | 1.66 | 2.36 | 8.1 | 0.079 |
| 0–20 | Temporal | 181 | -1.49 | 1.50 | 1.65 | 2.39 | 7.8 | 0.115 |
| 20–40 | Kalman | 918 | -2.62 | 2.91 | 3.23 | 4.35 | 9.9 | 0.493 |
| 20–40 | Temporal | 918 | -2.64 | 2.79 | 3.02 | 4.50 | 9.5 | 0.196 |
| 40–60 | Kalman | 1879 | -2.08 | 3.39 | 5.13 | 7.13 | 6.4 | 0.612 |
| 40–60 | Temporal | 1879 | -1.76 | 2.98 | 4.60 | 5.36 | 5.7 | 0.344 |
| 60–… | Kalman | 2205 | -9.79 | 12.11 | 20.44 | 32.12 | 12.5 | 1.009 |
| 60–… | Temporal | 2205 | -9.77 | 12.02 | 20.40 | 31.70 | 12.4 | 1.019 |

## 3. Theo từng đoạn

| Đoạn | Cấu hình | Khung | Sai số TB (m) | MAE (m) | RMSE (m) | P90 \|sai số\| (m) | MAPE (%) | Độ rung (m/khung) |
|---|---|---|---|---|---|---|---|---|
| 0 | Kalman | 494 | -8.71 | 12.00 | 25.29 | 23.51 | 13.1 | 1.346 |
| 0 | Temporal | 494 | -8.37 | 11.83 | 25.60 | 34.17 | 12.7 | 1.012 |
| 1 | Kalman | 1180 | -2.43 | 2.43 | 2.64 | 3.81 | 8.6 | 0.096 |
| 1 | Temporal | 1180 | -2.44 | 2.44 | 2.65 | 3.70 | 8.6 | 0.137 |
| 2 | Kalman | 967 | -0.28 | 4.72 | 9.89 | 12.96 | 5.4 | 0.765 |
| 2 | Temporal | 967 | -0.72 | 5.00 | 10.06 | 12.23 | 5.8 | 0.501 |
| 3 | Kalman | 900 | -3.64 | 4.62 | 6.35 | 10.07 | 8.1 | 0.527 |
| 3 | Temporal | 900 | -3.44 | 3.94 | 5.17 | 6.31 | 6.9 | 0.331 |
| 4 | Kalman | 416 | -1.84 | 2.53 | 4.12 | 6.88 | 4.9 | 0.724 |
| 4 | Temporal | 416 | -1.76 | 2.16 | 3.37 | 4.62 | 4.2 | 0.281 |
| 5 | Kalman | 690 | -6.59 | 7.61 | 11.83 | 16.59 | 11.6 | 0.284 |
| 5 | Temporal | 690 | -6.41 | 7.43 | 11.56 | 16.56 | 11.4 | 0.439 |
| 6 | Kalman | 536 | -22.64 | 22.74 | 28.07 | 55.00 | 20.3 | 1.477 |
| 6 | Temporal | 536 | -21.58 | 21.99 | 27.83 | 54.87 | 19.4 | 1.680 |

## 4. Dự đoán khoảng cách sau 1 s

So `gap_pred_m` với khoảng cách radar thật sau 1 s; đối chứng là "giữ nguyên khoảng cách hiện tại" (không có chuyển động).

| Cách dự đoán | Khung | Sai số TB (m) | MAE (m) | RMSE (m) | P90 \|sai số\| (m) | MAPE (%) | Độ rung (m/khung) |
|---|---|---|---|---|---|---|---|
| Giữ nguyên khoảng cách hiện tại | 4934 | -4.33 | 6.04 | 10.84 | 16.34 | 9.1 | 0.479 |
| Temporal (gap_pred_m) | 4934 | -4.72 | 6.85 | 11.93 | 16.32 | 10.7 | 1.614 |

Tổng thời gian đánh giá 0 phút.
