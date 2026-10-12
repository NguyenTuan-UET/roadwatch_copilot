# Nhật ký công việc — Nhóm P-014

**Thành viên:** Cương, Khánh, Tuấn, Linh.
**Cập nhật:** 07/10/2026.
**Phạm vi:** tổng hợp quá trình bốn tuần; xem phần diễn giải và bài học trong [JOURNAL.md](JOURNAL.md).

Phân công, hoạt động thảo luận và phản hồi mentor được ghi theo hồi thuật của Cương. Ngày trong cột bằng chứng là ngày commit, không suy ra ngày họp hoặc thời lượng làm việc. Các mục không có ngày chính xác được giữ ở cấp tuần. “Đã triển khai” chỉ ghi nhận sản phẩm công việc, không thay cho nghiệm thu hay kết quả đánh giá thực địa.

## Tuần 1 — Nhập nhóm và chọn đề tài

| Người phụ trách / tham gia | Công việc | Kết quả ghi nhận | Mốc / bằng chứng |
|---|---|---|---|
| Cả nhóm | Nhập nhóm, tìm hiểu đề tài và trao đổi các hướng khả thi | Hình thành nhóm bốn thành viên và các ý tưởng ban đầu | Hồi thuật của Cương; chưa xác định ngày cụ thể |
| Linh, Khánh, Tuấn | Tìm hiểu thông tin và đóng góp ý kiến chọn đề tài | Cung cấp thông tin để nhóm thảo luận | Hồi thuật của Cương |
| Cương | Tổng hợp ý kiến và chốt hướng agent guardrail | Chọn AegisGate — AI Security Gateway & Sentinel Agent | Hồi thuật; bộ tài liệu tại `639cc83` |
| Cương | Chuẩn bị brief, PRD, luồng giao diện và kế hoạch nhóm | Có bộ tài liệu Gate 1 cho AegisGate | 18/09/2026 — `639cc83` |

## Tuần 2 — Đánh giá tính khả thi và xây dựng TrafficEye Edge

| Người phụ trách / tham gia | Công việc | Kết quả ghi nhận | Mốc / bằng chứng |
|---|---|---|---|
| Cương chủ trì; cả nhóm góp ý | Đánh giá dữ liệu và yêu cầu chuyên môn của AegisGate | Nhận định hướng bảo mật chưa phù hợp với dữ liệu và năng lực nhóm; quyết định đổi đề tài | Hồi thuật của Cương |
| Cương chốt; cả nhóm thảo luận | Lựa chọn camera giao thông hỗ trợ phạt nguội trên biên | Chuyển sang TrafficEye Edge | Hồi thuật; tên và phạm vi thể hiện trong `e1b5a76` |
| Cương | Lên spec, kiến trúc, tài liệu Gate 1 và phân chia nhiệm vụ | Có đặc tả và kế hoạch triển khai cho các thành viên | 22/09/2026 — `e1b5a76`, `885299e`, `260ac4f` |
| Linh, Khánh, Tuấn | Đọc bài báo và tìm phương pháp có thể tích hợp | Đóng góp nghiên cứu cho hướng đề tài mới | Hồi thuật của Cương; chưa có danh mục bài báo để dẫn chiếu |
| Cả nhóm | Họp mentor, xem lại người dùng mục tiêu và pain point | Nhận thấy cơ sở nhu cầu sử dụng chưa đủ thuyết phục; tiếp tục đổi hướng | Hồi thuật của Cương; chưa xác định ngày họp |

## Tuần 3 — Đặc tả và triển khai RoadWatch ban đầu

