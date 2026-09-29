# Quy tắc tài liệu RoadWatch

Áp dụng cho mọi tài liệu của nhóm: `README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `docs/` (trừ `docs/guide/`), `eval/`, `JOURNAL.md`, `WORKLOG.md`. **Không sửa `docs/guide/`**: đó là sách của môn học, do BTC quản lý.

## 1. Định dạng chung

- **Mã hoá và xuống dòng.** Markdown mã hoá UTF-8. Không đổi kiểu xuống dòng (CRLF/LF) của cả file. Nếu `git diff` báo cả file bị đổi, kiểm tra kiểu xuống dòng trước khi commit.
- **Ngôn ngữ.** Viết tiếng Việt rõ ràng, câu ngắn. Thuật ngữ tiếng Anh giữ nguyên ở lần đầu, kèm giải thích nếu người đọc có thể chưa biết.
- **Identifier giữ nguyên** và đặt trong backtick: tên trường, tên hàm, tên file, lệnh (`distance_m`, `rerun-B`, `configs/active.json`). Không dịch và không đổi chữ hoa, chữ thường.
- **Heading.**
  - Mỗi file có đúng một heading cấp 1; không nhảy cấp.
  - Mục đánh số trong spec giữ số ổn định, vì nơi khác dẫn chiếu kiểu "spec 3.7". Thêm mục mới thì đặt ở cuối hoặc dùng số con; không đánh số lại.
- **Bảng.**
  - Luôn có hàng tiêu đề; mỗi ô một ý.
  - Ký tự `|` trong ô phải viết thành `\|`.
  - Nội dung dài hơn vài dòng thì dùng danh sách, không nhồi vào ô.
- **Code block.**
  - Luôn ghi tên ngôn ngữ: `bash`, `python`, `yaml`, `json`, `text`, `mermaid`.
  - Lệnh trong tài liệu phải là lệnh chạy được, lấy từ cấu hình repo. Danh sách lệnh kiểm tra chỉ có ở [code-rules.md](code-rules.md), mục 8.
- **Liên kết.**
  - Dùng liên kết tương đối.
  - Tên file có dấu cách hoặc ngoặc (ví dụ các file requirements có đuôi ` (1).md`) phải bọc trong `<…>`: `[file 1](<../requirements/RoadWatch_Copilot_1_Tong_quan_du_an (1).md>)`.
  - Dẫn chiếu tới mục bằng số mục ("spec 3.7") thay vì anchor tự sinh, vì anchor dễ gãy khi sửa tiêu đề.

## 2. Một nội dung, một nguồn chuẩn

- Bảng nguồn chuẩn nằm ở [AGENTS.md](../../AGENTS.md), mục 2. Nơi khác chỉ tóm tắt ngắn và **dẫn chiếu** tới nguồn chuẩn, không chép lại.
- **Sơ đồ là bản trực quan dẫn chiếu tới văn bản.** Khi sơ đồ khác văn bản thì văn bản thắng, và phải sửa sơ đồ ngay.
  - [docs/architecture_diagram.md](../architecture_diagram.md) vẽ theo spec.
  - Sơ đồ trong `docs/plan/` vẽ theo bảng task ở `docs/plan/README.md`, mục 4.
- **Tên người** chỉ xuất hiện trong `docs/plan/`, `WORKLOG.md` và `JOURNAL.md`. Các nơi khác dùng vai trò: R-A, R-B, R-C, R-D, PO.

## 3. Sơ đồ Mermaid

**Cú pháp an toàn.** Các lỗi nêu ở bảng dưới đã được thử trên Mermaid 11.16.1 ngày 29/09.

| Việc | Cách viết |
|---|---|
| ID node | Ngắn, ASCII, viết hoa, không dấu: `PA`, `JN`, `WP_A1`. **ID `end` viết thường làm hỏng flowchart.** Đặt dấu cách quanh mũi tên cho dễ đọc: `A --> B` |
| Nhãn node | Luôn đặt trong ngoặc kép: `PA["perception (BT-A)"]`. **Nhãn không có ngoặc kép mà chứa `(` làm hỏng flowchart** |
| Nhãn cạnh | `A -- "nhãn" --> B`; nét đứt: `A -. "nhãn" .-> B` |
| Xuống dòng trong nhãn | `<br/>` |
| Dấu `<` và `>` | Viết `#lt;` và `#gt;`; cách này chạy được cả ở flowchart lẫn sequence diagram. **Không dùng `&lt;`**: dấu `;` của nó làm hỏng sequence diagram |
| Tin nhắn trong sequence diagram | **Không dùng `;`**: làm hỏng sơ đồ. **Không dùng `#`**, trừ khi là phần của `#lt;` hoặc `#gt;`: phần chữ sau `#` bị mất mà không báo lỗi |

**Nội dung:**
- Mỗi sơ đồ có một đoạn ngắn ngay dưới hoặc ngay trên, nói sơ đồ thể hiện gì và dẫn chiếu mục nguồn.
- **Mũi tên bàn giao ghi sản phẩm cụ thể**, không ghi chung chung. Ví dụ: schema, fixture, `Measurement`, cấu hình, dataset hoặc nhãn, run log, báo cáo, API. Nên kèm ID task (WP-xx).
- **Phân biệt MVP với mở rộng.**
  - Phần MVP tuần 1 vẽ nét liền.
  - Phần tuần 2–4 hoặc chưa quyết vẽ nét đứt (`classDef ext stroke-dasharray: 5 5`), và ghi rõ "(tuần 2–4)" hoặc mã OQ trong nhãn.
- **Đề xuất chưa duyệt** phải ghi chú (ví dụ ADR chờ duyệt) ở đoạn mô tả đi kèm.
- **Không chép một sơ đồ sang nhiều file.** Sơ đồ hệ thống chỉ nằm ở spec mục 2 và `docs/architecture_diagram.md`; nơi khác đặt liên kết.

**Kiểm tra render trước khi commit.**
- Xem bằng trình xem Markdown có hỗ trợ Mermaid (GitHub, hoặc extension Mermaid của VS Code).
- Nếu chưa render được thì ghi rõ trong PR là mới kiểm tra văn bản.
- Các phiên bản Mermaid có thể khác nhau đôi chút, nên sơ đồ nên dùng cú pháp cơ bản ở bảng trên.

## 4. ID và trạng thái

- **Giữ nguyên ID**: WP, AC, OQ, ADR, F, I, D, KS.
  - ID mới nối tiếp số lớn nhất hiện có.
  - ID bị bỏ được liệt kê ở mục "ID đã bỏ" của file chứa nó, và **không bao giờ dùng lại**.
- **Trạng thái tổng của task** chỉ ghi ở `docs/plan/README.md`: cột TT ở mục 4, và một dòng tóm tắt ở mục 4.3. Ý nghĩa ký hiệu và luật cập nhật ở mục 0 của file đó.
  - **Checklist chi tiết** nằm dưới từng task trong `docs/plan/phan-viec/<người>.md`, gồm ba nhóm: bàn giao, kiểm thử và kiểm chứng, review và nghiệm thu. Không chép checklist sang plan, và không tạo bảng trạng thái ở nơi khác.
  - Không ghi trạng thái hiện tại của code (số test, lệnh nào đã có) vào `AGENTS.md` hay các file quy tắc.
- **Không tự ghi** "APPROVED", "đã duyệt", "DONE", ✅ hay "đã nghiệm thu" khi chưa có bằng chứng tương ứng:
  - **Duyệt:** người duyệt (thường là PO) nói rõ, và nơi ghi nhận có ngày cùng người duyệt.
  - **Xong / ✅:** reviewer đã kiểm theo mục "Kiểm chứng" của task.
  - **Đạt AC:** có đúng loại bằng chứng mà spec mục 7 ghi cho AC đó (fixture hay unit test, integration test, hoặc dữ liệu thực địa; xem [code-rules](code-rules.md), mục 10), và reviewer đã kiểm. Báo cáo đánh giá thì gắn hash theo spec 5.5. Không thêm điều kiện ngoài spec.
- **Nội dung chờ duyệt** mang nhãn phiên bản, ví dụ `[v1.1]`, cho tới khi PO duyệt. Chỉ khi PO duyệt mới bỏ nhãn.

## 5. Phân biệt mức độ chắc chắn

| Loại | Cách ghi | Ví dụ |
|---|---|---|
| Giả định | Ghi "giả định" hoặc 🟡; tham số cấu hình thì liệt kê trong `provisional_keys` | `d_cam_cản` = 1,5 m (giả định, file 3) |
| Số đo | Giá trị, đơn vị, phương pháp, ngày, số mẫu, link bằng chứng | "Đo bằng thước, ảnh kèm theo" |
| Mục tiêu | Ghi "mục tiêu đề xuất" cho tới khi được chốt; nêu ai chốt | Giảm ≥ 50% (đề xuất, chốt với mentor) |
| Kết quả | Số đo so với mục tiêu, kèm hash cấu hình, dữ liệu và code; ít mẫu thì ghi "sơ bộ" hoặc "chưa kết luận" | AC-M4 với n < 200 thì là "chưa kết luận" |
| Quyết định đã duyệt | Ai duyệt, ngày nào, ghi ở đâu (ADR, OQ) | "ADR-12, PO chốt 29/09" |

**Không bịa** số đo thực địa, ngưỡng, hạn nộp hay phê duyệt. Điều chưa biết thì ghi TBD hoặc mở một Open Question.

## 6. Khi hành vi thay đổi

Sửa trong **cùng một PR** mọi nơi bị ảnh hưởng:
1. **Spec:** mục mô tả hành vi, bảng ADR và OQ, bảng tình huống lỗi (mục 6), tiêu chí AC nếu liên quan. Viết thẳng vào mục đó, không nối thêm "ghi chú sửa".
2. **Hợp đồng dữ liệu:** theo [code-rules.md](code-rules.md), mục 9.
3. **Task:** bảng ở `docs/plan/README.md` và mục chi tiết trong file phân việc.
4. **Sơ đồ bị ảnh hưởng:** spec mục 2, `docs/architecture_diagram.md`, `docs/plan/so-do.md`, sơ đồ trong file phân việc.
5. **Mục 12 của spec:** nếu code và spec lệch nhau thì thêm một dòng D-x.

**Kiểm tra trước khi mở PR:**
- liên kết nội bộ mở được;
- mọi ID được nhắc tới đều tồn tại;
- owner, reviewer và phụ thuộc trong sơ đồ khớp bảng task;
- `git diff --check` sạch.
