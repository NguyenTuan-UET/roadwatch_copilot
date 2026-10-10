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

- Mọi số liệu trên trang là giả lập, có nhãn "Dữ liệu giả lập". Để nối server thật, đổi `MOCK = true` thành `false` trong khối `api` của `demo.html` và phục vụ trang cùng nguồn với `src/roadwatch/web.py`.
- Mô hình 3D và phông chữ tải từ CDN (cdnjs, jsdelivr, Google Fonts), nên cần mạng khi mở.
- Ảnh buồng lái được nhúng sẵn trong `index.html`.
