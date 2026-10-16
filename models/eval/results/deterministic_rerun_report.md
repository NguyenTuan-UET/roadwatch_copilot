# Reproducibility: hai lần chạy trên toàn bộ golden dataset

Cùng model, cùng ngưỡng, cùng 300 case (mỗi case 5 frame), chạy hai lần liên tiếp bằng `python src_train/eval_evidence.py`.

| Hệ thống | Đạt lần 1 | Đạt lần 2 | Case có kết quả đạt/không đạt giống nhau |
|---|---:|---:|---:|
| gr14VinAI | 83.7% | 83.7% | 100.0% |

Chênh lệch lớn nhất giữa hai lần chạy trên mọi đầu ra (xác suất có xe, khoảng cách): 0.000000.

Model là một mạng nơ-ron chạy tất định, không có bước lấy mẫu ngẫu nhiên, và người chấm là code so với nhãn radar, không phải LLM-judge; vì vậy hai lần chạy cho cùng kết quả. Độ ổn định của sản phẩm theo thời gian được đo bằng pass^5 trên 5 frame liên tiếp (mục 3 của báo cáo).
