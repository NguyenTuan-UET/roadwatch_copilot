# Design review — TrafficEye Edge

> **Căn cứ:** `CLAUDE.md` mục 10 · **Ngày:** 21/09/2026
> **Đối tượng review:** `docs/report/trafficeye-edge-report.md` v0.2, `docs/eval/protocol.md` v1.0, `docs/plan/timeline.md` v1.0
> **Người review:** Claude, trong vai Senior Architect
> **Lưu ý:** CRITICAL/HIGH/MEDIUM/LOW là **mức rủi ro kỹ thuật**, không phải đánh giá chất lượng dự án.
> **Trạng thái:** **PO đã duyệt ngày 21/09.**
> - H-01: HTTPS + outbox.
> - H-03: phương án (a), kiểm soát truy cập ở server.
> - H-06: chuyển WP-12 sang TV4, WP-23 sang TV2.
> - Duyệt toàn bộ C-01, H-02, H-04, H-05, H-07, H-08, M-01.
> - Các mục MEDIUM và LOW còn lại áp dụng theo đề xuất.
>
> Đã cập nhật vào báo cáo v0.3, protocol và timeline v1.1. L-01 (kiểm tra SHA-256 trong script) sẽ là một task trong `/write-plan`.

---

## Tóm tắt

- **22 phát hiện:** 1 CRITICAL, 9 HIGH, 8 MEDIUM, 4 LOW.
- **Ba nhóm vấn đề lớn:**
  1. **Dữ liệu đầu vào:** góc quay và tốc độ khung của video điện thoại. Hai việc này **phải chốt trước khi quay trong tuần này**.
  2. **Phạm vi MVP đang quá tải:** hai kênh truyền cho một thiết bị, mã hóa đầu–cuối chưa rõ cách giải mã, và TV1 giữ quá nhiều việc trên đường găng.
  3. **Hai tuyên bố chưa có phép đo:** quyền riêng tư (tỉ lệ biển số hoặc khuôn mặt bị lọt, không được che) và độ chính xác đếm xe.

---

## Bảng phát hiện

### CRITICAL

| ID | Hạng mục | Phát hiện | Hệ quả nếu bỏ qua | Đề xuất | Hạn |
|---|---|---|---|---|---|
| C-01 | Dữ liệu, giả định ngầm | Tiêu chí chọn nút giao thiếu hai điều kiện. (a) Phải quay **từ phía sau dòng xe**, vì xe máy ở Việt Nam chỉ có biển số phía sau; từ vị trí này, mặt đèn của hướng đang giám sát cũng quay về phía camera. (b) Đèn phải đủ lớn trong khung và đọc được cả ban ngày lẫn buổi tối | Quay sai góc thì bản cho CSGT không có biển số và máy trạng thái không đọc được đèn → phải quay và gán nhãn lại → vỡ đường găng | Thêm hai tiêu chí vào WP-02. Trước khi chốt nút, quay thử 10 phút ban ngày và 10 phút buổi tối, kiểm tra đọc được đèn và biển số | 23/09 |

### HIGH

