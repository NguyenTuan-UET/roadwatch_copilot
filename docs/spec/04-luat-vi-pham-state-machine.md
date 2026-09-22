# Đặc tả Hệ thống (Spec) — Phần 4: Luật Phát hiện Vi phạm & Máy Trạng thái (FR-VIO, EVN, PRV, OCR)
> Nguồn: Tách từ trafficeye-spec.md (Mục 4.4, 4.5, 7) tuân thủ SDLC Bước 4: Software Design
> Bao gồm: 3 luật vi phạm (vượt đèn, sai làn, ngược chiều), máy trạng thái đèn, gói bằng chứng 3-5s, bảo vệ riêng tư.

### 4.4 Vi phạm

Tóm tắt luật ở mục 7; chi tiết điều kiện và mã loại trừ ở `docs/spec/false-positives.md`.

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



## 7. Luật phát hiện theo loại vi phạm (tóm tắt)

Chi tiết điều kiện, dấu hiệu phân biệt và cách loại trừ ở `docs/spec/false-positives.md`. Mức phạt lấy theo các nguồn tổng hợp Nghị định 168/2024/NĐ-CP; phải đối chiếu nguyên văn trước khi đưa lên slide.

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

