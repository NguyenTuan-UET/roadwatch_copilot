# PRODUCT REQUIREMENTS DOCUMENT (PRD) — TRAFFICEYE EDGE

**Sản phẩm:** TrafficEye Edge — Hệ thống Camera AI giám sát giao thông tại biên & phân tích tuyến hành lang  
**Phiên bản:** 1.0 (Dành cho Gate 1 — VinUni AI20K Build Phase)  
**Nhóm phát triển:** Đội P-014 (4 thành viên)  
**Trạng thái:** Đặc tả yêu cầu sản phẩm & kiến trúc hệ thống  

---

## 1. Tổng quan sản phẩm (Product Overview)
**TrafficEye Edge** là hệ thống camera thông minh ứng dụng thị giác máy tính tại biên (Edge Computing) nhằm tự động phát hiện các hành vi vi phạm trật tự an toàn giao thông, đo lường lưu lượng theo chu kỳ đèn và phân tích mức độ ùn tắc liên nút giao trên tuyến hành lang 3 camera. Hệ thống tuân thủ nghiêm ngặt nguyên tắc **Quyền riêng tư theo thiết kế (Privacy by Design)** và quy trình **Thẩm định 2 bước có con người kiểm soát (2-Step HITL)** trước khi ban hành quyết định xử phạt nguội.

### Mục tiêu chính:
1. **Xử lý triệt để tại biên:** Nhận diện phương tiện, bám vết, đo đếm lưu lượng và phát hiện vi phạm trực tiếp trên thiết bị biên; không truyền video thô về trung tâm nhằm tiết kiệm băng thông mạng và bảo vệ quyền riêng tư.
2. **Độ chính xác cao (Precision > Recall):** Chỉ tạo hồ sơ ứng viên vi phạm khi thỏa mãn đầy đủ các điều kiện tất định chặt chẽ, giảm thiểu tối đa tỷ lệ báo oan (False Positive).
3. **Phân tích liên nút giao (Corridor Analysis):** Kết nối dữ liệu từ 3 camera trên cùng một trục đường để tính toán độ trễ, phân loại mức độ phục vụ (LOS A–F theo chuẩn HCM 2010), phát hiện sớm tràn hàng chờ (spillback) và điểm nghẽn (bottleneck).
4. **Bảo mật và toàn vẹn pháp lý:** Niêm phong gói bằng chứng bằng mã băm SHA-256 và chữ ký số Ed25519 ngay tại camera để phục vụ đối soát công khai.

---

## 2. Người dùng & Phân quyền (User Roles & Permissions)

| Vai trò | Mô tả | Quyền hạn chính |
|---|---|---|
| **Điều hành viên (Operator)** | Cán bộ trực ca tại Trung tâm Điều hành Giao thông (TOC). | - Giám sát Dashboard thời gian thực và bản đồ tuyến hành lang 3 camera.<br>- Xem cảnh báo ùn tắc, tràn hàng chờ.<br>- Thực hiện **Duyệt Bước 1 (Sơ duyệt)** trên gói bằng chứng đã che biển số: Xác nhận có vi phạm hoặc Loại bỏ kèm mã lý do. |
| **Cán bộ CSGT (CSGT Officer)** | Cán bộ Cảnh sát Giao thông có thẩm quyền xử phạt. | - Tiếp nhận danh sách hồ sơ đã qua sơ duyệt Bước 1.<br>- Thực hiện **Thẩm định Bước 2**: Xem hình ảnh/video rõ biển số xe vi phạm.<br>- Ký số phê duyệt và ban hành quyết định phạt nguội. |
| **Công dân (Public Citizen)** | Người tham gia giao thông tra cứu phạt nguội. | - Truy cập Cổng dịch vụ công trực tuyến.<br>- Nhập mã vụ việc / biển số xe để tra cứu clip bằng chứng.<br>- Đối soát tính toàn vẹn của bằng chứng qua mã băm SHA-256 và chữ ký số. |
| **Quản trị viên (Admin / DevOps)** | Kỹ sư vận hành và bảo trì hệ thống. | - Quản lý danh sách camera biên và cập nhật Cấu hình cảnh (Scene Config).<br>- Theo dõi trạng thái hoạt động (Health/Heartbeat) và dung lượng hàng đợi Outbox. |

---

## 3. Yêu cầu chức năng chi tiết (Functional Requirements)

