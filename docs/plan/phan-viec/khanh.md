# Việc của Khánh

> **Vai trò:** người thứ hai về kỹ thuật, và **người giữ tập test**. Bạn viết hai luật vi phạm, phần truyền dữ liệu và quản lý thiết bị, Agent, và chịu trách nhiệm toàn bộ khâu đo cuối cùng.
> **Thời gian cần:** khoảng 31 / 40 / 44 / 46 / 32 giờ cho tuần 1 → 5. Đây là mức tải cao nhất team.
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
| Hợp đồng dữ liệu | Định dạng đã chốt cho cấu hình, sự kiện và API (spec mục 6). Đổi hợp đồng phải qua Change Request |
| Edge, trung tâm | Edge: máy ở nút giao, chạy AI trên video. Trung tâm: FastAPI + PostgreSQL, nhận dữ liệu từ edge |
| Outbox | Hàng đợi SQLite trên edge. Dữ liệu nằm đó tới khi trung tâm xác nhận đã nhận, nên mất mạng không mất dữ liệu |
| Heartbeat | Tín hiệu "tôi còn sống" edge gửi định kỳ |
| Trạng thái mong muốn | Cấu hình trung tâm muốn edge chạy. Edge hỏi mỗi 10 giây rồi tự áp dụng (spec mục 6.7) |
| OTA, canary | OTA: cập nhật phần mềm cho edge từ xa. Canary: cập nhật thử một máy trước, lỗi thì tự quay lại bản cũ |
| MQTT, Last Will | Kênh nhắn tin nhẹ, ở đây chỉ để báo edge "có thay đổi". Last Will: tin broker tự gửi khi edge mất kết nối |
| `signal_cycle` | Sự kiện edge gửi sau mỗi chu kỳ đèn: thời gian xanh, vàng, đỏ; số xe đến, số xe thoát; hàng chờ |
| Luật tất định | Luật viết bằng điều kiện rõ ràng về hình học và thời gian. AI không quyết định vi phạm |
| Ứng viên vi phạm | Ca hệ thống nghi là vi phạm. Phải qua người duyệt mới thành vi phạm |
| Lớp ngữ cảnh | Bước chạy trước luật, gắn lý do loại trừ (xe ưu tiên, đèn không rõ…) |
| Mã loại trừ | Lý do một ca trông giống vi phạm nhưng không phải: W1–W8 (ngược chiều), L1–L8 (sai làn). Danh mục ở `docs/spec/false-positives.md` |
| WW, LN | Đi ngược chiều; sai làn. Sai làn có 3 kiểu: LN-a (làn dành cho loại xe khác), LN-b (đè vạch liền), LN-c (đi sai hướng mũi tên) |
| Ngưỡng, đóng băng | Ngưỡng: các con số trong luật. Đóng băng (11/10): khóa luật và ngưỡng, sau đó không đổi |
| Tập dev, tập test | Tập dev: video để phát triển. Tập test: video quay sau ngày đóng băng, chỉ dùng để đo một lần |
| Người giữ tập test | Người duy nhất cầm video test, niêm phong nó và chạy đo (protocol gọi là custodian). Ở dự án này là bạn |
| Niêm phong | Tính SHA-256 của mọi file và giữ 2 bản sao mã hóa ở 2 nơi, để chứng minh video không bị sửa hay xem trộm |
| SHA-256, pHash | SHA-256: "dấu vân tay" của file. pHash: dấu vân tay theo nội dung ảnh, để phát hiện video test trùng video dev |
| Manifest | File CSV liệt kê các video: mã, camera, thời lượng, SHA-256 |
| Gán nhãn, gán nhãn mù | Xem video và ghi lại sự kiện thật để so với hệ thống. Gán mù: không xem kết quả hệ thống |
| Phân xử, `ambiguous` | Phân xử: quyết định khi hai người gán nhãn khác nhau. `ambiguous`: nhãn cho ca không chắc, kèm lý do |
| Kappa | Số đo hai người gán nhãn đồng ý với nhau đến đâu. 1 là khớp hoàn toàn; cần từ 0,8 trở lên |
| Precision, Wilson 95% | Precision: trong các cảnh báo, bao nhiêu phần trăm là vi phạm thật. Wilson 95%: khoảng tin cậy đi kèm |
| Agent, `interrupt()` | Agent: chương trình LangGraph dùng LLM soạn báo cáo. `interrupt()`: dừng lại chờ người duyệt trước khi phát hành |
| Tag | Nhãn git đánh dấu một commit, ví dụ `labels-lock-test-v1` |
| PR, review, CI | PR: yêu cầu gộp code. Review: người khác đọc và duyệt. CI: máy tự chạy test; CI xanh mới được gộp |
| DoD | Điều kiện "xong" chung cho mọi việc (spec mục 9.2) |

