# Báo Cáo Kỹ Thuật Tổng Quan — TrafficEye Edge v1.0
> Nguồn: Tinh gọn từ trafficeye-edge-report.md (Bảo toàn các phân tích cốt lõi).
> Độ dài chuẩn: 150 - 250 dòng.

## 1. Tóm tắt điều hành

TrafficEye Edge là hệ thống camera giao thông xử lý AI **ngay tại biên**. Ở mỗi nút giao, một thiết bị edge làm các việc sau:
- phát hiện, theo dõi, đếm xe theo làn, hướng và loại xe;
- ước tính mật độ, hàng chờ, đo theo chu kỳ đèn (sự kiện `signal_cycle` v1);
- xác định **ứng viên** vi phạm: vượt đèn đỏ, đi ngược chiều, sai làn (đủ 3 kiểu: theo loại xe, qua vạch liền, sai mũi tên);
- chỉ gửi **sự kiện, số liệu và gói bằng chứng tối thiểu** về trung tâm, không bao giờ gửi video liên tục.

Con người đưa ra quyết định cuối cùng qua hai bước duyệt; AI chỉ tạo ứng viên. Điều hành viên xem bản đã che biển số. Sau khi điều hành viên xác nhận, cán bộ CSGT mới được xem bản dành cho CSGT: xe vi phạm hiện rõ, các xe khác đã che biển số và khuôn mặt. Mọi lần xem đều được ghi nhật ký.

**Kiến trúc trong một dòng:**
Camera (RTSP) → Edge node [YOLO26 + ByteTrack + máy trạng thái đèn + lớp ngữ cảnh + các luật vi phạm dạng plugin + đo chu kỳ đèn + đóng gói bằng chứng có chữ ký + OCR cho xe vi phạm] → outbox cục bộ → HTTPS → FastAPI + PostgreSQL + kho bằng chứng (trên cloud từ CP2, tức Live URL) → Dashboard có bản đồ, màn hình Tuyến (điều hành viên, CSGT) + Agent soạn báo cáo, giải thích và gợi ý điều phối (chỉ đọc, người duyệt).

Chiều ngược lại, trung tâm → edge: edge hỏi định kỳ trạng thái mong muốn; từ CP2 có thêm kênh điều khiển MQTT.

**Năm quyết định chính:**
1. **MVP chạy mô phỏng** [Đã chốt]. Camera là video mẫu phát qua RTSP. Edge là một container trên laptop, thiết kế để chuyển sang Jetson Orin Nano Super mà không phải đổi kiến trúc.
2. **AI chỉ dùng ở chỗ thật sự cần** [Đề xuất]. AI dùng cho phát hiện xe và phát hiện biển số để che. Tracking, đếm, trạng thái đèn và quyết định vi phạm dùng hình học, máy trạng thái và quy tắc. Agent không tham gia quyết định vi phạm.
3. **Precision trước recall.** Một ứng viên phải thỏa 6 điều kiện rồi mới qua 2 bước duyệt của người. Việc đo theo giao thức đã duyệt, báo kèm khoảng tin cậy Wilson 95%.
4. **Quyền riêng tư theo thiết kế** [Đã chốt]. Video thô liên tục không rời thiết bị. Bằng chứng được giữ ở mức tối thiểu và niêm phong bằng SHA-256 + Ed25519 ngay tại edge.
5. **Phạm vi** (chi tiết ở spec mục 2):
   - **CP1, ngày 14/10, 80% (53/65 điểm ≈ 82%):**
     - Tuyến 3 nút giao (3 camera cùng lúc, FR-MC-1 MUST);
     - đếm theo làn; mật độ và ùn tắc;
     - đo theo chu kỳ đèn (`signal_cycle` v1, FR-DEN-4);
     - phân tích nút và tuyến: v/c, độ trễ, LOS theo HCM, phát hiện tràn hàng chờ (spillback) và nút cổ chai (bottleneck) (FR-COR-1, FR-COR-2);
     - vượt đèn đỏ (RL), đi ngược chiều (WW), sai làn đủ 3 kiểu (LN-a, LN-b, LN-c);
     - duyệt 2 bước; trang xác minh;
     - OCR biển số xe vi phạm; Agent báo cáo ca trực;
     - bản đồ; màn hình Tuyến (FR-UI-7);
     - benchmark FP16; đo mAP, độ chính xác đếm, precision;
     - demo mất mạng rồi đồng bộ lại.
   - **CP2, ngày 23/10, 100%:**
     - OTA; kênh điều khiển MQTT; gợi ý điều phối; trợ lý giải thích;
     - xuất hồ sơ vi phạm (FR-EXP-1);
     - INT8; mô phỏng Jetson;
     - kết quả trên tập test (gồm cả đo chu kỳ đèn và sự kiện tuyến FR-EVAL-8);
     - checklist sẵn sàng production; Live URL (trung tâm trên cloud).

