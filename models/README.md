# gr14VinAI — model

## Overview

Model ONNX của khối nhận thức (~30M tham số, FP16, opset 20): nhận chuỗi ảnh camera, cho xe phía trước, làn đường, mép đường và pose; laptop chạy bằng ONNX Runtime (`src/roadwatch/model.py`), `/phone` chạy bản chuyển đổi trên GPU điện thoại. Kiến trúc: [architechture_model.md](architechture_model.md).

## Workflow

`download_model.py` → `gr14VinAI.onnx` (laptop, CPU) → `make_phone_models` → `gr14VinAI.{mixed,capture,fp32}.onnx` (điện thoại, onnxruntime-web).

## Quick Start

```bash
python scripts/roadwatch/download_model.py
python -m scripts.roadwatch.make_phone_models   # chỉ cần cho /phone
```

## Outputs

| File / thư mục | Ý nghĩa |
|---|---|
| `gr14VinAI.onnx` | model laptop; `download_model.py` dừng nếu file đã có |
| `gr14VinAI.mixed.onnx`, `gr14VinAI.capture.onnx` | bản GPU cho `/phone`, không commit |
| `gr14VinAI.fp32.onnx` | bản CPU cho `/phone`, không commit |
| `ort-web/` | onnxruntime-web cho `/phone`, không commit |
| `phrases-demo/` | câu cảnh báo WAV (`info`, `warning`, `emergency`) |
| `architechture_model.md` | đầu vào/đầu ra, backbone, vision heads, temporal aggregation |

Kết quả đo của model và bằng chứng: [eval/README.md](../eval/README.md).

Quay lại [README chính](../README.md).
