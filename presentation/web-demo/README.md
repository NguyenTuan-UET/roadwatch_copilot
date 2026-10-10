# Web demo RoadWatch Copilot

Bản demo giao diện chạy hoàn toàn trên trình duyệt, dùng dữ liệu giả lập đúng schema API 1.0.0 (`src/roadwatch/openapi.json`).

| File | Nội dung |
|---|---|
| `index.html` | Buồng lái mở đầu: chạm chữ V, màn hình giữa phóng to, logo, rồi vào web demo |
| `demo.html` | Web demo: Intro, Kiến trúc (sơ đồ và mô hình 3D), Chạy video, Lái thử, Lịch sử, Kỹ sư |
| `cao-toc-3d.html` | Mô hình 3D cao tốc (three.js), nhúng trong trang Kiến trúc, có đồng hồ tốc độ góc dưới bên phải |

## Mở

Các trang nhúng nhau bằng `iframe`, nên cần một server tĩnh thay vì mở file trực tiếp:

```bash
python -m http.server 8000 --directory presentation/web-demo
# rồi mở http://127.0.0.1:8000/
```

## Ghi chú

- Mặc định mọi số liệu trên trang là giả lập, có nhãn "Dữ liệu giả lập".

## Nối server thật

`serve.py` phục vụ trang và chuyển `/api/*`, `/health` sang server RoadWatch, nên trang gọi API cùng nguồn. Thêm `?live` vào URL để tắt dữ liệu giả lập:

```bash
python -m src.roadwatch.web                  # server, cổng 8765
python presentation/web-demo/serve.py        # web demo, cổng 8000
# rồi mở http://127.0.0.1:8000/?live
```

Đổi địa chỉ server bằng biến `RW_API`, cổng web demo bằng `PORT`. Server cần `models/gr14VinAI.onnx` để chạy video; thiếu file này trang báo "Thiếu model".
- Mô hình 3D và phông chữ tải từ CDN (cdnjs, jsdelivr, Google Fonts), nên cần mạng khi mở.
- Ảnh buồng lái được nhúng sẵn trong `index.html`.
