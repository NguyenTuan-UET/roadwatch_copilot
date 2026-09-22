# TrafficEye Edge — AI Camera Giao Thông Thông Minh Chạy Tại Biên

> **VinUni AI20K — Build Phase | Đội P-014**  
> Hệ thống camera giao thông xử lý AI trực tiếp tại biên: phát hiện, bám vết, đếm phương tiện, phát hiện vi phạm vượt đèn đỏ với độ chính xác cao (Precision-First), bảo vệ quyền riêng tư theo thiết kế và quy trình duyệt 2 bước có con người kiểm soát (Human-in-the-loop).

---

## 📌 Đặc tả hệ thống (System Specification)

Nguồn sự thật duy nhất (Single Source of Truth) về yêu cầu và hợp đồng giao tiếp:
- 📜 [**Đặc tả hệ thống TrafficEye Edge (Spec v1.0)**](docs/spec/trafficeye-spec.md): Quy định chi tiết các yêu cầu chức năng (FR), phi chức năng (NFR), tiêu chí nghiệm thu (AC) và hợp đồng API.
- 🗺️ [**Bản đồ tài liệu & Kiến trúc trực quan**](docs/Trucquanhoadocs.md): Sơ đồ luồng quan hệ giữa các tài liệu và kiến trúc tổng thể 5 phân tầng.

---

## 📚 Tài liệu kỹ thuật chuyên sâu

- 📑 [**Báo cáo kỹ thuật TrafficEye Edge (v0.3)**](docs/report/trafficeye-edge-report.md): Nghiên cứu kiến trúc, lựa chọn công nghệ, phân tích trade-off và cơ chế niêm phong bằng chứng.
- 🔍 [**Biên bản Design Review**](docs/report/design-review.md): 22 phát hiện rủi ro kỹ thuật theo góc nhìn Senior Architect và các quyết định tối ưu hoá đã chốt.
- 📅 [**Kế hoạch & Timeline 25 Work Packages**](docs/plan/timeline.md): Tiến độ chi tiết theo tuần và 8 mốc quan trọng (M0–M7).
- 🧪 [**Giao thức đánh giá Precision (Wilson 95%)**](docs/eval/protocol.md): Quy chuẩn đo kiểm khoa học, chống rò rỉ dữ liệu (data leakage) và công thức tính cỡ mẫu.
- 🚨 [**Khảo sát 15 trường hợp báo nhầm (A1–E5)**](docs/survey/false-positives.md): Bảng phân tích chi tiết các tình huống trông giống vi phạm nhưng không phạm luật và thuật toán loại trừ.

---

## 1. Vấn đề cốt lõi (Problem Statement)
- **Quá tải băng thông & Chi phí đám mây:** Việc truyền liên tục video HD/4K từ hàng nghìn camera về trung tâm gây tốn kém hạ tầng mạng và lưu trữ.
- **Xâm phạm quyền riêng tư:** Video thô chứa khuôn mặt và biển số xe của mọi người dân truyền qua mạng tiềm ẩn nguy cơ rò rỉ dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP).
- **Nguy cơ báo nhầm & Phạt oan:** Mô hình AI thông thường dễ báo nhầm (xe dài qua vạch, dừng đè vạch, nhường xe ưu tiên...), gây bức xúc xã hội khi mức phạt ô tô lên đến 18–20 triệu đồng và trừ điểm GPLX.

---

## 2. Giải pháp (Solution)
**TrafficEye Edge** giải quyết triệt để các vấn đề trên thông qua 5 trụ cột:
1. **Edge AI Vision Pipeline:** Phát hiện xe (YOLO), bám vết (ByteTrack) và đếm phương tiện trực tiếp tại camera; chỉ gửi metadata số liệu đếm và gói bằng chứng khi có sự kiện vi phạm ($>90\%$ tiết kiệm băng thông).
2. **Deterministic Violation Engine (Precision $\ge 95\%$):** Kiểm tra 6 điều kiện hình học và thời gian tất định để loại bỏ 15 tình huống báo nhầm A1–E5. Tuyệt đối không dùng LLM/Agent đen để ra quyết định vi phạm.
3. **Privacy by Design & Cryptographic Sealing:** Tự động làm mờ biển số và mặt người trên mọi khung hình; niêm phong gói bằng chứng (3 ảnh + video ngắn) bằng mã băm SHA-256 và chữ ký số Ed25519 ngay tại biên.
4. **Offline-First Resilience (SQLite Outbox):** Lưu đệm sự kiện vào SQLite cục bộ khi mất mạng và tự động đồng bộ bù khi có kết nối trở lại.
5. **Two-Step Human-in-the-Loop (HITL):** 
   - *Bước 1 (Điều hành viên):* Sơ duyệt trên bản ẩn $100\%$ biển số.
   - *Bước 2 (Cán bộ CSGT):* Thẩm định trên bản hiện biển số xe vi phạm (các xe khác vẫn che mờ) và lập biên bản xử phạt; toàn bộ truy cập được ghi nhận vào Audit Log.

---

## 3. Tech Stack

| Thành phần | Công nghệ |
|---|---|
| **Edge Vision & Tracking** | Python, OpenCV, YOLO (tối ưu hóa cho Edge), ByteTrack |
| **Edge Storage & Sync** | SQLite Outbox, HTTP Client (HTTPS/TLS 1.3), Cryptography (Ed25519, SHA-256) |
| **Central Backend** | FastAPI, Python 3.11/3.13, PostgreSQL, SQLAlchemy |
| **Central Frontend** | Next.js, TailwindCSS, TypeScript, Lucide Icons |
| **AI Reporting Assistant** | LangGraph, OpenAI / Gemini LLM |
| **Evaluation & Quality** | Pytest, Wilson Score Interval, Ruff Linter |
| **DevOps & Packaging** | Docker Compose (Edge Simulator + Backend + DB + Frontend) |

---

## 4. Cấu trúc thư mục

```text
├── .agents/                 # Hooks và rules tự động cho Antigravity IDE
├── .ai-log/                 # Nhật ký prompt AI tự động gửi chấm điểm (session.jsonl)
├── .claude/                 # Cấu hình hooks cho Claude Code CLI
├── docs/
│   ├── eval/                # Giao thức đánh giá (protocol.md) và mẫu báo cáo
│   ├── gate1/               # Bộ tài liệu nộp Gate 1 (Brief, PRD, Wireframe, Plan)
│   ├── guide/               # Technical Guidebook 10 chương VinUni AI20K
│   ├── plan/                # Kế hoạch và timeline chi tiết (timeline.md)
│   ├── report/              # Báo cáo kỹ thuật (v0.3) và Design Review
│   └── survey/              # Khảo sát các trường hợp báo nhầm (false-positives.md)
├── scripts/                 # Scripts ghi log AI, đánh giá và submit log
├── src/                     # Mã nguồn hệ thống (Edge, Backend, Agent)
├── tests/                   # Bộ test kiểm thử
├── Dockerfile               # Multi-stage Docker build
└── docker-compose.yml       # Khởi chạy full-stack hệ thống
```

---

## 5. Thành viên nhóm (Team P-014)

1. **Nguyễn Huy Cường (Leader)** — Edge AI & Vision Lead
2. **Thành viên 2** — Backend & Security Architect
3. **Thành viên 3** — Frontend & UI/UX Engineer
4. **Thành viên 4** — QA, Evaluation & DevOps
