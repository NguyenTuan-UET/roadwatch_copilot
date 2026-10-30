# Web demo RoadWatch Copilot

## Overview

Bản demo giao diện chạy hoàn toàn trên trình duyệt, dùng dữ liệu giả lập theo schema API 1.0.0 (bản cũ; API hiện là 2.0.0, xem `src/roadwatch/openapi.json`). Mọi số trên trang có nhãn "Dữ liệu giả lập" và không dùng làm kết quả đánh giá.

## Workflow

`index.html` (buồng lái, chạm chữ V) → `demo.html` (đổi `MOCK = true` thành `false` trong khối `api` và phục vụ cùng nguồn với `src/roadwatch/web.py` để nối server thật) → `cao-toc-3d.html` nhúng trong trang Kiến trúc.

## Quick Start

Các trang nhúng nhau bằng `iframe`, nên cần server tĩnh; mô hình 3D và phông chữ tải từ CDN nên cần mạng:

```bash
python -m http.server 8000 --directory presentation/web-demo
# rồi mở http://127.0.0.1:8000/
```

## Outputs

| File | Ý nghĩa |
|---|---|
| `index.html` | buồng lái mở đầu: chạm chữ V, màn hình giữa phóng to, logo; ảnh nhúng sẵn |
| `demo.html` | Intro, Kiến trúc (sơ đồ và mô hình 3D), Chạy video, Lái thử, Lịch sử, Kỹ sư |
| `cao-toc-3d.html` | mô hình 3D cao tốc (three.js), đồng hồ tốc độ góc dưới bên phải |

Quay lại [README chính](../../README.md).