### 3.1. Phân hệ 1: Edge Vision & Rule Engine (Xử lý tại biên)
- **FR-1 (Nhận diện & Bám vết phương tiện):**
  - Nhận diện 4 nhóm phương tiện: Xe máy (`motorcycle`), Ô tô con (`car`), Xe buýt (`bus`), Xe tải (`truck`) bằng YOLO.
  - Bám vết liên tục (Object Tracking) bằng ByteTrack, duy trì Track ID qua các khung hình, xử lý che khuất ngắn hạn.
  - Đếm xe qua vạch ảo theo từng làn đường và theo phút.
- **FR-2 (Phát hiện vượt đèn đỏ - Red Light Running):**
  - Máy trạng thái theo dõi màu đèn giao thông (Đỏ / Vàng / Xanh).
  - Áp dụng thời gian ân hạn (grace period) 0.5s sau khi đèn chuyển Đỏ.
  - Kiểm tra 6 điều kiện tất định (vị trí tâm xe vượt qua vạch dừng khi đèn đang đỏ, duy trì vận tốc hợp lệ).
- **FR-3 (Phát hiện đi ngược chiều - Wrong Way):**
  - So sánh vector chuyển động của phương tiện với vector hướng cho phép của làn đường trong Scene Config.
  - Cảnh báo khi góc lệch vượt quá $120^\circ$ trong thời gian liên tục $\ge 1.0\text{s}$.
- **FR-4 (Phát hiện vi phạm làn đường - Lane Violation):**
  - **LN-a (Sai làn theo loại xe):** Xe máy đi vào làn dành riêng cho ô tô hoặc ngược lại.
  - **LN-b (Đè/chèn vạch liền):** Phương tiện chuyển làn cắt qua vạch sơn liền phân làn.
  - **LN-c (Sai mũi tên chỉ hướng):** Xe đi thẳng ở làn bắt buộc rẽ hoặc rẽ ở làn chỉ được đi thẳng.
- **FR-5 (Đo chu kỳ đèn - Signal Cycle Measurement):**
  - Tự động nhận diện thời điểm đổi pha đèn để đo: thời gian đỏ ($r$), xanh ($g$), vàng ($y$), tổng chu kỳ ($C$) và tỷ lệ xanh ($g/C$).
  - Đóng gói và phát sự kiện `signal_cycle` v1 về trung tâm sau mỗi chu kỳ.

### 3.2. Phân hệ 2: Quyền riêng tư & Lưu trữ biên (Privacy & Edge Storage)
- **FR-6 (Làm mờ tự động & Niêm phong bằng chứng):**
  - Tự động phát hiện và làm mờ khuôn mặt của tất cả người tham gia giao thông và biển số của các phương tiện không vi phạm.
  - Tạo 2 gói bằng chứng: Bản dành cho Điều hành viên (che biển số) và Bản dành cho CSGT (hiện biển số xe vi phạm).
  - Tính toán mã băm SHA-256 cho video chứng cứ (khoảng 3–5 giây) và tạo chữ ký số Ed25519 ngay tại Edge.
- **FR-7 (Chịu lỗi ngoại tuyến qua SQLite Outbox):**
  - Mọi sự kiện vi phạm và số liệu lưu lượng được ghi vào SQLite Outbox cục bộ trước khi truyền qua mạng.
  - Khi đứt kết nối Internet, dữ liệu được giữ an toàn tại biên; khi mạng phục hồi, background worker tự động đẩy dữ liệu về trung tâm theo thứ tự thời gian mà không bị mất mát.

### 3.3. Phân hệ 3: Phân tích tuyến hành lang & Máy chủ trung tâm (Central Backend)
- **FR-8 (Phân tích hành lang 3 nút giao - Corridor Analysis):**
  - Tổng hợp dữ liệu từ 3 camera kế tiếp trên cùng một tuyến đường.
  - Tính toán tỷ số lưu lượng trên năng lực thông hành ($v/c$), độ trễ trung bình ($d = d_1 + d_2$) và xếp hạng mức độ phục vụ (LOS từ A đến F) theo tiêu chuẩn Highway Capacity Manual (HCM 2010).
  - Tự động phát hiện hiện tượng tràn hàng chờ (spillback) từ nút hạ lưu về nút thượng lưu và nhận diện nút cổ chai (bottleneck).
