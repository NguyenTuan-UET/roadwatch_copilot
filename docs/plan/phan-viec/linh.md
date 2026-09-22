# Việc của Linh

> **Vai trò:** làm toàn bộ giao diện (dashboard), vận hành dữ liệu video, và gán nhãn.
> **Thời gian cần:** khoảng 35 / 39 / 44 / 42 / 29 giờ cho tuần 1 → 5.
> File này chỉ nói về việc của bạn. Lịch chung và ai giữ việc nào: `docs/plan/timeline.md`. Hai file lệch nhau thì theo timeline.

## Thuật ngữ trong file này

| Từ | Nghĩa |
|---|---|
| WP-xx | Gói việc số xx trong kế hoạch chung (`docs/plan/timeline.md` mục 4). Mỗi WP là một issue trên GitHub Project |
| TASK-0xx | Một bước nhỏ trong plan M1 (`docs/plan/2026-09-21-m1-skeleton.md`), có sẵn code và lệnh kiểm tra |
| PH1…PH11 | 11 phân hệ của hệ thống. Bản đồ ở `docs/architecture_diagram.md` mục 0 |
| M0…M7 | Mốc nội bộ: M0 duyệt spec 24/09, M1 khung chạy 27/09, M2 luật lõi 04/10, M3 đóng băng 11/10, M4 khóa nhãn test 18/10, M5 chạy test 19/10, M7 khóa code 25/10 |
| CP1, CP2 | Hai buổi demo với ban tổ chức: CP1 ngày 14/10 (80%), CP2 ngày 23/10 (100%, sẵn sàng production) |
| Spec, FR, AC | Spec quy định hệ thống phải làm gì (`docs/spec/trafficeye-spec.md`). FR-xxx là một yêu cầu; AC là tiêu chí nghiệm thu. Các trang giao diện là FR-UI-1…9 |
| Hợp đồng dữ liệu, API | Định dạng đã chốt cho sự kiện (spec mục 6.3) và API trung tâm (spec mục 6.5). Giao diện gọi đúng các API này |
| Dữ liệu mẫu | Dữ liệu giả viết đúng theo hợp đồng, để dựng trang trước khi API thật xong |
| SSE, vé SSE | SSE: trung tâm đẩy thông báo mới lên trình duyệt ngay. Vé SSE: mã dùng một lần, sống ngắn, để mở kết nối SSE |
| Duyệt 2 bước | Bước 1: điều hành viên xem bản đã che biển số, xác nhận hoặc bác bỏ. Bước 2: CSGT xem biển số xe vi phạm và quyết định |
| Ứng viên vi phạm | Ca hệ thống nghi là vi phạm. Phải qua người duyệt mới thành vi phạm |
| Nhật ký nối băm | Nhật ký mà mỗi dòng chứa mã băm của dòng trước. Sửa một dòng là bị lộ; trang nhật ký có nút kiểm chuỗi |
| Heartbeat, trạng thái mong muốn | Heartbeat: tín hiệu "tôi còn sống" của camera. Trạng thái mong muốn: cấu hình trung tâm muốn camera chạy, kể cả chế độ điều khiển tay |
| "Đang gửi bù" | Trạng thái camera vừa có mạng lại và đang gửi dữ liệu còn tồn |
| LOS, tràn hàng chờ | LOS: mức phục vụ của nút giao, từ A (thông thoáng) tới F (tắc). Tràn hàng chờ: hàng xe ở nút sau kéo dài tới tận nút trước |
| CFR 15 FPS | Video được chuyển về đúng 15 khung hình mỗi giây, không dao động. Điện thoại thường quay với tốc độ khung thay đổi |
| Manifest, SHA-256 | Manifest: file CSV liệt kê các video (mã, camera, thời lượng, SHA-256). SHA-256: "dấu vân tay" của file |
| Tập dev, tập test | Tập dev: video để phát triển. Tập test: video quay sau ngày đóng băng (11/10), chỉ dùng để đo một lần |
| Gán nhãn, gán nhãn mù | Xem video và ghi lại sự kiện thật để so với hệ thống. Gán mù: không xem kết quả hệ thống |
| `ambiguous` | Nhãn cho ca không chắc, kèm ghi chú lý do. Không đoán |
| Kappa | Số đo hai người gán nhãn đồng ý với nhau đến đâu. 1 là khớp hoàn toàn; cần từ 0,8 trở lên |
| OCR | Đọc chữ trên biển số. Hai công cụ cần so: fast-plate-ocr và PaddleOCR |
| Agent | Chương trình dùng LLM soạn báo cáo và giải thích ứng viên. Người duyệt rồi mới phát hành |
| PR, review, CI | PR: yêu cầu gộp code. Review: người khác đọc và duyệt. CI: máy tự chạy test; CI xanh mới được gộp |
| DoD | Điều kiện "xong" chung cho mọi việc (spec mục 9.2) |

