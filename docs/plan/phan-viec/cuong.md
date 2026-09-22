# Việc của Nguyễn Huy Cường

> **Vai trò:** PO + PM; người viết luật vượt đèn đỏ và **người duy nhất chỉnh ngưỡng**; hiệu năng trên thiết bị edge.
> **Thời gian cần:** khoảng 23 / 39 / 36 / 42 / 40 giờ cho tuần 1 → 5.
> File này chỉ nói về việc của bạn. Lịch chung và ai giữ việc nào: `docs/plan/timeline.md`. Hai file lệch nhau thì theo timeline.

## Thuật ngữ trong file này

| Từ | Nghĩa |
|---|---|
| WP-xx | Gói việc số xx trong kế hoạch chung (`docs/plan/timeline.md` mục 4). Mỗi WP là một issue trên GitHub Project |
| TASK-0xx | Một bước nhỏ trong plan M1 (`docs/plan/2026-09-21-m1-skeleton.md`), có sẵn code và lệnh kiểm tra |
| PH1…PH11 | 11 phân hệ của hệ thống. Bản đồ ở `docs/architecture_diagram.md` mục 0 |
| M0…M7 | Mốc nội bộ: M0 duyệt spec 24/09, M1 khung chạy 27/09, M2 luật lõi 04/10, M3 đóng băng 11/10, M4 khóa nhãn test 18/10, M5 chạy test 19/10, M7 khóa code 25/10 |
| CP1, CP2 | Hai buổi demo với ban tổ chức: CP1 ngày 14/10 (80%), CP2 ngày 23/10 (100%, sẵn sàng production) |
| Spec, FR, AC | Spec quy định hệ thống phải làm gì (`docs/spec/trafficeye-spec.md`). FR-xxx là một yêu cầu; AC là tiêu chí nghiệm thu của yêu cầu đó |
| Change Request | Đề nghị đổi spec sau M0. Ghi vào `docs/spec/changes.md`; PO duyệt |
| Edge | Máy đặt ở nút giao (MVP dùng laptop), chạy AI trên video tại chỗ |
| Luật tất định | Luật viết bằng điều kiện rõ ràng về hình học và thời gian. AI không quyết định vi phạm |
| Ứng viên vi phạm | Ca hệ thống nghi là vi phạm. Phải qua người duyệt mới thành vi phạm |
| Lớp ngữ cảnh | Bước chạy trước luật, gắn lý do loại trừ (xe ưu tiên, đèn không rõ…) |
| Mã loại trừ | Lý do một ca trông giống vi phạm nhưng không phải: A1–E5 (vượt đèn đỏ), W1–W8 (ngược chiều), L1–L8 (sai làn). Danh mục ở `docs/spec/false-positives.md` |
| RL, WW, LN | Vượt đèn đỏ, đi ngược chiều, sai làn. Sai làn có 3 kiểu: LN-a (làn dành cho loại xe khác), LN-b (đè vạch liền), LN-c (đi sai hướng mũi tên) |
| Ngưỡng, chỉnh ngưỡng | Các con số trong luật, ví dụ thời gian ân hạn sau khi đèn chuyển đỏ. Chỉnh ngưỡng là chọn các con số này trên tập dev |
| Leave-one-video-out | Cách chỉnh ngưỡng: lần lượt để riêng một video ra kiểm, chỉnh trên các video còn lại. Tránh chọn con số chỉ khớp với dữ liệu đã thấy |
| Đóng băng | Khóa ngưỡng và luật ngày 11/10. Sau đó không đổi nữa, để số đo trên tập test là thật |
| Tập dev, tập test | Tập dev: video để phát triển và chỉnh ngưỡng. Tập test: video quay sau ngày đóng băng, chỉ dùng để đo một lần |
| Precision, Wilson 95% | Precision: trong các cảnh báo hệ thống đưa ra, bao nhiêu phần trăm là vi phạm thật. Wilson 95%: khoảng tin cậy đi kèm con số đó |
| Ablation | Tắt thử một phần (ví dụ lớp ngữ cảnh) để đo phần đó giúp được bao nhiêu |
| Đăng ký trước | File `eval/preregistration.md`: ghi sẵn cách đo và ngưỡng trước khi có tập test |
| mAP, AP50 | Độ chính xác của model phát hiện xe, từ 0 đến 1. AP50 tính riêng cho từng loại xe |
| Cổng tinh chỉnh model | Quyết định ngày 04/10: nếu AP50 của xe máy < 0,5 thì huấn luyện thêm YOLO trên dữ liệu Việt Nam |
| ONNX, TensorRT FP16, INT8 | Các cách đóng gói và nén model để chạy nhanh hơn trên GPU |
| Soak test | Chạy liền 24 giờ để xem hệ thống có rò bộ nhớ, bị sập hay chậm dần không |
| HCM, LOS | Phương pháp đánh giá nút giao (Highway Capacity Manual). LOS là mức phục vụ, từ A (thông thoáng) tới F (tắc) |
| MediaMTX | Phần mềm phát lặp video đã quay thành luồng như camera thật |
| PR, review, CI | PR: yêu cầu gộp code. Review: người khác đọc và duyệt. CI: máy tự chạy test; CI xanh mới được gộp |
| DoD | Điều kiện "xong" chung cho mọi việc (spec mục 9.2) |