| ID | Hạng mục | Phát hiện | Hệ quả nếu bỏ qua | Đề xuất | Hạn |
|---|---|---|---|---|---|
| H-01 | Over-engineering | Chỉ một edge node nhưng MVP dùng hai kênh truyền (MQTT cho sự kiện, HTTPS cho bằng chứng), kèm broker và một dịch vụ ingest riêng. MQTT cũng **không thay được outbox**, vì client MQTT chỉ đệm tin trong RAM; vẫn phải có outbox SQLite | Thêm việc broker, TLS, ACL, dịch vụ ingest, hai cơ chế xác thực, trong khi demo không thấy khác biệt | MVP dùng **HTTPS + outbox** cho cả sự kiện và bằng chứng; edge tự hỏi cấu hình định kỳ. MQTT chuyển sang lộ trình, khi có nhiều thiết bị | M0 |
| H-02 | Đúng đắn, tái lập | Video điện thoại thường có tốc độ khung thay đổi (VFR), trong khi pipeline và `evaluate.py` tính thời gian bằng `frame / fps`. Chạy thời gian thực qua RTSP còn có thể rơi khung, tùy tải của máy | Ân hạn tính sai, ghép cảnh báo với nhãn sai; kết quả đánh giá không tái lập được | Kiểm tra video bằng ffprobe. Chuyển mọi video sang tốc độ khung cố định 15 FPS trước khi gán nhãn (`ffmpeg -fps_mode cfr -r 15`). Gán nhãn và chạy hệ thống trên **cùng một file** (SHA-256 trong manifest). Đánh giá chạy ở chế độ đọc file, không rơi khung. Ghi FPS xử lý vào config đóng băng. Khi demo thời gian thực thì ghi lại số khung bị rơi | Trước WP-09 (27/09) |
| H-03 | Quyền riêng tư, mâu thuẫn thiết kế | Báo cáo (mục 10) nói bản CSGT được mã hóa bằng khóa công khai của CSGT nên "máy chủ không đọc được", nhưng không nói **giải mã ở đâu**. Nếu server giải mã để hiển thị thì server phải giữ khóa riêng, và câu trên thành sai | Hoặc nói sai trước giám khảo, hoặc phát sinh việc lớn (giải mã trên trình duyệt, quản lý khóa của người dùng) | Chọn một trong hai: **(a)** MVP mã hóa khi lưu + RBAC + nhật ký, và nói trung thực "server kiểm soát quyền truy cập"; mã hóa đầu–cuối để vào lộ trình. **(b)** Giải mã ngay trên trình duyệt CSGT bằng thư viện như libsodium.js | M0 |
| H-04 | Thiếu yêu cầu, lỗi AI | Tuyên bố quyền riêng tư dựa vào detector biển số và vùng che mặt, nhưng **không có phép đo tỉ lệ bị lọt** (biển số hoặc khuôn mặt không được che) | Không chứng minh được câu "người không vi phạm không bị lộ biển số"; mỗi biển số lọt là một lần rò rỉ dữ liệu cá nhân | Thêm chỉ số vào protocol: soát tay N gói bằng chứng của tập test, đếm biển số và khuôn mặt bị lọt trên bản điều hành viên và bản CSGT, báo tỉ lệ kèm Wilson 95% | Trước M3 |
| H-05 | Báo nhầm, hình học | Khi nhìn từ phía sau, bánh trước bị thân xe che, và cạnh dưới bbox là **đuôi xe**. Nếu dùng điểm đuôi để xét "còn trước vạch khi đèn đỏ bật", một xe đã qua vạch bằng đầu từ lúc vàng vẫn bị coi là chưa qua → **báo nhầm**. Đây là dạng mở rộng của A1 và A3 | Đúng loại báo nhầm nguy hiểm nhất: xe đi tiếp hợp lệ khi đèn vàng bị gắn cờ | Ước lượng điểm đầu xe = điểm đuôi + chiều dài theo loại xe, tính dọc hướng làn trên mặt phẳng đường (homography); thêm biên an toàn; đưa các ca "đầu xe qua vạch lúc vàng" vào mẫu âm khó của tập dev | WP-10, WP-11 |
| H-06 | Phạm vi, phụ thuộc vào một người | TV1 giữ 9 gói việc, phần lớn trên đường găng: pipeline, đèn, quy tắc, biển số, bằng chứng, chỉnh ngưỡng, hiệu năng, slide, phỏng vấn | TV1 bận vài ngày là trễ ngày đóng băng | Chuyển WP-12 (detector biển số) sang TV4, vì gắn với dữ liệu; chuyển WP-23 (hiệu năng, băng thông) sang TV2. TV1 giữ pipeline, quy tắc, chỉnh ngưỡng, phỏng vấn | M0 |
| H-07 | Tiến độ, gán nhãn | Gán nhãn đôi toàn bộ tập dev và test (dòng thời gian đèn + mọi lần qua vạch trong pha vàng và đỏ, có bbox) rất tốn công, và dồn lên TV2, TV3, là những người đang làm backend và frontend | Nhãn trễ → chỉnh ngưỡng trễ → đóng băng trễ | Ở WP-09, đo thời gian gán nhãn thực tế (số phút công cho mỗi phút video), rồi mới chốt số giờ video cần quay. Tập dev: một người gán, người thứ hai gán ngẫu nhiên 30% để tính kappa. Tập test: giữ gán đôi toàn bộ [Đã chốt] | 27/09 |
| H-08 | Điểm lỗi duy nhất của demo | Toàn bộ demo chạy trên một laptop | Máy lỗi hoặc không có GPU là mất phần quan trọng nhất (demo là ưu tiên số 1) | Chuẩn bị máy dự phòng đã cài sẵn image; quay sẵn video chạy trọn kịch bản làm phương án cuối cùng; đo FPS ngay trên máy demo từ tuần 1 | Tuần 1 đo; 18/10 xong |
| H-09 | Sản phẩm, giả định | Người dùng (điều hành viên, CSGT) vẫn là giả định, trong khi tiêu chí thứ hai của team là chứng minh người dùng | Pitch thiếu bằng chứng về người dùng | WP-08 đã có. Đặt mốc: ít nhất 1 cuộc phỏng vấn trước 04/10; nếu không có thì chuyển sang ban quản lý khu dân cư làm nguồn bằng chứng dự phòng | 04/10 |

