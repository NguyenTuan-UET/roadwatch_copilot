# 1-PAGE PROJECT BRIEF — AEGISGATE

**Tên dự án:** AegisGate (AI Security Gateway & Sentinel Agent)  
**Mã đội:** P-014 | **Khoá học:** VinUni AI20K — Build Phase  
**Quy mô nhóm:** 4 thành viên  

---

## 1. Vấn đề cốt lõi (Problem Statement)
- **Bối cảnh:** Các doanh nghiệp đang ồ ạt tích hợp LLM vào quy trình vận hành và ứng dụng phục vụ người dùng cuối (CSKH, tra cứu nội bộ, trợ lý ảo).
- **Điểm nghẽn:** Thiếu một lớp bảo vệ và giám sát tập trung (AI Firewall / AI Gateway). Các ứng dụng đối mặt với 3 rủi ro nghiêm trọng:
  1. **Prompt Injection & Jailbreak:** Kẻ xấu thao túng mô hình để bỏ qua rào cản an toàn, đánh cắp system prompt hoặc tri thức độc quyền.
  2. **Rò rỉ dữ liệu nhạy cảm (PII Leakage):** Người dùng vô tình hoặc cố ý đưa CCCD, số thẻ tín dụng, email, bí mật kinh doanh vào prompt hoặc LLM trả về dữ liệu nhạy cảm (vi phạm PDPA/GDPR).
  3. **Thiếu cơ chế phản ứng sự cố có con người kiểm soát (HITL):** Các giải pháp chặn tự động cứng nhắc dễ gây false positive (chặn nhầm), trong khi việc thiếu kiểm soát diện rộng dẫn đến nguy cơ mất an toàn hệ thống.

---

## 2. Giải pháp: AegisGate (Solution)
**AegisGate** là hệ thống AI Security Gateway kết hợp Sentinel Agent thông minh hoạt động theo cơ chế **Chốt chặn thời gian thực (Real-time Guardrails)** và **Phản ứng sự cố có con người tham gia (Human-in-the-loop - HITL)**.

- **Chốt chặn 2 chiều (Bi-directional Guardrails):**
  - **Input Guard:** Kiểm tra prompt của người dùng trước khi gửi tới LLM mục tiêu. Phát hiện prompt injection, lọc nội dung độc hại và tự động làm mờ (masking) thông tin PII bằng Microsoft Presidio.
  - **Output Guard:** Quét câu trả lời của LLM trước khi trả về cho người dùng để ngăn chặn rò rỉ dữ liệu nhạy cảm hoặc phản hồi sai lệch.
- **Sentinel Agent (LangGraph):**
  - Phân loại mức độ nghiêm trọng của sự cố (Severity: Low, Medium, Critical).
  - Tự động lập hồ sơ phân tích sự cố (Incident Report) và đề xuất Rule phòng thủ mới.
- **Human-in-the-Loop (HITL) Workflow:**
  - Đối với các vi phạm mức độ cao/tấn công lặp lại, Sentinel Agent đẩy cảnh báo vào hàng đợi duyệt để Kỹ sư bảo mật (Security Engineer) xác nhận trước khi áp dụng chặn diện rộng (IP/User blacklist) hoặc kích hoạt rule mới vào Firewall.
- **SecOps Dashboard:**
  - Bảng điều khiển giám sát trực quan tần suất tấn công, cảnh báo spike bất thường và quản lý trạng thái xử lý sự cố.

---

## 3. Khách hàng & Người dùng mục tiêu (Target Users)
1. **AI Security Engineer (Kỹ sư an toàn AI):** Theo dõi dashboard, duyệt các cảnh báo nghiêm trọng (HITL), tinh chỉnh rule và chính sách bảo mật.
2. **SecOps / Vận hành hệ thống:** Giám sát lưu lượng, độ trễ và tình trạng hoạt động của các dịch vụ LLM nội bộ.
3. **End-user / Client App:** Các ứng dụng nội bộ gửi request qua AegisGate để được bảo vệ an toàn mà không làm giảm trải nghiệm (độ trễ tăng thêm < 150ms).

---

## 4. Tech Stack cốt lõi
- **AI Agent & Guardrails:** LangGraph (State Machine & HITL), Microsoft Presidio (PII), Fast LLM Classifier / NeMo Guardrails.
- **Backend:** FastAPI (Async REST API), Redis (Semantic Cache & Rate Limiting), PostgreSQL (Lưu trữ logs & sự cố).
- **Frontend:** Next.js, TailwindCSS, TypeScript, Radix UI.
- **DevOps & Monitoring:** Docker Compose, GitHub Actions CI/CD, Langfuse Tracing.

---

## 5. Phạm vi MVP (Scope for Demo Day)
- [x] **Cơ bản:** Web Dashboard có phân quyền (Security Engineer, Operator); Chốt chặn Input/Output real-time (phát hiện Injection, Mask PII); Log sự cố tập trung.
- [x] **Nâng cao:** LangGraph Agent tự phân loại Severity; Luồng HITL duyệt chặn IP/User vi phạm; Agent tự sinh rule phòng thủ mới; Cảnh báo tấn công đột biến (Attack Spike).