## 1. Bạn phụ trách gì

| Phân hệ | Phần của bạn |
|---|---|
| PH3 · Luật vi phạm | Luật đi ngược chiều; luật sai làn đủ 3 kiểu |
| PH4 · Bằng chứng và riêng tư | Phát hiện và che biển số |
| PH2 · Đèn tín hiệu và cấu hình cảnh | Đo chu kỳ đèn trên edge (`signal_cycle`) |
| PH5 · Truyền dữ liệu và quản lý thiết bị | Outbox và gửi dữ liệu (trong khung M1); heartbeat; trạng thái mong muốn; OTA; MQTT |
| PH6 · Trung tâm | Khung trung tâm M1: lưu sự kiện, API nhận sự kiện, API dashboard, Docker Compose |
| PH9 · Agent AI | Agent báo cáo ca trực; trợ lý giải thích ứng viên (phần Agent) |
| PH10 · Đánh giá và dữ liệu | Hướng dẫn gán nhãn; `scripts/evaluate.py`; gán nhãn dev; **giữ tập test**, phân xử nhãn, chạy test một lần; báo cáo đánh giá |

## 2. Đọc gì trước khi bắt đầu

| Thứ tự | Đọc | Để biết |
|---|---|---|
| 1 | `README.md` | Sản phẩm làm gì (10 phút) |
| 2 | `docs/architecture_diagram.md` mục 0–3 | Hệ thống gồm 11 phân hệ nào, dữ liệu đi ra sao |
| 3 | Spec mục 6.3, 6.5, 6.6, 6.7, và mục 9 | Hợp đồng sự kiện, API, giao diện luật, kênh điều khiển; thế nào là xong |
| 4 | Spec mục 7.2, 7.3 và `docs/spec/false-positives.md` mục 3, 4 | Hai luật của bạn và các ca dễ báo nhầm |
| 5 | `docs/eval/protocol.md` (cả file) | Bạn giữ tập test nên cần nắm toàn bộ giao thức đo |
| 6 | Plan M1: phần B (TASK-008…013) và TASK-019 | Hướng dẫn code tuần 1 |

## 3. Quy tắc bắt buộc với bạn

1. **Không chỉnh ngưỡng** và không tham gia việc chỉnh ngưỡng (WP-20). Luật của bạn dùng ngưỡng khởi điểm ở spec mục 6.2; giá trị cuối do người chỉnh ngưỡng chọn.
2. **Trước 11/10 không mở video test**, vì tới 06/10 bạn còn viết luật. Với tập test dự phòng (S5, 03/10): nhận thẻ nhớ, tính SHA-256, giữ 2 bản sao mã hóa ở 2 nơi (M-07), không mở.
3. **Sau đóng băng (11/10) không sửa code luật ngược chiều và sai làn nữa**, vì từ đây bạn mở tập test. Thấy lỗi thì mở issue cho người chỉnh ngưỡng.
4. **Chạy test đúng một lần** (19/10). Chạy lại trước giám khảo phải dùng đúng config đã đóng băng; log khi đó ghi `rerun_same_config`.
5. **Khi phân xử nhãn:** không chắc thì gán `ambiguous` kèm lý do (protocol mục 4.5). Cách này không làm phồng precision.
6. **14–21/10 không được vắng:** chỉ bạn được chạy test, không ai thay được.

## 4. Việc theo thứ tự thời gian

Mỗi việc ghi: **Làm** (các bước), **Cần có** (thứ phải có trước, và ngày dự kiến có), **Nộp** (kết quả), **Xong khi** (cách kiểm tra). Dấu ⚠ đánh dấu việc mà người khác đang chờ: việc này trễ thì cả team trễ.

### Tuần 1 (22–27/09)

#### Việc 1 · Review spec phần luật và đánh giá — hạn 24/09 · WP-32
- **Làm:** đọc spec mục 7 (luật) và mục 4.12 (đánh giá). Ghi chỗ thiếu hoặc mâu thuẫn.
- **Nộp:** góp ý gửi trước buổi M0.

