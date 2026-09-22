# Đặc tả hệ thống (Spec) — TrafficEye Edge

> **Phiên bản:** 1.0-draft · 21/09/2026.
> - PO đã chốt Q1–Q4 ngày 21/09 (mục 14).
> - Toàn văn spec và Q5 được duyệt tại M0 (24/09).
> - Sửa ngày 21/09, sau khi chốt Q1–Q4:
>   - thêm NFR-DEP-2 (Live URL) và mục 6.7 (kênh điều khiển, MQTT);
>   - `GET desired` chuyển từ CP2 lên CP1, vì lớp ngữ cảnh ở CP1 cần chế độ điều khiển tay (C4, W6, L8), và báo cáo mục 6.6 đã duyệt kênh hỏi định kỳ;
>   - cỡ việc CP1 lúc đó là 45/56.
> - Bổ sung ngày 21/09, PO chốt Q6–Q9 (mục 14):
>   - sai làn đủ 3 kiểu, cả ba đều MUST;
>   - thêm phân tích ùn tắc theo tuyến 3 nút: FR-DEN-4, FR-COR-1, FR-COR-2, FR-UI-7, FR-EVAL-8, mục 6.8;
>   - FR-MC-1 lên MUST; FR-MC-2 gộp vào FR-COR-2; FR-AGT-3 xuống COULD; FR-EXP-1 chuyển sang CP2;
>   - cỡ việc: CP1 = 53/65 ≈ 82%.
>
> **Vai trò của tài liệu:** nguồn sự thật duy nhất về *yêu cầu, tiêu chí nghiệm thu và hợp đồng giao tiếp*.
> - Báo cáo kỹ thuật (`docs/report/trafficeye-edge-report.md`) giải thích *vì sao chọn*.
> - Spec quy định *làm gì* và *thế nào là xong*.
> - Khi PRD Gate 1, README hay báo cáo mâu thuẫn với spec thì theo spec. Danh sách mâu thuẫn ở mục 13.
>
> **Căn cứ:** đề bài chính thức (PO gửi ngày 21/09); báo cáo v0.4; design review (22 phát hiện, đã duyệt); `docs/eval/protocol.md`; `docs/survey/false-positives.md`.

---

## 0. Cách dùng spec để không phải đập đi xây lại

1. **Mọi việc trỏ về một ID.**
   - Yêu cầu có ID `FR-…` hoặc `NFR-…`, kèm mức ưu tiên, checkpoint và tiêu chí nghiệm thu (AC) đo được.
   - WP và TASK phải ghi ID. Việc chưa có ID thì chưa được bắt đầu (mục 9.1).
2. **Hợp đồng trước, code sau.**
   - Cấu hình cảnh, sự kiện và API ở mục 6 được chốt từ bây giờ, kể cả phần tới CP2 mới dùng.
   - Hai phía code theo cùng hợp đồng. Phía nào chưa có thì dùng dữ liệu mẫu ghi trong spec.
3. **Một mô hình cảnh, nhiều luật.**
   - Mọi loại vi phạm dùng chung cấu hình làn/vạch/vùng (mục 6.1) và cùng giao diện luật (mục 6.6).
   - Thêm loại vi phạm = thêm cấu hình + một lớp luật; không sửa pipeline.
4. **Lát dọc trước, làm sâu sau.** Mỗi tính năng chạy đủ đường edge → trung tâm → giao diện ở mức tối thiểu, rồi mới tinh chỉnh.
5. **Đổi spec có thủ tục** (mục 12): ghi lý do, ảnh hưởng, người duyệt, tăng phiên bản.
   - Thêm trường tùy chọn: không phá vỡ hợp đồng.
   - Đổi hoặc xóa trường: phải lên phiên bản mới.

---

## 1. Đối chiếu với đề bài chính thức

Các mức đánh giá trong bảng:
- **Vượt**: làm hơn yêu cầu.
- **Đúng**: đủ yêu cầu.
- **Thiếu**: chưa có, hoặc chưa đủ.
- **Thụt lùi**: đề yêu cầu nhưng thiết kế v0.3 lại hạ ưu tiên.
- **Lệch có chủ đích**: khác gợi ý của đề, có lý do đã duyệt.

| # | Đề bài | Thiết kế v0.3 | Đánh giá | Bổ sung trong spec |
|---|---|---|---|---|
| 1 | Xử lý on-edge; chỉ gửi metadata, sự kiện, ảnh bằng chứng đã làm mờ | Outbox; 3 bản bằng chứng; video thô không rời thiết bị | Đúng | Giữ: FR-SYNC, FR-PRV |
| 2 | Đếm, phân loại xe **theo làn và hướng** | Đếm theo vạch và hướng, chưa theo làn | Thiếu | FR-CNT-2 |
| 3 | Ước tính **mật độ, ùn tắc** | Có mật độ nhưng xếp SHOULD, nằm trong danh sách cắt | Thụt lùi | FR-DEN-1, FR-DEN-2, nâng lên MUST; thêm đo theo chu kỳ đèn và phân tích theo tuyến (FR-DEN-4, FR-COR-1, FR-COR-2) |
| 4 | Vi phạm **vượt đèn đỏ** | 6 điều kiện, 22 mã loại trừ, giao thức đo precision | Vượt | Giữ: FR-VIO-RL |
| 5 | Vi phạm **sai làn** | Chỉ nằm ở hướng mở rộng | Thiếu | FR-VIO-LN (đủ 3 kiểu, đều MUST) |
| 6 | Vi phạm **đi ngược chiều** | Chỉ nằm ở hướng mở rộng | Thiếu | FR-VIO-WW |
| 7 | (Phần thực trạng) **dừng, đỗ sai** | Chưa có | Thiếu | FR-VIO-ST (COULD) |
| 8 | Agent **lập luận ngữ cảnh** (pha đèn, giờ cao điểm) để giảm cảnh báo sai | Pha đèn có trong luật; Agent chỉ tóm tắt và bị cắt đầu tiên | Thụt lùi | FR-CTX-1 (lớp ngữ cảnh tất định), FR-AGT-2 (trợ lý giải thích) |
| 9 | Agent **tổng hợp báo cáo**, có tool báo cáo | SHOULD, bị cắt đầu tiên | Thụt lùi | FR-AGT-1, nâng lên MUST |
| 10 | Làm mờ biển số và khuôn mặt, trừ bằng chứng vi phạm **có phân quyền** | Bản CSGT chỉ mở sau duyệt bước 1, có nhật ký | Đúng | Giữ: FR-PRV, FR-HITL |
| 11 | Chống báo nhầm, precision cao | Giao thức có đăng ký trước, Wilson 95% | Vượt | FR-EVAL-3, mở rộng cho mọi loại vi phạm |
| 12 | Realtime **≥ 15 FPS** | Đo được 28 FPS trên CPU cho detect + track; chưa đo khi có luật và che | Thiếu phép đo đầu–cuối | NFR-PERF-1 |
| 13 | Chạy offline khi mất kết nối | Outbox đã chạy thử | Đúng | NFR-OFF-1 |
| 14 | Đo FPS, độ trễ, **kích thước model** | Kế hoạch đo còn chung chung | Thiếu | FR-OPT-1, FR-OPT-2, FR-OPT-3 |
| 15 | YOLOv8-nano + ByteTrack/DeepSORT, lượng tử hóa TensorRT/ONNX | YOLO26n + ByteTrack; TensorRT/ONNX | Vượt: model mới hơn, cùng giấy phép AGPL-3.0 | FR-OPT-2 thêm INT8 |
| 16 | ANPR/OCR biển số nhẹ, **chỉ dùng khi vi phạm** | Chỉ có detector biển số để che | Thiếu | FR-OCR-1 |
| 17 | Logic pha đèn và **vạch làn** | Có pha đèn, vạch dừng; chưa có vạch phân làn | Thiếu | Mô hình cảnh v2 (mục 6.1) |
| 18 | Mô phỏng camera bằng video mẫu | MediaMTX | Đúng | — |
| 19 | Backend FastAPI | Có | Đúng | — |
| 20 | Dashboard React + **bản đồ** | Next.js (React), chưa có bản đồ | Thiếu | FR-UI-3 |
| 21 | Mô phỏng Jetson edge | Chạy trên PC, trích số benchmark Jetson | Chưa rõ; đã có câu hỏi gửi BTC (L-04) | FR-OPT-3 |
| 22 | MQTT | Bỏ khỏi MVP (H-01) vì chỉ có 1 thiết bị | Lệch có chủ đích, nay đã xử lý | **Đã chốt (Q2):** ở CP2, MQTT làm kênh điều khiển (Last Will, thông báo trạng thái mong muốn và OTA; mục 6.7). Dữ liệu vẫn đi HTTPS + outbox |
| 23 | Docker | Có | Đúng | — |
| 24 | Cơ bản: đăng nhập **≥ 2 vai trò** | 4 vai trò | Đúng | FR-AUTH-1 |
| 25 | Cơ bản: HITL duyệt trước khi ghi nhận | Duyệt 2 bước | Vượt | FR-HITL-1…3 |
| 26 | Cơ bản: metric **mAP** | Chưa có | Thiếu | FR-EVAL-1 |
| 27 | Cơ bản: độ chính xác đếm | Có (M-01) | Đúng | FR-EVAL-2, thêm theo làn |
| 28 | Cơ bản: precision vi phạm | Có | Vượt | FR-EVAL-3 |
| 29 | Nâng cao: tối ưu edge (FPS, độ trễ, kích thước, offline) | Một phần | Thiếu | FR-OPT, NFR-OFF-1 |
| 30 | Nâng cao: ùn tắc + **gợi ý điều phối** | Chưa có gợi ý | Thiếu | FR-COR-1, FR-COR-2 (nguyên nhân ùn tắc theo tuyến); FR-DSP-1 gợi ý theo nguyên nhân |
| 31 | Nâng cao: **nhiều camera phối hợp** | 1 nút, 1 camera | Thiếu | FR-MC-1 (3 camera trên một tuyến), FR-COR-2 |
| 32 | Nâng cao: đánh giá đếm và vi phạm | Có | Đúng | — |
| 33 | Nâng cao: giám sát nhiều camera + **OTA** | Chưa có | Thiếu | FR-DEV-1, FR-DEV-2, FR-OTA-1 |
| 34 | Nâng cao: guardrails làm mờ, phân quyền truy cập bằng chứng | Có, và có đo tỉ lệ che lọt | Vượt | Giữ: FR-PRV, FR-EVAL-5 |

**Kết luận:**
- **Phần nền đúng hướng và mạnh hơn mặt bằng chung:** xử lý tại biên, riêng tư theo thiết kế, precision có giao thức chống thổi phồng, duyệt 2 bước, chạy khi mất mạng, chuỗi giám sát bằng chứng.
- **Phạm vi chức năng hẹp hơn đề:**
  - mới có 1 trong 3 loại vi phạm đề nêu;
  - mật độ/ùn tắc và Agent bị xếp vào nhóm cắt đầu tiên;
  - chưa có OCR, mAP, bản đồ;
  - chưa có mục nâng cao nào về nhiều camera, OTA, gợi ý điều phối.
- Spec này bổ sung các phần thiếu, **giữ nguyên các quyết định đã duyệt** (H-01…L-04), và sắp lại ưu tiên theo đề.

---

## 2. Phạm vi, ưu tiên và checkpoint

**Mức ưu tiên:**
- **MUST:** mục "Cơ bản" của đề, cộng các ràng buộc bắt buộc.
- **SHOULD:** các mục "Nâng cao" đã chọn.
- **COULD:** chỉ làm nếu còn thời gian; không tính vào % hoàn thành.
- **WON'T:** không làm trong giai đoạn này.

**Cỡ việc:** 1 = nhỏ, 2 = vừa, 3 = lớn. Cỡ dùng để tính % hoàn thành (mục 8.3).

