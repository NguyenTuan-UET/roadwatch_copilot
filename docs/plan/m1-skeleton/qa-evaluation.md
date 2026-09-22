# M1 Skeleton — Phân Hệ QA, DevOps & Nghiệm Thu (Tasks 017 - 022)
> Phụ trách: TV4 (Khánh) và cả nhóm. Gói việc: WP-03, WP-07, WP-31.
> Tuân thủ SDLC Bước 5: Implementation Task Cards (Chuẩn 150 - 250 dòng).

### TASK-017 · Video mẫu 15 FPS và camera mô phỏng bằng MediaMTX
| | |
|---|---|
| **Goal** | Có `data/samples/sample.mp4` (15 FPS cố định, tối đa 1080p), và luồng `rtsp://localhost:8554/cam1` phát lặp từ Docker Compose |
| **Người · hạn** | Tuấn · 24/09; bước 1–3 nên xong trong 23/09 vì TASK-006 cần video |
| **Files** | Modify `docker-compose.yml`. Dữ liệu (không commit): `data/samples/vehicles.mp4`, `data/samples/sample.mp4` |
| **Exact location** | `docker-compose.yml`: thêm service `mediamtx` sau service `backend`, trước khối `volumes:` |
| **Depends on** | TASK-013 (bước 4–5) |
| **Validate** | Step 3 và Step 5 |
| **Expected** | ffprobe báo `width=1920`, `height=1080`, `r_frame_rate=15/1`, `avg_frame_rate=15/1`, `nb_frames=324`; luồng RTSP báo `h264`, `1920`, `1080`, `15/1` |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Cài ffmpeg**
- [ ] **Step 2: Tải video mẫu.** Đây là video công khai trong tài liệu thư viện `supervision`, 4K, 25 FPS, dài 21,5 giây. **Chỉ dùng để thử code**: không đưa vào tập đánh giá, không đưa lên slide, không commit.
- [ ] **Step 3: Chuẩn hóa theo H-02**
- [ ] **Step 4: Thêm camera mô phỏng** — trong `docker-compose.yml`, thêm service sau đây sau `backend`, cùng cấp với nó:
- [ ] **Step 5: Chạy và kiểm tra luồng**
- [ ] **Step 6: Commit**

---

### TASK-018 · Script lập manifest (WP-03)
| | |
|---|---|
| **Goal** | Từ một thư mục phiên quay, ghi hoặc ghép vào manifest CSV có SHA-256; từ chối video không phải 15 FPS cố định (H-02). Manifest là đầu vào của `evaluate.py` |
| **Người · hạn** | Linh · 25/09 |
| **Files** | Create `scripts/make_manifest.py`, `tests/test_make_manifest.py`; Modify `docs/eval/protocol.md` |
| **Exact location** | `protocol.md` mục 8: dòng `dev.csv` trong khối cây thư mục |
| **Depends on** | Test không cần gì. Chạy thật cần ffprobe (TASK-017 Step 1) |
| **Validate** | `pytest tests/test_make_manifest.py -v`, rồi chạy thật ở Step 5 |
| **Expected** | `4 passed`; chạy thật nhận video 15 FPS và từ chối video 25 FPS với exit code 2 |
**Interfaces — Produces:**
- Lệnh: `python scripts/make_manifest.py data/eval/<split>/<session_id> --manifest eval/manifests/<split>.csv --camera-id <id> --location <nut> --condition <day|night|rain>`.
- Cột CSV: `video_id, session_id, camera_id, fps, duration_s, sha256, location, condition`.
- Chạy lại cho cùng một phiên thì dòng của phiên đó được thay; một `video_id` đã thuộc phiên khác thì bị từ chối.
- `evaluate.py` (TASK-019) đọc đúng các cột này. Test kiểm chéo nằm ở TASK-019, nên task này không cần `evaluate.py`.
- [ ] **Step 1: Viết test** — `tests/test_make_manifest.py`
- [ ] **Step 2: Chạy test, xác nhận fail**
- [ ] **Step 3: Viết code** — `scripts/make_manifest.py`
- [ ] **Step 4: Chạy test, xác nhận pass**
- [ ] **Step 5: Chạy thật với ffprobe** (sau TASK-017 Step 3)
- lần chạy đầu in `data/eval/smoke.csv: 1 videos`, CSV có `sample,smoke,cam-01,15,21.6,<sha256>,sample,day`;
- lần chạy sau in `error: ...vehicles.mp4: 25.000 FPS, need constant 15 FPS. Normalize first: ffmpeg ...` và `exit=2`.
- [ ] **Step 6: Sửa protocol mục 8.** Trong `docs/eval/protocol.md`, thay dòng
- [ ] **Step 7: Commit**
---

---

