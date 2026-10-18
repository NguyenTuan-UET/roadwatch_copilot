# Tài liệu thuyết trình và demo

## Overview

Tài liệu cho Demo Day: slide trong [`../docs/slides/`](../docs/slides/) (`RoadWatch_Copilot_P-014.pdf`, `index.html`), web demo chạy trên trình duyệt với dữ liệu giả lập, và video app chạy thật trong `../video/`. Bản triển khai: [c4-app-014.vercel.app](https://c4-app-014.vercel.app/); video demo: [YouTube](https://youtu.be/Su2nJbZoxnE). Số liệu trên slide lấy từ [eval/README.md](../eval/README.md), không lấy từ web demo.

## Workflow

1. Giới thiệu problem (< 30 giây).
2. Demo live feature chính (2-3 phút): web demo hoặc [video app chạy offline](../video/offline.mp4).
3. Hiển thị kết quả AI (1 phút), dẫn nguồn từ `eval/`.
4. Tóm tắt impact (< 30 giây).

## Quick Start

```bash
python -m http.server 8000 --directory presentation/web-demo
# rồi mở http://127.0.0.1:8000/
```

## Outputs

| File / thư mục | Ý nghĩa |
|---|---|
| [`../docs/slides/`](../docs/slides/) | slide thuyết trình 15 trang (PDF và HTML) |
| [web-demo/](web-demo/README.md) | web demo tĩnh, mọi số là dữ liệu giả lập |
| `../video/` | video và GIF app chạy thật, không phải dữ liệu giả lập |

Quay lại [README chính](../README.md).
