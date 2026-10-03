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

**Bản bàn giao:** đầu nhánh `feat/wp-p4-contracts-v1`. Hợp đồng dữ liệu ở phiên bản 1.1.0, chưa review và chưa gắn thẻ. Commit chứa code của từng phần (tình trạng từng task: [docs/plan/README.md](docs/plan/README.md), mục 4.3):

| Phần | Commit |
|---|---|
| `run --measurements`, bộ phát loa, mẫu cấu hình, workflow RoadWatch | `f30174b` |
| Hợp đồng 1.1.0 và phiên mẫu có xe, người, làn | `b29ba35` |
| Bộ câu nói: script render, `MANIFEST.json`, độ dài và hash trong `v0.yaml` | `6536665` |
| Job template bỏ qua `tests/roadwatch` | `483d20f` |

**Tình trạng (02/10/2026).** Các mức dưới đây khác nhau; không suy mức này ra mức kia.

| Mức | Tình trạng |
|---|---|
| Code và test bằng dữ liệu mẫu | Đã chạy trên máy phát triển (Windows 11), với kho cấu hình tạm và cấu hình test |
| Âm thanh | Bộ WAV nháp đã render bằng Piper. Trên máy phát triển, bộ phát `winsound` được gọi không lỗi cho cả tám câu; chưa có người nghe xác nhận. `aplay` trên Linux chưa chạy lần nào |
| Máy demo và A thật | Chưa chạy. Chưa có model và cấu hình đã điền |
| Người và Làn | Mới có hợp đồng dữ liệu và dữ liệu mẫu. B chưa có luật, nên chưa có cảnh báo nào cho người hay cho lệch làn |
| Chất lượng trên dữ liệu thực địa | Chưa đánh giá. Dữ liệu mẫu là dữ liệu tổng hợp, không phải bằng chứng nghiệm thu |

### 1. Lấy code, cài và kiểm tra

```bash
git fetch origin
git switch feat/wp-p4-contracts-v1
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements-roadwatch.txt
python -m pytest tests/roadwatch/test_handoff.py --confcutdir=tests/roadwatch -q
```

Lệnh cuối không cần A, file WAV hay cấu hình thật. Nó dựng một kho cấu hình tạm bằng chính các lệnh `hitl`, chạy B trên phiên mẫu ở `tests/roadwatch/fixtures/handoff/`, kiểm log bằng `check-run`, chạy lại bằng `rerun-b --verify`, rồi chạy `live` với loa giả lập. Lệnh chạy toàn bộ test: [code-rules](docs/development/code-rules.md), mục 8.

### 2. Người giữ máy cung cấp gì

| Thứ cần có | Đặt ở đâu | Cách làm |
|---|---|---|
| Cấu hình | `config/proposals/v0.yaml` | Thay mọi `null` mang nhãn `TODO(machine)` hoặc `TODO(A)`. Phần B không đổi khi chuyển máy. Lệnh `hitl propose` từ chối file còn `null` |
| File WAV | Thư mục `audio.phrase_dir`, mặc định `models/phrases/` | Giải nén gói WAV được bàn giao (mục 3) |
| Kho cấu hình | `--root configs` | Tạo một lần bằng `hitl init`. Không commit |
| Đầu ra của A | `--measurements`, hoặc model ONNX khai ở mục `detector` | Xem mục 5 |
| Tốc độ | File GPS CSV, khai ở `gps_file` của session manifest | Cột `time_utc`, `speed_mps`; tuỳ chọn `recv_time_utc`, `speed_accuracy_mps` |
| Thư mục log | `--out runs` | Mỗi lần chạy ghi vào `runs/<run_id>/`. Không commit |

Trong cấu hình có ba loại thông tin, không lẫn với nhau: phụ thuộc máy (đường dẫn), do A cung cấp (model, tham số nhận diện, số đo camera và lắp đặt KS-2…KS-5 ở requirements file 3), và tham số nghiệp vụ của B. Không đổi ngưỡng của B vì chuyển máy.

Có hai file cấu hình, dùng cho hai việc khác nhau:

| File | Dùng để | Ghi chú |
|---|---|---|
| `config/proposals/v0.yaml` | Mẫu để điền rồi đề xuất vào kho thật | Chưa điền đủ thì bị từ chối |
| `tests/roadwatch/fixtures/handoff/test-config.yaml` | Chạy thử fixture trên một kho tạm | Mang nhãn `ASSUMPTION(test-only)`: không có số đo thật, không dùng cho lần chạy thật; với file này chỉ chạy được `--audio simulated` |