#### Việc 2 · Chọn tuyến 3 nút giao — hạn 25/09 · WP-02
- **Làm:** đi khảo sát cùng PO. Phần của bạn: kiểm tra tiêu chí cho luật ngược chiều và sai làn (timeline tuần 1, "Tiêu chí chọn tuyến 3 nút", nhóm "Tiêu chí vi phạm").
- **Xong khi:** tuyến được chọn có đủ chỗ để quan sát được ca ngược chiều và cả 3 kiểu sai làn.

#### Việc 3 · Khung trung tâm M1 — hạn 27/09 · WP-05 · PH5, PH6
- **Làm:** làm lần lượt TASK-008 → TASK-013 trong plan M1: outbox, gửi dữ liệu, lớp lưu dữ liệu, API nhận sự kiện, API dashboard, Docker Compose. Mỗi TASK có sẵn code, lệnh kiểm tra và kết quả mong đợi. TASK-001 (hợp đồng sự kiện v1, 22/09) làm cặp với người làm khung edge.
- **Nộp:** mỗi TASK một commit.
- **Xong khi:** mọi lệnh "Validate" của TASK-008…013 ra đúng "Expected". ⚠ Dashboard và API đăng nhập đang chờ khung này.

#### Việc 4 · Hướng dẫn gán nhãn — hạn 27/09 · WP-09 · PH10
- **Làm:**
  1. Viết hướng dẫn gán nhãn bản 0 trong `docs/eval/`, dựa trên `docs/spec/false-positives.md`. Nội dung cần có: liệt kê ở timeline tuần 1, "Nội dung hướng dẫn gán nhãn".
  2. Gán thử một clip của buổi quay S1 cùng người gán thứ hai.
  3. Tính kappa; đo số phút công cho mỗi phút video; chốt số giờ video cần quay.
- **Cần có:** clip S1 (26/09).
- **Xong khi:** kappa ≥ 0,8. Nếu thấp hơn: sửa hướng dẫn, gán lại. ⚠ Người gán nhãn đang chờ hướng dẫn này.

#### Việc 5 · Viết `scripts/evaluate.py` — hạn 27/09 · TASK-019 · PH10
- **Làm:**
  1. Viết plan TDD bằng `/write-plan`, theo các mục protocol ghi trong TASK-019 của plan M1.
  2. Viết script mới (nhóm chưa có script này): đọc manifest và nhãn, kiểm `video_sha256`, khớp cảnh báo với nhãn, tính precision kèm Wilson 95%, ghi log mỗi lần chạy.
  3. Viết `tests/test_evaluate.py`, gồm 3 test bắt buộc ghi trong TASK-019.
- **Nộp:** `scripts/evaluate.py`, `tests/test_evaluate.py`.
- **Xong khi:** `pytest tests/test_evaluate.py` xanh; chạy `--split dev` trên dữ liệu giả in đúng định dạng ở protocol mục 10.3. ⚠ Luật vượt đèn đỏ và việc gán nhãn dev cần script này để kiểm kết quả.

### Tuần 2 (28/09–04/10)

#### Việc 6 · Luật đi ngược chiều — hạn 03/10 · WP-33 · PH3
- **Làm:** viết luật theo spec mục 7.2 và `docs/spec/false-positives.md` mục 3, dùng khung luật chung. Mỗi ca bị loại ghi đúng mã W1–W8. Viết test cho từng điều kiện và từng mã.
- **Cần có:** khung luật và lớp ngữ cảnh (có từ 27/09); máy trạng thái đèn và cấu hình cảnh v2 (WP-10, có từ 30/09). Chưa có thì làm trên dữ liệu giả theo spec mục 6.6.
- **Nộp:** PR có test; người giữ luật review.
- **Xong khi:** đạt FR-VIO-WW AC1 trên clip dev.

#### Việc 7 · Niêm phong tập test dự phòng (S5) — 03/10 · WP-16 · PH10
- **Làm:** đi quay buổi S5 (chiều 03/10). Nhận thẻ nhớ của cả tổ quay; tính SHA-256 mọi file; lưu 2 bản sao mã hóa ở 2 nơi. **Không mở video.**
- **Xong khi:** có SHA-256 của mọi file; 2 bản sao ở 2 nơi.

#### Việc 8 · Phát hiện và che biển số — hạn 04/10 · WP-12 · PH4
- **Làm:** gắn detector biển số; che biển số trên bản gửi điều hành viên. Làm sẵn phương án dự phòng: che nửa dưới bbox của xe.
- **Cần có:** khung edge M1 (WP-04).
- **Xong khi:** bộ ảnh kiểm tra không còn lộ biển số nào. ⚠ Gói bằng chứng có ký cần phần này.

