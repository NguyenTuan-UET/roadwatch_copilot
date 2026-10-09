---
doc_id: "RW-REVIEW-1-1"
doc_type: "archive"
status: "archived"
authority_for: []
---

# Tóm tắt để review bộ tài liệu v1.1 (29/09/2026)

> **Đã hết hiệu lực: PO duyệt bộ tài liệu v1.1 ngày 29/09/2026.** Quyết định của PO ghi ở cột cuối của mục 5 và đã được chép vào các nguồn chuẩn. Từ nay chỉ đọc các nguồn chuẩn ([AGENTS.md](../../AGENTS.md), mục 2). File này giữ lại làm lịch sử.

## 1. Bối cảnh

- **Sản phẩm.** RoadWatch Copilot cảnh báo khoảng cách và nguy cơ va chạm cho tài xế mới trên cao tốc. Sản phẩm chạy offline trên CPU laptop và chỉ cảnh báo. Có ba bài toán:
  - **BT-A:** CV, đo khoảng cách và TTC.
  - **BT-B:** luật và máy trạng thái quyết định cảnh báo.
  - **BT-C:** cấu hình có HITL, log và kiểm chứng.
- **Spec.** v1.0 được PO duyệt ngày 28/09. Mọi thay đổi sau đó mang nhãn [v1.1] và **chưa được duyệt**, trừ ADR-12 (không dùng LLM) do PO chốt ngày 29/09.
- **Code.** Có code nền trên nhánh `feat/roadwatch-mvp` (8 commit). Code sản phẩm đang tạm dừng cho tới khi PO duyệt bộ tài liệu này. Chưa tiêu chí nghiệm thu nào đạt.
- **Lịch.** Hạn nộp MVP là cuối tuần 1; tuần 2–4 là phần mở rộng. Ngày nộp cụ thể chưa chốt (OQ-A7).

## 2. Thứ tự đọc đề xuất

1. **File này**: khoảng 5 phút.
2. **[AGENTS.md](../../AGENTS.md)**: phạm vi, ranh giới không được phá, nguồn chuẩn, quy trình làm một task.
3. **[docs/architecture_diagram.md](../architecture_diagram.md)**: năm sơ đồ (thành phần runtime, công cụ BT-C, một lần xử lý, HITL, ranh giới triển khai).
4. **[Spec](../specs/roadwatch-architecture.md)**: phần đầu và Quy ước, mục 2 (sơ đồ đã bổ sung), mục 10 (OQ), mục 11 (yêu cầu môn học), mục 12 (giả định I-x và điểm lệch D-x, gồm D-11…D-13 mới), và hai đề xuất chờ duyệt ở 3.7 (OQ-B12) và 3.10 (OQ-B13). Các mục khác là v1.0 đã duyệt, chỉ đọc khi cần.
5. **[docs/plan/README.md](README.md) → [so-do.md](so-do.md) → file phân việc của bạn** trong `phan-viec/`.
6. **[code-rules.md](../development/code-rules.md) và [docs-rules.md](../development/docs-rules.md)**.
7. **[README.md](../../README.md) và [ARCHITECTURE.md](../../ARCHITECTURE.md)**: kiểm nhanh rằng template môn học không còn được giới thiệu như thể là sản phẩm.

## 3. Điều gì đã đổi so với spec v1.0