### 3. Bộ WAV

File WAV không nằm trong Git (`models/` không được commit). Bộ hiện có là gói `roadwatch-phrases-draft-20261002-e2d47790.zip`, do PO gửi riêng; SHA-256 của gói là `29e50c97d780798d5badd6f45bc0592961d5b3523328e894f257502c5b06eeca`. Giải nén vào `models/` để có `models/phrases/`.

```bash
python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml
python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml --play
```

- Lệnh đầu chỉ kiểm file: đủ tám câu, đúng độ dài và đúng hash ghi trong cấu hình. Lệnh sau phát lần lượt từng câu qua chính bộ phát mà `live` dùng, để người giữ máy nghe.
- Đây là **bản nháp**: văn bản tám câu chưa được PO duyệt (spec 10.1, OQ-B5). Thư mục `draft/` có hai câu nghe thử cho Người đi bộ và Lệch làn; không cảnh báo nào dùng chúng.
- Nguồn và giấy phép ghi trong `models/phrases/MANIFEST.json`. Engine: `piper-tts` 1.8.0, giấy phép GPL-3.0-or-later, chỉ là công cụ render và không nằm trong runtime. Giọng: `vi_VN-vais1000-medium` từ kho `rhasspy/piper-voices`, dữ liệu VAIS-1000, giấy phép CC BY 4.0: phải ghi nguồn khi công bố âm thanh.
- Chỉ render lại khi cần đổi câu; cách làm ghi ở đầu `scripts/roadwatch/render_phrases.py`. Piper thêm nhiễu ngẫu nhiên, nên render lại cho ra file khác: khi đó phải thay cả `audio.phrases` lẫn `audio.phrases_sha256` trong cấu hình.

### 4. Đưa cấu hình vào kho

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
- Muốn thử chuỗi lệnh này trước khi có cấu hình thật: dùng một thư mục tạm cho `--root` và file `test-config.yaml` ở mục 2.

### 5. Điểm nối A

A giao số đo theo hợp đồng `Measurement` (spec 4.2). Hình dạng chính xác: `$defs.Measurement` trong [docs/specs/schemas/contracts.schema.json](docs/specs/schemas/contracts.schema.json). Có hai cách nối:

| Cách | A giao gì | Lệnh |
|---|---|---|
| A chạy ngoài repo | File `measurements.jsonl`: mỗi khung một dòng, `seq` tăng từ 0, `t_ns` không lùi | `run` kèm `--measurements` |
| A trong repo (`src/roadwatch/perception.py`) | Model ONNX, khai ở `detector.model_path` và `detector.model_sha256` | `run` không kèm `--measurements`; runtime đọc video của session manifest |

- Cả hai cách đều **đọc file đã ghi xong**. Chưa có đường nhận số đo trực tiếp từ A hay từ camera. Với `--measurements`, chế độ `live` chỉ phát lại file theo đúng thời gian của từng bản ghi.
- Cách thứ nhất chưa được quyết là cách chính thức: xem OQ-A12 ở spec mục 10.3.

Mỗi bản ghi mang ba nhóm thông tin của cùng một khung hình:

| Nhóm | Trường | Đơn vị | Ghi chú |
|---|---|---|---|
| Khung | `seq`, `sched_n`, `frame_idx`, `t_ns` | `t_ns`: nano giây theo đồng hồ phiên | `seq` là thứ tự bản ghi. `frame_idx` là `null` khi không có khung |
| Xe dẫn đầu | `lead`, `distance_m`, `ttc_s` | m, s | `lead` luôn là xe. Bảng khoảng cách TT 38 chỉ áp cho `lead` |
| Đối tượng khác | `risk_objects[]`: `identity_id`, `kind`, `zone`, `distance_m`, `ttc_s` | m, s | `kind` là `vehicle` hoặc `person`. `zone.inside` cho biết đối tượng có nằm trong vùng rủi ro không. Xe dẫn đầu không lặp lại ở đây |
| Làn | `lane`: `status`, `t_ns`, `left_m`, `right_m` | m | Khoảng cách ngang từ trục dọc của xe tới vạch trái và vạch phải. `lane.t_ns` là khung mà kết quả làn được tính từ đó |

