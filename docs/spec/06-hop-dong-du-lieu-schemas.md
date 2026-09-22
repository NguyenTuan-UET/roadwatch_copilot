# Đặc tả Hệ thống (Spec) — Phần 6: Hợp đồng Dữ liệu & Schemas
> Nguồn: Tách từ trafficeye-spec.md (Mục 6.1, 6.2, 6.3, 6.4, 6.8) tuân thủ SDLC Bước 4: Data Schemas
> Bao gồm: Cấu hình nút giao YAML, Ngưỡng đóng băng, JSON sự kiện Edge->Hub, Manifest gói bằng chứng.

## 6. Hợp đồng dữ liệu và giao tiếp (chốt từ M0)

### 6.1 Cấu hình cảnh v2 — `configs/scenes/<camera_id>.yaml`

Tương thích ngược với M1: bộ đọc M1 chỉ dùng `camera_id`, `count_line`, `classes` và bỏ qua các khóa khác. Tọa độ tính bằng pixel trên khung đã chuẩn hóa (H-02).

```yaml
camera_id: cam-01
intersection_id: int-A              # nút giao mà camera này nhìn; dùng cho FR-DEN-4 và cấu hình tuyến (mục 6.8)
frame_size: [1920, 1080]
location: {lat: 21.0285, lon: 105.8542, name: "Nút giao X — hướng Bắc"}  # cho bản đồ (FR-UI-3)
homography:                     # tùy chọn; ≥ 4 cặp điểm ảnh ↔ mặt đường (mét); cần cho tốc độ và điểm đầu xe (H-05)
  image: [[812, 1010], [1455, 1004], [1260, 640], [930, 642]]
  ground: [[0, 0], [7, 0], [7, 30], [0, 30]]
count_line: {id: line-1, a: [0, 900], b: [1920, 900]}     # như M1
classes: {2: car, 3: motorcycle, 5: bus, 7: truck}         # lớp được đếm (như M1)
extra_detect_classes: {0: person}                          # chỉ để che mặt và loại trừ B4, không đếm
lights:
  - id: head-N
    roi: [1500, 80, 1560, 240]
    bulbs: {red: [1500, 80, 1560, 130], yellow: [1500, 135, 1560, 185], green: [1500, 190, 1560, 240]}
lanes:
  - id: L1
    polygon: [[300, 1080], [760, 1080], [900, 600], [760, 600]]
    direction: [0, -1]              # hướng được phép đi, trên ảnh (lên trên = đi xa camera); dùng cho WW
    allowed_classes: [motorcycle]   # LN-a; bỏ trống = mọi lớp
    allowed_exits: [right]          # LN-c; left | straight | right | u_turn
    light: head-N
    right_turn_on_red: false        # C3
  - id: L2
    polygon: [[760, 1080], [1500, 1080], [1260, 600], [900, 600]]
    direction: [0, -1]
    allowed_classes: []
    allowed_exits: [straight, left]
    light: head-N
    right_turn_on_red: false
stop_lines:
  - {lanes: [L1, L2], a: [300, 700], b: [1500, 700]}
dividers:                           # vạch giữa các làn
  - {between: [L1, L2], polyline: [[760, 1080], [830, 700]], type: solid}    # solid: cấm chuyển làn (LN-b)
  - {between: [L1, L2], polyline: [[830, 700], [900, 600]], type: dashed}
intersection_zone: [[200, 600], [1700, 600], [1700, 150], [200, 150]]       # M-03
exits:                              # cạnh ra khỏi vùng giao lộ → hướng đi (LN-c, RL)
  - {direction: left, segment: [[200, 600], [200, 150]]}
  - {direction: straight, segment: [[200, 150], [1700, 150]]}
  - {direction: right, segment: [[1700, 150], [1700, 600]]}
wrong_way_zones:                    # phần đường một chiều không mô hình hóa thành làn (WW)
  - {id: shoulder-N, polygon: [[1500, 1080], [1700, 1080], [1600, 700], [1400, 700]], direction: [0, -1]}
no_stop_zones:                      # FR-VIO-ST
  - {id: box, polygon: [[200, 600], [1700, 600], [1700, 150], [200, 150]]}
rules:                              # bật hoặc tắt từng luật tại nút này; ngưỡng nằm trong configs/frozen/*.yaml
  red_light: true
  wrong_way: true
  lane_class: false                 # nút này không có làn riêng; LN-a bật ở nút nào trên tuyến có làn riêng theo loại xe
  lane_solid_line: true
  lane_exit: true
  illegal_stop: false
```

