# Đặc tả Hệ thống (Spec) — Phần 3: Yêu cầu Chức năng Nền tảng & Hệ thống (FR-DEV, ING, HITL, UI, AGT)
> Nguồn: Tách từ trafficeye-spec.md (Mục 4.6 - 4.13) tuân thủ SDLC Bước 1: Functional Requirements
> Bao gồm: Quản lý thiết bị, Ingest API, Duyệt vi phạm HITL, Dashboard Web, Agent LangGraph, Multi-cam.

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
- AC4 (22/09, học từ đối thủ): sau khi có mạng lại, trang sức khỏe và bản đồ hiện "đang gửi bù", kèm mốc `captured_at` mới nhất đã nhận, cho tới khi gửi hết (quy tắc ở mục 6.7). Chạy bình thường 30 phút thì trạng thái này không xuất hiện lần nào.

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
- Kênh SSE (FR-UI-2) không nhận JWT trong URL mà nhận **vé ngắn hạn** (mục 6.5), vì trình duyệt không gửi được header `Authorization` khi mở SSE. Đối thủ bị nhận xét đúng ở điểm này: kênh WebSocket khẩn cấp của họ để JWT trong query string. AC: vé đã dùng hoặc đã quá hạn thì trả 401 (có test).

**FR-HITL-1** — MUST · CP1

Duyệt bước 1 (điều hành viên, xem bản đã che): xác nhận, hoặc bác bỏ kèm mã lý do.
- AC1: quyết định được lưu kèm người duyệt, thời điểm, mã lý do.
- AC2: ứng viên mới hiện trên hàng đợi trong ≤ 5 giây mà không cần tải lại trang.
- AC3 (22/09): ngắt mạng của trình duyệt 2 phút; trong lúc đó trung tâm nhận ứng viên mới. Khi có mạng lại, hàng đợi hiện đủ mọi ứng viên mà không cần tải lại trang, kể cả khi access token đã hết hạn trong lúc mất mạng.

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
| FR-UI-2 | Hàng đợi duyệt theo vai trò; lọc theo loại vi phạm và trạng thái; cập nhật trực tiếp bằng SSE; mất kết nối thì tự xin vé mới và nối lại, thời gian chờ tăng dần từ 1 tới 30 giây. **Mỗi lần nối lại thì tải lại hàng đợi** (`GET /api/v1/candidates`) rồi mới nghe tiếp, vì SSE chỉ đẩy sự kiện phát sinh sau khi kết nối; nếu không tải lại, ứng viên đến trong lúc mất kết nối sẽ không bao giờ hiện. JWT hết hạn thì dùng refresh token (FR-AUTH-1) trước khi xin vé. **Duyệt được bằng bàn phím:** một phím xác nhận; một phím bác bỏ, mở danh sách mã lý do để chọn bằng phím số; một phím sang ứng viên kế tiếp | MUST · CP1 |
| FR-UI-3 | Bản đồ (Leaflet + OpenStreetMap): vị trí camera, màu theo trạng thái (trực tuyến / mất kết nối / ùn tắc). Không có Internet thì hiện ảnh bản đồ tĩnh | MUST · CP1 |
| FR-UI-4 | Trang xác minh bằng chứng: chữ ký, mã băm, chuỗi `parent_hash`. Không hiện ảnh nên có thể mở công khai | MUST · CP1 |
| FR-UI-5 | Trang sức khỏe: mỗi camera có trạng thái (theo bảng ở mục 6.7), FPS, độ trễ, số khung rơi, độ sâu outbox, nhiệt độ, phiên bản model và cấu hình, lần cuối nhận heartbeat. Có nút bật hoặc tắt chế độ điều khiển tay (chỉ `operator`); khi đang bật, dashboard hiện băng cảnh báo cho biết bật từ lúc nào | MUST · CP1 |
| FR-UI-6 | Trang báo cáo: bản nháp của Agent, người duyệt, lịch sử | MUST · CP1 |
| FR-UI-7 | Trang Tuyến: bản đồ tuyến tô màu theo mức ùn tắc, có mũi tên chỉ hướng tràn hàng chờ; bản đồ nhiệt nút × thời gian (ô 5 phút); thẻ từng nút (LOS, X, % chu kỳ thất bại, chu kỳ và thời gian xanh thực tế, tốc độ thoát bão hòa); danh sách sự kiện tuyến kèm số liệu; nút thiếu dữ liệu hiện màu xám | MUST · CP1 |
| FR-UI-8 | Trang nhật ký (admin, auditor): lọc theo người, hành động, ứng viên và khoảng thời gian; có nút kiểm chuỗi nối băm (FR-HITL-3) và nút xuất CSV. Demo CP1 dùng trang này để cho thấy lượt CSGT đã xem bản CSGT | MUST · CP1 |
| FR-UI-9 | Vẽ cấu hình cảnh (làn, vạch, vùng, ROI đèn) trên ảnh nền rồi xuất ra YAML theo mục 6.1. Sau ngày 11/10, đổi cấu hình vẫn phải qua CR (mục 12) | COULD |

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