## 1. Bạn phụ trách gì

| Phân hệ | Phần của bạn |
|---|---|
| PH8 · Giao diện | Toàn bộ dashboard: số đếm, duyệt bước 1, bản đồ, sức khỏe camera, màn CSGT, xác minh, nhật ký, trang Tuyến, trang báo cáo, trợ lý giải thích |
| PH6 · Trung tâm | Xuất hồ sơ vi phạm (PDF + JSON) |
| PH4 · Bằng chứng và riêng tư | Chọn công cụ OCR (thử nghiệm và so sánh) |
| PH10 · Đánh giá và dữ liệu | Script lập manifest; chuyển video về 15 FPS; gán nhãn dev chính; công cụ đo tuyến; gán nhãn mù tập test |
| PH11 · Vận hành và hiệu năng | GitHub Project và quy tắc làm việc trên repo |
| — Hỗ trợ | Đặt lịch và ghi chép phỏng vấn người dùng |

## 2. Đọc gì trước khi bắt đầu

| Thứ tự | Đọc | Để biết |
|---|---|---|
| 1 | `README.md` | Sản phẩm làm gì (10 phút) |
| 2 | `docs/architecture_diagram.md` mục 0, 1 và 3 | Hệ thống gồm 11 phân hệ nào; luồng duyệt 2 bước |
| 3 | Spec mục 3 và 4.8 | Ai được làm gì; yêu cầu của từng trang giao diện |
| 4 | Spec mục 6.3 và 6.5 | Dữ liệu và API mà giao diện dùng |
| 5 | `docs/gate1/wireframe-ui-flow.md` | Wireframe đã nộp ở Gate 1 |
| 6 | Plan M1: phần C (TASK-014…016), TASK-018, TASK-021 | Hướng dẫn code tuần 1 |
| 7 | `docs/eval/protocol.md` mục 2.6, 5 và 13.8 | Chuẩn hóa video; quy tắc gán nhãn; bảng đo tuyến |

## 3. Quy tắc bắt buộc với bạn

1. **Khi đi quay buổi S5 (03/10) và S6 (14/10): chỉ bấm máy**, giao thẻ nhớ ngay cho người giữ tập test, không xem lại.
2. **Không chạy hệ thống trên video test**, và không xem kết quả hệ thống trên tập test trước khi nhãn được khóa (18/10).
3. **Gán nhãn đúng theo hướng dẫn gán nhãn.** Ca nào không chắc thì gán `ambiguous` kèm ghi chú, không đoán.
4. **15–18/10 gán nhãn toàn thời gian.** Mọi việc giao diện cho CP1 phải xong trước 14/10.
5. **Mọi trang giao diện phải đạt:** tiếng Việt; hiển thị tốt từ 360 px; có dark mode; có trạng thái đang tải, lỗi, rỗng; PR kèm ảnh chụp màn hình trên máy tính và điện thoại.
6. **Không ngồi chờ API:** dựng trang trên dữ liệu mẫu theo hợp đồng trước, khi API có thì nối vào.

## 4. Việc theo thứ tự thời gian

Mỗi việc ghi: **Làm** (các bước), **Cần có** (thứ phải có trước, và ngày dự kiến có), **Nộp** (kết quả), **Xong khi** (cách kiểm tra). Dấu ⚠ đánh dấu việc mà người khác đang chờ: việc này trễ thì cả team trễ.