**Kiểm tra khi nạp** (22/09; học từ bước kiểm hình học trước khi lưu trong Calibration Studio của đối thủ). Nếu cấu hình sai, edge không khởi động và báo lỗi rõ ràng, giống bộ đọc M1. Các lỗi bị chặn:
- polygon có ít hơn 3 điểm, hoặc có điểm nằm ngoài `frame_size`;
- `id` làn bị trùng;
- `light`, `between`, `stop_lines[].lanes` trỏ tới `id` không tồn tại;
- `direction` là vector 0;
- `homography` có ít hơn 4 cặp điểm;
- `allowed_exits` có hướng không có trong `exits`.

Cách làm:
- Schema khai báo bằng Pydantic, đã có sẵn cùng FastAPI.
- Có lệnh vẽ cấu hình lên một khung của video để soát bằng mắt. Mọi PR đổi cấu hình cảnh phải đính kèm ảnh này. Đây chính là bước "kiểm tra cấu hình bằng clip thử trước khi bật luật" của W7 và L6 (`false-positives.md`).
- Giao diện vẽ trên web (FR-UI-9) chỉ ở mức COULD, vì MVP chỉ có 3 camera.

Quan hệ trước/sau giữa các nút không khai báo ở đây; nó nằm trong cấu hình tuyến (mục 6.8).

### 6.2 Ngưỡng đóng băng — `configs/frozen/rl-v1.yaml`

Giá trị dưới đây là **điểm khởi đầu**. Ngưỡng được chỉnh bằng leave-one-video-out trên dev, rồi đóng băng ngày 11/10. SHA-256 của file được ghi trong báo cáo đánh giá.

```yaml
model: {weights: yolo26n.pt, imgsz: 640, format: tensorrt-fp16}
processing_fps: 15
light: {min_stable_frames: 3, vote_window: 5}
quality: {min_track_frames: 10, max_interpolated_ratio: 0.2}
red_light: {grace_s: 0.8, confirm_zone_s: 2.0, front_margin_m: 0.5}
wrong_way: {window_s: 1.5, min_angle_deg: 135, min_distance_m: 5.0, min_speed_kmh: 8, min_windows: 2}
lane_class: {min_dwell_s: 2.0, min_distance_m: 10.0, min_class_vote: 0.8}
lane_solid_line: {min_dwell_after_s: 1.0}
lane_exit: {min_entry_frames: 5}
congestion: {speed_ratio: [0.7, 0.4, 0.2], occupancy: [0.3, 0.6, 0.8], sustain_min: 3, cycle_failure_k: 2}
```

Ngưỡng của phân tích tuyến (FR-COR-1, FR-COR-2) nằm ở file riêng, đóng băng cùng ngày và cùng tag:

```yaml
# configs/frozen/corridor-v1.yaml
period_min: 15
min_valid_cycles: 5
blocked_discharge_ratio: 0.3        # có hàng chờ mà xe thoát < 30% tốc độ bão hòa
spillback_consecutive_cycles: 2
spillback_match_cycles: 1           # B phải tắc trong khoảng ± 1 chu kỳ
bottleneck: {x_min: 0.9, failure_rate_min: 0.5}
```

### 6.3 Sự kiện edge → trung tâm

**Vỏ chung** — giữ nguyên từ contract v1 (plan M1, TASK-001):