| Nhóm tính năng | ID | Ưu tiên | Cỡ | Checkpoint |
|---|---|---|---|---|
| Thu nhận video, nhận diện, tracking | FR-CAM-1, FR-DET-1, FR-DET-2 | MUST | 2 | M1 → CP1 |
| Đếm theo làn, hướng, loại xe | FR-CNT-1, FR-CNT-2 | MUST | 2 | CP1 |
| Mật độ, hàng chờ, mức ùn tắc | FR-DEN-1, FR-DEN-2 | MUST | 2 | CP1 |
| Đo theo chu kỳ đèn (sự kiện `signal_cycle`) | FR-DEN-4 | MUST | 2 | CP1 |
| Hiệu năng từng nút: v/c, độ trễ, mức phục vụ | FR-COR-1 | MUST | 1 | CP1 |
| Phân tích tuyến: tràn hàng chờ, nút cổ chai | FR-COR-2 | MUST | 2 | CP1 |
| Máy trạng thái đèn | FR-LGT-1 | MUST | 3 | CP1 |
| Lớp ngữ cảnh và mã lý do | FR-CTX-1 | MUST | 1 | CP1 |
| Vượt đèn đỏ | FR-VIO-0, FR-VIO-RL | MUST | 3 | CP1 |
| Đi ngược chiều | FR-VIO-WW | MUST | 2 | CP1 |
| Sai làn LN-b, LN-c | FR-VIO-LN | MUST | 3 | CP1 |
| Sai làn LN-a | FR-VIO-LN | MUST | 1 | CP1 |
| Che biển số, khuôn mặt; 3 bản bằng chứng | FR-PRV-1, FR-PRV-2, FR-PRV-3 | MUST | 3 | CP1 |
| Gói bằng chứng có chữ ký | FR-EVD-1, FR-EVD-2 | MUST | 2 | CP1 |
| Đồng bộ mọi loại sự kiện | FR-SYNC-1, FR-SYNC-2 | MUST | 2 | M1 → CP1 |
| Đăng nhập, phân quyền | FR-AUTH-1 | MUST | 2 | CP1 |
| Duyệt 2 bước và nhật ký nối băm | FR-HITL-1, FR-HITL-2, FR-HITL-3 | MUST | 3 | CP1 |
| Dashboard, bản đồ, trang xác minh | FR-UI-1…FR-UI-4 | MUST | 3 | CP1 |
| Trang Tuyến | FR-UI-7 | MUST | 2 | CP1 |
| Heartbeat, trang sức khỏe, trạng thái mong muốn (chế độ điều khiển tay) | FR-DEV-1, FR-UI-5 | MUST | 2 | CP1 |
| OCR biển số xe vi phạm | FR-OCR-1 | SHOULD | 2 | CP1 |
| Agent báo cáo ca trực | FR-AGT-1, FR-UI-6 | MUST | 2 | CP1 |
| Xuất ONNX, TensorRT FP16 và benchmark | FR-OPT-1 | MUST | 2 | CP1 |
| Công cụ đo mAP và đếm (chạy trên dev) | FR-EVAL-1, FR-EVAL-2 | MUST | 1 | CP1 |
| Công cụ đo chu kỳ đèn và sự kiện tuyến (chạy trên dev) | FR-EVAL-8 | MUST | 1 | CP1 |
| 3 camera trên cùng một tuyến, chạy đồng thời | FR-MC-1 | MUST | 2 | CP1 |
| **Cộng tới CP1** | | | **53 / 65 ≈ 82%** | |
| OTA có ký, tự quay lại bản cũ; kênh điều khiển | FR-OTA-1, FR-DEV-2 | SHOULD | 2 | CP2 |
| Gợi ý điều phối khi ùn tắc | FR-DSP-1 | SHOULD | 2 | CP2 |
| Trợ lý giải thích ứng viên | FR-AGT-2 | SHOULD | 1 | CP2 |
| Xuất hồ sơ vi phạm | FR-EXP-1 | SHOULD | 1 | CP2 |
| INT8 và mô phỏng Jetson | FR-OPT-2, FR-OPT-3 | SHOULD | 1 | CP2 |
| Đánh giá trên tập test (mọi metric) | FR-EVAL-1…FR-EVAL-8 | MUST | 2 | CP2 |
| Sẵn sàng production, gồm cả Live URL | NFR-SEC-1, NFR-REL-1, NFR-OBS-1, NFR-DEP-1, NFR-DEP-2 | MUST | 3 | CP2 |
| **Tổng** | | | **65** | |

**COULD** (không tính vào %): FR-VIO-ST (dừng, đỗ sai); FR-AGT-3 (hỏi đáp số liệu); FR-DEN-3 (hồ sơ theo khung giờ); FR-INT-3, FR-INT-4, FR-INT-5. FR-MC-2 đã gộp vào FR-COR-2.

**WON'T trong giai đoạn này:**
- mua Jetson thật (trừ khi PO đổi quyết định);
- nhận diện khuôn mặt (không bao giờ làm);
- đo tốc độ để xử phạt (thiết bị cần kiểm định);
- phát hiện mũ bảo hiểm, dây an toàn (cần model và dữ liệu riêng);
- tự tính hoặc tự đổi thời gian đèn: PO chọn chỉ phân tích ùn tắc (Q6). FR-DSP-1 vẫn chỉ gợi ý, người quyết định. Việc tính thời gian đèn tối ưu (Webster, kiểm chứng bằng mô phỏng SUMO) để ở hướng mở rộng (báo cáo mục 19).

---

## 3. Vai trò và quyền

"—" là không có quyền. Mọi quyền được kiểm ở backend, không chỉ ẩn trên giao diện.

| Hành động | Điều hành viên (`operator`) | CSGT (`csgt`) | Quản trị (`admin`) | Kiểm toán (`auditor`) | Thiết bị edge |
|---|---|---|---|---|---|
| Xem số đếm, mật độ, phân tích tuyến, bản đồ, sức khỏe camera | ✓ | ✓ | ✓ | ✓ | — |
| Xem ứng viên, bản điều hành viên (đã che) | ✓ | ✓ | — | — | — |
| Duyệt bước 1 | ✓ | — | — | — | — |
| Xem bản CSGT (sau bước 1; mỗi lần xem được ghi nhật ký) | — | ✓ | — | — | — |
| Duyệt bước 2, xuất hồ sơ vi phạm | — | ✓ | — | — | — |
| Yêu cầu và duyệt báo cáo của Agent | ✓ | ✓ | — | — | — |
| Chấp nhận hoặc bỏ qua gợi ý điều phối | ✓ | — | — | — | — |
| Bật hoặc tắt chế độ điều khiển tay của nút giao (có ghi nhật ký) | ✓ | — | — | — | — |
| Quản lý camera, cấu hình cảnh, bản phát hành OTA | — | — | ✓ | — | — |
| Xem nhật ký truy cập, kiểm chuỗi nối băm | — | — | ✓ | ✓ | — |
| Gửi sự kiện, bằng chứng, heartbeat; nhận cấu hình | — | — | — | — | ✓ (token riêng mỗi thiết bị) |

Đề bài yêu cầu tối thiểu 2 vai trò (người vận hành và quản trị/CSGT); thiết kế có 4 vai trò người dùng.

---

## 4. Yêu cầu chức năng (FR)

Mỗi yêu cầu có tiêu chí nghiệm thu (AC). Con số đánh dấu [mục tiêu] là đích ban đầu; được chốt lại sau lần đo đầu tiên, và việc chốt lại phải ghi vào mục 12.

### 4.1 Thu nhận video, nhận diện, tracking

**FR-CAM-1** — MUST · M1 → CP1

Nguồn video là file đã chuẩn hóa 15 FPS cố định, hoặc luồng RTSP. Mất luồng RTSP thì tự kết nối lại.
- AC1: với file 15 FPS, số khung được xử lý bằng `nb_frames` của file.
- AC2: tắt MediaMTX 30 giây rồi bật lại. Edge xử lý tiếp trong ≤ 10 giây sau khi luồng có lại, không thoát tiến trình, outbox nguyên vẹn.
- AC3: log ghi mỗi lần mất luồng và mỗi lần có lại.

**FR-DET-1** — MUST · CP1

Phát hiện `car`, `motorcycle`, `bus`, `truck`, và `person` (dùng để che mặt và cho mã loại trừ B4).
- AC: mAP được báo cáo theo FR-EVAL-1.
- Điểm quyết định trước 04/10: nếu AP50 của `motorcycle` trên tập khung dev < 0,5 thì mở việc tinh chỉnh model.

**FR-DET-2** — MUST · CP1

ByteTrack với `persist=True`, giữ ID trên từng luồng.
- AC: báo cáo tỉ lệ sự kiện thật được một track liền mạch bao phủ (protocol mục 6).

### 4.2 Đếm, mật độ, ùn tắc tại nút và theo tuyến

**FR-CNT-1** — MUST · M1

Đếm xe cắt vạch theo hướng và loại xe, gom theo bucket 60 giây.
- AC: test của TASK-003 và TASK-004 trong plan M1 pass.

**FR-CNT-2** — MUST · CP1

Gán `lane_id` cho xe theo polygon làn tại điểm cắt vạch (sự kiện count v1.1, mục 6.3).
- AC1: mọi xe cắt vạch trong polygon làn có `lane_id`; xe nằm ngoài mọi làn có `lane_id = null`.
- AC2: [mục tiêu] sai số phần trăm của tổng số đếm từng làn ≤ 10%, đo trên 2 đoạn × 10 phút đếm tay của tập dev; báo riêng xe máy.

**FR-DEN-1** — MUST · CP1

Mỗi làn, mỗi phút tính:
- lưu lượng (xe/phút);
- độ chiếm dụng trung bình (số xe trong polygon làn);
- tốc độ trung bình km/h (cần homography; không có thì để `null`);
- hàng chờ lớn nhất (số xe đứng yên liên tiếp tính từ vạch dừng).

AC: [mục tiêu] sai số tuyệt đối trung bình của hàng chờ ≤ 2 xe, đo trên ≥ 20 chu kỳ đèn đếm tay (dev).

**FR-DEN-2** — MUST · CP1

Mức ùn tắc 0–3 (thông thoáng / chậm / đông / ùn tắc), theo ngưỡng trong cấu hình. Sinh sự kiện `congestion` khi một trong hai điều kiện đúng:
- (a) mức ≥ 2 kéo dài ≥ K phút;
- (b) **xe không thoát hết trong một pha xanh** (vẫn còn hàng chờ khi đèn xanh kết thúc) ≥ K chu kỳ liên tiếp. Đây là khái niệm "cycle failure" trong kỹ thuật giao thông.

AC: trên các đoạn dev được người gán nhãn "ùn tắc", sự kiện xuất hiện trong ≤ 2 phút; trên các đoạn gán nhãn "thông thoáng" không có sự kiện nào.

**FR-DEN-3** — COULD

Hồ sơ theo khung giờ (giờ cao điểm cấu hình được), để báo "bất thường so với cùng khung giờ các ngày trước".

**FR-DEN-4** — MUST · CP1: đo theo chu kỳ đèn

Mỗi chu kỳ đèn tính từ lúc đèn bắt đầu xanh tới lần bắt đầu xanh kế tiếp. Với mỗi đầu đèn và nhóm làn nó điều khiển, cứ hết một chu kỳ edge gửi một sự kiện `signal_cycle` (mục 6.3), gồm:
- thời gian xanh, vàng, đỏ thực tế (từ FR-LGT-1);
- số xe đến (cắt vạch đếm) và số xe thoát (cắt vạch dừng), theo loại xe;
- hàng chờ lớn nhất, và số xe còn kẹt khi hết xanh;
- lượt thoát bão hòa: số xe thoát và số giây, tính từ đầu pha xanh tới khi hàng chờ có sẵn lúc bắt đầu xanh đã thoát hết (hoặc tới khi hết xanh);
- số giây vùng giao lộ bị chặn khi đèn xanh, tức có xe đứng yên trong vùng giao lộ;
- số giây hàng chờ dài quá khung hình, tức đuôi hàng chờ chạm mép xa của làn trong ảnh.

Chu kỳ có lúc đèn ở trạng thái `UNKNOWN` vẫn được gửi nhưng mang `valid = false`; trung tâm không dùng các chu kỳ này.

AC:
- AC1: độ dài chu kỳ và thời gian xanh có sai số trung vị ≤ 1 giây so với nhãn đèn (dev). [mục tiêu]
- AC2: số xe thoát mỗi chu kỳ sai lệch ≤ 10% so với đếm tay, trên ≥ 20 chu kỳ mỗi nút (dev). [mục tiêu]
- AC3: có test cho việc cắt chu kỳ từ chuỗi trạng thái đèn, gồm cả chu kỳ có `UNKNOWN`.

**FR-COR-1** — MUST · CP1: hiệu năng từng nút

Trung tâm tính cho mỗi nút, theo khung 15 phút, chỉ từ các chu kỳ hợp lệ:

```text
PCU theo TCVN 13592:2022 Bảng 3, cột tốc độ thiết kế 30–50 km/h (cấu hình được, mục 6.8):
  xe máy 0,3 · ô tô con 1,0 · xe tải 2,5 · xe buýt 3,0

q   = lưu lượng đến (PCU/giờ)
s   = trung vị tốc độ thoát bão hòa của các chu kỳ (PCU/giờ xanh); cần ≥ 5 chu kỳ hợp lệ
g/C = tỉ lệ xanh thực tế;   c = s · g/C;   X = q / c
d1  = 0,5 · C · (1 − g/C)² / (1 − min(1, X) · g/C)
d2  = 900 · T · [(X − 1) + √((X − 1)² + 8 · k · I · X / (c · T))],   T = 0,25 giờ; k = 0,5; I = 1
trễ = d1 + d2 (giây/xe)
LOS: A ≤ 10 · B ≤ 20 · C ≤ 35 · D ≤ 55 · E ≤ 80 · F > 80 giây/xe
     quy ước của spec: X > 1 cũng xếp F, vì khi quá tải thì trễ ước tính không còn đáng tin
% chu kỳ thất bại = số chu kỳ còn xe kẹt khi hết xanh / số chu kỳ hợp lệ
```

Quy định kèm theo:
- Khi hàng chờ dài quá khung hình, xe đến bị đếm trễ, nên q thấp hơn nhu cầu thật. Kết quả khi đó ghi "X ≥ giá trị đo" và gắn cờ `lower_bound`.
- Không đủ chu kỳ hợp lệ thì trả "không đủ dữ liệu"; hệ thống không suy đoán.
- Độ trễ và LOS là **ước tính theo HCM**. Không có nhãn thật để đối chiếu; điều này ghi vào mục hạn chế.

AC:
- AC1: có test so công thức với ví dụ tính tay: ít nhất 3 bộ số, trong đó có một bộ X > 1.
- AC2: tốc độ thoát bão hòa sai lệch ≤ 15% so với đếm tay kèm bấm giờ, trên ≥ 20 chu kỳ mỗi nút (dev). [mục tiêu]

**FR-COR-2** — MUST · CP1: phân tích ùn tắc theo tuyến

Tuyến gồm 3 nút có đèn liên tiếp; 3 camera cùng nhìn theo một chiều xe chạy (FR-MC-1, cấu hình ở mục 6.8). Giờ của 3 camera khớp nhau trong ± 1 giây: manifest ghi giờ bắt đầu quay, và mỗi máy quay màn hình đồng hồ chuẩn lúc bắt đầu.

