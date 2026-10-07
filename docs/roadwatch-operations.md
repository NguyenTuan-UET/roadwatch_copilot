# RoadWatch: vận hành, độ tin cậy và quản trị AI

Tài liệu này mô tả server demo `src/roadwatch/web.py` và luồng xử lý `src/roadwatch/job.py`. Kiến trúc, hợp đồng dữ liệu và tiêu chí nghiệm thu vẫn lấy từ [spec](specs/roadwatch-architecture.md). BT-B trong server demo là bản rút gọn `src/roadwatch/decide.py`, không thay cho engine MVP của spec 3.3–3.7.

## 1. Đối chiếu với Technical Book (chương 07–12)

| Chương | Trong RoadWatch | Ở đâu |
|---|---|---|
| 07 Workflow Design & Reliability | Luồng từng khung có trạng thái rõ ràng; khung lỗi bị bỏ qua; heartbeat; phát hiện treo; fail-safe theo năng lực | Mục 2, 3; `src/roadwatch/job.py` |
| 08 Phát triển API với FastAPI | API REST + SSE + MJPEG, model Pydantic, kiểm tra tham số, OpenAPI tại `/docs` | Mục 4; `src/roadwatch/web.py` |
| 09 Giao diện người dùng | Trang 3 khu BT-A/B/C, cập nhật từng khung, sáng/tối, `aria-live` cho cảnh báo, bàn phím, lịch sử lần chạy | `src/roadwatch/web.html` |
| 10 Kiểm thử và Đánh giá | Test BT-B, test API (validate, path traversal, xóa dữ liệu), test luồng; đánh giá BT-A trên dữ liệu comma | `tests/roadwatch/`; `eval/results/` |
| 11 Privacy, Security & AI Governance | Chỉ chạy trên máy; giới hạn upload; header bảo mật; xóa dữ liệu; nguồn gốc model; giới hạn đã biết | Mục 5, 6 |
| 12 DevOps và Triển khai | Docker không chạy root, healthcheck, compose, biến môi trường, log JSON, CI có build image | Mục 7 |

## 2. Luồng xử lý một lần chạy

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> loading: "POST /api/runs"
    loading --> running: "khung đầu tiên"
    running --> done: "hết video"
    running --> stopped: "POST /api/stop"
    loading --> failed: "video hỏng"
    running --> failed: "20 khung lỗi liên tiếp hoặc ffmpeg lỗi"
    done --> loading: "video mới"
    stopped --> loading: "video mới"
    failed --> loading: "video mới"
```

Mỗi khung đi qua: giải mã ffmpeg (20 Hz) → BT-A `Pipeline.step` → BT-B `Decider.step` → vẽ HUD → ghi video kết quả → đẩy trạng thái qua SSE. BT-B lấy thời gian từ chỉ số khung, không từ đồng hồ hệ thống. Khi nhập `fy`, chạy lại cùng video cho cùng quyết định; khi `fy` học ở luồng nền, khung đổi `fy` phụ thuộc tốc độ máy nên quyết định có thể khác.

## 3. Độ tin cậy

| Tình huống | Hệ thống làm gì |
|---|---|
| Một khung làm model lỗi | Bỏ khung đó, không cảnh báo từ khung đó, đếm `bad_frames`. 20 khung lỗi liên tiếp (1 s) thì lần chạy `failed` |
| Chưa biết `fy` | Chạy ngay với `fy` tạm; học `fy` ở luồng nền rồi đổi. Trong lúc đó cảnh báo khoảng cách tắt, cảnh báo TTC vẫn bật |
| Học `fy` thất bại (xe chậm, video cắt ghép) | Giữ `fy` tạm, cảnh báo khoảng cách tắt suốt lần chạy, giao diện báo lý do |
| Ảnh không phủ đủ khung model (`coverage` < 95 %) | Trạng thái `unreliable`, không cảnh báo khoảng cách và TTC |
| Lần chạy không ra khung mới trong 2 s | `/health` trả `degraded`, `hung: true` |
| ffmpeg ghi video lỗi | Lần chạy `failed`, có thông báo lỗi |
| Server tắt giữa chừng | `runs/demo/heartbeat.json` ngừng cập nhật (ghi mỗi giây, ghi nguyên tử) |

## 4. API

Hợp đồng API cho frontend (endpoint, `LiveStatus`, SSE, lỗi, phiên bản): [specs/roadwatch-api.md](specs/roadwatch-api.md). Tài liệu tự sinh: `http://127.0.0.1:8765/docs`.

## 5. Privacy và security

