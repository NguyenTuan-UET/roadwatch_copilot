# Benchmark gr14VinAI

34 video test Comma2k19: 3.778 frame, 2.226 frame radar có xe.

| Chỉ số | Kết quả |
|---|---:|
| MAE trên frame radar có xe | **2,73 m** |
| F1 phát hiện xe cùng làn | **0,946** |
| gr14VinAI | **30,56 ms/frame** |
| Cả pipeline | **54,61 ms/frame** |

Cả pipeline chưa đạt 20 FPS; chưa đo tốc độ điện thoại.

[So sánh với hình học và thử nghiệm thực địa](../README.md) · [Cách đo](../evaluation_protocol.md) · [Số liệu đầy đủ](model_benchmark_metrics.json).
