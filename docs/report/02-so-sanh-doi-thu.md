# So sánh với đối thủ cùng đề DEV-14

> **Ngày:** 22/09/2026
> **Đối thủ:** TrafficEye Edge của T233 (Group 05), Cohort 3.
> **Bên tôi:** P-014, TrafficEye Edge, Cohort 4.
> **Phạm vi:** chỉ dùng hai nguồn dưới đây. Khuyến nghị chỉ lấy từ những gì đã xuất hiện ở một trong hai bên; không thêm ý tưởng thứ ba.

---

## 0. Nguồn, cách trích dẫn, cách đọc kết luận

### 0.1 Nguồn đã đọc

| Nguồn | Nội dung thực có | Đã đọc |
|---|---|---|
| **#1 — Đối thủ** `VINAI/Website-downloader/TrafficEye-analysis/` | **1 file phân tích** `TrafficEye-Edge-phan-tich-ky-thuat.md` (1151 dòng) và 33 ảnh (`assets/inside` 9, `live` 3, `slides` 14, `video` 7). **Không có mã nguồn.** Chính file phân tích ghi: không tìm thấy repo công khai của đội (dòng 93) | Toàn bộ file md. Kiểm chéo 3 ảnh: `inside/05-csgt-studio.jpg`, `inside/02-operator-phan-tich-ai.jpg`, `slides/page-12.png`, đều khớp văn bản |
| **#2 — Bên tôi** `P-014/docs/` (trừ `gate1/`) | spec v1.0-draft, báo cáo v0.4, design review, survey báo nhầm, protocol, mẫu báo cáo, timeline v2.0, plan M1, 2 file sơ đồ | Toàn bộ, riêng plan M1 đọc phần khung và các TASK liên quan. `docs/guide/` là giáo trình chung của khóa (xem `guide/chapter-01.md` dòng 6–16), không phải thiết kế TrafficEye, nên không dùng làm bằng chứng |

### 0.2 Ký hiệu trích dẫn

