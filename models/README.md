# gr14VinAI: đo khoảng cách xe phía trước chỉ bằng camera

gr14VinAI nhìn hai frame camera liên tiếp và trả lời: **phía trước có xe cùng làn trong 100 m không, và cách bao nhiêu mét**. Model có 9,28 triệu tham số, chạy khoảng 30 ms mỗi frame trên CPU. Model chưa từng thấy video đường Việt Nam khi train.

| | Chạy thực tế ở Việt Nam, so với radar | Bộ dữ liệu test (34 video), so với radar | Human baseline, so với người |
|---|---:|---:|---:|
| Số frame / ảnh được chấm | 1.257 frame | 2.118 frame | 22 ảnh có xe (30 ảnh) |
| Sai số trung vị | **2,70 m** | **1,52 m** | 5,90 m |
| MAE | **4,35 m** | **2,55 m** | 5,92 m |
| Lệch không quá 15% | **83,0%** | **96,6%** | 9/22 |
| Có/không có xe | | F1 **0,946** | khớp **30/30** |

Thực tế và test chỉ chấm frame mà cả model lẫn radar đều thấy xe. Human baseline không có radar: cột đó đo model khác người bao nhiêu, không phải ai đúng hơn.

Chi tiết đánh giá (thực tế, human baseline, Comma2k19): [eval/README.md](../eval/README.md).

---

## Trong thư mục có gì

| Vị trí | Nội dung |
|---|---|
| `src_train/` | code: model, train, benchmark, phương pháp hình học, test; kiến trúc ở [src_train/README.md](src_train/README.md) |
| `../eval/` | dữ liệu, kết quả và báo cáo đánh giá |