Các quy tắc đều tất định. Ngưỡng nằm trong `configs/frozen/corridor-v1.yaml` (mục 6.2), được chỉnh trên dev và đóng băng ngày 11/10:
- **Tràn hàng chờ từ B về A** (B là nút phía trước của A theo chiều xe chạy) khi đủ cả hai điều kiện:
  - ở A, trong ≥ 2 chu kỳ liên tiếp: đèn xanh, có hàng chờ, nhưng xe thoát < 30% tốc độ bão hòa, hoặc vùng giao lộ bị chặn;
  - cùng lúc đó (lệch không quá 1 chu kỳ), B đang ùn tắc (mức ≥ 2) hoặc hàng chờ ở B dài quá khung hình.

  Khi đó trung tâm sinh sự kiện tuyến `spillback` tại A, với `cause_node = B`.
- **Nút cổ chai:** nút xa nhất theo chiều xe chạy đang ùn tắc (X ≥ 0,9, hoặc ≥ 50% chu kỳ thất bại), và nguyên nhân không phải do nút phía trước tràn về. Khi đó sinh sự kiện tuyến `bottleneck`.
- Nút mất kết nối hoặc thiếu chu kỳ hợp lệ bị đánh dấu "không đủ dữ liệu", và quy tắc không dùng nút đó để kết luận.
- Mỗi sự kiện tuyến kèm các con số làm căn cứ: X, % chu kỳ thất bại, số giây vùng giao lộ bị chặn…

Chỉ phân tích chiều xe chạy mà camera nhìn. Chiều ngược lại không đo; điều này ghi vào mục hạn chế.

AC:
- AC1: có test cho từng quy tắc bằng chuỗi số liệu dựng sẵn, gồm các trường hợp: có tràn; không tràn; có dấu hiệu tràn nhưng thiếu dữ liệu ở B; hai nút cùng tắc.
- AC2: trên các đoạn dev đã gán nhãn "tràn hàng chờ", sự kiện `spillback` xuất hiện, lệch không quá 1 chu kỳ. Báo precision và recall; n < 30 thì ghi "chỉ minh họa".
- AC3: phát lại một buổi quay dev của cả tuyến (3 video cùng lúc) thì trang Tuyến hiện các sự kiện đúng thứ tự thời gian.

### 4.3 Pha đèn và ngữ cảnh

**FR-LGT-1** — MUST · CP1

Máy trạng thái đèn theo báo cáo mục 8, bước 6.
- AC1: sai lệch mốc chuyển pha trung vị ≤ 2 khung so với nhãn đèn (dev).
- AC2: trong toàn bộ thời gian ROI bị che, trạng thái là `UNKNOWN`; hệ thống không đoán.
- AC3: output không có chuyển pha không hợp lệ (ví dụ XANH → ĐỎ mà không qua VÀNG).

**FR-CTX-1** — MUST · CP1

Lớp ngữ cảnh **tất định**, dùng chung cho mọi luật. Ngữ cảnh gồm:
- pha đèn của làn;
- cửa sổ có xe ưu tiên;
- chế độ điều khiển tay (điều hành viên bật hoặc tắt; edge nhận qua `desired`, FR-DEV-1);
- mức mật độ hiện tại;
- khung giờ.

Mọi ứng viên bị loại đều có mã lý do. Mỗi phút gửi một sự kiện `rejection_summary`.
- AC1: 100% lần loại có mã lý do nằm trong danh mục của `false-positives.md`.
- AC2: có báo cáo ablation trên dev: tắt từng nhóm loại trừ thì số FP tăng bao nhiêu (số đo thật).

Đây là phần **"lập luận ngữ cảnh để giảm cảnh báo sai"** của đề bài. Theo CLAUDE.md mục 7–8, quyết định vi phạm là tất định; LLM không quyết định. Agent (FR-AGT-2) chỉ giải thích và điều tra khi người dùng yêu cầu; không tự xác nhận hay bác bỏ.

### 4.4 Vi phạm

Tóm tắt luật ở mục 7; chi tiết điều kiện và mã loại trừ ở `docs/survey/false-positives.md`.

**FR-VIO-0** — MUST · CP1

Giao diện luật chung (mục 6.6). Mỗi ứng viên có `violation`, `track_id`, `lane_id`, thời điểm, các điều kiện đo được, `config_sha256`, `model_version`.
- AC1: review code xác nhận thêm một luật chỉ cần một file luật và một mục cấu hình.
- AC2: mọi luật chạy chung một bộ test hợp đồng.

**FR-VIO-RL** — MUST · CP1

Vượt đèn đỏ: 6 điều kiện; dùng vùng giao lộ (M-03) và điểm đầu xe ước lượng (H-05).
- AC1: các ca khó A1–E5 có trong tập dev bị loại đúng mã; trình diễn được ít nhất 1 ca mỗi nhóm A, B, D, E.
- AC2: precision trên dev (leave-one-video-out) kèm Wilson 95% được báo cáo trước ngày đóng băng.
- AC3: precision trên tập test theo protocol, tại CP2.

**FR-VIO-WW** — MUST · CP1

Đi ngược chiều (mục 7.2).
- AC1: trong các clip dev có ca ngược chiều đã gán nhãn, ít nhất 1 ca đi đầu–cuối tới màn hình duyệt.
- AC2: các ca W1–W8 xuất hiện trong dev bị loại đúng mã.
- AC3: precision trên tập test được báo cáo; nếu n < 30 thì ghi "chỉ minh họa".

**FR-VIO-LN** — MUST · CP1

Động cơ luật làn với 3 kiểu (mục 7.3):
- LN-a: sai làn theo loại xe;
- LN-b: chuyển làn qua vạch liền;
- LN-c: đi sai hướng theo mũi tên của làn.

**Cả 3 kiểu đều MUST** (PO chốt 21/09, Q8).
- Mỗi kiểu có AC riêng như FR-VIO-WW (AC1–AC3) và dùng mã L1–L8.
- Precision trên tập test báo riêng từng kiểu.
- Dữ liệu cho từng kiểu lấy từ các nút trên tuyến; tiêu chí chọn tuyến ở timeline, WP-02.

**FR-VIO-ST** — COULD

Dừng, đỗ trong vùng cấm (mục 7.4). Nếu làm sau ngày đóng băng thì chỉ trình diễn, không báo precision.

### 4.5 Bằng chứng, riêng tư, OCR

**FR-EVD-1** — MUST · CP1

Gói bằng chứng cho mọi loại vi phạm, gồm:
- 3 khung chính, chọn theo từng loại vi phạm;
- clip là chuỗi JPEG từ t − 3 s tới t + 2 s (Orin Nano không có bộ mã hóa video phần cứng);
- manifest (mục 6.4);
- SHA-256 và chữ ký Ed25519;
- `parent_hash` trỏ tới bản đầy đủ nằm trên thiết bị.

AC:
- AC1: sửa 1 byte bất kỳ thì phép xác minh báo sai (có test).
- AC2: [mục tiêu] gói tạo xong ≤ 3 giây sau khi luật kích hoạt, kích thước ≤ 5 MB.

**FR-EVD-2** — MUST · CP1

Gói được tải lên sau metadata, có checksum, và tải tiếp khi có mạng lại.
- AC: ngắt mạng giữa lúc đang tải. Sau khi nối lại, gói ở trung tâm có SHA-256 khớp manifest.

**FR-PRV-1** — MUST · CP1

Bản điều hành viên che mọi biển số và khuôn mặt. Nếu detector biển số không chắc chắn thì che nửa dưới bbox của xe (dự phòng).

**FR-PRV-2** — MUST · CP1

Bản CSGT: chỉ xe vi phạm hiện rõ; mọi xe khác vẫn bị che.

**FR-PRV-3** — MUST · CP1

Bản đầy đủ không che: niêm phong, chỉ nằm trên thiết bị, bị xóa khi hết thời hạn lưu giữ (Q5 đề xuất 7 ngày).

AC chung cho FR-PRV:
- tỉ lệ che lọt trên tập test được báo cáo kèm Wilson 95% (FR-EVAL-5);
- [mục tiêu] ≤ 1% biển số bị lọt;
- mọi ca lọt được liệt kê.

**FR-OCR-1** — SHOULD · CP1

OCR biển số **chỉ cho xe vi phạm**:
- cắt ảnh biển số ở các khung tốt nhất, bỏ phiếu qua nhiều khung;
- trả chuỗi biển số kèm độ tin cậy; dưới ngưỡng thì đánh dấu "cần người đọc";
- chuỗi biển số chỉ nằm trong trường mà CSGT mới xem được.

AC:
- AC1: không có lời gọi OCR nào cho xe không vi phạm (kiểm bằng test và log).
- AC2: báo cáo tỉ lệ khớp hoàn toàn trên các ca vi phạm của tập test (FR-EVAL-6).
- AC3: 100% ca có độ tin cậy thấp được chuyển cho người đọc.

Công cụ được chọn ở WP-37, giữa fast-plate-ocr (giấy phép MIT, chạy ONNX) và PaddleOCR (Apache-2.0). Phải thử trên biển số Việt Nam 2 dòng, vì tài liệu fast-plate-ocr không nhắc tới Việt Nam hay biển số 2 dòng.

### 4.6 Truyền dữ liệu và quản lý thiết bị

**FR-SYNC-1** — MUST · M1

Outbox và sender (plan M1, TASK-008 và TASK-009).

**FR-SYNC-2** — MUST · CP1

Mọi loại sự kiện ở mục 6.3 đi qua cùng outbox; trung tâm chống trùng theo `event_id`.
- AC: ngắt mạng 10 phút trong lúc có cả vi phạm lẫn số đếm. Sau khi nối lại, tổng số bản ghi bằng số `event_id` khác nhau, và không thiếu phút nào.

**FR-DEV-1** — MUST · CP1

Heartbeat mỗi 10 giây (sự kiện health v1). Trung tâm đánh dấu thiết bị mất kết nối khi quá 30 giây không nhận được heartbeat.

Cũng mỗi 10 giây, edge gọi `GET /api/v1/devices/{id}/desired` để lấy **trạng thái mong muốn** (mục 6.7). Ở CP1, trạng thái này là chế độ điều khiển tay của từng camera, dùng cho các mã C4, W6, L8. Từ CP2, trạng thái có thêm cấu hình và bản phát hành. Đây chính là kênh "trung tâm → edge bằng hỏi định kỳ" đã duyệt ở design review (báo cáo mục 6.6): thiết bị không phải mở cổng nào.
- AC1: tắt edge thì trang sức khỏe báo "mất kết nối" trong ≤ 40 giây.
- AC2: điều hành viên bật chế độ điều khiển tay thì trong ≤ 15 giây edge ngừng tạo ứng viên RL, WW, LN ở camera đó. Các lần bị chặn được ghi mã C4, W6, L8. Có test.
- AC3: gọi `desired` thất bại (mất mạng, lỗi 5xx) thì edge giữ trạng thái đã nhận gần nhất, không quay về mặc định. Có test.

**FR-DEV-2** — SHOULD · CP2 · đã chốt Q2

Thêm kênh điều khiển bằng **MQTT**; hợp đồng ở mục 6.7. MQTT chỉ làm hai việc:
- báo thiết bị còn sống: broker phát **Last Will** `offline` khi edge rớt kết nối mà không kịp báo;
- báo "trạng thái mong muốn vừa đổi": edge gọi `GET desired` ngay, không chờ hết chu kỳ 10 giây.

Những gì không đổi:
- nội dung trạng thái mong muốn vẫn lấy qua HTTPS; cấu hình và model phải qua kiểm chữ ký theo FR-OTA-1;
- sự kiện và bằng chứng vẫn đi HTTPS + outbox (H-01);
- hỏi định kỳ 10 giây (FR-DEV-1) vẫn chạy. Mất broker thì hệ thống chỉ chậm hơn, không mất chức năng.

AC:
- AC1: tắt tiến trình edge đột ngột hoặc ngắt mạng của edge thì bản đồ và trang sức khỏe báo "mất kết nối" trong ≤ 10 giây.
- AC2: bật chế độ điều khiển tay thì edge áp dụng trong ≤ 5 giây.
- AC3: tắt broker thì FR-DEV-1 AC2 (≤ 15 giây) vẫn đạt, và trang sức khỏe báo "kênh điều khiển gián đoạn".

**FR-OTA-1** — SHOULD · CP2

Cập nhật cấu hình hoặc model bằng bản phát hành có ký (Ed25519, khóa của quản trị) kèm SHA-256. Quy trình trên edge:
1. kiểm chữ ký;
2. áp dụng;
3. theo dõi sức khỏe trong 2 phút;
4. giữ bản mới, hoặc tự quay lại bản cũ.

Bản phát hành được thử trên 1 camera trước (canary).
- AC1: bản phát hành sai chữ ký bị từ chối (có test).
- AC2: model hỏng (không chạy được) thì edge tự quay lại bản cũ trong ≤ 3 phút (trình diễn).
- AC3: trang sức khỏe hiện phiên bản đang chạy.

### 4.7 Trung tâm và duyệt

**FR-AUTH-1** — MUST · CP1

Đăng nhập bằng tên và mật khẩu (băm bằng bcrypt hoặc argon2); JWT gồm access token 15 phút và refresh token; 4 vai trò.
- AC: có test cho mọi endpoint: sai vai trò trả 403, thiếu token trả 401.
- Trong M1, các endpoint đọc chưa cần đăng nhập (chỉ chạy localhost). Từ CP1, mọi endpoint đọc cần JWT.

**FR-HITL-1** — MUST · CP1

Duyệt bước 1 (điều hành viên, xem bản đã che): xác nhận, hoặc bác bỏ kèm mã lý do.
- AC1: quyết định được lưu kèm người duyệt, thời điểm, mã lý do.
- AC2: ứng viên mới hiện trên hàng đợi trong ≤ 5 giây mà không cần tải lại trang.

**FR-HITL-2** — MUST · CP1