| Nội dung | Ở đâu |
|---|---|
| Không dùng LLM, LangGraph, RAG, vector database. Bản đề xuất "Engineer Copilot" trước đó bị bỏ | Spec: ADR-12, NG12 |
| Giao diện theo giai đoạn: tuần 1 chỉ CLI và âm thanh; tuần 2–4 có web UI cục bộ bằng FastAPI | Spec: ADR-13, mục 11.5 |
| Vai trò R-A…R-D; người phụ trách thành phần chịu trách nhiệm phương pháp; owner cụ thể do plan quyết | Spec: Quy ước |
| Sơ đồ mục 2 bổ sung các giao tiếp đã có trong văn bản nhưng hình còn thiếu: nhật ký đầu vào, tick, `SystemEvent`, nhãn, cấu hình đầu vào của `rerun-B`. Hành vi không đổi | Spec mục 2 |
| Đối chiếu 10 deliverables và 5 tiêu chí của môn học | Spec mục 11 |
| Giả định code tự chọn (I-1…I-15) và điểm lệch (D-1…D-13). Ba điểm mới: D-11 chưa chặn split `test_*` trong HITL; D-12 spec thiếu `reports/`, `roles.json`; D-13 runtime import cả module `configstore` | Spec mục 12 |
| Open Questions: đánh dấu OQ-B1 đã trả lời; bỏ các câu hỏi về Copilot; thêm OQ-A11, OQ-E1, OQ-E2 | Spec mục 10 |
| Sơ đồ kiến trúc viết lại: thành phần theo thread và hàng đợi, công cụ BT-C, trình tự một lần xử lý, trình tự HITL có các nhánh bị từ chối, ranh giới triển khai | `docs/architecture_diagram.md` |
| `ARCHITECTURE.md` thành trang lối vào; `README.md` giới thiệu RoadWatch và tách rõ yêu cầu đã chốt, đề xuất chưa duyệt, code thực tế | Gốc repo |
| AGENTS.md viết lại ngắn gọn, không chứa trạng thái dễ lỗi thời. Thêm quy tắc code và quy tắc tài liệu | `AGENTS.md`, `docs/development/` |
| Plan: 49 task, mỗi task có owner, reviewer, phụ thuộc, đầu ra, điều kiện xong, cách kiểm chứng. Thêm sơ đồ phối hợp, sơ đồ phụ thuộc và đường găng, sơ đồ ngắn trong từng file phân việc | `docs/plan/` |
| Sửa phụ thuộc task: WP-D12, WP-A6, WP-P8 cần bộ chuyển đổi GPS; WP-A6 cần clip; WP-D6 cần nhãn; WP-D2 và WP-D3 không còn cùng làm session manifest | Plan mục 4 |
| Theo dõi tiến độ. Mỗi task có checklist ba nhóm (bàn giao có đường dẫn, kiểm thử và kiểm chứng, review và nghiệm thu), cập nhật ngay khi xong từng mục, kèm bằng chứng. Plan giữ trạng thái tổng và một dòng liên kết cho mỗi task đang mở. Code và tiến độ đi trong cùng commit. `WORKLOG.md` chỉ là nhật ký | Plan mục 0 và 4.3; các file `phan-viec`; `AGENTS.md` mục 4; code-rules mục 11 |
| Guardrail Khẩn cấp khi đợt tiếp diễn: bốn trường hợp (bắt đầu đợt, duy trì, phục hồi từ `HOLD_E`, phát lại), bảy kịch bản S1–S7, ba phương án. **Chờ PO chọn** | Spec 3.5, 3.7, 6.2, 10.1 (OQ-B12); WP-B9 |
| Luật fail-safe viết lại đúng bảng 3.4: hai năng lực độc lập; tốc độ `lost` không tắt `cap_ttc`; tốc độ `stale` không đổi năng lực, không sinh câu báo; guardrail đủ ba điều kiện, kể cả `cap_ttc = on` | `AGENTS.md` mục 1; code-rules mục 5 |
| Chạy thử cấu hình đề xuất bằng `--proposed` cho replay và live, không kích hoạt, gắn cờ, không làm bằng chứng nghiệm thu. **Chờ PO duyệt** | Spec 3.10, 4.4, 10.1 (OQ-B13), D-8; sơ đồ HITL; WP-C2 |
| Giữ kín `test_small` và `test_final`: người tinh chỉnh A, B chỉ xem phiên `dev`; Cương kiểm phiên giữ kín bằng script chỉ in metadata; Linh chuyển đổi GPS của các phiên này | WP-D3, WP-D10, WP-A4, WP-A12; `so-do.md` mục 1 |
| WP-P7 phụ thuộc đúng các task cho ra bằng chứng AC-M (WP-D6, WP-P8, WP-P4, WP-B9, WP-A3, WP-A6, WP-C2) thay cho "mọi task tuần 1" | Plan mục 4.1; `so-do.md` mục 2; WP-P7 |
| Nhãn `test_final`: gán mù, kiểm bằng `EventLabel`, đóng băng bằng hash; WP-D11 chỉ chấm trên bộ nhãn đã đóng băng | WP-D10, WP-D11 |
| Luật bằng chứng nghiệm thu: mỗi AC dùng đúng loại bằng chứng mà spec mục 7 ghi (fixture hay unit test, integration test, dữ liệu thực địa), không thêm điều kiện | code-rules mục 10; docs-rules mục 4; plan mục 0 |

Các file requirements không thay đổi.

## 4. Người review nên kiểm

1. **Phân công và tải.** Phân công ở plan mục 1 có đúng ý PO không; tải ở plan mục 5 có thực tế không.
2. **Đường găng.** Buổi quay (WP-D2, WP-D3) có kịp N2–N3 không.
3. **Task của bạn.** "Xong khi" và "Kiểm chứng" có đo được không, có đủ để người khác xác nhận không.
4. **Sơ đồ so với văn bản.** Sơ đồ có thể hiện đúng spec và đúng bảng task không; có giao tiếp quan trọng nào bị bỏ sót không.
5. **Không bịa.** Không tài liệu nào ghi một số đo, ngưỡng, hạn nộp hay phê duyệt như thể đã có, khi thực tế chưa có.