**Không làm trong giai đoạn này:** phần cứng thật (không bắt buộc), nhận diện khuôn mặt, đo tốc độ để xử phạt, phát hiện mũ bảo hiểm và dây an toàn, điều khiển đèn tự động.

**Vì sao cách dùng AI này mạnh ở tiêu chí 1 (mức độ ứng dụng AI):**
- AI nằm đúng chỗ mà thuật toán cố định không làm được, tức là nhìn và nhận ra xe.
- Phần còn lại giải thích được: mỗi ứng viên bị loại đều có mã lý do, và precision có số đo kèm khoảng tin cậy.
- Giám khảo thấy được cả "AI làm gì" lẫn "vì sao tin được AI".

---

## 2. Bài toán, người dùng và giả định

| Hạng mục | Nội dung | Trạng thái |
|---|---|---|
| Người dùng chính | Điều hành viên ca trực ở trung tâm điều hành giao thông, theo dõi nhiều camera cùng lúc | Giả định, cần phỏng vấn [Đã chốt là giả định] |
| Người dùng thứ hai | Cán bộ CSGT duyệt vi phạm (HITL) | Giả định |
| Có thể thêm | Ban quản lý khu dân cư (VinOcean Park…) | Nằm trong phạm vi nhưng **không phải trọng tâm MVP** [Đã chốt]; xem hướng mở rộng #8 |
| Nỗi đau (giả định) | Không thể canh hàng chục luồng video; dễ bỏ sót sự việc; duyệt vi phạm tốn công | Cần bằng chứng |
| Người trả tiền | Tổ chức vận hành hệ thống, khác với người dùng | Cần tách riêng khi pitch |

**Giá trị theo từng bên** (rút ra từ buổi GRILL):
- **Điều hành viên:** làm việc theo *cảnh báo có bằng chứng* thay vì canh cả tường màn hình. Lợi ích này đến từ việc lọc sự kiện; AI chạy ở trung tâm cũng làm được.
- **Tổ chức vận hành** (đây mới là lợi ích riêng của edge):
  - ít tốn băng thông và máy chủ GPU tập trung;
  - khi mất mạng vẫn không mất số liệu và bằng chứng;
  - dữ liệu thô không rời thiết bị.
- **Người dân:** ít bị lộ hình ảnh và biển số; người không vi phạm không bị gửi biển số đi.

**Giả định kỹ thuật cần kiểm chứng sớm:**
1. Khi tích hợp, nguồn camera **phải là video liên tục** [Đã chốt]; ảnh tĩnh không dùng được vì cần tracking. MVP dùng video quay sẵn nên không phụ thuộc vào điểm này, nhưng phải kiểm tra lại trước khi tích hợp camera thật (mục 20).
2. Góc camera thấy cùng lúc đèn, vạch dừng và các làn.
3. Video có đủ vi phạm để đo: ít nhất 60 cảnh báo trên tập test (protocol, mục 7.2).
4. Video bao phủ đủ các pha đèn và nhiều tình huống giao thông, gồm cả các ca khó A1–E5 [Đã chốt].

---

## 3. Phân rã bài toán