## 1. Bạn phụ trách gì

| Phân hệ | Phần của bạn |
|---|---|
| — Điều phối | Duyệt spec (M0), nghiệm thu mỗi tuần, CP1, CP2, phỏng vấn người dùng, slide, nộp bài |
| PH3 · Luật vi phạm | Khung luật chung, lớp ngữ cảnh, luật vượt đèn đỏ. **Chỉnh ngưỡng mọi luật** và đóng băng. Review luật ngược chiều và sai làn |
| PH7 · Phân tích giao thông | Mật độ, hàng chờ, ùn tắc tại nút; gợi ý điều phối |
| PH10 · Đánh giá và dữ liệu | Tập khung đo mAP; quyết định cổng tinh chỉnh model; bộ clip demo |
| PH11 · Vận hành và hiệu năng | GPU trên máy demo, ONNX/TensorRT, INT8, chạy 3 camera, soak test 24 giờ |

## 2. Đọc gì trước khi bắt đầu

| Thứ tự | Đọc | Để biết |
|---|---|---|
| 1 | `README.md` | Sản phẩm làm gì (10 phút) |
| 2 | `docs/architecture_diagram.md` mục 0–3 | Hệ thống gồm 11 phân hệ nào, dữ liệu đi ra sao |
| 3 | Spec mục 2, 8, 9, 12, 14 | Phạm vi, CP1/CP2, thế nào là xong, cách đổi spec, các câu còn mở |
| 4 | Spec mục 4.3, 4.4, 6.2, 6.6, 7 | Yêu cầu và giao diện của luật, file ngưỡng |
| 5 | `docs/spec/false-positives.md` mục 1, 2, 6 | Các ca dễ báo nhầm của vượt đèn đỏ |
| 6 | `docs/eval/protocol.md` mục 2.4, 3, 11, 13.7 | Cách chỉnh ngưỡng, đóng băng, các quy tắc chống lộ tập test |
| 7 | `docs/plan/timeline.md` (cả file) | Bạn là PM nên cần nắm toàn bộ lịch |

## 3. Quy tắc bắt buộc với bạn

1. **Không bao giờ mở thư mục test hay xem video test.** Không đi quay buổi S5 (03/10) và S6 (14/10).
2. **Chỉ bạn được chỉnh ngưỡng.** Sau đóng băng (11/10), chỉ bạn được sửa code luật, và chỉ sửa lỗi không làm đổi logic phát hiện.
3. **Tuần 3 (05–11/10) là tuần chỉnh ngưỡng:** chỉ họp standup; phỏng vấn dời sang tuần 2 và tuần 4. Buổi demo tối 11/10 giao người khác điều hành, bạn vẫn ký nghiệm thu.
4. **Review mọi PR chạm luật trong 24 giờ.**
5. **Máy demo là laptop của bạn.** Máy dự phòng phải cài xong trước 18/10.

## 4. Việc theo thứ tự thời gian

Mỗi việc ghi: **Làm** (các bước), **Cần có** (thứ phải có trước, và ngày dự kiến có), **Nộp** (kết quả), **Xong khi** (cách kiểm tra). Dấu ⚠ đánh dấu việc mà người khác đang chờ: việc này trễ thì cả team trễ.

### Tuần 1 (22–27/09)

#### Việc 1 · Chủ trì duyệt spec (M0) — hạn 24/09 · WP-32
- **Làm:** gửi spec cho cả team đọc trước. Họp M0: đi qua từng mục, chốt phân vai và các câu còn mở ở spec mục 14 (Q5 thời hạn lưu giữ, Q10 tài khoản giám khảo, Q11). Gắn tag `spec-v1.0`. Tạo `docs/spec/changes.md` làm sổ Change Request.
- **Nộp:** tag `spec-v1.0` trên GitHub; file `docs/spec/changes.md`.
- **Xong khi:** mọi câu ở spec mục 14 đã có quyết định. ⚠ Cả team chờ mốc này.

