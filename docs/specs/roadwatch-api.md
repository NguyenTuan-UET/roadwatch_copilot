# RoadWatch demo API (cho frontend)

Hợp đồng giữa server demo `src/roadwatch/web.py` và mọi giao diện gọi tới nó.

- **Nguồn chuẩn:** model Pydantic trong `src/roadwatch/schemas.py`.
- **Bản máy đọc:** [openapi.json](../../src/roadwatch/openapi.json), sinh bằng `python -m scripts.roadwatch.export_api_schema`. CI chạy `--check` và báo lỗi khi file này lệch code.
- **Xem và thử trực tiếp:** `http://127.0.0.1:8765/docs` khi server đang chạy.
- **Giao diện dùng API này:** web app `src/roadwatch/ui/` ở `/app` (file tĩnh phục vụ ở `/ui/`; link mở sẵn một lần chạy: `/app#runs/<run_id>`), vào từ màn buồng lái ở `/`; trang cũ `src/roadwatch/judge.html` ở `/judge` và `src/roadwatch/web.html` ở `/engineer`.

Phiên bản API: `1.5.0` (1.5.0 thêm `calib_rpy_deg` và `calib_settled` vào `LabStatus`, và `/api/lab/frame` có hình trong lượt hiệu chỉnh góc; 1.2.0 thêm `GET /api/frame`; 1.3.0 thêm log GPS, thông số ống kính và kết quả theo comma_ai/lead_distance, mục 3; 1.4.0 thêm Lab trực tiếp, `preview_every`, `Ops.video_fps`, tham số `wide` và hiệu chỉnh góc của Lab như `app.py` của comma_ai/lead_distance), trả trong `api_version` của `/health` và của mọi `LiveStatus`. Thêm trường tùy chọn thì tăng MINOR; đổi tên, đổi kiểu hoặc bỏ trường thì tăng MAJOR.

## 1. Quy ước

- Base URL: `http://127.0.0.1:8765`, cùng nguồn với trang. Server mặc định chỉ nghe trên máy; không có CORS. HTTP Basic được bật khi đặt `RW_PASSWORD`, áp dụng cả WebSocket, trừ endpoint health.
- Đơn vị nằm trong tên trường: `_m` mét, `_s` giây, `_kmh` km/h, `_deg` độ, `_px` pixel, `_ms` mili giây, `_us` micro giây.
- **Không có dữ liệu thì là `null`, không bao giờ là `0`.** Ví dụ không có xe trước thì `lead.gap_m = null`.
- `t_s` là thời gian trong video (khung thứ `frame` chia 20 Hz), không phải giờ hệ thống.
- Lỗi trả `{"detail": "<câu tiếng Việt>"}`, hiển thị nguyên văn được. Riêng lỗi 422 (sai kiểu tham số) dùng dạng danh sách mặc định của FastAPI.

## 2. Endpoint