| # | Bài toán con | Loại lời giải | Mức |
|---|---|---|---|
| 1 | Nhận và giải mã video (RTSP/file) | Kỹ thuật | MUST |
| 2 | Phát hiện và phân loại xe | **ML** (detector) | MUST |
| 3 | Theo dõi xe qua các khung | Thuật toán liên kết (Kalman + IoU) | MUST |
| 4 | Hiệu chuẩn cảnh: vạch dừng, vùng giao lộ, làn, vùng đèn | Cấu hình + hình học | MUST |
| 5 | Trạng thái đèn tín hiệu | Phân loại màu trong ROI + **máy trạng thái** | MUST |
| 6 | Đếm xe theo làn, loại và hướng | Hình học (xe cắt qua vạch theo đúng hướng; gán làn bằng polygon) | MUST |
| 7 | Mật độ, hàng chờ, đo theo chu kỳ đèn (`signal_cycle` v1) và phân tích nút/tuyến (v/c, độ trễ, LOS theo HCM, tràn hàng chờ `spillback`, nút cổ chai `bottleneck`) | Hình học + thống kê theo chu kỳ đèn + công thức HCM | MUST (spec v1.0) |
| 8 | Ứng viên vi phạm: vượt đèn đỏ (RL), đi ngược chiều (WW), sai làn đủ 3 kiểu (LN-a, LN-b, LN-c); dừng đỗ sai ở mức COULD | **Bộ quy tắc cố định dạng plugin** trên một mô hình cảnh chung; mã A1–E5, W1–W8, L1–L8, S1–S6 | MUST |
| 9 | Đóng gói bằng chứng, che biển số, niêm phong | ML (phát hiện biển số) + mật mã | MUST |
| 10 | Hàng đợi cục bộ, đồng bộ khi có mạng | Kỹ thuật (outbox) | MUST |
| 11 | Backend, lưu trữ, phân quyền, nhật ký truy cập | Kỹ thuật | MUST |
| 12 | Dashboard và duyệt 2 bước | Kỹ thuật + UX | MUST |
| 13 | Agent: báo cáo ca trực và báo cáo sự cố (MUST); trợ lý giải thích ứng viên, gợi ý điều phối (SHOULD); hỏi đáp số liệu (COULD) | **LLM + công cụ chỉ đọc**, người duyệt | MUST / SHOULD / COULD |
| 14 | Giám sát FPS, độ trễ, tài nguyên | Kỹ thuật | Bản cơ bản MUST, đầy đủ SHOULD |
| 15 | Đánh giá precision có khoảng tin cậy | Thống kê | MUST (đã có script) |
| 16 | OCR biển số xe vi phạm; bản đồ; 3 camera trên cùng một tuyến (FR-MC-1); màn hình Tuyến | ML + kỹ thuật | MUST (spec v1.0) |
| 17 | OTA có ký và tự quay lại bản cũ; INT8; mô phỏng Jetson | Kỹ thuật | SHOULD (CP2) |

Chỉ có 3/16 bài toán con cần ML hoặc LLM. Đây là cách áp dụng đúng quy tắc "không nhét AI vào mọi chỗ" trong `CLAUDE.md`.

---



## 18. MVP

### 18.1 Phạm vi

Theo spec v1.0 mục 2, có tính cỡ việc và checkpoint (tổng 65 điểm).