| Ký hiệu | File |
|---|---|
| `DT:L…` | `TrafficEye-Edge-phan-tich-ky-thuat.md` (nguồn #1), số dòng |
| `DT-img:…` | ảnh trong `TrafficEye-analysis/assets/` |
| `spec:L…` | `docs/spec/trafficeye-spec.md` |
| `report:L…` | `docs/report/trafficeye-edge-report.md` |
| `review:<mã>` | `docs/report/design-review.md`, theo mã phát hiện (C-01, H-01…) |
| `fp:L…` | `docs/survey/false-positives.md` |
| `protocol:L…` | `docs/eval/protocol.md` |
| `timeline:L…` | `docs/plan/timeline.md` |
| `plan:L…` | `docs/plan/2026-09-21-m1-skeleton.md` |
| `arch:L…` / `tq:L…` | `docs/architecture_diagram.md` / `docs/Trucquanhoadocs.md` |

Sau ngày 22/09 có ba file đổi chỗ: `false-positives.md` sang `docs/spec/`, design review thành phụ lục A của báo cáo, và chính file này sang `docs/report/`. Các ký hiệu trên vẫn trỏ tới đường dẫn tại commit `885299e`.

Số dòng của các file bên tôi tính theo commit `885299e`, tức bản trước khi sửa ở mục 5. Sau khi sửa, số dòng của spec và timeline đã lệch. Xem đúng bản đã trích bằng lệnh `git show 885299e:docs/spec/trafficeye-spec.md`. `Trucquanhoadocs.md` đã bị xóa ngày 22/09; xem lại bằng `git show 885299e:docs/Trucquanhoadocs.md`.

### 0.3 Cách đọc cột "Ai vượt trội"

Hai bên đang ở hai giai đoạn khác nhau:
- Đối thủ là Cohort 3, đã qua Demo Day tháng 9/2026 (`DT:L5`, lộ trình `DT:L876-881`). Họ có sản phẩm chạy, dù chỉ chạy một phần.
- Bên tôi đang ở tuần 1. Docs ghi rõ: "Chưa có code hệ thống" (`report:L14`, `protocol:L4`).

Vì vậy mỗi kết luận ghi kèm **căn cứ so sánh**:
- **(thiết kế):** so bản thiết kế của tôi với thiết kế hoặc hành vi quan sát được của đối thủ.
- **(thực thi):** so cái đang chạy thật; ở loại này bên tôi chưa có gì để đặt lên bàn cân.

**Lệch giữa bối cảnh và docs:** bối cảnh bạn gửi ghi "MQTT" trong stack. Docs đã chốt: dữ liệu đi **HTTPS + outbox**, còn MQTT chỉ làm kênh điều khiển từ CP2 (`review:H-01`; `spec:L1292`, Q2). Bảng dưới làm theo docs.

---

## 1. Tóm tắt

- **Thiết kế của tôi mạnh hơn ở mọi khía cạnh quyết định precision, riêng tư và toàn vẹn bằng chứng**: luật vi phạm, HITL, làm mờ, chữ ký bằng chứng, hợp đồng sự kiện, giao thức đo.
- **Đối thủ hơn ở mọi khía cạnh cần hệ thống chạy thật**: model đã fine-tune và có số đo, backend, giao diện, Live URL, công cụ mô phỏng.
- **Không có ô "Tôi vượt trội" nào đã được chứng minh bằng code chạy.** Hơn nữa, `scripts/evaluate.py` mà docs nói "đã có" không nằm trong repo (mục 4, G4).
- **Kết quả:** 18 dòng so sánh.
  - Tôi vượt trội: 10 dòng, đều ở mức thiết kế, trừ dòng tài liệu và Git.
  - Đối thủ vượt trội: 6 dòng, đều ở mức thực thi hoặc độ rộng.
  - Ngang nhau hoặc không đủ dữ liệu: 2 dòng.

---

## 2. Bảng so sánh

| # | Khía cạnh | Đối thủ làm gì (trích file) | Tôi làm gì (trích tài liệu) | Ai vượt trội | Lý do |
|---|---|---|---|---|---|
| 1 | **Kiến trúc tổng thể** | Kiến trúc lai "hai đường vào, một bộ não" (`DT:L42`, `L142-163`):<br>• Đường A: node biên Python chạy YOLOv8n ONNX, ByteTrack, luật vi phạm, SHA-256 + làm mờ, đệm SQLite (`DT:L161`).<br>• Đường B: Central Vision Gateway kéo luồng iHanoi/HPSmart về suy luận tập trung (`DT:L162`).<br>• 3 tầng deploy dùng chung schema (`DT:L43-46`).<br>Thực tế:<br>• "camera biên" là nguồn SIMULATION do server phát (`DT:L68`, `L298-301`);<br>• ngày 22/09 chỉ đường B chạy (`DT:L1025`);<br>• 2 hợp đồng Edge→Backend chạy song song, chưa hợp nhất (`DT:L870`) | Edge-first thuần: edge → outbox → HTTPS → FastAPI + PostgreSQL → dashboard (`report:L41`, `L132-165`).<br>• Edge là container trên laptop; thiết bị đích là Jetson Orin Nano Super (`report:L46`).<br>• Video thô liên tục không rời thiết bị (`spec:L624`).<br>• Trung tâm lên cloud trước CP2, edge chạy local (`spec:L630`).<br>• Một hợp đồng sự kiện (`spec:L739-742`) | **Tôi vượt trội** (thiết kế) | Đường B là suy luận tập trung. Chính người phân tích ghi nó đi ngược luận điểm edge-first (`DT:L1069`), và trên server nó chỉ đạt 5–6 FPS (`DT:L986`). Hai hợp đồng chưa hợp nhất là lỗi kiến trúc đội tự nhận. Thiết kế của tôi có một đường dữ liệu và một hợp đồng. **Nhưng** chỉ đối thủ có hệ thống đang chạy với camera thật |
| 2 | **Model + tracking** | • YOLOv8n (Ultralytics), 4 lớp; ONNX FP32 12,85 MB, nhanh hơn PyTorch 1,32× (`DT:L204`, `L220`).<br>• Fine-tune trên dữ liệu Đà Nẵng: mAP50 từ 0,590 lên 0,892, đo trên 5.463 ảnh val; có AP theo lớp (`DT:L221-222`).<br>• ByteTrack 1,35 ms. Khử hộp trùng khác lớp, giảm phân mảnh ID từ 1,46 xuống 1,19 (`DT:L223-224`).<br>• 55,8 ms/khung, đo trên MX150 (`DT:L237`).<br>• Chưa có FP16/INT8; TensorRT chưa có số (`DT:L701`, `L720`).<br>• **Input size: không tìm thấy trong repo.**<br>• Trên server: 5–6 FPS (`DT:L986`) | • YOLO26n, `imgsz` 640, đích TensorRT FP16 (`spec:L711`, `L620`).<br>• INT8 chỉ dùng nếu mAP50 giảm ≤ 2 điểm (`spec:L583`), vì INT8 làm mAP YOLO26n trên Orin giảm từ 0,480 xuống 0,449 (`report:L280`).<br>• Trọng số COCO; fine-tune nếu AP50 xe máy < 0,5 trước 04/10 (`spec:L198`).<br>• ByteTrack; chuyển BoT-SORT nếu số đo cho thấy đổi ID gây báo nhầm (`report:L296`).<br>• Benchmark p50/p95 từng tầng (`spec:L573-579`).<br>• Số đo duy nhất: 28 FPS trên CPU cho detect + track (`spec:L65`) | **Đối thủ vượt trội** (thực thi) | Đối thủ có model đã fine-tune, có số mAP và độ trễ, dù chỉ đo trên tập val và laptop MX150. Tôi mới có kế hoạch và một số FPS CPU. Cổng FP16/INT8 theo độ lệch mAP của tôi chặt hơn trên giấy, nhưng chưa có số nào để so |
| 3 | **Logic phát hiện vi phạm** | • Loại vi phạm: `RED_LIGHT_VIOLATION`, `WRONG_LANE`, `WRONG_DIRECTION` (`DT:L226`).<br>• Xác nhận khi track ổn định đủ N frame và thỏa hình học làn (`DT:L225`, `L777`).<br>• Máy trạng thái đèn vàng; có ROI đèn (`DT:L227`).<br>• Làn có `direction`, `allowed_classes`; vùng thoát có miễn trừ rẽ phải (`DT:L327-331`).<br>• Ngưỡng thấy được: ngược chiều "8 frame" (`DT:L988`); trong mock có "7 frame" và "142°" (`DT:L228`).<br>• **Ngưỡng vượt đèn đỏ: không tìm thấy.**<br>• Chưa đối chiếu đếm tay (`DT:L866`).<br>• Trên hệ thống thật: đèn UNKNOWN ở HP-CAM-001; 438/473 track không rơi vào làn đã vẽ (`DT:L986-987`) | • Vượt đèn đỏ: 6 điều kiện, 22 mã loại trừ A1–E5 (`fp:L19-77`).<br>• Ngược chiều: W1–W8. Sai làn LN-a/b/c: L1–L8 (`fp:L81-138`).<br>• Ngưỡng theo giây, mét, km/h qua homography (`spec:L715-719`).<br>• Ước lượng điểm đầu xe, vì camera nhìn từ phía sau (`review:H-05`); dùng vùng giao lộ thay cho vạch (`review:M-03`).<br>• Đèn UNKNOWN, NHẤP NHÁY, TẮT thì chặn gắn cờ (`spec:L312`, `report:L390-394`).<br>• Lớp ngữ cảnh tất định có mã lý do và ablation (`spec:L315-326`).<br>• Luật dạng plugin (`spec:L870-906`); đóng băng 11/10 | **Tôi vượt trội** (thiết kế) | Ngưỡng đếm frame đổi nghĩa theo FPS. Tài liệu không nói "frame" ở đây là khung của luồng gốc hay khung đã xử lý:<br>• theo luồng gốc 20 fps (`DT:L271`), 8 frame ≈ 0,4 s;<br>• theo khung xử lý của job HP-CAM-003 (6,1 FPS, `DT:L986`), 8 frame ≈ 1,3 s.<br>Ngưỡng của tôi dùng đơn vị vật lý trên video đã chuẩn hóa 15 FPS (`review:H-02`), kèm danh mục mẫu âm khó có mã. Chưa có dòng code luật nào |
| 4 | **Event schema và giao tiếp edge–trung tâm** | • Gửi metadata JSON + ảnh đã làm mờ qua Ingestion API (`DT:L154`, `L233`).<br>• Đệm SQLite: ngắt mạng 30 s, xả 15/15 bản ghi, 0 trùng (`DT:L234`, `L702`).<br>• Có `connection_state` 5 trạng thái và `offline_buffer_count` (`DT:L234`).<br>• `event_id` dạng `{camera}-{unix_ts}-{seq}` (`DT:L1004`).<br>• **Giao thức edge→trung tâm cụ thể và khóa chống trùng: không tìm thấy** (`DT:L1070` ghi "chưa rõ").<br>• 2 hợp đồng song song (`DT:L870`).<br>• **Kênh trung tâm→edge: không tìm thấy** | • Vỏ chung: `schema_version`, `event_id` (UUIDv7), `seq`, `device_id`, `camera_id`, `type`, `captured_at`, `processed_at`, `source` (`spec:L739-742`); 8 loại sự kiện (`spec:L746-755`); quy tắc tăng phiên bản (`spec:L807-809`).<br>• HTTPS + outbox SQLite: chỉ xóa khi trung tâm xác nhận; backoff tới 30 s; trung tâm đặt UNIQUE trên `event_id`; phát hiện lỗ hổng `seq` (`report:L526-531`; `plan:L1133-1253`).<br>• Bằng chứng tải sau metadata, có checksum (`spec:L385-388`).<br>• AC: ngắt mạng 10 phút (`spec:L430`); chịu được ≥ 24 giờ (`spec:L623`).<br>• Trung tâm→edge: edge hỏi `desired` mỗi 10 s, có `revision`; MQTT chỉ báo "có thay đổi", từ CP2 (`spec:L432-455`, `L908-975`) | **Tôi vượt trội** (thiết kế) | Khóa chống trùng rõ ràng và một hợp đồng có phiên bản giải đúng hai vấn đề đối thủ tự nhận còn mở. Phép thử của tôi lớn hơn: 10 phút, trộn nhiều loại sự kiện, so với 15 bản ghi. Outbox và chống trùng mới chạy thử trên bản sao tạm, chưa có trong repo (`plan:L23-26`) |
| 5a | **Backend, API** | • FastAPI + PostgreSQL (có pgvector) + Redis (`DT:L44-45`, `L494`).<br>• Khoảng 60 endpoint, suy ra từ front-end (`DT:L503-570`).<br>• Middleware request-id (`DT:L181`).<br>• Test: 643 passed theo video, 933 theo edufun (`DT:L709`, `L717`).<br>• Chạy production sau Cloudflare → Caddy (`DT:L165-184`) | • FastAPI + PostgreSQL (`report:L350`).<br>• 22 endpoint đặc tả, có vai trò và checkpoint (`spec:L842-868`).<br>• M1: `POST /api/v1/events` xác thực bằng token thiết bị (`plan:L1681-1693`).<br>• Chưa có code hệ thống (`report:L14`) | **Đối thủ vượt trội** (thực thi) | Đối thủ có backend chạy thật, bề mặt API rộng và bộ test; số test lệch giữa hai nguồn (`DT:L717`). Bên tôi mới có đặc tả |
| 5b | **Xác thực, phân quyền** | • JWT lưu `localStorage`; xử lý 401/403/429, tức có rate limit (`DT:L465-468`).<br>• 2 vai trò OPERATOR, ADMIN_CSGT, có ma trận route (`DT:L472-482`).<br>• WebSocket thông báo dùng ticket ngắn hạn qua subprotocol; WebSocket khẩn cấp để JWT trong query string (`DT:L447-448`).<br>• Có tài khoản kiểm thử công khai (`DT:L469`).<br>Lỗi quan sát được:<br>• `/edge/live` trả URL camera kèm user/pass cho mọi tài khoản (`DT:L1018`);<br>• API sự cố trả CCCD, SĐT cho Operator (`DT:L1021`);<br>• audit chỉ ghi IP Docker (`DT:L1023`) | • 4 vai trò người dùng (operator, csgt, admin, auditor) cộng token riêng cho từng thiết bị; kiểm quyền ở backend (`spec:L159-175`).<br>• Mật khẩu băm bcrypt/argon2; JWT 15 phút + refresh; test 401/403 cho mọi endpoint (`spec:L472-476`).<br>• Trường OCR lọc theo vai trò (`spec:L780`).<br>• Bí mật chỉ qua biến môi trường; giới hạn tần suất đăng nhập; production không còn tài khoản mặc định; chạy `pip-audit`, `npm audit` (`spec:L635-641`) | **Tôi vượt trội** (thiết kế) | Tách quyền mịn hơn: có vai trò kiểm toán riêng, lọc trường theo vai. Spec có quy định chặn đúng loại lỗi đã thấy ở đối thủ (lộ credential, lộ PII). Đối thủ có hệ thống chạy và kỹ thuật ticket WebSocket tốt; thiết kế của tôi chưa có code kiểm chứng |
| 6 | **HITL, quy trình duyệt** | • Một bước: CSGT duyệt bằng phím A/R, hoàn tác U, ghi chú ≥ 8 ký tự (`DT:L386-389`, `L989`).<br>• Sự kiện ở PENDING, không tự phạt (`DT:L395`).<br>• Mở ảnh gốc cần vai trò CSGT và lý do (`DT:L389`).<br>• Nhưng UI ghi "Operator được xem ảnh bằng chứng gốc" (`DT:L1022`; `DT-img:inside/05-csgt-studio.jpg`), và Operator vào được `/csgt-studio` (`DT:L478`).<br>• Ngày 22/09: 179 vi phạm chờ, 0 lượt duyệt hay bác bỏ (`DT:L988`, `L990`) | • Hai bước (`spec:L478-489`):<br>&nbsp;&nbsp;– điều hành viên xem bản đã che, xác nhận hoặc bác bỏ kèm mã lý do;<br>&nbsp;&nbsp;– CSGT chỉ mở được bản CSGT sau bước 1, mỗi lần xem ghi nhật ký, có test.<br>• Hàng đợi cập nhật qua SSE trong ≤ 5 s (`spec:L482`).<br>• Bị bác bỏ thì xóa gói bằng chứng theo chính sách lưu giữ (`report:L193-194`) | **Tôi vượt trội** (thiết kế) | Tách vai: người sơ duyệt không thấy biển số. Mã lý do khi bác bỏ trở thành dữ liệu phân tích báo nhầm. UI của đối thủ mâu thuẫn với chính slide của họ. Đối thủ hơn về tốc độ thao tác duyệt: phím tắt và hoàn tác |
| 7 | **Riêng tư** (làm mờ ở bước nào) | • Tại biên: băm SHA-256 ảnh gốc, rồi Gaussian blur (`DT:L230`, `L903`).<br>• Blur theo heuristic 25% phía dưới crop xe; chưa có model dò biển số (`DT:L231`, `L868`).<br>• ANPR chỉ chạy sau khi duyệt (`DT:L232`).<br>• Có `privacy_state` và `raw_image_url` riêng (`DT:L641`, `L685`).<br>• **Đường B làm mờ ở bước nào: không tìm thấy.**<br>• Chưa đo tỉ lệ biển số/khuôn mặt bị lọt | • Che tại edge (`report:L511-513`).<br>• 3 bản (`spec:L390-400`):<br>&nbsp;&nbsp;– bản điều hành viên che hết;<br>&nbsp;&nbsp;– bản CSGT chỉ để rõ xe vi phạm;<br>&nbsp;&nbsp;– bản đầy đủ niêm phong trên thiết bị, xóa khi hết hạn.<br>• Detector biển số, dự phòng che nửa dưới bbox; detect `person` để che mặt (`spec:L196`, `L392`).<br>• Đo tỉ lệ lọt kèm Wilson, mục tiêu ≤ 1% (`spec:L402-405`; `review:H-04`).<br>• OCR chỉ cho xe vi phạm (`spec:L407-417`); không nhận diện khuôn mặt (`spec:L152`); căn cứ Luật 91/2025 (`report:L518`) | **Tôi vượt trội** (thiết kế) | Bên tôi có phép đo tỉ lệ lọt, và bản CSGT vẫn che các xe khác. Đối thủ dùng heuristic mà chính người phân tích ghi là có thể lọt (`DT:L1063`). Ý "băm trước khi che" của đối thủ tương đương `parent_hash` của tôi (`spec:L379`, `L831`) |
| 8 | **Frontend, dashboard, UX** | • Next.js 16, Tailwind, Zustand, Leaflet + CARTO, hls.js, dark/light (`DT:L497`).<br>• Ma trận camera 1×1 → 3×3 → Hero (`DT:L372`); bản đồ GIS có nón FOV (`DT:L311`).<br>• Calibration Studio với 6 công cụ vẽ (`DT:L314-332`); CSGT Studio; trang Audit có bộ lọc và xuất CSV (`DT:L404`); cổng SOS (`DT:L418`).<br>Lỗi quan sát được: hiển thị "64400%", KPI 6168,5 phút, mock đóng gói vào production (`DT:L987`, `L991`, `L1072`) | • 7 trang FR-UI-1…7 (`spec:L504-512`): số đếm; hàng đợi SSE; bản đồ Leaflet + OSM, có ảnh tĩnh khi mất mạng; trang xác minh công khai; trang sức khỏe có nút chế độ điều khiển tay; báo cáo Agent; trang Tuyến.<br>• Tiếng Việt, responsive từ 360 px, dark mode, có trạng thái tải/lỗi/rỗng (`spec:L502`).<br>• Cấu hình cảnh sửa tay bằng YAML (`spec:L647`). **Giao diện hiệu chuẩn: không có trong docs** | **Đối thủ vượt trội** (thực thi) | Đối thủ có giao diện chạy thật, nhiều màn hình, có công cụ hiệu chuẩn. Bên tôi mới là danh sách trang |
| 9 | **Đánh giá** (mAP, precision, recall; có tách tập test không) | • mAP50 0,892 trên 5.463 ảnh **val** Đà Nẵng (`DT:L221`, `L699`). **Tập test tách riêng: không tìm thấy.**<br>• Precision vi phạm chưa có số; mục tiêu ≥ 98% (`DT:L704`, `L866`).<br>• Offline 15/15 (`DT:L702`).<br>• Băng thông "giảm > 95%" không nêu cách đo (`DT:L705`).<br>• FPS có ghi rõ môi trường đo (`DT:L697`).<br>• Nhiều số không khớp giữa các nguồn (`DT:L712-726`) | Giao thức đã duyệt:<br>• chia theo phiên quay; chỉnh ngưỡng bằng leave-one-video-out; đóng băng 11/10 bằng SHA-256 + tag; tập test quay sau đóng băng; 2 người gán nhãn mù, đo kappa; chạy test đúng một lần; Wilson 95%; trạng thái `burned` nếu đổi config sau khi xem (`protocol:L15-25`, `L44-138`);<br>• bảng cỡ mẫu (`protocol:L231-248`);<br>• mAP: khoảng 200 khung dev, và khoảng 150 khung test gán nhãn không dùng model gợi ý (`protocol:L464-477`);<br>• precision báo riêng từng loại (`protocol:L459-461`); tỉ lệ lọt; MAE của đếm (`protocol:L228-229`) | **Tôi vượt trội** (phương pháp) | Chỉ bên tôi tách tập test và đặt cỡ mẫu tối thiểu, nên con số precision (khi có) bảo vệ được trước giám khảo. **Nhưng** hiện chưa có số đo nào, và script đánh giá không có trong repo (G4) |
| 10 | **Hạ tầng, DevOps** (Docker, CI/CD, deploy, OTA) | • Docker Compose (`DT:L183`).<br>• Production: Cloudflare → Caddy → Next.js + FastAPI trên domain riêng (`DT:L165-184`, `L498`).<br>• **CI/CD: không tìm thấy** (chỉ có câu "Ruff 100%", `DT:L709`).<br>• OTA nằm ở lộ trình 2027 (`DT:L876-881`) | • Docker Compose từ tuần 1 (plan TASK-013); đã có CI chạy ruff + pytest (`report:L370`).<br>• CI thêm build dashboard và Docker; độ phủ test `src/edge` ≥ 80% (`spec:L631`).<br>• Live URL trước CP2 (`spec:L630`; timeline WP-52).<br>• OTA ký Ed25519, canary, tự quay lại bản cũ (`spec:L457-468`).<br>• Runbook, thử khôi phục DB, soak test 24 giờ (`spec:L627-629`) | **Đối thủ vượt trội** (thực thi) | Họ đã có Live URL chạy production; WP-52 của tôi chưa bắt đầu. Về thiết kế, CI và OTA của tôi đầy đủ hơn: đối thủ chưa có OTA |
| 11a | **Chất lượng code, kiểm thử** | • **Không có mã nguồn** (`DT:L93`).<br>• Chỉ nhận xét được qua bundle front-end: mock trong production, `API_BASE_URL` hard-code, tên trường tiếng Việt không dấu, cổng 8000 cố định (`DT:L1071-1077`).<br>• Số test do đội tự công bố (`DT:L709`) | • Chưa có code hệ thống (`report:L14`).<br>• Plan M1 viết theo TDD; 62 test pass khi chạy thử trên bản sao tạm (`plan:L23-26`).<br>• DoD yêu cầu unit test và test tái hiện lỗi (`spec:L1147`) | **Ngang nhau / không đủ dữ liệu so sánh** | Trong hai nguồn này, không bên nào có mã nguồn đọc được |
| 11b | **Tài liệu, quy trình Git** | • Tài liệu công khai: slide 14 trang, video, trang edufun (`DT:L83-90`).<br>• Có slide "Hiện trạng và giới hạn" (`DT:L862-870`).<br>• **Quy trình Git: không tìm thấy** (không có repo, `DT:L93`) | • Spec có ID, AC đo được, DoR/DoD, thủ tục Change Request (`spec:L25-39`, `L1133-1164`, `L1245-1262`).<br>• Design review 22 phát hiện (`review`, mục Tóm tắt).<br>• Mỗi WP một nhánh, mỗi TASK một commit Conventional Commits, PR có review, CI xanh mới merge (`plan:L60-63`; `timeline:L357-360`).<br>• Điểm trừ: 2 file sơ đồ còn những câu mà spec mục 13 đã đánh dấu sai (G5) | **Tôi vượt trội** | Tài liệu của tôi truy vết được từ yêu cầu tới nghiệm thu. Đối thủ không có repo để đánh giá quy trình, và số liệu giữa các nguồn của họ lệch nhau (`DT:L712-726`) |
| 12a | *Khác:* **Toàn vẹn bằng chứng và audit** | • Băm SHA-256 ảnh gốc (`DT:L230`).<br>• Audit có `chain_hash` + `previous_hash`, endpoint `verify-integrity`, xuất CSV (`DT:L391`, `L398-404`).<br>• **Chữ ký số: không tìm thấy** | • Gói bằng chứng có SHA-256, chữ ký Ed25519 bằng khóa thiết bị, `parent_hash`, `signing_key_id` (`spec:L372-383`, `L811-840`).<br>• Sửa 1 byte thì phép xác minh báo sai (`spec:L382`).<br>• Trang xác minh công khai, không hiện ảnh (`spec:L509`).<br>• Mã băm đầu chuỗi nhật ký commit ra git hằng ngày (`review:L-02`; `spec:L492`) | **Tôi vượt trội** (thiết kế) | Băm chỉ chứng minh bằng chứng không bị đổi; chữ ký còn chứng minh thiết bị nào đã tạo ra nó. Chuỗi nhật ký của đối thủ nằm trong cùng DB, đúng rủi ro L-02: "người kiểm soát DB có thể dựng lại cả chuỗi" |
| 12b | *Khác:* **Nhiều camera, phân tích tuyến** | • Gom cụm Haversine ≤ 1 km: công bố 159 camera → 40 cụm; CSDL demo có 4 cụm (`DT:L307`, `L981`).<br>• Corridor link có `distance_meters`, `expected_transit_sec`, mục đích chống đếm trùng và ước lượng hàng chờ (`DT:L309`).<br>• **Bằng chứng phần phân tích chạy thật: không tìm thấy** (chỉ có CRUD và mock) | • Tuyến 3 nút, 3 camera chạy đồng thời (`spec:L563-565`).<br>• Sự kiện `signal_cycle` mỗi chu kỳ đèn (`spec:L240-255`).<br>• v/c, độ trễ HCM d1 + d2, LOS, tràn hàng chờ, nút cổ chai, ngưỡng đóng băng (`spec:L257-304`, `L723-733`).<br>• Đo sai số theo FR-EVAL-8 (`protocol:L520-532`) | **Tôi vượt trội** (thiết kế) | Bên tôi có công thức, ngưỡng và tiêu chí nghiệm thu; đối thủ mới có mô hình dữ liệu. Rủi ro: phần này nặng (TV2 là điểm nóng tuần 3, `spec:L1211`) và chưa có code |
| 12c | *Khác:* **Agent, trợ lý AI** | • RAG: pgvector HNSW + bge-m3 + reranker; trả lời kèm trích dẫn; chỉ tham vấn (`DT:L454-461`).<br>• Ngày 22/09 trang ghi "Đã kết nối Trung tâm" và có 3 gợi ý tự sinh. Người phân tích không gửi câu hỏi nên chưa kiểm được chất lượng (`DT:L461`, `L994`).<br>• START triage là luật, API tự gắn cờ `RULE_BASED` (`DT:L993`) | • LangGraph; công cụ chỉ đọc số liệu tổng hợp, không trả biển số hay ảnh (`spec:L518`; `review:M-05`).<br>• Báo cáo chỉ phát hành sau `interrupt()`; có chế độ không LLM; có test so khớp số liệu (`spec:L516-526`).<br>• Agent không quyết định vi phạm (`spec:L328`) | **Ngang nhau / không đủ dữ liệu so sánh** | Cả hai giữ Agent ở vai tham vấn. Đối thủ có trang chạy nhưng không có dữ liệu về độ đúng của câu trả lời; bên tôi có tiêu chí test nhưng chưa có code |
| 12d | *Khác:* **Công cụ demo, mô phỏng** | • Simulation Controller: tải clip ≤ 300 MB, gán clip cho camera, trả MJPEG; có API trigger/stop kịch bản (`DT:L301-302`, `L537-543`).<br>• Ngày 22/09: 5/5 kịch bản `video_exists: false`, 0/24 camera có nhịp tim, worker STOPPED/ERROR (`DT:L982-984`) | • MediaMTX phát lặp video qua RTSP (`report:L328`; plan TASK-017).<br>• Máy dự phòng và video ghi sẵn (`review:H-08`).<br>• Kịch bản CP1 phải chạy trọn 2 lần liên tiếp không can thiệp tay (`spec:L1080`) | **Đối thủ vượt trội** (thực thi) | Họ có công cụ chọn clip và kịch bản theo yêu cầu; tôi mới có phát lặp. Nhưng công cụ của họ hỏng đúng lúc được quan sát, đúng loại rủi ro mà `review:H-08` đã tính |
| 12e | *Khác:* **Phạm vi ngoài đề** | • Cổng công dân SOS, VNeID sandbox, điều phối 115, START triage, sóng xanh NTCIP 1202 mô phỏng (`DT:L406-441`).<br>• Phần lớn là sandbox hoặc mô phỏng (`DT:L1064-1068`).<br>• KPI sai vì dữ liệu mẫu (`DT:L991`) | • Không có.<br>• Spec mục 1 đối chiếu 34 mục của đề bài, không mục nào như trên (`spec:L52-87`).<br>• Năng lực 500 giờ đã được ghi là "tham vọng" (`spec:L1199`) | **Đối thủ vượt trội** (độ rộng) | Họ rộng hơn và có câu chuyện B2G. Đây không phải lợi thế theo ràng buộc của tôi: phần lớn là sandbox, và API sự cố làm lộ CCCD, SĐT (`DT:L1021`), trái với nguyên tắc riêng tư trước tiên |

---

## 3. Hai danh sách rút ra

### 3.1 Nên học từ đối thủ

Mức độ hợp được xét theo ba ràng buộc: edge/offline, precision-first, và 5 tuần.

| # | Kỹ thuật của đối thủ | Mức độ hợp | Lý do (đối chiếu docs của tôi) |
|---|---|---|---|
| 1 | **Khử hộp trùng khác lớp** (một xe bị gán 2 lớp), giúp giảm phân mảnh ID từ 1,46 xuống 1,19 (`DT:L224`) | **Hợp** | • Đổi ID và dao động lớp là nguồn báo nhầm đã có mã trong docs của tôi: E1 (`fp:L73`), W4 (`fp:L101`), L2 (`fp:L132`).<br>• Docs hiện chỉ có phương án đổi sang BoT-SORT khi cần (`report:L296`). Khử hộp trùng là bước rẻ hơn, nên thử trước.<br>• Con số 1,46 → 1,19 là đội tự công bố; phải đo lại trên dev |
| 2 | **Fine-tune trên dữ liệu giao thông Việt Nam**: mAP50 từ 0,590 lên 0,892 (`DT:L221`) | **Cần điều chỉnh** | • Docs có cổng quyết định: AP50 xe máy < 0,5 trước 04/10 thì tinh chỉnh (`spec:L198`).<br>• Baseline 0,590 của đối thủ gợi ý cổng này nhiều khả năng sẽ kích hoạt. Nên chuẩn bị nhãn sớm thay vì đợi tới 04/10.<br>• Không chuyển được con số sang bên tôi: khác model (YOLOv8n so với YOLO26n), và tài liệu không nêu nguồn bộ 5.463 ảnh |
| 3 | **Kiểm tra hình học của cấu hình khi lưu**, theo phần Pydantic trong Calibration Studio (`DT:L314-321`) | **Hợp** | • Cấu hình cảnh v2 có nhiều polygon, vạch và cạnh ra (`spec:L647-702`) cho 3 camera (`spec:L563`).<br>• Bộ đọc M1 chỉ kiểm vạch đếm và danh sách lớp (`plan:L739`).<br>• Cấu hình sai hướng hoặc lệch vạch chính là W7 và L6 (`fp:L104`, `L136`) |
| 4 | **Giao diện vẽ làn và vạch trên web**: 6 công cụ, "2 phút mỗi camera" (`DT:L323-332`, `L706`) | **Cần điều chỉnh** | • Spec không có trang này; chỉ có 3 camera; TV3 đã nhiều việc (`timeline:L275`).<br>• Sau ngày đóng băng 11/10, mọi thay đổi cấu hình phải qua CR (`spec:L1260`), nên công cụ vẽ không được phép lách quy tắc đóng băng.<br>• Con số "2 phút" là đội tự công bố |
| 5 | **Simulation Controller + kịch bản demo** (`DT:L301-302`) | **Cần điều chỉnh** | • Khớp với phần demo CP1 "phát lại các ca khó kèm mã lý do" (`spec:L1071`).<br>• Bài học từ chính đối thủ: lúc được quan sát, 5/5 kịch bản thiếu file video và 0/24 camera có nhịp tim (`DT:L982-984`). Nếu làm thì phải đưa việc kiểm tra kịch bản vào tổng duyệt demo (`review:H-08`) |
| 6 | **Ticket ngắn hạn cho kênh realtime**, thay vì để JWT trong URL (`DT:L447`); đối thủ bị nhận xét ở chỗ họ không làm vậy (`DT:L1076`) | **Hợp** | • Kênh SSE `GET /api/v1/stream` của tôi cần JWT từ CP1 (`spec:L860`, `L476`).<br>• EventSource của trình duyệt không gửi được header, nên nếu không dùng ticket thì token sẽ nằm trong URL, đúng lỗi của đối thủ |
| 7 | **Hiện trạng thái "đang gửi bù"** và số bản ghi đang đệm trên UI (`connection_state` có `syncing`, `offline_buffer_count`, `DT:L234`) | **Hợp** | • Health đã có `outbox_depth` (`spec:L754`), nhưng bảng trạng thái thiết bị chưa có trạng thái "đang gửi bù" (`spec:L966-971`).<br>• Demo CP1 có đoạn "ngắt mạng 2 phút rồi đồng bộ bù" (`spec:L1072`); trạng thái này giúp phần demo đó dễ hiểu. Làm tốn ít công |
| 8 | **Trang audit có bộ lọc, xuất CSV và nút kiểm toàn vẹn** (`DT:L404`) | **Hợp** | • Đã có API `GET /api/v1/audit` và công cụ kiểm chuỗi (`spec:L859`, `L492`).<br>• Bảng FR-UI chưa có trang audit cho admin và auditor (`spec:L504-512`) |
| 9 | **Ghi IP thật của người dùng khi chạy sau reverse proxy** (bài học từ lỗi của đối thủ, `DT:L1023`) | **Hợp** | • Live URL của tôi chạy TLS qua reverse proxy (`spec:L1280`; WP-49).<br>• Nhật ký truy cập dự định ghi IP (`arch:L151`). Không xử lý thì sẽ gặp đúng lỗi của đối thủ |
| 10 | **Phím tắt khi duyệt**: A/R/U/Space, ghi chú tối thiểu (`DT:L989`) | **Cần điều chỉnh** | • Bác bỏ ở bước 1 phải kèm mã lý do (`spec:L480`), nên phím tắt phải dẫn tới bước chọn mã.<br>• "Hoàn tác" phải được ghi nhật ký, và chỉ cho phép trước bước 2 (`spec:L486`) |
| 11 | **Tài khoản kiểm thử chọn nhanh cho khách** (`DT:L469`) | **Cần điều chỉnh** | • Mâu thuẫn với NFR-SEC-1 "không còn tài khoản mặc định" (`spec:L640`).<br>• Ở đối thủ, tài khoản demo công khai đọc được credential camera và PII (`DT:L1018`, `L1021`).<br>• Chỉ dùng trên Live URL chạy dữ liệu demo (`spec:L630`) và với quyền tối thiểu |
| 12 | **Đường B: Central Vision Gateway** kéo luồng CCTV về suy luận tập trung (`DT:L162`) | **Không hợp** | • Trái NFR-PRIV-1 "video thô không rời thiết bị" (`spec:L624`).<br>• Ở đối thủ: chỉ đạt 5–6 FPS (`DT:L986`), lộ credential (`DT:L1018`), rủi ro điều khoản sử dụng (`DT:L1079`) |
| 13 | **RAG pgvector + bge-m3 + reranker** (`DT:L454-461`) | **Không hợp** | • Báo cáo đã chốt "Vector DB: Không cần" (`report:L344`).<br>• Nguyên tắc trích dẫn nguồn đã có: báo cáo kèm ID sự kiện nguồn (`report:L468`) |
| 14 | **SOS, 115, VNeID, sóng xanh** (`DT:L406-441`) | **Không hợp** | • Không nằm trong 34 mục đề bài (`spec:L52-87`).<br>• Ở đối thủ phần này phần lớn là sandbox và làm lộ PII (`DT:L1021`).<br>• Năng lực của team đã sát trần (`spec:L1199`) |
| 15 | **Tự gom cụm camera bằng Haversine** (`DT:L307-310`) | **Không hợp** | MVP có 1 tuyến 3 nút, khai báo tay trong `configs/corridors/` (`spec:L977-991`). Gom cụm tự động chỉ có ích khi có hàng trăm camera |

**Đã có tương đương, không cần học thêm:**
- **Băm trước khi che** (`DT:L230`): bên tôi có `parent_hash` trỏ tới bản đầy đủ trên thiết bị (`spec:L379`, `L831`).
- **Ngân sách độ trễ tách tầng, ghi môi trường đo** (`DT:L237`, `L1090`): FR-OPT-1 đo p50/p95 từng tầng (`spec:L575`); protocol mục 13.6 ghi máy và driver (`protocol:L510`).
- **Slide hiện trạng và giới hạn** (`DT:L862`): report mục 20; protocol mục 7.7; checklist CP2 có "mục hạn chế" (`spec:L1105`).
- **Cờ minh bạch trong API** (`synthetic`, `analysis_mode`, `DT:L993`, `L1003`): bên tôi có `source: replay` (`spec:L741`), nhãn "không dùng LLM" (`spec:L526`), `valid = false` (`spec:L250`), cờ `lower_bound` (`spec:L277`).
- **Tự kết nối lại khi mất luồng** (`DT:L272`): FR-CAM-1 AC2 (`spec:L187-191`).

### 3.2 Tôi đang vượt trội

Chỉ liệt kê điểm có lý do kỹ thuật, không liệt kê điểm chỉ vì đối thủ chưa làm. Mọi mục đều **ở mức thiết kế**; cột cuối ghi điều kiện để lợi thế thành thật.

| # | Lợi thế | Bằng chứng vì sao là lợi thế thật | Điều kiện để giữ |
|---|---|---|---|
| 1 | **Ngưỡng luật theo đơn vị vật lý, trên video đã chuẩn hóa 15 FPS** | • Ngưỡng của đối thủ là "8 frame" (`DT:L988`) trên luồng 20 fps (`DT:L271`), trong khi AI của họ chỉ chạy 5–6 FPS (`DT:L986`). Cùng con số 8 nhưng thời gian thật tương ứng thay đổi theo tải.<br>• Bên tôi dùng giây, mét, km/h (`spec:L715-719`) và đóng băng `processing_fps` (`spec:L712`; `review:H-02`). Ngưỡng tái lập được, nên precision đo trên dev còn đúng khi chạy demo | Homography phải được hiệu chuẩn cho cả 3 camera (`spec:L656-658`) |
| 2 | **Danh mục mẫu âm khó có mã, kèm cơ chế tạm dừng khi số ca bất thường** | • Hàng đợi của đối thủ có 179 cảnh báo, chưa ai duyệt, phần lớn từ một camera, và 438/473 track không rơi vào làn đã vẽ (`DT:L987-990`).<br>• Không kết luận được các cảnh báo đó sai. Nhưng đây đúng mẫu hình mà W7 ("tỉ lệ ca rất cao", `fp:L104`) và quy tắc "số ca tăng đột biến thì tạm dừng và hỏi điều hành viên" (C4, W6, L8: `fp:L56`, `L103`, `L138`) được thiết kế để chặn | Mã lý do phải được xuất thật (`rejection_summary`, `spec:L753`), và phải có số ablation (`spec:L326`) |
| 3 | **Đèn UNKNOWN chặn gắn cờ, có tiêu chí kiểm** | • HUD của đối thủ hiện "đèn: UNKNOWN" (`DT:L986`; `DT-img:inside/02-operator-phan-tich-ai.jpg`).<br>• Luật của họ có chặn khi đèn UNKNOWN hay không: không tìm thấy.<br>• Bên tôi: FR-LGT-1 AC2 (`spec:L312`), điều kiện 1 của luật vượt đèn đỏ (`fp:L21`), và chu kỳ có UNKNOWN bị đánh dấu `valid = false` (`spec:L250`) | Có test cho AC2 |
| 4 | **Giao thức đo tách tập test, có cỡ mẫu tối thiểu** | • Mục tiêu precision ≥ 98% của đối thủ chưa có số (`DT:L866`); mAP của họ chỉ đo trên val (`DT:L221`).<br>• Protocol của tôi chỉ ra: 20 cảnh báo đúng hết thì cận dưới Wilson vẫn chỉ 83,9%, và cần ≥ 59 cảnh báo không sai cái nào mới khẳng định được ≥ 95% (`protocol:L23-24`). Một con số precision không kèm n thì không bảo vệ được. Spec cũng tự sửa câu "≥ 95%" trong README của chính team (`spec:L1272`) | Script đánh giá phải thật sự có trong repo (G4); tập test phải có ≥ 30 cảnh báo mỗi loại |
| 5 | **Duyệt 2 bước, tách vai, tối thiểu dữ liệu** | • UI của đối thủ ghi Operator được xem ảnh gốc (`DT:L1022`), mâu thuẫn slide của họ.<br>• Bên tôi: người sơ duyệt chỉ thấy bản đã che; CSGT chỉ mở bản CSGT sau bước 1, có test (`spec:L486-488`). Ít người thấy biển số hơn, khớp với Luật 91/2025 (`report:L518`) | Kiểm quyền ở backend, có test 403 |
| 6 | **Làm mờ có đo tỉ lệ lọt, có detector biển số** | • Đối thủ che theo heuristic 25% dưới crop xe, chưa đo (`DT:L868`); người phân tích nêu rủi ro mặt người đi xe máy và biển số nằm lệch vùng sẽ lọt (`DT:L1063`).<br>• Bên tôi có mục tiêu ≤ 1% kèm Wilson và liệt kê mọi ca lọt (`spec:L402-405`) | Phương án dự phòng "che nửa dưới bbox" cũng phải qua phép đo này |
| 7 | **Chữ ký thiết bị, kèm neo chuỗi nhật ký ra ngoài DB** | • Chuỗi băm của đối thủ nằm trong chính DB của họ (`DT:L402`), nên người kiểm soát DB dựng lại được cả chuỗi (`review:L-02`).<br>• Bên tôi ký Ed25519 bằng khóa thiết bị (`spec:L378`, `L835`): chứng minh được nguồn gốc, không chỉ chứng minh không bị đổi. Mã băm đầu chuỗi commit ra git hằng ngày | Khóa thiết bị không commit vào repo (DoD 6, `spec:L1150`) |
| 8 | **Một hợp đồng sự kiện có phiên bản, khóa chống trùng rõ** | • Đối thủ tự nhận 2 hợp đồng chưa hợp nhất (`DT:L870`); khóa chống trùng "chưa rõ" (`DT:L1070`); mới thử với 15 bản ghi (`DT:L702`).<br>• Bên tôi: vỏ chung + quy tắc phiên bản (`spec:L739-742`, `L807-809`); `event_id` UNIQUE, phát hiện lỗ hổng `seq` (`report:L490-493`); AC ngắt mạng 10 phút với nhiều loại sự kiện (`spec:L430`) | TASK-008/009/011 phải được merge thật vào repo |
| 9 | **Quy định bảo mật chặn đúng các lỗi đã quan sát ở đối thủ** | • Đối thủ: lộ URL kèm user/pass (`DT:L1018`); lộ CCCD, SĐT cho Operator (`DT:L1021`); JWT trong query string (`DT:L1076`).<br>• Bên tôi: bí mật chỉ qua biến môi trường (`spec:L638`); lọc trường theo vai (`spec:L780`); công cụ Agent không trả biển số (`review:M-05`); test 401/403 cho mọi endpoint (`spec:L475`) | Mới là quy định; cần test và checklist CP2 (`spec:L1099`) để thành thật |
| 10 | **Quản trị phạm vi cho 5 tuần** | • Lúc quan sát, đối thủ có phần mô phỏng không chạy, 5/5 kịch bản thiếu video, KPI 6168,5 phút, hiển thị "64400%" (`DT:L1025`, `L984`, `L991`, `L987`): dấu hiệu độ rộng vượt độ ổn định.<br>• Bên tôi có thứ tự cắt, danh sách không bao giờ cắt, và điểm kích hoạt (`spec:L1215-1241`); DoD bắt chạy được trong môi trường tích hợp (`spec:L1149`); demo phải chạy trọn 2 lần (`spec:L1080`) | **Phạm vi của tôi cũng lớn**: 65 điểm, khoảng 500 giờ, tự ghi là "tham vọng" (`spec:L1199`). Lợi thế này chỉ thật nếu các điểm kích hoạt cắt được áp dụng đúng hạn |

---

## 4. Giới hạn của phân tích

**G1 — Nguồn #1 không phải repo mã nguồn.** Thư mục đối thủ chỉ có một file phân tích do người khác viết và ảnh chụp. Không có dòng code backend, edge node, model hay luật nào (`DT:L93`). Mọi mục ghi "code" ở trên thật ra là một trong ba loại bằng chứng:

| Loại bằng chứng | Những gì chỉ đánh giá được theo cách này |
|---|---|
| **Lời đội tự công bố** (slide, video, edufun); không kiểm chứng được | mAP 0,892; FPS trên MX150; ONNX 12,85 MB; offline 15/15; số test 643/933; băng thông > 95%; máy trạng thái đèn vàng; băm trước khi che; stack RAG; khử hộp trùng khác lớp |
| **Hành vi quan sát trên demo sống** (API trả về, UI); thấy được kết quả, không thấy code | 24 camera; hàng đợi 179 vi phạm; ngưỡng "8 frame"; lộ credential; lộ PII; IP trong audit; 5–6 FPS; đèn UNKNOWN; gán làn `null` |
| **Bundle front-end đã beautify** | bề mặt API; schema; các trường hiệu chuẩn; xác thực kênh realtime; ma trận quyền theo route; ngưỡng ùn tắc trong mock |

**G2 — Chưa kiểm hết ảnh.** Tôi dựa vào phần chép tay của người phân tích và chỉ kiểm chéo 3/33 ảnh. Ba ảnh đó khớp văn bản.

**G3 — Trạng thái đối thủ là ảnh chụp tại một thời điểm** (khoảng 13:07 ngày 22/09, `DT:L957`). Các lỗi quan sát được có thể đã được sửa sau đó.

**G4 — Bên tôi chỉ có tài liệu, và có một chỗ tài liệu nói quá.**
- Docs ghi chưa có code hệ thống (`report:L14`, `protocol:L4`).
- Docs cũng ghi `scripts/evaluate.py` và `tests/test_evaluate.py` "đã có" (`protocol:L4`, `report:L14`). Kiểm tra repo ngày 22/09 cho thấy hai file này **không có trong cây thư mục và chưa từng được commit**: `git log --all` cho hai đường dẫn này không trả kết quả; chỉ còn file `.pyc` trong `tests/__pycache__/`.
- 62 test của plan M1 pass trên một bản sao tạm, không phải trong repo (`plan:L23-26`).

**G5 — Docs của tôi còn mâu thuẫn nội bộ.** Tôi lấy spec làm nguồn sự thật (`spec:L16-19`). Hai file sơ đồ còn các câu mà spec mục 13 đã đánh dấu phải sửa:

| File | Đang ghi | Spec quy định |
|---|---|---|
| `tq:L182` | "tiết kiệm > 99,9%" băng thông | chỉ báo số đo thật (`spec:L1273`) |
| `tq:L214` | "> 7 ngày" | thử thật ≥ 24 giờ (`spec:L1279`) |
| `arch:L175` | "TLS 1.3" | TLS từ CP2 qua reverse proxy (`spec:L1280`) |
| `arch:L39`, `tq:L196` | "clip 4s" | chuỗi JPEG từ t − 3 s tới t + 2 s (`spec:L376`) |

Giám khảo đọc hai file này sẽ thấy khác spec.

**G6 — So sánh về thực thi vốn không cân.** Đối thủ đã qua Demo Day (`DT:L5`), còn bên tôi mới ở tuần 1 (M1 là 27/09, `timeline:L48`). Các dòng "Đối thủ vượt trội (thực thi)" phản ánh độ chênh giai đoạn, không phải chất lượng thiết kế. Ngược lại, các dòng "Tôi vượt trội (thiết kế)" cũng chưa chứng minh được là làm ra được.

**G7 — Không so số đo.** Bên tôi chưa có mAP, precision hay FPS đầu–cuối, nên bảng không so con số với con số. Số 28 FPS CPU (`spec:L65`) chỉ đo detect + track, chưa có luật và che.

---

## 5. Đã áp dụng vào docs (22/09, là đề xuất, duyệt tại M0)

Đã sửa:
- **spec** (nguồn sự thật) và **timeline**: chỉ thêm tiêu chí nghiệm thu, không đổi ngày nào;
- **báo cáo kỹ thuật** lên v0.5;
- **protocol** mục 2.4: chốt model trước, chỉnh ngưỡng sau;
- `architecture_diagram.md`: cho khớp spec, gồm cả các lỗi G5; đây là file sơ đồ duy nhất (file nộp bài);
- `Trucquanhoadocs.md` **đã xóa**: bản đồ tài liệu chuyển thành bảng trong `README.md`, sơ đồ gộp vào `architecture_diagram.md`;
- `README.md` và `CLAUDE.md`: sửa các câu sai mà spec mục 13 đã đánh dấu.

Không đổi: phân vai và ngày trong timeline. PO sẽ chia lại việc và chốt ngày sau.

| # (mục 3.1) | Kỹ thuật | Đã đưa vào | Ghi chú |
|---|---|---|---|
| 1 | Khử hộp trùng khác lớp | spec FR-DET-2 (AC2); timeline WP-38 | Đo trước, chỉ bật bộ lọc khi số đo cho thấy cần. Ưu tiên `agnostic_nms` có sẵn của Ultralytics |
| 2 | Fine-tune sớm | spec FR-DET-1; **Q11** | **Chờ PO.** Cổng quyết định là 04/10, nhưng WP-38 hạn 06/10. Nguồn dữ liệu tinh chỉnh chưa có |
| 3 | Kiểm hình học của cấu hình | spec mục 6.1; timeline WP-10 | Kiểm bằng Pydantic khi nạp; có ảnh overlay đính kèm PR |
| 4 | Vẽ cấu hình trên web | spec FR-UI-9 (COULD) | Chỉ có 3 camera; sau 11/10 đổi cấu hình vẫn phải qua CR |
| 5 | Simulation Controller | spec mục 8.1; timeline CP1 | Bộ clip lấy từ dev (không bao giờ từ test), có SHA-256, kiểm trước mỗi lần demo |
| 6 | Vé ngắn hạn cho kênh realtime | spec mục 6.5, FR-AUTH-1, FR-UI-2; timeline WP-13, WP-14 | Vé dùng một lần, sống 30 giây; nối lại với thời gian chờ tăng dần từ 1 tới 30 giây |
| 7 | Trạng thái "đang gửi bù" | spec mục 6.7, FR-DEV-1 AC4; timeline WP-40 | Hiển thị tiến độ bằng mốc `captured_at`, không hiện số lượng, vì `health` cũng đi qua outbox |
| 8 | Trang nhật ký | spec FR-UI-8; timeline WP-19 | Cỡ nhóm giữ nguyên 3; PO xác nhận tại M0 |
| 9 | IP thật sau reverse proxy | spec NFR-SEC-1, checklist CP2; timeline WP-49 | Dùng tham số `--forwarded-allow-ips` có sẵn của Uvicorn |
| 10 | Phím tắt khi duyệt | spec FR-UI-2 | **Không lấy nút hoàn tác.** Xác nhận nhầm ở bước 1 vẫn còn bước 2 của CSGT chặn lại. Thêm hoàn tác nghĩa là thêm chuyển trạng thái và dòng nhật ký, chưa đáng làm trong 5 tuần |
| 11 | Tài khoản kiểm thử | **Q10** | **Chờ PO**: mâu thuẫn với NFR-SEC-1 |
| 12–15 | Đường B, RAG, SOS, gom cụm Haversine | Không áp dụng | Lý do ở mục 3.1 |

**Tình trạng các giới hạn ở mục 4:**
- G4 **vẫn đúng**: nhóm chưa viết script nào. Ngày 22/09 PO chốt không đưa bản `evaluate.py` từ lần chạy thử plan M1 vào repo; script được viết mới ở TASK-019 (Khánh, 27/09). Các chỗ ghi "đã có" trong docs đã sửa thành "chưa viết".
- G5 **đã sửa**, ngày 22/09: băng thông, 7 ngày, TLS 1.3, clip 4s; thêm cả "xuất biên bản phạt" (hệ thống chỉ tạo ứng viên) và MQTT (chỉ là kênh điều khiển).
