# Evaluation Evidence Report: gr14VinAI

gr14VinAI là model thị giác: từ ảnh camera trả lời có xe cùng làn trong 100 m không và cách bao nhiêu mét. Việc chấm do code làm, so với radar; LLM-judge, citation và RAGAS không áp dụng. Mọi con số là số đo; phần chưa có dữ liệu ghi CHƯA CÓ.

Nguồn số đo: `src_train/eval_evidence.py` (golden, so sánh trên bộ dữ liệu, `eval/results/`), `eval/report/scripts/make_readme_figures.py` (thực địa, human baseline).

## 1. Benchmark spec (4-tuple)

Chi tiết: [evaluation_protocol.md](evaluation_protocol.md). Tóm tắt:

- **Request:** một cặp frame liên tiếp từ camera trước; câu hỏi: có xe cùng làn trong 100 m không, cách bao nhiêu mét.
- **Environment:** `gr14VinAI.onnx` (9.282.186 tham số), ngưỡng 0,40 chọn trên validation; onnxruntime CPU 4 luồng. Model không dùng radar và không nhớ gì giữa các case.
- **Stopping criteria:** mỗi case chạy đúng một lần, không thử lại; pass@5 / pass^5 dùng đúng 5 frame liên tiếp. Model, ngưỡng và bộ case chốt trước khi chấm.
- **Scorer:** code so với radar. Case có xe: phải báo có xe và lệch không quá 15%; case không có xe: phải báo không có xe.

## 2. Golden dataset

- `eval/inputs/golden.jsonl`, 300 case: 150 on (có xe 35-92 m, giữa làn), 75 off (không có xe cùng làn), 75 edge (xe dưới 35 m, trên 92 m, hoặc sát mép làn).
- Nguồn: frame của 34 video test Comma2k19, đáp án là nhãn radar. Không case nào do AI nghĩ ra; rút ngẫu nhiên (seed 0), lần lượt từng video.
- "Cùng làn": xe gần nhất trong 100 m, cách tâm làn không quá 1,5 m; tâm làn bám theo đường đi thật của xe.

## 3. Kết quả định lượng (golden, 300 case)

| Hệ thống | Đạt | Đúng | Đủ | An toàn | MAE khi báo có xe | pass@5 | pass^5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hình học (bounding box + pinhole) | 32,7% | 13,3% | 21,8% | 38,7% | 9,6 m | CHƯA CÓ | CHƯA CÓ |
| **gr14VinAI** | **83,7%** | **86,2%** | **90,2%** | **90,0%** | **2,8 m** | **90,0%** | **78,0%** |

- **Đúng:** case có xe, báo có xe và trong dung sai 15%. **Đủ:** case có xe mà hệ thống phát hiện được. **An toàn:** không bỏ sót xe và không báo xa hơn thực tế quá 15%. **pass@5 / pass^5:** đạt ở ít nhất 1 / cả 5 frame liên tiếp quanh case.
- Theo loại case (gr14VinAI): on 94,7%, off 76,0%, edge 69,3%.
- Reproducibility: hai lần chạy cùng đạt 83,7%, mọi đầu ra giống hệt ([deterministic_rerun_report.md](results/deterministic_rerun_report.md)).

**Ngoài phạm vi (theo nhóm xác định):**

| Nhóm | Dữ liệu | Kết quả |
|---|---|---|
| Xe gần 10-20 m, bộ dữ liệu | 60 frame test, 4 video | đạt 95,0%; phát hiện 100%; MAE 2,27 m |
| Xe gần 10-20 m, thực tế | 236 frame | lệch ≤ 15%: 89,8%; MAE 1,41 m |
| Camera điện thoại, đường Việt Nam | 1.257 frame (mục 5) | lệch ≤ 15%: 83,0%; MAE 4,35 m |
| Trời mưa | CHƯA CÓ | CHƯA CÓ |

## 4. So sánh

### 4.1. Với phương pháp hình học (3.778 frame test)