| MUST | SHOULD | COULD / lộ trình |
|---|---|---|
| Tuyến 3 nút giao (3 camera cùng lúc, FR-MC-1) | OCR biển số xe vi phạm (có chế độ người đọc) | Dừng, đỗ sai (FR-VIO-ST) |
| Phát hiện + tracking + đếm theo làn, loại, hướng | Xuất hồ sơ vi phạm (FR-EXP-1, chuyển sang CP2) | Hỏi đáp số liệu (FR-AGT-3) |
| Đo theo chu kỳ đèn trên edge (`signal_cycle` v1, FR-DEN-4) | OTA có ký, canary, tự quay lại bản cũ | API dữ liệu mở; bot Telegram; bộ điều khiển đèn giả lập (FR-INT-3..5) |
| Phân tích nút và tuyến theo HCM: v/c, độ trễ, LOS, tràn hàng chờ `spillback`, nút cổ chai (FR-COR-1, FR-COR-2) | Gợi ý điều phối khi ùn tắc (người quyết định, FR-DSP-1) | Tích hợp camera thật; chạy trên Jetson thật |
| Vượt đèn đỏ (RL), đi ngược chiều (WW), sai làn đủ 3 kiểu (LN-a, LN-b, LN-c) | Trợ lý giải thích ứng viên (FR-AGT-2) | DeepStream nhiều luồng |
| Trạng thái đèn + lớp ngữ cảnh + mã lý do | INT8; mô phỏng Jetson bằng giới hạn tài nguyên | Mã hóa đầu–cuối cho CSGT; chạy lại thao tác che |
| Gói bằng chứng 3 bản, có ký; che biển số và khuôn mặt | Kênh điều khiển MQTT (đã chốt Q2, FR-DEV-2) | Mũ bảo hiểm, dây an toàn (cần model riêng) |
| Outbox + đồng bộ khi có mạng; heartbeat; hỏi định kỳ trạng thái mong muốn | Prometheus/Grafana | |
| Đăng nhập 4 vai trò; duyệt 2 bước; nhật ký nối băm | | |
| Dashboard, bản đồ, màn hình Tuyến (FR-UI-7), trang xác minh, trang sức khỏe | | |
| Agent báo cáo ca trực, có người duyệt và chế độ không LLM | | |
| Benchmark ONNX / TensorRT FP16 (FPS, độ trễ, kích thước model) | | |
| Đo mAP, độ chính xác đếm, precision từng loại vi phạm (Wilson 95%), đo chu kỳ đèn và sự kiện tuyến (FR-EVAL-8), tỉ lệ che lọt | | |
| Checklist sẵn sàng production (CP2), gồm Live URL (đã chốt Q3); máy dự phòng + video ghi sẵn | | |

### 18.2 Kế hoạch 5 tuần

Mốc, việc theo tuần và người làm: `docs/plan/timeline.md`. Ràng buộc vai trò để không lộ tập test: `docs/eval/protocol.md` mục 11 và 13.7.

### 18.3 Kịch bản demo khoảng 5 phút [Đề xuất]

1. **(30 s) Vấn đề và người dùng:** một điều hành viên không thể canh hàng chục màn hình; ùn tắc lan truyền giữa các nút khó phát hiện nguyên nhân gốc nếu chỉ nhìn từng camera riêng lẻ.
2. **(60 s) Dashboard và Tuyến 3 nút:** tuyến 3 nút chạy trực tiếp, số đếm theo làn; màn hình Tuyến hiện bản đồ nhiệt nút × thời gian, phát hiện tràn hàng chờ B → A; một cảnh báo vượt đèn đỏ xuất hiện kèm bản đã che biển số.
3. **(60 s) Duyệt 2 bước:** điều hành viên xác nhận → đăng nhập tài khoản CSGT → mở bản CSGT (chỉ xe vi phạm hiện rõ) → nhật ký truy cập hiện ra.
4. **(30 s) Trang xác minh:** sửa 1 byte trong file bằng chứng → trang báo "không khớp".
5. **(45 s) Mất mạng:** ngắt mạng edge → sự kiện dồn trong hàng đợi → nối lại → đồng bộ đủ, không trùng.
6. **(45 s) Số đo:** precision X% [Wilson L–U] trên N cảnh báo, với tập test quay sau khi đóng băng; đo chu kỳ đèn và tràn hàng chờ; chạy lại `evaluate.py` ngay trước giám khảo.
7. **(30 s)** Agent báo cáo ca trực (có bước người duyệt) và các hướng mở rộng.

Kịch bản đầy đủ cho CP1 (khoảng 10 phút) và CP2 (khoảng 12 phút) nằm ở spec mục 8.

**Phương án dự phòng (H-08):** máy thứ hai đã cài sẵn image, và một video ghi sẵn toàn bộ kịch bản demo.

**Bộ clip kịch bản và bước kiểm tra trước demo** (22/09, spec 8.1):
- mỗi đoạn cần phát lại có clip riêng, lấy từ dev (không bao giờ từ test), kèm SHA-256;
- trước mỗi lần demo: đủ clip, mọi camera có heartbeat, outbox rỗng.

Đối thủ cùng đề hỏng đúng ở bước này: lúc được quan sát, 5/5 kịch bản thiếu file, 0/24 camera có nhịp tim.

