# Tóm tắt schema để sửa một model khác cho khớp `main`

Lấy từ code ở commit `0da24b4` và đo trực tiếp trên `models/gr14VinAI.onnx` ngày 10/10/2026. Nguồn chuẩn vẫn là code: `src/roadwatch/model.py`, `pipeline.py`, `schemas.py`. File này chỉ tóm tắt.

## 1. Ba chỗ có thể ghép model

Luồng trên `main`: video → `decode` (YUV, 20 Hz) → warp và đóng gói → **model** → `Parser` → `Pipeline.step` trả `Result` → BT-B (`decide.py`), HUD (`hud.py`), API (`schemas.py`).

| Mức | Model khác phải khớp cái gì | Code phải sửa |
|---|---|---|
| 1. File ONNX | Input, output và metadata ở mục 2 | Không: đặt file vào `models/gr14VinAI.onnx` |
| 2. Lớp Python | `reset()` và `step(new_img)` trả `dict` ở mục 3 | `model.py` |
| 3. Bản ghi `Result` | Chín trường ở mục 4 | `pipeline.py`, và `hud.py` nếu thiếu `outputs` |

Model chỉ đo khoảng cách (không có tốc độ xe mình, không có vạch làn) không khớp được mức 1 và 2. Với model như vậy chỉ còn mức 3, và vẫn vướng các trường bắt buộc ở mục 4.

## 2. Mức 1: file ONNX

### Input

| Tên | Shape | Kiểu | Nội dung |
|---|---|---|---|
| `new_img` | `[2, 6, 128, 256]` | `uint8` | Khung hiện tại, giá trị 0–255, không chuẩn hoá |
| `state_img_q` | `[2, 5, 6, 128, 256]` | `uint8` | Hàng đợi khung cũ, do chính model trả lại |

- **Trục 0 của `new_img`:** `0` là khung chính, `1` là khung rộng. Cả hai warp từ cùng một camera (`warp_maps`).
- **Sáu kênh:** ảnh warp 512×256 tách thành `Y[0::2,0::2]`, `Y[1::2,0::2]`, `Y[0::2,1::2]`, `Y[1::2,1::2]`, `U`, `V` (`pack_frame`).
- **Trạng thái:** input nào tên `X` mà model có output `next_X` thì code tự nạp `next_X` của khung trước vào `X`. Đầu clip mọi input là 0.
- **Shape phải tĩnh.** Code tạo mảng 0 theo shape khai báo: input `uint8` thành `uint8`, loại khác thành `float32`.
- **Tần số:** đúng 20 khung/giây (`MODEL_HZ`). `decode` tự lấy mẫu lại video về 20 Hz.

### Output

| Tên | Shape | Kiểu |
|---|---|---|
| `outputs` | `[1, 707]` | `float32` |
| `next_state_img_q` | `[2, 5, 6, 128, 256]` | `uint8` |

Metadata `output_slices` của file ONNX cho biết mỗi đầu ra nằm ở đâu trong `outputs`. Nó là `base64` của `pickle` một `dict` tên → `slice`; code chỉ cho phép kiểu `slice` khi đọc.

| Đầu ra | `slice` | Số phần tử | Sau khi parse | Cách parse |
|---|---|---|---|---|
| `pose` | `0:12` | 12 | `(1, 6)` + `pose_stds` | MDN |
| `road_transform` | `12:24` | 12 | `(1, 6)` + `road_transform_stds` | MDN |
| `lane_lines` | `24:552` | 528 | `(1, 4, 33, 2)` + `lane_lines_stds` | MDN |
| `lane_lines_prob` | `552:560` | 8 | `(1, 8)` | sigmoid |
| `lead` | `560:704` | 144 | `(1, 3, 6, 4)` + `lead_stds` | MDN |
| `lead_prob` | `704:707` | 3 | `(1, 3)` | sigmoid |