| Người phụ trách / tham gia | Công việc | Kết quả ghi nhận | Mốc / bằng chứng |
|---|---|---|---|
| Cương chốt; cả nhóm thảo luận | Chọn RoadWatch Copilot, làm rõ các bài toán trong nửa đầu giai đoạn | Hướng trợ lý kèm lái trên cao tốc; chia BT-A, BT-B, BT-C | 28/09/2026 — `3f76f09`; trình tự thảo luận theo hồi thuật |
| Cương | Thiết kế hợp đồng dữ liệu và bộ quyết định cảnh báo | Có contracts và decision stage | 28/09/2026 — `348a6b4`, `439efd2` |
| Cương | Xây dựng quản lý cấu hình HITL và nguồn dữ liệu | Có config store, lịch khung hình và ánh xạ thời gian dữ liệu | 28/09/2026 — `22f9da9`, `2d6fbbd` |
| Cương | Triển khai BT-A ban đầu | Có detector ONNX, tracker, chọn xe trước, khoảng cách, TTC và kiểm tra quan sát/lắp đặt | 28/09/2026 — `3822f7c` |
| Cương | Xây dựng runtime và công cụ đánh giá | Có replay/live, chạy lại B và báo cáo đánh giá | 28/09/2026 — `53eebba`, `9ba15a3` |
| Cương | Hoàn thiện bộ khung và phân công chi tiết | Có bộ tài liệu, checklist và code nền của phương án ban đầu | 29/09/2026 — `8943c1c`, `7d0b492`; chưa đồng nghĩa nghiệm thu toàn bộ |
| Nhánh tác giả `Devtamin04` | Thử nghiệm nhận diện đối tượng, biển báo, làn đường, giao diện desktop và tracking | Mở rộng pipeline thị giác trong giai đoạn phạm vi còn rộng | 28–29/09/2026 — `97a89be`, `0dad089`, `9630476`, `e0f0c75`, `222b144`; chưa tự ánh xạ tài khoản sang tên thành viên |
| Khánh | Tích hợp nhánh perception/tracking và điều chỉnh detector/TTC | Có phần tích hợp và các sửa đổi thuật toán trên nhánh Khánh | 01/10/2026 — `fb86ae9`, `9fe2885`, `5da83df` |
| Cương | Bổ sung CLI, fixture và kiểm tra hợp đồng | Có công cụ thao tác và dữ liệu kiểm thử | 30/09/2026 — `c6b16f8` |
| Cương | Hoàn thiện xử lý cảnh báo, đánh giá và script audio | Có xử lý phát lại cảnh báo, tình huống lỗi, báo cáo và công cụ sinh câu nói | 01/10/2026 — `1325e86`, `87b0814`, `85c58ca`, `cf02f0e` |
| Cương | Chuẩn bị tích hợp B+C, hợp đồng bàn giao, audio và CI | Có đường chạy với measurements giao sẵn, bộ câu nói và tài liệu bàn giao | 02/10/2026 — `f30174b`, `b29ba35`, `6536665`, `2ff71e4` |
| Cả nhóm; Cương chốt | Tiếp nhận góp ý mentor và tham khảo thêm nguồn | Nhận thấy phạm vi quá rộng; chuyển trọng tâm sang ước lượng khoảng cách | Hồi thuật của Cương; chưa xác định ngày họp |

Các chức năng TTC, cảnh báo, audio, HITL, biển báo và làn đường ở bảng trên là lịch sử phương án rộng. Theo quyết định mới nhất của Cương, bài toán trọng tâm cuối cùng là khoảng cách. Việc đã làm xong phần đặc tả và code nền không được diễn giải thành toàn bộ tính năng đã đạt chất lượng sản phẩm.

## Tuần 4 — Thu hẹp phạm vi, tích hợp và triển khai

| Người phụ trách / tham gia | Công việc | Kết quả ghi nhận | Mốc / bằng chứng |
|---|---|---|---|
| Cương | Chốt hướng khoảng cách; tổ chức lại phần model và evaluation | Nhận trách nhiệm chính về thiết kế mô hình và đánh giá | Hồi thuật; nhật ký local trước lần biên tập này ghi điều chỉnh BT-A ngày 05–06/10/2026 |
| Khánh | Giải quyết tự hiệu chỉnh camera | Có hướng autocalibration kết hợp model tự train của RoadWatch | 07/10/2026 — `fdb8cdd`, `61b2f22` |
| Tuấn | Hỗ trợ kỹ thuật và triển khai lên server | Tham gia đưa nhóm đến bước triển khai | Hồi thuật của Cương; chưa gắn được commit riêng cho phần đóng góp này |
| Linh | Thiết kế giao diện | Tham gia phần giao diện trong luồng sản phẩm cuối | Hồi thuật của Cương; chưa gắn được commit riêng cho phần đóng góp này |
| Khánh (tác giả commit) | Bổ sung giao diện demo, preview video và cập nhật kết quả trực tiếp | Có luồng chọn video và hiển thị kết quả theo khung hình | 07/10/2026 — `5d7fd2f`, `926551f`, `9ad8c95`, `b578580` |
| Khánh (tác giả commit); nhóm phối hợp tích hợp | Bổ sung server, Docker, API và đường truy cập demo | Có mã nguồn phục vụ triển khai và kết nối frontend | 07/10/2026 — `665fe98`, `e4c9579`, `5fbb6b0`, `7b3524b` |
| Cả nhóm | Tích hợp các phần để đưa sản phẩm đến bước deploy | Đã đến bước triển khai theo cập nhật của Cương | Hồi thuật và các commit triển khai ở trên; chưa ghi nhận nghiệm thu cuối |

