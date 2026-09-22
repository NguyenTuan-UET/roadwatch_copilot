# M1 Skeleton — Phân Hệ Backend Trung Tâm & Outbox (Tasks 008 - 013)
> Phụ trách chính: TV4 (Khánh) / Hỗ trợ: TV2 (Tuấn). Gói việc: WP-05.
> Tuân thủ SDLC Bước 5: Implementation Task Cards (Chuẩn 150 - 250 dòng).

### TASK-008 · Outbox SQLite
| | |
|---|---|
| **Goal** | Sự kiện nằm trên đĩa cho tới khi trung tâm xác nhận; `seq` tăng dần và không bao giờ bị dùng lại |
| **Người · hạn** | Khánh · 23/09 |
| **Files** | Create `src/edge/outbox.py`, `tests/test_edge/test_outbox.py` |
| **Exact location** | Package `src/edge/`. Tạo `src/edge/__init__.py` và `tests/test_edge/__init__.py` (rỗng) nếu TASK-002 chưa tạo |
| **Depends on** | — |
| **Validate** | `pytest tests/test_edge/test_outbox.py -v` |
| **Expected** | `3 passed` |
**Interfaces — Produces:**
- `Outbox(path: Path)` với `.put(event: dict) -> int` (trả `seq`), `.peek(limit) -> list[dict]` (mỗi dict có thêm khóa `"seq"`), `.ack(up_to_seq)`, `len(outbox)`, `.close()`.
- Mỗi luồng mở một `Outbox` riêng, vì kết nối sqlite3 không được dùng chung giữa các luồng.
- [ ] **Step 1: Viết test** — `tests/test_edge/test_outbox.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — `src/edge/outbox.py`
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-009 · Sender HTTP, thử lại khi mất mạng
| | |
|---|---|
| **Goal** | Gửi theo thứ tự `seq`, chỉ xóa khỏi outbox khi trung tâm trả 2xx. Mất mạng thì thử lại, thời gian chờ nhân đôi tới tối đa 30 giây |
| **Người · hạn** | Khánh · 24/09 |
| **Files** | Create `src/edge/sender.py`, `tests/test_edge/test_sender.py` |
| **Exact location** | File mới |
| **Depends on** | TASK-008 |
| **Validate** | `pytest tests/test_edge/test_sender.py -v` |
| **Expected** | `4 passed` |
**Interfaces**
- Consumes: `Outbox` (TASK-008). Endpoint `POST /api/v1/events` với body `{"events": [...]}` và header `Authorization: Bearer <token>` (TASK-011). Ở đây endpoint được thay bằng server giả trong test.
- Produces (TASK-007 dùng):
- [ ] **Step 1: Viết test** — `tests/test_edge/test_sender.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — `src/edge/sender.py`
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-010 · Lớp dữ liệu trung tâm
| | |
|---|---|
| **Goal** | Tạo bảng `events`; ghi không trùng theo `event_id`; truy vấn số đếm và danh sách camera. Cùng một SQL chạy được trên PostgreSQL (Compose) và SQLite (test, chạy nhanh trên máy) |
| **Người · hạn** | Khánh · 24/09 |
| **Files** | Modify `requirements.txt`; Create `src/db.py`, `tests/test_db.py` |
| **Exact location** | `requirements.txt`, khối `# Database (uncomment as needed)`: thay hai dòng `# sqlalchemy>=2.0.0` và `# psycopg2-binary>=2.9.0` |
| **Depends on** | TASK-001 |
| **Validate** | `pytest tests/test_db.py -v` |
| **Expected** | `3 passed` |
**Interfaces — Produces** (TASK-011, 012 dùng):
- `get_engine() -> Engine`: có `lru_cache`, đọc `DATABASE_URL`.
- `init_db(engine)`: chạy lại nhiều lần vẫn an toàn.
- `insert_events(conn, events: list[CountEvent]) -> int`: trả số sự kiện mới.
- `count_buckets(conn, camera_id: str, limit: int) -> list[dict]`:
- `list_cameras(conn) -> list[dict]`: khóa `camera_id`, `last_seen`, `events`.
- Thời gian lưu dạng TEXT: UTC, chính xác tới mili giây, nên sắp xếp theo chuỗi cũng là theo thời gian, và giống nhau trên cả hai loại DB.
- [ ] **Step 1: Thêm thư viện** — trong `requirements.txt`, khối Database thành:
- [ ] **Step 2: Viết test** — `tests/test_db.py`
- [ ] **Step 3: Chạy test, xác nhận fail**
- [ ] **Step 4: Viết code** — `src/db.py`
- [ ] **Step 5: Chạy test, xác nhận pass**
- [ ] **Step 6: Commit**
---