- **FR-9 (Trợ lý báo cáo AI - AI Reporting Agent):**
  - Tự động truy vấn dữ liệu từ PostgreSQL và soạn thảo báo cáo tổng hợp ca trực giao thông (lưu lượng cao điểm, số vụ vi phạm, tình trạng nút nghẽn) bằng ngôn ngữ tự nhiên.

### 3.4. Phân hệ 4: Giao diện người dùng & Quy trình HITL (Central Frontend)
- **FR-10 (Live Traffic & Corridor Dashboard):**
  - Hiển thị bản đồ tuyến 3 nút giao với trạng thái màu sắc theo mức phục vụ LOS (Xanh lá: A/B, Vàng: C/D, Đỏ: E/F).
  - Hiển thị biểu đồ lưu lượng theo chu kỳ đèn và bảng cảnh báo ùn tắc thời gian thực.
- **FR-11 (Màn hình thẩm định vi phạm 2 bước):**
  - **Màn hình Bước 1 (Operator):** Xem video/ảnh vi phạm đã che biển số; các nút thao tác: "Chấp thuận" hoặc "Loại bỏ" (kèm mã lý do như xe ưu tiên, biển số mờ, hiệu lệnh CSGT).
  - **Màn hình Bước 2 (CSGT):** Tiếp nhận các hồ sơ đã qua Bước 1; hiển thị biển số rõ nét; nút thao tác: "Ký số phê duyệt" hoặc "Bác bỏ".
- **FR-12 (Cổng xác minh công khai - Public Verification Portal):**
  - Trang web công khai cho phép công dân nhập mã hồ sơ để xem clip chứng cứ và kiểm tra kết quả đối soát toàn vẹn mã băm SHA-256.

---

## 4. Yêu cầu phi chức năng (Non-Functional Requirements)

1. **Hiệu năng xử lý tại biên (Edge Performance):**
   - Tốc độ xử lý tại Edge đạt tối thiểu **$\ge 15$ FPS** ở độ phân giải 1080p trên thiết bị biên (Jetson Orin Nano / GPU laptop).
   - Độ trễ gửi sự kiện vi phạm về máy chủ trung tâm **$< 2.0\text{s}$** trong điều kiện mạng bình thường.
2. **Độ tin cậy & Chịu lỗi (Reliability & Resilience):**
   - Tỷ lệ mất mát dữ liệu sự kiện khi mất mạng là **0%** nhờ cơ chế Transactional Outbox (dung lượng đệm SQLite lưu được tối thiểu 7 ngày ngoại tuyến).
   - Hệ thống camera tự động kết nối lại luồng RTSP trong vòng 5 giây khi bị gián đoạn tín hiệu video.
3. **Bảo mật & Pháp lý (Security & Legal Integrity):**
   - Không truyền video thô liên tục qua Internet; chỉ truyền sự kiện, metadata và video chứng cứ ngắn đã niêm phong.
   - 100% video chứng cứ được bảo vệ tính toàn vẹn bằng SHA-256 và chữ ký số Ed25519.
   - Phân quyền nghiêm ngặt (RBAC) giữa Điều hành viên và CSGT; ghi nhật ký kiểm toán (Audit Log) cho mọi thao tác xem và duyệt.

---

## 5. Tiêu chí nghiệm thu (Acceptance Criteria)

- [ ] Camera AI tại Edge phát hiện chính xác xe vi phạm vượt đèn đỏ (RL), đi ngược chiều (WW) và 3 kiểu sai làn (LN-a, LN-b, LN-c).
- [ ] Gói bằng chứng tự động làm mờ mặt và biển số xe xung quanh, băm SHA-256 và ký số Ed25519 tại chỗ.
- [ ] Khi ngắt kết nối mạng mô phỏng, camera tiếp tục ghi nhận sự kiện vào SQLite; khi bật lại mạng, toàn bộ dữ liệu tự động đồng bộ về trung tâm đầy đủ.
- [ ] Hệ thống trung tâm tiếp nhận sự kiện từ 3 camera, tính toán độ trễ và hiển thị trực quan mức độ phục vụ LOS A–F của tuyến hành lang trên Dashboard.
- [ ] Điều hành viên thực hiện duyệt Bước 1 (bản che biển số) và Cán bộ CSGT thực hiện duyệt Bước 2 (bản rõ biển số).
- [ ] Người dân tra cứu mã vụ việc trên Cổng dịch vụ công và hệ thống hiển thị xác nhận mã băm SHA-256 trùng khớp 100%.