---

## 19. Hướng mở rộng

Từ v0.4, một phần các hướng dưới đây đã vào phạm vi của spec v1.0:

| Hướng | Phần đã vào phạm vi | Phần còn là hướng mở rộng |
|---|---|---|
| #3 | Đi ngược chiều, sai làn đủ 3 kiểu (MUST); dừng đỗ sai (COULD) | Mũ bảo hiểm, dây an toàn, dùng điện thoại |
| #4 | OCR biển số xe vi phạm (SHOULD) | Biển số nhiều dạng khác |
| #6 | 3 camera trên cùng một tuyến; phân tích tràn hàng chờ và nút cổ chai (MUST) | Hành lang nhiều nút giao phức tạp (> 3 nút), mạng lưới diện rộng |
| #7 | Gợi ý điều phối có giải thích (SHOULD) | Tự động tính toán và điều chỉnh chu kỳ đèn (Webster, SUMO) |
| #10 | OTA có ký, canary, tự quay lại bản cũ (SHOULD) | Quản lý đội hàng trăm thiết bị |
| #12 | MQTT làm kênh điều khiển ở CP2 (đã chốt Q2) | Chuyển cả luồng dữ liệu sang MQTT 5; mã hóa đầu–cuối cho bản CSGT |

| # | Hướng | Giá trị | Điều kiện cần | Độ khó |
|---|---|---|---|---|
| 1 | Tích hợp camera thật, rồi chạy trên Jetson thật; đo FPS, điện năng, nhiệt | Chứng minh hệ thống chạy được với dữ liệu và phần cứng thật | Camera cấp được **video liên tục** [Đã chốt]; mua thiết bị (399 USD [S1]) | Thấp–TB |
| 2 | DeepStream 9.1 nhiều luồng (nvinfer, nvtracker, giải mã phần cứng) [S7] | Nhiều camera trên một thiết bị | Pipeline MVP đã ổn định | Cao |
| 3 | Thêm vi phạm: dừng/đỗ sai (thời gian dừng trong vùng cấm), không đội mũ bảo hiểm (cần model phân loại) | Tăng giá trị cho CSGT | Dữ liệu có nhãn và giao thức đo riêng cho từng loại | TB–Cao |
| 4 | Đọc biển số Việt Nam 1–2 dòng (OCR) | Tự động tra cứu | Dữ liệu và đánh giá độ chính xác OCR; rủi ro riêng tư cao hơn | Cao |
| 5 | Lấy trạng thái đèn từ bộ điều khiển | Loại bỏ nhóm lỗi D | Hợp tác với đơn vị quản lý đèn | TB (kỹ thuật) / Cao (hợp tác) |
| 6 | Mạng lưới đô thị thông minh: tương quan ùn tắc đa tuyến; Agent phân tích lan truyền toàn thành phố | Điều hành cả khu vực | Nhiều nút giao chạy cùng lúc | Cao |
| 7 | Tự động điều chỉnh chu kỳ đèn bằng mô phỏng SUMO và công thức Webster | Tối ưu hóa giao thông tự động | Thử nghiệm mô phỏng và giấy phép cơ quan chức năng | Cao |
| 8 | Phiên bản khu dân cư (VinOcean Park…): đỗ sai chỗ, tốc độ nội khu, hàng chờ ở cổng. Nằm trong phạm vi nhưng không phải trọng tâm MVP [Đã chốt] | Khách hàng tư nhân, dễ tiếp cận | Phỏng vấn ban quản lý | TB |
| 9 | Vòng học chủ động: ca bị bác bỏ → mẫu âm khó → huấn luyện lại; theo dõi drift | Precision tăng dần theo thời gian | Model registry, quy trình gán nhãn | TB |
| 10 | Vận hành đội thiết bị: OTA có ký (cosign [S16]), triển khai dần, rollback | Quản lý hàng trăm thiết bị | CI/CD, hạ tầng | Cao |
| 11 | Con đường pháp lý để dùng xử phạt thật (kiểm định thiết bị, quy trình bằng chứng) | Dùng được trong thực thi | Cơ quan có thẩm quyền | Ngoài phạm vi team |
| 12 | Chuyển cả luồng dữ liệu sang MQTT 5 khi có nhiều thiết bị (kênh điều khiển MQTT đã làm ở CP2); mã hóa đầu–cuối cho bản CSGT; chạy lại thao tác che từ trang xác minh (đưa ra khỏi MVP ở design review) | Đúng kiến trúc production, tăng bảo mật | Có nhiều edge node; hệ thống quản lý khóa cho người dùng | TB |

