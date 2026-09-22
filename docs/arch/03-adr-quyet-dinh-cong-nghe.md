# Kiến trúc Hệ thống — Phần 3: Quyết Định Công Nghệ (ADR) & Đánh Đổi (Trade-offs)
> Nguồn: Tách từ Báo cáo kỹ thuật TrafficEye Edge (Mục 6, 7, 21) tuân thủ SDLC Bước 2: ADRs.

## 6. So sánh công nghệ và quyết định

Mỗi quyết định đi theo trình tự: yêu cầu → các lựa chọn → đánh đổi → quyết định → lý do.

### 6.1 Thiết bị edge

**Yêu cầu:**
- suy luận tại chỗ ít nhất 15 FPS mỗi luồng, để tracking xe máy ổn định;
- còn dư tài nguyên cho ảnh độ phân giải cao;
- bộ công cụ trưởng thành, vì team chưa làm edge bao giờ.

| | Jetson Orin Nano Super 8GB | Pi 5 + AI HAT+ 26 TOPS | RK3588 | Mini PC x86 + OpenVINO |
|---|---|---|---|---|
| Giá | **399 USD**, tăng từ 249 USD ngày 22/07/2026 [S1] | Pi 5 4GB ~110 USD (sau 3 đợt tăng giá) + HAT 110 USD [S8] | Rẻ nhất [Cần kiểm chứng] | Chưa khảo sát |
| Hiệu năng đã kiểm chứng | YOLO26n TensorRT FP16: 4,57 ms/ảnh ở 640, chưa tính tiền/hậu xử lý [S2] | Chủ yếu là số của các model có sẵn từ Hailo | NPU ~6 TOPS [Cần kiểm chứng] | Chưa có số |
| Chạy model | GPU + TensorRT; gần như model nào xuất ra ONNX cũng chạy | Phải compile bằng Hailo Dataflow Compiler | Toolkit RKNN, quantize dễ tụt độ chính xác | OpenVINO |
| Video | Có giải mã phần cứng, **không có mã hóa phần cứng** (DeepStream 9.1 có tùy chọn dùng encoder phần mềm cho Orin Nano) [S7] | Chỉ giải mã phần cứng H.265 [Cần kiểm chứng] | Giải mã phần cứng H.264/H.265 | Quick Sync |

**Quyết định:** Jetson Orin Nano Super là **thiết bị mục tiêu**; MVP **mô phỏng trên PC** [Đã chốt việc mô phỏng; Đề xuất về thiết bị].

**Lý do:** TensorRT và DeepStream 9.1 hỗ trợ cả Jetson Orin lẫn máy x86 có GPU rời [S7]. Vì vậy cùng một pipeline chạy được trên PC lúc phát triển và trên Jetson khi triển khai.

### 6.2 Khung pipeline video: tự viết bằng Python/OpenCV hay dùng DeepStream?

**Yêu cầu:**
- MVP: xong trong 5 tuần với team mới.
- Production: nhiều luồng trên một thiết bị, giải mã bằng phần cứng.

**Ba lựa chọn:**
- **(a)** Python + OpenCV/FFmpeg + Ultralytics, chạy bằng TensorRT hoặc ONNX.
- **(b)** Tự viết pipeline GStreamer.
- **(c)** NVIDIA DeepStream 9.1, phát hành 14/07/2026: có nvinfer, nvtracker, giải mã phần cứng, Python bindings cài bằng pip trên cả x86 và Jetson [S7].

**Đánh đổi:**
- **(a)** cho kết quả nhanh nhất, dễ debug, dễ viết bộ quy tắc. Đổi lại, giải mã và tiền xử lý tốn CPU, khó mở rộng lên nhiều luồng.
- **(c)** cho hiệu năng tốt nhất trên Jetson (không chép dữ liệu qua lại, chạy batch). Đổi lại, phải học nhiều, debug khó, và metadata phải đi qua pyds. YOLO và RF-DETR đều đã có hướng dẫn chạy trong DeepStream [S6].
- **(b)** linh hoạt nhưng phải tự làm nhiều thứ.

