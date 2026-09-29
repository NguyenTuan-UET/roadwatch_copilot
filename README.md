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
| Âm thanh | Câu thu sẵn, render offline bằng Piper TTS vi_VN; phát bằng `winsound` trên Windows | Requirements file 2; spec 12 (D-1) |
| Giao diện | Tuần 1: CLI và âm thanh. Tuần 2–4: web UI cục bộ bằng FastAPI | Spec ADR-13 |
| Kiểm tra | pytest, ruff | `ruff.toml`, `Makefile`, CI |
| **Không dùng** | LLM, LangGraph, RAG, vector database | Spec ADR-12, NG12 |

Phần nào đã có code, phần nào chưa: [docs/plan/README.md, mục 3](docs/plan/README.md).

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install numpy opencv-python onnxruntime "pydantic>=2.10" pyyaml pytest ruff
```

- Danh sách gói trên lấy từ các lệnh import trong `src/roadwatch/`. File dependency riêng cho RoadWatch sẽ được thêm ở WP-C1.
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
- **Công cụ web** (ChatGPT, Gemini Web…): ghi log thủ công theo [.agents/workflows/log.md](.agents/workflows/log.md).

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
