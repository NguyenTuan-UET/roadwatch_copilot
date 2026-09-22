# TrafficEye Edge — AI Camera Giao Thông Thông Minh Chạy Tại Biên

> **VinUni AI20K — Build Phase | Đội P-014**  
> Hệ thống camera giao thông xử lý AI trực tiếp tại biên: phát hiện, bám vết, đếm phương tiện theo làn; phân tích ùn tắc theo tuyến; phát hiện vi phạm (vượt đèn đỏ, đi ngược chiều, sai làn) theo nguyên tắc precision trước (Precision-First); bảo vệ quyền riêng tư theo thiết kế và quy trình duyệt 2 bước có con người kiểm soát (Human-in-the-loop).

---

## 📚 Tài liệu: đọc gì, ở đâu

**Thành viên team: mở file việc của bạn trước** — `docs/plan/phan-viec/<tên>.md`. File đó giải thích thuật ngữ, liệt kê việc theo thứ tự kèm các bước làm, và chỉ đúng phần tài liệu cần đọc.

| File | Dùng để | Ai đọc |
|---|---|---|
| [docs/architecture_diagram.md](docs/architecture_diagram.md) | **Kiến trúc** (file duy nhất): hệ thống gồm 11 phân hệ nào; mọi sơ đồ. File nộp bài | Mọi người, đọc đầu tiên |
| [docs/spec/trafficeye-spec.md](docs/spec/trafficeye-spec.md) | **Yêu cầu** (nguồn sự thật): làm gì, thế nào là xong, hợp đồng dữ liệu | Mọi người, theo mục được chỉ trong file việc |
| [docs/spec/false-positives.md](docs/spec/false-positives.md) | Các ca trông giống vi phạm nhưng không phải (mã A1–E5, W1–W8, L1–L8) | Người viết luật, người gán nhãn |
| [docs/plan/timeline.md](docs/plan/timeline.md) | **Kế hoạch chung:** mốc, ai làm việc nào, lịch quay, phụ thuộc. File duy nhất ghi tên người làm | PO; ai cần biết đầu vào của mình do ai giữ |
| [docs/plan/phan-viec/](docs/plan/phan-viec/) | **Việc của từng người:** `cuong.md`, `tuan.md`, `khanh.md`, `linh.md` | Mỗi người đọc file của mình |
| [docs/plan/2026-09-21-m1-skeleton.md](docs/plan/2026-09-21-m1-skeleton.md) | Hướng dẫn code từng bước cho M1 (TASK-001…022) | Người làm TASK tương ứng |
| [docs/eval/protocol.md](docs/eval/protocol.md), [docs/eval/report-template.md](docs/eval/report-template.md) | **Cách đo** precision (Wilson 95%), chống lộ tập test; mẫu báo cáo đo | Người chỉnh ngưỡng, người giữ tập test, người gán nhãn |
| [docs/report/trafficeye-edge-report.md](docs/report/trafficeye-edge-report.md) | **Lý do** chọn kiến trúc và công nghệ. Phụ lục A: design review 21/09 (các mã H-01, M-03…) | PO; ai cần biết "vì sao" |
| [docs/report/so-sanh-doi-thu.md](docs/report/so-sanh-doi-thu.md) | So sánh với đối thủ cùng đề; các điểm học được đã áp dụng xong | PO |
| `docs/gate1/`, `docs/guide/` | Hồ sơ Gate 1 đã nộp; giáo trình của khóa học. Không sửa | Tham khảo |

Khi các file nói khác nhau, tin theo thứ tự: **spec → kiến trúc → timeline → các file còn lại.**

---

## 1. Vấn đề cốt lõi (Problem Statement)
- **Quá tải băng thông & Chi phí đám mây:** Việc truyền liên tục video HD/4K từ hàng nghìn camera về trung tâm gây tốn kém hạ tầng mạng và lưu trữ.
- **Xâm phạm quyền riêng tư:** Video thô chứa khuôn mặt và biển số xe của mọi người dân truyền qua mạng tiềm ẩn nguy cơ rò rỉ dữ liệu cá nhân (Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15, hiệu lực từ 01/01/2026).
- **Nguy cơ báo nhầm & Phạt oan:** Mô hình AI thông thường dễ báo nhầm (xe dài qua vạch, dừng đè vạch, nhường xe ưu tiên...), gây bức xúc xã hội khi mức phạt ô tô lên đến 18–20 triệu đồng và trừ điểm GPLX.

---