**Quyết định:** MVP dùng **(a)**, đặt sau các interface rõ ràng (`FrameSource`, `Detector`, `Tracker`). **DeepStream là hướng ADVANCED** khi chạy nhiều luồng trên Jetson thật [Đề xuất].

**Lý do:** rủi ro lớn nhất của MVP là thời gian và độ ổn định khi demo, không phải thông lượng. Với 1–2 luồng mô phỏng, (a) là đủ. Các interface cho phép đổi phần xử lý video sau này mà giữ nguyên bộ quy tắc.

→ Trả lời câu hỏi trong `role.md`: **nên dùng DeepStream cho production nhiều luồng trên Jetson, không nên dùng cho MVP 5 tuần.**

### 6.3 Detector

**Yêu cầu:**
- xe máy dày đặc, vật thể nhỏ;
- chạy thời gian thực trên edge;
- xuất được sang TensorRT hoặc ONNX;
- giấy phép phù hợp.

| Lựa chọn | Điểm mạnh | Điểm yếu |
|---|---|---|
| **YOLO26** (Ultralytics, phát hành 01/2026) [S3] | Hệ sinh thái mạnh nhất: train, xuất TensorRT, tracking tích hợp sẵn [S4], có benchmark trên Jetson [S2] | Giấy phép **AGPL-3.0 hoặc Enterprise**: phải công khai mã nguồn phần kết nối với model; dùng thương mại thì phải mua license [S3] |
| YOLO27 | Đã công bố, bản lớn vượt 60 mAP COCO [S3] | **Chưa phát hành trọng số** [S3] |
| **RF-DETR** (Roboflow, ICLR 2026) | Apache 2.0 cho các bản mở; RF-DETR-L đạt 56,5 AP, 6,8 ms trên T4 với TensorRT FP16 [S6] | Chưa có benchmark trên Orin Nano trong đợt kiểm chứng này |

**Quyết định** [Đề xuất]:
- MVP dùng **YOLO26n hoặc YOLO26s** qua Ultralytics, bắt đầu từ trọng số COCO.
- Chỉ fine-tune bằng dữ liệu Việt Nam khi số đo cho thấy cần.
- Ưu tiên **FP16** hơn INT8 nếu đủ nhanh. Trên Orin Nano Super, INT8 làm mAP COCO của YOLO26n giảm từ 0,480 xuống 0,449 [S2], ngược với ưu tiên precision.
- **Chốt model trước, chỉnh ngưỡng sau** (22/09). Ngưỡng luật được chọn trên box và track của một model cụ thể. Nếu cổng tinh chỉnh (spec FR-DET-1) kích hoạt thì phải train xong, chạy lại cache và chỉnh lại toàn bộ ngưỡng trước ngày đóng băng (protocol mục 2.4). Đây là chuỗi tuần tự; thêm người không làm nó ngắn lại. Đối thủ cùng đề báo mAP50 tăng từ 0,590 lên 0,892 sau khi tinh chỉnh trên dữ liệu Việt Nam (YOLOv8n, tự công bố), nên khả năng cổng kích hoạt là có thật.

**Hướng thương mại:** đánh giá RF-DETR (Apache 2.0) hoặc mua license Enterprise.

### 6.4 Tracker

**Yêu cầu:** ít đổi ID (E1 là một nguồn báo nhầm), nhẹ, dễ tích hợp.

| Tracker | MOTA | IDF1 | HOTA | Ghi chú |
|---|---|---|---|---|
| ByteTrack | 80,3 | 77,3 | 63,1 | Nhẹ, có sẵn trong Ultralytics (`bytetrack.yaml`) [S4] |
| OC-SORT | 78,0 | 77,5 | 63,2 | Tốt khi xe bị che khuất |
| BoT-SORT | 80,5 | 80,2 | 65,0 | Có ReID tùy chọn, tốn tính toán hơn; tracker mặc định của Ultralytics (`botsort.yaml`) [S4] |