- **Trạng thái.** Mọi đại lượng đo là `{value, status, sigma, reasons}`. Thiếu dữ liệu thì `value` là `null`, kèm `status` (`not_applicable`, `unavailable`, `unreliable`) và `reasons`; không ghi 0. `risk_objects` là `null` khi A không báo cáo, là `[]` khi A đã nhìn và không thấy ai ngoài xe dẫn đầu.
- **Liên kết.** Danh tính trong `risk_objects` dùng chung không gian với `lead.identity_id`. `lane.t_ns` không lớn hơn `t_ns` của bản ghi; hiệu hai mốc là tuổi của kết quả làn. Giờ GPS được đưa về đồng hồ phiên bằng `video_start_utc_guess_ns` và `gps_offset_ms` của session manifest. Trong log, `decision_inputs.ref.seq` trỏ tới `measurements.seq`, `alerts.trigger.input_seq` trỏ tới `decision_inputs.seq`, và `audio_plan.alert_id` trỏ tới `alerts.alert_id`.
- `risk_objects` và `lane` là phần chuẩn bị cho tuần 2–4 (hợp đồng 1.1.0). **B chưa đọc hai trường này**: chúng được kiểm, ghi log và chạy lại được, nhưng không sinh cảnh báo nào (spec 10.3, OQ-A13 và OQ-A14). File viết theo 1.0.0, không có hai trường, vẫn chạy được.

Một bản ghi hợp lệ, lấy từ phiên mẫu ở giây 15,2 (trong file, mỗi bản ghi nằm trên một dòng):

```json
{
  "schema": "rw.measurement", "schema_version": "1.1.0", "run_id": "r", "seq": 152, "t_ns": 15200000000,
  "clock": "session", "sched_n": 152, "frame_idx": 152,
  "observation": {"status": "ok", "reasons": []},
  "mount_check": {"state": "ok", "since_t_ns": 0, "deviation_px": null},
  "lead": {
    "status": "ok", "reasons": [], "identity_id": 1, "track_id": 1, "since_t_ns": 0, "basis": "fixed_roi",
    "bbox_px": [900.0, 500.0, 1020.0, 560.0], "det_score": 0.9, "change": null, "lateral_offset_m": null
  },
  "distance_m": {"value": 90.0, "status": "ok", "sigma": null, "reasons": []},
  "ttc_s": {"value": null, "status": "not_applicable", "sigma": null, "reasons": ["not_closing"]},
  "risk_objects": [
    {
      "identity_id": 3, "track_id": 23, "kind": "person",
      "bbox_px": [1200.0, 470.0, 1240.0, 560.0], "det_score": 0.8,
      "zone": {"status": "ok", "inside": true, "basis": "fixed_roi", "reasons": []},
      "distance_m": {"value": 30.0, "status": "ok", "sigma": null, "reasons": []},
      "ttc_s": {"value": 1.2, "status": "ok", "sigma": null, "reasons": []}
    }
  ],
  "lane": {
    "status": "ok", "reasons": [], "t_ns": 15200000000,
    "left_m": {"value": 1.75, "status": "ok", "sigma": null, "reasons": []},
    "right_m": {"value": 1.75, "status": "ok", "sigma": null, "reasons": []}
  }
}
```

Luật A phải giữ (spec 4.0, 4.2, 4.6):
- Không thêm trường ngoài hợp đồng. File có trường thừa, sai MAJOR của `schema_version`, `seq` hở hoặc `t_ns` lùi bị từ chối trước khi ghi bất cứ gì, kèm tên file và số dòng.
- `distance_m` tính từ cản trước. `ttc_s` là `not_applicable` khi hai xe không lại gần nhau.
- A chỉ ghi điều nó quan sát. A không quyết định cảnh báo: việc đó của B.

Lệnh đã chạy trên phiên mẫu:

```bash
python -m src.roadwatch.cli run --session tests/roadwatch/fixtures/handoff/session.json --measurements tests/roadwatch/fixtures/handoff/measurements.jsonl --root configs --out runs
python -m src.roadwatch.cli run --session tests/roadwatch/fixtures/handoff/session.json --measurements tests/roadwatch/fixtures/handoff/measurements.jsonl --root configs --out runs --mode live
```

