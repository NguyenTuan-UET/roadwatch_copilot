# Đặc tả Hệ thống (Spec) — Phần 1: Tổng quan, Phạm vi & Vai trò
> Nguồn: Tách từ trafficeye-spec.md (Mục 0, 1, 2, 3) tuân thủ SDLC Bước 1: Discovery & Requirements
> Quy tắc ngữ cảnh: 150 - 250 dòng/file.

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
> - Bổ sung ngày 22/09, **đề xuất, duyệt tại M0**. Các mục học từ đối thủ cùng đề (`docs/report/so-sanh-doi-thu.md`, mục 3.1 và 5):
>   - FR-DET-2: đo trước, rồi mới khử hộp trùng khác lớp;
>   - mục 6.1: kiểm tra hình học khi nạp cấu hình cảnh, kèm ảnh overlay để soát; giao diện vẽ trên web ở mức COULD (FR-UI-9);
>   - mục 6.5 và FR-AUTH-1: kênh SSE xác thực bằng vé ngắn hạn, không để JWT trong URL;
>   - mục 6.7 và FR-DEV-1 AC4: trạng thái "đang gửi bù";
>   - FR-UI-2: duyệt bằng bàn phím; FR-UI-8: trang nhật ký (cỡ nhóm giữ nguyên 3, vì trang chỉ đọc trên API đã có);
>   - NFR-SEC-1: nhật ký ghi IP thật khi chạy sau reverse proxy;
>   - mục 8.1: bộ clip kịch bản và bước kiểm tra trước mỗi lần demo;
>   - mục 14: thêm Q10 (giám khảo đăng nhập Live URL thế nào) và Q11 (cổng tinh chỉnh 04/10 đang sớm hơn hạn WP-38 là 06/10);
>   - FR-HITL-1 AC3 và FR-UI-2: nối lại SSE thì tải lại hàng đợi, để không bỏ sót ứng viên đến trong lúc mất mạng;
>   - FR-DET-1: chốt model trước khi chỉnh ngưỡng (protocol mục 2.4).
>
> **Vai trò của tài liệu:** nguồn sự thật duy nhất về *yêu cầu, tiêu chí nghiệm thu và hợp đồng giao tiếp*.
> - Báo cáo kỹ thuật (`docs/report/trafficeye-edge-report.md`) giải thích *vì sao chọn*.
> - Spec quy định *làm gì* và *thế nào là xong*.
> - Khi PRD Gate 1, README hay báo cáo mâu thuẫn với spec thì theo spec. Danh sách mâu thuẫn ở mục 13.
>
> **Căn cứ:** đề bài chính thức (PO gửi ngày 21/09); báo cáo v0.4; design review (22 phát hiện, đã duyệt); `docs/eval/protocol.md`; `docs/spec/false-positives.md`.

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
| Dashboard, bản đồ, trang xác minh, trang nhật ký | FR-UI-1…FR-UI-4, FR-UI-8 | MUST | 3 | CP1 |
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

**COULD** (không tính vào %): FR-VIO-ST (dừng, đỗ sai); FR-AGT-3 (hỏi đáp số liệu); FR-DEN-3 (hồ sơ theo khung giờ); FR-INT-3, FR-INT-4, FR-INT-5; FR-UI-9 (vẽ cấu hình cảnh trên web). FR-MC-2 đã gộp vào FR-COR-2.

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