Số liệu trên là MOT17 [S5]. MOT17 là bộ **người đi bộ**, không phải giao thông Việt Nam.

**Quyết định:** MVP dùng **ByteTrack**. Chuyển sang BoT-SORT nếu phần tách nguồn lỗi (protocol, mục 6) cho thấy đổi ID là nguồn báo nhầm hoặc cảnh báo trùng lớn nhất [Đề xuất].

**Lý do:** chọn theo số đo trên dữ liệu của chính team, không theo bảng xếp hạng người đi bộ.

**Trước khi đổi tracker** (22/09): đo số box trùng khác lớp trên tập khung dev, tức một xe bị gán thành hai lớp. Nếu con số đáng kể thì khử hộp trùng trước, vì đây là cách rẻ hơn để giảm đổi ID (spec FR-DET-2). Đối thủ báo cách này giảm phân mảnh ID từ 1,46 xuống 1,19 (họ tự công bố).

### 6.5 Trạng thái đèn

**Ba lựa chọn:**
- **(a)** ROI cố định + phân loại màu (HSV hoặc CNN nhỏ) + máy trạng thái;
- **(b)** detector đèn giao thông tổng quát;
- **(c)** lấy tín hiệu trực tiếp từ bộ điều khiển đèn.

**Quyết định:** dùng (a) cho MVP; (c) là mục tiêu khi lên production [Đề xuất].

**Lý do:**
- Camera đứng yên nên vị trí đèn cố định, không cần detector.
- Máy trạng thái có thêm các trạng thái KHÔNG RÕ, NHẤP NHÁY, TẮT, và các trạng thái này chặn gắn cờ (nhóm D1–D6).
- (c) loại gần hết lỗi nhóm D, nhưng cần tích hợp với hạ tầng mà team không có.

### 6.6 Truyền thông

**Đã chốt sau design review (H-01):** MVP dùng **HTTPS + outbox** cho mọi luồng từ edge về trung tâm; MQTT chuyển sang lộ trình. Lý do: chỉ có 1 edge node, và client MQTT chỉ đệm tin trong RAM nên dù dùng MQTT vẫn phải có outbox. Tức là MQTT thêm broker, ACL và dịch vụ ingest mà không bớt được việc nào.

**Bổ sung ngày 21/09 (Q2, đối chiếu với đề bài):** ở CP2, MQTT vào hệ thống nhưng chỉ làm **kênh điều khiển**. Dữ liệu vẫn đi HTTPS + outbox như trên.
- MQTT có hai việc:
  - Last Will báo thiết bị rớt kết nối trong ≤ 10 giây;
  - thông báo "trạng thái mong muốn vừa đổi", để edge hỏi lại ngay.
- Lý do chọn cách này: MQTT làm tốt đúng hai việc mà hỏi định kỳ làm kém, còn độ bền dữ liệu vẫn nằm ở outbox.
- Hỏi định kỳ có từ CP1 và luôn chạy. Mất broker thì hệ thống chỉ chậm lại.
- Hợp đồng chi tiết ở spec mục 6.7.

| Luồng | MVP | Production | Lý do |
|---|---|---|---|
| Camera → edge | RTSP. Khi mô phỏng, MediaMTX phát lặp video mẫu (`ffmpeg -re -stream_loop -1 ... -f rtsp`) [S17] | RTSP từ camera thật (bắt buộc là video liên tục) | Chuẩn của camera IP |
| Edge → trung tâm: sự kiện, số đếm, health | HTTPS POST từ outbox SQLite, thử lại theo backoff, chống trùng bằng `event_id` | MQTT 5, QoS 1, giữ phiên (Session Expiry), qua TLS [S11] | MVP: một giao thức, dễ test. Production: nhiều thiết bị, đẩy dữ liệu chủ động |
| Edge → trung tâm: gói bằng chứng (cỡ MB) | HTTPS upload, kiểm tra mã băm | Như MVP | Dữ liệu lớn cần xác thực |
| Trung tâm → edge: cấu hình, chế độ điều khiển tay | CP1: edge tự hỏi định kỳ (polling) mỗi 10 giây. CP2: thêm thông báo qua MQTT, nội dung vẫn lấy qua HTTPS | Như CP2, thêm mTLS cho MQTT | Không cần mở cổng vào thiết bị |
| Trung tâm → trình duyệt | SSE, xác thực bằng vé ngắn hạn dùng một lần (spec 6.5); không để JWT trong URL | Như MVP | Cảnh báo hiện ngay trên dashboard. Trình duyệt không gửi được header khi mở SSE, nên cần vé |