### Tuần 1 (22–27/09)

#### Việc 1 · Đọc spec phần giao diện và API — hạn 24/09 · WP-32
- **Làm:** đọc spec mục 4.8 và 6.5. Ghi câu hỏi nếu có.
- **Nộp:** câu hỏi gửi trước buổi M0.

#### Việc 2 · GitHub Project — hạn 25/09 · WP-07 · PH11
- **Làm:** tạo GitHub Project có các trường Spec ID, Size, Checkpoint. Mỗi WP một issue, ghi người làm theo timeline mục 4. Viết quy tắc đặt tên nhánh và PR. Viết chính sách không commit video thô (M-06).
- **Cần có:** quyền quản trị repo.
- **Xong khi:** mọi WP đều có issue.

#### Việc 3 · Đặt lịch phỏng vấn — hạn 25/09 · WP-08
- **Làm:** giữ danh sách liên hệ; đặt lịch ít nhất một cuộc phỏng vấn trước 04/10.
- **Cần có:** bộ câu hỏi phỏng vấn (có từ 25/09).

#### Việc 4 · Script lập manifest — hạn 25/09 · TASK-018 · PH10
- **Làm:** làm theo TASK-018 trong plan M1 (có sẵn code và test). Script đọc một thư mục video, tính SHA-256, ghi vào manifest CSV, từ chối video không phải 15 FPS cố định.
- **Nộp:** `scripts/make_manifest.py`, `tests/test_make_manifest.py`.
- **Xong khi:** lệnh "Validate" của TASK-018 ra đúng "Expected".

#### Việc 5 · Khung dashboard — hạn 27/09 · WP-06 · PH8
Nên bắt đầu Việc 9 (màn duyệt bước 1) trên dữ liệu mẫu ngay từ 24/09, song song với việc này.
- **Làm:** làm lần lượt TASK-014 → TASK-016 và TASK-021 trong plan M1: khung Next.js, trang số đếm, trang cảnh báo tạm, CI cho dashboard, mục chạy thử M1 trong README.
- **Cần có:** API dashboard (trong khung trung tâm M1, có từ 27/09). Trước đó dùng dữ liệu mẫu.
- **Nộp:** mỗi TASK một commit.
- **Xong khi:** mọi lệnh "Validate" của các TASK trên ra đúng "Expected".

#### Việc 6 · Gán thử clip S1 — 27/09 · WP-09 · PH10
- **Làm:** gán một clip của buổi quay S1 theo hướng dẫn gán nhãn bản 0, làm người gán thứ hai để tính kappa.
- **Cần có:** hướng dẫn gán nhãn bản 0; clip S1 (26/09).
- **Xong khi:** đã có kappa. **Đây là điểm kiểm tra của bạn:** kappa cần từ 0,8 trở lên (xem mục 5).

### Tuần 2 (28/09–04/10)

#### Việc 7 · Chuyển video S1, S2 về 15 FPS và lập manifest dev — hạn 30/09 · WP-03 · PH10
- **Làm:** chuyển video S1, S2 về 15 FPS cố định bằng lệnh ffmpeg ở plan M1 (mục Global Constraints). Chạy `scripts/make_manifest.py` để lập `eval/manifests/dev.csv`.
- **Cần có:** video của buổi quay S1 và S2.
- **Xong khi:** mọi file có SHA-256 trong manifest. ⚠ Tập khung đo mAP và việc gán nhãn dev chờ việc này.

#### Việc 8 · Chọn công cụ OCR — hạn 01/10 · WP-37 · PH4
- **Làm:** so sánh fast-plate-ocr và PaddleOCR trên ít nhất 100 ảnh biển số Việt Nam lấy từ bộ dữ liệu công khai, có cả biển 2 dòng. Đo tỉ lệ đọc đúng hoàn toàn và tốc độ.
- **Nộp:** bảng so sánh và công cụ được chọn, ghi vào issue WP-37.
- **Xong khi:** đã chọn công cụ. ⚠ Phần tích hợp OCR chờ kết quả này.