| Phương thức | Đường dẫn | Trả về | Dùng để |
|---|---|---|---|
| `GET` | `/health` | `Health` | Server sống, có model không, job có bị treo không |
| `GET` | `/health/live` | `{"status": "alive"}` | Process còn trả lời; dùng cho Docker HEALTHCHECK |
| `GET` | `/health/ready` | `{"status", "model"}` | Có model, sẵn sàng chạy; 503 nếu thiếu model |
| `GET` | `/api/config` | `BtBConfig` | Bảng ngưỡng Thông tư 38, tham số BT-B, văn bản ba câu nói |
| `GET` | `/api/samples` | `SampleVideo[]` | Danh sách video mẫu trên server |
| `POST` | `/api/samples/{sample_id}/run` | `RunStarted` | Chạy video mẫu, `rt=true` mặc định |
| `POST` | `/api/gps` | `GpsUploaded` | Tải log GPS (GPX / NMEA / CSV) cho lần chạy kế tiếp (mục 3) |
| `POST` | `/api/runs` | `RunStarted` | Tải video lên và chạy ngay (mục 3) |
| `POST` | `/api/stop` | `Stopping` | Dừng lần chạy hiện tại |
| `GET` | `/api/status` | `LiveStatus` | Trạng thái hiện tại (một lần) |
| `GET` | `/api/events` | SSE, mỗi tin một `LiveStatus` | Cập nhật theo từng khung (mục 4) |
| `WS` | `/api/ws` | mỗi tin một `LiveStatus` (JSON) | Như `/api/events` nhưng qua WebSocket; **dùng cái này khi đi qua Cloudflare Tunnel** |
| `GET` | `/api/history` | `History` | 600 điểm đồ thị gần nhất (30 s), dùng khi mở trang giữa lần chạy |
| `GET` | `/api/stream` | MJPEG | Video đã chú thích; đặt làm `src` của `<img>` |
| `GET` | `/api/frame` | `image/jpeg`, `204` khi chưa có khung | Khung đã chú thích mới nhất, từng ảnh một. Giao diện dùng endpoint này, xin ảnh sau khi ảnh trước đã hiện: MJPEG trong `<img>` bị Chrome ngừng hiện sau khoảng 400 phần (~20 MB) trên cùng kết nối, và bị proxy, tunnel hay chuyển tiếp cổng gom lại |
| `GET` | `/api/lab/segments` | `LabSegment[]` | Segment comma2k19 trên máy (`RW_LAB_DIR`) cho trang Lab |
| `POST` | `/api/lab/segments/{seg_id}/run` | `LabStatus` | Chạy BT-A trên cả segment như `app.py` của comma_ai/lead_distance: `bumper` (camera tới radar, mặc định 1,52 m), `fy` (mặc định 910 px), `log` (dùng tốc độ CAN), `wide` (`dup` mặc định: đầu vào camera rộng là ảnh hẹp nhân đôi; `warp`). Góc camera ước lượng trên 300 frame đầu, chỉ áp yaw, cố định cả lần chạy; 409 nếu đang chạy segment khác |
| `GET` | `/api/lab/status` | `LabStatus` | Tiến độ: `done` / `total` frame, trong đó `calib_frames` frame đầu là lượt hiệu chỉnh góc; trong lượt đó `calib_rpy_deg` là [roll, pitch, yaw] ước lượng đến lúc này (chỉ yaw được áp) và `calib_settled` cho biết đã đủ mẫu |
| `GET` | `/api/lab/segments/{seg_id}/result` | `LabResult` | Kết quả đã lưu, một giá trị mỗi frame; `rpy_deg` là góc ước lượng, `rpy_applied_deg` là góc đã áp (chỉ yaw) |
| `GET` | `/api/lab/live?since=n` | `LabLive` | Giá trị từng frame của segment Lab đang chạy, từ frame `n` (chỉ frame đủ cột); trang Lab vẽ biểu đồ trực tiếp từ đây |
| `GET` | `/api/lab/frame` | `image/jpeg`, `204` khi chưa có khung | Khung mới nhất của segment Lab đang chạy: khung thô trong lượt hiệu chỉnh góc, khung đã chú thích sau đó |
| `GET` | `/api/phrases/{kind}` | WAV | Câu nói thu sẵn; `kind` ∈ `info`, `warning`, `emergency` |
| `GET` | `/api/runs` | `RunInfo[]` | Lịch sử lần chạy, mới nhất trước |
| `GET` | `/api/runs/{run_id}/files/{name}` | MP4, JSON hoặc CSV | `annotated.mp4` (tua được), `decisions.json`, `run.json`, `lead_distance.csv`, `calibration.json` |
| `DELETE` | `/api/runs/{run_id}` | `Deleted` | Xóa lần chạy và video đã tải lên; 409 nếu đang chạy |

## 3. Tải video và chạy

Thân request là **bytes của file video** (không dùng multipart). Tham số đi trên query:

