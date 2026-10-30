# Benchmark gr14VinAI

34 video test Comma2k19: 3.778 frame, 2.226 frame radar có xe.

| Chỉ số | Kết quả |
|---|---:|
| MAE trên frame radar có xe | **2,73 m** |
| F1 phát hiện xe cùng làn | **0,946** |
| gr14VinAI | **30,56 ms/frame** |
| Cả pipeline | **54,61 ms/frame** |

Cả pipeline trên laptop chưa đạt 20 FPS. Trên điện thoại (offline, WebGPU, đo 17/10/2026): khoảng 70 ms/frame, 15 FPS khi máy mát, 12 FPS khi máy nóng ([cách đo](../evaluation_protocol.md)).

[So sánh với hình học và thử nghiệm thực địa](../README.md) · [Cách đo](../evaluation_protocol.md) · [Số liệu đầy đủ](model_benchmark_metrics.json).
