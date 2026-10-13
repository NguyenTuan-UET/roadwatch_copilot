---
doc_id: "RW-FEEDBACK-SETUP"
doc_type: "view"
status: "draft"
authority_for: []
---

# Tạo phiếu và lưu dữ liệu khảo sát

Theo yêu cầu khảo sát người dùng ngày 13/10/2026. Đây là bộ mẫu thu dữ liệu,
chưa có kết quả khảo sát. Không tìm thấy file `user_feedback.csv` chứa 7 câu trích
trong repo hiện tại; mẫu mới không thay thế bằng chứng cũ.

## Tạo Google Form

1. Mở [Google Apps Script](https://script.google.com/), đăng nhập tài khoản Google của bạn và tạo dự án mới.
2. Chép toàn bộ [create_feedback_form.js](create_feedback_form.js) vào `Code.gs`, thay nội dung mẫu, rồi lưu.
3. Chọn hàm `createFeedbackForm`, bấm **Run / Chạy** và cấp quyền tạo/quản lý Form khi Google yêu cầu.
4. Trong **Execution log / Nhật ký thực thi**, lấy đường dẫn **Chỉnh sửa** và **Gửi khảo sát**.
5. Mở đường dẫn chỉnh sửa, kiểm tra 6 câu và quyền truy cập của người trả lời trước khi gửi đường dẫn khảo sát cho ít nhất 5 người ngoài nhóm đã dùng sản phẩm.

Script tạo Form có 3 thang điểm 1–5, câu mở và câu đồng ý trích dẫn; không thu email
và không công khai bản tổng hợp trả lời. Chạy lại trong cùng dự án sẽ lấy lại Form
đã tạo, không thêm câu hỏi hoặc tạo một Form mới. Chưa chạy script trên tài khoản Google thực tế.

Khác với phiếu người dùng đưa ban đầu: câu 6 thêm **Không đồng ý trích dẫn**.
Người chọn đáp án này vẫn được chấm điểm, nhưng không đưa lời của họ vào phần trích
nguyên văn trong báo cáo. Sự đồng ý đối với câu trả lời mới không tự động áp dụng
cho 7 câu trích cũ; cần xác nhận riêng trước khi dùng lại các câu đó.

## CSV phản hồi

[user_feedback.csv](user_feedback.csv) là mẫu chỉ có tiêu đề, đúng 9 cột yêu cầu.
Mỗi người một dòng; chưa biết thông tin nào thì để ô đó trống. Chỉ nhập điểm nguyên
từ 1 đến 5 do người trả lời chấm. Người cũ không liên lạc lại được thì giữ dòng cũ,
để trống điểm; khi lập báo cáo hiển thị “không chấm”, không điền chữ này vào cột số.

- `user`: tên nếu được đồng ý trích kèm tên; nếu cần ẩn tên, dùng mã ổn định như `Người dùng 1`.
- `date`: ngày trả lời từ dấu thời gian của Form, định dạng `YYYY-MM-DD`; không lấy ngày tạo file.
- `quote`: nguyên văn câu 5, kể cả lỗi chính tả. Với người từ chối trích dẫn, để trống trong CSV dùng cho báo cáo; giữ câu trả lời trong bằng chứng gốc được lưu riêng.
- `fix_made`, `fix_date`: chỉ điền sau khi thực hiện sửa, kèm bằng chứng; ngày theo `YYYY-MM-DD`.
- `team_reading`: nhóm tự xếp `tích cực`, `tiêu cực` hoặc `câu hỏi`; đây không phải điểm người dùng.

Mở CSV bằng Excel/Google Sheets với mã hóa UTF-8 để giữ tiếng Việt. Dùng ứng dụng
bảng tính để lưu CSV đúng cách khi câu trích có dấu phẩy, dấu nháy hoặc xuống dòng.

## Bản sản phẩm và bằng chứng gốc

[feedback_sessions.csv](feedback_sessions.csv) ghi mỗi lần dùng sản phẩm: mã/tên
`user` khớp CSV phản hồi, ngày dùng `date_used`, bản đã dùng `product_version`
(ví dụ mã bản phát hành hoặc commit thực tế kèm ứng dụng/web), và đường dẫn bằng
chứng `evidence` nếu có. Không tự suy ra phiên bản từ câu trích.

Trong Google Form, vào **Responses / Câu trả lời**, mở menu và chọn tải câu trả lời
dạng CSV. Giữ nguyên file tải về trong `eval/`, ví dụ tên `google_form_responses_YYYY-MM-DD.csv`
với ngày tải thực tế. Đây mới là bằng chứng gốc: có dấu thời gian, điểm và lựa chọn
đồng ý trích dẫn. Không tự tạo file này hoặc sửa nội dung của nó.

Đối chiếu file gốc khi nhập `user_feedback.csv`; không ghi đè bằng chứng 7 phản hồi
cũ. Giữ file có tên thật ở nơi nhóm kiểm soát truy cập; không commit CSV phản hồi
thật hoặc CSV gốc chứa thông tin cá nhân lên repo công khai.

Các đường dẫn `src_train/app.py`, `src_train/eval_evidence.py` và
`evaluation_evidence.md` trong hướng dẫn được cung cấp không có ở repo này.
Bộ mẫu không tạo báo cáo tự động hoặc giả định các chương trình đó tồn tại.

API tạo phiếu tham khảo [FormApp](https://developers.google.com/apps-script/reference/forms/form-app),
[Form](https://developers.google.com/apps-script/reference/forms/form) và
[ScaleItem](https://developers.google.com/apps-script/reference/forms/scale-item) của Google.
