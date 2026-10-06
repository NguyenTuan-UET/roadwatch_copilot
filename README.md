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
| **BT-A · Đo** | Camera gắn kính tự hiệu chuẩn, model supercombo cho xe phía trước; đo khoảng cách từ cản trước và TTC, có công bố sai số |
| **BT-B · Nói** | Luật và máy trạng thái quyết định có cần nhắc không, nhắc ở mức nào, câu gì; có cơ chế chống nói nhiều và guardrail cho cảnh báo Khẩn cấp |
| **BT-C · Kiểm chứng** | Cấu hình có phiên bản, đổi qua người duyệt (HITL); nhật ký "vì sao nói hoặc không nói"; chạy lại và so sánh với baseline |

Chi tiết: [requirements file 2](<docs/requirements/RoadWatch_Copilot_2_Bai_toan_chinh (1).md>). Kiến trúc: [ARCHITECTURE.md](ARCHITECTURE.md).

## Tech stack

| Lớp | Công nghệ | Căn cứ |
|---|---|---|
| Ngôn ngữ | Python ≥ 3.11 | `ruff.toml`, CI |
| CV (BT-A) | ONNX Runtime trên CPU (FP32), OpenCV, NumPy; model openpilot supercombo (MIT) và hiệu chuẩn camera tự động | Spec 2, 3.1, 4.2 |
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

Trong cấu hình có ba loại thông tin, không lẫn với nhau: phụ thuộc máy (đường dẫn), do A cung cấp (model supercombo kèm hash, tham số hiệu chuẩn, `d_cam_bumper_m` đo ở KS-3), và tham số nghiệp vụ của B. Không đổi ngưỡng của B vì chuyển máy.

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

A là package [`src/roadwatch/`](src/roadwatch/): camera tự hiệu chuẩn, ảnh được warp vào khung ảnh của model openpilot supercombo, rồi lấy xe dẫn đầu, khoảng cách, TTC và làn từ đầu ra của model. Người dùng chỉ nhập khoảng cách camera–cản trước. Cần `ffmpeg` trong PATH.

```bash
uv venv .venv && uv pip install -p .venv -r requirements-roadwatch.txt
.venv/bin/python scripts/roadwatch/download_model.py          # tải supercombo, kiểm SHA-256, tỉa thành models/gr14VinAI.onnx, xóa bản gốc
.venv/bin/python -m src.roadwatch VIDEO --fps 20 --d-cam-bumper 1.5
.venv/bin/python -m src.roadwatch.web                          # giao diện demo: http://127.0.0.1:8765
.venv/bin/python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q
```

Kết quả: `VIDEO.roadwatch.mp4` (video có lớp phủ) và `VIDEO.roadwatch.json` (trạng thái, hiệu chuẩn, khoảng cách, TTC từng khung). Truyền đúng `--fps` của lúc quay; fps ghi trong file video thường sai.

- Hợp đồng A → B là `Measurement` 2.0.0 (spec 4.2, đề xuất chờ PO duyệt): khoảng cách, TTC, xe dẫn đầu, làn, khối `calibration`, `mount_check`.
- A hiện ghi video có lớp phủ và một file JSON tóm tắt; **chưa xuất `measurements.jsonl` theo 2.0.0**. Cách nối A với runtime: spec mục 10.3, OQ-A12.
- A chỉ ghi điều nó quan sát. A không quyết định cảnh báo: việc đó của B.

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
| R-A | Model supercombo kèm hash và tham số `calibration`, `model`; `d_cam_bumper_m` (KS-3) cho `mount`. Cách nối A: OQ-A12 |
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
src/roadwatch/        BT-A: tự hiệu chuẩn camera + supercombo (vendor/openpilot: 6 file openpilot, MIT)
tests/roadwatch/      Test của BT-A
models/               Model và bộ WAV (không commit)
docs/requirements/    Yêu cầu
docs/specs/           Spec kiến trúc và hợp đồng dữ liệu
docs/plan/            Kế hoạch và phân việc
docs/development/     Quy tắc code và tài liệu
docs/notes/           Ghi chú phân tích bài toán B, C
docs/guide/           Sách của môn học (không sửa)
eval/, presentation/  Báo cáo đánh giá; slide và video demo
config/proposals/     Cấu hình đề xuất (HITL)
scripts/roadwatch/    Tải model, kiểm tài liệu
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