Phương pháp hình học không học từ dữ liệu: tìm khung xe bằng detector có sẵn rồi tính khoảng cách từ đáy khung bằng mô hình camera lỗ kim. Sai số tính trên frame mà hệ thống và radar cùng thấy xe.

| Hệ thống | Precision | Recall | F1 | Frame cùng thấy xe | MAE | Trung vị | Lệch ≤ 15% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hình học (bounding box + pinhole) | 0,858 | 0,267 | 0,407 | 594 | 8,91 m | 4,84 m | 59,3% |
| **gr14VinAI** | **0,940** | **0,951** | **0,946** | **2.118** | **2,55 m** | **1,52 m** | **96,6%** |

### 4.2. Với con người (30 ảnh đường Việt Nam)

Một người đánh giá xem 30 ảnh trong `eval/human_baseline/anh/` và ghi có xe cùng làn không, cách bao nhiêu mét; gr14VinAI trả lời cùng 30 ảnh. Các ảnh này không có radar, nên bảng dưới đo **model khác người bao nhiêu**, không chấm ai đúng hơn.

| | Kết quả |
|---|---:|
| Có/không có xe khớp với người | 30/30 (22 có xe, 8 không có xe) |
| Lệch khoảng cách, 22 ảnh có xe: trung bình / trung vị | 5,92 m / 5,90 m |
| Lệch ít nhất / nhiều nhất | 4,2 m / 7,8 m |
| Ảnh lệch không quá 15% so với người | 9/22 |

Dữ liệu: `eval/human_baseline/nguoi_danh_gia.csv`, `gr14VinAI.csv`, `comparison_30_images.csv`.

## 5. Thực tế: Vinhomes Ocean Park 2 và cao tốc Hà Nội - Hải Phòng