#### Việc 2 · Chạy thử GPU trên máy demo — hạn 25/09 · WP-31 (TASK-020) · PH11
- **Làm:** theo TASK-020 trong plan M1: cập nhật driver NVIDIA (đang là 528.25), cài torch bản CUDA, đo FPS, thử chạy GPU trong Docker.
- **Nộp:** `docs/report/spike-wp31.md`, gồm bảng FPS và quyết định chạy edge bằng Docker hay conda.
- **Xong khi:** có quyết định Docker hay conda. ⚠ Khung edge đang chờ quyết định này.

#### Việc 3 · Chọn tuyến 3 nút giao — hạn 25/09 · WP-02
- **Làm:** khảo sát ngoài đường theo tiêu chí ở `docs/plan/timeline.md` (tuần 1, "Tiêu chí chọn tuyến 3 nút"). Đi cùng người viết luật ngược chiều và sai làn để kiểm cả tiêu chí của hai luật đó.
- **Nộp:** tên 3 nút và ảnh chụp vị trí đặt máy, ghi vào issue WP-02.
- **Xong khi:** tuyến đạt đủ tiêu chí. Nếu không nút nào có làn dành riêng cho loại xe thì chọn thêm một điểm quay riêng cho LN-a.

#### Việc 4 · Chuẩn bị phỏng vấn người dùng — hạn 25/09 · WP-08
- **Làm:** lập danh sách liên hệ và bộ câu hỏi. Gửi ban tổ chức câu hỏi "mô phỏng Jetson" nghĩa là gì (L-04).
- **Nộp:** danh sách liên hệ và bộ câu hỏi trong issue WP-08.
- **Xong khi:** đã gửi liên hệ đầu tiên và câu hỏi cho ban tổ chức.

#### Việc 5 · Khung luật và lớp ngữ cảnh — hạn 27/09 · phần đầu WP-11 · PH3
- **Làm:** viết các kiểu dữ liệu `FrameContext`, `Candidate`, `Rejection` và giao diện luật theo spec mục 6.6. Viết lớp ngữ cảnh gắn mã lý do. Chạy trên dữ liệu giả. Viết một luật mẫu kèm test mẫu để các luật khác làm theo.
- **Nộp:** PR code khung luật, có test.
- **Xong khi:** một luật khác import được khung và chạy được test mẫu. ⚠ Luật ngược chiều và sai làn đang chờ khung này.

#### Việc 6 · Dự nghiệm thu M1 — 27/09
- **Làm:** chạy thử hệ thống đầu–cuối theo TASK-022 của plan M1.
- **Xong khi:** TASK-022 đạt.

### Tuần 2 (28/09–04/10)

#### Việc 7 · Review máy trạng thái đèn — hạn 30/09 · WP-10 · PH2
- **Làm:** đọc PR máy trạng thái đèn. Kiểm tra ba trạng thái KHÔNG RÕ, NHẤP NHÁY, TẮT đều chặn luật (luật không được báo vi phạm khi đèn ở ba trạng thái này).
- **Xong khi:** đã approve PR.

#### Việc 8 · Luật vượt đèn đỏ — hạn 02/10 · WP-11 · PH3
- **Làm:**
  1. Viết luật 6 điều kiện theo spec mục 7.1 và `docs/spec/false-positives.md` mục 1–2 (6 điều kiện liệt kê ở `docs/architecture_diagram.md` mục 2).
  2. Mỗi ca bị loại ghi đúng mã A1–E5.
  3. Xuất `alerts.jsonl` và `rejection_summary` (đếm số ca bị loại theo từng mã).
  4. Viết test cho từng điều kiện và từng mã.
- **Cần có:** máy trạng thái đèn và cấu hình cảnh v2 (WP-10, có từ 30/09); `scripts/evaluate.py` (TASK-019, có từ 27/09). Chưa có thì làm trên dữ liệu giả theo spec mục 6.6.
- **Nộp:** PR luật vượt đèn đỏ, có test.
- **Xong khi:** đạt FR-VIO-0 AC1–AC2, và `python scripts/evaluate.py --split dev` chạy được trên kết quả của luật. ⚠ Gói bằng chứng cần kiểu `Candidate` hoàn chỉnh từ việc này.

#### Việc 9 · Tập khung đo mAP — hạn 02/10 · WP-38 · PH10
- **Làm:** chọn khoảng 200 khung hình từ video dev S1–S2. Cho model gợi ý box rồi sửa tay. Viết script tính mAP50 và mAP50-95 cho từng loại xe. Đếm số cặp box trùng nhau nhưng khác loại (FR-DET-2 AC2).
- **Cần có:** video S1–S2 đã chuyển về 15 FPS (có từ 30/09).
- **Nộp:** tập khung có nhãn, script mAP, bảng kết quả.
- **Xong khi:** có số mAP theo từng loại xe cho YOLO26n trên dev.