- **MDN:** nửa đầu là giá trị, nửa sau là log độ lệch chuẩn (code lấy `exp`).
- **sigmoid:** model trả logit, code đổi ra xác suất.
- Vị trí `slice` được phép khác, miễn metadata ghi đúng. Số phần tử của mỗi đầu ra thì cố định, vì `Parser` ép về shape trong bảng.

## 3. Mức 2: `dict` mà code thật sự đọc

Lớp thay `Gr14VinAI` cần `reset()` (xoá trạng thái) và `step(new_img)` trả `dict` có các khoá dưới đây. Hệ toạ độ: `x` tới trước, `y` sang phải, `z` xuống dưới, gốc tại camera.

| Khoá và chỉ số | Ý nghĩa | Dùng ở |
|---|---|---|
| `pose[0, 0]` | Tốc độ xe mình, m/s | `pipeline.py` (TTC), `calibration.py` |
| `pose[0, 1]`, `pose[0, 2]` | Vận tốc ngang và dọc, m/s: yaw = `atan2(pose[1], pose[0])`, pitch = `-atan2(pose[2], pose[0])` | `calibration.py` |
| `pose[0, 5]` | Tốc độ quay yaw, rad/s | `calibration.py` (cổng "đi thẳng") |
| `pose_stds[0, :3]` | Độ bất định của vận tốc | `calibration.py` (cổng hiệu chuẩn, học `fy`) |
| `road_transform[0, 2]` | Chiều cao camera, m | `pipeline.py` (`height_m`) |
| `road_transform_stds[0, :3]` | Độ bất định của `road_transform`; chỉ số 2 là của chiều cao | `calibration.py` (cổng hiệu chuẩn, học `fy`) |
| `lead[0, 0, 0]` | `(x, y, v, a)` của xe trước lúc này: `x` m trước camera, `y` m lệch phải, `v` m/s tốc độ xe trước; `a` không dùng | `pipeline.py`, `hud.py`, `evaluate.py` |
| `lead_prob[0, 0]` | Xác suất có xe trước; ngưỡng `0.5` | `pipeline.py` |
| `lane_lines[0, i]` | Vạch thứ `i`: `(y, z)` tại 33 mốc `X_IDXS` (0 đến 192 m) | `hud.py` |
| `lane_lines_prob[0, 1::2]` | Xác suất tồn tại của 4 vạch; vẽ khi lớn hơn `0.5` | `hud.py`, `evaluate.py` |

Thiếu một khoá thì `pipeline.py` báo `KeyError`, khung đó bị tính là khung lỗi; 20 khung lỗi liên tiếp thì run chuyển `failed` (`job.py`).

## 4. Mức 3: `pipeline.Result`

| Trường | Kiểu | Ý nghĩa | Được `None` |
|---|---|---|---|
| `status` | `str` | `'calibrating k/5'`, `'calibrated'` hoặc `'unreliable: <lý do>'` | Không |
| `rpy` | `np.ndarray` 3 phần tử | Roll, pitch, yaw của camera, rad | Không |
| `height_m` | `float` | Chiều cao camera so với mặt đường | Không |
| `ego_speed_mps` | `float` | Tốc độ xe mình | Không |
| `lead_prob` | `float` | Xác suất có xe trước, 0 đến 1 | Không |
| `gap_m` | `float \| None` | Từ đầu xe mình tới xe trước: `x - d_cam_bumper` | Khi `lead_prob < 0.5` |
| `lead_speed_mps` | `float \| None` | Tốc độ xe trước | Chỉ khi `gap_m` là `None` |
| `ttc_s` | `float \| None` | `gap / (ego - lead)` khi hiệu tốc độ lớn hơn `0.5` m/s và kết quả nhỏ hơn 10 s | Các trường hợp còn lại |
| `outputs` | `dict` | `dict` ở mục 3 | Không |

