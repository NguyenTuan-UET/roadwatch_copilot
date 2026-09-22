# M1 Skeleton — Phân Hệ Edge: Nhận Diện & Đếm Xe (Tasks 002 - 007)
> Phụ trách chính: TV2 (Tuấn) / Hỗ trợ: TV1 (Cường). Gói việc: WP-04.
> Tuân thủ SDLC Bước 5: Implementation Task Cards (Chuẩn 150 - 250 dòng).

### TASK-002 · Hình học: điểm nằm phía nào, chuyển động có cắt đoạn thẳng không
| | |
|---|---|
| **Goal** | Hai hàm hình học thuần để biết một xe có cắt vạch đếm hay không |
| **Người · hạn** | Tuấn · 23/09 |
| **Files** | Create `src/edge/__init__.py` (rỗng), `src/edge/geometry.py`, `tests/test_edge/__init__.py` (rỗng), `tests/test_edge/test_geometry.py` |
| **Exact location** | Package mới `src/edge/`, thư mục test mới `tests/test_edge/`. Tạo hai file `__init__.py` rỗng nếu TASK-008 chưa tạo |
| **Depends on** | — |
| **Validate** | `pytest tests/test_edge/test_geometry.py -v` |
| **Expected** | `4 passed` |
**Interfaces — Produces:**
- `Point = tuple[float, float]`, tọa độ pixel: x sang phải, y xuống dưới.
- `side(a, b, p) -> int`: trả `+1` hoặc `-1` tùy phía của đường a–b, và `0` khi p nằm trên đường.
- `crosses_segment(p, q, a, b) -> bool`: chuyển động p → q có đi qua đoạn a–b không. Điều kiện: p và q nằm ở hai phía khác nhau của đường a–b.
- [ ] **Step 1: Viết test** — `tests/test_edge/test_geometry.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — tạo `src/edge/__init__.py` và `tests/test_edge/__init__.py` (hai file rỗng), rồi `src/edge/geometry.py`:
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-003 · Đếm xe cắt vạch (`LineCounter`)
| | |
|---|---|
| **Goal** | Mỗi track chỉ được đếm một lần, khi điểm giữa cạnh dưới bbox cắt vạch; biết xe đi hướng nào |
| **Người · hạn** | Tuấn · 23/09 |
| **Files** | Create `src/edge/counting.py`, `tests/test_edge/test_counting.py` |
| **Exact location** | File mới |
| **Depends on** | TASK-001 (`Direction`), TASK-002 |
| **Validate** | `pytest tests/test_edge/test_counting.py -v` |
| **Expected** | `7 passed` |
**Interfaces**
- Consumes: `Point`, `side`, `crosses_segment` (TASK-002); `Direction` (TASK-001).
- Produces:
- Quy ước hướng: "forward" là cắt vạch từ bên phải sang bên trái của vector a→b, nhìn trên ảnh. Vẽ vạch từ trái sang phải thì xe đi lên trên khung hình (đi xa camera quay từ phía sau) được tính là forward.
- [ ] **Step 1: Viết test** — `tests/test_edge/test_counting.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — `src/edge/counting.py`
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-004 · Gom số đếm theo phút và tạo sự kiện
| | |
|---|---|
| **Goal** | Gom số đếm vào bucket 60 giây theo giờ nguồn; tạo body sự kiện đúng contract; `event_id` là UUIDv7 |
| **Người · hạn** | Tuấn · 24/09 |
| **Files** | Modify `src/edge/counting.py`, `tests/test_edge/test_counting.py` |
| **Exact location** | Thay khối import ở đầu mỗi file, rồi thêm code vào cuối file |
| **Depends on** | TASK-003 |
| **Validate** | `pytest tests/test_edge/test_counting.py -v` |
| **Expected** | `10 passed` |
**Interfaces — Produces** (TASK-007 dùng):
- `Bucket = tuple[datetime, Counter[tuple[str, str]]]`, tức (giờ bắt đầu bucket, `(vehicle_class, direction) → số xe`).
- `BucketCounts(bucket_seconds=60)`:
- `uuid7() -> UUID`; `iso(t: datetime) -> str`.
- `make_count_event(*, device_id, camera_id, line_id, bucket, bucket_seconds, source) -> dict`: body sự kiện **chưa có `seq`**; outbox (TASK-008) thêm `seq` khi lưu.
- [ ] **Step 1: Viết test** — trong `tests/test_edge/test_counting.py`, thay dòng import đầu tiên `from src.edge.counting import LineCounter, Track` bằng:
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — trong `src/edge/counting.py`, thay khối import và dòng `Box = ...` ở đầu file bằng:
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-005 · File cấu hình cảnh (scene YAML)
| | |
|---|---|
| **Goal** | Đọc vạch đếm và danh sách lớp xe từ YAML; file sai thì báo lỗi rõ ràng |
| **Người · hạn** | Tuấn · 24/09 |
| **Files** | Modify `requirements.txt`; Create `src/edge/scene.py`, `configs/scenes/sample.yaml`, `tests/test_edge/test_scene.py` |
| **Exact location** | `requirements.txt`: thêm một dòng cuối khối `# Core` (sau `python-dotenv>=1.0.0`) |
| **Depends on** | TASK-002 |
| **Validate** | `pytest tests/test_edge/test_scene.py -v` |
| **Expected** | `6 passed` |
**Interfaces — Produces:**
- `Scene(camera_id: str, line_id: str, line_a: Point, line_b: Point, classes: dict[int, str])`
- `load_scene(path: Path) -> Scene`; file sai thì raise `ValueError`.
- [ ] **Step 1: Thêm thư viện** — trong `requirements.txt`, thêm dòng sau `python-dotenv>=1.0.0`:
- [ ] **Step 2: Viết test** — `tests/test_edge/test_scene.py`
- [ ] **Step 3: Chạy test, xác nhận fail**
- [ ] **Step 4: Viết code** — `src/edge/scene.py`
- [ ] **Step 5: Chạy test, xác nhận pass**
- [ ] **Step 6: Commit**
---

