# PHÂN CÔNG NHIỆM VỤ 4 THÀNH VIÊN & LỘ TRÌNH TRIỂN KHAI

**Dự án:** AegisGate (AI Security Gateway & Sentinel Agent)  
**Mã đội:** P-014 | **Quy mô:** 4 thành viên  

---

## 1. Phân chia vai trò 4 thành viên (Team Roles & Responsibilities)

| Thành viên | Vai trò phụ trách | Trách nhiệm chính ở Gate 1 (Hiện tại) | Trách nhiệm ở Giai đoạn Build (Sau Gate 1) |
|---|---|---|---|
| **Thành viên 1** *(Trưởng nhóm)* | **AI Lead & System Architect** | - Khảo sát bài toán và chốt đề tài với cả nhóm.<br>- Viết 1-Page Brief & PRD.<br>- Cấu hình repo & AI Log Hook.<br>- Phân chia nhiệm vụ cho cả nhóm. | - Thiết kế và lập trình LangGraph StateGraph (Sentinel Agent).<br>- Tích hợp Microsoft Presidio & Guardrail nodes.<br>- Xây dựng logic phân loại Severity và tự sinh Rule. |
| **Thành viên 2** | **Backend & Security Engineer** | - Tìm hiểu kiến trúc FastAPI trong template.<br>- Nghiên cứu thư viện Microsoft Presidio & cơ chế caching Redis.<br>- Phối hợp chốt đặc tả API trong PRD. | - Lập trình API Gateway routes (`/chat`, `/incidents`, `/rules`).<br>- Tích hợp Redis Rate Limiting và PostgreSQL database.<br>- Quản lý cơ chế xác thực RBAC cho 2 vai trò. |
| **Thành viên 3** | **Frontend & UI/UX Engineer** | - Đóng góp ý kiến về luồng trải nghiệm (UI Flow).<br>- Lên khung Wireframe cho Dashboard & Modal HITL.<br>- Chuẩn bị boilerplate Next.js + TailwindCSS. | - Xây dựng SecOps Dashboard giám sát thời gian thực.<br>- Xây dựng Modal duyệt sự cố HITL (Phê duyệt chặn/rule).<br>- Xây dựng màn hình Gateway Test Playground để demo. |
| **Thành viên 4** | **QA, Evaluation & DevOps** | - Nghiên cứu chương 8 & 9 trong Technical Guidebook.<br>- Chuẩn bị danh sách bộ dữ liệu mẫu (Prompt Injection & PII test cases).<br>- Khởi tạo file WORKLOG.md và JOURNAL.md. | - Đóng gói hệ thống bằng Docker Compose (Backend + DB + Redis + UI).<br>- Viết unit test & integration test tự động.<br>- Chạy bài test đánh giá hiệu quả phát hiện rủi ro (Deliverable #10: Evaluation Report). |

---

## 2. Kế hoạch làm việc nhóm từ Gate 1 đến Demo Day

```mermaid
gantt
    title LỘ TRÌNH THỰC HIỆN DỰ ÁN AEGISGATE (P-014)
    dateFormat  YYYY-MM-DD
    section Gate 1 (Tuần 1)
    Chốt đề tài & Phân chia việc        :done, 2026-09-18, 2d
    Hoàn thiện Brief, PRD & Wireframe    :active, 2026-09-18, 2d
    Nộp Gate 1 (/gate submit)           :crit, 2026-09-20, 1d
    section Sprint 1 (Tuần 2)
    Dựng lõi Guardrails & Presidio PII   :2026-09-21, 5d
    Xây dựng FastAPI Gateway & Redis     :2026-09-21, 5d
    Khởi tạo Next.js Dashboard UI       :2026-09-23, 4d
    section Sprint 2 (Tuần 3)
    Hoàn thiện LangGraph Sentinel Agent :2026-09-26, 5d
    Ghép nối luồng duyệt HITL           :2026-09-28, 4d
    Docker Compose toàn bộ stack        :2026-09-29, 3d
    section Demo Day (Tuần 4)
    Chạy Benchmark & Viết Eval Report   :2026-10-02, 3d
    Quay Video Demo & Làm Slide Pitch   :2026-10-04, 3d
    Tổng duyệt 10 Deliverables          :crit, 2026-10-06, 2d
```

---

## 3. Checklist chuẩn bị để nộp Gate 1 ngay hôm nay
- [x] **AI Log Setup:** Đã cài đặt và kiểm tra ghi nhận prompt tự động vào `.ai-log/session.jsonl`.
- [x] **1-Page Brief:** File `docs/gate1/1-page-brief.md` đã sẵn sàng.
- [x] **PRD:** File `docs/gate1/prd.md` đã sẵn sàng.
- [x] **Wireframe / UI Flow:** File `docs/gate1/wireframe-ui-flow.md` đã sẵn sàng.
- [x] **Bảng phân công nhiệm vụ:** File `docs/gate1/team-roles-and-plan.md` đã sẵn sàng.
- [ ] **Họp nhóm (30 phút):** Trưởng nhóm chia sẻ tài liệu này cho 3 thành viên, giải thích nhanh vai trò và cùng bấm `/gate submit`.