- **Dữ liệu không rời máy.** Không gọi mạng khi chạy; không có LLM hay dịch vụ ngoài (ADR-12). Server mặc định chỉ nghe `127.0.0.1`; trong Docker, compose chỉ mở cổng trên `127.0.0.1`.
- **Video dashcam chứa biển số, khuôn mặt của người khác.** Video tải lên nằm trong `runs/demo/<run_id>/`, không được commit (`.gitignore`), không được phục vụ lại qua API. Chỉ giữ `RW_KEEP_RUNS` lần chạy mới nhất; người dùng xóa được từng lần chạy ở giao diện hoặc `DELETE /api/runs/{run_id}`. Không đăng video của người khác lên mạng khi chưa làm mờ.
- **Kiểm tra đầu vào:** chỉ nhận đuôi video; giới hạn `RW_MAX_UPLOAD_MB`; từ chối file rỗng; tham số có khoảng hợp lệ; `run_id` và tên file theo danh sách cho phép, nên không đọc được file ngoài thư mục lần chạy.
- **Header:** `Content-Security-Policy` chỉ cho tài nguyên cùng nguồn, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- **Container** chạy bằng user `roadwatch`, model gắn chỉ đọc.
- **Chưa có:** đăng nhập hai vai trò tài xế và kỹ sư (spec 11.5). Server demo một người dùng, chỉ trên máy; không mở ra mạng LAN khi chưa có đăng nhập.

## 6. Quản trị AI

- **Chỉ cảnh báo** (NG1): không điều khiển xe, không đọc dữ liệu xe.
- **Nguồn gốc model:** openpilot supercombo, MIT, commit `c933446…`, SHA-256 bản gốc `65a08adc…`; bản tỉa `models/gr14VinAI.onnx` (spec I-26). Không huấn luyện lại. Mã openpilot đi kèm ở `src/roadwatch/vendor/g01T014VinAI/` với `LICENSE.openpilot`.
- **Giải thích được:** mỗi quyết định nói hay im lặng có lý do, lưu trong `decisions.json` và hiện trên giao diện.
- **Con người kiểm soát ngưỡng:** tham số BT-B là giá trị tạm của `config/proposals/v0.yaml`; đổi qua HITL (spec 3.10). Giao diện demo không sửa cấu hình.
- **Giới hạn đã biết:** dữ liệu đánh giá là của comma (Mỹ), chưa có dữ liệu Việt Nam; học `fy` sai trên 3/10 video calib_challenge; video zoom hẹp, cắt ghép hoặc mưa to làm số đo kém tin cậy; câu nói tiếng Việt là bản nháp chưa duyệt (OQ-B5). Số liệu ở `eval/results/`.

## 7. Triển khai

Chạy trực tiếp (cần `ffmpeg`):

```bash
uv venv && uv pip install -r requirements-roadwatch.txt
python scripts/roadwatch/download_model.py
python -m src.roadwatch.web
```

Bằng Docker (model đã tải vào `models/`):

```bash
docker compose up --build roadwatch
```

**Live URL từ laptop demo (Cloudflare Tunnel).** Laptop chạy server như trên; `cloudflared` mở một URL HTTPS công khai trỏ về `127.0.0.1:8765`. Không cần tài khoản Cloudflare, nhưng URL đổi mỗi lần khởi động và chỉ sống khi laptop bật.

```bash
RW_PASSWORD='<mật khẩu>' scripts/roadwatch/serve_tunnel.sh   # in URL và thông tin đăng nhập; Ctrl+C dừng cả hai
```

- Bắt buộc có `RW_PASSWORD`; không đặt thì script tự sinh một mật khẩu ngẫu nhiên và in ra. Mọi đường dẫn trừ `/health` cần đăng nhập HTTP Basic, kể cả WebSocket.
- Cloudflare gói miễn phí chặn request lớn hơn 100 MB, nên script đặt `RW_MAX_UPLOAD_MB=100` và chỉ giữ `RW_KEEP_RUNS=5` lần chạy.
- Quick tunnel gom luồng SSE lại thành khối và gửi trễ nhiều giây. Vì vậy giao diện nhận cập nhật qua WebSocket `/api/ws`; đo qua tunnel được khoảng 21 tin/s, khoảng cách lớn nhất giữa hai tin 0,06 s.
- Cài `cloudflared`: tải bản `cloudflared-linux-amd64` từ trang phát hành GitHub của Cloudflare, so SHA-256 với ghi chú phát hành, đặt vào `PATH`.
- Muốn URL cố định thì cần tài khoản Cloudflare và một tên miền (named tunnel); quick tunnel không cho chọn tên.

Biến môi trường: `.env.example`, mục RoadWatch. Log ra stdout dạng JSON mỗi dòng. CI (`.github/workflows/roadwatch.yml`): ruff, pytest RoadWatch, kiểm tài liệu, build image và gọi `/health`.
