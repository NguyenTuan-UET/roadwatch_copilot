# Đặc tả Hệ thống (Spec) — Phần 2: Yêu cầu Chức năng Edge Vision (FR-DET, TRK, DEN, LGT)
> Nguồn: Tách từ trafficeye-spec.md (Mục 4.1, 4.2, 4.3) tuân thủ SDLC Bước 1: Functional Requirements
> Tiêu chuẩn nghiệm thu: Given - When - Then.

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
- **Q11 (22/09):** timeline 3.0 kéo hạn tập khung dev (WP-38) lên 02/10, cho kịp điểm quyết định này. Khả năng phải tinh chỉnh là có thật: đối thủ cùng đề báo mAP50 tăng từ 0,590 lên 0,892 sau khi tinh chỉnh trên dữ liệu Việt Nam. Họ dùng YOLOv8n và tự công bố con số, nên chỉ dùng làm tham khảo.
- Model phải chốt trước khi bắt đầu chỉnh ngưỡng (WP-20). Đổi trọng số thì xóa cache và chỉnh lại toàn bộ ngưỡng (protocol mục 2.4).

**FR-DET-2** — MUST · CP1

ByteTrack với `persist=True`, giữ ID trên từng luồng.

**Khử hộp trùng khác lớp** (học từ đối thủ):
- Vấn đề: một xe bị phát hiện thành hai box thuộc hai lớp khác nhau (ví dụ `car` và `truck`), nên hai track tranh nhau một xe. Hậu quả là đổi ID (E1, W4) và lớp dao động (L2). Đối thủ báo khử hộp trùng giảm tỉ lệ phân mảnh ID từ 1,46 xuống 1,19 (họ tự công bố).
- Đo trước: trên tập khung dev (WP-38), đếm số cặp box khác lớp chồng lên cùng một xe, tức IoU ≥ ngưỡng (khởi điểm 0,7). YOLO26 được giới thiệu là suy luận end-to-end, không cần NMS [Cần kiểm chứng]. Vì vậy hiện tượng này có thể ít hơn so với YOLOv8n mà đối thủ dùng.
- Chỉ bật bộ lọc khi số đo cho thấy cần. Bộ lọc giữ box có confidence cao hơn; lớp xe lấy theo phiếu bầu của track. Nếu tham số `agnostic_nms` của Ultralytics dùng được với định dạng model đang chạy thì dùng nó, không viết bộ lọc riêng.

AC:
- AC1: báo cáo tỉ lệ sự kiện thật được một track liền mạch bao phủ (protocol mục 6).
- AC2: báo cáo số cặp box trùng khác lớp trên tập khung dev, trước và sau khi lọc (nếu có bật bộ lọc).

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