## 2. Giải pháp (Solution)
**TrafficEye Edge** giải quyết triệt để các vấn đề trên thông qua 5 trụ cột:
1. **Edge AI Vision Pipeline:** Phát hiện xe (YOLO), bám vết (ByteTrack) và đếm phương tiện trực tiếp tại camera; chỉ gửi metadata số liệu đếm và gói bằng chứng khi có sự kiện vi phạm. Băng thông tiết kiệm được sẽ báo bằng số đo thật so với bitrate video gốc, không hứa trước.
2. **Deterministic Violation Engine:** Luật tất định dạng plugin cho vượt đèn đỏ (6 điều kiện, mã loại trừ A1–E5), đi ngược chiều (W1–W8) và sai làn đủ 3 kiểu (L1–L8). Precision được báo bằng số đo kèm khoảng tin cậy Wilson 95% theo giao thức đã duyệt, không cam kết một con số trước. Tuyệt đối không dùng LLM/Agent để ra quyết định vi phạm.
3. **Privacy by Design & Cryptographic Sealing:** Tự động làm mờ biển số và mặt người trên mọi ảnh rời khỏi thiết bị; niêm phong gói bằng chứng (3 ảnh + chuỗi JPEG từ t − 3 s tới t + 2 s) bằng mã băm SHA-256 và chữ ký số Ed25519 ngay tại biên.
4. **Offline-First Resilience (SQLite Outbox):** Lưu đệm sự kiện vào SQLite cục bộ khi mất mạng và tự động đồng bộ bù khi có kết nối trở lại.
5. **Two-Step Human-in-the-Loop (HITL):** 
   - *Bước 1 (Điều hành viên):* Sơ duyệt trên bản ẩn $100\%$ biển số.
   - *Bước 2 (Cán bộ CSGT):* Thẩm định trên bản hiện biển số xe vi phạm (các xe khác vẫn che mờ), rồi phê duyệt để vi phạm được ghi nhận chính thức; toàn bộ truy cập được ghi nhận vào Audit Log.

---

## 3. Tech Stack

| Thành phần | Công nghệ |
|---|---|
| **Edge Vision & Tracking** | Python, OpenCV, YOLO26n (TensorRT FP16 / ONNX), ByteTrack |
| **Edge Storage & Sync** | SQLite Outbox, HTTPS (TLS qua reverse proxy từ CP2), Cryptography (Ed25519, SHA-256); MQTT (Mosquitto) chỉ làm kênh điều khiển từ CP2 |
| **Central Backend** | FastAPI, Python 3.11, PostgreSQL, SQLAlchemy |
| **Central Frontend** | Next.js, TailwindCSS, TypeScript, Lucide Icons |
| **AI Reporting Assistant** | LangGraph: công cụ chỉ đọc, người duyệt trước khi phát hành, có chế độ không LLM |
| **Evaluation & Quality** | Pytest, Wilson Score Interval, Ruff Linter |
| **DevOps & Packaging** | Docker Compose (Edge Simulator + Backend + DB + Frontend) |

---

## 4. Cấu trúc thư mục

```text
├── .agents/                 # Hooks và rules tự động cho Antigravity IDE
├── .ai-log/                 # Nhật ký prompt AI tự động gửi chấm điểm (session.jsonl)
├── .claude/                 # Cấu hình hooks cho Claude Code CLI
├── docs/
│   ├── architecture_diagram.md  # KIẾN TRÚC: 11 phân hệ và mọi sơ đồ (file nộp bài)
│   ├── spec/                # YÊU CẦU: spec (nguồn sự thật) + danh mục ca dễ báo nhầm
│   ├── plan/                # KẾ HOẠCH: timeline chung, phan-viec/ (việc từng người), plan code M1
│   ├── eval/                # ĐO: giao thức đánh giá + mẫu báo cáo đánh giá
│   ├── report/              # LÝ DO: báo cáo kỹ thuật (kèm design review) + so sánh đối thủ
│   ├── gate1/               # Hồ sơ Gate 1 đã nộp (Brief, PRD, Wireframe, Plan)
│   └── guide/               # Giáo trình 10 chương VinUni AI20K
├── scripts/                 # Scripts ghi log AI, đánh giá và submit log
├── src/                     # Mã nguồn hệ thống (Edge, Backend, Agent)
├── tests/                   # Bộ test kiểm thử
├── Dockerfile               # Multi-stage Docker build
└── docker-compose.yml       # Khởi chạy full-stack hệ thống
```

---

## 5. Thành viên nhóm (Team P-014)

1. **Nguyễn Huy Cường (Leader)** — PO + PM; luật lõi và chỉnh ngưỡng
2. **Tuấn** — Tech lead: kiến trúc, nền tảng edge ↔ trung tâm, production
3. **Khánh** — Kỹ thuật thứ hai (luật, `signal_cycle`, OTA, Agent); giữ tập test và báo cáo đánh giá
4. **Linh** — Giao diện, vận hành dữ liệu, gán nhãn

Ai phụ trách phân hệ nào: [docs/plan/timeline.md](docs/plan/timeline.md) mục 5.1. Việc của từng người: [docs/plan/phan-viec/](docs/plan/phan-viec/).