---

### TASK-006 · Bọc YOLO26 + ByteTrack
| | |
|---|---|
| **Goal** | Một lớp nhận vào khung hình, trả về danh sách `Track` (id, lớp xe, bbox), chỉ gồm các lớp khai báo trong scene |
| **Người · hạn** | Tuấn · 25/09 |
| **Files** | Create `requirements-edge.txt`, `src/edge/tracker.py`; Modify `.gitignore` |
| **Exact location** | `.gitignore`: thêm vào cuối file |
| **Depends on** | TASK-003 (`Track`), TASK-005; cần `data/samples/sample.mp4` (TASK-017 bước 2–3; cũng do Tuấn làm) |
| **Validate** | Lệnh smoke ở Step 4 |
| **Expected** | Một list 30 số nguyên, đa số lớn hơn 0 (lần chạy thử ngày 21/09 ra 3–5 xe mỗi khung) |
**Interfaces**
- Consumes: `Track` (TASK-003), `Scene.classes` (TASK-005).
- Produces: `YoloTracker(weights: str, classes: dict[int, str], imgsz: int = 640)`; gọi `tracker(frame) -> list[Track]`.
- [ ] **Step 1: Thêm thư viện edge** — tạo `requirements-edge.txt`:
- [ ] **Step 2: Không commit trọng số model** — thêm vào cuối `.gitignore`:
*.pt
- [ ] **Step 3: Viết code** — `src/edge/tracker.py`
- [ ] **Step 4: Chạy smoke** (lần đầu tự tải `yolo26n.pt`, 5,3 MB, về thư mục hiện tại)
- [ ] **Step 5: Commit**
---

---

### TASK-007 · Chương trình edge (CLI)
| | |
|---|---|
| **Goal** | Nối mọi phần: đọc video hoặc RTSP → track → đếm → bucket theo phút → outbox → luồng gửi. Log số đếm mỗi phút (điều kiện "Xong khi" của WP-04) |
| **Người · hạn** | Tuấn · 26/09 |
| **Files** | Create `src/edge/main.py` |
| **Exact location** | File mới |
| **Depends on** | TASK-004, 005, 006, 009; chạy đầu–cuối cần TASK-011 và 012 |
| **Validate** | Step 2–4 |
| **Expected** | Log có dòng `bucket ...` và `sent 1 events to central`; API `/counts` trả bucket có `total` > 0 |
**Interfaces**
- Consumes: `LineCounter`, `BucketCounts`, `make_count_event`, `Bucket` (003, 004); `load_scene` (005); `YoloTracker` (006); `Outbox` (008); `http_post`, `run_forever` (009); `POST /api/v1/events` (011).
- Produces: lệnh `python -m src.edge.main --source <file|rtsp://...> --scene <yaml> --token <token> [--replay]`.
- [ ] **Step 1: Viết code** — `src/edge/main.py`
- [ ] **Step 2: Chạy đầu–cuối với backend chạy trực tiếp (không cần Docker)**
- log có `processed 324 frames`;
- log có `bucket 2026-...: {('car', 'backward'): 4, ('car', 'forward'): 3, ('truck', 'backward'): 1} (seq 1)` và `sent 1 events to central`;
- `curl` trả `"total":8`.
- [ ] **Step 3: Kiểm tra khi mất mạng**
- [ ] **Step 4: Chạy trên RTSP** (sau TASK-017)
- [ ] **Step 5: Commit**
---

---
