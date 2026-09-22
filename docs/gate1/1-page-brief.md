# 1-PAGE PROJECT BRIEF — TRAFFICEYE EDGE

**Tên dự án:** TrafficEye Edge (Hệ thống Camera AI giám sát giao thông tại biên & phân tích tuyến hành lang)  
**Mã đội:** P-014 | **Khóa học:** VinUni AI20K — Build Phase Cohort 4  
**Quy mô nhóm:** 4 thành viên  

---

## 1. Vấn đề cốt lõi (Problem Statement)
- **Bối cảnh:** Tại các đô thị lớn ở Việt Nam, ùn tắc giao thông và vi phạm trật tự an toàn giao thông (vượt đèn đỏ, đi ngược chiều, lấn làn) diễn ra phổ biến nhưng lực lượng chức năng không thể túc trực 24/7 tại mọi nút giao.
- **Điểm nghẽn của các giải pháp hiện tại:**
  1. **Băng thông mạng và máy chủ quá tải:** Các hệ thống camera giám sát truyền thống phải stream toàn bộ luồng video thô (1080p liên tục) về máy chủ trung tâm, gây tắc nghẽn đường truyền mạng và tốn kém chi phí hạ tầng.
  2. **Xâm phạm quyền riêng tư:** Việc truyền và lưu trữ video thô liên tục làm lộ mặt và biển số xe của người dân bình thường không vi phạm, vi phạm các tiêu chuẩn bảo vệ dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP).
  3. **Thiếu khả năng phân tích tuyến liên nút giao:** Hiện tại các camera chỉ đo đếm rời rạc tại từng ngã tư, chưa có cơ chế liên kết 3 nút giao kế tiếp trên cùng một hành lang để tính toán độ trễ, mức độ phục vụ (LOS theo chuẩn HCM) và phát hiện sớm hiện tượng tràn hàng chờ (spillback) hay nút cổ chai (bottleneck).

---

## 2. Giải pháp: TrafficEye Edge (Solution)
**TrafficEye Edge** là hệ thống giám sát và phân tích giao thông hoạt động theo nguyên lý **xử lý hoàn toàn tại biên (Edge-first AI)** kết hợp **quy trình thẩm định 2 bước có con người tham gia (2-Step HITL)**:

- **Edge AI Vision & Rule Engine:**
  - Nhận diện 4 loại phương tiện (xe máy, ô tô, xe buýt, xe tải) bằng YOLO và bám vết chuyển động liên tục bằng ByteTrack.
  - Tự động phát hiện 3 loại vi phạm tất định theo luật giao thông:
    1. **Vượt đèn đỏ (Red Light - RL):** Máy trạng thái theo dõi đèn, áp dụng grace period 0.5s và kiểm tra 6 điều kiện chặt chẽ.
    2. **Đi ngược chiều (Wrong Way - WW):** Phân tích vector hướng di chuyển so với hướng quy định của làn.
    3. **Vi phạm làn đường (Lane Violation - LN):** Đủ 3 kiểu: LN-a (sai loại xe), LN-b (đè/chèn vạch liền), LN-c (rẽ sai hướng mũi tên chỉ dẫn).
  - Tự động đo chu kỳ đèn giao thông (`signal_cycle` v1): Đo thời gian xanh ($g$), đỏ ($r$), chu kỳ ($C$) và tỷ lệ xanh ($g/C$).
- **Quyền riêng tư & Bảo mật tại biên (Privacy by Design):**
  - Tự động làm mờ khuôn mặt và biển số xe của các phương tiện xung quanh; chỉ giữ biển số xe vi phạm.
  - Niêm phong gói bằng chứng bằng mã băm SHA-256 và chữ ký số Ed25519 ngay tại Edge trước khi gửi về trung tâm; không truyền video thô.
- **Khả năng chịu lỗi ngoại tuyến (Transactional Outbox):**
  - Lưu trữ tạm vào SQLite cục bộ tại Camera khi mất mạng; tự động đồng bộ về trung tâm khi có mạng trở lại mà không làm mất sự kiện.
