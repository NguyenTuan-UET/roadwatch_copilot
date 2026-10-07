# RoadWatch demo API (cho frontend)

Hợp đồng giữa server demo `src/roadwatch/web.py` và mọi giao diện gọi tới nó.

- **Nguồn chuẩn:** model Pydantic trong `src/roadwatch/schemas.py`.
- **Bản máy đọc:** [roadwatch-api.openapi.json](schemas/roadwatch-api.openapi.json), sinh bằng `python -m scripts.roadwatch.export_api_schema`. CI chạy `--check` và báo lỗi khi file này lệch code.
- **Xem và thử trực tiếp:** `http://127.0.0.1:8765/docs` khi server đang chạy.
- **Giao diện mẫu dùng API này:** `src/roadwatch/web.html`.

Phiên bản API: `1.0.0`, trả trong `api_version` của `/health` và của mọi `LiveStatus`. Thêm trường tùy chọn thì tăng MINOR; đổi tên, đổi kiểu hoặc bỏ trường thì tăng MAJOR.

## 1. Quy ước

- Base URL: `http://127.0.0.1:8765`, cùng nguồn với trang. Server chỉ nghe trên máy; không có CORS và chưa có đăng nhập.
- Đơn vị nằm trong tên trường: `_m` mét, `_s` giây, `_kmh` km/h, `_deg` độ, `_px` pixel, `_ms` mili giây, `_us` micro giây.
- **Không có dữ liệu thì là `null`, không bao giờ là `0`.** Ví dụ không có xe trước thì `lead.gap_m = null`.
- `t_s` là thời gian trong video (khung thứ `frame` chia 20 Hz), không phải giờ hệ thống.
- Lỗi trả `{"detail": "<câu tiếng Việt>"}`, hiển thị nguyên văn được. Riêng lỗi 422 (sai kiểu tham số) dùng dạng danh sách mặc định của FastAPI.

## 2. Endpoint

| Phương thức | Đường dẫn | Trả về | Dùng để |
|---|---|---|---|
| `GET` | `/health` | `Health` | Server sống, có model không, job có bị treo không |
| `GET` | `/api/config` | `BtBConfig` | Bảng ngưỡng Thông tư 38, tham số BT-B, văn bản ba câu nói |
| `POST` | `/api/runs` | `RunStarted` | Tải video lên và chạy ngay (mục 3) |
| `POST` | `/api/stop` | `Stopping` | Dừng lần chạy hiện tại |
| `GET` | `/api/status` | `LiveStatus` | Trạng thái hiện tại (một lần) |
| `GET` | `/api/events` | SSE, mỗi tin một `LiveStatus` | Cập nhật theo từng khung (mục 4) |
| `GET` | `/api/history` | `History` | 600 điểm đồ thị gần nhất (30 s), dùng khi mở trang giữa lần chạy |
| `GET` | `/api/stream` | MJPEG | Video đã chú thích; đặt làm `src` của `<img>` |
| `GET` | `/api/phrases/{level}` | WAV | Câu nói thu sẵn; `level` ∈ `info`, `warning`, `emergency` |
| `GET` | `/api/runs` | `RunInfo[]` | Lịch sử lần chạy, mới nhất trước |
| `GET` | `/api/runs/{run_id}/files/{name}` | MP4 hoặc JSON | `annotated.mp4` (tua được), `decisions.json`, `run.json` |
| `DELETE` | `/api/runs/{run_id}` | `Deleted` | Xóa lần chạy và video đã tải lên; 409 nếu đang chạy |

## 3. Tải video và chạy

Thân request là **bytes của file video** (không dùng multipart). Tham số đi trên query:

| Tham số | Bắt buộc | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `name` | Có | đuôi `.mp4 .mov .mkv .avi .hevc .h264 .webm` | Tên file gốc |
| `fps` | Có | 0 < `fps` ≤ 240 | Tốc độ khung lúc quay |
| `d` | Có | 0 ≤ `d` ≤ 5 | Khoảng cách camera tới cản trước (m) |
| `fy` | Không | 0 < `fy` ≤ 10000 | Tiêu cự (px); bỏ trống thì hệ thống tự học |
| `rt` | Không | `true` (mặc định) / `false` | Chạy đúng tốc độ thực 20 Hz hay nhanh nhất có thể |

