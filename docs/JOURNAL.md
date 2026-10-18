# Nhật ký phát triển — Nhóm P-014

**Thành viên:** Cương, Khánh, Tuấn, Linh.
**Người tổng hợp và chốt định hướng:** Cương.
**Cập nhật:** 18/10/2026.

Nhật ký ghi lại hành trình từ chọn đề tài đến triển khai RoadWatch, dựa trên hồi thuật của Cương và lịch sử Git. Các tuần dưới đây là các giai đoạn theo hồi thuật; ngày commit là mốc đối chiếu, không tự thay cho lịch tuần hoặc ngày họp mentor. Chi tiết công việc và bằng chứng nằm trong [WORKLOG.md](WORKLOG.md).

## Tuần 1 — Nhập nhóm, tìm hiểu và chọn AegisGate

### Mục tiêu và việc đã làm

Nhóm tập hợp bốn thành viên, cùng tìm hiểu các hướng đề tài có thể triển khai trong chương trình. Linh, Khánh và Tuấn đóng góp thông tin, trao đổi ý tưởng và cùng Cương xem xét lựa chọn. Cương là người tổng hợp ý kiến và chốt đề tài đầu tiên: hệ thống bảo vệ AI agent bằng guardrail, mang tên **AegisGate**.

Hướng ban đầu là xây dựng lớp kiểm tra đầu vào/đầu ra cho ứng dụng LLM, phát hiện prompt injection, hạn chế rò rỉ dữ liệu nhạy cảm và có con người tham gia xử lý sự cố. Cương chuẩn bị bộ tài liệu Gate 1 gồm brief, PRD, luồng giao diện và kế hoạch nhóm. Commit `639cc83` ngày 18/09/2026 ghi nhận bộ tài liệu này.

### Khó khăn và bài học

Nhóm mới tiếp cận bài toán nên đánh giá ban đầu còn thiên về ý tưởng và tính năng. Việc có một đề tài hấp dẫn chưa đủ để xác nhận nhóm có dữ liệu, kiến thức chuyên môn và phương pháp đánh giá phù hợp.

Bài học của tuần là cần kiểm tra tính khả thi sớm, trước khi đầu tư nhiều vào kiến trúc và triển khai.

### Hướng chuyển sang tuần 2

Cương phụ trách đánh giá sâu hơn về dữ liệu và yêu cầu chuyên môn của AegisGate; cả nhóm tiếp tục đóng góp ý kiến để quyết định có nên theo đuổi.

## Tuần 2 — Đánh giá lại và chuyển sang TrafficEye Edge

### Mục tiêu và việc đã làm

Cương chủ trì tìm hiểu và đánh giá AegisGate. Qua quá trình này, nhóm nhận thấy dữ liệu phục vụ bài toán chưa khả thi và yêu cầu về bảo mật chưa phù hợp với năng lực hiện tại. Sau khi kết hợp ý kiến của các thành viên, Cương chốt chuyển sang **TrafficEye Edge — camera giao thông hỗ trợ phạt nguội trên thiết bị biên**.

Cương xây dựng đặc tả, kiến trúc, kế hoạch triển khai và phân chia nhiệm vụ. Các commit `e1b5a76`, `885299e` và `260ac4f` ngày 22/09/2026 ghi nhận spec, tài liệu Gate 1 và timeline có phân công. Linh, Khánh và Tuấn tìm đọc các bài báo, khảo sát phương pháp có thể tích hợp vào hướng đề tài mới; đóng góp này được ghi theo hồi thuật của Cương, chưa gắn với danh sách bài báo cụ thể.

### Phản hồi mentor và quyết định

Khi trao đổi với mentor, nhóm nhận ra đề tài vẫn chưa thuyết phục về người dùng mục tiêu và vấn đề thực tế cần giải quyết (pain point). Dù đã có spec và phân công, nhóm cần xem lại lý do sản phẩm nên tồn tại và ai sẽ sử dụng nó.

Nhóm quyết định tiếp tục điều chỉnh hướng đề tài thay vì giữ TrafficEye Edge chỉ vì đã đầu tư công sức vào tài liệu.

### Bài học và hướng tiếp theo

Tính khả thi kỹ thuật phải đi cùng nhu cầu sử dụng. Nhóm cần làm rõ người dùng, hoàn cảnh sử dụng và giá trị mang lại trước khi mở rộng danh sách tính năng. Đây là cơ sở để chuyển sang RoadWatch ở tuần 3.

## Tuần 3 — Xây dựng RoadWatch và nhận ra phạm vi quá rộng

### Mục tiêu và việc đã làm

Nhóm chốt **RoadWatch Copilot**, hướng tới trợ lý kèm lái cho tài xế mới trên cao tốc. Trong nửa đầu giai đoạn này, nhóm dành nhiều thời gian làm rõ các bài toán, đầu vào/đầu ra và cách phối hợp giữa các phần.

Phạm vi ban đầu được thể hiện trong lịch sử như sau:

