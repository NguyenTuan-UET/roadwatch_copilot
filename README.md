# AegisGate — AI Security Gateway & Sentinel Agent

> **VinUni AI20K — Build Phase | Đội P-014**  
> Hệ thống chốt chặn bảo mật thời gian thực (Real-time AI Firewall) và xử lý sự cố an toàn cho các ứng dụng GenAI doanh nghiệp.

---

## 📌 Hồ sơ Gate 1 (Đã hoàn thiện)

Toàn bộ tài liệu nộp **Gate 1 - Chốt đề tài (+100 XP / member)** nằm trong thư mục [`docs/gate1/`](docs/gate1/):
- 📄 [**1-Page Project Brief**](docs/gate1/1-page-brief.md): Tóm tắt bài toán, giải pháp và phạm vi MVP.
- 📋 [**Product Requirements Document (PRD)**](docs/gate1/prd.md): Đặc tả chi tiết tính năng, luồng HITL, phân quyền RBAC và yêu cầu phi chức năng.
- 🎨 [**Wireframe & UI Flow**](docs/gate1/wireframe-ui-flow.md): Sơ đồ luồng hệ thống (Mermaid) và phác thảo giao diện SecOps Dashboard.
- 👥 [**Bảng phân công 4 thành viên & Kế hoạch**](docs/gate1/team-roles-and-plan.md): Phân rã nhiệm vụ và lộ trình triển khai đến Demo Day.
- ⚙️ **GitHub Repo & AI Log Setup:** Đã cấu hình và kích hoạt tự động tại `.ai-log/session.jsonl`.

---

## 1. Vấn đề cốt lõi (Problem Statement)
- **Bối cảnh:** Khi doanh nghiệp mở rộng các ứng dụng LLM nội bộ hoặc công khai, nguy cơ bị tấn công qua **Prompt Injection**, **Jailbreak** và **rò rỉ dữ liệu cá nhân (PII)** ngày càng gia tăng.
- **Thực trạng:** Thiếu một lớp bảo vệ trung gian (AI Gateway) vừa kiểm soát an toàn hai chiều Input/Output với độ trễ thấp, vừa tích hợp cơ chế con người tham gia xử lý (Human-in-the-loop - HITL) trước khi ra quyết định chặn diện rộng.

---

## 2. Giải pháp (Solution)
**AegisGate** cung cấp giải pháp toàn diện gồm 4 trụ cột:
1. **Real-time Bi-directional Guardrails:** Kiểm tra prompt đầu vào và câu trả lời đầu ra; tự động ẩn PII bằng Microsoft Presidio; ngăn chặn Jailbreak và Prompt Injection.
2. **Sentinel Agent (LangGraph):** Phân loại mức độ nghiêm trọng (Severity: Low, Medium, Critical), tự động sinh báo cáo sự cố (Incident Report) và đề xuất Rule phòng thủ mới.
3. **Human-in-the-Loop (HITL) Workflow:** Kỹ sư bảo mật duyệt các cảnh báo nguy hiểm trước khi đưa vào danh sách đen (Blacklist) hoặc cập nhật Rule vào Firewall diện rộng.
4. **SecOps Live Dashboard:** Bảng điều khiển thời gian thực theo dõi lưu lượng, sự cố và cảnh báo tấn công đột biến (Attack Spike).

---

## 3. Tech Stack

| Thành phần | Công nghệ |
|---|---|
| **AI Agent & Guardrails** | LangGraph (StateGraph & HITL), Microsoft Presidio (PII), LLM Classifier |
| **Backend** | FastAPI, Python 3.11, Redis (Cache & Rate Limiting), PostgreSQL |
| **Frontend** | Next.js, TailwindCSS, TypeScript, Radix UI |
| **Testing & Quality** | Pytest, Ruff Linter |
| **DevOps & Tracing** | Docker Compose, GitHub Actions CI/CD, LangSmith / Langfuse |

---

## 4. Bắt đầu nhanh (Quick Start)

### 4.1. Cài đặt môi trường
```bash
# 1. Kích hoạt môi trường (Python 3.11 hoặc Conda)
conda activate VinAI

# 2. Cài đặt thư viện
pip install -r requirements.txt

# 3. Cấu hình biến môi trường
cp .env.example .env
```

### 4.2. Khởi chạy Backend
```bash
uvicorn src.main:app --reload --port 8000
```
- API Docs (Swagger): <http://localhost:8000/docs>
- Health Check: <http://localhost:8000/health>

---

## 5. Cấu trúc thư mục

```text
├── .agents/                 # Hook và rules tự động cho Antigravity IDE
├── .ai-log/                 # Nhật ký prompt AI tự động gửi chấm điểm (session.jsonl)
├── docs/
│   ├── gate1/               # Bộ tài liệu nộp Gate 1 (Brief, PRD, Wireframe, Plan)
│   └── guide/               # Technical Guidebook 10 chương
├── scripts/                 # Scripts ghi log AI và git hook installer
├── src/
│   ├── agents/              # Lõi LangGraph Sentinel Agent (Graph, Nodes, Tools, State)
│   ├── api/                 # FastAPI routes (Gateway, Chat, Incidents, Status)
│   ├── models/              # Pydantic Schemas
│   ├── services/            # LLM & Presidio service clients
│   ├── config.py            # Pydantic Settings
│   └── main.py              # FastAPI application entry point
├── tests/                   # Bộ unit test và integration test
├── Dockerfile               # Multi-stage Docker build
└── docker-compose.yml       # Chạy full-stack backend, redis, db
```

---

## 6. Thành viên nhóm (Team P-014)

1. **Nguyễn Huy Cường (Leader)** — AI Lead & System Architect
2. **Thành viên 2** — Backend & Security Engineer
3. **Thành viên 3** — Frontend & UI/UX Engineer
4. **Thành viên 4** — QA, Evaluation & DevOps