#### Việc 9 · Luật sai làn đủ 3 kiểu — hạn 06/10 · WP-34 · PH3
- **Làm:** viết luật LN-a, LN-b, LN-c theo spec mục 7.3 và `docs/spec/false-positives.md` mục 4. Mỗi ca bị loại ghi đúng mã L1–L8. Viết test cho từng kiểu và từng mã.
- **Cần có:** như Việc 6.
- **Nộp:** PR có test; người giữ luật review.
- **Xong khi:** cả 3 kiểu bật được trên clip dev. ⚠ Việc chỉnh ngưỡng (07–10/10) cần luật này.

#### Việc 10 · Gán nhãn dev — hạn 08/10 · WP-15 · PH10
- **Làm:** gán chính các video của buổi S3. Gán lại 30% số video mà người gán chính còn lại đã gán (S1, S2, S4) để tính kappa.
- **Cần có:** hướng dẫn gán nhãn (Việc 4).
- **Xong khi:** `evaluate.py` đọc được mọi file nhãn; có kappa theo từng loại. ⚠ Việc chỉnh ngưỡng cần nhãn dev.

### Tuần 3 (05–11/10)

#### Việc 11 · Đo chu kỳ đèn trên edge — hạn 07/10 · WP-53 · PH2
- **Làm:** gửi sự kiện `signal_cycle` v1 sau mỗi chu kỳ (spec mục 6.3): thời gian xanh, vàng, đỏ; số xe đến và thoát; hàng chờ lớn nhất; hàng chờ còn tồn cuối chu kỳ; tốc độ thoát xe khi hàng chờ bắt đầu chạy.
- **Cần có:** máy trạng thái đèn (WP-10).
- **Xong khi:** đạt FR-DEN-4 AC1–AC3; đã kiểm kích thước sự kiện và lưu lượng qua outbox. ⚠ Phân tích tuyến và việc chỉnh ngưỡng chờ việc này; trễ một ngày là mất một ngày chỉnh ngưỡng.

#### Việc 12 · Heartbeat và trạng thái mong muốn — hạn 10/10 · WP-40 · PH5
- **Làm:** heartbeat từ edge; API `GET desired`; edge hỏi mỗi 10 giây và tự áp dụng; nút bật/tắt chế độ điều khiển tay; trạng thái "đang gửi bù" khi outbox còn tồn. Phần giao diện trang sức khỏe do người làm giao diện làm.
- **Cần có:** API đăng nhập (WP-13); khung luật (WP-11).
- **Xong khi:** đạt FR-DEV-1 AC1–AC4. ⚠ Chạy 3 camera cùng lúc cần việc này.

#### Việc 13 · Điều hành buổi demo tối 11/10
- **Làm:** điều hành buổi demo nội bộ thay PO (tuần này PO chỉnh ngưỡng). PO vẫn ký nghiệm thu.

#### Việc 14 · Agent báo cáo — hạn 13/10 (bắt đầu từ 09/10) · WP-42 · PH9
- **Làm:** Agent soạn báo cáo ca trực và báo cáo sự cố. Công cụ của Agent chỉ đọc số liệu tổng hợp, không trả biển số hay ảnh. Dùng `interrupt()` để chờ người duyệt. Có chế độ không LLM (sinh báo cáo theo mẫu). Giao diện trang báo cáo do người làm giao diện làm.
- **Cần có:** API đăng nhập (WP-13); phân tích tuyến (WP-54, có từ 10/10).
- **Xong khi:** đạt FR-AGT-1 AC1–AC3.

### Tuần 4 (12–18/10)

#### Việc 15 · Quay tập test chính (S6) — chiều 14/10 · WP-21 · PH10
- **Làm:** đi quay; nhận thẻ nhớ; tính SHA-256; kiểm tra trùng lặp với video dev bằng SHA-256 và pHash; lập manifest test.
- **Xong khi:** manifest test đủ 3 nút.

#### Việc 16 · Giao video test cho người gán nhãn — 15/10 · WP-22
- **Làm:** giao video test và hướng dẫn cho 2 người gán nhãn mù.
- **Xong khi:** cả hai đã nhận.