- **Phân tích hành lang 3 nút giao (Corridor Analyzer):**
  - Trung tâm tiếp nhận sự kiện từ 3 camera trên cùng một tuyến để tính toán lưu lượng ($v/c$), độ trễ trung bình ($d_1, d_2$), xếp hạng mức độ phục vụ (LOS từ A đến F theo chuẩn HCM 2010), phát hiện tràn hàng chờ và điểm nghẽn.
- **Quy trình duyệt 2 bước (2-Step HITL Workflow):**
  - **Bước 1 (Operator):** Điều hành viên xem bản bằng chứng đã che biển số, duyệt/loại bỏ ứng viên vi phạm.
  - **Bước 2 (CSGT):** Cán bộ CSGT xem bản rõ xe vi phạm, thẩm định tính pháp lý và ký phê duyệt xử phạt.
- **Cổng xác minh công khai (Public Verification Portal):**
  - Người dân tự tra cứu mã vụ việc, kiểm tra tính toàn vẹn của bằng chứng bằng đối soát mã băm SHA-256 và chữ ký số.

---

## 3. Khách hàng & Người dùng mục tiêu (Target Users)
1. **Điều hành viên giao thông (Operator):** Trực giám sát luồng xe trên bản đồ tuyến 3 nút giao, tiếp nhận cảnh báo ùn tắc và sơ duyệt Bước 1 các sự cố vi phạm.
2. **Cán bộ Cảnh sát Giao thông (CSGT):** Thẩm định Bước 2 trên hồ sơ vi phạm có đầy đủ bằng chứng, ký số ban hành quyết định phạt nguội.
3. **Người tham gia giao thông (Công dân):** Tra cứu công khai hồ sơ vi phạm của phương tiện mình, đối soát tính toàn vẹn của clip bằng chứng.
4. **Kỹ sư vận hành hệ thống (SysAdmin/DevOps):** Giám sát trạng thái hoạt động của camera biên, quản lý cấu hình cảnh (Scene Config).

---

## 4. Tech Stack cốt lõi
- **Edge AI & Computer Vision:** Python, YOLO (tối ưu hóa cho Edge/Jetson), ByteTrack, OpenCV, Cryptography (SHA-256, Ed25519), SQLite Outbox.
- **Central Backend:** FastAPI (RESTful API Gateway), SQLAlchemy, PostgreSQL (Timescale/Metadata & Violations), Redis.
- **Central Frontend:** Next.js, TailwindCSS, TypeScript, Lucide Icons, Leaflet / Mapbox.
- **AI Reporting Agent:** LangGraph + LLM (tổng hợp số liệu lưu lượng theo chu kỳ đèn và tự động soạn thảo báo cáo ca trực bằng tiếng Việt).
- **DevOps & QA:** Docker Compose, GitHub Actions, ruff, pytest.

---

## 5. Phạm vi triển khai (Milestones & Scope)
- **Checkpoint 1 (14/10/2026 - Đạt 53/65 điểm ≈ 82%):**
  - Tuyến 3 nút giao (3 camera hoạt động đồng thời).
  - Đếm xe theo làn, phân loại phương tiện, đo chu kỳ đèn (`signal_cycle` v1).
  - Phân tích tuyến: tính $v/c$, độ trễ $d$, xếp hạng LOS A–F, phát hiện tràn hàng chờ và nút cổ chai.
  - Phát hiện 3 loại vi phạm: Vượt đèn đỏ (RL), Đi ngược chiều (WW), Sai làn (LN-a, LN-b, LN-c).
  - Quy trình duyệt 2 bước (Operator & CSGT) + Cổng xác minh công khai bằng mã băm SHA-256.
  - Demo mô phỏng mất mạng Internet và tự động phục hồi đồng bộ qua SQLite Outbox.
- **Checkpoint 2 (23/10/2026 - Đạt 65/65 điểm = 100%):**
  - Tối ưu hóa mô hình INT8 / TensorRT trên Jetson Orin Nano giả lập.
  - Nâng cấp kênh điều khiển cấu hình từ xa (MQTT), gợi ý điều phối chu kỳ đèn.
  - Hoàn thiện bộ báo cáo đánh giá FR-EVAL-8 trên tập dữ liệu kiểm thử độc lập.