---

## 20. Rủi ro và điểm nghẽn

Các mức dưới đây là **mức rủi ro kỹ thuật**, không phải đánh giá chất lượng dự án.

| Mức | Rủi ro | Hệ quả | Giảm thiểu |
|---|---|---|---|
| HIGH | Video test không đủ vi phạm | Precision chỉ mang tính minh họa (dưới 30 cảnh báo) | Đếm tay số vi phạm mỗi giờ ở tuần 1; quay ở nút đông xe; gộp thêm tập test dự phòng |
| HIGH | Góc quay không thấy đèn, vạch và làn cùng lúc | Nút giao đó không làm được vượt đèn đỏ | Khảo sát góc quay trước; đặt tiêu chí chọn nút |
| HIGH | Xe máy dày, bị che → tracker đổi ID | Báo nhầm hoặc cảnh báo trùng | Điều kiện 4; tách nguồn lỗi; chuyển BoT-SORT nếu cần; tăng độ phân giải |
| HIGH | Phạm vi phình to (thêm vi phạm, Agent, OTA) | Không kịp có demo ổn định | Khóa phạm vi MVP; mọi thứ khác đưa vào mục 19 |
| MEDIUM | Camera thật không cấp được video liên tục (chỉ có ảnh tĩnh) | Không dùng được camera đó để phát hiện vượt đèn đỏ | Yêu cầu video liên tục đã chốt; MVP dùng video quay sẵn nên không bị chặn; kiểm tra trước khi tích hợp |
| MEDIUM | Nền tảng cloud cho Live URL không mở được cổng MQTT, hoặc tự ngủ khi vắng truy cập | Last Will và thông báo tức thì không chạy trên Live URL | Chọn nền tảng theo tiêu chí ở timeline WP-52; dùng MQTT qua WebSocket TLS ở cổng 443; hỏi định kỳ vẫn chạy nên không mất chức năng |
| MEDIUM | Tràn hàng chờ có thể hiếm trong các buổi quay | Dữ liệu đánh giá phân tích tuyến bị ít mẫu | Chọn tuyến hay tắc vào giờ cao điểm chiều và quay ≥ 90 phút; n < 30 thì ghi "chỉ minh họa" |
| MEDIUM | MVP chỉ có 1 tuyến 3 nút | Chưa đo được khả năng tổng quát sang nút giao khác | Ghi vào mục hạn chế; nếu kịp, quay thêm một clip ngắn ở nút khác để minh họa |
| MEDIUM | Ban đêm, mưa, chói | Precision giảm | Báo riêng theo điều kiện; cổng chất lượng |
| MEDIUM | Hiệu năng đo trên PC khác trên Jetson | Tuyên bố "real-time" thiếu căn cứ | Ghi rõ đo trên máy nào; dẫn benchmark Jetson công khai [S2]; mượn hoặc mua 1 thiết bị nếu có thể |
| MEDIUM | Team mới với CV và edge | Chậm tiến độ | Interface rõ ràng; bắt đầu từ Ultralytics; cuối tuần 1 phải chạy được đầu–cuối |
| MEDIUM | Giấy phép AGPL-3.0 của Ultralytics [S3] | Ổn cho repo thi công khai; vướng khi thương mại | Ghi vào slide; phương án thay thế là RF-DETR (Apache 2.0) [S6] |
| LOW | Repo còn tài liệu cũ chưa đồng bộ | Giám khảo thấy repo không nhất quán | Đồng bộ toàn bộ docs theo spec v1.0 |

Danh sách đầy đủ 22 phát hiện của design review nằm ở phụ lục A. Các biện pháp đã được duyệt đã đưa vào mục 6.6, 8, 10–14, 16, 17 và 18.

---