### MEDIUM

| ID | Hạng mục | Phát hiện | Hệ quả nếu bỏ qua | Đề xuất | Hạn |
|---|---|---|---|---|---|
| M-01 | Thiếu yêu cầu | Đếm xe là tính năng MUST nhưng không có phép đo độ chính xác, dù `CLAUDE.md` mục 14 yêu cầu counting accuracy và MAE/MAPE | Số đếm trên dashboard không có căn cứ | Đếm tay 2 đoạn, mỗi đoạn 10 phút, trên tập test theo loại xe và hướng; báo sai số tuyệt đối và sai số phần trăm | WP-27 |
| M-02 | Độ tin cậy của phép đo | Quy tắc ghép so IoU tại khung qua vạch **của mỗi bên**. Với xe máy nhỏ, nếu hệ thống và người gán nhãn lệch nhau khoảng 1 m về vị trí "đầu xe qua vạch", IoU có thể rơi dưới 0,3, và một vi phạm đúng bị tính thành một FP cộng một FN | Precision và recall bị kéo xuống giả tạo | Trước khi đóng băng, kiểm tra trên tập dev xem bao nhiêu cặp đúng bị rớt ngưỡng IoU. Nếu đáng kể: cảnh báo gửi kèm quỹ đạo ngắn, và so IoU **tại cùng một khung**. Ghi thay đổi vào bản đăng ký trước | Trước M3 |
| M-03 | Thiết kế | Một "vạch xác nhận" dạng đường thẳng không bắt được xe rẽ trái hoặc rẽ phải đi lệch khỏi vạch | Bỏ sót, hoặc xử lý sai xe rẽ | Dùng **vùng giao lộ** (polygon) thay cho một vạch: xe vào vùng này trong T_c giây thì tính là "đi tiếp" | WP-11 |
| M-04 | Triển khai | Máy của team chạy Windows. Dùng GPU trong Docker cần WSL2 + driver NVIDIA, và TensorRT trong container dễ vướng cài đặt | Mất nhiều ngày để dựng môi trường | Thử trước (spike) ngay trong tuần 1 trên đúng máy demo. Phương án dự phòng: edge chạy trực tiếp trong môi trường conda, còn trung tâm chạy trong Docker | 27/09 |
| M-05 | Quyền riêng tư | Agent gửi dữ liệu sự kiện tới một dịch vụ LLM bên ngoài | Có nguy cơ chuyển dữ liệu cá nhân ra ngoài | Công cụ của Agent chỉ trả dữ liệu tổng hợp; không trả biển số, ảnh hay đường dẫn tới bằng chứng | WP-42, WP-48 (timeline v2.0; trước là WP-24) |
| M-06 | Quyền riêng tư | Video thô (có biển số, khuôn mặt) nằm trên máy cá nhân và trên drive trong suốt dự án | Rò rỉ dữ liệu cá nhân | Dùng drive có phân quyền; ghi rõ chính sách xóa video thô sau khi nộp bài, chỉ giữ bản đã che | 25/09 |
| M-07 | Toàn vẹn dữ liệu | Chỉ custodian giữ tập test | Máy custodian hỏng là mất tập test | Giữ hai bản sao đã mã hóa ở hai nơi, cùng SHA-256 ghi trong manifest | 04/10 |
| M-08 | Bằng chứng khi mô phỏng | Video phát lại qua RTSP mất thời điểm quay gốc, nên edge đóng dấu giờ lúc phát lại | Bằng chứng ghi "vi phạm lúc 14:32 hôm nay" cho một cảnh quay từ tuần trước | Manifest ghi riêng `captured_at` (giờ quay gốc = giờ bắt đầu quay + độ lệch trong video) và `processed_at`, kèm cờ `source: replay` | WP-17 |

