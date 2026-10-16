# Benchmark gr14VinAI

Đo lại từ checkpoint `gr14VinAI.pt` bằng `python src_train/benchmark.py`. Ngưỡng has_target 0.4 chọn trên validation.

## 1. Khoảng cách trên tập test

Số từng video: `model_benchmark_metrics.json`.

3778 frame có nhãn, 2226 frame radar có target. Sai số tính trên frame có target.

| | MAE (m) | Trung vị (m) | RMSE (m) | Sai số tương đối | Lệch không quá 5 m | Lệch không quá 10 m |
|---|---:|---:|---:|---:|---:|---:|
| Đoán trung vị của tập train | 16.226 | 14.27 | 20.065 | 34.5% | 21.0% | 37.8% |
| gr14VinAI | 2.73 | 1.555 | 4.975 | 4.7% | 86.6% | 96.2% |

| Vùng / nhóm video | Frame có target | MAE (m) | Trung vị (m) | RMSE (m) | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 0-20 m | 60 | 2.27 | 0.251 | 10.649 | 1.0 | - |
| 20-40 m | 212 | 2.477 | 0.57 | 6.281 | 0.976 | - |
| 40-60 m | 512 | 2.457 | 1.289 | 4.636 | 0.988 | - |
| 60-80 m | 908 | 2.663 | 1.895 | 4.171 | 0.985 | - |
| 80-100 m | 534 | 3.258 | 1.986 | 4.957 | 0.845 | - |
| 9 video test ban đầu | 662 | 2.409 | 1.629 | 3.668 | 0.985 | 0.972 |
| 25 video test thêm sau | 1564 | 2.866 | 1.503 | 5.434 | 0.937 | 0.935 |
| 22 ban ngày | 1507 | 2.524 | 1.394 | 4.886 | 0.963 | 0.957 |
| 12 ban đêm | 719 | 3.162 | 1.957 | 5.156 | 0.928 | 0.921 |

## 2. Phát hiện có xe (has_target)

| Precision | Recall | F1 |
|---:|---:|---:|
| 0.94 | 0.951 | 0.946 |

## 3. Chi phí

| Số tham số | File ONNX | Latency trung bình | Trung vị | p95 | FPS | Cả pipeline mỗi frame |
|---:|---:|---:|---:|---:|---:|---:|
| 9,282,186 | 37.65 MB | 30.56 ms | 30.25 ms | 33.5 ms | 33 | 54.61 ms |

Latency: onnxruntime trên CPU, 4 luồng, mỗi lần 1 frame, 500 lần sau 50 lần làm nóng. Cả pipeline = giải mã video + cắt ảnh + model, trung bình trên mọi frame của video test.

## 4. Độ ổn định giữa hai frame liên tiếp (20 fps)

| | Khoảng cách đổi trung bình (m) | 95% dưới (m) | Xe hiện/mất mỗi phút |
|---|---:|---:|---:|
| Đầu ra thô | 0.56 | 1.73 | 16.6 |
| Sau làm mượt | 0.2 | 0.56 | 5.2 |

## Môi trường đo

- cpu: Intel64 Family 6 Model 191 Stepping 2, GenuineIntel
- onnxruntime_threads: 4
- onnxruntime: 1.30.0
- torch: 2.7.1+cu118
- accuracy_device: cuda
- video_frames: 40799
