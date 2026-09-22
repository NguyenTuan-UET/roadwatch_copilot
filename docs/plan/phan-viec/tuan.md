# Việc của Tuấn

> **Vai trò:** Tech lead. Bạn giữ kiến trúc và mọi hợp đồng dữ liệu giữa edge và trung tâm; làm lõi edge, lõi trung tâm và phần đưa lên production.
> **Thời gian cần:** khoảng 22 / 42 / 44 / 40 / 39 giờ cho tuần 1 → 5.
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
| Edge, trung tâm | Edge: máy ở nút giao, chạy AI trên video. Trung tâm: FastAPI + PostgreSQL, nhận dữ liệu từ edge và phục vụ dashboard |
| MediaMTX, RTSP | MediaMTX phát lặp video đã quay thành luồng RTSP, giống camera thật |
| Máy trạng thái đèn | Phần đổi màu đèn đọc được trên ảnh thành trạng thái ổn định: đỏ, vàng, xanh, nhấp nháy, tắt, không rõ |
| Cấu hình cảnh | File YAML mô tả một nút giao: làn, vạch dừng, vạch phân làn, cạnh ra, các vùng, phép chiếu mặt đường (spec mục 6.1) |
| Ứng viên vi phạm | Ca hệ thống nghi là vi phạm. Phải qua người duyệt mới thành vi phạm |
| Gói bằng chứng | 3 ảnh + đoạn clip từ 3 giây trước tới 2 giây sau sự kiện + manifest; có bản đã che biển số và bản cho CSGT |
| SHA-256, Ed25519 | SHA-256: "dấu vân tay" của file. Ed25519: chữ ký số, chứng minh gói do edge tạo ra và chưa bị sửa |
| JWT, 4 vai trò | JWT: mã đăng nhập gửi kèm mỗi request. 4 vai trò: điều hành viên, CSGT, kiểm toán, quản trị (spec mục 3) |
| SSE, vé SSE | SSE: trung tâm đẩy thông báo mới lên trình duyệt ngay. Vé SSE: mã dùng một lần, sống ngắn, để mở kết nối SSE |
| Duyệt 2 bước | Bước 1: điều hành viên xem bản đã che biển số. Bước 2: CSGT xem biển số xe vi phạm và quyết định |
| Nhật ký nối băm | Nhật ký mà mỗi dòng chứa mã băm của dòng trước. Sửa một dòng là bị lộ |
| HCM, v/c, LOS | Phương pháp đánh giá nút giao (Highway Capacity Manual). v/c: lưu lượng chia năng lực. LOS: mức phục vụ, từ A (thông thoáng) tới F (tắc) |
| Tràn hàng chờ, nút cổ chai | Tràn hàng chờ: hàng xe ở nút sau kéo dài tới tận nút trước. Nút cổ chai: nút làm nghẽn cả tuyến |
| OCR | Đọc chữ trên biển số |
| Hardening | Làm chắc bảo mật trước khi lên production: TLS, mật khẩu băm, giới hạn số lần đăng nhập, sao lưu… |
| Live URL | Địa chỉ web công khai để giám khảo truy cập |
| Soak test | Chạy liền 24 giờ để xem hệ thống có rò bộ nhớ, bị sập hay chậm dần không |
| Tập test, đóng băng | Tập test: video quay sau ngày đóng băng (11/10), chỉ dùng để đo một lần. Đóng băng: khóa luật và ngưỡng |
| Gán nhãn mù | Xem video và ghi lại vi phạm thật mà không xem kết quả của hệ thống |
| PR, review, CI | PR: yêu cầu gộp code. Review: người khác đọc và duyệt. CI: máy tự chạy test; CI xanh mới được gộp |
| DoD | Điều kiện "xong" chung cho mọi việc (spec mục 9.2) |

## 1. Bạn phụ trách gì

| Phân hệ | Phần của bạn |
|---|---|
| — Tech lead | Giữ hợp đồng dữ liệu (spec mục 6); review mọi PR chạm hợp đồng; giữ CI xanh; chủ trì M1 và tổng duyệt M7 |
| PH1 · Nhận diện và đếm xe | Khung edge M1; đếm xe theo làn |
| PH2 · Đèn tín hiệu và cấu hình cảnh | Máy trạng thái đèn; đọc và kiểm tra cấu hình cảnh v2 |
| PH4 · Bằng chứng và riêng tư | Gói bằng chứng có ký; tích hợp OCR |
| PH6 · Trung tâm | Đăng nhập và phân quyền; API ứng viên và vé SSE; luồng duyệt của CSGT; nhật ký nối băm; xác minh; xóa theo thời hạn |
| PH7 · Phân tích giao thông | Phân tích nút và tuyến theo HCM |
| PH11 · Vận hành và hiệu năng | Quyền repo; hardening; Live URL; giám sát; sửa lỗi khi chạy soak test |
| PH10 · Đánh giá và dữ liệu | Gán nhãn mù tập test |