Duyệt bước 2 (CSGT, xem bản CSGT), chỉ sau khi đã có bước 1: phê duyệt hoặc bác bỏ.
- AC1: CSGT không mở được bản CSGT khi chưa có xác nhận bước 1 (có test).
- AC2: mỗi lần xem sinh một dòng nhật ký.

**FR-HITL-3** — MUST · CP1

Nhật ký truy cập nối băm; mã băm đầu chuỗi được commit hằng ngày (L-02); có công cụ kiểm chuỗi.
- AC: sửa 1 dòng nhật ký thì công cụ kiểm báo đứt chuỗi.

**FR-EXP-1** — SHOULD · CP2 (chuyển từ CP1 ngày 21/09 để giảm tải cho TV3)

CSGT xuất hồ sơ vi phạm đã phê duyệt (PDF + JSON, kèm mã băm, chữ ký, link xác minh) cho quy trình phạt nguội.
- AC: hồ sơ mở được khi không có mạng; mã băm trong hồ sơ khớp với trang xác minh.

### 4.8 Giao diện

Yêu cầu chung cho mọi trang: tiếng Việt; responsive từ 360 px; dark mode theo hệ điều hành; có trạng thái đang tải, lỗi, rỗng. AC chung: qua checklist UX trên máy tính và điện thoại.

| ID | Trang | Ưu tiên · CP |
|---|---|---|
| FR-UI-1 | Số đếm theo camera/làn/loại/hướng; mật độ và mức ùn tắc theo thời gian | MUST · CP1 |
| FR-UI-2 | Hàng đợi duyệt theo vai trò; lọc theo loại vi phạm và trạng thái; cập nhật trực tiếp bằng SSE | MUST · CP1 |
| FR-UI-3 | Bản đồ (Leaflet + OpenStreetMap): vị trí camera, màu theo trạng thái (trực tuyến / mất kết nối / ùn tắc). Không có Internet thì hiện ảnh bản đồ tĩnh | MUST · CP1 |
| FR-UI-4 | Trang xác minh bằng chứng: chữ ký, mã băm, chuỗi `parent_hash`. Không hiện ảnh nên có thể mở công khai | MUST · CP1 |
| FR-UI-5 | Trang sức khỏe: mỗi camera có trạng thái (theo bảng ở mục 6.7), FPS, độ trễ, số khung rơi, độ sâu outbox, nhiệt độ, phiên bản model và cấu hình, lần cuối nhận heartbeat. Có nút bật hoặc tắt chế độ điều khiển tay (chỉ `operator`); khi đang bật, dashboard hiện băng cảnh báo cho biết bật từ lúc nào | MUST · CP1 |
| FR-UI-6 | Trang báo cáo: bản nháp của Agent, người duyệt, lịch sử | MUST · CP1 |
| FR-UI-7 | Trang Tuyến: bản đồ tuyến tô màu theo mức ùn tắc, có mũi tên chỉ hướng tràn hàng chờ; bản đồ nhiệt nút × thời gian (ô 5 phút); thẻ từng nút (LOS, X, % chu kỳ thất bại, chu kỳ và thời gian xanh thực tế, tốc độ thoát bão hòa); danh sách sự kiện tuyến kèm số liệu; nút thiếu dữ liệu hiện màu xám | MUST · CP1 |

### 4.9 Agent (LangGraph)

**FR-AGT-1** — MUST · CP1: báo cáo ca trực và báo cáo sự cố

- Công cụ chỉ đọc số liệu tổng hợp: số đếm, mật độ, sự kiện ùn tắc, phân tích tuyến (`corridor_summary`: nút cổ chai, các lần tràn hàng chờ, khung giờ có mức phục vụ xấu nhất), thống kê ứng viên theo loại và trạng thái, sức khỏe camera. Không trả biển số hay ảnh (M-05).
- Báo cáo gồm số liệu, sự kiện nổi bật, mục "Ùn tắc theo tuyến", đề xuất, và ID các sự kiện nguồn.
- Chỉ phát hành sau khi người duyệt (`interrupt()` của LangGraph).
- Không gọi được LLM thì sinh báo cáo theo mẫu cố định từ cùng số liệu.

AC:
- AC1: mọi con số trong báo cáo khớp kết quả công cụ (có test so khớp).
- AC2: báo cáo cho 1 ca (8 giờ dữ liệu) tạo xong ≤ 60 giây.
- AC3: cắt mạng tới LLM thì vẫn có báo cáo theo mẫu, gắn nhãn "không dùng LLM".

**FR-AGT-2** — SHOULD · CP2: trợ lý giải thích ứng viên

Người duyệt hỏi "vì sao xe này bị gắn cờ?". Agent gọi công cụ để lấy:
- các điều kiện đo được;
- dòng thời gian của đèn;
- các cờ rủi ro tất định: đèn kém tin cậy, xe bị che, nhiều ứng viên cùng lúc (có thể đang điều khiển tay);

rồi trả lời bằng ngôn ngữ tự nhiên. Agent **không** xác nhận, không bác bỏ, không sắp lại hàng đợi.

AC: câu trả lời trích đúng giá trị đo (có test); Agent không có công cụ ghi.

**FR-AGT-3** — COULD (hạ từ SHOULD ngày 21/09 để bù tải): hỏi đáp trên số liệu tổng hợp

Ví dụ: "nút nào nhiều vi phạm nhất tuần này?".
- AC: 10 câu hỏi mẫu được trả lời đúng khi đối chiếu với truy vấn SQL.

**FR-DSP-1** — SHOULD · CP2: gợi ý điều phối

- Khi có sự kiện ùn tắc, luật tất định đề xuất hành động kèm số liệu:
  - kéo dài pha xanh của hướng ùn tắc thêm 5–15 giây, nếu hướng cắt ngang còn dư năng lực;
  - điều CSGT tới nút;
  - thông báo phân luồng.
- Luật dùng nguyên nhân từ FR-COR-2. Nếu nút A tắc vì hàng chờ từ B tràn về thì gợi ý xử lý tại B, và **không** gợi ý kéo dài xanh ở A: xanh thêm chỉ đẩy thêm xe vào đoạn đường đang kẹt.
- Agent chỉ viết phần giải thích.
- Điều hành viên chấp nhận hoặc bỏ qua. Hệ thống không tự điều khiển đèn.

AC:
- trên đoạn dev có ùn tắc, gợi ý xuất hiện ≤ 2 phút sau sự kiện;
- mỗi gợi ý có số liệu nguồn;
- quyết định của người được lưu lại.

### 4.10 Nhiều camera

**FR-MC-1** — MUST · CP1 (nâng từ SHOULD ngày 21/09, vì phân tích tuyến cần)

3 luồng camera chạy đồng thời (3 đường MediaMTX, 3 cấu hình cảnh), đặt ở 3 nút liên tiếp của cùng một tuyến (FR-COR-2).
- AC1: mỗi luồng đạt ≥ 15 FPS trên máy demo trong 30 phút; nếu không đạt thì ghi rõ số luồng tối đa vẫn giữ được ≥ 15 FPS.
- AC2: cả 3 camera hiện trên bản đồ và trang sức khỏe.

**FR-MC-2** — gộp vào FR-COR-2 (21/09). Quan hệ trước/sau giữa các nút khai báo trong cấu hình tuyến (mục 6.8).

### 4.11 Tối ưu edge

**FR-OPT-1** — MUST · CP1

Xuất YOLO26n sang ONNX và TensorRT FP16. Script benchmark in bảng gồm:
- FPS;
- độ trễ p50/p95 từng tầng: giải mã, detect, track, luật, bằng chứng;
- kích thước model;
- mAP50 trên tập khung dev, cho từng định dạng.

AC: bảng có trong báo cáo đánh giá và chạy lại được bằng một lệnh.

**FR-OPT-2** — SHOULD · CP2

INT8 (TensorRT hoặc ONNX Runtime), hiệu chuẩn bằng khung dev. Chỉ dùng nếu mAP50 giảm ≤ 2 điểm.

**FR-OPT-3** — SHOULD · CP2

"Mô phỏng Jetson": chạy edge trong container giới hạn tài nguyên (CPU và 8 GB RAM như Jetson Orin Nano) và báo FPS; kèm số benchmark chính thức của Ultralytics cho Jetson, có trích nguồn. Điều chỉnh lại theo câu trả lời của BTC (L-04).

### 4.12 Đánh giá

Chi tiết ở `docs/eval/protocol.md` mục 13.

| ID | Metric | Ghi chú |
|---|---|---|
| FR-EVAL-1 | mAP50, mAP50-95, AP từng lớp | Tập khung dev (~200) dùng để chọn model. Tập khung test (~150, trích từ phiên test) gán nhãn **không** dùng model gợi ý |
| FR-EVAL-2 | Độ chính xác đếm theo làn và loại: sai số tuyệt đối, sai số % | Mở rộng M-01 |
| FR-EVAL-3 | Precision, recall từng loại vi phạm; Wilson 95%; báo nhầm/giờ/camera | n < 30 thì "chỉ minh họa" |
| FR-EVAL-4 | Sai số hàng chờ; độ đồng thuận mức ùn tắc với người đánh giá | |
| FR-EVAL-5 | Tỉ lệ che lọt | H-04 |
| FR-EVAL-6 | OCR: tỉ lệ khớp hoàn toàn; tỉ lệ phải chuyển cho người đọc | |
| FR-EVAL-7 | FPS đầu–cuối khi bật mọi luật; độ trễ p95 từ khung sự kiện tới outbox; CPU, GPU, RAM | |
| FR-EVAL-8 | Chu kỳ đèn và tuyến: sai số chu kỳ và thời gian xanh; sai số tốc độ thoát bão hòa; sai số số xe thoát mỗi chu kỳ; precision/recall "chu kỳ thất bại"; precision/recall sự kiện tràn hàng chờ | protocol mục 13.8. Độ trễ và LOS không có nhãn thật |

### 4.13 Tích hợp

| ID | Tích hợp | Ưu tiên |
|---|---|---|
| FR-INT-1 | Bản đồ (chính là FR-UI-3) | MUST |
| FR-INT-2 | Xuất hồ sơ cho quy trình phạt nguội (chính là FR-EXP-1) | SHOULD |
| FR-INT-3 | API dữ liệu mở: chỉ đọc số liệu tổng hợp, có khóa API, có tài liệu OpenAPI | COULD |
| FR-INT-4 | Bot Telegram báo camera mất kết nối hoặc ùn tắc cho điều hành viên | COULD |
| FR-INT-5 | Bộ điều khiển đèn giả lập, nhận các gợi ý đã được người duyệt | COULD |

---

## 5. Yêu cầu phi chức năng (NFR)

| ID | Yêu cầu | Cách đo | CP |
|---|---|---|---|
| NFR-PERF-1 | ≥ 15 FPS đầu–cuối mỗi luồng khi bật mọi luật; video 1080p, `imgsz` 640, trên máy demo có GPU. Báo thêm số khi chỉ dùng CPU | FPS trung bình trong 30 phút; ở chế độ live, số khung rơi ≤ 1% | CP1 đo, CP2 đạt |
| NFR-PERF-2 | Độ trễ p95 từ khung vi phạm hoàn tất tới lúc vào outbox ≤ 1 giây; tới dashboard ≤ 5 giây khi có mạng | Timestamp trong log | CP1 |
| NFR-PERF-3 | Báo kích thước model (MB); edge dùng ≤ 4 GB RAM và < 80% CPU trên máy demo | Benchmark | CP1 |
| NFR-OFF-1 | Mất mạng ≥ 24 giờ vẫn lưu đủ sự kiện và bằng chứng trong hạn mức đĩa cấu hình; nối lại thì gửi bù theo thứ tự, không trùng | Thử thật 1 giờ; tính toán dung lượng cho 24 giờ và 7 ngày trong runbook | CP2 |
| NFR-PRIV-1 | Video thô liên tục không rời thiết bị. Báo **băng thông thực đo** so với bitrate video gốc; không hứa con số trước khi đo | Đếm byte đã gửi | CP1 |
| NFR-PRIV-2 | Không nhận diện khuôn mặt; OCR chỉ cho xe vi phạm; dữ liệu bị xóa khi hết thời hạn lưu giữ | Review code; job xóa có test | CP2 |
| NFR-SEC-1 | Xem danh sách bên dưới | Checklist; `pip-audit`, `npm audit` | CP2 |
| NFR-REL-1 | Mọi dịch vụ tự khởi động lại và có healthcheck. Tắt lần lượt edge, backend, DB thì hệ thống tự phục hồi, không mất dữ liệu. Chạy liền 24 giờ: RAM không tăng quá 10%, FPS ổn định | Thử phục hồi; soak test | CP2 |
| NFR-OBS-1 | Log có cấu trúc; có metric Prometheus; cảnh báo camera mất kết nối trong ≤ 60 giây | Kiểm tra trực tiếp | CP2 |
| NFR-DEP-1 | Một lệnh triển khai cho từng vai (trung tâm, edge); phiên bản thư viện cố định; image gắn tag theo commit; có runbook; đã thử sao lưu và khôi phục DB một lần | Runbook và biên bản thử | CP2 |
| NFR-DEP-2 | **Live URL** (deliverable số 5 của AI20K; đã chốt Q3): phần trung tâm (API + DB + dashboard) chạy trên cloud, có TLS, chỉ dùng dữ liệu demo của dự án; edge chạy local và gửi dữ liệu lên qua HTTPS | Mở URL từ mạng ngoài; edge local gửi được sự kiện | CP2 |
| NFR-QA-1 | CI chạy ruff, pytest, lint và build dashboard, build Docker; độ phủ test của `src/edge` ≥ 80% | CI | CP1 |
| NFR-LEGAL-1 | Hệ thống chỉ tạo ứng viên; ghi nhận chính thức cần người duyệt; mỗi loại vi phạm có căn cứ pháp lý ghi trong `false-positives.md` | Review | CP1 |
| NFR-UX-1 | Tiếng Việt; responsive ≥ 360 px; dark mode; trạng thái lỗi rõ ràng | Checklist UX | CP2 |