- **BT-A — Thị giác máy tính:** phát hiện và theo dõi xe, chọn xe phía trước, ước lượng khoảng cách và chất lượng quan sát. Các nhánh thử nghiệm còn có nhận diện biển báo, làn đường và vùng có thể đi.
- **BT-B — Quyết định cảnh báo:** ghép dữ liệu, xác định khả năng cảnh báo, quản lý trạng thái và ưu tiên cảnh báo; chuẩn bị câu tiếng Việt thu sẵn.
- **BT-C — Cấu hình và kiểm chứng:** quản lý cấu hình có người duyệt (HITL), nhật ký, chạy lại dữ liệu, công cụ dòng lệnh và báo cáo đánh giá.

Cương hoàn thành phần đặc tả, phân công và bộ khung triển khai do mình phụ trách trong giai đoạn đó. Các commit ngày 28/09 ghi nhận lần lượt hợp đồng dữ liệu, bộ quyết định, kho cấu hình, nguồn dữ liệu, xử lý ảnh, runtime và đánh giá. Ngày 29/09–02/10, Cương tiếp tục bổ sung CLI, dữ liệu kiểm thử, xử lý các tình huống cảnh báo, hợp đồng bàn giao và audio.

Các nhánh của nhóm đồng thời thử nghiệm nhận diện đối tượng, theo dõi, biển báo, làn đường và tối ưu xử lý. Đây là bằng chứng về khối lượng đã triển khai; không đồng nghĩa toàn bộ hệ thống đã được nghiệm thu hoặc đạt chất lượng trên dữ liệu thực tế.

### Khó khăn và quyết định thu hẹp

Sau cuộc họp mentor và tham khảo thêm nhiều nguồn, nhóm nhận thấy phạm vi đang quá rộng. Nhiều bài toán cùng lúc làm tăng công sức tích hợp, kiểm thử và đánh giá, trong khi thời gian có hạn.

Cương chốt tập trung vào một ngách cuối cùng: **ước lượng khoảng cách từ camera**. Trọng tâm chuyển sang chất lượng mô hình, tự hiệu chỉnh camera và đánh giá kết quả. Các phần cảnh báo, audio, HITL và thử nghiệm khác được ghi ở đây như lịch sử phát triển, không tự coi là các mục tiêu bắt buộc của bản nộp cuối.

### Bài học và hướng tiếp theo

Hoàn thành nhiều phần code chưa chắc tạo ra một sản phẩm đủ rõ và dễ chứng minh hiệu quả. Nhóm cần một bài toán trọng tâm với cách đánh giá cụ thể, rồi phân công lại để đưa luồng chính đến bước triển khai.

## Tuần 4 — Tập trung khoảng cách và triển khai

### Phân công sau khi thu hẹp

Phân công ban đầu của giai đoạn này; được điều chỉnh lại ở giai đoạn hoàn thiện (mục dưới).

| Thành viên | Trách nhiệm theo phân công của nhóm |
|---|---|
| Cương | Thiết kế mô hình, đánh giá kết quả (evaluation), chốt hướng kỹ thuật; rà soát tiêu chí chương trình và chuẩn bị thuyết trình |
| Khánh | Giải quyết tự hiệu chỉnh camera (autocalibration); dự kiến phụ trách video demo |
| Tuấn | Hỗ trợ kỹ thuật và triển khai lên server; phụ trách slide |
| Linh | Thiết kế giao diện |

### Kết quả đến thời điểm ghi nhật ký

Theo cập nhật của Cương, nhóm đã đi đến bước triển khai. Lịch sử ngày 07/10 bổ sung bằng chứng kỹ thuật cho giai đoạn này: `fdb8cdd` đưa vào hướng tự hiệu chỉnh kết hợp model gr14VinAI; `b578580` bổ sung xử lý từ khung hình đầu và cập nhật giao diện theo từng khung; `665fe98` thêm FastAPI server, Docker và quy trình chạy; `e4c9579` bổ sung hợp đồng API cho giao diện; `5fbb6b0` và `7b3524b` bổ sung đường truy cập demo qua tunnel.

Các commit trên mang tên tác giả Khánh. Phân công model/evaluation của Cương, hỗ trợ triển khai của Tuấn và thiết kế giao diện của Linh được ghi theo hồi thuật của Cương; tác giả commit không được dùng thay cho toàn bộ đóng góp của nhóm. Bằng chứng ở thời điểm này ghi nhận code phục vụ triển khai và demo; số đo chất lượng mô hình và việc nghiệm thu được bổ sung ở giai đoạn hoàn thiện (mục dưới).

## Giai đoạn hoàn thiện — Dữ liệu thực tế, thiết bị biên và chuẩn bị nộp (đến 16/10)

### Việc đã làm

Phân công được điều chỉnh lại cho giai đoạn này. Toàn bộ các việc dưới đây đã hoàn thành và được nhóm nghiệm thu (xác nhận của Cương, 16/10/2026).