- **`status` được so khớp nguyên văn** (`job.py`): đúng bằng `'calibrated'` mới bật cảnh báo khoảng cách; bắt đầu bằng `unreliable` thì tắt cả cảnh báo TTC.
- **`ego_speed_mps` bắt buộc có:** BT-B tra ngưỡng luật theo tốc độ, và `ego_kmh` của API không nhận `null`.
- **`gap_m` có mà `lead_speed_mps` là `None`:** `hud.py` và `job.py` nhân với `3.6` nên run chuyển `failed`.
- **`outputs`:** `hud.draw` đọc `lead`, `lane_lines`, `lane_lines_prob`. Model không có các khoá này thì phải sửa `hud.py`.
- **Lớp thay `Pipeline`** còn cần đúng những thứ `job.py` gọi: `__init__(w, h, fy, d_cam_bumper, model)`, `step(y, u, v)` nhận ba mặt phẳng YUV420 `uint8`, `set_fy(fy)`, và các thuộc tính `K` (ma trận 3×3), `coverage` (0 đến 1), `cal.resets`.

## 5. Từ `Result` ra API

Model Pydantic ở `src/roadwatch/schemas.py`, `API_VERSION = '1.1.0'`. `job.py` điền như sau:

| Trường API (`LiveStatus`) | Lấy từ |
|---|---|
| `measure.frame`, `measure.t_s` | Chỉ số khung; `frame / 20` |
| `measure.ego_kmh` | `ego_speed_mps × 3.6` |
| `measure.lead.prob` | `lead_prob` |
| `measure.lead.gap_m` | `gap_m` |
| `measure.lead.speed_kmh` | `lead_speed_mps × 3.6`; `null` khi `gap_m` là `null` |
| `measure.ttc_s` | `ttc_s` |
| `measure.calibration` | `status`, `rpy` (đổi ra độ), `height_m`, `coverage`, `cal.resets`, trạng thái học `fy` |
| `sample` | `t_s`, `gap_m`, `ttc_s`, cùng `threshold_m` của BT-B |

- Đơn vị nằm trong tên trường: `_m`, `_s`, `_kmh`, `_deg`, `_px`, `_ms`, `_us`.
- **Không có dữ liệu thì là `null`, không bao giờ là `0`.**
- Mọi model đặt `extra='forbid'`: model khác muốn trả thêm trường mới thì phải sửa `schemas.py` theo [code-rules](docs/development/code-rules.md), mục 9.
- `Measurement` 2.0.0 ở spec 4.2 là hợp đồng khác, chưa có code trên `main`. Đừng nhầm với `Measurement` của API này.

## 6. Kiểm model của bạn

Chạy tại thư mục gốc của repo. Lệnh đầu in shape của từng đầu ra sau khi parse:

```bash
python -c "import numpy as np; from src.roadwatch.model import Gr14VinAI; p = Gr14VinAI('models/model_khac.onnx').step(np.zeros((2, 6, 128, 256), np.uint8)); print({k: v.shape for k, v in p.items()})"
```

Kết quả phải có đủ các khoá và shape này (đây là kết quả của model đang dùng):

```text
pose (1, 6), road_transform (1, 6), lane_lines (1, 4, 33, 2), lane_lines_prob (1, 8),
lead (1, 3, 6, 4), lead_prob (1, 3), pose_stds (1, 6), road_transform_stds (1, 6),
lane_lines_stds (1, 4, 33, 2), lead_stds (1, 3, 6, 4)
```

Lệnh chạy cả luồng luôn nạp `models/gr14VinAI.onnx`. Muốn thử model khác thì giữ lại bản cũ, đặt model mới vào đúng tên đó rồi chạy:

```bash
python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q
python -m src.roadwatch VIDEO --fps 20 --d-cam-bumper 1.5 --fy 910
```

`--fy 910` là tiêu cự của camera Comma2k19; video từ camera khác thì bỏ `--fy` để code tự học.