**Chi tiết NFR-SEC-1:**
- TLS cho mọi kết nối ra ngoài máy;
- mật khẩu được băm; dùng JWT; kiểm quyền (RBAC) ở backend;
- bí mật chỉ nằm trong biến môi trường;
- giới hạn tần suất đăng nhập;
- cấu hình production không còn tài khoản mặc định;
- quét lỗ hổng thư viện: không còn lỗ hổng mức High hoặc Critical chưa xử lý.

---

## 6. Hợp đồng dữ liệu và giao tiếp (chốt từ M0)

### 6.1 Cấu hình cảnh v2 — `configs/scenes/<camera_id>.yaml`

Tương thích ngược với M1: bộ đọc M1 chỉ dùng `camera_id`, `count_line`, `classes` và bỏ qua các khóa khác. Tọa độ tính bằng pixel trên khung đã chuẩn hóa (H-02).

```yaml
camera_id: cam-01
intersection_id: int-A              # nút giao mà camera này nhìn; dùng cho FR-DEN-4 và cấu hình tuyến (mục 6.8)
frame_size: [1920, 1080]
location: {lat: 21.0285, lon: 105.8542, name: "Nút giao X — hướng Bắc"}  # cho bản đồ (FR-UI-3)
homography:                     # tùy chọn; ≥ 4 cặp điểm ảnh ↔ mặt đường (mét); cần cho tốc độ và điểm đầu xe (H-05)
  image: [[812, 1010], [1455, 1004], [1260, 640], [930, 642]]
  ground: [[0, 0], [7, 0], [7, 30], [0, 30]]
count_line: {id: line-1, a: [0, 900], b: [1920, 900]}     # như M1
classes: {2: car, 3: motorcycle, 5: bus, 7: truck}         # lớp được đếm (như M1)
extra_detect_classes: {0: person}                          # chỉ để che mặt và loại trừ B4, không đếm
lights:
  - id: head-N
    roi: [1500, 80, 1560, 240]
    bulbs: {red: [1500, 80, 1560, 130], yellow: [1500, 135, 1560, 185], green: [1500, 190, 1560, 240]}
lanes:
  - id: L1
    polygon: [[300, 1080], [760, 1080], [900, 600], [760, 600]]
    direction: [0, -1]              # hướng được phép đi, trên ảnh (lên trên = đi xa camera); dùng cho WW
    allowed_classes: [motorcycle]   # LN-a; bỏ trống = mọi lớp
    allowed_exits: [right]          # LN-c; left | straight | right | u_turn
    light: head-N
    right_turn_on_red: false        # C3
  - id: L2
    polygon: [[760, 1080], [1500, 1080], [1260, 600], [900, 600]]
    direction: [0, -1]
    allowed_classes: []
    allowed_exits: [straight, left]
    light: head-N
    right_turn_on_red: false
stop_lines:
  - {lanes: [L1, L2], a: [300, 700], b: [1500, 700]}
dividers:                           # vạch giữa các làn
  - {between: [L1, L2], polyline: [[760, 1080], [830, 700]], type: solid}    # solid: cấm chuyển làn (LN-b)
  - {between: [L1, L2], polyline: [[830, 700], [900, 600]], type: dashed}
intersection_zone: [[200, 600], [1700, 600], [1700, 150], [200, 150]]       # M-03
exits:                              # cạnh ra khỏi vùng giao lộ → hướng đi (LN-c, RL)
  - {direction: left, segment: [[200, 600], [200, 150]]}
  - {direction: straight, segment: [[200, 150], [1700, 150]]}
  - {direction: right, segment: [[1700, 150], [1700, 600]]}
wrong_way_zones:                    # phần đường một chiều không mô hình hóa thành làn (WW)
  - {id: shoulder-N, polygon: [[1500, 1080], [1700, 1080], [1600, 700], [1400, 700]], direction: [0, -1]}
no_stop_zones:                      # FR-VIO-ST
  - {id: box, polygon: [[200, 600], [1700, 600], [1700, 150], [200, 150]]}
rules:                              # bật hoặc tắt từng luật tại nút này; ngưỡng nằm trong configs/frozen/*.yaml
  red_light: true
  wrong_way: true
  lane_class: false                 # nút này không có làn riêng; LN-a bật ở nút nào trên tuyến có làn riêng theo loại xe
  lane_solid_line: true
  lane_exit: true
  illegal_stop: false
```

Quan hệ trước/sau giữa các nút không khai báo ở đây; nó nằm trong cấu hình tuyến (mục 6.8).

### 6.2 Ngưỡng đóng băng — `configs/frozen/rl-v1.yaml`

Giá trị dưới đây là **điểm khởi đầu**. Ngưỡng được chỉnh bằng leave-one-video-out trên dev, rồi đóng băng ngày 11/10. SHA-256 của file được ghi trong báo cáo đánh giá.

```yaml
model: {weights: yolo26n.pt, imgsz: 640, format: tensorrt-fp16}
processing_fps: 15
light: {min_stable_frames: 3, vote_window: 5}
quality: {min_track_frames: 10, max_interpolated_ratio: 0.2}
red_light: {grace_s: 0.8, confirm_zone_s: 2.0, front_margin_m: 0.5}
wrong_way: {window_s: 1.5, min_angle_deg: 135, min_distance_m: 5.0, min_speed_kmh: 8, min_windows: 2}
lane_class: {min_dwell_s: 2.0, min_distance_m: 10.0, min_class_vote: 0.8}
lane_solid_line: {min_dwell_after_s: 1.0}
lane_exit: {min_entry_frames: 5}
congestion: {speed_ratio: [0.7, 0.4, 0.2], occupancy: [0.3, 0.6, 0.8], sustain_min: 3, cycle_failure_k: 2}
```

Ngưỡng của phân tích tuyến (FR-COR-1, FR-COR-2) nằm ở file riêng, đóng băng cùng ngày và cùng tag:

```yaml
# configs/frozen/corridor-v1.yaml
period_min: 15
min_valid_cycles: 5
blocked_discharge_ratio: 0.3        # có hàng chờ mà xe thoát < 30% tốc độ bão hòa
spillback_consecutive_cycles: 2
spillback_match_cycles: 1           # B phải tắc trong khoảng ± 1 chu kỳ
bottleneck: {x_min: 0.9, failure_rate_min: 0.5}
```

### 6.3 Sự kiện edge → trung tâm

**Vỏ chung** — giữ nguyên từ contract v1 (plan M1, TASK-001):

```text
schema_version, event_id (UUIDv7), seq, device_id, camera_id, type,
captured_at, processed_at, source (live | replay), payload
```

Trong v1, `type` chỉ có `count`. Spec v1.0 thêm các loại dưới đây; thêm loại mới là thay đổi không phá vỡ.

| `type` | Tần suất | Payload | Từ |
|---|---|---|---|
| `count` v1.1 | Mỗi phút | Như v1; mỗi dòng trong `rows` thêm `lane_id` (tùy chọn, mặc định `null`) | CP1 |
| `density` v1 | Mỗi phút | `{"bucket_seconds": 60, "lanes": [{"lane_id": "L1", "flow": 14, "occupancy_avg": 3.2, "speed_kmh_avg": 18.5, "queue_len_max": 7, "congestion_level": 1}]}` | CP1 |
| `congestion` v1 | Khi xảy ra | `{"lane_id": "L1", "level": 3, "cause": "cycle_failure", "started_at": "...", "residual_queue_cycles": 3}` | CP1 |
| `signal_cycle` v1 | Mỗi chu kỳ đèn (khoảng 1–2 phút) | Xem ví dụ dưới bảng | CP1 |
| `violation_candidate` v1 | Khi xảy ra | Xem ví dụ dưới bảng | CP1 |
| `rejection_summary` v1 | Mỗi phút | `{"bucket_seconds": 60, "counts": [{"rule": "red_light", "reason": "A1", "n": 3}]}` | CP1 |
| `health` v1 | Mỗi 10 giây | `{"fps": 15.2, "dropped_frames": 0, "lag_s": 0.3, "outbox_depth": 0, "cpu_pct": 41, "gpu_pct": 55, "ram_mb": 2100, "temp_c": 62, "model_version": "yolo26n-8.4.157-trt-fp16", "config_sha256": "...", "uptime_s": 3600, "manual_mode": false, "desired_revision": 42}`. Hai trường cuối là trạng thái edge **đang áp dụng** (mục 6.7) | CP1 |
| `ota_status` v1 | Khi xảy ra | `{"release_id": "...", "state": "applied", "reason": null}`; `state` ∈ `downloaded`, `applied`, `committed`, `rolled_back`, `rejected` | CP2 |

Ví dụ payload của `violation_candidate` v1:

```json
{
  "violation": "red_light",
  "track_id": 1834,
  "vehicle_class": "motorcycle",
  "lane_id": "L2",
  "t_event": "2026-10-05T08:15:03.400+00:00",
  "frame_index": 12345,
  "bbox": [820, 610, 900, 720],
  "conditions": {"light_state": "RED", "red_elapsed_s": 2.4, "entered_zone_after_s": 1.1},
  "context": {"density_level": 1, "manual_mode": false, "priority_window": false},
  "config_sha256": "…",
  "model_version": "yolo26n-8.4.157-trt-fp16",
  "evidence": {"package_id": "…", "variants": ["operator", "csgt"]},
  "ocr": {"text": "29B1-123.45", "confidence": 0.93}
}
```

Quy định cho payload trên:
- `violation` ∈ `red_light`, `wrong_way`, `lane_class`, `lane_solid_line`, `lane_exit`, `illegal_stop`.
- `frame_index` chỉ có khi nguồn là file (để khớp với nhãn khi đánh giá).
- `ocr` có thể là `null`. Trung tâm lưu `ocr` vào cột chỉ CSGT đọc được; API lọc trường này theo vai trò.

Ví dụ payload của `signal_cycle` v1 (FR-DEN-4):

```json
{
  "intersection_id": "int-A",
  "head_id": "head-N",
  "lane_ids": ["L1", "L2"],
  "cycle_start": "2026-10-05T17:15:03.400+00:00",
  "valid": true,
  "green_s": 32.0, "amber_s": 3.0, "red_s": 45.1,
  "arrivals":   {"motorcycle": 41, "car": 6, "bus": 0, "truck": 1},
  "departures": {"motorcycle": 37, "car": 5, "bus": 0, "truck": 1},
  "max_queue_veh": 23,
  "residual_queue_veh": 4,
  "discharge": {"counts": {"motorcycle": 30, "car": 4, "bus": 0, "truck": 1}, "duration_s": 17.5},
  "box_blocked_s": 0.0,
  "queue_overflow_s": 6.5
}
```

Quy định cho payload trên:
- `valid = false` khi trong chu kỳ có lúc đèn ở trạng thái `UNKNOWN`.
- Số xe gửi theo loại xe. Trung tâm tự đổi ra PCU (FR-COR-1), nên đổi hệ số PCU không cần cập nhật edge.
- Sự kiện tuyến (`spillback`, `bottleneck`) do **trung tâm** sinh, vì cần dữ liệu nhiều nút. Chúng không đi qua outbox; được lưu ở bảng riêng và phát qua SSE với loại `corridor_event`.

**Quy tắc phiên bản:**
- Thêm trường tùy chọn hoặc thêm `type` mới: giữ nguyên `schema_version`.
- Đổi nghĩa, đổi kiểu hoặc xóa trường: tăng `schema_version`. Trung tâm phải nhận được cả hai phiên bản cho tới khi mọi edge đã cập nhật.

### 6.4 Manifest của gói bằng chứng

```json
{
  "manifest_version": 1,
  "package_id": "0199b3c4-…",
  "event_id": "0199b3c4-…",
  "variant": "operator",
  "device_id": "edge-01",
  "camera_id": "cam-01",
  "violation": "red_light",
  "captured_at": "2026-10-05T08:15:03.400+00:00",
  "processed_at": "2026-10-05T08:15:05.100+00:00",
  "source": "replay",
  "files": [
    {"name": "key_1.jpg", "role": "light_red_vehicle_before_line", "t": "…", "sha256": "…"},
    {"name": "key_2.jpg", "role": "vehicle_after_line", "t": "…", "sha256": "…"},
    {"name": "key_3.jpg", "role": "plate_crop", "t": "…", "sha256": "…"},
    {"name": "clip/000.jpg", "role": "clip", "t": "…", "sha256": "…"}
  ],
  "parent_hash": "SHA-256 của bản đầy đủ đã niêm phong trên thiết bị",
  "config_sha256": "…",
  "model_version": "yolo26n-8.4.157-trt-fp16",
  "signing_key_id": "edge-01-2026-09",
  "signature": "base64 chữ ký Ed25519 trên JSON chuẩn hóa của manifest, không gồm trường signature"
}
```

- `variant` ∈ `operator`, `csgt`.
- Bản `operator` không có ảnh biển số rõ: `key_3.jpg` là ảnh đã che.

### 6.5 API trung tâm