| Tham số | Bắt buộc | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `name` | Có | đuôi `.mp4 .mov .mkv .avi .hevc .h264 .webm` | Tên file gốc |
| `fps` | Có | 0 < `fps` ≤ 240 | Tốc độ khung lúc quay |
| `d` | Có | 0 ≤ `d` ≤ 5 | Khoảng cách camera tới cản trước (m) |
| `fy` | Một trong ba | 0 < `fy` ≤ 10000 | Tiêu cự (px); có thì bỏ qua `lens` |
| `lens` | Không | `mm` (mặc định) / `px` / `fov` / `learn` | Cách cho tiêu cự khi không có `fy`: tiêu cự mm hoặc góc nhìn; `learn` tự học từ video, chỉ khi chọn. Mặc định phải nhập tay: không có `fy`, `f_mm` hay `hfov` (và không chọn `learn`) thì API trả 422 |
| `f_mm` | Khi `lens=mm` | 0 < `f_mm` ≤ 300 | Tiêu cự (mm), tương đương 35 mm nếu không có `sensor_mm` |
| `sensor_mm` | Không | 0 < `sensor_mm` ≤ 40 | Cạnh dài cảm biến (mm); có thì `f_mm` là tiêu cự thật |
| `hfov` | Khi `lens=fov` | 20 ≤ `hfov` ≤ 170 | Góc nhìn ngang của vùng ảnh camera (độ) |
| `fisheye` | Không | `false` (mặc định) / `true` | Ống kính fisheye (mô hình equidistant) cho `hfov` |
| `gps` | Không | 12 ký tự hex | `gps_id` từ `POST /api/gps`; log được chuyển vào thư mục lần chạy |
| `gps_offset` | Không | -600 ≤ `gps_offset` ≤ 3600 | Giờ GPS lúc video t = 0 (s, tính từ điểm GPS đầu); bỏ trống thì tự đồng bộ |
| `auto_focal` | Không | `false` (mặc định) / `true` | Thử nghiệm: hiệu chỉnh tiêu cự theo tốc độ GPS (cần `gps`) |
| `crop` | Không | `auto` (mặc định) / `full` / `x,y,w,h` | Vùng ảnh camera: tự bỏ viền đen, toàn khung, hoặc tự nhập |
| `pitch` | Không | `true` (mặc định) / `false` | Áp góc pitch tự hiệu chỉnh vào warp |
| `rt` | Không | `true` (mặc định) / `false` | Phát theo thời gian thực (tốc độ video gốc) hay nhanh nhất có thể |
| `preview_every` | Không | 1 ≤ `preview_every` ≤ 10, mặc định 2 | Làm mới khung xem trực tiếp (`/api/frame`, `/api/stream`) mỗi N khung video; nhỏ thì mượt hơn nhưng tốn CPU hơn |

Lỗi: 400 file rỗng, 404 không có `gps` này, 413 quá `RW_MAX_UPLOAD_MB`, 415 không phải video, 422 tham số sai.

Tham số ống kính, GPS và Nâng cao theo trang upload của `comma_ai/lead_distance` (`pages/Upload_video.py`, `realtime_lead.py`). Khi có log GPS và đã đồng bộ (sau khoảng 20 s xe chạy), tốc độ xe mình lấy theo GPS ở mọi nơi: HUD, ngưỡng cảnh báo và TTC.

**Log GPS:** `POST /api/gps?name=<tên file>`, thân request là bytes của file `.gpx .nmea .txt .log .csv` (tối đa 20 MB). Server đọc thử ngay và trả `GpsUploaded` {`gps_id`, `fixes`, `duration_s`}; 400 nếu không đọc được, 415 sai đuôi. Mỗi `gps_id` dùng cho một lần chạy.

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

Qua Cloudflare quick tunnel (`*.trycloudflare.com`), SSE bị gom lại và tới trễ nhiều giây. Dùng WebSocket, cùng nội dung tin:

```javascript
const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/api/ws');
ws.onmessage = (msg) => { const s = JSON.parse(msg.data); /* LiveStatus, như trên */ };
ws.onclose = () => setTimeout(reconnect, 1000);
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
| `outputs` | `Outputs` \| null | Có khi `done` hoặc `stopped`: `video_url`, `log_url`, `csv_url` (`lead_distance.csv`, một dòng mỗi tick, cột như comma `realtime_lead`), `calibration_url` |

**`Measurement` (BT-A):** `frame` (khung video của tick model; model chạy mỗi n khung, gần 20 Hz), `t_s`, `ego_kmh`, `ego_source` (`gps` / `model`), `gps` {`state`: `none` / `syncing` / `synced` / `low_confidence`, `offset_s`, `corr`}, `lead_raw_m` (khoảng cách thô của model ở tick này), `ttc_s` (null trừ khi đang áp sát và TTC < 10 s), `lead` {`prob`, `gap_m`, `speed_kmh`}, `calibration` {`status`, `calibrated`, `flags`, `fy_px`, `fy_state`, `pitch_deg`, `yaw_deg`, `height_m`, `coverage`, `remounts`}.

- `calibration.status`: `calibrating k/40` (k mẫu hiệu chuẩn góc đã nhận), `calibrated` hoặc `unreliable: <lý do>`.
- `calibration.calibrated = true` nghĩa là đã cho phép cảnh báo khoảng cách: góc lắp đã hội tụ và đã biết `fy`.

**`Decision` (BT-B):** `level` (mức đang hiệu lực hoặc null), `say` (câu phát **ở chính khung này**, null là im lặng), `reason` (lý do nói hay im lặng, tiếng Việt), `threshold_m` (ngưỡng luật ở tốc độ hiện tại; null dưới 60 km/h), `latency_us`.

**`Ops` (BT-C):** `fps` (khung xử lý mỗi giây), `video_fps` (fps của video; `fps` ≥ `video_fps` là theo kịp thời gian thực), `latency` {`last_ms`, `p50_ms`, `p95_ms`}, `bad_frames`, `raw_onsets` và `said`, mỗi trường là {`info`, `warning`, `emergency`}. `raw_onsets` đếm số lần nói nếu không có điều phối, `said` đếm số lần thật sự nói; so hai số này là ra mức "ít nói hơn".

Schema đầy đủ, gồm ràng buộc từng trường: [openapi.json](../../src/roadwatch/openapi.json), mục `components.schemas`.

## 6. Yêu cầu với giao diện

- Tài xế không bao giờ phải nhìn màn hình (requirements file 2, BT-B): âm thanh là kênh chính, màn hình chỉ phụ trợ.
- Phát `/api/phrases/{decision.say}` ngay khi nhận tin có `say` khác null.
- Không tự suy ra cảnh báo từ `measure`: quyết định nói hay không là của BT-B (`decision`).
- Hiển thị `null` thành "—", không thành `0`.

## 7. Video mẫu

Server đọc video mẫu từ `RW_SAMPLES_DIR` (mặc định `runs/samples/`). Mỗi mẫu có `<id>.mp4` và `<id>.json`; ID gồm chữ thường ASCII, chữ số, dấu gạch ngang hoặc gạch dưới, tối đa 40 ký tự. Chỉ các cặp file đủ video và metadata được liệt kê.

JSON chứa `title`, `note` tùy chọn, `fps`, `d` và `fy` tùy chọn. `fps`, `d`, `fy` dùng cùng giới hạn với API upload ở mục 3; không nhận NaN hoặc vô cực. Khi bỏ `fy`, API trả `null` và lần chạy dùng tiêu cự do người dùng nhập, hoặc tự học nếu chọn `lens=learn`.

`POST /api/samples/{sample_id}/run` nhận `rt` tùy chọn; ID không có trong danh sách trả 404. Video được hard-link hoặc sao chép vào thư mục riêng của lần chạy. Xóa lần chạy không xóa bản video mẫu.