## 5. Quyết định của PO (29/09/2026)

| # | Vấn đề | Đề xuất | Ảnh hưởng | Task bị chặn | PO chốt 29/09 |
|---|---|---|---|---|---|
| 1 | Duyệt bộ tài liệu v1.1 | Duyệt; sửa trực tiếp nếu cần | Mở lại việc viết code | Tất cả (WP-P1) | Duyệt, sau khi các quyết định dưới đây được ghi vào tài liệu |
| 2 | Code RoadWatch chỉ nằm trên nhánh cục bộ `feat/roadwatch-mvp`. `main` vẫn là template. CI chỉ chạy khi push lên `main`, `develop` hoặc khi mở PR vào `main` | Push nhánh lên remote, rồi chọn nhánh tích hợp (ví dụ PR vào `main` sau khi có WP-C1) | Ba thành viên chưa đọc được code; mất máy là mất code | WP-A0, WP-B0, WP-C1 | Theo đề xuất. Kiểm lại: code đã có trên `origin/cuongnh` từ 29/09 (merge f25f575), nên vế "chưa đọc được code" không còn đúng. Còn lại: PR vào `main` sau WP-C1 |
| 3 | `.github/CODEOWNERS` của template gán mọi file cho nhóm maintainer của môn học | Kiểm tra cài đặt bảo vệ nhánh trên GitHub. Nếu PR phải chờ họ duyệt thì hỏi BTC. Không tự sửa file này, vì chính nó thuộc quyền của họ | Có thể không merge được PR nào | Mọi PR; WP-C1 (sửa `.github/workflows`) | PO đã kiểm: nhóm tự merge PR vào `main` được. Không sửa CODEOWNERS |
| 4 | Code mẫu của template (`src/agents/`…) và `requirements.txt` của template làm CI và `pytest tests/` phức tạp hơn | Giữ nguyên trong tuần 1. WP-C1 cho CI cài đủ dependency, hoặc tách job riêng cho RoadWatch. Quyết giữ hay bỏ sau khi nộp MVP | Deliverable 1 "Source code" rõ ràng hơn nếu bỏ | WP-C1 | Theo đề xuất |
| 5 | Máy demo và danh sách người duyệt (OQ-B6, OQ-B7) | Cả bốn người là người duyệt, luôn khác người đề xuất; máy demo do PO chọn | Mọi số đo live phải lấy trên một máy cố định | WP-P2 → WP-A1, WP-P3, WP-C2, WP-A6, WP-P8 | Cả bốn người là người duyệt; máy demo là laptop của Khánh (PO đổi 30/09) |
| 6 | Duyệt cấu hình đầu tiên khi CLI chưa có (OQ-B3) | Gọi thẳng các hàm `configstore` bằng một đoạn script ngắn; vẫn giữ luật người đề xuất khác người duyệt | Runtime chạy được từ N2 | WP-P3 | Theo đề xuất. **PO đổi 30/09:** bỏ script; dùng trực tiếp `roadwatch hitl` trên máy demo (OQ-B3 đóng) |
| 7 | 22/30 file Python của RoadWatch chưa theo `ruff format` | Định dạng toàn bộ trong một commit riêng trước khi các nhánh task bắt đầu; hoặc quyết định không dùng formatter | Một diff lớn duy nhất; làm muộn thì dễ xung đột | Không chặn, nhưng càng sớm càng tốt | Theo đề xuất: format trong một commit riêng, làm ngay |
| 8 | Giữ, sửa hay bỏ từng dòng I-x, D-x (OQ-A10) | I-13 (`PENDING` không có vùng trễ): giữ đúng spec, đo trên `dev` ở WP-B3 rồi quyết. D-1 (`winsound`): chấp nhận cho MVP. D-11: làm trong WP-C2. D-12: sửa spec. D-13: chấp nhận cho MVP, kèm luật "chỉ gọi hàm đọc" | Hành vi của B; nội dung spec mục 3.10 và mục 4 | WP-B0, WP-B3, WP-C2, WP-P4 | Theo đề xuất, cả gói |
| 9 | Thứ tự cắt khi trễ (plan mục 5) | Như trong plan: chỉ dùng các lối lùi mà spec đã cho phép | Một số AC ghi "chưa đạt" hoặc "chưa kết luận" thay vì đạt | Cần chốt trước N5 | Theo đề xuất |
| 10 | Live URL (OQ-E1) | Hỏi mentor ở WP-P6. Nếu bắt buộc phải có URL: deploy web UI kỹ sư chỉ đọc, dữ liệu mẫu, không có runtime | Điểm deliverable 5; rủi ro mâu thuẫn với yêu cầu offline | WP-C9 (tuần 2–4) | Theo đề xuất; Cương hỏi mentor ở WP-P6 |
| 11 | Công nghệ phía giao diện của web UI (OQ-E2) | HTML render từ FastAPI: một process, chạy offline, không cần build Node | Tiêu chí UX/UI; có thêm một lần deploy hay không | WP-C10, WP-C6 (tuần 2) | Theo đề xuất |
| 12 | Hỏi mentor: OQ-A11 (không dùng LLM), OQ-A1 (mục tiêu 50%), OQ-A2 (sai số theo dải) | Hỏi trong WP-P6, trước N3 | Cách chấm "AI logs"; tiêu chí đạt của AC-M5, AC-M6 | WP-D6 (phần kết luận) | Theo đề xuất; hỏi trước N2 theo lịch mới |
| 13 | Ngày nộp MVP thật (OQ-A7) | PO cung cấp | Quy đổi N0…N7 ra ngày thật | Lập lịch | 04/10/2026. Lịch nén từ N0…N7 xuống N0…N5 (plan mục 0) |
| 14 | File Word (OQ-A6); ghi bù AI log (việc tồn) | PO xử lý khi có thời gian | Deliverable nộp bài | Không chặn tuần 1 | File Word đã sinh lại từ ba file requirements (OQ-A6). AI log ghi bù: PO tự làm |
| 15 | Chính tả tên: plan dùng "Cương" theo tin nhắn của PO; bản trước dùng "Cường" | PO xác nhận | Chỉ phải sửa trong `docs/plan/` | Không | Cương |
| 16 | File cấu hình đề xuất (đầu vào của `hitl propose`) chưa có nơi được commit, vì `configs/` là kho của máy demo và bị `.gitignore` | Lưu file đề xuất ở `config/proposals/`, có commit, để reviewer xem được diff | Checklist đang dùng đường dẫn này và ghi "chờ quyết định 16" | WP-B1, WP-P3, WP-A2, WP-A4, WP-B3 | Theo đề xuất |
| 17 | `eval/test_runs.jsonl` nằm trong `.gitignore`, trong khi đây là bằng chứng rằng `test_small` chỉ chạy đúng một lần | Bỏ file này khỏi `.gitignore` và commit nó cùng báo cáo | Nếu không commit, reviewer chỉ kiểm được trên máy đã chạy | WP-C4, WP-D6, WP-D11 | Theo đề xuất |
| 18 | Guardrail Khẩn cấp khi đợt tiếp diễn (OQ-B12, spec 3.7) | Phương án (b): phát lại ngay khi đủ ba điều kiện mà chưa lệnh Khẩn cấp nào của đợt `started` (lệnh gần nhất bị `cancelled` hoặc `expired`); không nhắc theo chu kỳ | (a) giữ nguyên thì S4, S7 im lặng cả đợt và phải ghi thành giới hạn; (b) sửa `episodes.py`, `stage.py` | WP-B9 (S4, S7) | Phương án (b) |
| 19 | Chạy thử cấu hình đề xuất (OQ-B13, spec 3.10) | Như đề xuất ở 3.10: `--proposed` cho replay và live, ai trong danh sách HITL cũng chạy được, không ghi kho cấu hình, gắn cờ `proposed_config` và `proposal_id`, từ chối `test_*`, không làm bằng chứng nghiệm thu | Không có thì đường `[A, live]` không làm được báo cáo tác động; `RunManifest` thêm hai trường (MINOR) | WP-C2 (`--proposed`) | Theo đề xuất |