| Phương thức, đường dẫn | Ai gọi | Mô tả | Từ |
|---|---|---|---|
| `POST /api/v1/events` | Thiết bị (token) | Nhận lô sự kiện mọi loại; chống trùng theo `event_id` | M1 → CP1 |
| `PUT /api/v1/evidence/{package_id}/{variant}` | Thiết bị | Tải gói bằng chứng (zip); kiểm SHA-256 với manifest | CP1 |
| `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh` | Người dùng | Trả JWT | CP1 |
| `GET /api/v1/cameras` | Mọi vai trò | Camera, vị trí, trạng thái | M1 → CP1 |
| `GET /api/v1/cameras/{id}/health` | Mọi vai trò | Heartbeat gần nhất | CP1 |
| `GET /api/v1/counts` | Mọi vai trò | Số đếm theo camera, làn, khoảng thời gian | M1 → CP1 |
| `GET /api/v1/density` | Mọi vai trò | Mật độ, hàng chờ, mức ùn tắc | CP1 |
| `GET /api/v1/intersections/{id}/performance` | Mọi vai trò | Theo khung 15 phút: q, s, g/C, X (kèm cờ `lower_bound`), độ trễ, LOS, % chu kỳ thất bại | CP1 |
| `GET /api/v1/corridors`, `GET /api/v1/corridors/{id}/status` | Mọi vai trò | Danh sách tuyến; ma trận nút × thời gian (mức ùn tắc, LOS) và các sự kiện tuyến | CP1 |
| `GET /api/v1/candidates`, `GET /api/v1/candidates/{id}` | operator, csgt | Hàng đợi, chi tiết; trường dữ liệu lọc theo vai trò | CP1 |
| `POST /api/v1/candidates/{id}/review` | operator (bước 1), csgt (bước 2) | Quyết định kèm mã lý do | CP1 |
| `GET /api/v1/evidence/{package_id}?variant=` | operator (bản che), csgt (bản CSGT, có ghi nhật ký) | Ảnh và clip | CP1 |
| `GET /api/v1/verify/{package_id}` | Công khai | Kết quả kiểm chữ ký và mã băm (không có ảnh) | CP1 |
| `GET /api/v1/audit` | admin, auditor | Nhật ký, kết quả kiểm chuỗi | CP1 |
| `GET /api/v1/stream` | operator, csgt | SSE: ứng viên mới, ùn tắc, sự kiện tuyến, camera mất kết nối | CP1 |
| `POST /api/v1/reports`, `POST /api/v1/reports/{id}/approve` | operator, csgt | Agent soạn bản nháp; người duyệt để phát hành | CP1 |
| `GET /api/v1/cases/{id}/export` | csgt | Hồ sơ vi phạm (PDF + JSON) | CP1 |
| `POST /api/v1/candidates/{id}/explain`, `POST /api/v1/ask` | operator, csgt | Trợ lý giải thích; hỏi đáp số liệu | CP2 |
| `GET /api/v1/suggestions`, `POST /api/v1/suggestions/{id}/decision` | operator | Gợi ý điều phối | CP2 |
| `GET /api/v1/devices/{id}/desired` | Thiết bị | Trạng thái mong muốn (mục 6.7); edge hỏi mỗi 10 giây | CP1 |
| `PUT /api/v1/cameras/{id}/manual-mode` | operator | Bật hoặc tắt chế độ điều khiển tay; tăng `revision`; ghi nhật ký | CP1 |
| `POST /api/v1/releases`, `POST /api/v1/devices/{id}/rollout` | admin | Tải bản phát hành có ký; triển khai canary | CP2 |
| `GET /api/v1/public/counts` | Khóa API | Dữ liệu mở (FR-INT-3) | COULD |

### 6.6 Giao diện luật trên edge

```python
@dataclass(frozen=True)
class FrameContext:
    frame_index: int
    t: datetime                        # source time: file = frame_index / fps; live = wall clock
    tracks: list[Track]                # bottom centre, estimated front point (H-05), class votes
    lights: dict[str, str]             # head id -> RED | YELLOW | GREEN | FLASHING | OFF | UNKNOWN
    density_level: dict[str, int]      # lane id -> 0..3
    manual_mode: bool                  # operator switched the intersection to manual control
    priority_window: bool              # a priority vehicle was seen within +-T seconds


@dataclass(frozen=True)
class Candidate:
    violation: str                     # red_light | wrong_way | lane_class | lane_solid_line | lane_exit | illegal_stop
    track_id: int
    lane_id: str | None
    t_event: datetime
    frame_index: int
    bbox: tuple[float, float, float, float]
    conditions: dict[str, float | str] # measured values that satisfied the rule


@dataclass(frozen=True)
class Rejection:
    violation: str
    track_id: int
    reason_code: str                   # A1..E5, W1..W8, L1..L8, S1..S6


class Rule(Protocol):
    name: str

    def update(self, ctx: FrameContext) -> list[Candidate | Rejection]: ...
```

### 6.7 Kênh điều khiển: trạng thái mong muốn và MQTT

**Trạng thái mong muốn.** Endpoint: `GET /api/v1/devices/{device_id}/desired`. Có từ CP1; thiết bị gọi bằng token riêng.

```json
{
  "schema_version": 1,
  "revision": 42,
  "cameras": {"cam-01": {"manual_mode": false}},
  "config": null,
  "release": null
}
```

- Mỗi thay đổi (bật/tắt chế độ tay, triển khai cấu hình, triển khai bản phát hành) làm `revision` của thiết bị tăng 1. Edge chỉ áp dụng khi `revision` lớn hơn bản đang giữ, nên nhận trùng hay nhận lại đều không gây hại.
- `config` và `release`:
  - ở CP1 là `null`;
  - từ CP2 có dạng `{"id": "...", "sha256": "...", "url": "..."}`. Edge tải qua HTTPS, kiểm SHA-256 và chữ ký theo FR-OTA-1 rồi mới áp dụng.
- Edge báo lại trạng thái đang áp dụng qua sự kiện `health` (các trường `manual_mode`, `desired_revision`). Dashboard so với `revision` ở trung tâm để biết thay đổi đã tới thiết bị chưa.

**MQTT** — từ CP2 (FR-DEV-2):

| Topic | Chiều | Retained | QoS | Payload |
|---|---|---|---|---|
| `trafficeye/<device_id>/status` | edge → trung tâm | có | 1 | Khi kết nối: `{"state": "online", "ts": "..."}`. Last Will, cũng retained: `{"state": "offline"}`. Khi tắt có chủ đích, edge tự publish `offline` trước khi ngắt |
| `trafficeye/<device_id>/desired` | trung tâm → edge | có | 1 | `{"revision": 42}`, chỉ để báo có bản mới. **Không bao giờ** chứa cấu hình, model hay lệnh |

- **Broker:** Eclipse Mosquitto 2.x, thêm một container vào stack trung tâm.
  - Lý do chọn: nhẹ; có sẵn Last Will, retained message và ACL theo tên đăng nhập.
  - EMQX hay HiveMQ hợp với cụm broker lớn, thừa khi chỉ có ≤ 10 thiết bị.
- **Client:** paho-mqtt trên cả edge và backend; MQTT 5.
  - Keepalive 5 giây. Khi mất kết nối, broker phát Last Will chậm nhất khoảng 1,5 × 5 = 7,5 giây sau đó, đủ cho FR-DEV-2 AC1.
  - Mỗi lần kết nối bắt đầu phiên sạch (clean start). Không cần giữ phiên, vì `desired` là retained nên kết nối lại là nhận ngay bản mới nhất.
- **Bảo mật:**
  - TLS; tắt truy cập ẩn danh; mỗi thiết bị một tài khoản, tên đăng nhập là `device_id`.
  - ACL: thiết bị chỉ được ghi vào topic `status` và đọc topic `desired` của chính nó; tài khoản backend đọc mọi `status`, ghi mọi `desired`:

    ```text
    user backend
    topic read trafficeye/+/status
    topic write trafficeye/+/desired

    # %u = tên đăng nhập = device_id
    pattern write trafficeye/%u/status
    pattern read trafficeye/%u/desired
    ```

  - Kẻ chiếm được broker vẫn không đẩy được cấu hình giả: payload chỉ là số `revision`, còn nội dung lấy qua HTTPS và có chữ ký. Tệ nhất là thiết bị hỏi `desired` thừa vài lần, hoặc trạng thái online/offline sai tạm thời; heartbeat HTTPS vẫn là nguồn đối chiếu.
- **Mạng khi deploy lên cloud (WP-52):** edge luôn chủ động kết nối ra ngoài. Broker phải nhận được kết nối từ Internet, bằng một trong hai cách:
  - cổng 8883 (MQTT qua TLS);
  - MQTT qua WebSocket TLS ở cổng 443, nếu nền tảng cloud chỉ mở HTTP(S).

  Phải kiểm tra điểm này khi chọn nền tảng.

**Trạng thái thiết bị trên dashboard.** Một quy tắc dùng chung cho bản đồ (FR-UI-3), trang sức khỏe (FR-UI-5) và cảnh báo (NFR-OBS-1).

Khi backend đang kết nối được với broker:

| Điều kiện | Hiển thị |
|---|---|
| Quá 30 giây không nhận được `health` | Mất kết nối |
| Đã nhận Last Will `offline`, sau đó chưa có `health` mới | Mất kết nối |
| Đã nhận Last Will `offline`, nhưng sau đó vẫn có `health` mới | Hoạt động, mất kênh điều khiển |
| Còn lại | Hoạt động |

- Nhận lại `online` thì bỏ trạng thái Last Will.
- Mốc so sánh là thời điểm **trung tâm nhận** sự kiện, không phải `captured_at`, vì outbox có thể gửi bù sự kiện cũ.
- Khi backend mất kết nối tới broker, và trong toàn bộ CP1 (chưa có MQTT), chỉ dùng dòng đầu tiên. Nếu là do backend mất broker, dashboard hiện thêm băng "kênh điều khiển gián đoạn".

### 6.8 Cấu hình tuyến — `configs/corridors/<corridor_id>.yaml`

```yaml
corridor_id: cor-01
name: "Tuyến X, chiều Đông → Tây"
nodes:                      # xếp đúng theo chiều xe chạy mà camera nhìn
  - {intersection_id: int-A, camera_id: cam-01, link_to_next_m: 450}
  - {intersection_id: int-B, camera_id: cam-02, link_to_next_m: 380}
  - {intersection_id: int-C, camera_id: cam-03, link_to_next_m: null}
pcu: {motorcycle: 0.3, car: 1.0, truck: 2.5, bus: 3.0}   # TCVN 13592:2022 Bảng 3, cột 30–50 km/h
```

- Thứ tự trong `nodes` quyết định nút nào là "nút phía trước" trong quy tắc tràn hàng chờ (FR-COR-2).
- `link_to_next_m` đo trên bản đồ. Giá trị này dùng để hiển thị và giải thích (ví dụ "đoạn 450 m giữa A và B đã kín"), không dùng trong quy tắc.
- Bảng PCU có thể chỉnh; ghi rõ nguồn khi đổi.

---

## 7. Luật phát hiện theo loại vi phạm (tóm tắt)

Chi tiết điều kiện, dấu hiệu phân biệt và cách loại trừ ở `docs/survey/false-positives.md`. Mức phạt lấy theo các nguồn tổng hợp Nghị định 168/2024/NĐ-CP; phải đối chiếu nguyên văn trước khi đưa lên slide.

### 7.1 Vượt đèn đỏ (RL) — MUST

6 điều kiện ở `false-positives.md` mục 1; mã loại trừ A1–E5. Đây là loại vi phạm chính, có giao thức đánh giá đầy đủ.

### 7.2 Đi ngược chiều (WW) — MUST

**Chỉ áp dụng ở phần đường có một hướng đi rõ ràng:** làn có `direction`, hoặc vùng trong `wrong_way_zones` (đường một chiều, phần đường có dải phân cách hay vạch liền).

**Điều kiện (phải thỏa đồng thời):**
1. Xe nằm trong phần đường nói trên.
2. Hướng chuyển động lệch > `min_angle_deg` so với hướng được phép, trong ≥ `min_windows` cửa sổ `window_s` liên tiếp.
3. Quãng đường đi ngược ≥ `min_distance_m`.
4. Tốc độ ≥ `min_speed_kmh`, để loại người dắt xe và xe lùi ngắn.
5. Track liền mạch, có detection thật ở đầu và cuối đoạn.
6. Không có ngữ cảnh miễn trừ.

**Mã loại trừ:** W1–W8.

**Căn cứ:**
- Luật TTATGTĐB 2024 quy định người lái phải đi đúng làn, đúng phần đường.
- Nghị định 168/2024: đi ngược chiều đường một chiều, hoặc đi ngược chiều trên đường có biển "Cấm đi ngược chiều": ô tô bị phạt 18–20 triệu đồng, xe máy 4–6 triệu đồng.

### 7.3 Vi phạm làn đường (LN) — MUST, đủ cả 3 kiểu (Q8)

**LN-a — sai làn theo loại xe.** Loại xe không nằm trong `allowed_classes` của làn, và:
- xe ở trong làn ≥ `min_dwell_s` và đi được ≥ `min_distance_m`;
- phiếu bầu lớp của track ≥ `min_class_vote`.

**LN-b — chuyển làn qua vạch liền.** Điểm tiếp đất của xe đi hết qua một đoạn vạch `solid` sang làn bên cạnh, rồi ở lại làn mới ≥ `min_dwell_after_s`. Bánh xe chỉ chạm vạch thì không tính trong MVP, để giữ precision.

**LN-c — đi sai hướng theo mũi tên của làn.** Xe vào vạch dừng ở làn A (ổn định ≥ `min_entry_frames` khung), nhưng rời vùng giao lộ qua một cạnh `exits` có hướng không nằm trong `allowed_exits` của làn A.

**Mã loại trừ:** L1–L8.

**Căn cứ:**
- Luật TTATGTĐB 2024, Điều 13:
  - phải đi trong một làn, chỉ chuyển làn ở nơi cho phép, mỗi lần chỉ sang làn liền kề;
  - xe không được đi vào làn dành riêng cho loại xe khác.
- Nghị định 168/2024: đi không đúng phần đường hoặc làn đường quy định: ô tô bị phạt 4–6 triệu đồng và trừ 2 điểm; xe máy 600–800 nghìn đồng.
- Chuyển làn không đúng nơi cho phép cũng bị phạt theo Nghị định 168/2024.

