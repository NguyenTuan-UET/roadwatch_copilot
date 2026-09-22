# Đặc tả Hệ thống (Spec) — Phần 7: Hợp đồng API & Kênh Giao tiếp
> Nguồn: Tách từ trafficeye-spec.md (Mục 6.5, 6.6, 6.7) tuân thủ SDLC Bước 4: API Contracts
> Bao gồm: REST API trung tâm FastAPI, Giao diện Luật vi phạm Python, Kênh điều khiển hai chiều MQTT.

### 6.5 API trung tâm

| Phương thức, đường dẫn | Ai gọi | Mô tả | Từ |
|---|---|---|---|
| `POST /api/v1/events` | Thiết bị (token) | Nhận lô sự kiện mọi loại; chống trùng theo `event_id` | M1 → CP1 |
| `PUT /api/v1/evidence/{package_id}/{variant}` | Thiết bị | Tải gói bằng chứng (zip); kiểm SHA-256 với manifest | CP1 |
| `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh` | Người dùng | Trả JWT | CP1 |
| `GET /api/v1/cameras` | Mọi vai trò | Camera, vị trí, trạng thái | M1 → CP1 |
| `GET /api/v1/cameras/{id}/health` | Mọi vai trò | Heartbeat gần nhất | CP1 |
| `GET /api/v1/counts` | Mọi vai trò | Số đếm theo camera, làn, khoảng thời gian | M1 → CP1 |
| `GET /api/v1/density` | Mọi vai trò | Mật độ, hàng chờ, mức ùn tắc | CP1 |
| `GET /api/v1/intersections/{id}/performance` | Mọi vai trò | Theo khung 15 phút: q, s, g/C, X (kèm cờ `lower_bound`), độ trễ, LOS, % chu kỳ thất bại | CP1 |
| `GET /api/v1/corridors`, `GET /api/v1/corridors/{id}/status` | Mọi vai trò | Danh sách tuyến; ma trận nút × thời gian (mức ùn tắc, LOS) và các sự kiện tuyến | CP1 |
| `GET /api/v1/candidates`, `GET /api/v1/candidates/{id}` | operator, csgt | Hàng đợi, chi tiết; trường dữ liệu lọc theo vai trò | CP1 |
| `POST /api/v1/candidates/{id}/review` | operator (bước 1), csgt (bước 2) | Quyết định kèm mã lý do | CP1 |
| `GET /api/v1/evidence/{package_id}?variant=` | operator (bản che), csgt (bản CSGT, có ghi nhật ký) | Ảnh và clip | CP1 |
| `GET /api/v1/verify/{package_id}` | Công khai | Kết quả kiểm chữ ký và mã băm (không có ảnh) | CP1 |
| `GET /api/v1/audit` | admin, auditor | Nhật ký, kết quả kiểm chuỗi | CP1 |
| `POST /api/v1/stream/ticket` | operator, csgt | Đổi JWT lấy vé SSE: vé dùng một lần, hết hạn sau 30 giây, gắn với người dùng | CP1 |
| `GET /api/v1/stream?ticket=` | operator, csgt | SSE: ứng viên mới, ùn tắc, sự kiện tuyến, camera mất kết nối. Xác thực bằng vé (FR-AUTH-1). Vì vé chỉ dùng một lần, giao diện phải xin vé mới mỗi lần nối lại | CP1 |
| `POST /api/v1/reports`, `POST /api/v1/reports/{id}/approve` | operator, csgt | Agent soạn bản nháp; người duyệt để phát hành | CP1 |
| `GET /api/v1/cases/{id}/export` | csgt | Hồ sơ vi phạm (PDF + JSON) | CP1 |
| `POST /api/v1/candidates/{id}/explain`, `POST /api/v1/ask` | operator, csgt | Trợ lý giải thích; hỏi đáp số liệu | CP2 |
| `GET /api/v1/suggestions`, `POST /api/v1/suggestions/{id}/decision` | operator | Gợi ý điều phối | CP2 |
| `GET /api/v1/devices/{id}/desired` | Thiết bị | Trạng thái mong muốn (mục 6.7); edge hỏi mỗi 10 giây | CP1 |
| `PUT /api/v1/cameras/{id}/manual-mode` | operator | Bật hoặc tắt chế độ điều khiển tay; tăng `revision`; ghi nhật ký | CP1 |
| `POST /api/v1/releases`, `POST /api/v1/devices/{id}/rollout` | admin | Tải bản phát hành có ký; triển khai canary | CP2 |
| `GET /api/v1/public/counts` | Khóa API | Dữ liệu mở (FR-INT-3) | COULD |