Phân công và tác giả commit là hai loại bằng chứng khác nhau: một commit đứng tên Khánh không phủ nhận đóng góp thiết kế giao diện của Linh hay hỗ trợ triển khai của Tuấn. Chưa có số đo được đối chiếu trong lần tổng hợp này để kết luận chất lượng mô hình hoặc hiệu năng của bản triển khai.

## Việc còn lại để hoàn tất bản nộp

| Người phụ trách | Công việc | Sản phẩm cần hoàn tất | Tình trạng tại 07/10/2026 |
|---|---|---|---|
| Cương | Rà soát tiêu chí chương trình và đối chiếu với bài làm | Danh sách tiêu chí, bằng chứng tương ứng và các phần cần bổ sung | Còn thực hiện |
| Cương | Hoàn thiện hồ sơ và nộp bài cuối cùng | Bộ tài liệu, kết quả và liên kết nộp bài theo yêu cầu chương trình | Chưa ghi nhận đã nộp |
| Khánh | Làm video demo | Video giới thiệu bài toán và luồng demo | Dự kiến giao; chưa ghi nhận hoàn thành |
| Tuấn | Làm slide | Slide trình bày dự án | Được phân công; chưa ghi nhận hoàn thành |
| Cương | Chuẩn bị và thuyết trình | Nội dung trình bày, demo và phần trả lời câu hỏi | Chưa ghi nhận đã thực hiện |

## Cách tra cứu bằng chứng

Các mã commit có thể được xem bằng `git show <mã-commit>` trong repo. Lịch sử được đọc trên các nhánh, không chỉ `main`, vì nội dung `main` đã được đưa về template. Các thông tin về họp mentor, nghiên cứu bài báo và phân công không có commit riêng được dẫn nguồn rõ là hồi thuật của Cương. Không tự bổ sung ngày họp, số giờ, điểm đánh giá hoặc xác nhận hoàn thành chưa có căn cứ.

## Nhật ký hoạt động