#### Việc 10 · Review luật ngược chiều — hạn 03/10 · WP-33 · PH3
- **Làm:** đọc PR, kiểm tra có test cho từng điều kiện và từng mã W1–W8.
- **Xong khi:** đã approve PR.

#### Việc 11 · Phỏng vấn người dùng — hạn 04/10 · WP-08
- **Làm:** phỏng vấn ít nhất một người dùng (điều hành viên hoặc CSGT). Có người ghi chép.
- **Nộp:** biên bản phỏng vấn (H-09).

#### Việc 12 · Quyết định cổng tinh chỉnh model (M2) — 04/10 · PH10
- **Làm:** xem AP50 của xe máy ở Việc 9.
  - Nếu ≥ 0,5: giữ model.
  - Nếu < 0,5: tinh chỉnh YOLO trong 04–06/10 (khoảng 10 giờ), rồi chạy lại cache mọi video dev (protocol mục 2.4). Khi đó WP-39 có thể chuyển người (timeline, tuần 2).
- **Nộp:** quyết định ghi vào `docs/spec/changes.md`.

### Tuần 3 (05–11/10) — tuần chỉnh ngưỡng

#### Việc 13 · Review luật sai làn — hạn 06/10 · WP-34 · PH3
- **Làm:** đọc PR, kiểm tra có test cho cả 3 kiểu LN-a, LN-b, LN-c và từng mã L1–L8.
- **Xong khi:** đã approve PR.

#### Việc 14 · Mật độ, hàng chờ, ùn tắc — hạn 08/10 · WP-39 · PH7
- **Làm:** tính mật độ và hàng chờ tại nút; phát hiện ùn tắc theo từng chu kỳ đèn (FR-DEN-1, FR-DEN-2).
- **Cần có:** máy trạng thái đèn và cấu hình cảnh v2 (WP-10).
- **Xong khi:** đạt FR-DEN-1 AC và FR-DEN-2 AC trên các đoạn dev đã gán nhãn. ⚠ Phân tích tuyến và gợi ý điều phối dùng kết quả này.

#### Việc 15 · Chỉnh ngưỡng — 07–10/10 · WP-20 · PH3, PH10
- **Làm:**
  1. Chỉnh ngưỡng bằng leave-one-video-out trên tập dev cho mọi luật (RL, WW, LN-a, LN-b, LN-c) và cho ngưỡng phân tích tuyến.
  2. Kiểm tra quy tắc ghép (M-02).
  3. Làm ablation lớp ngữ cảnh.
  4. Viết `eval/preregistration.md`.
- **Cần có:** nhãn dev (08/10); luật ngược chiều (03/10); luật sai làn (06/10); sự kiện `signal_cycle` (07/10); công cụ đo tuyến (09/10); phân tích tuyến (10/10).
- **Nộp:** bảng precision trên dev theo từng loại, kèm Wilson 95%; file đăng ký trước.
- **Xong khi:** có số cho mọi loại vi phạm được đánh giá. ⚠ **Đây là điểm nghẽn số 1 của cả dự án:** thiếu đầu vào nào một ngày là mất một ngày chỉnh ngưỡng. Mỗi standup trong tuần 2–3, hỏi từng đầu vào đã tới đâu.

#### Việc 16 · Đóng băng (M3) — 11/10 · PH3
- **Làm:** ghi `configs/frozen/rl-v1.yaml` và `configs/frozen/corridor-v1.yaml` (spec mục 6.2, 6.8). Tính SHA-256 hai file. Gắn tag `eval-freeze-v1` và đẩy lên GitHub.
- **Xong khi:** tag đã có trên GitHub. ⚠ Sau mốc này mới được quay tập test chính.

### Tuần 4 (12–18/10)

#### Việc 17 · ONNX, TensorRT FP16 và đo tốc độ — hạn 13/10 · WP-41 · PH11
- **Làm:** xuất model sang ONNX, rồi TensorRT FP16. Đo tốc độ từng tầng (đọc video, phát hiện, bám vết, luật).
- **Nộp:** bảng đo chạy lại được bằng một lệnh.

#### Việc 18 · 3 camera cùng lúc — hạn 13/10 · WP-44 · PH11
- **Làm:** chạy 3 luồng MediaMTX với 3 cấu hình cảnh, mỗi nút của tuyến một luồng.
- **Cần có:** heartbeat và trạng thái mong muốn (WP-40, có từ 10/10).
- **Xong khi:** đạt FR-MC-1 AC1–AC2; cả 3 camera cấp dữ liệu cho phân tích tuyến.

