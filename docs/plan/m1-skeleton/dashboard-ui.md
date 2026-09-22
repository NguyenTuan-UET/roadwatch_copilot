# M1 Skeleton — Phân Hệ Web Dashboard (Tasks 014 - 016)
> Phụ trách chính: TV3 (Linh). Gói việc: WP-06.
> Tuân thủ SDLC Bước 5: Implementation Task Cards (Chuẩn 150 - 250 dòng).

### TASK-014 · Khung dashboard Next.js
| | |
|---|---|
| **Goal** | Tạo app Next.js 16 trong `dashboard/`. Bỏ Google Fonts để build không cần Internet; có thanh điều hướng; dark mode theo cài đặt hệ điều hành |
| **Người · hạn** | Linh · 23/09 |
| **Files** | Create thư mục `dashboard/` bằng create-next-app, `dashboard/.env.example`; Modify `dashboard/src/app/layout.tsx`, `dashboard/src/app/globals.css`, `dashboard/.gitignore` |
| **Exact location** | Chạy lệnh tạo app từ thư mục gốc repo |
| **Depends on** | — |
| **Validate** | `cd dashboard && npm run lint && npm run build` |
| **Expected** | Lint không báo lỗi; build liệt kê route `/` và `/_not-found` |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Tạo app** (tại thư mục gốc repo)
- [ ] **Step 2: Thay `dashboard/src/app/layout.tsx`**
- [ ] **Step 3: Thay `dashboard/src/app/globals.css`.** Bỏ hai biến font Geist:
- [ ] **Step 4: File cấu hình mẫu.** Tạo `dashboard/.env.example`:
- [ ] **Step 5: Kiểm tra**
- [ ] **Step 6: Commit** (tại thư mục gốc repo; `node_modules` và `.next` đã bị `.gitignore` bỏ qua)

---

### TASK-015 · Trang số đếm
| | |
|---|---|
| **Goal** | Trang `/` gồm: danh sách camera; biểu đồ thanh xếp chồng theo loại xe cho từng phút; bảng số đếm. Tự làm mới mỗi 5 giây |
| **Người · hạn** | Linh · 25/09 |
| **Files** | Create `dashboard/src/lib/api.ts`; Replace `dashboard/src/app/page.tsx` |
| **Exact location** | `dashboard/src/lib/` là thư mục mới |
| **Depends on** | TASK-014. Dữ liệu thật cần TASK-012; trước đó dùng dữ liệu nạp bằng lệnh `curl` của TASK-013 |
| **Validate** | Lint và build, rồi kiểm tra tay ở Step 4 |
| **Expected** | Biểu đồ và bảng hiện đúng số trong DB. Tắt backend thì trong vòng 5 giây hiện thông báo lỗi đỏ; bật lại thì thông báo biến mất |
**Interfaces — Consumes:** `GET /api/v1/cameras` và `GET /api/v1/counts` (TASK-012), đúng dạng JSON đã ghi ở đó.
- [ ] **Step 1: Client API** — `dashboard/src/lib/api.ts`
- [ ] **Step 2: Trang số đếm** — thay toàn bộ `dashboard/src/app/page.tsx`
- [ ] **Step 3: Kiểm tra build**
- [ ] **Step 4: Kiểm tra tay với dữ liệu**
- có nút `cam-01`; mỗi phút một thanh màu; bảng có cột tổng;
- `docker compose stop backend` thì trong 5 giây hiện dòng đỏ "Không gọi được API";
- `docker compose start backend` thì dòng đỏ biến mất.
- [ ] **Step 5: Commit**
---

---

### TASK-016 · Trang cảnh báo tạm và CI cho dashboard
| | |
|---|---|
| **Goal** | Trang `/alerts` giữ chỗ (WP-06 ghi "trang cảnh báo tạm để trống"). CI build dashboard ở mỗi lần push và PR |
| **Người · hạn** | Linh · 26/09 |
| **Files** | Create `dashboard/src/app/alerts/page.tsx`; Modify `.github/workflows/ci.yml` |
| **Exact location** | `ci.yml`: thêm job `dashboard` vào cuối khối `jobs:`, ngang hàng với `lint-and-test` |
| **Depends on** | TASK-015 |
| **Validate** | `npm run build` có route `/alerts`; tab Actions trên GitHub có 2 job xanh |
| **Expected** | Như trên |

**Các bước thực thi (DoD Steps):**
- [ ] **Step 1: Trang giữ chỗ** — `dashboard/src/app/alerts/page.tsx`
- [ ] **Step 2: Job CI** — thêm vào cuối `.github/workflows/ci.yml` (thụt lề 2 dấu cách, cùng cấp với `lint-and-test:`):
- [ ] **Step 3: Kiểm tra**
- [ ] **Step 4: Commit**

---
