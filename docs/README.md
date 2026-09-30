# Hệ Thống Tài Liệu Kỹ Thuật — TrafficEye Edge

> **Phương pháp luận:** Spec-Driven Development (Phát triển theo Đặc tả) kết hợp Kỹ nghệ AI Agent.  
> **Quy trình chuẩn:** [QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md](QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md) (Toàn văn 7 bước kỹ thuật, Ma trận RACI & 5 nguyên tắc vàng).

---

## 1. Bảng Tra Cứu Nhanh ("Bạn Cần Gì $\rightarrow$ Mở File Nào")

| Bạn Cần | Mở Thư Mục / File |
|---|---|
| **Hiểu quy trình phát triển chuẩn AI & ma trận RACI** | [QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md](QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md) |
| **Đặc tả hệ thống, yêu cầu FR, hợp đồng API & Schemas** | [spec/](spec/README.md) *(Trái tim của dự án)* |
| **Kiến trúc 11 phân hệ, NFR hiệu năng & quyết định ADR** | [architecture_diagram.md](architecture_diagram.md) và [arch/](arch/README.md) |
| **Chiến lược kiểm thử & giao thức đo lường Wilson 95%** | [eval/](eval/README.md) |
| **Xem việc của mình tuần này & cập nhật Checkbox DoD** | [plan/phan-viec/](plan/phan-viec/README.md) $\rightarrow$ file tên của bạn |
| **Xem lộ trình tổng thể, 56 gói việc & mốc M1 Skeleton** | [plan/](plan/README.md) |
| **Báo cáo tổng kết dự án & phân tích đối thủ** | [report/](report/README.md) |
| **Hồ sơ nghiệm thu Gate 1 & Wireframe UX** | [gate1/](gate1/README.md) |
| **Giáo trình bài giảng VinAI** | [guide/](guide/README.md) |
| **Mã nguồn RoadWatch (perception, tracking, risk engine, GUI) & cách chạy** | [../roadwatch/README.md](../roadwatch/README.md), benchmark: [../roadwatch/docs/](../roadwatch/docs/) |

---

## 2. Bản Đồ Cấu Trúc Tài Liệu (Hub & Spoke Model)

```text
docs/
├── README.md                      # [HUB TỔNG] Router điều hướng toàn bộ docs (< 100 dòng)
├── QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md  # [KIM CHỈ NAM] Toàn văn quy trình 7 bước (211 dòng)
├── architecture_diagram.md        # [BƯỚC 2] Bản đồ 11 phân hệ và sơ đồ kiến trúc nộp bài
│
├── spec/                          # ★ [TRỌNG TÂM] Đặc tả yêu cầu, Luật vi phạm, Schemas, API (Bước 1, QD, 4)
├── arch/                          # [BƯỚC 2] Kiến trúc 11 phân hệ, NFRs, ADRs, Design review (Bước 2)
├── eval/                          # [BƯỚC QD & 7] Chiến lược kiểm thử, Giao thức Wilson 95%, Nghiệm thu (Bước QD, 7)
├── plan/                          # [BƯỚC 5] Lộ trình, WP-01..56, M1 Skeleton, Task tracking cá nhân (Bước 5)
├── report/                        # Báo cáo kỹ thuật tổng quan v1.0 và Phân tích đối thủ
├── gate1/                         # Hồ sơ Gate 1 đã nộp (Brief, PRD, Phân công, Wireframe UX)
└── guide/                         # Giáo trình khóa học VinAI
```

---

## 3. Thứ Tự Ưu Tiên Chân Lý (Order of Truth)
Khi có sự mâu thuẫn giữa các tài liệu, thứ tự ưu tiên được áp dụng nghiêm ngặt:
1. **[spec/](spec/README.md)** (Yêu cầu chức năng & Hợp đồng dữ liệu/API đã chốt)
2. **[QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md](QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md)** & **[eval/](eval/README.md)** (Tiêu chuẩn chất lượng & DoD)
3. **[arch/](arch/README.md)** & **[architecture_diagram.md](architecture_diagram.md)** (Kiến trúc kỹ thuật)
4. **[plan/](plan/README.md)** (Lộ trình & Phân công)
5. Các tài liệu tham khảo và báo cáo còn lại.