- `run` in ra thư mục lần chạy. Với `--measurements`, lần chạy mang cờ `measurements_input`, không có `frames.jsonl`, và `video_file` của session manifest chỉ ghi tên video mà A đã xử lý.
- Lệnh thứ hai phát câu qua loa theo thời gian thực và mất 27 giây với phiên mẫu.

Kết quả của B trên phiên mẫu (bảng pháp lý ở 90 km/h là 70 m):

| Thời điểm | Cảnh báo | Vì sao |
|---|---|---|
| 4,5 s | `warning` | Khoảng cách 55 m từ giây thứ 3, đủ `T_confirm` |
| 7,0 s | `emergency` | TTC 1,5 s dưới ngưỡng: phát ngay |
| 19,1 s | `cap_distance_off` | GPS ngừng sau 12,1 s: tốc độ `lost` ở 17,1 s, báo sau `T_notify` |
| 20,0 s | `emergency` | Mất tốc độ chỉ tắt cảnh báo khoảng cách; cảnh báo va chạm vẫn phát, và ngắt câu trạng thái đang nói |
| 23,1 s | `recovery` | GPS trở lại ở 21,1 s |

Ở giây 15 đến 16 phiên mẫu có một người trong vùng rủi ro với TTC dưới ngưỡng Khẩn cấp, và ở giây 24 đến 26 xe trôi tới cách vạch phải 0,3 m. B không cảnh báo ở hai đoạn này: luật cho người và cho làn chưa được PO quyết.

### 6. Âm thanh khi chạy

| Hệ điều hành | Bộ phát | Đã kiểm chứng |
|---|---|---|
| Windows | `winsound` (thư viện chuẩn) | 02/10/2026, máy phát triển: `run --mode live` trên phiên mẫu gọi bộ phát cho đủ năm cảnh báo, không lỗi; `--check --play` gọi đủ tám câu. Chưa có người nghe xác nhận |
| Linux | Lệnh `aplay` (gói hệ thống `alsa-utils`) | Chưa chạy lần nào; mới có test với tiến trình giả |
| Khác | Không có | `live` từ chối khởi động |

- Mặc định là `--audio speaker`. Thiếu file WAV, file có độ dài hoặc hash khác cấu hình, hoặc máy không có bộ phát thì lần chạy bị từ chối. Runtime không tự chuyển sang im lặng.
- `--audio simulated` chạy không phát tiếng, dùng khi chưa có WAV. Lần chạy mang cờ `simulated_audio`, và `run_stats.json` ghi `null` ở số câu đã phát. Không dùng làm bằng chứng đã phát âm thanh.

### 7. Kiểm tra log

```bash
python -m src.roadwatch.cli check-run runs/<run_id>
python -m src.roadwatch.cli rerun-b runs/<run_id> --verify
python -m src.roadwatch.cli compare runs/<run_a> runs/<run_b> --streams decisions alerts audio_plan
```

- `check-run` kiểm từng luồng theo hợp đồng và kiểm các luồng khớp nhau.
- `rerun-b --verify` chạy lại B trên nhật ký đầu vào và so với kết quả gốc.
- `compare` so hai lần chạy trên dữ liệu nghiệp vụ; cùng đầu vào và cùng cấu hình thì phải giống nhau.
- Trong `runs/<run_id>/`: `alerts.jsonl` là cảnh báo, `audio_plan.jsonl` là kế hoạch phát, `audio_events.jsonl` là việc bộ phát đã làm (chỉ ở `live`), `run_manifest.json` ghi cấu hình, phê duyệt và các cờ của lần chạy.

### 8. Còn phụ thuộc

| Phụ thuộc | Cần gì |
|---|---|
| R-A | Model ONNX kèm hash và tham số `perception`, hoặc file `measurements.jsonl` đúng hợp đồng; số đo KS-2…KS-5 cho `camera` và `mount`. Cách nối package A hiện có: OQ-A12 |
| Máy demo | Chạy lại mục 1 đến 7 trên chính máy đó, có người nghe; thử `aplay` nếu máy chạy Linux |
| PO | OQ-B5 (văn bản câu nói), OQ-A12, OQ-A13 (người), OQ-A14 (lệch làn), OQ-A15 (phiên bản hợp đồng khi bật cảnh báo mới); chỉ định reviewer cho các task do một người vừa làm vừa là reviewer |
| Thực địa | Dữ liệu, nhãn và đánh giá: chưa có |

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