**Không dùng Kafka hay NATS:** chỉ cân nhắc khi lên hàng trăm camera [Đề xuất].

### 6.7 Lưu trữ

| Loại dữ liệu | MVP | Production |
|---|---|---|
| Giao dịch: camera, vi phạm, lượt duyệt, người dùng, nhật ký | PostgreSQL | PostgreSQL |
| Chuỗi thời gian: số đếm theo phút | PostgreSQL, bảng thường | TimescaleDB. Lõi là Apache 2.0; continuous aggregates và retention theo Timescale License, miễn phí khi tự host [S13] |
| Bằng chứng (ảnh, clip) | Thư mục trên đĩa + đường dẫn lưu trong DB | Kho tương thích S3. **Không dùng MinIO bản cộng đồng**: đã ngừng phát hành bản build từ 10/2025 và bị archive từ 04/2026 [S12] |
| Hàng đợi trên edge | SQLite | SQLite |
| Vector DB | Không cần | Chỉ khi thật sự có nhu cầu tìm kiếm ngữ nghĩa |

### 6.8 Các lựa chọn còn lại

| Thành phần | Chọn | Lý do | Hướng nâng cấp |
|---|---|---|---|
| Backend | FastAPI (có sẵn trong template) | Team đã quen, async, tự sinh OpenAPI | Tách service khi tải tăng |
| Frontend | Next.js + bản đồ (Leaflet hoặc MapLibre) | Có sẵn trong template | — |
| Agent | LangGraph: `interrupt()` + `Command(resume=...)`, bắt buộc có checkpointer [S14] | Có sẵn trong template, hỗ trợ bước người duyệt | Thêm công cụ đọc nhiều nguồn |
| Triển khai | Docker Compose; trung tâm deploy lên cloud trước CP2 (Live URL) [Đã chốt]; trên Jetson dùng NVIDIA container runtime | Một lệnh cho mỗi vai; edge ở máy local nối lên trung tâm trên cloud | K3s hoặc công cụ quản lý đội thiết bị |
| Giám sát | Endpoint `/metrics` + Prometheus/Grafana; jetson-stats (jtop) khi chạy thiết bị thật [S15] | Chuẩn phổ biến | Cảnh báo tự động |
| Ký model và container | cosign `sign-blob` / `verify-blob`, có chế độ keyless [S16] | Chuẩn mở | Registry + triển khai dần |

---

## 7. Stack đề xuất

| Lớp | MVP | Khi lên production |
|---|---|---|
| Camera | Video mẫu → MediaMTX (RTSP) | Camera IP thật (RTSP) |
| Edge: pipeline | Python 3.11, OpenCV/FFmpeg, Ultralytics YOLO26 + ByteTrack, TensorRT hoặc ONNX Runtime | DeepStream 9.1 trên Jetson Orin |
| Edge: quy tắc và bằng chứng | Quy tắc tự viết, SQLite outbox, `cryptography` (Ed25519) | Khóa trong secure element |
| Truyền thông | Dữ liệu: HTTPS + outbox SQLite [Đã chốt]. Điều khiển: hỏi định kỳ từ CP1; thêm MQTT (Mosquitto) từ CP2 [Đã chốt] | Dữ liệu cũng qua MQTT 5 + mTLS khi có nhiều thiết bị |
| Trung tâm | FastAPI, PostgreSQL, bằng chứng lưu trên đĩa (mã hóa khi lưu) | TimescaleDB, kho S3 |
| Giao diện | Next.js | + SSO |
| Agent | LangGraph, công cụ chỉ đọc | Thêm nhiều nguồn dữ liệu |
| DevOps | Docker Compose, GitHub Actions (đã có CI: ruff + pytest) | K3s, OTA có ký |
| Đánh giá | `scripts/evaluate.py` theo `docs/eval/protocol.md` | Đo định kỳ, theo dõi drift |