Video 28 phút, ứng dụng hiện khoảng cách model, radar và Δ; lấy 2 frame/giây, đọc bằng OCR, sai số = |Δ|. Chấm 1.257 frame có số radar (quy tắc lọc: [README](../README.md#1-đánh-giá-thực-tế-vinhomes-ocean-park-2-và-cao-tốc-hà-nội---hải-phòng)).

| Phạm vi | Frame | MAE | Trung vị | Lệch ≤ 15% | Δ trung bình |
|---|---:|---:|---:|---:|---:|
| Mọi frame | 1.257 | 4,35 m | 2,70 m | 83,0% | −2,62 m |
| Radar trong 100 m | 1.215 | 4,00 m | 2,60 m | 83,9% | −2,25 m |

Theo khoảng cách: 10-20 m MAE 1,41 m, 20-60 m 3,1-4,4 m, 60-100 m 9,8-13,8 m. Dữ liệu: `eval/radar_vinhomeocp/`. Thời gian chạy mỗi frame trên điện thoại: CHƯA CÓ.

## 6. Feedback người dùng

`eval/inputs/user_feedback.csv`: 25 phản hồi, mỗi dòng có nhóm, điểm, nguyên văn và đề xuất cải tiến. 20 dòng có điểm (1-3), trung bình 1,95; 5 dòng cuối không có điểm.

| Nhóm | Số phản hồi | Điểm TB | Ý chính |
|---|---:|---:|---|
| Giao diện (cả điện thoại) | 7 | 2,0 | log chiếm chỗ, thiếu thanh tiến độ và nút dừng, màu tối, chật trên điện thoại |
| Độ chính xác | 4 | 1,75 | chưa rõ có tính xe máy/xe tải không; sợ nhầm làn ở đường cong; chưa có bằng chứng cho mưa, ngược sáng; đổi điện thoại phải hiệu chỉnh camera |
| Thiết bị edge | 3 | 1,33 | nóng máy, pin, không hiện FPS/nhiệt độ |
| Hiệu năng | 2 | 2,0 | video dài chạy chậm, log cập nhật liên tục |
| An toàn | 1 | 1,0 | hiện hai chữ số thập phân tạo cảm giác chính xác giả |
| Hướng mở rộng, pain point | 3 | 3,0 | dùng camera hành trình có sẵn; chưa nói người lái nên làm gì |
| Khác (tiếp cận, xử lý lỗi, tương thích, âm thanh, demo) | 5 | 2,5 | màu khó phân biệt; lỗi đọc video khó hiểu; hỏi iPhone; thích cảnh báo giọng nói; muốn có video mẫu |

Việc đã sửa theo feedback và ngày sửa: CHƯA CÓ (file chỉ ghi đề xuất).

## 7. Before/after

Vòng 1-5 đo trên cùng 10 video test ban đầu, cùng nhãn và cùng bộ golden của 10 video đó, nên so trực tiếp được. Số được ghi lúc đo trong `eval/inputs/model_iteration_history.json`; file model cũ không còn.

| Chỉ số | Vòng 1 (0,92 tr. tham số) | Vòng 2 (5,06 tr.) | Vòng 3 (9,19 tr.) | Vòng 4 (+ lật gương) | Vòng 5 (+ phóng ảnh) |
|---|---:|---:|---:|---:|---:|
| Test: MAE | 8,05 m | 5,93 m | 4,42 m | 4,12 m | 3,87 m |
| Test: F1 có xe | 0,794 | 0,859 | 0,898 | 0,898 | 0,943 |
| Golden: tỉ lệ đạt | chưa đo | 66,3% | 79,7% | 78,3% | 86,7% |
| Golden: pass^5 | chưa đo | 61,0% | 73,7% | 75,0% | 84,0% |
| Golden: an toàn | chưa đo | 75,3% | 85,3% | 84,7% | 94,0% |
| Latency trung vị CPU | 3,16 ms | 12,56 ms | 14,39 ms | 29,46 ms | 56,3 ms |

- **Vòng 1 → 2:** mạng MBConv 12 khối → 23 khối, dữ liệu giữ nguyên.
- **Vòng 3:** kiến trúc hai luồng (toàn cảnh + fovea quanh điểm tụ), attention do radar hướng dẫn, đầu ra phân phối khoảng cách; train trên mọi frame thay vì 120 frame mỗi video.
- **Vòng 4:** cùng trọng số, lấy trung bình ảnh gốc và ảnh lật gương (thời gian chạy gấp đôi).
- **Vòng 5:** train lại với phép phóng ảnh quanh điểm tụ (0,8-1,3 lần, nhãn đổi theo d/s).

**Vòng 6 và vòng cuối** (tập test và nhãn đổi, nên không chung bảng với vòng 1-5; đối chiếu hai định nghĩa nhãn: `eval/inputs/label_rule_comparison.json`). Vòng 6 thêm 254 video và đổi "cùng làn" sang hành lang bám theo đường đi của xe. Vòng cuối bỏ 24 video chạng vạng khỏi train/validation/test và lấy mẫu cân bằng theo (ngày, đêm) × khoảng cách; train hai seed, chọn seed 2 trên validation. Chấm trên cùng 34 video test:

| Model | MAE | F1 có xe |
|---|---:|---:|
| Vòng 6 | 2,83 m | 0,949 |
| **Vòng cuối** | **2,73 m** | **0,946** |

Trên validation hai seed vòng cuối đạt MAE 2,28 / 2,15 m so với 2,32 m của vòng 6: chênh lệch cùng cỡ chênh lệch giữa hai seed. Chỉ số đầy đủ: [model_benchmark_report.md](results/model_benchmark_report.md).

## Nguồn tham khảo

- Dữ liệu: Comma2k19 của comma.ai, giấy phép MIT.
- Kiến trúc: Kiến trúc hai luồng gr14VinAI do tác giả tự thiết kế và huấn luyện từ đầu (from scratch) trên tập dữ liệu của dự án, tích hợp luồng toàn cảnh ConvNeXt, luồng fovea độ nét cao, nhúng bản đồ hình học camera, spatial attention định hướng bởi radar và đầu ra phân phối khoảng cách.
