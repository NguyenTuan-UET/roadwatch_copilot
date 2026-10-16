# Công cụ dòng lệnh RoadWatch

## Overview

Script quanh pipeline: chuẩn bị model, tạo dữ liệu đầu vào, đánh giá và kiểm tra trước PR; code runtime không import chúng. Chạy từ thư mục gốc repo, đúng kiểu lệnh ghi bên dưới (`python -m …` hoặc `python scripts/…`).

## Workflow

Chuẩn bị model → tạo log GPS/radar cho video → chạy app → đánh giá, so sánh điện thoại với laptop → kiểm tra schema và tài liệu.

## Quick Start

```bash
python scripts/roadwatch/download_model.py
python -m scripts.roadwatch.make_phone_models
python -m scripts.roadwatch.comma2k19_to_gpx data/dashcam/* --out data/gps
python scripts/roadwatch/export_radar_csv.py data/comma2k19/0 out.csv
python -m scripts.roadwatch.evaluate --videos ../test_videos --calib ../third_party/calib_challenge --out eval/results/bt_a_eval.md
python -m scripts.roadwatch.export_api_schema --check
python -m scripts.roadwatch.check_docs
RW_PASSWORD=... scripts/roadwatch/serve_tunnel.sh
```

## Outputs

| Script | Ý nghĩa |
|---|---|
| `download_model.py`, `make_phone_models.py` | `models/gr14VinAI.onnx` và bản cho điện thoại |
| `comma2k19_to_gpx.py`, `export_radar_csv.py` | log GPS (`.gpx`) và radar (`.csv`) để tải lên trang Chạy video |
| `evaluate.py`, `eval_temporal.py`, `eval_lane_test.py`, `compare_lane_variants.py` | báo cáo đánh giá (đường dẫn `--out` hoặc tham số), kết quả chính ở [eval/](../../eval/README.md) |
| `compare_phone_clip.py`, `lane_jitter_ref.py` | bảng so sánh điện thoại với laptop, in ra màn hình |
| `export_onphone_golden.py` | dữ liệu chuẩn `tests/roadwatch/fixtures/onphone/` cho test JS |
| `export_api_schema.py` | ghi `src/roadwatch/openapi.json`; `--check` báo lỗi khi file cũ |
| `check_docs.py` | kiểm link, ID và metadata tài liệu |
| `serve_tunnel.sh` | URL HTTPS công khai cho server demo (ngrok hoặc Cloudflare) |
| `add_lane_clips.py`, `make_alert_sounds.py` | thêm clip làn vào tab Lab; tạo WAV cảnh báo |

Lệnh kiểm tra đầy đủ: [code-rules](../../docs/development/code-rules.md), mục 7. Quay lại [README chính](../../README.md).