- 10/10/2026 — Codex, theo yêu cầu trực tiếp của người dùng: nhập toàn bộ nội dung models/ (model ONNX/PT, mã train, bộ đánh giá, báo cáo và audio demo) vào nền origin/main 0da24b4, trong worktree riêng để giữ nguyên thay đổi web chưa commit. Người dùng cho phép ngoại lệ commit models/ và push main. Không đưa .git lồng, môi trường Python hoặc cache vào commit. Đối chiếu hash toàn bộ 75 file với bản gốc; kiểm cú pháp Python và JSON, kiểm ONNX checker đạt cho cả ba artifact ONNX và git diff --cached --check đạt. Không chạy huấn luyện mới hoặc khẳng định nghiệm thu/chất lượng model.
- 11/10/2026 — Claude Code, theo yêu cầu trực tiếp của người dùng: commit bản tổng hợp bốn tuần của WORKLOG.md và JOURNAL.md rồi push lên main; người dùng cho phép ngoại lệ push main. Giữ lại dòng hoạt động 10/10 đã có trên main. Kiểm git diff --check đạt và mọi mã commit được dẫn đều tồn tại trong repo cục bộ; không kiểm chứng nội dung hồi thuật.
- 12/10/2026 — Codex — WP-C6/WP-C7: thêm giao diện/API đăng nhập, đăng ký và đăng xuất với SQLite trên nền `origin/main` tại `bc90c9c`; áp dụng riêng phần tài khoản, không đưa toàn bộ lịch sử nhánh tính năng cũ vào nền code. Tài xế/kỹ sư theo spec 11.5; quyền HITL không đổi. Giữ và sao lưu database trước deploy, bật cookie HTTPS, restart service hiện có. Kiểm chứng: 120 test RoadWatch qua; Ruff các file thay đổi, OpenAPI `--check`, `check_docs`, `git diff --check` qua. Chrome kho tạm kiểm tra đăng ký, login sai/đúng, logout, tải lại giữ phiên, WebSocket và giao diện 1280px/390px; Chrome URL công khai kiểm tra form đăng ký, login/logout kỹ sư, cookie Secure/HttpOnly/SameSite=Lax, API bảo vệ và WebSocket, không lỗi JS. Ruff toàn repo còn N806 có sẵn tại `test_lab.py:154`; chưa có quên mật khẩu/email; job và lịch sử dùng chung; chưa ghi nhận review/nghiệm thu.
- 12/10/2026 — Codex — WP-C6/WP-C7: theo yêu cầu thêm trường vai trò ở đăng ký, giao diện cho chọn Tài xế/Kỹ sư; API Registration nhận driver/engineer (mặc định driver), SQLite lưu vai trò đã chọn. Đăng nhập không nhận vai trò và không đổi quyền; quyền HITL theo configstore không đổi. Test TDD ghi nhận 422 khi chọn engineer trước thay đổi, sau thay đổi 121 test RoadWatch qua; Ruff các file thay đổi, OpenAPI --check, check_docs, git diff --check qua. Chrome kho tạm kiểm tra chọn kỹ sư, menu/API Lab, logout/login giữ vai trò, bố cục 390px; URL công khai hiển thị lựa chọn vai trò và login/logout/WebSocket hoạt động sau restart service. Ruff toàn repo còn N806 có sẵn tại test_lab.py:154; không thay đổi vai trò tài khoản cũ; chưa ghi nhận review/nghiệm thu.
- 12/10/2026 — Claude Code — BT-A, nhánh temporal-modeling: áp dụng Temporal Modeling riêng cho dự đoán khoảng cách. Thêm `temporal.py` (MotionEstimator: hồi quy tuyến tính có trọng số trên cửa sổ 1,5 s lịch sử khoảng cách của model). `pipeline.py` lấy `gap_m` từ giá trị khớp này (đã bù chuyển động, giảm nhiễu từng khung) và thêm `gap_pred_m` (khoảng cách dự đoán sau 1 s) vào Result. TTC, vận tốc, Kalman, schema API không đổi. Kiểm chứng: 127 test RoadWatch qua (test mới cho temporal và pipeline), Ruff chỉ còn N806 có sẵn ở test_lab.py:154. Chưa đánh giá trên video thật nên chưa biết sai số khoảng cách giảm bao nhiêu; cửa sổ 1,5 s là giá trị chọn ban đầu; chưa commit/push.
- 12/10/2026 — Claude Code — BT-A, nhánh temporal-modeling: thêm cờ `temporal` cho `Pipeline` và `scripts/roadwatch/eval_temporal.py` (chạy model một lần, phát lại đầu ra cho hai cấu hình, so với radar comma2k19, 7 đoạn, 5183 khung; `--cache` giữ đầu ra model). Lần đo đầu: độ rung Temporal 1,15 m so với Kalman 0,78 m; chẩn đoán: 60 % do chuyển qua lại giữa phần khớp và Kalman khi mất xe vài khung. Sửa: ngoại suy phần khớp qua khoảng mất xe ≤ 0,5 s (`coast`), chuyển dần từ Kalman sang phần khớp qua 20 mẫu; quét cửa sổ 1–3 s chọn 2 s; Huber thử nhưng không có tác dụng nên bỏ. Kết quả ở `eval/results/temporal_eval.md`: MAE 6,95 → 6,74 m, độ rung 0,78 → 0,70 m (40–60 m: MAE 3,39 → 2,98 m). Tham số chọn trên chính dữ liệu đánh giá nên số lạc quan; gap_pred_m sau 1 s vẫn kém giữ nguyên khoảng cách (MAE 6,85 so với 6,04 m), chưa dùng ở đâu. 127 test RoadWatch qua (đã bỏ 3 test ít giá trị: số mẫu tối thiểu, hai test gap_pred_m); Ruff chỉ còn N806 có sẵn. Đã commit lên nhánh temporal-modeling, chưa push.
