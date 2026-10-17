# Cách đo và giới hạn

## Bộ kiểm thử

- 34 video test Comma2k19, 3.778 frame có nhãn radar; 2.226 frame radar có xe. Không video nào trùng train/validation, nhưng 6 video test cùng chuyến xe với video train.
- 300 ca golden: 150 có xe, 75 không có xe, 75 ca biên; lấy từ 34 video trên với seed 0. Đây là tập con, không phải một bộ test độc lập.
- Nhãn đánh giá chọn xe gần nhất trong 100 m, lệch tâm làn không quá 1,5 m; tâm làn theo đường đi thật của xe.
- Mỗi ca chấm một lần.
- Ca đạt: báo đúng không có xe, hoặc báo có xe và khoảng cách lệch không quá 15% so với radar. F1 tổng hợp precision và recall phát hiện xe cùng làn.
- MAE là sai số tuyệt đối trung bình. Phải ghi rõ tính trên mọi frame radar có xe hay chỉ các frame hệ thống và radar cùng thấy xe; hai cách không tương đương.
- Hai lần chấm cho kết quả giống nhau: [kết quả tái lập](results/deterministic_rerun_report.md). pass@5 / pass^5 trong JSON lần lượt là đạt ở ít nhất một / cả năm frame liên tiếp quanh ca.

## Thực địa tại Việt Nam

Video khoảng 28 phút tại Vinhomes Ocean Park 2 và cao tốc Hà Nội – Hải Phòng; theo nhóm, camera iPhone 14 Pro Max và radar xe VinFast VF8. Kết quả gộp cả hai địa điểm.

Lấy 2 frame/giây; đọc bằng OCR các số model, radar và Δ trên màn hình; sai số = |Δ|.

1. Tổng 3.355 frame → 1.451 frame có số radar → 1.437 frame có cả radar và Δ.
2. Kiểm tra ba số có khớp nhau sau quy tắc làm tròn của màn hình hay không. Mỗi 20 frame liên tiếp có radar và Δ, bỏ tối đa 5 frame đọc sai, ưu tiên độ lệch lớn nhất.
3. Bỏ 180 frame; còn 1.257 frame được chấm, gồm 12 frame đọc sai được giữ lại theo giới hạn trên.

Đây là số đo gián tiếp qua OCR sau lọc, không phải log radar đồng bộ trực tiếp. Không dùng để kết luận riêng cho Ocean Park hoặc về tỷ lệ bỏ sót xe trong toàn video. Dữ liệu và script: [field_metrics.json](radar_vinhomeocp/field_metrics.json), [make_readme_figures.py](report/scripts/make_readme_figures.py).

## Thời gian xử lý và phạm vi

Thời gian gr14VinAI đo 500 lần sau 50 lần làm nóng: trung bình 30,56 ms, trung vị 30,25 ms, p95 33,5 ms. Toàn bộ xử lý trung bình 54,61 ms/frame, vượt ngân sách 50 ms của 20 FPS. Trên điện thoại (`/phone` thêm vào màn hình chính, mất mạng, GPU qua WebGPU của Safari): khoảng 70 ms/frame; đo trong điều hòa (máy được giữ mát, như trong ô tô bật điều hòa) giữ 15 FPS; khi máy nóng tụt về 12 FPS do giảm xung nhiệt. Dung lượng tải về dưới 90 MB; nhóm đo ngày 17/10/2026, chưa đo lặp lại như benchmark laptop. [Video demo](../video/offline.mp4) chỉ minh họa app chạy offline, không phải bản ghi số đo. [Số liệu benchmark](results/model_benchmark_metrics.json).

Chưa kiểm chứng trời mưa; tập test đã loại 24 video chạng vạng. So sánh với baseline của dự án không chứng minh hơn SafeGap hay sản phẩm thị trường. 30 ảnh human baseline không có radar nên chỉ đo mức đồng thuận với người, không xác định ai đúng hơn.