```text
schema_version, event_id (UUIDv7), seq, device_id, camera_id, type,
captured_at, processed_at, source (live | replay), payload
```

Trong v1, `type` chỉ có `count`. Spec v1.0 thêm các loại dưới đây; thêm loại mới là thay đổi không phá vỡ.

| `type` | Tần suất | Payload | Từ |
|---|---|---|---|
| `count` v1.1 | Mỗi phút | Như v1; mỗi dòng trong `rows` thêm `lane_id` (tùy chọn, mặc định `null`) | CP1 |
| `density` v1 | Mỗi phút | `{"bucket_seconds": 60, "lanes": [{"lane_id": "L1", "flow": 14, "occupancy_avg": 3.2, "speed_kmh_avg": 18.5, "queue_len_max": 7, "congestion_level": 1}]}` | CP1 |
| `congestion` v1 | Khi xảy ra | `{"lane_id": "L1", "level": 3, "cause": "cycle_failure", "started_at": "...", "residual_queue_cycles": 3}` | CP1 |
| `signal_cycle` v1 | Mỗi chu kỳ đèn (khoảng 1–2 phút) | Xem ví dụ dưới bảng | CP1 |
| `violation_candidate` v1 | Khi xảy ra | Xem ví dụ dưới bảng | CP1 |
| `rejection_summary` v1 | Mỗi phút | `{"bucket_seconds": 60, "counts": [{"rule": "red_light", "reason": "A1", "n": 3}]}` | CP1 |
| `health` v1 | Mỗi 10 giây | `{"fps": 15.2, "dropped_frames": 0, "lag_s": 0.3, "outbox_depth": 0, "cpu_pct": 41, "gpu_pct": 55, "ram_mb": 2100, "temp_c": 62, "model_version": "yolo26n-8.4.157-trt-fp16", "config_sha256": "...", "uptime_s": 3600, "manual_mode": false, "desired_revision": 42}`. Hai trường cuối là trạng thái edge **đang áp dụng** (mục 6.7) | CP1 |
| `ota_status` v1 | Khi xảy ra | `{"release_id": "...", "state": "applied", "reason": null}`; `state` ∈ `downloaded`, `applied`, `committed`, `rolled_back`, `rejected` | CP2 |

Ví dụ payload của `violation_candidate` v1:

```json
{
  "violation": "red_light",
  "track_id": 1834,
  "vehicle_class": "motorcycle",
  "lane_id": "L2",
  "t_event": "2026-10-05T08:15:03.400+00:00",
  "frame_index": 12345,
  "bbox": [820, 610, 900, 720],
  "conditions": {"light_state": "RED", "red_elapsed_s": 2.4, "entered_zone_after_s": 1.1},
  "context": {"density_level": 1, "manual_mode": false, "priority_window": false},
  "config_sha256": "…",
  "model_version": "yolo26n-8.4.157-trt-fp16",
  "evidence": {"package_id": "…", "variants": ["operator", "csgt"]},
  "ocr": {"text": "29B1-123.45", "confidence": 0.93}
}
```

Quy định cho payload trên:
- `violation` ∈ `red_light`, `wrong_way`, `lane_class`, `lane_solid_line`, `lane_exit`, `illegal_stop`.
- `frame_index` chỉ có khi nguồn là file (để khớp với nhãn khi đánh giá).
- `ocr` có thể là `null`. Trung tâm lưu `ocr` vào cột chỉ CSGT đọc được; API lọc trường này theo vai trò.

Ví dụ payload của `signal_cycle` v1 (FR-DEN-4):