#### Việc 17 · OTA và MQTT — hạn 18/10 · WP-46 · PH5
- **Làm:** bản phát hành có ký; canary; tự quay lại bản cũ khi lỗi. Kênh MQTT: Mosquitto có TLS và ACL; Last Will; thông báo `desired` (spec mục 6.7).
- **Cần có:** Việc 12.
- **Xong khi:** đạt FR-OTA-1 AC1–AC3 và FR-DEV-2 AC1–AC3. ⚠ Live URL cần phần broker này.

#### Việc 18 · Phân xử và khóa nhãn test (M4) — 17–18/10 · WP-22 · PH10
- **Làm:** so nhãn của 2 người gán; phân xử các chỗ khác nhau; tính kappa; khóa nhãn bằng tag `labels-lock-test-v1`.
- **Cần có:** nhãn của 2 người gán (tối 17/10).
- **Xong khi:** tag đã đẩy lên GitHub.

### Tuần 5 (19–25/10)

#### Việc 19 · Chạy test một lần (M5) — 19/10 · WP-27 · PH10
- **Làm:** chạy `scripts/evaluate.py --split test` với config đã đóng băng, đúng một lần.
- **Xong khi:** log `eval/logs/test_runs.jsonl` ghi `status: fresh`.

#### Việc 20 · Báo cáo đánh giá — hạn 21/10 · WP-27 · PH10
- **Làm:** điền `eval/results/report.md` theo mẫu `docs/eval/report-template.md`: precision từng loại vi phạm (sai làn báo riêng 3 kiểu), mAP, đếm theo làn, đo chu kỳ đèn và sự kiện tuyến, tỉ lệ che lọt, OCR, hiệu năng.
- **Xong khi:** đủ mọi mục của mẫu. ⚠ Slide cuối dùng số của báo cáo này.

#### Việc 21 · Trợ lý giải thích ứng viên (phần Agent) — hạn 21/10 · WP-48 · PH9
- **Làm:** Agent giải thích vì sao một ca thành ứng viên; hỏi đáp số liệu nếu làm FR-AGT-3. Phần giao diện do người làm giao diện làm.
- **Cần có:** Việc 14.
- **Xong khi:** đạt FR-AGT-2 AC.

#### Việc 22 · Tài liệu — hạn 22/10 · WP-30
- **Làm:** viết phần đánh giá và quy trình giữ tập test trong tài liệu dự án.

#### Việc 23 · CP2 — 23/10
- **Làm:** chạy lại `evaluate.py` trước giám khảo bằng đúng config đã đóng băng.
- **Xong khi:** log ghi `rerun_same_config`.

#### Việc 24 · Tổng duyệt — 25/10 · WP-29

## 5. Việc có thể phát sinh

- **Cổng tinh chỉnh model kích hoạt ngày 04/10** và bạn xong luật sai làn đúng 06/10: bạn nhận thêm WP-39 (mật độ, hàng chờ, ùn tắc; hạn 08/10).
- **API ứng viên (WP-13) trễ ngày 04/10:** bạn nhận phần API tuyến của WP-54.
- **Quá tải ở tuần 4:** đề xuất cắt MQTT trước (mục 3 trong danh sách cắt, timeline mục 7). Bớt được khoảng 7 giờ mà hệ thống không mất chức năng, vì edge vẫn hỏi định kỳ.

## 6. Việc lặp lại

- **Mỗi ngày:** standup 15 phút; cập nhật `WORKLOG.md`.
- **Tối Chủ nhật** (27/09, 04/10, 11/10, 18/10): demo nội bộ.
- **Đi quay:** S1 (26/09 chiều), S3 (30/09 cao điểm chiều), S4 (02/10 tối), S5 (Việc 7), S6 (Việc 15). Mỗi máy quay màn hình time.is lúc bắt đầu để khớp giờ.
- **PR của bạn** cần review trong 24 giờ: PR luật do người giữ luật review; PR chạm hợp đồng edge ↔ trung tâm do tech lead review.

## 7. Khi bị chặn

- Thiếu thứ ở dòng "Cần có": đừng ngồi chờ, làm trước trên dữ liệu mẫu theo hợp đồng ở spec mục 6.
- Quá hạn một ngày vẫn chưa có: nêu ngay ở standup. Ai giữ thứ đó: `docs/plan/timeline.md` mục 5.3.
- Thấy thiết kế sai: dừng lại, ghi rõ vấn đề, đề xuất cách sửa qua Change Request (spec mục 12). Không tự đổi hợp đồng dữ liệu.