Lỗi: 400 file rỗng, 413 quá `RW_MAX_UPLOAD_MB`, 415 không phải video, 422 tham số sai.

```javascript
const r = await fetch(`/api/runs?${new URLSearchParams({name: file.name, fps: 30, d: 1.5})}`,
                      {method: 'POST', body: file});
if (!r.ok) alert((await r.json()).detail);
const {run_id} = await r.json();
```

## 4. Nhận kết quả theo từng khung

```javascript
const es = new EventSource('/api/events');
es.addEventListener('status', (msg) => {
  const s = JSON.parse(msg.data);          // LiveStatus
  if (s.decision?.say) new Audio(`/api/phrases/${s.decision.say}`).play();
  if (s.sample) chartPush(s.sample);       // tự giữ bộ đệm 30 s
});
```

Server gửi một tin cho mỗi khung đã xử lý và mỗi lần đổi trạng thái. Tin có dạng `event: status` nên phải dùng `addEventListener('status', …)`; `onmessage` không nhận được tin này. Video đã chú thích lấy riêng qua `<img src="/api/stream">`.

## 5. `LiveStatus`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `api_version` | string | |
| `state` | `idle` \| `loading` \| `running` \| `done` \| `stopped` \| `failed` | |
| `run_id` | string \| null | 12 ký tự hex |
| `error` | string \| null | Có khi `failed` |
| `measure` | `Measurement` \| null | BT-A; `null` trước khung đầu |
| `decision` | `Decision` \| null | BT-B |
| `ops` | `Ops` \| null | BT-C |
| `sample` | `Sample` \| null | Một điểm đồ thị của khung này |
| `events` | `SpokenEvent[]` | 30 câu đã nói gần nhất, cũ trước |
| `outputs` | `Outputs` \| null | Có khi `done` hoặc `stopped`: `video_url`, `log_url` |

**`Measurement` (BT-A):** `frame`, `t_s`, `ego_kmh`, `ttc_s` (null trừ khi đang áp sát và TTC < 10 s), `lead` {`prob`, `gap_m`, `speed_kmh`}, `calibration` {`status`, `calibrated`, `fy_px`, `fy_state`, `pitch_deg`, `yaw_deg`, `height_m`, `coverage`, `remounts`}.

- `calibration.status`: `calibrating k/5`, `calibrated` hoặc `unreliable: <lý do>`.
- `calibration.calibrated = true` nghĩa là đã cho phép cảnh báo khoảng cách: góc lắp đã hội tụ và đã biết `fy`.

**`Decision` (BT-B):** `level` (mức đang hiệu lực hoặc null), `say` (câu phát **ở chính khung này**, null là im lặng), `reason` (lý do nói hay im lặng, tiếng Việt), `threshold_m` (ngưỡng luật ở tốc độ hiện tại; null dưới 60 km/h), `latency_us`.

**`Ops` (BT-C):** `fps`, `latency` {`last_ms`, `p50_ms`, `p95_ms`}, `bad_frames`, `raw_onsets` và `said`, mỗi trường là {`info`, `warning`, `emergency`}. `raw_onsets` đếm số lần nói nếu không có điều phối, `said` đếm số lần thật sự nói; so hai số này là ra mức "ít nói hơn".

Schema đầy đủ, gồm ràng buộc từng trường: [roadwatch-api.openapi.json](schemas/roadwatch-api.openapi.json), mục `components.schemas`.

## 6. Yêu cầu với giao diện

- Tài xế không bao giờ phải nhìn màn hình (requirements file 2, BT-B): âm thanh là kênh chính, màn hình chỉ phụ trợ.
- Phát `/api/phrases/{decision.say}` ngay khi nhận tin có `say` khác null.
- Không tự suy ra cảnh báo từ `measure`: quyết định nói hay không là của BT-B (`decision`).
- Hiển thị `null` thành "—", không thành `0`.