### LOW

| ID | Hạng mục | Phát hiện | Hệ quả nếu bỏ qua | Đề xuất | Hạn |
|---|---|---|---|---|---|
| L-01 | Script | `evaluate.py` chưa kiểm tra `video_sha256` trong file nhãn có khớp SHA-256 trong manifest không | Nhãn làm trên một file mà hệ thống chạy trên file khác (ví dụ trước và sau khi chuyển sang CFR) mà không ai phát hiện | Thêm bước kiểm tra này vào script sau khi thiết kế được duyệt (bước review không viết code) | Sau M0 |
| L-02 | Bảo mật | Nhật ký nối băm chưa được "neo" ra ngoài hệ thống | Người kiểm soát DB có thể dựng lại cả chuỗi | Mỗi ngày commit mã băm đầu chuỗi vào repo; GitHub lưu thời điểm commit | WP-18 |
| L-03 | Demo | Edge và trung tâm chạy cùng một máy nên khó cho thấy "mất mạng" thật | Phần demo mất mạng kém thuyết phục | Dùng `docker network disconnect` cho container edge, kèm bộ đếm byte hiển thị trên màn hình | WP-23 |
| L-04 | Phạm vi | Đề chưa định nghĩa rõ "mô phỏng Jetson" là gì | Có thể thiếu một điều kiện chấm | Hỏi BTC. Nếu không rõ, giới hạn tài nguyên của container edge và ghi rõ trong báo cáo | 25/09 |

---

## Over-engineering và thành phần có thể bỏ khỏi MVP

| Thành phần | Đề xuất | Lý do |
|---|---|---|
| MQTT broker + dịch vụ ingest riêng | Bỏ khỏi MVP (H-01) | Chỉ có 1 edge node; outbox đã xử lý chuyện mất mạng |
| Mã hóa đầu–cuối cho bản CSGT | Tùy quyết định ở H-03 | Cần giải mã trên trình duyệt và quản lý khóa của người dùng |
| Chạy lại thao tác che trên thiết bị từ trang xác minh | Bỏ khỏi MVP; giữ phần kiểm chữ ký và mã băm | Tốn nhiều công, ít giá trị cho demo |
| Prometheus/Grafana | Giữ ở mức SHOULD | Một trang sức khỏe hệ thống đơn giản là đủ |

---

## Những điểm thiết kế đúng, nên giữ

- AI chỉ dùng cho phát hiện. Mọi phần còn lại là logic cố định, và có mã lý do cho từng ứng viên bị loại.
- 6 điều kiện + duyệt 2 bước; AI chỉ tạo ứng viên.
- Giao thức đo có chống rò rỉ dữ liệu, chỉ chạy test một lần, và báo khoảng tin cậy.
- Bằng chứng tối thiểu; video thô không rời thiết bị; bản CSGT che các xe khác.
- Interface tách pipeline khỏi bộ quy tắc, nên sau này chuyển sang DeepStream không phải viết lại quy tắc.

---

## Cần PO xác nhận để qua M0

1. **H-01:** dùng HTTPS + outbox thay cho MQTT trong MVP?
2. **H-03:** chọn phương án (a) hay (b)?
3. **H-06:** chuyển WP-12 sang TV4 và WP-23 sang TV2?
4. Đồng ý đưa C-01, H-02, H-04, H-05, H-07, H-08, M-01 vào báo cáo, protocol và timeline?

Các mục MEDIUM và LOW còn lại sẽ áp dụng theo đề xuất, trừ khi PO phản đối.

**Sau khi xác nhận:** cập nhật báo cáo lên v0.3, cập nhật protocol và timeline → chạy `/write-plan`.
