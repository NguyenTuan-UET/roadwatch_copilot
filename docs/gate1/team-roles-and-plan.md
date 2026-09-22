# PHÂN CÔNG NHIỆM VỤ 4 THÀNH VIÊN & LỘ TRÌNH TRIỂN KHAI

**Dự án:** TrafficEye Edge (Hệ thống Camera AI giám sát giao thông tại biên & phân tích tuyến hành lang)  
**Mã đội:** P-014 | **Quy mô:** 4 thành viên  
**Cập nhật:** 22/09/2026, theo `docs/plan/timeline.md` bản 3.0. Khi file này lệch với timeline thì theo timeline.

---

## 1. Phân chia vai trò 4 thành viên (Team Roles & Responsibilities)

| Thành viên | Vai trò phụ trách | Trách nhiệm ở Gate 1 (Đặc tả & Thiết kế) | Trách nhiệm ở giai đoạn Build (Thực thi & Tích hợp) |
|---|---|---|---|
| **Nguyễn Huy Cường** *(Trưởng nhóm, TV1)* | **PO + PM; luật lõi và chỉnh ngưỡng** | - Khảo sát bài toán và chốt đề tài TrafficEye Edge.<br>- Soạn Brief, PRD, spec, báo cáo kỹ thuật, danh mục báo nhầm, giao thức đánh giá.<br>- Phân bổ Work Packages. | - Duyệt spec (M0), nghiệm thu hằng tuần, CP1, CP2; phỏng vấn người dùng; pitch.<br>- Luật vượt đèn đỏ và lớp ngữ cảnh; mật độ và ùn tắc; gợi ý điều phối.<br>- **Người duy nhất chỉnh ngưỡng** và đóng băng cấu hình (11/10).<br>- Hiệu năng edge (ONNX, TensorRT FP16, INT8, 3 camera); soak test trên máy demo. |
| **Tuấn** *(Tech lead, TV2)* | **Kiến trúc, nền tảng edge ↔ trung tâm, production** | - Review kiến trúc và các hợp đồng dữ liệu (spec mục 6). | - Khung edge M1; máy trạng thái đèn và cấu hình cảnh v2.<br>- Đăng nhập, phân quyền, API ứng viên; gói bằng chứng ký Ed25519; luồng duyệt CSGT và nhật ký nối băm.<br>- Phân tích nút và tuyến theo HCM (LOS, tràn hàng chờ, nút cổ chai); tích hợp OCR.<br>- Hardening, Live URL, quan sát hệ thống; review code, CI.<br>- Gán nhãn mù tập test. |
| **Khánh** *(TV4)* | **Kỹ thuật thứ hai; custodian tập test; đánh giá** | - Nghiên cứu giao thức đánh giá và hướng dẫn gán nhãn. | - Hỗ trợ Cường: luật đi ngược chiều, luật làn đủ 3 kiểu, detector biển số và che.<br>- Hỗ trợ Tuấn: hạ tầng trung tâm M1, `signal_cycle`, heartbeat và trạng thái mong muốn, OTA và MQTT.<br>- Custodian: niêm phong, phân xử nhãn, chạy test một lần, báo cáo đánh giá (Deliverable #10).<br>- Agent báo cáo ca trực và trợ lý giải thích. |
| **Linh** *(TV3)* | **Giao diện, vận hành dữ liệu, gán nhãn** | - Wireframe và UI flow. | - Toàn bộ dashboard Next.js: duyệt bước 1, bản đồ, CSGT, xác minh, sức khỏe, trang Tuyến, báo cáo, nhật ký, xuất hồ sơ.<br>- GitHub Project; chuyển video 15 FPS, manifest.<br>- Gán nhãn dev chính và gán nhãn mù tập test; spike OCR; công cụ đo tuyến. |

Ai phụ trách phân hệ nào của hệ thống: `docs/plan/timeline.md` mục 5.1. Các ràng buộc chống lộ tập test (ai không được chỉnh ngưỡng, ai không được mở tập test): timeline mục 5.2.

---

## 2. Các mốc chính

| Mốc | Ngày | Nội dung |
|---|---|---|
| M0 | 24/09 | Duyệt spec và phân vai |
| M1 | 27/09 | Khung chạy đầu–cuối |
| M2 | 04/10 | Luật lõi; quyết định có tinh chỉnh model không |
| M3 | 11/10 | **Đóng băng** ngưỡng |
| CP1 | 14/10 | Demo 1, hoàn thành 80% |
| M4, M5 | 18/10, 19/10 | Khóa nhãn test; chạy test một lần |
| CP2 | 23/10 | Demo 2, 100%, sẵn sàng production |
| Nộp bài | 26/10 | |

Gantt theo từng người, lịch quay video và các điểm dễ nghẽn: `docs/plan/timeline.md` mục 3 và 5.

---

## 3. Phân chia Work Packages

Việc được cân theo giờ công, không theo số WP, vì các WP to nhỏ khác nhau. Bảng giờ công theo tuần: timeline mục 5.4.

Việc của từng người, theo thứ tự, kèm các bước làm và điều kiện "xong":
* **Nguyễn Huy Cường:** `docs/plan/phan-viec/cuong.md`
* **Tuấn:** `docs/plan/phan-viec/tuan.md`
* **Khánh:** `docs/plan/phan-viec/khanh.md`
* **Linh:** `docs/plan/phan-viec/linh.md`

---

## 4. Checklist hoàn thành Gate 1
- [x] **AI Log Setup:** Ghi nhận tự động prompt vào `.ai-log/session.jsonl`.
- [x] **1-Page Brief:** File `docs/gate1/1-page-brief.md` đầy đủ thông tin đề tài TrafficEye Edge.
- [x] **PRD:** File `docs/gate1/prd.md` chi tiết các phân hệ, yêu cầu chức năng FR và phi chức năng NFR.
- [x] **Wireframe & UI Flow:** File `docs/gate1/wireframe-ui-flow.md` trực quan hóa toàn bộ luồng hoạt động và giao diện.
- [x] **Phân công nhiệm vụ & Lộ trình:** File `docs/gate1/team-roles-and-plan.md` rõ ràng cho cả 4 thành viên.
