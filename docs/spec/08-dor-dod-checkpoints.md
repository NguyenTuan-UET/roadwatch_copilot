# Đặc tả Hệ thống (Spec) — Phần 8: Quản trị Nghiệm thu (DoR, DoD, Checkpoint & Quyết định PO)
> Nguồn: Tách từ trafficeye-spec.md (Mục 8, 9, 10, 11, 12, 13, 14) tuân thủ SDLC Bước QD & Bước 7
> Định nghĩa hoàn thành (DoD), Tiêu chí nghiệm thu CP1/CP2 và 11 quyết định kỹ thuật từ PO.

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
- **Bộ clip kịch bản** (học từ Simulation Controller của đối thủ):
  - mỗi đoạn demo cần phát lại có một clip riêng: một ca cho mỗi loại vi phạm, các ca khó kèm mã lý do, một đoạn ùn tắc;
  - clip lấy từ các phiên dev, không bao giờ lấy từ tập test;
  - clip được liệt kê trong `eval/manifests/demo.csv`, kèm SHA-256;
  - MediaMTX phát mỗi clip ở một đường dẫn riêng.
- **Kiểm tra trước mỗi lần demo**, kể cả buổi tổng duyệt:
  - mọi clip trong `demo.csv` có trên máy demo và khớp SHA-256;
  - mọi camera có heartbeat;
  - outbox rỗng.

  Đối thủ cùng đề hỏng đúng ở bước này: lúc được quan sát, 5/5 kịch bản của họ thiếu file video, và 0/24 camera có nhịp tim.
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
| Bảo mật | TLS; mật khẩu băm; JWT có hạn và refresh; RBAC có test; giới hạn tần suất đăng nhập; bí mật chỉ qua biến môi trường; không còn tài khoản mặc định; `pip-audit` và `npm audit` không còn lỗ hổng High/Critical; nhật ký ghi IP thật khi truy cập qua reverse proxy (thử trên Live URL) |
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
- **Phân vai và tải việc** (22/09): xem timeline 3.0 mục 5. Mã vai: TV1 = Cường, TV2 = Tuấn, TV3 = Linh, TV4 = Khánh.
  - Ước lượng chi tiết: khoảng 751 giờ, tức cần khoảng 40 giờ/người/tuần ở tuần 2–4, không phải 25 giờ.
  - Vì cần 3 người chạm vào tập test, chỉ TV1 được chỉnh ngưỡng, và TV1 nằm trên đường găng đóng băng.
- **Ca ngược chiều và sai làn có thể hiếm** tại nút đã chọn:
  - tiêu chí chọn nút (WP-02) được bổ sung để giảm rủi ro này;
  - **không dàn dựng vi phạm trên đường** (nguy hiểm, trái luật); chỉ dùng các ca xảy ra tự nhiên;
  - loại nào có n < 30 thì báo cáo là "chỉ minh họa".
- **OCR biển số Việt Nam 2 dòng** có thể chưa đạt. Khi đó dùng chế độ người đọc, tức là FR-OCR-1 AC3.
- **Tuần 3 là tuần nặng nhất của cả team** (chỉnh ngưỡng, gói bằng chứng, phân tích tuyến, các trang CSGT và Tuyến). Đã bù tải như sau: FR-AGT-3 xuống COULD, FR-EXP-1 sang CP2, WP-18 và WP-19 lùi sang 12/10.
- **Mỗi buổi quay cần 3 người có mặt cùng lúc**, và có khoảng 5 buổi: khảo sát tuyến, 2 buổi dev, tập test dự phòng, tập test chính.
- **Tràn hàng chờ có thể hiếm** trong các buổi quay. Chọn tuyến hay tắc vào giờ cao điểm chiều và quay ≥ 90 phút; n < 30 thì ghi "chỉ minh họa".

**Thứ tự cắt, những gì không bao giờ cắt, và điểm kích hoạt:** `docs/plan/timeline.md` mục 7 (một bản duy nhất, có ghi ai được bớt việc khi cắt).

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
| Q5 | Phân vai và thời hạn lưu giữ | Phân vai: thay bằng timeline 3.0 mục 5 (22/09). Thời hạn lưu giữ: đề xuất tối đa 7 ngày | Chờ duyệt tại M0 (24/09) |
| Q6 | Mức "chỉnh đèn" | Chỉ phân tích ùn tắc; không tự tính hay tự đổi thời gian đèn. Webster + SUMO để ở hướng mở rộng | **Đã chốt 21/09** |
| Q7 | Dữ liệu cho phân tích tuyến | Quay thật 3 nút liên tiếp, cùng lúc, bằng 3 camera của FR-MC-1 | **Đã chốt 21/09** |
| Q8 | "Làm full cả 3 vấn đề" | 3 loại vi phạm của đề; sai làn đủ 3 kiểu, đều MUST. Dừng/đỗ sai vẫn là COULD | **Đã chốt 21/09** |
| Q9 | Phân tích tuyến vào checkpoint nào | Xong trước CP1; đánh giá trên tập test ở CP2. Bù tải: FR-AGT-3 xuống COULD, FR-EXP-1 sang CP2, WP-40 sang TV4 | **Đã chốt 21/09** |
| Q10 | Giám khảo đăng nhập Live URL bằng cách nào (thêm 22/09) | Chưa có. Đối thủ đặt nút "chọn nhanh tài khoản kiểm thử" ngay trên trang login, và chính tài khoản công khai đó đọc được credential camera và PII. NFR-SEC-1 cấm tài khoản mặc định ở production. **Đề xuất:**<br>• mỗi vai (operator, csgt, auditor) có một tài khoản riêng cho giám khảo, và **không cấp vai admin**;<br>• tài khoản chỉ có trên Live URL chạy dữ liệu demo, do script seed tạo, mật khẩu ngẫu nhiên;<br>• mật khẩu gửi trong tài liệu nộp bài, không hiện trên trang login;<br>• khóa tài khoản khi URL hết hạn sống (Demo Day + 7 ngày, WP-52).<br>Như vậy không vi phạm NFR-SEC-1, vì đây không phải tài khoản mặc định có sẵn trong code | Chờ PO tại M0 (24/09) |
| Q11 | Hạn tập khung mAP dev so với cổng tinh chỉnh (thêm 22/09) | FR-DET-1 quyết định có tinh chỉnh hay không trước 04/10, nhưng WP-38 hạn 06/10. Cũng chưa có nguồn dữ liệu tinh chỉnh: dữ liệu đó không được trùng tập khung dev dùng để chọn model, cũng không được trùng tập test. **Đề xuất:**<br>• thứ tự: WP-38 xong trước khi quyết định ở cổng; model chốt trước WP-20 (protocol mục 2.4);<br>• dữ liệu tinh chỉnh: khung từ các phiên dev, trừ khoảng 200 khung mAP dev, cộng dữ liệu công khai của Việt Nam nếu xin được (báo cáo mục 16); không bao giờ lấy từ phiên test;<br>• timeline 3.0 áp dụng phương án này: WP-38 xong 02/10, quyết định cổng tại M2 (04/10) | Chờ PO tại M0 (24/09) |

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
