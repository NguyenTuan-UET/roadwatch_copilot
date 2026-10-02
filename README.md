# RoadWatch Copilot

> **Trợ lý kèm lái cho tài xế mới trên cao tốc.** Hệ thống đo khoảng cách tới xe phía trước và nhắc sớm bằng giọng Việt, chỉ khi thật cần. Thiết bị gắn kính, không can thiệp vào xe, chạy offline.
>
> Mã đề DEV-04 · AI Thiết bị (VinFast). Nhóm P-014, khoá AI20K.

## Trạng thái (cập nhật 29/09/2026)

| Phần | Mức độ chốt | Nguồn |
|---|---|---|
| Yêu cầu: bài toán, phạm vi, lộ trình 4 tuần | Đã chốt ở bản brainstorming 2, bỏ hồ sơ xe theo ADR-04 ngày 28/09. Một số điểm còn chờ mentor xác nhận (file 1, mục 11) | [docs/requirements/](docs/requirements/) |
| Kiến trúc và hợp đồng dữ liệu | v1.1 được PO duyệt ngày 29/09 (v1.0: 28/09) | [spec](docs/specs/roadwatch-architecture.md) |
| Kế hoạch phân việc | PO duyệt ngày 29/09; hạn nộp MVP 04/10/2026 | [docs/plan/README.md](docs/plan/README.md) |
| Code | Có code nền trên nhánh `feat/roadwatch-mvp`, **chưa được nghiệm thu** | [docs/plan/README.md, mục 3](docs/plan/README.md) |

## Vấn đề

- Từ 27/8/2026, lỗi không giữ khoảng cách trên cao tốc bị xử phạt. Tài xế mới chưa cảm nhận được khoảng cách ở tốc độ cao.
- Các giải pháp hiện có hoặc nói nhiều, bắt nhìn màn hình, hoặc phải khoan đục xe.

Chi tiết: [requirements file 1](<docs/requirements/RoadWatch_Copilot_1_Tong_quan_du_an (1).md>), mục 1–3.

## Giải pháp

| Bài toán | Làm gì |
|---|---|
| **BT-A · Đo** | Phát hiện xe phía trước bằng camera gắn kính, đo khoảng cách từ cản trước theo một cấu hình lắp cố định và đo TTC, có công bố sai số |
| **BT-B · Nói** | Luật và máy trạng thái quyết định có cần nhắc không, nhắc ở mức nào, câu gì; có cơ chế chống nói nhiều và guardrail cho cảnh báo Khẩn cấp |
| **BT-C · Kiểm chứng** | Cấu hình có phiên bản, đổi qua người duyệt (HITL); nhật ký "vì sao nói hoặc không nói"; chạy lại và so sánh với baseline |

Chi tiết: [requirements file 2](<docs/requirements/RoadWatch_Copilot_2_Bai_toan_chinh (1).md>). Kiến trúc: [ARCHITECTURE.md](ARCHITECTURE.md).

## Tech stack

| Lớp | Công nghệ | Căn cứ |
|---|---|---|
| Ngôn ngữ | Python ≥ 3.11 | `ruff.toml`, CI |
| CV (BT-A) | ONNX Runtime trên CPU (FP32), OpenCV, NumPy; detector họ YOLO | Requirements file 2; spec 3.1 |
| Hợp đồng dữ liệu | Pydantic v2; bản ghi JSONL | Spec 4 |
| Cấu hình và HITL | YAML có phiên bản; SQLite (thư viện chuẩn), chỉ dùng cho HITL | Spec 3.10 |
| Âm thanh | Câu thu sẵn, render offline bằng Piper TTS vi_VN; phát bằng `winsound` trên Windows hoặc lệnh `aplay` trên Linux (chưa thử trên máy Linux) | Requirements file 2; spec 12 (D-1) |
| Giao diện | Tuần 1: CLI và âm thanh. Tuần 2–4: web UI cục bộ bằng FastAPI | Spec ADR-13 |
| Kiểm tra | pytest, ruff | `ruff.toml`, `Makefile`, CI |
| **Không dùng** | LLM, LangGraph, RAG, vector database | Spec ADR-12, NG12 |