### 7.4 Dừng, đỗ sai (ST) — COULD

**Điều kiện:**
- xe đứng yên trong `no_stop_zones` ≥ T giây;
- đèn của hướng đi đó đang XANH;
- phía trước xe không có hàng chờ.

Hai điều kiện sau dùng để loại xe dừng do đèn đỏ hoặc do ùn tắc.

**Mã loại trừ:** S1–S6.

**Căn cứ:** Nghị định 168/2024 cấm dừng, đỗ tại nơi đường bộ giao nhau hoặc trong phạm vi 5 m tính từ mép đường giao nhau; ô tô bị phạt 800 nghìn – 1 triệu đồng. Phần đường dành cho người đi bộ qua đường cũng cấm dừng, đỗ.

---

## 8. Checkpoint

### 8.1 CP1 — Thứ Tư 14/10/2026: "80% — luồng chính và phô diễn kỹ thuật"

CP1 đặt sau ngày đóng băng (11/10), vì mọi luật được đánh giá đều phải xong trước khi đóng băng. Hai ngày 12–13/10 dành cho các hạng mục không ảnh hưởng tới ngưỡng: Agent, OCR, benchmark, trang Tuyến.

**Phạm vi:** mọi hạng mục có cột Checkpoint là CP1 trong bảng mục 2, tổng cỡ 53/65.

**Kịch bản demo (khoảng 10 phút):**

| Thời lượng | Nội dung |
|---|---|
| 1' | Bối cảnh; kiến trúc; bảng đối chiếu đề bài (mục 1) |
| 2' | **Luồng chính vượt đèn đỏ:** camera RTSP mô phỏng → cảnh báo → duyệt bước 1 (bản che) → bước 2 (bản CSGT, có nhật ký) → ghi nhận chính thức → trang xác minh |
| 1' | Một ca đi ngược chiều và 3 kiểu sai làn (mỗi kiểu một ca), đi đầu–cuối |
| 1' | **Tuyến 3 nút:** bản đồ nhiệt nút × thời gian; một lần tràn hàng chờ B → A kèm số liệu; nút cổ chai; mức phục vụ từng nút; đếm theo làn; trang sức khỏe |
| 1' | **"Hệ thống từ chối gì và vì sao":** phát lại các ca khó kèm mã lý do; bật chế độ điều khiển tay → ứng viên mới bị chặn với mã C4; kết quả ablation |
| 1' | Ngắt mạng 2 phút rồi đồng bộ bù; sửa 1 byte bằng chứng → trang xác minh báo sai |
| 1' | Bảng hiệu năng PyTorch / ONNX / TensorRT FP16 (FPS, độ trễ p95, kích thước model); mAP trên tập khung dev |
| 1' | Agent báo cáo ca trực (có bước người duyệt, có chế độ không LLM); OCR biển số |
| 1' | Số dev theo từng loại vi phạm (leave-one-video-out, Wilson 95%), **nói rõ chưa phải số test**; kế hoạch tới CP2 |

**Nghiệm thu CP1:**
- Mọi hạng mục CP1 đạt AC. Bằng chứng (link PR, ảnh, log) nằm trong issue tương ứng.
- Tổng điểm hoàn thành ≥ 80% theo mục 8.3. Nếu thấp hơn: ghi rõ hạng mục thiếu, người làm, hạn mới; hoặc cắt theo mục 11.
- Kịch bản demo chạy trọn 2 lần liên tiếp trên máy demo, không can thiệp tay.
- Phản hồi của stakeholder được ghi vào `docs/plan/cp1-feedback.md`. Phản hồi nào làm đổi spec thì đi qua thủ tục mục 12.

### 8.2 CP2 — Thứ Sáu 23/10/2026: "100% — sẵn sàng production"

**"Sẵn sàng production" trong dự án này nghĩa là:** hệ thống triển khai và vận hành được theo chuẩn production trên hạ tầng mô phỏng, cộng ít nhất một nguồn RTSP trực tiếp. **Không** có nghĩa là đã lắp đặt cho một thành phố.

**Phạm vi:**
- CP1;
- các mục nâng cao: OTA, kênh điều khiển MQTT, gợi ý điều phối, trợ lý giải thích, INT8, mô phỏng Jetson;
- Live URL: trung tâm chạy trên cloud (NFR-DEP-2);
- xuất hồ sơ vi phạm (FR-EXP-1, chuyển từ CP1);
- kết quả chạy tập test một lần (19/10);
- toàn bộ checklist production dưới đây.

**Checklist production** — mỗi mục là "có hoặc không", kèm bằng chứng:

| Nhóm | Mục kiểm tra |
|---|---|
| Bảo mật | TLS; mật khẩu băm; JWT có hạn và refresh; RBAC có test; giới hạn tần suất đăng nhập; bí mật chỉ qua biến môi trường; không còn tài khoản mặc định; `pip-audit` và `npm audit` không còn lỗ hổng High/Critical |
| Tin cậy | Tự khởi động lại và healthcheck; thử phục hồi khi tắt edge, backend, DB, mạng; soak test 24 giờ đạt; outbox không mất, không trùng; job xóa theo thời hạn lưu giữ đang chạy |
| Quan sát | Trang sức khỏe; cảnh báo camera mất kết nối; log có cấu trúc; Prometheus (Grafana nếu kịp) |
| Triển khai | Một lệnh cho mỗi vai; image gắn tag theo commit; runbook (khởi động, dừng, cập nhật OTA, quay lại bản cũ, sao lưu và khôi phục); đã thử khôi phục DB; **Live URL chạy được** từ mạng ngoài (NFR-DEP-2) |
| Dữ liệu | Thời hạn lưu giữ được thực thi; chuỗi nhật ký kiểm được; đã đo tỉ lệ che lọt |
| Chất lượng | CI xanh; độ phủ test `src/edge` ≥ 80%; test đầu–cuối tự động (`scripts/e2e_smoke.sh`) |
| Tài liệu | README, spec, báo cáo kỹ thuật, báo cáo đánh giá, tài liệu API (OpenAPI), mục hạn chế |
| Thực địa | Chạy ≥ 30 phút với một nguồn RTSP trực tiếp: camera IP, hoặc ứng dụng biến điện thoại thành camera |

**Kịch bản demo (khoảng 12 phút):**
1. Luồng chính CP1, rút gọn.
2. Nhiều camera trên bản đồ; ùn tắc → gợi ý điều phối → người duyệt.
3. Trợ lý giải thích một ứng viên.
4. OTA: cập nhật trực tiếp (thông báo đi qua MQTT), rồi thử bản hỏng để thấy hệ thống tự quay lại bản cũ.
5. Tắt edge → bản đồ báo "mất kết nối" trong ≤ 10 giây nhờ Last Will. Tắt DB → hệ thống tự phục hồi. Trình log soak test 24 giờ. Toàn bộ chạy trên Live URL.
6. Kết quả tập test: precision từng loại vi phạm (sai làn báo riêng 3 kiểu), mAP, độ chính xác đếm, độ chính xác đo chu kỳ đèn và sự kiện tuyến, tỉ lệ che lọt, OCR, hiệu năng FP16/INT8.

**Nghiệm thu CP2:**
- Checklist production xanh toàn bộ.
- Đã có báo cáo đánh giá tập test, log ghi `status: fresh`.
- Demo chạy trọn 2 lần, trên cả máy chính và máy dự phòng.
- PO ký nghiệm thu.
- Các lỗi còn tồn đọng được ghi vào mục hạn chế.

### 8.3 Cách tính % hoàn thành

- Mỗi hạng mục ở mục 2 có cỡ 1–3.
- Một hạng mục chỉ được tính "xong" khi đạt DoD (mục 9.2) và đã merge vào `main`.
- % hoàn thành = tổng cỡ các hạng mục đã xong / 65.
- Theo dõi trên GitHub Project, với các trường `Spec ID`, `Size`, `Checkpoint`, `Status`.
- Báo % hằng tuần trong buổi demo nội bộ tối Chủ nhật.

---

## 9. Definition of Ready và Definition of Done

### 9.1 Definition of Ready — việc chỉ được bắt đầu khi

- có ID trong spec, và AC đo được;
- phụ thuộc đã merge, hoặc đã có dữ liệu mẫu theo hợp đồng mục 6;
- có dữ liệu thử (clip, nhãn) nếu việc cần;
- đã có người làm và người review;
- đủ nhỏ: ≤ 2 ngày công. Lớn hơn thì tách.

### 9.2 Definition of Done chung — áp dụng cho mọi việc

1. Đạt mọi AC của các ID liên quan; bằng chứng (lệnh và output, ảnh, log) dán vào PR.
2. Merge vào `main` qua PR có ít nhất 1 người review; CI xanh.
3. Logic mới có unit test; sửa lỗi thì có test tái hiện lỗi; test không phụ thuộc mạng.
4. Đúng hợp đồng mục 6. Nếu đổi hợp đồng thì đã qua thủ tục mục 12.
5. Chạy được trong môi trường tích hợp (Docker Compose hoặc máy demo), không chỉ trên máy người làm.
6. Không commit bí mật, video thô, dữ liệu cá nhân.
7. Tài liệu liên quan đã cập nhật: README, runbook; spec nếu hành vi thay đổi.
8. Việc ở edge: FPS đầu–cuối trên máy demo vẫn ≥ 15 sau thay đổi.
9. Issue được đóng kèm link PR; WORKLOG được cập nhật.

### 9.3 DoD bổ sung theo loại việc

| Loại việc | Điều kiện thêm |
|---|---|
| Luật vi phạm | Có test cho từng điều kiện và từng mã loại trừ; `evaluate.py --split dev` chạy không lỗi; người làm không đọc thư mục test |
| API | Có test phân quyền (401/403); OpenAPI hiển thị đúng; nếu nhận sự kiện thì có test chống trùng |
| Giao diện | Có trạng thái tải/lỗi/rỗng; responsive 360 px; dark mode; ảnh chụp màn hình trong PR |
| Đánh giá | Tuân thủ protocol: config đã đóng băng, log có `status`, có mã băm; kết quả điền vào mẫu báo cáo |
| Hạ tầng, production | Có trong runbook; đã thử trên máy sạch; có cách quay lại bản cũ |
| Agent | Công cụ chỉ đọc; số liệu trong câu trả lời khớp công cụ (có test); có chế độ chạy không LLM |

### 9.4 Ai nghiệm thu

| Người | Kiểm tra gì |
|---|---|
| Reviewer của PR | DoD kỹ thuật |
| PO (TV1) | AC, tại buổi demo nội bộ tối Chủ nhật |
| TV4 (custodian) | Các hạng mục đánh giá |

---

## 10. Đổi mới và tích hợp

| # | Hạng mục | Vì sao khác biệt | Cách chứng minh | ID |
|---|---|---|---|---|
| I1 | Chuỗi giám sát bằng chứng: chữ ký số, `parent_hash`, trang xác minh | Bằng chứng khó bị sửa mà không bị phát hiện; tạo lòng tin với CSGT | Demo sửa 1 byte → xác minh báo sai | FR-EVD-1, FR-UI-4 |
| I2 | Giao thức đo chống thổi phồng: đăng ký trước, tập test chạy một lần, Wilson 95% | Hiếm thấy ở dự án sinh viên; con số tin được | Log `status: fresh`; tag đóng băng | FR-EVAL-3 |
| I3 | Lớp ngữ cảnh tất định có mã lý do | Giải thích được hệ thống đã từ chối gì và vì sao; đo được mức giảm báo nhầm | Ablation trên dev | FR-CTX-1 |
| I4 | Ùn tắc tính theo chu kỳ đèn (cycle failure) và gợi ý điều phối có giải thích | Dùng khái niệm kỹ thuật giao thông thật, không chỉ đếm số xe | Demo, sai số hàng chờ | FR-DEN-2, FR-DSP-1 |
| I5 | Agent an toàn: công cụ chỉ đọc, người duyệt, chế độ không LLM | Có AI nhưng không để LLM quyết định chuyện pháp lý | Test so khớp số liệu | FR-AGT-1, FR-AGT-2 |
| I6 | OTA có ký, canary, tự quay lại bản cũ | Thực hành production, hiếm ở dự án thi | Demo cập nhật bản hỏng | FR-OTA-1 |
| I7 | Bảng tối ưu edge FP32 / FP16 / INT8 kèm độ lệch mAP | Nhận định về edge dựa trên số đo | Bảng benchmark | FR-OPT-1, FR-OPT-2 |
| I8 | Luật dạng plugin trên một mô hình cảnh chung | Thêm loại vi phạm mà không phải viết lại | Review code; số dòng thay đổi khi thêm luật | FR-VIO-0 |
| I9 | Phân tích ùn tắc theo tuyến từ camera: đo chu kỳ đèn thực tế và tốc độ thoát bão hòa (việc kỹ sư giao thông thường phải bấm giờ tay); phát hiện tràn hàng chờ giữa các nút mà không cần biết xe là xe nào | Dùng khái niệm kỹ thuật giao thông thật (v/c, HCM, LOS); giải thích được; không thêm rủi ro riêng tư | Demo trang Tuyến; FR-EVAL-8 | FR-DEN-4, FR-COR-1, FR-COR-2 |
| T1 | Bản đồ camera và trạng thái | Điều hành viên nhìn toàn cảnh | FR-UI-3 | FR-INT-1 |
| T2 | Xuất hồ sơ cho quy trình phạt nguội | Nối vào quy trình làm việc thật của CSGT | FR-EXP-1 | FR-INT-2 |
| T3 | Kênh điều khiển thiết bị bằng MQTT: Last Will báo mất kết nối, thông báo trạng thái mong muốn và OTA; hỏi định kỳ luôn chạy làm đường dự phòng | Quản lý đội thiết bị; khớp gợi ý MQTT của đề | FR-DEV-2 AC1–AC3 | FR-DEV-2 |
| T4 | API dữ liệu mở, bot Telegram, bộ điều khiển đèn giả lập | Tích hợp với hệ sinh thái đô thị thông minh | COULD | FR-INT-3…5 |
| T5 | Live URL: trung tâm chạy trên cloud, edge ở máy local | Chứng minh mô hình edge → cloud chạy thật; deliverable số 5 | NFR-DEP-2 | NFR-DEP-2 |

