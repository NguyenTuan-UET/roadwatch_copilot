# gr14VinAI — Kết quả thực nghiệm

## Overview

Đánh giá khoảng cách tới xe phía trước của gr14VinAI, khối nhận thức của pipeline, trên video thật; không dùng dữ liệu mô phỏng. Bộ test, quy tắc chấm và giới hạn (chưa đo đối đầu SafeGap, chưa kiểm chứng trời mưa): [evaluation_protocol.md](evaluation_protocol.md).

## Workflow

1. **Thực địa:** video có HUD model và radar → đọc số qua OCR → lọc frame theo quy tắc chấm.
2. **Comma2k19:** chấm 34 video test và 300 ca golden (`inputs/golden.jsonl`) với radar CAN.
3. **Human baseline:** so khoảng cách model với người đánh giá trên 30 ảnh.
4. **Hình:** vẽ từ các file kết quả → `report/figures/`.

## Quick Start

Dựng lại số liệu thực địa, human baseline và hình `field_*.png`, `human_baseline.png` (cần thêm `pandas`, `matplotlib`, `openpyxl`; ghi đè các file CSV và PNG tương ứng):

```bash
python eval/report/scripts/make_readme_figures.py
```

## Outputs

| File / thư mục | Ý nghĩa |
|---|---|
| [radar_vinhomeocp/field_metrics.json](radar_vinhomeocp/field_metrics.json) | Thực địa Ocean Park 2 + cao tốc Hà Nội – Hải Phòng, 1.257 frame: MAE **4,35 m**, trung vị **2,70 m**, **83,0%** lệch ≤ 15% (radar đọc qua OCR) |
| [results/golden_dataset_metrics.json](results/golden_dataset_metrics.json) | Comma2k19, 300 ca: đạt **83,7%** (hình học 32,7%); F1 **0,946** (hình học 0,407) trên 3.778 frame |
| [human_baseline/comparison_30_images.csv](human_baseline/comparison_30_images.csv) | 30 ảnh, không có radar: khớp có/không có xe 30/30; lệch trung vị 5,90 m so với người |
| [results/model_benchmark_metrics.json](results/model_benchmark_metrics.json) | Comma2k19: MAE 2,73 m trên 2.226 frame radar có xe. Laptop, 500 lần: model **30,56 ms/frame**; cả pipeline 54,61 ms/frame, chưa đạt 50 ms của 20 FPS |
| [evaluation_protocol.md](evaluation_protocol.md) | Điện thoại, offline, GPU qua WebGPU của Safari, nhóm đo 17/10/2026: khoảng **70 ms/frame**; **15 FPS** trong điều hòa, tụt về **12 FPS** khi máy nóng; tải về dưới 90 MB. Video minh họa: [offline.mp4](../video/offline.mp4) |
| [results/deterministic_rerun_report.md](results/deterministic_rerun_report.md) | Hai lần chấm cho cùng kết quả |
| `report/figures/` | Hình kết quả; báo cáo đầy đủ ở [final_evaluation_report.md](final_evaluation_report.md) |

Quay lại [README chính](../README.md).
