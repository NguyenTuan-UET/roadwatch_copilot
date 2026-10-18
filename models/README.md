# gr14VinAI — model

## Overview

Model ONNX của khối nhận thức (~30M tham số, FP16, opset 20): nhận chuỗi ảnh camera, cho xe phía trước, làn đường, mép đường và pose; laptop chạy bằng ONNX Runtime (`src/roadwatch/model.py`), `/phone` chạy bản chuyển đổi trên GPU điện thoại. Kiến trúc: [architechture_model.md](architechture_model.md).

## Workflow

`download_model.py` → `gr14VinAI.onnx` (laptop, CPU) → `make_phone_models` → `gr14VinAI.{mixed,capture,fp32}.onnx` (điện thoại, onnxruntime-web 1.20.1). Thư viện onnxruntime-web 1.20.1 đặt ở `models/ort-web/1.20.1/` (`ort.webgpu.min.js`, `ort-wasm-simd-threaded.jsep.{mjs,wasm}`, lấy bằng `npm pack onnxruntime-web@1.20.1`); bản này cùng graph capture là cách duy nhất chạy bền trong Safari (README mục 6).

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
| `phrases-demo/` | âm cảnh báo WAV (`chime`, `info`, `warning`, `emergency`) |
| `architechture_model.md` | đầu vào/đầu ra, backbone, vision heads, temporal aggregation |

Kết quả đo của model và bằng chứng: [eval/README.md](../eval/README.md).

Quay lại [README chính](../README.md).