#### Việc 19 · Chuẩn bị CP1 — hạn 13/10 · PH10
- **Làm:** lập bộ clip kịch bản `eval/manifests/demo.csv`, **chỉ lấy từ tập dev**. Viết checklist kiểm tra trước demo.
- **Xong khi:** kiểm tra trước demo đạt 2 lần liên tiếp.

#### Việc 20 · CP1 — 14/10
- **Làm:** chủ trì demo. Ghi phản hồi vào `docs/plan/cp1-feedback.md`. **Buổi chiều không đi quay S6.**

#### Việc 21 · Gợi ý điều phối — hạn 17/10 · WP-47 · PH7
- **Làm:** luật tất định đưa ra gợi ý khi ùn tắc; Agent chỉ viết phần giải thích; người vận hành quyết định (FR-DSP-1).
- **Cần có:** Việc 14; phân tích tuyến (WP-54); Agent báo cáo (WP-42, có từ 13/10).
- **Xong khi:** đạt FR-DSP-1 AC.

#### Việc 22 · Slide nháp và kịch bản demo CP2 — hạn 18/10 · WP-26
- **Làm:** soạn slide nháp và kịch bản demo theo spec mục 8.2.
- **Xong khi:** cả team đã đọc một lượt.

### Tuần 5 (19–25/10)

#### Việc 23 · INT8 và mô phỏng Jetson — hạn 21/10 · WP-23 · PH11
- **Làm:** nén model INT8; chạy trong giới hạn tài nguyên giống Jetson; đo FPS đầu–cuối khi bật mọi luật.
- **Nộp:** bảng FP32 / FP16 / INT8, kèm độ lệch mAP.
- **Xong khi:** FPS đầu–cuối ≥ 15.

#### Việc 24 · Soak test 24 giờ và thử phục hồi — 20–22/10 · WP-50 · PH11
- **Làm:** chạy liền 24 giờ trên máy demo. Lần lượt tắt edge, backend, DB, mạng để xem hệ thống tự phục hồi. Ghi log. Lỗi phát sinh thì mở issue cho người phụ trách production sửa.
- **Cần có:** bản hardening production (WP-49, có từ 20/10).
- **Xong khi:** mục Tin cậy trong checklist CP2 xanh; có log soak test.

#### Việc 25 · Tài liệu — hạn 22/10 · WP-30
- **Làm:** viết mục hạn chế của hệ thống và ghi chú cho phần pitch.

#### Việc 26 · Slide, video demo, bộ câu hỏi giám khảo — hạn 23/10 · WP-28
- **Làm:** chốt slide, quay video demo, soạn câu trả lời 30 giây và bộ câu hỏi giám khảo.
- **Cần có:** báo cáo đánh giá (WP-27, có từ 21/10).

#### Việc 27 · CP2 — 23/10
- **Làm:** chủ trì demo; ký nghiệm thu khi checklist production xanh.

#### Việc 28 · Tổng duyệt và nộp bài — 25/10 và 26/10 · WP-29
- **Làm:** tổng duyệt trên máy chính và máy dự phòng (25/10); nộp bài (26/10).

## 5. Việc lặp lại

- **Mỗi ngày:** standup 15 phút; cập nhật `WORKLOG.md`; theo dõi % hoàn thành trên GitHub Project.
- **Tối Chủ nhật** (27/09, 04/10, 11/10, 18/10): demo nội bộ; nghiệm thu các WP theo cột "Nghiệm thu" của timeline; báo % hoàn thành theo spec mục 8.3.
- **Đi quay video dev:** S1 (26/09 chiều), S2 (28/09 cao điểm chiều), S3 (30/09 cao điểm chiều), S4 (02/10 tối). Mỗi máy quay màn hình time.is lúc bắt đầu để khớp giờ.
- **Review** mọi PR chạm luật trong 24 giờ.
- **Change Request:** giữ sổ `docs/spec/changes.md`.

## 6. Khi bị chặn

- Thiếu thứ ở dòng "Cần có": đừng ngồi chờ, làm trước trên dữ liệu mẫu theo hợp đồng ở spec mục 6.
- Quá hạn một ngày vẫn chưa có: nêu ngay ở standup. Ai giữ thứ đó: `docs/plan/timeline.md` mục 5.3.
- Thấy thiết kế sai: dừng lại, ghi rõ vấn đề, đề xuất cách sửa qua Change Request (spec mục 12). Không tự đổi hợp đồng dữ liệu.