---

## 11. Năng lực, rủi ro phạm vi và danh sách cắt

**Năng lực giả định:** 4 người × khoảng 25 giờ/tuần × 5 tuần ≈ 500 giờ. Phạm vi MUST + SHOULD là tham vọng. Kế hoạch dựa vào ba điều:
- spec và plan chi tiết, để giảm làm lại;
- dữ liệu mẫu theo hợp đồng, để các phía làm song song;
- danh sách cắt có điểm kích hoạt.

**Rủi ro chính:**
- **TV1 quá tải ở tuần 2–3** (đèn, 3 loại luật, mật độ, chỉnh ngưỡng). Đã chuyển gói bằng chứng và đếm theo làn sang TV2, phỏng vấn người dùng sang TV3 (Q5).
- **Ca ngược chiều và sai làn có thể hiếm** tại nút đã chọn:
  - tiêu chí chọn nút (WP-02) được bổ sung để giảm rủi ro này;
  - **không dàn dựng vi phạm trên đường** (nguy hiểm, trái luật); chỉ dùng các ca xảy ra tự nhiên;
  - loại nào có n < 30 thì báo cáo là "chỉ minh họa".
- **OCR biển số Việt Nam 2 dòng** có thể chưa đạt. Khi đó dùng chế độ người đọc, tức là FR-OCR-1 AC3.
- **TV2 là điểm nóng mới ở tuần 3**, vì nhận thêm đo theo chu kỳ và phân tích tuyến. Để bù: WP-40 chuyển sang TV4, FR-AGT-3 xuống COULD, FR-EXP-1 sang CP2.
- **Mỗi buổi quay cần 3 người có mặt cùng lúc**, và có khoảng 5 buổi: khảo sát tuyến, 2 buổi dev, tập test dự phòng, tập test chính.
- **Tràn hàng chờ có thể hiếm** trong các buổi quay. Chọn tuyến hay tắc vào giờ cao điểm chiều và quay ≥ 90 phút; n < 30 thì ghi "chỉ minh họa".

**Thứ tự cắt khi thiếu thời gian** (cắt từ trên xuống):
1. FR-INT-3, FR-INT-4, FR-INT-5
2. FR-VIO-ST
3. MQTT (FR-DEV-2). Hỏi định kỳ đã có từ CP1 nên cắt MQTT không mất chức năng; chỉ mất việc báo mất kết nối trong ≤ 10 giây và thông báo tức thì
4. FR-OPT-2 (giữ FP16)
5. FR-DSP-1 (chỉ giữ sự kiện ùn tắc và sự kiện tuyến)
6. Bản đồ nhiệt của trang Tuyến (giữ bản đồ và bảng số)
7. Tuyến giảm còn 2 nút (FR-MC-1 còn 2 camera)
8. FR-OTA-1 (chỉ cập nhật cấu hình, vẫn giữ kiểm chữ ký)

**Không bao giờ cắt:**
- vượt đèn đỏ, đi ngược chiều, sai làn đủ 3 kiểu;
- che biển số và khuôn mặt; duyệt 2 bước; chữ ký bằng chứng; đăng nhập;
- đếm theo làn, mật độ, phần lõi của phân tích tuyến (đo theo chu kỳ, hiệu năng từng nút, phát hiện tràn hàng chờ), Agent báo cáo ca trực;
- các metric mAP, độ chính xác đếm, precision vi phạm;
- chạy offline; đo FPS.

**Điểm kích hoạt:**

| Mốc | Nếu chưa đạt | Hành động |
|---|---|---|
| 25/09 | Không tuyến nào có làn riêng theo loại xe | Quay thêm một điểm riêng cho LN-a; báo PO |
| M2 (04/10) | Luật vượt đèn đỏ chưa qua thử trên dev | Cắt ngay FR-VIO-ST; TV4 hỗ trợ viết test cho luật; FR-DSP-1 xuống COULD để giải phóng TV1 ở tuần 4 |
| 04/10 | WP-13 (API ứng viên) trễ | Chuyển API tuyến (WP-54) sang TV4 |
| 08/10 | Luật làn chưa sẵn sàng | Luật làn chỉ trình diễn, không báo precision trên test |
| CP1 (14/10) | Hoàn thành < 70% | Cắt ngay các mục 1–5 trong danh sách |
| 19/10 | Chạy test bị trượt lịch | Dùng tập test dự phòng |

---

## 12. Quản lý thay đổi (Change Request)

Mỗi thay đổi ghi vào `docs/spec/changes.md` theo mẫu:

```text
CR-xxx · ngày · người đề xuất
Thay đổi: …
Lý do: …
Ảnh hưởng: ID spec | hợp đồng | lịch | người làm
Phương án đã cân nhắc: …
Quyết định (PO): duyệt / không duyệt · spec lên phiên bản …
```

**Nguyên tắc:**
- Sau M0 (24/09), spec chỉ đổi qua CR.
- Sau M3 (11/10), không đổi ngưỡng và không đổi luật của các loại vi phạm được đánh giá.
- Sau CP2 (23/10), chỉ sửa lỗi.
- Đổi kiến trúc: dừng → giải thích → đề xuất → chờ PO duyệt (CLAUDE.md mục 12).

---

## 13. Mâu thuẫn với các tài liệu khác, cần sửa

PRD Gate 1, README, kế hoạch Gate 1 và CLAUDE.md được viết lại ngày 21/09. Spec **không sửa các file đó**; người phụ trách cần sửa theo bảng dưới.

| Tài liệu | Đang ghi | Theo spec |
|---|---|---|
| PRD mục 1 và 4.2; README; 1-page brief | "Precision ≥ 95%" như một cam kết | Báo precision đo được kèm Wilson 95%. Muốn cận dưới Wilson ≥ 95% thì cần ≥ 59 cảnh báo và 0 báo nhầm. Kể cả đo được 57/60 = 95%, cận dưới Wilson chỉ khoảng 86%. n < 30 thì chỉ minh họa |
| PRD mục 1; README; brief; CLAUDE.md mục 1 | "Giảm > 90% băng thông" | Chỉ báo số đo thật (NFR-PRIV-1) |
| PRD; README; brief; CLAUDE.md mục 1 | "15 tình huống báo nhầm" | Có 22 mã A1–E5 cho vượt đèn đỏ, cộng các mã W, L, S mới |
| PRD mục 4.3; README; brief | Trích Nghị định 13/2023/NĐ-CP | Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15, hiệu lực từ 01/01/2026 (báo cáo mục 12) |
| README; kế hoạch Gate 1 | "25 gói công việc" | Timeline v2.0 có WP-01…WP-56 |
| PRD; CLAUDE.md mục 1 | Chỉ có vượt đèn đỏ | Thêm WW, LN (đủ 3 kiểu), ST, mật độ/ùn tắc, phân tích tuyến, OCR, mAP, bản đồ và các mục nâng cao |
| PRD FR-3.3 | Clip video 3–5 giây | Chuỗi JPEG từ t − 3 s tới t + 2 s (Orin Nano không có bộ mã hóa phần cứng) |
| PRD FR-4.3 | Đệm tối thiểu 7 ngày | Thử thật ≥ 24 giờ; tính toán dung lượng cho 7 ngày (NFR-OFF-1) |
| PRD mục 4.3 | TLS 1.3 | TLS từ CP2 qua reverse proxy; M1 chạy HTTP trên localhost |
| PRD FR-3.1 | "Làm mờ trên mọi khung hình" | Làm mờ trên gói bằng chứng và mọi ảnh rời khỏi thiết bị; video thô liên tục không rời thiết bị |
| Kế hoạch Gate 1 | Agent và Docker Compose để ở tuần 5 | Docker Compose từ tuần 1 (plan M1); Agent báo cáo phải xong trước CP1 |
| README | Python 3.11/3.13 | Python 3.11 (CI và Dockerfile) |

---

## 14. Quyết định của PO

| # | Câu hỏi | Quyết định | Trạng thái |
|---|---|---|---|
| Q1 | Phạm vi vi phạm | MUST: vượt đèn đỏ, đi ngược chiều, sai làn (ít nhất 2 kiểu; Q8 nâng lên đủ 3 kiểu). COULD: dừng, đỗ sai | **Đã chốt 21/09** |
| Q2 | Có đưa MQTT vào không | Dữ liệu vẫn đi HTTPS + outbox (H-01). Ở CP2, thêm MQTT làm **kênh điều khiển**: báo mất kết nối bằng Last Will, thông báo trạng thái mong muốn và OTA (FR-DEV-2, mục 6.7) | **Đã chốt 21/09** |
| Q3 | Live URL (deliverable số 5 của AI20K) | Triển khai phần trung tâm lên cloud, có TLS, trước CP2; chỉ dùng dữ liệu demo của dự án; edge chạy local và gửi dữ liệu lên (NFR-DEP-2, WP-52) | **Đã chốt 21/09** |
| Q4 | Ngày checkpoint | CP1: Thứ Tư 14/10 (80%). CP2: Thứ Sáu 23/10 (100%) | **Đã chốt 21/09** |
| Q5 | Phân vai và thời hạn lưu giữ | Đề xuất: từ tuần 2, phỏng vấn người dùng chuyển sang TV3; gói bằng chứng và đếm theo làn chuyển sang TV2; thời hạn lưu giữ tối đa 7 ngày | Chờ duyệt tại M0 (24/09) |
| Q6 | Mức "chỉnh đèn" | Chỉ phân tích ùn tắc; không tự tính hay tự đổi thời gian đèn. Webster + SUMO để ở hướng mở rộng | **Đã chốt 21/09** |
| Q7 | Dữ liệu cho phân tích tuyến | Quay thật 3 nút liên tiếp, cùng lúc, bằng 3 camera của FR-MC-1 | **Đã chốt 21/09** |
| Q8 | "Làm full cả 3 vấn đề" | 3 loại vi phạm của đề; sai làn đủ 3 kiểu, đều MUST. Dừng/đỗ sai vẫn là COULD | **Đã chốt 21/09** |
| Q9 | Phân tích tuyến vào checkpoint nào | Xong trước CP1; đánh giá trên tập test ở CP2. Bù tải: FR-AGT-3 xuống COULD, FR-EXP-1 sang CP2, WP-40 sang TV4 | **Đã chốt 21/09** |

---

## Nguồn

- Luật Trật tự, an toàn giao thông đường bộ 2024 (36/2024/QH15), Điều 13 — [xaydungchinhsach.chinhphu.vn](https://xaydungchinhsach.chinhphu.vn/luat-trat-tu-an-toan-giao-thong-duong-bo-quy-dinh-su-dung-lan-duong-119241218175948161.htm); [toàn văn](https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Luat-trat-tu-an-toan-giao-thong-duong-bo-2024-so-36-2024-QH15-444251.aspx)
- Nghị định 168/2024/NĐ-CP, mức phạt đi ngược chiều — [xaydungchinhsach.chinhphu.vn](https://xaydungchinhsach.chinhphu.vn/muc-phat-moi-voi-nguoi-dieu-khien-xe-o-to-xe-may-di-nguoc-chieu-tu-1-1-2025-119241231112057474.htm); [toàn văn Nghị định](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-168-2024-nd-cp-quy-dinh-xu-phat-vi-pham-hanh-chinh-ve-trat-tu-atgt-duong-bo-119241231164556785.htm)
- Nghị định 168/2024/NĐ-CP, đi không đúng làn và chuyển làn — [thuvienphapluat.vn](https://thuvienphapluat.vn/banan/tin-tuc/muc-phat-loi-chuyen-lan-duong-khong-dung-quy-dinh-moi-nhat-theo-nghi-dinh-168-13039); [vnlawfirm.vn](https://vnlawfirm.vn/loi-di-khong-dung-phan-duong-hoac-lan-duong-phat-bao-nhieu/)
- Nghị định 168/2024/NĐ-CP, dừng và đỗ nơi đường bộ giao nhau — [vnlawfirm.vn](https://vnlawfirm.vn/dung-xe-do-xe-tai-vi-tri-noi-duong-bo-giao-nhau-bi-phat-bao-nhieu/); [phaplyxe.vn](https://phaplyxe.vn/loi-do-xe-noi-duong-bo-giao-nhau/)
- fast-plate-ocr (giấy phép MIT, model "global", chạy ONNX) — [GitHub](https://github.com/ankandrew/fast-plate-ocr)
- TCVN 13592:2022 Đường đô thị, Bảng 3 (hệ số quy đổi ra xe con, Điều 6.2.1) — [atld.vn](https://www.atld.vn/law/3304/content). Đây là bản đăng lại; cần đối chiếu bản chính thức trước khi trích trong báo cáo
- Công thức độ trễ d1, d2 của HCM — [NACTO](https://nacto.org/wp-content/uploads/control_delay_variability_at_signalized_intersection_darma.pdf). Ngưỡng LOS của nút có đèn — [Loudoun County](https://www.loudoun.gov/DocumentCenter/View/161296/Existing-Conditions-Delay-and-Level-of-Service), là bản tóm tắt thứ cấp, chưa đối chiếu bản gốc HCM
- Các nguồn công nghệ khác (YOLO26, ByteTrack, MediaMTX, TensorRT): báo cáo kỹ thuật, mục 22