## 2. Đọc gì trước khi bắt đầu

| Thứ tự | Đọc | Để biết |
|---|---|---|
| 1 | `README.md` | Sản phẩm làm gì (10 phút) |
| 2 | `docs/architecture_diagram.md` (cả file) | Kiến trúc; bạn là người giữ nó |
| 3 | Spec mục 3, 6 (cả mục), 9 | Vai trò, mọi hợp đồng dữ liệu, thế nào là xong |
| 4 | Spec mục 4.3 (FR-LGT), 4.5, 4.7, 4.2 (FR-COR), 5 (NFR), 8.2 | Yêu cầu của các việc bạn làm; checklist production của CP2 |
| 5 | Plan M1: phần A (TASK-001…007) và TASK-017, 022 | Hướng dẫn code tuần 1 |
| 6 | `docs/eval/protocol.md` mục 5 và 13.7 | Quy tắc gán nhãn mù và chống lộ tập test |

## 3. Quy tắc bắt buộc với bạn

1. **Khi đi quay buổi S5 (03/10) và S6 (14/10): chỉ bấm máy**, giao thẻ nhớ ngay cho người giữ tập test, không xem lại.
2. **Không chạy hệ thống trên video test**, và không xem kết quả hệ thống trên tập test trước khi nhãn được khóa (18/10).
3. **Sau đóng băng (11/10) không sửa code luật.** Thấy lỗi thì mở issue cho người chỉnh ngưỡng.
4. **15–18/10 gán nhãn toàn thời gian**, không nhận việc code khác.
5. **Review mọi PR chạm hợp đồng edge ↔ trung tâm trong 24 giờ.**

## 4. Việc theo thứ tự thời gian

Mỗi việc ghi: **Làm** (các bước), **Cần có** (thứ phải có trước, và ngày dự kiến có), **Nộp** (kết quả), **Xong khi** (cách kiểm tra). Dấu ⚠ đánh dấu việc mà người khác đang chờ: việc này trễ thì cả team trễ.

### Tuần 1 (22–27/09)

#### Việc 1 · Review kiến trúc và hợp đồng — hạn 24/09 · WP-32
- **Làm:** đọc spec mục 6 (cấu hình cảnh, sự kiện, API, giao diện luật, kênh điều khiển). Ghi chỗ thiếu hoặc mâu thuẫn.
- **Nộp:** góp ý gửi trước buổi M0.
- **Xong khi:** góp ý đã được trả lời ở buổi M0.

#### Việc 2 · Quyền repo — hạn 25/09 · WP-07 (phần quyền) · PH11
- **Làm:** cấp quyền repo cho cả team; bật bảo vệ nhánh `main` (phải qua PR và CI); kiểm tra CODEOWNERS của template không chặn PR của team.
- **Xong khi:** một PR thử của thành viên khác gộp được sau khi có review và CI xanh.

#### Việc 3 · Khung edge M1 — hạn 27/09 · WP-04 · PH1
- **Làm:** làm lần lượt TASK-001 → TASK-007 và TASK-017 trong plan M1. Mỗi TASK có sẵn code, lệnh kiểm tra và kết quả mong đợi. TASK-001 (hợp đồng sự kiện v1) làm cặp với người làm khung trung tâm. Bước 1–3 của TASK-017 nên xong ngày 23/09 vì TASK-006 cần video mẫu.
- **Cần có:** quyết định chạy edge bằng Docker hay conda (WP-31, có từ 25/09).
- **Nộp:** mỗi TASK một commit.
- **Xong khi:** mọi lệnh "Validate" của các TASK trên ra đúng "Expected".

#### Việc 4 · Chủ trì nghiệm thu M1 — 27/09 · TASK-022
- **Làm:** chạy đầu–cuối: video mẫu → edge → outbox → trung tâm → dashboard hiện số đếm. Thử ngắt mạng rồi nối lại: không mất, không trùng sự kiện.
- **Nộp:** kết quả ghi vào `WORKLOG.md`.
- **Xong khi:** TASK-022 đạt. ⚠ Cả team chờ mốc này.

### Tuần 2 (28/09–04/10)

#### Việc 5 · Máy trạng thái đèn và cấu hình cảnh v2 — hạn 30/09 · WP-10 · PH2
Nên bắt đầu từ 26/09.
- **Làm:**
  1. Máy trạng thái đèn: đỏ, vàng, xanh, nhấp nháy, tắt, không rõ. Ba trạng thái KHÔNG RÕ, NHẤP NHÁY, TẮT phải chặn luật.
  2. Bộ đọc cấu hình cảnh v2: làn, vạch phân làn, cạnh ra, các vùng, phép chiếu mặt đường.
  3. Kiểm tra hình học khi nạp: cấu hình sai thì từ chối, theo spec mục 6.1.
  4. Vẽ ảnh overlay cấu hình lên khung hình của từng camera.
