# RoadWatch demo API (cho frontend)

Hợp đồng giữa server demo `src/roadwatch/web.py` và mọi giao diện gọi tới nó.

- **Nguồn chuẩn:** model Pydantic trong `src/roadwatch/schemas.py`.
- **Bản máy đọc:** [openapi.json](../../src/roadwatch/openapi.json), sinh bằng `python -m scripts.roadwatch.export_api_schema`. CI chạy `--check` và báo lỗi khi file này lệch code.
- **Xem và thử trực tiếp:** [c4-app-014.vercel.app/docs](https://c4-app-014.vercel.app/docs) (bản triển khai), hoặc `http://127.0.0.1:8765/docs` khi chạy local.
- **Giao diện dùng API này:** web app `src/roadwatch/ui/` ở `/app` (file tĩnh phục vụ ở `/ui/`; link mở sẵn một lần chạy: `/app#runs/<run_id>`), vào từ màn buồng lái ở `/`; trang đo trên điện thoại ở `/phone` (mục 4); trang cũ `src/roadwatch/judge.html` ở `/judge` và `src/roadwatch/web.html` ở `/engineer`.

Phiên bản API: `2.0.0`, trả trong `api_version` của `/health` và của mọi `LiveStatus`. Thêm trường tùy chọn thì tăng MINOR; đổi tên, đổi kiểu hoặc bỏ trường thì tăng MAJOR. Lịch sử: mục 10.

## 1. Quy ước

- Base URL: `http://127.0.0.1:8765`, cùng nguồn với trang. Server mặc định chỉ nghe trên máy; không có CORS. Mặc định dùng tài khoản SQLite và cookie `rw_session` (HttpOnly, SameSite=Lax, 12 giờ), áp dụng cả WebSocket và signaling WebRTC. Trang `/login`, `/register`, `/`, file UI và health công khai. API chưa đăng nhập trả 401; `/app` chuyển tới `/login`. `RW_ACCOUNTS=0` dùng HTTP Basic cũ khi đặt `RW_PASSWORD`.
- Đơn vị nằm trong tên trường: `_m` mét, `_s` giây, `_kmh` km/h, `_deg` độ, `_px` pixel, `_ms` mili giây, `_us` micro giây.
- **Không có dữ liệu thì là `null`, không bao giờ là `0`.** Ví dụ không có xe trước thì `lead.gap_m = null`.
- `t_s` là thời gian trong video (khung thứ `frame` chia 20 Hz), không phải giờ hệ thống.
- Lỗi trả `{"detail": "<câu tiếng Việt>"}`, hiển thị nguyên văn được. Riêng lỗi 422 (sai kiểu tham số) dùng dạng danh sách mặc định của FastAPI.
- **Tài khoản:** tên đăng nhập gồm 3–40 ký tự ASCII: chữ, số, `.`, `_`, `-`; mật khẩu 8–128 ký tự. Đăng ký nhận `role` là `driver` hoặc `engineer`; giá trị khác trả 422. Đăng nhập chỉ nhận tên đăng nhập/mật khẩu, không cho đổi vai trò. `/engineer` và `/api/lab/…` chỉ cho kỹ sư (403 với tài xế). Request thay đổi dữ liệu và WebSocket từ Origin khác bị từ chối. Bản demo dùng chung một job và lịch sử lần chạy giữa các tài khoản; chưa tách dữ liệu theo người dùng.

## 2. Endpoint

| Phương thức | Đường dẫn | Trả về | Dùng để |
|---|---|---|---|
| `GET` | `/health` | `Health` | Server sống, có model không, job có bị treo không |
| `GET` | `/health/live` | `{"status": "alive"}` | Process còn trả lời; dùng cho Docker HEALTHCHECK |
| `GET` | `/health/ready` | `{"status", "model"}` | Có model, sẵn sàng chạy; 503 nếu thiếu model |
| `POST` | `/api/auth/register` | `Account`, 201 | JSON `{username, password, role?}`; `role` là `driver` (mặc định) hoặc `engineer`; tạo tài khoản và phiên đăng nhập; 409 khi trùng tên |
| `POST` | `/api/auth/login` | `Account` | JSON `{username, password}`; 401 nếu sai, 429 sau 5 lần sai trong 5 phút |
| `GET` | `/api/auth/me` | `Account` | `{username, role}` của phiên hiện tại |
| `POST` | `/api/auth/logout` | `LoggedOut` | Thu hồi phiên, xóa cookie và đóng WebRTC của phiên |
| `GET` | `/api/config` | `BtBConfig` | Bảng ngưỡng Thông tư 38, tham số BT-B, mô tả từng âm báo |
| `GET` | `/api/samples` | `SampleVideo[]` | Danh sách video mẫu trên server |
| `POST` | `/api/samples/{sample_id}/run` | `RunStarted` | Chạy video mẫu, `rt=true` mặc định |
| `POST` | `/api/gps` | `GpsUploaded` | Tải log GPS (GPX / NMEA / CSV) cho lần chạy kế tiếp (mục 3) |
| `POST` | `/api/radar?name=` | `RadarUploaded` | Thân là file CSV (`.csv`, tối đa 20 MB): cột thời gian từ đầu video (`t`, `t_s`, `time`, `time_s`, giây) và khoảng cách radar tới xe phía trước (`radar_m`, `distance_m`, `dist`, `d`, mét; ô trống hoặc NaN = không có xe); 415 khi sai đuôi, 400 khi không đọc được hoặc dưới 3 khoảng cách dùng được. Truyền `radar_id` vào `radar` của `POST /api/runs` (dùng một lần). Chạy video hiện khoảng cách radar, Δ so với model ở bảng và ở sáu ô như tab Lab |
| `POST` | `/api/runs` | `RunStarted` | Tải video lên và chạy ngay (mục 3) |
| `POST` | `/api/stop` | `Stopping` | Dừng lần chạy hiện tại |
| `GET` | `/api/status` | `LiveStatus` | Trạng thái hiện tại (một lần) |
| `GET` | `/api/events` | SSE, mỗi tin một `LiveStatus` | Cập nhật theo từng khung (mục 4) |
| `WS` | `/api/ws` | mỗi tin một `LiveStatus` (JSON) | Như `/api/events` nhưng qua WebSocket; **dùng cái này khi đi qua Cloudflare Tunnel** |
| `GET` | `/api/history` | `History` | 600 điểm đồ thị gần nhất (30 s), dùng khi mở trang giữa lần chạy |
| `GET` | `/api/rtc` | `RtcConfig` | ICE servers cho WebRTC (`iceServers`); cùng yêu cầu đăng nhập như các API khác |
| `POST` | `/api/rtc/offer` | `RtcAnswer` | Nhận `{run_id, type: "offer", sdp}`; trả `{peer_id, type: "answer", sdp}` đã có ICE candidates. Video-only, tối đa 4 người xem. SDP tối đa 65.536 ký tự; 409 nếu run đã kết thúc, 400 nếu SDP không hợp lệ, 503 nếu đủ người xem, 504 khi ICE quá thời gian |
| `POST` | `/api/phone/offer` | `PhoneAnswer` | Bắt đầu đo trực tiếp từ điện thoại (mục 4): nhận `PhoneOffer` `{type: "offer", sdp, d, f_mm \| hfov, auto_focal?, pitch?}`, trả `{run_id, type: "answer", sdp}`. Thay lần chạy đang có; 400 nếu offer không có video, 422 nếu thiếu tiêu cự hoặc `d` ngoài 0–5 m, 504 khi ICE quá thời gian |
| `WS` | `/api/phone/ws` | `{run_id}`, rồi `{ack: n}` sau mỗi khung và `{overlay}` sau mỗi tick model | Đo trực tiếp từ điện thoại không qua WebRTC (mục 4). Query là `PhoneSettings` `{d, f_mm \| hfov, auto_focal?, pitch?}`; đóng mã 1008 khi chưa đăng nhập hoặc thông số sai |
| `POST` | `/api/phone/clip-result` | `{id}` | Kết quả từng khung khi `/phone` chạy một video có sẵn trên GPU điện thoại; JSON tối đa 8 MB, lưu `runs/<dir>/phone_clips/<id>.json` để so với Lái thử (`scripts/roadwatch/compare_phone_clip.py`). Không có trong OpenAPI |
| `POST` | `/api/bench/result` | `{logged: true}` | Nhật ký đo của trang điện thoại (CPU/GPU, thời gian model, lỗi WebGPU); JSON tối đa 64 KB, ghi `runs/<dir>/bench.jsonl`. Không có trong OpenAPI |
| `DELETE` | `/api/rtc/{peer_id}` | `RtcClosed` | Đóng peer và giải phóng socket/encoder; gọi lại vẫn trả `{closed: true}` |
| `GET` | `/api/stream` | MJPEG | Video đã chú thích; đặt làm `src` của `<img>` |
| `GET` | `/api/frame` | `image/jpeg`, `204` khi chưa có khung | Khung đã chú thích mới nhất, từng ảnh một; giữ cho công cụ và giao diện cũ. Web app dùng WebRTC |
| `GET` | `/api/lab/segments` | `LabSegment[]` | Segment comma2k19 trên máy (`RW_LAB_DIR`) cho trang Lab |
| `POST` | `/api/lab/segments/{seg_id}/run` | `LabStatus` | Chạy BT-A trên cả segment như `app.py` của comma_ai/lead_distance: `bumper` (camera tới radar, mặc định 1,52 m), `fy` (mặc định 910 px), `log` (dùng tốc độ CAN), `wide` (`dup` mặc định: đầu vào camera rộng là ảnh hẹp nhân đôi; `warp`). Góc camera ước lượng trên 300 frame đầu, chỉ áp yaw, cố định cả lần chạy; 409 nếu đang chạy segment khác |
| `POST` | `/api/lab/stop` | `Stopping` | Dừng segment đang chạy, kể cả trong lượt hiệu chỉnh góc; trạng thái thành `stopped`, kết quả đã lưu trước đó giữ nguyên |
| `GET` | `/api/lab/status` | `LabStatus` | Tiến độ: `done` / `total` frame, trong đó `calib_frames` frame đầu là lượt hiệu chỉnh góc; trong lượt đó `calib_rpy_deg` là [roll, pitch, yaw] ước lượng đến lúc này (chỉ yaw được áp) và `calib_settled` cho biết đã đủ mẫu |
| `GET` | `/api/lab/segments/{seg_id}/result` | `LabResult` | Kết quả đã lưu, một giá trị mỗi frame; `rpy_deg` là góc ước lượng, `rpy_applied_deg` là góc đã áp (chỉ yaw) |
| `GET` | `/api/lab/live?since=n` | `LabLive` | Giá trị từng frame của segment Lab đang chạy, từ frame `n` (chỉ frame đủ cột); trang Lab vẽ biểu đồ trực tiếp từ đây |
| `GET` | `/api/lab/segments/{seg_id}/video` | MP4 | Video đã chú thích của kết quả đã lưu (tua được); 404 nếu segment chưa chạy |
| `GET` | `/api/lab/frame` | `image/jpeg`, `204` khi chưa có khung | Khung mới nhất của segment Lab đang chạy: khung thô trong lượt hiệu chỉnh góc, khung đã chú thích sau đó |
| `GET` | `/api/phrases/{kind}` | WAV | Âm báo; `kind` ∈ `chime` (chuông), `info`, `warning` (giọng thu sẵn), `emergency` (ba tiếng bíp) |
| `GET` | `/api/runs` | `RunInfo[]` | Lịch sử lần chạy, mới nhất trước |
| `GET` | `/api/runs/{run_id}/files/{name}` | MP4, JSON hoặc CSV | `annotated.mp4` (tua được), `decisions.json`, `run.json`, `lead_distance.csv`, `calibration.json`, `gps.csv` (chỉ lần đo từ điện thoại) |
| `DELETE` | `/api/runs/{run_id}` | `Deleted` | Xóa lần chạy và video đã tải lên; 409 nếu đang chạy |

## 3. Tải video và chạy

Thân request là **bytes của file video** (không dùng multipart). Tham số đi trên query:

| Tham số | Bắt buộc | Ràng buộc | Ý nghĩa |
|---|---|---|---|
| `name` | Có | đuôi `.mp4 .mov .mkv .avi .hevc .h264 .webm` | Tên file gốc |
| `fps` | Có | 0 < `fps` ≤ 240 | Tốc độ khung lúc quay. Model đo vận tốc từ thời gian giữa hai khung, nên fps sai thì tốc độ sai theo tỉ lệ. Khi file cho biết tốc độ khung (không phải luồng thô `.hevc`, `.h264`) và `fps` lệch quá 5 %, `calibration.flags` có `fps_differs_from_video` |
| `d` | Có | 0 ≤ `d` ≤ 5 | Khoảng cách camera tới cản trước (m) |
| `fy` | Một trong ba | 0 < `fy` ≤ 10000 | Tiêu cự (px); có thì bỏ qua `lens` |
| `lens` | Không | `mm` (mặc định) / `px` / `fov` / `learn` | Cách cho tiêu cự khi không có `fy`: tiêu cự mm hoặc góc nhìn; `learn` tự học từ video, chỉ khi chọn. Mặc định phải nhập tay: không có `fy`, `f_mm` hay `hfov` (và không chọn `learn`) thì API trả 422 |
| `f_mm` | Khi `lens=mm` | 0 < `f_mm` ≤ 300 | Tiêu cự (mm), tương đương 35 mm nếu không có `sensor_mm` |
| `sensor_mm` | Không | 0 < `sensor_mm` ≤ 40 | Cạnh dài cảm biến (mm); có thì `f_mm` là tiêu cự thật |
| `hfov` | Khi `lens=fov` | 20 ≤ `hfov` ≤ 170 | Góc nhìn ngang của vùng ảnh camera (độ) |
| `fisheye` | Không | `false` (mặc định) / `true` | Ống kính fisheye (mô hình equidistant) cho `hfov` |
| `gps` | Không | 12 ký tự hex | `gps_id` từ `POST /api/gps`; log được chuyển vào thư mục lần chạy |
| `gps_offset` | Không | -600 ≤ `gps_offset` ≤ 3600 | Giờ GPS lúc video t = 0 (s, tính từ điểm GPS đầu); bỏ trống thì bằng 0: log được coi là bắt đầu cùng video và dùng thẳng, không có bước đồng bộ |
| `auto_focal` | Không | `false` (mặc định) / `true` | Thử nghiệm: hiệu chỉnh tiêu cự theo tốc độ GPS (cần `gps`) |
| `crop` | Không | `auto` (mặc định) / `full` / `x,y,w,h` | Vùng ảnh camera: tự bỏ viền đen, toàn khung, hoặc tự nhập |
| `pitch` | Không | `true` (mặc định) / `false` | Áp góc pitch tự hiệu chỉnh vào warp |
| `rt` | Không | `true` (mặc định) / `false` | Phát theo thời gian thực (tốc độ video gốc) hay nhanh nhất có thể |
| `preview_every` | Không | 1 ≤ `preview_every` ≤ 10, mặc định 2 | Làm mới khung xem trực tiếp (`/api/frame`, `/api/stream`) mỗi N khung video; nhỏ thì mượt hơn nhưng tốn CPU hơn |

Lỗi: 400 file rỗng, 404 không có `gps` này, 413 quá `RW_MAX_UPLOAD_MB`, 415 không phải video, 422 tham số sai.

Tham số ống kính, GPS và Nâng cao theo trang upload của `comma_ai/lead_distance` (`pages/Upload_video.py`, `realtime_lead.py`). Khi có log GPS, tốc độ xe mình lấy theo GPS ở mọi nơi ngay từ khung đầu: HUD và ngưỡng cảnh báo. Log được coi là bắt đầu cùng video (độ lệch `gps_offset` mặc định 0) và dùng thẳng, không có bước đồng bộ; log bắt đầu lệch so với video thì phải nhập `gps_offset`, nếu không ngưỡng cảnh báo dùng tốc độ sai giờ.

**Log GPS:** `POST /api/gps?name=<tên file>`, thân request là bytes của file `.gpx .nmea .txt .log .csv` (tối đa 20 MB). Server đọc thử ngay và trả `GpsUploaded` {`gps_id`, `fixes`, `duration_s`}; 400 nếu không đọc được, 415 sai đuôi. Mỗi `gps_id` dùng cho một lần chạy.

```javascript
const r = await fetch(`/api/runs?${new URLSearchParams({name: file.name, fps: 30, d: 1.5})}`,
                      {method: 'POST', body: file});
if (!r.ok) alert((await r.json()).detail);
const {run_id} = await r.json();
```

## 4. Đo trực tiếp từ điện thoại

Trang `/phone` (cần đăng nhập) dùng camera sau và GPS của điện thoại thay cho file video và log GPS. Có hai chế độ: **chạy trên điện thoại** (mặc định, offline; model và BT-A/BT-B chạy bằng JS trên GPU điện thoại, không gửi ảnh; README mục 6) và **gửi về server** (mô tả dưới đây):

- **Hai đường kết nối**, chọn trên trang:
  - **Qua trang web** (mặc định): WebSocket `/api/phone/ws` trên chính kết nối HTTPS của trang. Tin nhị phân là ảnh JPEG của camera sau (trang gửi rộng 640 px, chất lượng 0,7); tin văn bản là một tin GPS. Server trả `{ack: n}` sau mỗi khung. Trang giới hạn số khung chưa được ack (tối đa 12, và ngừng gửi thêm khi khung cũ nhất chờ lâu hơn vòng đi về thấp nhất cộng 250 ms), nên mạng chậm thì gửi ít khung hơn chứ không dồn hàng đợi. Sau mỗi tick model, server gửi `{overlay: {frame, lane, path, lead}}`: `lane` là `{left, right}`, mỗi bên là danh sách `[u, v]` từ gần ra xa; `path` cùng dạng với `lane`, là dải dọc theo hướng đi dự đoán từ chuyển động của xe (độ cong = tốc độ quay / tốc độ, từ `pose` của model); `lead` là `{u, v, dist_m, close}`; `u`, `v` là tỉ lệ 0–1 của khung ảnh; `null` khi không có. Trang vẽ thảm làn và tam giác xe dẫn đầu lên camera trực tiếp, cùng hình học với HUD của video đã chú thích. Đi được qua 4G, VPN và proxy chỉ cho HTTPS.
  - **WebRTC**: `POST /api/phone/offer`, một `RTCPeerConnection` có track video `sendonly` và data channel `gps`; server gửi lại trên data channel đó `{frame, lane, path, lead}` sau mỗi tick model (cùng nội dung `overlay` ở trên). Ít dữ liệu hơn nhưng thường chỉ nối được khi hai máy cùng mạng.
- **Tin GPS** là JSON `{speed, lat, lon, acc}` lấy từ `navigator.geolocation`: `speed` tính bằng m/s, `null` hoặc âm nghĩa là không biết; `acc` tính bằng mét. Safari chỉ cho dùng camera và vị trí khi trang là HTTPS.
- **Đồng hồ.** Server gắn thời gian lúc khung hoặc tin GPS tới, tính bằng giây từ lúc nhận offer (đồng hồ phiên). Không dùng giờ của điện thoại. `t_s` trong `LiveStatus` theo đồng hồ này.
- **Khung hình.** Server chỉ giữ khung mới nhất và đưa vào model khoảng 50 ms một lần. Khung bị thay trước khi được dùng thì bỏ. Nếu độ phân giải đổi giữa chừng, khung được co về cỡ khung đầu. Khung dọc (cao hơn rộng) làm lần chạy lỗi: cần xoay ngang điện thoại.
- **Tốc độ.** Lấy tin GPS mới nhất còn mới (≤ 3 s). Tin có `acc` > 50 m bị bỏ. Không có `speed` thì tính từ vị trí của tin trước. Quá 3 s không có tin thì không có tốc độ GPS.
- **Màn đo.** Video camera hiện ở kích thước thật (`object-fit: contain`); một khung góc trên trái như HUD của Lái thử hiện khoảng cách `lead.gap_m` ± `lead.gap_std_m`, tốc độ ước lượng từ ảnh `model_kmh` và tốc độ GPS. Tốc độ GPS lấy thẳng từ `navigator.geolocation` trên điện thoại, không qua server, nên hiện ngay cả khi server chưa đồng bộ GPS.
- **Kết thúc.** Lần chạy kết thúc khi điện thoại ngắt kết nối, khi gọi `POST /api/stop` (server đóng kết nối của điện thoại), hoặc khi không có khung nào trong 10 s. Phiên được lưu như video tải lên, thêm `gps.csv` (`t, speed_mps, lat, lon, accuracy_m`); `run.json` có `source: "phone"`.

## 5. Nhận kết quả theo từng khung

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

## 6. `LiveStatus`

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `api_version` | string | |
| `state` | `idle` \| `loading` \| `running` \| `done` \| `stopped` \| `failed` | |
| `run_id` | string \| null | 12 ký tự hex |
| `error` | string \| null | Có khi `failed` |
| `measure` | `Measurement` \| null | BT-A; `null` trước khung đầu |
| `decision` | `Decision` \| null | BT-B |
| `ops` | `Ops` \| null | Vận hành: tốc độ xử lý, latency, số câu nói |
| `sample` | `Sample` \| null | Một điểm đồ thị của khung này |
| `events` | `SpokenEvent[]` | 30 câu đã nói gần nhất, cũ trước |
| `outputs` | `Outputs` \| null | Có khi `done` hoặc `stopped`: `video_url`, `log_url`, `csv_url` (`lead_distance.csv`, một dòng mỗi tick, cột như comma `realtime_lead`), `calibration_url` |

**`Measurement` (BT-A):** `frame` (khung video của tick model; model chạy mỗi n khung, gần 20 Hz), `t_s`, `ego_kmh`, `ego_source` (`gps` / `model`), `model_kmh` (tốc độ ước lượng chỉ từ ảnh, làm mượt như `ego_kmh`; vẫn gửi khi `ego_kmh` theo GPS), `gps` {`state`: `none` / `syncing` / `synced` / `low_confidence`, `offset_s`, `corr`}, `lead_raw_m` (khoảng cách thô của model ở tick này), `ttc_s` (null trừ khi đang áp sát và giá trị < 10 s), `lead` {`prob`, `gap_m`, `speed_kmh`, `gap_std_m` (độ lệch chuẩn của model cho khoảng cách, phần ± hiển thị; null khi không có xe)}, `calibration` {`status`, `calibrated`, `flags`, `fy_px`, `fy_state`, `pitch_deg`, `yaw_deg`, `height_m`, `coverage`, `remounts`}.

- `calibration.status`: `calibrating k/40` (k mẫu hiệu chuẩn góc đã nhận), `calibrated` hoặc `unreliable: <lý do>`.
- `calibration.calibrated = true` nghĩa là đã cho phép cảnh báo khoảng cách: góc lắp đã hội tụ và đã biết `fy`.

**`Decision` (BT-B):** `level` (mức đang hiệu lực hoặc null), `say` (câu phát **ở chính khung này**, null là im lặng), `reason` (lý do nói hay im lặng, tiếng Việt), `threshold_m` (ngưỡng cảnh báo ở tốc độ hiện tại: khoảng cách theo luật từ 60 km/h, quãng đường 2 s dưới 60 km/h và trên 100 km/h; null dưới 20 km/h), `latency_us`.

**`Ops`:** `fps` (khung xử lý mỗi giây), `video_fps` (fps của video; `fps` ≥ `video_fps` là theo kịp thời gian thực), `latency` {`last_ms`, `p50_ms`, `p95_ms`}, `bad_frames`, `raw_onsets` và `said`, mỗi trường là {`chime`, `info`, `warning`, `emergency`}. `raw_onsets` đếm số lần nói nếu không có điều phối, `said` đếm số lần thật sự nói; so hai số này là ra mức "ít nói hơn".

Schema đầy đủ, gồm ràng buộc từng trường: [openapi.json](../../src/roadwatch/openapi.json), mục `components.schemas`.

## 7. WebRTC cho video trực tiếp

Web app dùng một `<video autoplay muted playsinline>` nhận track WebRTC từ server. Server giữ khung BGR đã chú thích mới nhất ở mọi frame; mỗi người xem lấy khung mới nhất, tối đa 30 FPS và rộng tối đa 640 px, không xếp hàng khung cũ. `preview_every` vẫn chỉ điều khiển JPEG cho `/api/frame` và `/api/stream`. Số đo và câu cảnh báo tiếp tục qua `/api/ws`; WebRTC không thay đổi BT-A, BT-B hay nội dung video đã ghi.

Phiên đăng nhập bảo vệ signaling và cấu hình ICE; cookie gửi cùng nguồn. Peer không kết nối trong 30 giây được đóng; đổi run, kết thúc run, đóng trang và dừng server cũng giải phóng peer. Giao diện thử nối lại sau mất kết nối và hiện lỗi nếu mạng không cho truyền video trực tiếp.

HTTPS tunnel chỉ chở signaling; media đi qua ICE/UDP hoặc TURN. `RW_RTC_ICE_SERVERS` là JSON array của `{urls: ["stun:…"], username?, credential?}`; mặc định STUN Cloudflare, `[]` để chỉ dùng LAN/offline. Khi NAT chặn kết nối trực tiếp, cần TURN; không mặc định có relay công khai.

## 8. Video mẫu

Server đọc video mẫu từ `RW_SAMPLES_DIR` (mặc định `runs/samples/`). Mỗi mẫu có `<id>.mp4` và `<id>.json`; ID gồm chữ thường ASCII, chữ số, dấu gạch ngang hoặc gạch dưới, tối đa 40 ký tự. Chỉ các cặp file đủ video và metadata được liệt kê.

JSON chứa `title`, `note` tùy chọn, `fps`, `d` và `fy` tùy chọn. `fps`, `d`, `fy` dùng cùng giới hạn với API upload ở mục 3; không nhận NaN hoặc vô cực. Khi bỏ `fy`, API trả `null` và lần chạy dùng tiêu cự do người dùng nhập, hoặc tự học nếu chọn `lens=learn`.

`POST /api/samples/{sample_id}/run` nhận `rt` tùy chọn; ID không có trong danh sách trả 404. Video được hard-link hoặc sao chép vào thư mục riêng của lần chạy. Xóa lần chạy không xóa bản video mẫu.

## 9. Yêu cầu với giao diện

- Tài xế không bao giờ phải nhìn màn hình (nguyên tắc BT-B): âm thanh là kênh chính, màn hình chỉ phụ trợ.
- Phát `/api/phrases/{decision.say}` ngay khi nhận tin có `say` khác null.
- Không tự suy ra cảnh báo từ `measure`: quyết định nói hay không là của BT-B (`decision`).
- Hiển thị `null` thành "—", không thành `0`.

## 10. Lịch sử phiên bản

| Phiên bản | Thay đổi |
|---|---|
| 2.0.0 | Theo [kế hoạch nhắc khoảng cách](../warning_to_do.md): BT-B chỉ theo khoảng cách; `BtBConfig` bỏ tham số TTC, ân hạn, cooldown, thay bằng tham số nhắc sớm, nhắc lại, giảm nhanh; thêm mức `chime` vào `Level` và `AlertCounts`; `Decision.threshold_m` là ngưỡng cảnh báo ở tốc độ hiện tại |
| 1.9.0 | Đo trực tiếp từ điện thoại: `POST /api/phone/offer`, `WS /api/phone/ws`; `POST /api/lab/stop`; `Measurement.model_kmh`, `Measurement.gps_kmh`, `radar_m`; `POST /api/radar` và tham số `radar` của `POST /api/runs`; `Lead.gap_std_m`; `LabResult.curv_gt`, `curv_yaw`, `curv_drawn` (độ cong 1/km, + = trái; có `curv_gt` khi segment có `gt.csv`) cùng ở `LabLive` |
| 1.8.0 | Chọn vai trò khi đăng ký |
| 1.7.0 | Tài khoản cục bộ và phiên đăng nhập |
| 1.6.0 | Signaling WebRTC cho video live |
| 1.5.0 | `calib_rpy_deg`, `calib_settled` trong `LabStatus`; `/api/lab/frame` có hình trong lượt hiệu chỉnh góc |
| 1.4.0 | Lab trực tiếp, `preview_every`, `Ops.video_fps`, tham số `wide` và hiệu chỉnh góc của Lab như `app.py` của comma_ai/lead_distance |
| 1.3.0 | Log GPS, thông số ống kính và kết quả theo comma_ai/lead_distance (mục 3) |
| 1.2.0 | `GET /api/frame` |