Phần nào đã có code, phần nào chưa: [docs/plan/README.md, mục 3](docs/plan/README.md).

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements-roadwatch.txt
```

- `requirements-roadwatch.txt` là file dependency của RoadWatch (WP-C1). Ngày 02/10/2026 file này đã được cài vào một venv mới và chạy đủ test trên Windows, với Python 3.11 và 3.13; chưa chạy trên Linux.
- `requirements.txt` hiện là dependency của template môn học (FastAPI, LangChain, LangGraph…), không phải của RoadWatch.
- Lệnh kiểm tra (test, lint): [docs/development/code-rules.md](docs/development/code-rules.md), mục 8.

### Ghi log AI (yêu cầu của môn học)

Mỗi thành viên chạy một lần sau khi clone:

```bash
bash scripts/setup_hooks.sh                                      # Linux / macOS / Git Bash
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1 # Windows PowerShell
```

- **Biến môi trường.** Tạo `.env` từ `.env.example`, rồi điền `AI_LOG_API_KEY` bằng key riêng tạo tại [dashboard Phoenix](https://phoenix.note.transformerlabs.ai/api-keys). RoadWatch không cần các biến LLM, database hay vector store khác trong `.env.example`: đó là biến của template.
- **Hook và log.** Mở công cụ AI tại thư mục gốc của repo để hook ghi được prompt. Không sửa `.ai-log/`, không push bằng `--no-verify`.
- **Codex CLI.** Mở terminal ở thư mục gốc `P-014`, chạy `codex`, rồi dùng `/hooks` để review và trust hai hook `UserPromptSubmit` và `Stop` của `.codex/hooks.json`. Codex bỏ qua hook mới hoặc đã thay đổi cho tới khi người dùng xác nhận; có file hook chưa có nghĩa là hook đang chạy. Xem [hướng dẫn chính thức](https://learn.chatgpt.com/docs/hooks). Nếu dùng app/VS Code hoặc API integration không nạp hook của repo, dùng luồng thủ công `codex-app` trong workflow bên dưới.
- **Trạng thái gửi là cục bộ.** `.ai-log/.submitted_count` do script gửi quản lý và bị Git bỏ qua, giống `session.jsonl`. Không commit hay sao chép bộ đếm từ máy khác: bộ đếm lớn hơn số dòng log sẽ khiến script bỏ qua log mới. Nếu gặp trường hợp này, giữ bản sao trạng thái để kiểm tra; không xoá nội dung prompt.
- **Công cụ web** (ChatGPT, Gemini Web…): ghi log thủ công theo [.agents/workflows/log.md](.agents/workflows/log.md).

## Chạy B+C và nối A

Dành cho người giữ máy chạy A+B+C. Mọi lệnh chạy từ gốc repo. Đường dẫn tương đối trong cấu hình và trên dòng lệnh tính từ gốc repo; riêng đường dẫn trong session manifest tính từ thư mục chứa manifest.

**Tình trạng (02/10/2026).** Ba mức dưới đây khác nhau; không suy mức này ra mức kia. Trạng thái task: [docs/plan/README.md](docs/plan/README.md), mục 4.3.

| Mức | Tình trạng |
|---|---|
| Code và test bằng dữ liệu mẫu | Đã chạy trên máy phát triển (Windows), với kho cấu hình tạm, cấu hình test và loa giả lập |
| Máy demo và A thật | Chưa chạy. Chưa có model, file WAV và cấu hình đã điền; đường phát `aplay` trên Linux chưa được thử |
| Chất lượng trên dữ liệu thực địa | Chưa đánh giá. Chưa có dữ liệu, nhãn hay tinh chỉnh tham số |

### 1. Kiểm tra sau khi cài

Không cần A, file WAV hay cấu hình thật:

```bash
python -m pytest tests/roadwatch/test_handoff.py --confcutdir=tests/roadwatch -q
```

Test này dựng một kho cấu hình tạm bằng chính các lệnh `hitl`, chạy B trên phiên mẫu ở `tests/roadwatch/fixtures/handoff/`, kiểm log bằng `check-run`, chạy lại bằng `rerun-b --verify`, rồi chạy `live` với loa giả lập. Phiên mẫu là dữ liệu tổng hợp, không phải số đo thực địa. Lệnh chạy toàn bộ test: [code-rules](docs/development/code-rules.md), mục 8.

### 2. Người giữ máy cung cấp gì

| Thứ cần có | Đặt ở đâu | Cách làm |
|---|---|---|
| Cấu hình | `config/proposals/v0.yaml` | Thay mọi `null` mang nhãn `TODO(machine)`, `TODO(install)`, `TODO(A)`. Phần B không đổi khi chuyển máy. Lệnh `hitl propose` từ chối file còn `null` |
| File WAV | Thư mục `audio.phrase_dir`, mặc định `models/phrases/` | Render theo hướng dẫn ở đầu `scripts/roadwatch/render_phrases.py`, rồi chép `phrases` và `phrases_sha256` mà script in ra vào mục `audio` |
| Kho cấu hình | `--root configs` | Tạo một lần bằng `hitl init`. Không commit |
| Đầu ra của A | `--measurements`, hoặc model ONNX khai ở mục `detector` | Xem mục 4 |
| Tốc độ | File GPS CSV, khai ở `gps_file` của session manifest | Cột `time_utc`, `speed_mps`; tuỳ chọn `recv_time_utc`, `speed_accuracy_mps` |
| Thư mục log | `--out runs` | Mỗi lần chạy ghi vào `runs/<run_id>/`. Không commit |

Ba loại thông tin trong cấu hình không lẫn với nhau: phụ thuộc máy (đường dẫn), phụ thuộc camera và cách lắp (số đo KS-2…KS-5 ở requirements file 3), và tham số nghiệp vụ của B. Không đổi ngưỡng của B vì chuyển máy.

### 3. Đưa cấu hình vào kho

Do người làm, không do công cụ AI ([AGENTS.md](AGENTS.md), mục 1). Người duyệt phải khác người đề xuất.

```bash
python -m src.roadwatch.cli hitl init --root configs --approvers <người-duyệt-1> <người-duyệt-2>
python -m src.roadwatch.cli hitl propose --root configs --config config/proposals/v0.yaml --by <người-đề-xuất>
python -m src.roadwatch.cli hitl report --root configs --proposal <proposal_id> --dataset <dataset.json>
python -m src.roadwatch.cli hitl approve --root configs --proposal <proposal_id> --report <sha> --by <người-duyệt>
python -m src.roadwatch.cli hitl activate --root configs --approval <approval_id> --by <người-duyệt> --dataset <dataset.json>
python -m src.roadwatch.cli hitl status --root configs
```

- Mỗi lệnh in ra mã mà lệnh sau cần: `propose` in `proposal_id`, `report` in `sha`, `approve` in `approval_id`.
- `report` và `activate` từ chối khi working tree có thay đổi chưa commit.
- `<dataset.json>` liệt kê các phiên và split của chúng, theo mẫu `tests/roadwatch/fixtures/handoff/dataset.json`. Split `test_*` bị từ chối.

### 4. Điểm nối A

A giao số đo theo hợp đồng `Measurement` (spec 4.2). Hình dạng chính xác: `$defs.Measurement` trong [docs/specs/schemas/contracts.schema.json](docs/specs/schemas/contracts.schema.json). Có hai cách nối:

| Cách | A giao gì | Lệnh |
|---|---|---|
| A chạy ngoài repo | File `measurements.jsonl`: mỗi khung một dòng, `seq` tăng từ 0, `t_ns` không lùi | `run` kèm `--measurements` |
| A trong repo (`src/roadwatch/perception.py`) | Model ONNX, khai ở `detector.model_path` và `detector.model_sha256` | `run` không kèm `--measurements`; runtime đọc video của session manifest |

Cách thứ nhất chưa được quyết là cách chính thức: xem OQ-A12 ở spec mục 10.3.

Một bản ghi hợp lệ, là dòng đầu của phiên mẫu (trong file, mỗi bản ghi nằm trên một dòng):

```json
{
  "schema": "rw.measurement", "schema_version": "1.0.0", "run_id": "r", "seq": 0, "t_ns": 0, "clock": "session",
  "sched_n": 0, "frame_idx": 0,
  "observation": {"status": "ok", "reasons": []},
  "mount_check": {"state": "ok", "since_t_ns": 0, "deviation_px": null},
  "lead": {
    "status": "ok", "reasons": [], "identity_id": 1, "track_id": 1, "since_t_ns": 0, "basis": "fixed_roi",
    "bbox_px": [900.0, 500.0, 1020.0, 560.0], "det_score": 0.9, "change": null, "lateral_offset_m": null
  },
  "distance_m": {"value": 90.0, "status": "ok", "sigma": null, "reasons": []},
  "ttc_s": {"value": null, "status": "not_applicable", "sigma": null, "reasons": ["not_closing"]}
}
```

Luật A phải giữ (spec 4.0, 4.2, 4.6):
- Thiếu dữ liệu thì `value` là `null`, kèm `status` và `reasons`; không ghi 0.
- Không thêm trường ngoài hợp đồng. File có trường thừa, sai `schema_version`, `seq` hở hoặc `t_ns` lùi bị từ chối trước khi ghi bất cứ gì, kèm tên file và số dòng.
- `distance_m` tính từ cản trước. `ttc_s` là `not_applicable` khi hai xe không lại gần nhau.

Lệnh đã chạy trên phiên mẫu:

```bash
python -m src.roadwatch.cli run --session tests/roadwatch/fixtures/handoff/session.json --measurements tests/roadwatch/fixtures/handoff/measurements.jsonl --root configs --out runs
python -m src.roadwatch.cli check-run runs/<run_id>
python -m src.roadwatch.cli rerun-b runs/<run_id> --verify
```

- `run` in ra thư mục lần chạy. Với `--measurements`, lần chạy mang cờ `measurements_input`, không có `frames.jsonl`, và `video_file` của session manifest chỉ ghi tên video mà A đã xử lý.
- `check-run` kiểm từng luồng theo hợp đồng và kiểm các luồng khớp nhau. `rerun-b --verify` chạy lại B trên nhật ký đầu vào và so với kết quả gốc.

Kết quả của B trên phiên mẫu (cấu hình test; bảng pháp lý ở 90 km/h là 70 m):

| Thời điểm | Cảnh báo | Vì sao |
|---|---|---|
| 4,5 s | `warning` | Khoảng cách 55 m từ giây thứ 3, đủ `T_confirm` |
| 7,0 s | `emergency` | TTC 1,5 s dưới ngưỡng: phát ngay |
| 19,1 s | `cap_distance_off` | GPS ngừng sau 12,1 s: tốc độ `lost` ở 17,1 s, báo sau `T_notify` |
| 20,0 s | `emergency` | Mất tốc độ chỉ tắt cảnh báo khoảng cách; cảnh báo va chạm vẫn phát |
| 23,1 s | `recovery` | GPS trở lại ở 21,1 s |

### 5. Âm thanh

- `run --mode live` phát câu theo thời gian thực. Backend: `winsound` trên Windows, lệnh `aplay` trên Linux (gói hệ thống `alsa-utils`). Hệ điều hành khác chưa được hỗ trợ.
- Mặc định là `--audio speaker`. Thiếu file WAV, file có độ dài hoặc hash khác cấu hình, hoặc máy không có backend thì lần chạy bị từ chối. Runtime không tự chuyển sang im lặng.
- `--audio simulated` chạy không phát tiếng, dùng khi chưa có WAV. Lần chạy mang cờ `simulated_audio`, và `run_stats.json` ghi `null` ở số câu đã phát. Không dùng làm bằng chứng đã phát âm thanh.
- Nghe thử cả thư viện qua đúng backend của `live`:

```bash
python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml --play
```

### 6. Còn phụ thuộc

| Phụ thuộc | Cần gì |
|---|---|
| R-A | Model ONNX kèm hash và tham số `perception`, hoặc file `measurements.jsonl` đúng hợp đồng. Cách nối package A hiện có: OQ-A12 |
| Thực địa | Số đo KS-2…KS-5 cho mục `camera` và `mount` |
| File WAV | Render bằng Piper trên máy demo, rồi cập nhật mục `audio` (WP-B2) |
| Máy demo | Chạy lại mục 1 đến 5 trên chính máy đó; thử `aplay` nếu máy chạy Linux |
| PO | OQ-A12, OQ-A13; chỉ định reviewer cho các task do một người vừa làm vừa là reviewer |

## Tài liệu

| Tài liệu | Dùng khi |
|---|---|
| [AGENTS.md](AGENTS.md) | Bắt đầu một task: nguồn chuẩn, tài liệu cần đọc theo loại task, quy trình. Áp dụng cho cả người và công cụ AI |
| [docs/development/code-rules.md](docs/development/code-rules.md) | Viết code, test, mở PR |
| [docs/development/docs-rules.md](docs/development/docs-rules.md) | Viết tài liệu và sơ đồ Mermaid |
| [docs/plan/README.md](docs/plan/README.md) | Xem ai làm gì, phụ thuộc, trạng thái |

## Cấu trúc repo

```text
src/roadwatch/        Code RoadWatch: contracts, BT-A, BT-B, runtime, BT-C
tests/roadwatch/      Test của RoadWatch
docs/requirements/    Yêu cầu
docs/specs/           Spec kiến trúc và hợp đồng dữ liệu
docs/plan/            Kế hoạch và phân việc
docs/development/     Quy tắc code và tài liệu
docs/guide/           Sách của môn học (không sửa)
eval/, presentation/  Báo cáo đánh giá; slide và video demo
scripts/              Hook ghi log AI của môn học
```

Code mẫu của template môn học vẫn còn trong repo nhưng **không** thuộc sản phẩm: `src/agents/`, `src/api/`, `src/services/`, `src/models/`, `src/config.py`, `src/main.py`, `tests/test_agents/`, `tests/test_api/`, `tests/conftest.py`.

## Hướng dẫn của môn học (AI20K)

- **Technical Guidebook:** bản online ở <https://phoenix.note.transformerlabs.ai/technical-book>; bản offline ở `docs/guide/`. Thư mục `docs/guide/` do BTC quản lý (xem `.github/CODEOWNERS`), nhóm không sửa.
- **10 deliverables và 5 tiêu chí chấm:** [docs/guide/deliverables/checklist.md](docs/guide/deliverables/checklist.md). Cách RoadWatch đáp ứng từng mục: spec, mục 11.
- **Nhật ký:** [JOURNAL.md](JOURNAL.md) ghi mỗi tuần, [WORKLOG.md](WORKLOG.md) ghi mỗi ngày.
- **File của repo template:** [README_boilerplate.md](README_boilerplate.md) là khung README gốc. [CONTRIBUTING.md](CONTRIBUTING.md) và `.github/PULL_REQUEST_TEMPLATE.md` là quy trình của repo template. Quy trình của nhóm nằm ở [code-rules](docs/development/code-rules.md).

## Đội

Thành viên và vai trò: [docs/plan/README.md, mục 1](docs/plan/README.md).

## License

[MIT](LICENSE).