---

### TASK-011 · API nhận sự kiện
| | |
|---|---|
| **Goal** | `POST /api/v1/events`: xác thực token thiết bị; `device_id` trong sự kiện phải khớp token; ghi không trùng; trả `accepted` và `duplicates` |
| **Người · hạn** | Khánh · 25/09 |
| **Files** | Modify `src/config.py`, `src/main.py`; Create `src/api/events.py`, `tests/test_api/test_events.py` |
| **Exact location** | `src/config.py`: dòng `app_name` và ngay sau `database_url`. `src/main.py`: thay toàn bộ file (nội dung ở Step 4) |
| **Depends on** | TASK-010 |
| **Validate** | `pytest tests/test_api -v` |
| **Expected** | `9 passed` (3 test cũ của template + 6 test mới) |
**Interfaces — Produces** (hợp đồng HTTP cho TASK-009):
- `POST /api/v1/events`, header `Authorization: Bearer <token>`, body `EventBatch`, trả `200` kèm `{"accepted": n, "duplicates": m}`.
- Mã lỗi: `401` nếu thiếu hoặc sai token; `403` nếu `device_id` khác thiết bị của token; `422` nếu sai schema.
- Cấu hình: `DEVICE_TOKENS="edge-01:token1,edge-02:token2"`.
- [ ] **Step 1: Viết test** — `tests/test_api/test_events.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Sửa cấu hình** — trong `src/config.py`:
- [ ] **Step 4: Viết code** — tạo `src/api/events.py`:
- [ ] **Step 5: Chạy test, xác nhận pass**
- [ ] **Step 6: Commit**
---

---

### TASK-012 · API cho dashboard
| | |
|---|---|
| **Goal** | `GET /api/v1/counts?camera_id=&limit=` và `GET /api/v1/cameras` |
| **Người · hạn** | Khánh · 25/09 |
| **Files** | Modify `src/api/events.py`, `tests/test_api/test_events.py` |
| **Exact location** | `src/api/events.py`: thay hai dòng import `fastapi` và `src.db`, rồi thêm code vào cuối file. Test: thêm vào cuối file |
| **Depends on** | TASK-011 |
| **Validate** | `pytest tests/test_api -v` |
| **Expected** | `10 passed` |
**Interfaces — Produces** (TASK-015 dùng):
- `GET /api/v1/counts?camera_id=cam-01&limit=30` (1 ≤ `limit` ≤ 1440) trả:
- `GET /api/v1/cameras` trả: `{"cameras": [{"camera_id": "cam-01", "last_seen": "2026-09-21T12:14:58.374+00:00", "events": 3}]}`
- [ ] **Step 1: Viết test** — thêm vào cuối `tests/test_api/test_events.py`:
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — trong `src/api/events.py`, đổi hai dòng import thành:
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Commit**
---

---

### TASK-013 · Docker Compose: PostgreSQL + backend
| | |
|---|---|
| **Goal** | `docker compose up` chạy PostgreSQL 17 và backend; backend tự tạo bảng; container trung tâm không được mount thư mục video thô |
| **Người · hạn** | Khánh · 26/09 |
| **Files** | Modify `docker-compose.yml` (viết lại), `.env.example`, `.dockerignore` |
| **Exact location** | `.env.example`: thay khối `# ---- Database ----` và thêm khối mới sau nó. `.dockerignore`: thêm vào cuối |
| **Depends on** | TASK-011 |
| **Validate** | Step 4 |
| **Expected** | Backend `healthy`; lần POST đầu trả `accepted 1`, lần sau trả `duplicates 1`; bảng `events` trong PostgreSQL có 1 dòng |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Viết lại `docker-compose.yml`**. Bỏ khóa `version:` (Compose v2 đã coi là lỗi thời):
- [ ] **Step 2: Sửa `.env.example`.** Thay 4 dòng của khối Database, từ `# ---- Database ----` tới `# DATABASE_URL=sqlite:///./data/app.db`, bằng:
- [ ] **Step 3: Không đưa video thô và `node_modules` vào image backend.** Thêm vào cuối `.dockerignore`:
- [ ] **Step 4: Chạy và kiểm tra** (Docker Desktop phải đang chạy)
- [ ] **Step 5: Commit**

---