### TASK-019 · Viết `evaluate.py`, gồm kiểm tra SHA-256 của video (L-01)
| | |
|---|---|
| **Goal** | Script đánh giá theo protocol: đọc manifest và nhãn, khớp cảnh báo với nhãn, tính precision kèm Wilson 95%, ghi log mỗi lần chạy. Từ chối file nhãn gán trên một video khác với video ghi trong manifest (L-01, protocol mục 2.6) |
| **Người · hạn** | Khánh · 27/09 |
| **Files** | Create `scripts/evaluate.py`, `tests/test_evaluate.py` |
| **Đặc tả** | protocol mục 2.6 (SHA-256), 3.3 (log mỗi lần chạy, trạng thái `burned`), 4.1–4.5 (đơn vị đo, quy tắc khớp, trùng lặp, ca mơ hồ), 7.2 (Wilson), 8 (đường dẫn), 10.3 (định dạng màn hình) |
| **Depends on** | — (manifest dùng đúng các cột ở TASK-018, mục Interfaces; không cần code của TASK-018) |
| **Validate** | `pytest tests/test_evaluate.py -v`; `ruff check` |
| **Expected** | Test xanh. Chạy `--split dev` trên dữ liệu giả in đúng định dạng ở protocol mục 10.3 |
**Interfaces**
- Manifest bắt buộc có cột `sha256`, và không được để trống.
- Mỗi file nhãn bắt buộc có `video_sha256` trùng với giá trị trong manifest; sai thì exit code 2 và không ghi log.
**Test bắt buộc có**, ngoài test cho từng quy tắc ở dòng Đặc tả:
- nhãn có `video_sha256` khác manifest: exit code 2, stderr có chữ `video_sha256`, không ghi log;
- đọc được một manifest CSV có đúng các cột TASK-018 ghi ra (dựng CSV trong test, không import `make_manifest.py`);
- Wilson cho 9/10 ra đúng giá trị ở bảng protocol mục 7.2.
- [ ] **Step 1: Viết plan TDD** bằng `/write-plan` từ các mục ở dòng Đặc tả: mỗi quy tắc một test, viết test trước.
- [ ] **Step 2: Làm theo plan đó**, tới khi `pytest tests/test_evaluate.py -v` xanh và `ruff check` sạch.
- [ ] **Step 3: Commit**
---

---

### TASK-020 · WP-31: đo FPS trên máy demo, quyết định chạy edge bằng Docker hay conda
| | |
|---|---|
| **Goal** | Có số FPS thật trên máy demo (CPU và GPU), và quyết định edge chạy trong Docker (GPU qua WSL2) hay chạy trực tiếp bằng conda (M-04) |
| **Người · hạn** | Cường · 25/09 |
| **Files** | Create `scripts/bench_fps.py`, `docs/report/spike-wp31.md` |
| **Exact location** | File mới |
| **Depends on** | TASK-017 Step 1–3 (video mẫu), `requirements-edge.txt` (TASK-006 Step 1) |
| **Validate** | Step 2–5 |
| **Expected** | Có bảng FPS và một quyết định ghi trong `spike-wp31.md` |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Script đo** — `scripts/bench_fps.py`
- [ ] **Step 2: Đo trên CPU**
- [ ] **Step 3: Cài torch bản CUDA** (trên máy demo có GPU NVIDIA)
- [ ] **Step 4: Đo trên GPU**
- [ ] **Step 5: Thử GPU trong Docker** (Docker Desktop dùng WSL2)
- [ ] **Step 6: Ghi kết quả vào `docs/report/spike-wp31.md`** gồm:
- [ ] **Step 7: Commit**

---

### TASK-021 · README: thêm hướng dẫn chạy thử M1 (WP-07)
| | |
|---|---|
| **Goal** | `README.md` đã được viết lại cho TrafficEye (bản chưa commit, sửa lúc 18:54 ngày 21/09). Task này chỉ **bổ sung** mục "Chạy thử (M1)" và cập nhật cây thư mục; không viết lại các mục khác |
| **Người · hạn** | Linh · 25/09. Sửa lại lệnh sau TASK-022 nếu có thay đổi |
| **Files** | Modify `README.md` |
| **Exact location** | Chèn mục mới ngay trước dòng `## 4. Cấu trúc thư mục`. Trong khối cây thư mục của mục 4, thêm 2 dòng sau dòng `├── .claude/ ...` và sửa dòng `├── src/ ...` |
| **Depends on** | Người đang viết lại README đã commit bản của mình |
| **Validate** | Step 3 |
| **Expected** | README hiển thị đúng trên GitHub; các lệnh được chạy thật ở TASK-022 |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Chèn mục chạy thử** — ngay trước dòng `## 4. Cấu trúc thư mục`:

---
