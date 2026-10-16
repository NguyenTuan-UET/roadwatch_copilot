# Evaluation protocol (4-tuple): gr14VinAI

Sản phẩm là model thị giác, không phải agent LLM. Bốn phần của khung: request = một case camera; environment = model, dữ liệu và máy chạy; stopping criteria = model chạy bao nhiêu lần, trong bao lâu; scorer = cách chấm. Có ba lượt đo: bộ dữ liệu (máy tính, video Comma2k19), thực tế (ứng dụng, đường Việt Nam) và human baseline (30 ảnh đường Việt Nam).

## Request: đầu vào test là gì

- Một case là một cặp frame liên tiếp (cách nhau 0,05 giây) từ camera trước. Câu hỏi: phía trước có xe cùng làn trong 100 m không, nếu có thì cách bao nhiêu mét.
- **Bộ dữ liệu:** `eval/inputs/golden.jsonl`, 300 case từ 34 video test Comma2k19: 150 on (có xe 35-92 m, giữa làn), 75 off (không có xe cùng làn), 75 edge (xe dưới 35 m, trên 92 m, hoặc sát mép làn). Rút ngẫu nhiên (seed 0), lần lượt từng video; không case nào do AI nghĩ ra. Đại diện cho cao tốc California, ngày và đêm, camera cao 1,22 m; chưa đại diện cho chạng vạng (24 video bị loại), trời mưa, đường Việt Nam.
- **Thực tế:** video quay trên đường nội khu Vinhomes Ocean Park 2 và cao tốc Hà Nội - Hải Phòng, 28 phút, lấy 2 frame/giây (`eval/radar_vinhomeocp/`). Theo nhóm: quay bằng iPhone 14 Pro Max, radar của xe VinFast VF8.
- **Human baseline:** 30 ảnh đường Việt Nam (`eval/human_baseline/anh/`), cùng câu hỏi.
- **Ngoài phạm vi (theo nhóm xác định):** xe gần 10-20 m, camera điện thoại, trời mưa. 10-20 m đo trên tập test và trên dữ liệu thực tế; camera điện thoại từ lượt thực tế; trời mưa CHƯA CÓ.

## Environment: chạy trong bối cảnh nào

- Model `gr14VinAI.onnx` (9.282.186 tham số, 37,65 MB). Ngưỡng báo có xe 0,40 chọn trên validation, giữ cố định khi chấm.
- **Bộ dữ liệu:** onnxruntime CPU, 4 luồng, mỗi lần một frame; 34 video test (3.778 frame có nhãn radar), không video nào nằm trong train hay validation. 6 video test cùng chuyến xe với một video train, vì 100 video ban đầu được chia theo đoạn chứ không theo chuyến.
- **Thực tế:** ứng dụng của nhóm chạy model trên video và hiện khoảng cách model, radar và Δ = model − radar trên màn hình.
- Tiền xử lý: cắt cửa sổ 512 × 256 quanh điểm tụ, đưa vào frame hiện tại và frame trước. Model không nhớ gì giữa các case và không dùng radar; radar chỉ là đáp án.

## Stopping criteria: dừng khi nào

- Mỗi case chạy đúng một lần, trả lời ngay: không lặp, không thử lại, không chọn đáp án tốt nhất.
- pass@5 và pass^5 dùng đúng 5 frame liên tiếp quanh case (0,25 giây). Một lượt chấm kết thúc khi hết 300 case; hệ thống thiếu đáp số ở bất kỳ case nào thì cả dòng ghi CHƯA CÓ.
- Ngân sách thời gian: camera 20 hình/giây, tức 50 ms mỗi frame. Riêng model 30,25 ms (trung vị; p95 33,5 ms), trong ngân sách; cả pipeline (giải mã video, cắt ảnh, model) 54,61 ms, vượt ngân sách. Trên điện thoại: CHƯA CÓ.
- Model, ngưỡng và bộ case chốt trước khi chấm; không chỉnh gì sau khi xem kết quả.

## Scorer: chấm thế nào

- Chấm bằng code, không dùng LLM-judge, không chấm bằng mắt. Đáp án là radar, một cảm biến độc lập với camera và model.
- **Luật đạt:** case có xe phải báo có xe và lệch không quá 15% so với radar; case không có xe phải báo không có xe.
- **Bộ dữ liệu** (hàm `passed` trong `src_train/eval_evidence.py`): tỉ lệ đạt, đúng, đủ, an toàn (không bỏ sót xe, không báo xa hơn thực tế quá 15%), MAE, pass@5, pass^5; chạy hai lần để so (`eval/results/deterministic_rerun_report.md`).
- **Thực tế** (`eval/report/scripts/make_readme_figures.py`): sai số = |Δ| trên frame radar có số; OCR đọc sai được bỏ tối đa 5 trên mỗi 20 frame liên tiếp; báo MAE, trung vị, tỉ lệ lệch không quá 15%.
- **Human baseline:** không có radar, nên so câu trả lời của model với của người (khớp có/không có xe, độ lệch khoảng cách), không chấm đúng sai.
- Không áp dụng: citation và RAGAS, vì sản phẩm không truy xuất tài liệu.