#### Việc 9 · Màn duyệt bước 1 — hạn 04/10 · WP-14 · PH8
- **Làm:** hàng đợi ứng viên; nhận ứng viên mới qua SSE bằng vé ngắn hạn; mất kết nối thì nối lại và tải lại hàng đợi; xác nhận hoặc bác bỏ bằng bàn phím, bác bỏ phải chọn mã lý do.
- **Cần có:** API ứng viên và vé SSE (WP-13, có từ 04/10). Trước đó dùng dữ liệu mẫu.
- **Xong khi:** đạt FR-HITL-1 AC1–AC3.

#### Việc 10 · Ghi chép phỏng vấn — 04/10 · WP-08
- **Nộp:** biên bản buổi phỏng vấn.

#### Việc 11 · Bản đồ camera và số đếm theo làn — hạn 06/10 · WP-36 · PH8
- **Làm:** bản đồ các camera; số đếm theo từng làn. Khi không có Internet thì bản đồ hiện bằng ảnh tĩnh.
- **Cần có:** sự kiện đếm theo làn (WP-35, có từ 02/10).
- **Xong khi:** có ảnh chụp trên máy tính và điện thoại.

#### Việc 12 · Gán nhãn dev — hạn 08/10 · WP-15 · PH10
- **Làm:**
  1. Chuyển video S3, S4 về 15 FPS và thêm vào manifest dev.
  2. Gán chính các video của S1, S2, S4.
  3. Gán lại 30% số video S3 (do người gán chính còn lại gán) để tính kappa.
- **Cần có:** hướng dẫn gán nhãn.
- **Xong khi:** `evaluate.py` đọc được mọi file nhãn; có kappa theo từng loại. ⚠ Việc chỉnh ngưỡng (07–10/10) cần nhãn dev.

### Tuần 3 (05–11/10)

#### Việc 13 · Công cụ đo tuyến — hạn 09/10 · WP-56 · PH10
- **Làm:** viết `scripts/evaluate_corridor.py`, đo đúng các cột ở bảng protocol mục 13.8: chu kỳ đèn, thời gian xanh, tốc độ thoát xe, số xe thoát, chu kỳ thất bại, tràn hàng chờ.
- **Cần có:** sự kiện `signal_cycle` (WP-53, có từ 07/10); hợp đồng sự kiện tuyến (spec mục 6.3).
- **Xong khi:** chạy được trên dữ liệu dev; có bảng so khớp với nhãn. ⚠ Việc chỉnh ngưỡng tuyến cần công cụ này.

#### Việc 14 · Trang sức khỏe camera — hạn 10/10 · WP-40 (phần giao diện) · PH8
- **Làm:** hiện trạng thái từng camera theo bảng ở spec mục 6.7, kể cả "đang gửi bù"; nút bật/tắt chế độ điều khiển tay.
- **Cần có:** API sức khỏe và trạng thái mong muốn (WP-40, có từ 10/10). Trước đó dùng dữ liệu mẫu.
- **Xong khi:** đạt FR-UI-5.

#### Việc 15 · Màn CSGT, xác minh, thống kê, nhật ký — hạn 12/10 · WP-19 · PH8
Bắt đầu trên dữ liệu mẫu từ 07/10.
- **Làm:** màn duyệt bước 2 của CSGT; trang xác minh bằng chứng; trang thống kê; trang nhật ký (FR-UI-8) hiện các lượt CSGT xem bản CSGT, có nút kiểm chuỗi nối băm.
- **Cần có:** luồng duyệt của CSGT ở trung tâm (WP-18, có từ 12/10).
- **Xong khi:** chạy trọn luồng duyệt 2 bước trên giao diện; nút kiểm chuỗi báo đúng.

#### Việc 16 · Trang Tuyến — hạn 13/10 · WP-55 · PH8
- **Làm:** bản đồ tuyến tô màu theo mức ùn tắc, kèm mũi tên tràn hàng chờ; bản đồ nhiệt nút × thời gian (ô 5 phút); thẻ hiệu năng từng nút.
- **Cần có:** API phân tích tuyến (WP-54, có từ 10/10).
- **Xong khi:** đạt FR-UI-7 AC1–AC3.

