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
- **Tên người** chỉ xuất hiện trong `WORKLOG.md` và `JOURNAL.md`. Các nơi khác dùng vai trò: R-A, R-B, R-C, R-D, PO.

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
- **Bảng task và checklist** (`docs/plan/`) đã gỡ khỏi repo ngày 09/10/2026 vì không còn khớp code. ID `WP-…` còn lại trong spec và tài liệu khác là tham chiếu lịch sử; nội dung cũ đọc bằng `git show de4611f:docs/plan/README.md`. Không tạo bảng trạng thái mới trong repo khi PO chưa yêu cầu.
  - Không ghi trạng thái hiện tại của code (số test, lệnh nào đã có) vào `AGENTS.md` hay các file quy tắc.
- **Không tự ghi** "APPROVED", "đã duyệt", "DONE", ✅ hay "đã nghiệm thu" khi chưa có bằng chứng tương ứng:
  - **Duyệt:** người duyệt (thường là PO) nói rõ, và nơi ghi nhận có ngày cùng người duyệt.
  - **Xong / ✅:** reviewer đã chạy lại các lệnh kiểm tra và kiểm phần thay đổi.
  - **Đạt AC:** có đúng loại bằng chứng mà spec mục 7 ghi cho AC đó (fixture hay unit test, integration test, hoặc dữ liệu thực địa; xem [code-rules](code-rules.md), mục 10), và reviewer đã kiểm. Báo cáo đánh giá thì gắn hash theo spec 5.5. Không thêm điều kiện ngoài spec.
- **Nội dung chờ duyệt** mang nhãn phiên bản, ví dụ `[v1.1]`, cho tới khi PO duyệt. Chỉ khi PO duyệt mới bỏ nhãn.
- Khi một quyết định đã duyệt, nguồn chuẩn chỉ giữ luật có hiệu lực, ngoại lệ và cách kiểm chứng. Các phương án không được chọn nằm trong biên bản lịch sử. Không để nhãn chờ của một OQ đã trả lời trong nội dung có hiệu lực.

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
3. **Sơ đồ bị ảnh hưởng:** spec mục 2, `docs/architecture_diagram.md`.
4. **Mục 12 của spec:** nếu code và spec lệch nhau thì thêm một dòng D-x.

**Kiểm tra trước khi mở PR:**
- liên kết nội bộ mở được;
- mọi ID được nhắc tới đều tồn tại;
- `git diff --check` sạch.

## 7. Cấu trúc để agent đọc và công cụ kiểm tra

**Điểm vào** là [AGENTS.md](../../AGENTS.md), mục 2–3. Agent đọc đúng các mục nguồn đã dẫn chiếu ở đó. Không cần nạp toàn bộ spec, sách môn học hay schema sinh tự động vào ngữ cảnh.

**Metadata đầu file.** Bắt buộc cho spec kiến trúc và bản sơ đồ kiến trúc. File lưu trữ dùng metadata để không bị hiểu là chỉ dẫn hiện hành. Những file còn lại giữ cấu trúc hiện có; không thêm bản sao trạng thái task vào metadata.

Metadata là YAML front matter giới hạn: mỗi dòng `key: value`, giá trị viết theo JSON (chuỗi có ngoặc kép, danh sách trên một dòng). Không dùng YAML nhiều dòng, alias hay giá trị ngày không có ngoặc kép. Công cụ kiểm chỉ cần thư viện chuẩn Python.

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| `doc_id` | string | Có | ID duy nhất, ổn định của tài liệu |
| `doc_type` | string | Có | `specification`, `plan`, `view`, `archive` |
| `status` | string | Có | `draft`, `proposed`, `approved`, `active`, `archived`; đây là trạng thái **tài liệu**, không phải trạng thái code |
| `authority_for` | array of string | Có | Những nội dung tài liệu làm nguồn chuẩn; `view` và `archive` luôn là `[]` |
| `version` | string | Khi `approved` | Phiên bản tài liệu, độc lập với phiên bản schema dữ liệu |
| `approved_by` | string | Khi `approved` | Vai trò đã duyệt, dựa trên bằng chứng có sẵn |
| `approved_on` | string | Khi `approved` | Ngày ISO `YYYY-MM-DD` |
| `approval_ref` | string | Khi `approved` | Đường dẫn tương đối tới biên bản phê duyệt |

`active` nghĩa là tài liệu đang dùng, không khẳng định PO đã duyệt. `archive` luôn đi với `archived`. Ngày duyệt và phiên bản chỉ đổi khi có quyết định mới, không đổi vì chỉnh cách trình bày. Các mục chưa quyết trong tài liệu đã duyệt phải ghi ID OQ còn mở rõ ràng; agent không được tự chọn đáp án.

**Mẫu hợp đồng dữ liệu:** bảng dùng cột `Trường`, `Kiểu/literal`, `Bắt buộc`, `Cho phép null`, `Đơn vị`, `Ràng buộc`. Ghi literal JSON chính xác; tên dịch chỉ dùng trong giải thích. Nếu bảng mô tả bản ghi đầu ra còn JSON Schema mô tả đầu vào model, ghi rõ khác biệt do mặc định/validator. Mọi thay đổi ngữ nghĩa vẫn theo code-rules mục 9.

**Kiểm tra tự động:** [check_docs.py](../../scripts/roadwatch/check_docs.py) kiểm tài liệu nhóm ngoài `docs/guide/`, cùng `AGENTS.md`, `README.md`, `ARCHITECTURE.md`:
- metadata, ID tài liệu duy nhất và đường dẫn bằng chứng duyệt;
- đích của liên kết Markdown nội tuyến tương đối (bỏ qua khối code);
- ID OQ, AC, ADR, F, I, D, KS viết đầy đủ, đối chiếu bảng nguồn chuẩn; ID `WP-…` không còn được đối chiếu vì bảng task đã gỡ;
- nhãn `chờ OQ-…` hoặc `ADR-…, chờ duyệt` trái với quyết định đã được ghi nhận. Bỏ qua lịch sử lưu trữ và bằng chứng checklist `[x]` có ngày.

**Giới hạn:** script không xác thực con người đã phê duyệt, không kiểm URL ngoài, anchor, đường dẫn chỉ viết trong backtick, ID viết tắt trong khoảng, ngữ nghĩa giữa các đoạn hay phụ thuộc ẩn trong câu văn; không render Mermaid. Reviewer vẫn phải kiểm những phần này. Lệnh chạy script, test và kiểm snapshot schema nằm ở [code-rules](code-rules.md), mục 8.