| Thành viên | Việc trong tuần cuối | Trạng thái |
|---|---|---|
| Cương | Cùng Tuấn thu thập dữ liệu thực tế; làm video demo; viết lại tài liệu | ✅ Hoàn thành, đã nghiệm thu |
| Tuấn | Hoàn thiện triển khai trên thiết bị biên; cùng Cương thu thập dữ liệu thực tế | ✅ Hoàn thành, đã nghiệm thu |
| Khánh | Rà soát tổng thể repo | ✅ Hoàn thành, đã nghiệm thu |
| Linh | Làm slide | ✅ Hoàn thành, đã nghiệm thu |
| Cả nhóm | Tối ưu tốc độ chạy trên web và giao diện demo; họp thống nhất cách trình bày và xử lý các khó khăn còn tồn đọng | ✅ Hoàn thành, đã nghiệm thu |

✅ **Triển khai trên thiết bị biên.** Tuấn hoàn thiện việc chạy model ngay trên điện thoại. Lịch sử ngày 14–16/10 ghi nhận phần này: `4fcfead` đo trực tiếp từ camera điện thoại, `611c769` đưa model, chọn làn và vẽ làn lên điện thoại như trên laptop, `72df321` thêm bảng điều khiển và bật/tắt hiệu chuẩn, `5cd39f7` và `c5b8d05` thêm trang cài đặt và icon cho `/phone`.

✅ **Thu thập dữ liệu thực tế và đánh giá.** Cương và Tuấn quay video trên đường nội khu Vinhomes Ocean Park 2 và cao tốc Hà Nội - Hải Phòng, so khoảng cách của model với radar xe VF8 hiện trên cùng màn hình. Trên 1.257 frame được chấm, sai số trung vị là 2,70 m và 83,0% frame lệch không quá 15%; ở 10-20 m sai số trung vị là 0,70 m, còn trên 60 m sai số tăng rõ. Nhóm bổ sung human baseline trên 30 ảnh đường Việt Nam và kết quả trên bộ dữ liệu test Comma2k19. Toàn bộ dữ liệu, cách đo và kết quả nằm ở [eval/](../eval/README.md); commit `d21104b` ngày 16/10 đưa phần model và đánh giá vào repo.

✅ **Tối ưu web và giao diện demo.** Nhóm tối ưu tốc độ chạy trên web và giao diện demo: màn hình chờ đến khi tải xong tài nguyên (`055b9ff`), dọn lại bố cục giao diện (`463a1a1`, `2f49525`), ảnh nền và cảnh mở đầu cho trang web và trang điện thoại (`ba847e6`, `04d48cf`).

✅ **Rà soát repo và tài liệu.** Khánh rà soát tổng thể repo. Cương viết lại tài liệu cho khớp với phạm vi cuối: đánh giá model chỉ dựa trên thư mục `eval/`, bỏ các kế hoạch kiểm chứng cũ không còn dùng.

✅ **Slide và video demo.** Linh hoàn thành slide, Cương hoàn thành video demo.

✅ **Họp nhóm.** Cả nhóm họp, thống nhất cách trình bày sản phẩm và xử lý nốt các khó khăn còn tồn đọng trước khi nộp.

## Tuần cuối — Tổng hợp code, hoàn thiện bản trình bày và nộp bài (đến 18/10)

### Việc đã làm

| Thành viên | Việc trong tuần cuối |
|---|---|
| Cương | Tổng hợp lại code cho bản nộp |
| Tuấn | Nghiên cứu hướng phát triển tương lai của sản phẩm |
| Khánh, Linh | Tối ưu slide và bổ sung thêm video demo |

Sau khi các phần chính đã chạy được, tuần cuối dành cho việc gom code về một bản nộp thống nhất và hoàn thiện phần trình bày. Song song, nhóm xem xét sản phẩm có thể đi tiếp theo hướng nào sau chương trình.

✅ **Nộp bài.** Nhóm hoàn thành và nộp bài ngày 18/10/2026: bản triển khai tại [c4-app-014.vercel.app](https://c4-app-014.vercel.app/), video demo trên [YouTube](https://youtu.be/Su2nJbZoxnE), slide ở [docs/slides/](slides/), tài liệu đồng bộ theo [README](../README.md).

### Khó khăn

Tuần này nhóm không gặp khó khăn đáng kể nhờ được mentor hỗ trợ trong quá trình hoàn thiện.

## Bài học rút ra

Nhóm đi qua ba hướng đề tài và một lần thu hẹp lớn bên trong RoadWatch. Mỗi lần thay đổi xuất phát từ việc hiểu rõ hơn rào cản dữ liệu, năng lực, nhu cầu người dùng hoặc khối lượng triển khai. Điều nhóm rút ra là phải kiểm chứng sớm các giả định này, chốt phạm vi đủ hẹp và dành thời gian cho đánh giá, tích hợp cùng bằng chứng nộp bài.