### Tuần 4 (12–18/10)

#### Việc 17 · Trang báo cáo của Agent — hạn 13/10 · WP-42 (phần giao diện) · PH8
- **Làm:** hiện bản nháp báo cáo, người duyệt, lịch sử báo cáo (FR-UI-6).
- **Cần có:** Agent báo cáo (WP-42, có từ 13/10). Trước đó dùng dữ liệu mẫu.
- **Xong khi:** duyệt và phát hành được một báo cáo từ giao diện.

#### Việc 18 · CP1 — 14/10
- **Làm:** chạy phần giao diện trong buổi demo.

#### Việc 19 · Quay tập test chính (S6) — chiều 14/10
- **Làm:** chỉ bấm máy; giao thẻ nhớ ngay cho người giữ tập test; không xem lại.

#### Việc 20 · Gán nhãn mù tập test — 15–18/10 · WP-22 · PH10
- **Làm:** gán nhãn theo hướng dẫn, độc lập với người gán thứ hai.
- **Cần có:** video test và hướng dẫn (nhận ngày 15/10).
- **Nộp:** file nhãn, trước tối 17/10.

### Tuần 5 (19–25/10)

#### Việc 21 · Giao diện trợ lý giải thích — hạn 21/10 · WP-48 (phần giao diện) · PH8
- **Làm:** khung giải thích ứng viên trên màn duyệt; ô hỏi đáp số liệu nếu làm FR-AGT-3. Dựng trên dữ liệu mẫu trước.
- **Cần có:** trợ lý giải thích phần Agent (WP-48, có từ 21/10).
- **Xong khi:** đạt FR-AGT-2 AC.

#### Việc 22 · Tài liệu — hạn 22/10 · WP-30
- **Làm:** ảnh chụp màn hình và hướng dẫn dùng giao diện.

#### Việc 23 · Xuất hồ sơ vi phạm — hạn 23/10 · WP-45 · PH6, PH8
- **Làm:** xuất hồ sơ PDF + JSON, có mã băm, chữ ký, link xác minh; mở được khi không có mạng.
- **Cần có:** luồng duyệt của CSGT (WP-18).
- **Xong khi:** đạt FR-EXP-1 AC.

#### Việc 24 · CP2 — 23/10
- **Làm:** chạy phần giao diện trong buổi demo.

#### Việc 25 · Tổng duyệt — 25/10 · WP-29

## 5. Điểm kiểm tra: kappa ngày 27/09

Nếu kappa gán thử của bạn thấp hơn 0,8:
1. Học lại hướng dẫn gán nhãn, rồi gán lại clip thử.
2. Nếu vẫn thấp: đổi cách chia gán nhãn. Bạn gán các nhãn đếm (số xe thoát mỗi chu kỳ, hàng chờ), vốn ít phải phán đoán; các sự kiện vi phạm do người gán còn lại gán chính.

## 6. Việc lặp lại

- **Mỗi ngày:** standup 15 phút; cập nhật `WORKLOG.md`.
- **Tối Chủ nhật** (27/09, 04/10, 11/10, 18/10): demo nội bộ.
- **Đi quay:** S1 (26/09 chiều), S2 (28/09 cao điểm chiều), S4 (02/10 tối), S5 (03/10 chiều, tập test dự phòng: chỉ bấm máy), S6 (Việc 19). Mỗi máy quay màn hình time.is lúc bắt đầu để khớp giờ.

## 7. Khi bị chặn

- Thiếu thứ ở dòng "Cần có": đừng ngồi chờ, dựng trên dữ liệu mẫu theo hợp đồng ở spec mục 6.
- Quá hạn một ngày vẫn chưa có: nêu ngay ở standup. Ai giữ thứ đó: `docs/plan/timeline.md` mục 5.3.
- Thấy thiết kế sai: dừng lại, ghi rõ vấn đề, đề xuất cách sửa qua Change Request (spec mục 12). Không tự đổi hợp đồng dữ liệu.