### 6.6 Giao diện luật trên edge

```python
@dataclass(frozen=True)
class FrameContext:
    frame_index: int
    t: datetime                        # source time: file = frame_index / fps; live = wall clock
    tracks: list[Track]                # bottom centre, estimated front point (H-05), class votes
    lights: dict[str, str]             # head id -> RED | YELLOW | GREEN | FLASHING | OFF | UNKNOWN
    density_level: dict[str, int]      # lane id -> 0..3
    manual_mode: bool                  # operator switched the intersection to manual control
    priority_window: bool              # a priority vehicle was seen within +-T seconds


@dataclass(frozen=True)
class Candidate:
    violation: str                     # red_light | wrong_way | lane_class | lane_solid_line | lane_exit | illegal_stop
    track_id: int
    lane_id: str | None
    t_event: datetime
    frame_index: int
    bbox: tuple[float, float, float, float]
    conditions: dict[str, float | str] # measured values that satisfied the rule


@dataclass(frozen=True)
class Rejection:
    violation: str
    track_id: int
    reason_code: str                   # A1..E5, W1..W8, L1..L8, S1..S6


class Rule(Protocol):
    name: str

    def update(self, ctx: FrameContext) -> list[Candidate | Rejection]: ...
```

### 6.7 Kênh điều khiển: trạng thái mong muốn và MQTT

**Trạng thái mong muốn.** Endpoint: `GET /api/v1/devices/{device_id}/desired`. Có từ CP1; thiết bị gọi bằng token riêng.

```json
{
  "schema_version": 1,
  "revision": 42,
  "cameras": {"cam-01": {"manual_mode": false}},
  "config": null,
  "release": null
}
```

- Mỗi thay đổi (bật/tắt chế độ tay, triển khai cấu hình, triển khai bản phát hành) làm `revision` của thiết bị tăng 1. Edge chỉ áp dụng khi `revision` lớn hơn bản đang giữ, nên nhận trùng hay nhận lại đều không gây hại.
- `config` và `release`:
  - ở CP1 là `null`;
  - từ CP2 có dạng `{"id": "...", "sha256": "...", "url": "..."}`. Edge tải qua HTTPS, kiểm SHA-256 và chữ ký theo FR-OTA-1 rồi mới áp dụng.
- Edge báo lại trạng thái đang áp dụng qua sự kiện `health` (các trường `manual_mode`, `desired_revision`). Dashboard so với `revision` ở trung tâm để biết thay đổi đã tới thiết bị chưa.

**MQTT** — từ CP2 (FR-DEV-2):

| Topic | Chiều | Retained | QoS | Payload |
|---|---|---|---|---|
| `trafficeye/<device_id>/status` | edge → trung tâm | có | 1 | Khi kết nối: `{"state": "online", "ts": "..."}`. Last Will, cũng retained: `{"state": "offline"}`. Khi tắt có chủ đích, edge tự publish `offline` trước khi ngắt |
| `trafficeye/<device_id>/desired` | trung tâm → edge | có | 1 | `{"revision": 42}`, chỉ để báo có bản mới. **Không bao giờ** chứa cấu hình, model hay lệnh |

- **Broker:** Eclipse Mosquitto 2.x, thêm một container vào stack trung tâm.
  - Lý do chọn: nhẹ; có sẵn Last Will, retained message và ACL theo tên đăng nhập.
  - EMQX hay HiveMQ hợp với cụm broker lớn, thừa khi chỉ có ≤ 10 thiết bị.