- **Nộp:** PR có test; ảnh overlay của từng camera.
- **Xong khi:** đạt FR-LGT-1 AC1–AC3; cấu hình của M1 vẫn đọc được; cấu hình sai bị từ chối (có test). ⚠ **Điểm nghẽn số 2 của dự án:** 6 việc khác đang chờ việc này. Nếu trễ, hoãn Việc 7 một ngày để xong việc này trước.

#### Việc 6 · Đếm xe theo làn — hạn 02/10 · WP-35 · PH1
- **Làm:** gắn `lane_id` vào số đếm; gửi sự kiện `count` bản 1.1 (spec mục 6.3).
- **Cần có:** Việc 5.
- **Xong khi:** đạt FR-CNT-2 AC1; trung tâm nhận được `count` v1.1. ⚠ Bản đồ số đếm theo làn trên dashboard chờ việc này.

#### Việc 7 · Đăng nhập, API ứng viên, vé SSE — hạn 04/10 · WP-13 · PH6
- **Làm:**
  1. Đăng nhập, JWT, 4 vai trò (spec mục 3).
  2. Nhận sự kiện `violation_candidate` và gói bằng chứng từ edge; chống trùng.
  3. API ứng viên cho màn duyệt (spec mục 6.5).
  4. Vé SSE: cấp vé ngắn hạn, dùng một lần.
- **Cần có:** khung trung tâm M1 (WP-05, có từ 27/09).
- **Nộp:** PR có test.
- **Xong khi:** có test 401/403 cho mọi endpoint; test chống trùng; thử ngắt mạng giữa lúc tải bằng chứng; vé SSE đã dùng hoặc quá hạn thì trả 401. ⚠ Màn duyệt bước 1 chờ API này.

### Tuần 3 (05–11/10)

#### Việc 8 · Gói bằng chứng có ký — hạn 08/10 · WP-17 · PH4
- **Làm:** với mọi loại vi phạm: lấy 3 khung hình và clip JPEG từ 3 giây trước tới 2 giây sau sự kiện; lập manifest (spec mục 6.4); ký Ed25519. Bản đầy đủ giữ trên thiết bị; chỉ gửi bản đã che và bản CSGT.
- **Cần có:** kiểu `Candidate` hoàn chỉnh (WP-11, có từ 02/10); bộ che biển số (WP-12, có từ 04/10). Chưa có bộ che thì tạm che nửa dưới bbox.
- **Xong khi:** đạt FR-EVD-1 AC1–AC2.

#### Việc 9 · Phân tích nút và tuyến — hạn 10/10 · WP-54 · PH7
- **Làm:** tại trung tâm, tính cho từng nút: lưu lượng q, năng lực thoát s, tỉ lệ xanh g/C, độ bão hòa X, độ trễ d1 + d2, LOS A–F theo HCM. Phát hiện tràn hàng chờ và nút cổ chai. Mở API hiệu năng nút và tuyến; phát sự kiện tuyến qua SSE.
- **Cần có:** sự kiện `signal_cycle` (WP-53, có từ 07/10); mật độ và hàng chờ (WP-39, có từ 08/10).
- **Xong khi:** đạt FR-COR-1 AC1–AC2 và FR-COR-2 AC1–AC3; API trả đúng schema. ⚠ Việc chỉnh ngưỡng tuyến và trang Tuyến chờ việc này.

#### Việc 10 · Chọn nền tảng cloud — trước 12/10 · chuẩn bị WP-52 · PH11
- **Làm:** chọn nền tảng theo tiêu chí ở `docs/plan/timeline.md` (tuần 4, "Tiêu chí chọn nền tảng cloud"). Kiểm tra giới hạn gói miễn phí trên trang nhà cung cấp.
- **Xong khi:** đã chọn, và đã thử broker MQTT nhận được kết nối từ mạng ngoài.

#### Việc 11 · Luồng duyệt của CSGT — hạn 12/10 · WP-18 · PH6
Chuẩn bị cấu hình hardening song song với việc này (xem Việc 16).
- **Làm:** mở quyền xem bản CSGT sau khi bước 1 xác nhận; nhật ký nối băm cho mọi lượt truy cập; API xác minh bằng chứng; job xóa theo thời hạn lưu giữ.
- **Cần có:** Việc 7 và Việc 8.
- **Xong khi:** đạt FR-HITL-2 AC1–AC2 và FR-HITL-3 AC. ⚠ Màn CSGT chờ việc này.

### Tuần 4 (12–18/10)