```json
{
  "intersection_id": "int-A",
  "head_id": "head-N",
  "lane_ids": ["L1", "L2"],
  "cycle_start": "2026-10-05T17:15:03.400+00:00",
  "valid": true,
  "green_s": 32.0, "amber_s": 3.0, "red_s": 45.1,
  "arrivals":   {"motorcycle": 41, "car": 6, "bus": 0, "truck": 1},
  "departures": {"motorcycle": 37, "car": 5, "bus": 0, "truck": 1},
  "max_queue_veh": 23,
  "residual_queue_veh": 4,
  "discharge": {"counts": {"motorcycle": 30, "car": 4, "bus": 0, "truck": 1}, "duration_s": 17.5},
  "box_blocked_s": 0.0,
  "queue_overflow_s": 6.5
}
```

Quy định cho payload trên:
- `valid = false` khi trong chu kỳ có lúc đèn ở trạng thái `UNKNOWN`.
- Số xe gửi theo loại xe. Trung tâm tự đổi ra PCU (FR-COR-1), nên đổi hệ số PCU không cần cập nhật edge.
- Sự kiện tuyến (`spillback`, `bottleneck`) do **trung tâm** sinh, vì cần dữ liệu nhiều nút. Chúng không đi qua outbox; được lưu ở bảng riêng và phát qua SSE với loại `corridor_event`.

**Quy tắc phiên bản:**
- Thêm trường tùy chọn hoặc thêm `type` mới: giữ nguyên `schema_version`.
- Đổi nghĩa, đổi kiểu hoặc xóa trường: tăng `schema_version`. Trung tâm phải nhận được cả hai phiên bản cho tới khi mọi edge đã cập nhật.

### 6.4 Manifest của gói bằng chứng

```json
{
  "manifest_version": 1,
  "package_id": "0199b3c4-…",
  "event_id": "0199b3c4-…",
  "variant": "operator",
  "device_id": "edge-01",
  "camera_id": "cam-01",
  "violation": "red_light",
  "captured_at": "2026-10-05T08:15:03.400+00:00",
  "processed_at": "2026-10-05T08:15:05.100+00:00",
  "source": "replay",
  "files": [
    {"name": "key_1.jpg", "role": "light_red_vehicle_before_line", "t": "…", "sha256": "…"},
    {"name": "key_2.jpg", "role": "vehicle_after_line", "t": "…", "sha256": "…"},
    {"name": "key_3.jpg", "role": "plate_crop", "t": "…", "sha256": "…"},
    {"name": "clip/000.jpg", "role": "clip", "t": "…", "sha256": "…"}
  ],
  "parent_hash": "SHA-256 của bản đầy đủ đã niêm phong trên thiết bị",
  "config_sha256": "…",
  "model_version": "yolo26n-8.4.157-trt-fp16",
  "signing_key_id": "edge-01-2026-09",
  "signature": "base64 chữ ký Ed25519 trên JSON chuẩn hóa của manifest, không gồm trường signature"
}
```

- `variant` ∈ `operator`, `csgt`.
- Bản `operator` không có ảnh biển số rõ: `key_3.jpg` là ảnh đã che.



### 6.8 Cấu hình tuyến — `configs/corridors/<corridor_id>.yaml`

```yaml
corridor_id: cor-01
name: "Tuyến X, chiều Đông → Tây"
nodes:                      # xếp đúng theo chiều xe chạy mà camera nhìn
  - {intersection_id: int-A, camera_id: cam-01, link_to_next_m: 450}
  - {intersection_id: int-B, camera_id: cam-02, link_to_next_m: 380}
  - {intersection_id: int-C, camera_id: cam-03, link_to_next_m: null}
pcu: {motorcycle: 0.3, car: 1.0, truck: 2.5, bus: 3.0}   # TCVN 13592:2022 Bảng 3, cột 30–50 km/h
```

- Thứ tự trong `nodes` quyết định nút nào là "nút phía trước" trong quy tắc tràn hàng chờ (FR-COR-2).
- `link_to_next_m` đo trên bản đồ. Giá trị này dùng để hiển thị và giải thích (ví dụ "đoạn 450 m giữa A và B đã kín"), không dùng trong quy tắc.
- Bảng PCU có thể chỉnh; ghi rõ nguồn khi đổi.

---