## 6. Kiểm tra đã chạy và giới hạn

| Kiểm tra | Kết quả |
|---|---|
| Thời điểm | Mọi kết quả dưới đây chạy lại ngày 29/09, **sau** khi sửa 7 phát hiện review. Kết quả của các vòng trước không được dùng làm bằng chứng |
| Render Mermaid: 12 sơ đồ (1 ở spec, 5 ở `architecture_diagram.md`, 2 ở `so-do.md`, 4 ở file phân việc) | Cả 12 render được. Dùng Mermaid 11.16.1 (bản đi kèm extension VS Code "Mermaid Chart"), trong Chromium headless, mạng bị chặn. Hai mẫu đối chứng, một đúng và một sai, cho kết quả như mong đợi. Đã xem ảnh chụp của sơ đồ HITL (khối chạy thử) và sơ đồ phụ thuộc (mũi tên vào WP-P7) |
| Các luật cú pháp Mermaid ghi ở docs-rules | Đã thử từng luật ở vòng trước: ID `end` làm hỏng sơ đồ; nhãn có `(` mà không có ngoặc kép làm hỏng sơ đồ; `&lt;` làm hỏng sequence diagram; `;` làm hỏng tin nhắn; `#` làm mất chữ. Vòng này script vẫn quét các luật này trên mọi sơ đồ |
| Script kiểm tài liệu (chạy tạm, không nằm trong repo) | Không có lỗi. Đã kiểm: 113 liên kết; cả 49 task đều có checklist đủ ba nhóm; mục bàn giao nào cũng có đường dẫn; mục `[x]` nào cũng có bằng chứng kèm ngày; TT khớp checklist; task khác ⬜ nào cũng có dòng ở plan mục 4.3 trỏ đúng file của owner; mọi ID WP, OQ, AC, I, D được nhắc tới đều tồn tại (kể cả OQ-B12, OQ-B13); reviewer khác owner; reviewer trong sơ đồ ngắn khớp bảng (kể cả WP-D3 có hai reviewer); 59 phụ thuộc tuần 1 trong bảng khớp đúng sơ đồ, **không còn ngoại lệ cho WP-P7**; không task nào ghi phụ thuộc kiểu "mọi task"; mốc ngày không đi lùi; đường găng khớp. **Mới:** toàn bộ 74 phụ thuộc tuần 1–4 không có chu trình, không task nào tự phụ thuộc, không task tuần 1 nào chờ task tuần 2–4. Đã cài 7 lỗi giả vào bản sao (chu trình, phụ thuộc "mọi task", thiếu mũi tên, task tuần 1 chờ tuần 2–4, tự phụ thuộc, sơ đồ ngắn thiếu reviewer, OQ chưa định nghĩa): script bắt đủ 7 |
| `git diff --check`, cùng quét khoảng trắng thừa và tab trong các file chưa track | Sạch |
| `python -m pytest tests/roadwatch --confcutdir=tests/roadwatch --ignore=tests/roadwatch/test_cli.py` | 104 passed. Vòng này không sửa code |
| Cùng lệnh, không có `--ignore` | 1 lỗi khi thu thập `test_cli.py`: test viết trước cho WP-C2, chưa commit, đỏ có chủ đích |
| `ruff check src/roadwatch tests/roadwatch` | Chỉ một lỗi I001 ở `test_cli.py`, cùng nguyên nhân; bỏ file đó ra thì sạch |