#### Việc 12 · Tích hợp OCR — hạn 13/10 · WP-43 · PH4
- **Làm:** gắn công cụ OCR đã chọn ở WP-37 vào gói bằng chứng; chỉ đọc biển số của xe vi phạm.
- **Cần có:** kết quả chọn công cụ OCR (WP-37, có từ 01/10); Việc 8.
- **Xong khi:** đạt FR-OCR-1 AC1 và AC3.

#### Việc 13 · CP1 — 14/10
- **Làm:** tích hợp mọi phần; chạy trọn kịch bản demo 2 lần trước giờ demo.

#### Việc 14 · Quay tập test chính (S6) — chiều 14/10
- **Làm:** chỉ bấm máy; giao thẻ nhớ ngay cho người giữ tập test; không xem lại.

#### Việc 15 · Gán nhãn mù tập test — 15–18/10 · WP-22 · PH10
- **Làm:** gán nhãn theo hướng dẫn gán nhãn, độc lập với người gán thứ hai. Ca nào không chắc thì gán `ambiguous` kèm ghi chú, không đoán.
- **Cần có:** video test và hướng dẫn (nhận ngày 15/10).
- **Nộp:** file nhãn, trước tối 17/10.

### Tuần 5 (19–25/10)

#### Việc 16 · Hardening production — hạn 20/10 · WP-49 · PH11
- **Làm:** TLS qua reverse proxy; mật khẩu băm; giới hạn tần suất đăng nhập; quản lý bí mật; sao lưu DB; job xóa theo thời hạn; giới hạn tài nguyên; ghi IP thật của người dùng (`--proxy-headers`, `--forwarded-allow-ips`).
- **Cần có:** Việc 11.
- **Xong khi:** mục Bảo mật và Triển khai trong checklist CP2 (spec mục 8.2) xanh. ⚠ Soak test 24 giờ chỉ bắt đầu được sau việc này.

#### Việc 17 · Live URL — hạn 21/10 · WP-52 · PH11
- **Làm:** đưa phần trung tâm (API, DB, dashboard, broker MQTT) lên cloud, có TLS; tạo tài khoản giám khảo theo quyết định Q10.
- **Cần có:** Việc 16; OTA và MQTT (WP-46, có từ 18/10).
- **Xong khi:** mở được URL từ mạng ngoài (trình duyệt ẩn danh, mạng 4G); edge ở máy local gửi được sự kiện và nối được broker; URL sống tới hết Demo Day + 7 ngày.

#### Việc 18 · Sửa lỗi khi chạy soak test — 20–22/10 · WP-50 · PH11
- **Làm:** sửa các lỗi được báo trong lúc chạy liền 24 giờ.
- **Xong khi:** soak test đạt.

#### Việc 19 · Giám sát hệ thống — hạn 22/10 · WP-51 · PH11
- **Làm:** cảnh báo khi camera mất kết nối; log có cấu trúc; Prometheus (Grafana nếu kịp).
- **Xong khi:** mục Quan sát trong checklist CP2 xanh.

#### Việc 20 · Tài liệu — hạn 22/10 · WP-30
- **Làm:** runbook vận hành; tài liệu OpenAPI.

#### Việc 21 · CP2 — 23/10
- **Làm:** vận hành hệ thống trong lúc demo.

#### Việc 22 · Tổng duyệt và khóa code (M7) — 25/10 · WP-29
- **Làm:** chủ trì tổng duyệt; chuẩn bị máy dự phòng; khóa code, từ đây chỉ sửa lỗi nghiêm trọng.
- **Xong khi:** demo chạy trọn trên cả máy chính và máy dự phòng.

## 5. Việc lặp lại

- **Mỗi ngày:** standup 15 phút; cập nhật `WORKLOG.md`.
- **Tối Chủ nhật** (27/09, 04/10, 11/10, 18/10): demo nội bộ.
- **Review** mọi PR chạm hợp đồng edge ↔ trung tâm trong 24 giờ; giữ CI xanh.
- **Đi quay:** S2 (28/09 cao điểm chiều), S3 (30/09 cao điểm chiều), S5 (03/10 chiều, tập test dự phòng: chỉ bấm máy), S6 (Việc 14). Mỗi máy quay màn hình time.is lúc bắt đầu để khớp giờ.

## 6. Khi bị chặn

- Thiếu thứ ở dòng "Cần có": đừng ngồi chờ, làm trước trên dữ liệu mẫu theo hợp đồng ở spec mục 6.
- Quá hạn một ngày vẫn chưa có: nêu ngay ở standup. Ai giữ thứ đó: `docs/plan/timeline.md` mục 5.3.
- Thấy thiết kế sai: dừng lại, ghi rõ vấn đề, đề xuất cách sửa qua Change Request (spec mục 12). Không tự đổi hợp đồng dữ liệu.