- **Client:** paho-mqtt trên cả edge và backend; MQTT 5.
  - Keepalive 5 giây. Khi mất kết nối, broker phát Last Will chậm nhất khoảng 1,5 × 5 = 7,5 giây sau đó, đủ cho FR-DEV-2 AC1.
  - Mỗi lần kết nối bắt đầu phiên sạch (clean start). Không cần giữ phiên, vì `desired` là retained nên kết nối lại là nhận ngay bản mới nhất.
- **Bảo mật:**
  - TLS; tắt truy cập ẩn danh; mỗi thiết bị một tài khoản, tên đăng nhập là `device_id`.
  - ACL: thiết bị chỉ được ghi vào topic `status` và đọc topic `desired` của chính nó; tài khoản backend đọc mọi `status`, ghi mọi `desired`:

    ```text
    user backend
    topic read trafficeye/+/status
    topic write trafficeye/+/desired

    # %u = tên đăng nhập = device_id
    pattern write trafficeye/%u/status
    pattern read trafficeye/%u/desired
    ```

  - Kẻ chiếm được broker vẫn không đẩy được cấu hình giả: payload chỉ là số `revision`, còn nội dung lấy qua HTTPS và có chữ ký. Tệ nhất là thiết bị hỏi `desired` thừa vài lần, hoặc trạng thái online/offline sai tạm thời; heartbeat HTTPS vẫn là nguồn đối chiếu.
- **Mạng khi deploy lên cloud (WP-52):** edge luôn chủ động kết nối ra ngoài. Broker phải nhận được kết nối từ Internet, bằng một trong hai cách:
  - cổng 8883 (MQTT qua TLS);
  - MQTT qua WebSocket TLS ở cổng 443, nếu nền tảng cloud chỉ mở HTTP(S).

  Phải kiểm tra điểm này khi chọn nền tảng.

**Trạng thái thiết bị trên dashboard.** Một quy tắc dùng chung cho bản đồ (FR-UI-3), trang sức khỏe (FR-UI-5) và cảnh báo (NFR-OBS-1).

Khi backend đang kết nối được với broker:

| Điều kiện | Hiển thị |
|---|---|
| Quá 30 giây không nhận được `health` | Mất kết nối |
| Đã nhận Last Will `offline`, sau đó chưa có `health` mới | Mất kết nối |
| Đã nhận Last Will `offline`, nhưng sau đó vẫn có `health` mới | Hoạt động, mất kênh điều khiển |
| Hai sự kiện `health` nhận gần nhất đều có `outbox_depth` > 0 | Hoạt động, đang gửi bù. Hiện kèm mốc `captured_at` mới nhất đã nhận |
| Còn lại | Hoạt động |

- Nhận lại `online` thì bỏ trạng thái Last Will.
- Vì sao dòng "đang gửi bù" dựa vào `outbox_depth`:
  - `health` cũng đi qua outbox, nên sau khi có mạng lại, trung tâm nhận các `health` cũ trước; chúng đều có `outbox_depth` > 0.
  - Lúc chạy bình thường, sender gửi hết outbox trong vài giây, nên hiếm khi hai `health` liên tiếp cùng có `outbox_depth` > 0.
  - Trung tâm không biết chính xác còn bao nhiêu sự kiện chờ, nên hiển thị tiến độ bằng mốc `captured_at` mới nhất đã nhận, không hiện số lượng.
  - Ý tưởng lấy từ trạng thái `syncing` và `offline_buffer_count` của đối thủ.
- Mốc so sánh là thời điểm **trung tâm nhận** sự kiện, không phải `captured_at`, vì outbox có thể gửi bù sự kiện cũ.
- Khi backend mất kết nối tới broker, và trong toàn bộ CP1 (chưa có MQTT), chỉ dùng dòng đầu tiên và dòng "đang gửi bù". Nếu là do backend mất broker, dashboard hiện thêm băng "kênh điều khiển gián đoạn".