---



## 21. Quyết định kiến trúc cuối cùng

**Đã chốt:**
- Mô phỏng camera bằng video mẫu, mô phỏng thiết bị edge.
- Người dùng: điều hành viên và CSGT (vẫn là giả định, cần phỏng vấn).
- Bằng chứng tối thiểu, phân quyền theo vai.
- Chuỗi giám sát bằng chứng.
- Giao thức đánh giá và script đánh giá.
- Khi tích hợp, camera phải cấp video liên tục; không dùng ảnh tĩnh.
- MVP có 1 tuyến gồm 3 nút giao liên tiếp (FR-MC-1 MUST). Phát triển bằng video quay sẵn trước (cả 3 nút cùng lúc), rồi mới tích hợp camera thật. Video phải bao phủ đủ các pha đèn và nhiều tình huống.
- Khu dân cư nằm trong phạm vi nhưng không phải trọng tâm MVP. MVP tập trung vào nút giao và tuyến đường có đèn, làn rõ ràng.
- Đóng băng cấu hình ngày 11/10 (cả ngưỡng luật vi phạm và ngưỡng phân tích tuyến). Sau mốc này chỉ đổi kiến trúc hoặc công nghệ lớn khi có lý do kỹ thuật rõ ràng.
- Bản cho CSGT: xe vi phạm hiện rõ, các xe khác được che biển số và khuôn mặt. AI chỉ tạo ứng viên; người xác nhận thì vi phạm mới được ghi nhận chính thức.

**Đã chốt sau design review** (PO duyệt ngày 21/09, xem phụ lục A):
- Jetson Orin Nano Super là thiết bị mục tiêu.
- Pipeline Python cho MVP; DeepStream để sau.
- YOLO26 (FP16) + ByteTrack.
- Trạng thái đèn: ROI + máy trạng thái.
- **HTTPS + outbox** cho mọi luồng dữ liệu edge → trung tâm (H-01). Q2 bổ sung MQTT làm kênh điều khiển từ CP2.
- Bản CSGT: mã hóa khi lưu + RBAC + nhật ký; mã hóa đầu–cuối để vào lộ trình (H-03).
- PostgreSQL + thư mục bằng chứng.
- FastAPI + Next.js + LangGraph (công cụ chỉ đọc, chỉ trả dữ liệu tổng hợp).
- Docker Compose; edge có thể chạy trực tiếp bằng conda nếu dùng GPU trong Docker trên Windows gặp khó.
- Video chuẩn hóa 15 FPS cố định; ước lượng điểm đầu xe; dùng vùng giao lộ thay cho vạch xác nhận.
- Phân vai: detector biển số chuyển sang TV4, đo hiệu năng và băng thông chuyển sang TV2 (H-06).