**Giới hạn kiểm chứng:**
- **Chưa xem trên GitHub.** GitHub có thể dùng phiên bản Mermaid khác; sơ đồ dày (`so-do.md`) đọc được nhưng khá chật.
- **Chưa có dữ liệu thật.** Mọi kiểm chứng trên dữ liệu thật vẫn còn nằm ở phía trước.
- **Lệnh cài đặt trong README chưa chạy lại** trên môi trường sạch; máy hiện tại đã có sẵn các gói.
- **Cài đặt bảo vệ nhánh trên GitHub:** PO kiểm ngày 29/09, nhóm tự merge được (quyết định 3).
- **Nhánh của thành viên khác mới xem qua ref cục bộ, chưa `git fetch`.** Theo các ref này, chưa nhánh nào có việc của RoadWatch.

## 7. Lưu trữ các phương án OQ-B12

Phần dưới giữ các phương án trước khi chốt. **Không dùng làm chỉ dẫn triển khai.** PO đã chọn (b) ngày 29/09; luật có hiệu lực và S1–S7 nằm ở spec 3.7.

- **(a) Giữ như hiện tại.** Sửa câu đầu mục này thành "phát ngay ở khung bắt đầu đợt". S4 và S7 ghi thành giới hạn đã biết (AC-M11). Không đổi code.
- **(b) Đề xuất ở trên.** Sửa `decision/episodes.py` và `decision/stage.py`; thêm vào test thuộc tính: ở mọi khung đủ ba điều kiện, hoặc B phát ở khung đó, hoặc đợt đã có lệnh Khẩn cấp `started` hay đang chờ.
- **(c) Như (b), cộng nhắc lại theo chu kỳ** khi đợt kéo dài. Cần thêm một tham số có biên cứng, và có rủi ro nói nhiều (P6). Không đề xuất cho MVP.