**Đã chốt ngày 21/09, sau khi đối chiếu với đề bài và chốt Q1–Q9** (spec mục 14):
- Q1: MUST gồm vượt đèn đỏ, đi ngược chiều, sai làn. Dừng, đỗ sai là COULD.
- Q2: dữ liệu vẫn đi HTTPS + outbox. Ở CP2 thêm MQTT làm kênh điều khiển: Last Will, thông báo trạng thái mong muốn. Hỏi định kỳ có từ CP1 và luôn chạy.
- Q3: trung tâm deploy lên cloud trước CP2 (Live URL); edge chạy local.
- Q4: CP1 ngày thứ Tư 14/10; CP2 ngày thứ Sáu 23/10.
- Q6: Mức "chỉnh đèn": chỉ phân tích ùn tắc; không tự tính hay tự đổi thời gian đèn. Webster + SUMO để ở hướng mở rộng.
- Q7: Dữ liệu cho phân tích tuyến: quay thật 3 nút liên tiếp, cùng lúc, bằng 3 camera của FR-MC-1.
- Q8: Làm full cả 3 vấn đề: 3 loại vi phạm của đề; sai làn đủ 3 kiểu (LN-a, LN-b, LN-c), đều MUST. Dừng/đỗ sai vẫn là COULD.
- Q9: Phân tích tuyến vào checkpoint nào: xong trước CP1; đánh giá trên tập test ở CP2. Bù tải: FR-AGT-3 xuống COULD, FR-EXP-1 sang CP2, WP-40 sang TV4. Cỡ việc CP1 = 53/65 ≈ 82%.

**Đề xuất theo đề bài chính thức** (spec v1.0, toàn văn duyệt tại M0 ngày 24/09):
- Thêm luật đi ngược chiều và luật làn (LN-a, LN-b, LN-c) trên cùng mô hình cảnh v2 và cùng giao diện luật dạng plugin.
- Nâng mật độ/ùn tắc, phân tích tuyến 3 nút, 3 camera và Agent báo cáo ca trực lên MUST.
- Thêm lớp ngữ cảnh tất định có mã lý do.
- Thêm OCR chỉ cho xe vi phạm, đo mAP, bản đồ, màn hình Tuyến.
- Mục nâng cao cho CP2: OTA có ký, gợi ý điều phối, xuất hồ sơ vi phạm, INT8, mô phỏng Jetson.
- Hợp đồng sự kiện mở rộng không phá vỡ v1: `count` v1.1, `density`, `congestion`, `signal_cycle` v1, `violation_candidate`, `rejection_summary`, `health`, `ota_status`.
- Checkpoint đo bằng cỡ việc: CP1 = 53/65 ≈ 82%; Definition of Ready/Done và checklist production ở spec mục 8–9.

**Đề xuất ngày 22/09, học từ đối thủ cùng đề** (duyệt tại M0; chi tiết ở `docs/report/so-sanh-doi-thu.md` mục 5):
- Chốt model trước khi chỉnh ngưỡng; đổi trọng số thì chỉnh lại toàn bộ ngưỡng.
- Đo trước, rồi mới khử hộp trùng khác lớp.
- Kiểm tra hình học cấu hình cảnh khi nạp, kèm ảnh overlay; giao diện vẽ trên web ở mức COULD.
- SSE xác thực bằng vé ngắn hạn; trạng thái "đang gửi bù"; duyệt bằng bàn phím, không có nút hoàn tác.
- Trang nhật ký; nhật ký ghi IP thật sau reverse proxy.
- Bộ clip kịch bản và bước kiểm tra trước demo.
- **Không lấy** từ đối thủ: suy luận tập trung (đường B), RAG, cổng SOS, tự gom cụm camera.

**Còn mở:**
1. Chọn tuyến 3 nút MVP theo tiêu chí (hạn 25/09).
2. Q5: phân vai và thời hạn lưu giữ (đề xuất tối đa 7 ngày); chốt tại M0.
3. Chọn nền tảng cloud cho Live URL theo tiêu chí ở timeline WP-52 (trước 12/10).
4. Hỏi BTC định nghĩa "mô phỏng Jetson" (L-04).
5. Q10: giám khảo đăng nhập Live URL bằng cách nào (spec mục 14 có đề xuất).
6. Q11: thứ tự "tập khung mAP dev → cổng tinh chỉnh → chỉnh ngưỡng", và nguồn dữ liệu tinh chỉnh (spec mục 14 có đề xuất).

---

