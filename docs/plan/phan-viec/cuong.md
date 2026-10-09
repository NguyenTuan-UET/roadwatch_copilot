# Phần việc của Cương: PO/Lead + R-C (BT-C, tích hợp)

Bạn giữ kiến trúc, `contracts`, BT-C (cấu hình và HITL, runtime, log, `rerun-B`, CLI) và việc tích hợp. Bạn cũng chịu trách nhiệm phương pháp và tính đúng của phần **tái lập** trong báo cáo.

- **Owner, reviewer, phụ thuộc, hạn, trạng thái tổng:** [README](../README.md), mục 4. Nếu sơ đồ dưới đây khác bảng đó thì bảng thắng.
- **Checklist dưới mỗi task:** cập nhật ngay khi xong từng mục, theo luật ở [README](../README.md), mục 0.
- **Tài liệu cần đọc:** [AGENTS.md](../../../AGENTS.md), mục 3, các dòng "Runtime", "Cấu hình, HITL, CLI", "Hợp đồng dữ liệu" và "Tài liệu, sơ đồ".

```mermaid
flowchart LR
  IN["Nhận vào<br/>tham số B (WP-B1) · model + hash (WP-A1)<br/>đề xuất cấu hình A, B (WP-A2, WP-A4, WP-B3)<br/>fixture F1–F16 (WP-B9) · WAV (WP-B2)<br/>clip dev + manifest (WP-D3) · CSV GPS (WP-A12)<br/>báo cáo đánh giá (WP-D6)"]
  DO["Làm (tuần 1)<br/>WP-P1…P4, WP-P6…P8<br/>WP-C2, WP-C3, WP-C11 · WP-P5"]
  CHK["Kiểm chứng<br/>vòng HITL bằng CLI (AC-M9)<br/>chạy lại được lần chạy (AC-M1, M10)<br/>fixture sai bị từ chối"]
  REV["Reviewer<br/>Tuấn: P2, C2, P8<br/>Khánh: P3, C3, P6, P5 (tuần 2–4)<br/>Khánh + Tuấn: P4, C11 (đề xuất)<br/>Linh: P5 (tuần 1), P7 · cả nhóm: P1"]
  OUT["Bàn giao<br/>máy demo, người duyệt (WP-P2)<br/>cấu hình active (WP-P3) · CLI (WP-C2)<br/>contracts v1.0 (WP-P4)<br/>giới hạn + demo MVP (WP-P7)"]
  IN --> DO --> CHK --> REV --> OUT
```

## Thuật ngữ riêng

| Từ | Nghĩa |
|---|---|
| `configstore` | Kho cấu hình: phiên bản bất biến, file phê duyệt, con trỏ `active.json`. SQLite chỉ dùng cho HITL (spec 3.10) |
| Báo cáo tác động | Số liệu trước và sau khi đổi cấu hình. Chạy theo `affects` của mục bị đổi: `[B]` thì `rerun-B`; `[A]` thì replay; `[A, live]` thì replay cộng một lần live |
| `--proposed` | Chạy replay, hoặc live cho đường `[A, live]`, với cấu hình đề xuất chưa duyệt, chỉ để làm báo cáo tác động; không kích hoạt gì. Kết quả bị gắn cờ và không dùng để nghiệm thu (D-8; spec 3.10, OQ-B13 được PO duyệt 29/09) |
| Fixture | File JSONL mẫu, gồm loại hợp lệ và loại sai hợp đồng (spec 4.6) |
| Dấu vân tay máy | Thông tin máy demo ghi trong `run_manifest`, dùng để ràng buộc các kết quả đo live |

## Tuần 1

### WP-P1 · Duyệt bộ tài liệu
- **Xong khi:** không còn mục [v1.1] nào chưa quyết; ba thành viên đã đọc phần của mình; mâu thuẫn nào tìm thấy thì đã được sửa hoặc ghi thành OQ.
- **Kiểm chứng:** mỗi reviewer ghi một dòng xác nhận vào `WORKLOG.md`.
- **Checklist:**
  - Bàn giao
    - [x] Các phần [v1.1] trong `docs/specs/roadwatch-architecture.md` → 29/09/2026: đã soạn; sửa lại theo 7 phát hiện review (3.5, 3.7 với OQ-B12; 3.10, 4.4 với OQ-B13; 6.2; 10.1; D-8), chờ PO duyệt; commit 8943c1c
    - [x] `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/architecture_diagram.md` → 29/09/2026: đã soạn; sửa lại AGENTS mục 1 (guardrail đủ ba điều kiện, fail-safe theo từng năng lực) và sơ đồ HITL (khối chạy thử, chờ OQ-B13); commit 8943c1c
    - [x] `docs/development/code-rules.md`, `docs/development/docs-rules.md` → 29/09/2026: đã soạn; sửa lại code-rules mục 5 (fail-safe), mục 10 và docs-rules mục 4 (mỗi AC dùng đúng loại bằng chứng của spec mục 7); commit 8943c1c
    - [x] `docs/plan/` (README, `so-do.md`, `review-v1.1.md`, bốn file phân việc) → 29/09/2026: đã soạn; sửa lại WP-D3, WP-D10, WP-D11, WP-P7, WP-C2, WP-B9, WP-A4, WP-A12, hai sơ đồ ở `so-do.md`, quyết định 18 và 19; commit 8943c1c
    - [x] Quyết định cho từng I-x, D-x ghi thẳng vào spec mục 12 (OQ-A10) → 29/09/2026: PO chốt theo review-v1.1 mục 5, quyết định 8; đã ghi vào spec mục 12, D-12 sửa vào 3.10; commit 4ed1285
    - [x] Câu trả lời OQ-B12 (spec 3.7) và OQ-B13 (spec 3.10), ghi ở spec mục 10.1 → 29/09/2026: OQ-B12 chọn (b), OQ-B13 duyệt như 3.10; đã ghi ở 3.7, 3.10, 10.1; commit 4ed1285
    - [x] 01/10/2026: bổ sung quy tắc đồng bộ GitHub đầu phiên và chỉ push nhánh task trong `AGENTS.md`, code-rules mục 11 theo yêu cầu người dùng. Đã fetch và đọc diff `origin/main` tại `b6e560a`; chưa tích hợp vì working tree có việc dở. Còn thiếu: review và đưa thay đổi vào PR sau đồng bộ; tiếp theo: xử lý việc dở an toàn. Chưa commit.
    - [ ] Một commit riêng cho bộ tài liệu, không gộp với `tests/roadwatch/test_cli.py` → tiếp theo: commit sau khi PO duyệt
    - [x] Chuẩn hóa trạng thái spec/plan, luật Khẩn cấp đang có hiệu lực và literal hợp đồng ở `docs/specs/roadwatch-architecture.md` → 29/09/2026: sửa theo quyết định đã ghi nhận; không đổi runtime; trong commit chuẩn hóa WP-P1
    - [x] `scripts/roadwatch/check_docs.py`, `scripts/roadwatch/export_schemas.py`, `docs/specs/schemas/contracts.schema.json`, `tests/roadwatch/test_documentation.py` → 29/09/2026: kiểm metadata, link, ID, task và phụ thuộc; snapshot 16 model gốc từ Pydantic; không đổi code runtime; trong commit chuẩn hóa WP-P1
  - Kiểm thử và kiểm chứng
    - [x] Kiểm lại tài liệu sau chuẩn hóa cho agent → 29/09/2026: các lệnh kiểm tài liệu, snapshot schema và unittest ở code-rules mục 8 đều đạt; 2 test công cụ, gồm 10 ca cài lỗi trên bản sao. `uvx ruff check scripts/roadwatch tests/roadwatch/test_documentation.py` và `git diff --check` sạch. Toàn bộ RoadWatch: 106 test đạt trong môi trường tạm có pytest; Mermaid không đổi, chưa render lại trong phiên này. Bằng chứng đi cùng commit chuẩn hóa WP-P1.
  - Review và nghiệm thu
    - [ ] 01/10/2026, review PR #3 (`fe1ec62`): sửa check_docs đang coi ID ở bảng tiến độ 4.3 là định nghĩa task; một ID không tồn tại (tiền tố `WP-P`, số 999) đặt ở bảng đó vẫn qua kiểm tra. Tiếp theo: chỉ lấy định nghĩa WP từ danh mục task và danh sách ID đã bỏ, thêm test hồi quy. Bằng chứng các kiểm tra đã chạy ở WORKLOG ngày 01/10; không thay xác nhận của ba reviewer.
    - [ ] Ba reviewer đọc phần của mình và ghi xác nhận vào `WORKLOG.md`
    - [x] PO duyệt, rồi bỏ nhãn [v1.1] ở các mục được duyệt → 29/09/2026: PO duyệt trong phiên làm việc với AI, ghi ở review-v1.1 mục 5; đã bỏ nhãn trong spec; commit 4ed1285

### WP-P2 · Người duyệt HITL và máy demo
- **Xong khi:** WP-C2 và WP-P3 dùng được danh sách người duyệt; WP-A1, WP-A6, WP-P8 đo trên cùng một máy.
- **Kiểm chứng:** reviewer xác nhận mọi thay đổi cấu hình luôn có ít nhất một người duyệt khác người đề xuất.
- **Checklist:**
  - Bàn giao
    - [x] Câu trả lời OQ-B6 (máy demo) và OQ-B7 (người đề xuất, người duyệt), ghi trong `docs/specs/roadwatch-architecture.md`, mục 10.1 → 30/09/2026: laptop của Khánh (PO đổi từ laptop của Cương); cả bốn người là người duyệt; commit 4ed1285
  - Kiểm thử và kiểm chứng
    - [ ] Danh sách đủ để tạo `roles.json` bằng `hitl init` trên máy demo (`configs/` không commit)
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-P3 · Cấu hình khởi tạo
- **Xong khi:** trên máy demo, runtime khởi động không gặp lỗi F23, và `run_manifest` có `approval_id`.
- **Kiểm chứng:** người duyệt chạy một replay ngắn và thấy `approval_id` trong manifest; kiểm rằng mọi giá trị không phải số đo đều nằm trong `provisional_keys`.
- **Checklist:**
  - Bàn giao
    - [ ] File cấu hình v0 ghép phần B (WP-B1) và phần A (WP-A1), lưu ở `config/proposals/v0.yaml` → 02/10/2026: file đã có đủ mọi mục của `rw.config`. Phần B giữ nguyên của WP-B1; mục `audio` ghi độ dài và hash đo từ bộ WAV nháp (WP-B2); `runtime` lấy giá trị của cấu hình test và nằm trong `provisional_keys`; `mount.d_cam_bumper_m` = 1,5 m là giả định của requirements file 3. Giá trị theo máy là `null` kèm nhãn `TODO(machine)`; phần A gồm `mount`, `calibration`, `model` (06/10/2026), nên `hitl propose` từ chối file (test `test_the_config_template_is_refused_until_its_todo_values_are_filled`). Cấu hình đầy đủ chỉ để chạy fixture nằm riêng ở `tests/roadwatch/fixtures/handoff/test-config.yaml`, mang nhãn `ASSUMPTION(test-only)`. Còn thiếu: ngưỡng của A sau WP-A4, số đo KS-3. Tiếp theo: Tuấn và người giữ máy demo điền, rồi đề xuất qua HITL. Commit `f30174b`, `6536665`
    - [ ] Phê duyệt đầu tiên trên máy demo: `configs/versions/`, `configs/approvals/`, `configs/active.json` (không commit; ghi `approval_id` làm bằng chứng)
    - [x] ~~`scripts/roadwatch/hitl_bootstrap.py`~~ → **bỏ** theo quyết định PO 30/09/2026 (OQ-B3 đóng): cấu hình v0 khởi tạo bằng `python -m src.roadwatch.cli hitl` (`init` → `propose` → `report` → `approve` bởi người khác → `activate`) trên máy demo. Bằng chứng CLI làm được: `test_first_config_goes_through_the_cli_without_a_bootstrap_script` trong `tests/roadwatch/test_cli_guards.py`
  - Kiểm thử và kiểm chứng
    - [ ] Replay ngắn trên máy demo chạy được, `run_manifest.json` có `approval_id` → 02/10/2026: mới chạy trên máy phát triển, với kho tạm, vai trò thử và cấu hình test (không phải v0): `run --measurements` trên phiên mẫu cho manifest có `approval_id`, không có cờ `unapproved_code`. Còn thiếu: máy demo và cấu hình v0 đã điền
  - Review và nghiệm thu
    - [ ] Người duyệt (khác người đề xuất) kiểm theo mục "Kiểm chứng"

### WP-C2 · CLI
- **Xong khi:** `tests/roadwatch/test_cli.py` xanh mà không sửa kỳ vọng của test, và chạy trọn được một vòng HITL bằng CLI.
- **Kiểm chứng:** reviewer chạy tay kịch bản AC-M9 (spec 7.1) trên máy demo và ghi biên bản vào mô tả PR. Chạy thêm một lần `--proposed` (OQ-B13) và xác nhận `active.json`, `approvals/` không đổi.
- **Code có sẵn:** lõi T2 (README mục 3).
- **Checklist:**
  - Bàn giao
    - [x] `tests/roadwatch/test_cli.py` viết trước: vòng HITL qua CLI, xuất JSON Schema → 28/09/2026: 2 test, đỏ có chủ đích vì chưa có `cli.py`. 30/09/2026: **xanh 2/2, không sửa test** (`python -m pytest tests/roadwatch/test_cli.py -v --confcutdir=tests/roadwatch` → 2 passed)
    - [x] `src/roadwatch/cli.py`: `run`, `rerun-b`, `eval`, `perf`, `schema`, `hitl` (`init`, `propose`, `report`, `approve`, `activate`, `rollback`, `recover`, `status`) → 30/09/2026: đủ lệnh, chạy bằng `python -m src.roadwatch.cli`; thêm `check-run` và `compare` cho WP-P8. Thêm hàm đọc `configstore.proposal_config` (không giữ khoá). `hitl report` chọn đường theo `affects`: `[B]` chạy `rerun-B` trên lần chạy dev có cùng cấu hình A; `[A]`, `[A, live]` chỉ nhận lần chạy `--proposed` của đúng đề xuất. `eval` bắt buộc nhập `--lead-max-s`, `--max-late-s`, `--tau`, không có mặc định (OQ-A3). Chưa commit
    - [x] `--proposed <proposal_id>` cho replay và live (D-8), trong `src/roadwatch/runtime.py`, `src/roadwatch/cli.py`; cờ `proposed_config` và `proposal_id` trong `run_manifest` (`src/roadwatch/contracts/`); `hitl report` chỉ nhận lần chạy thử đúng đề xuất và đúng sha cấu hình (spec 3.10, OQ-B13) → 30/09/2026: runtime chỉ gọi `load_version`, không đọc SQLite, không ghi kho; từ chối split `test_*`. `RunManifest`: thêm `proposal_id` (MINOR, mặc định `null`), `approval_id` được là `null` với lần chạy thử; `contracts_version` 0.1.0 → 0.2.0; spec 4.4 đã sửa theo. Chưa commit
    - [x] `hitl report` từ chối dữ liệu thuộc split `test_*` (D-11), trong `src/roadwatch/cli.py` → 30/09/2026: có `_refuse_test_split`. Chưa có model `DatasetManifest`, nên hàm tìm mọi `split: test_*` trong file; đổi sang dùng model khi WP-D4 định nghĩa manifest. Chưa commit
    - [x] `run_stats.json` trong thư mục lần chạy, do `src/roadwatch/runtime.py` ghi → 30/09/2026: PO chốt nội dung (mẫu JSON, ghi vào spec 4.4); `runtime.run_stats` đếm lại từ các luồng sau khi chạy xong, không đụng đường nóng; trường audio là `null` ở replay. `check-run` coi file này là bắt buộc với replay và live. Test `test_run_stats_summarise_what_the_run_logged` (replay và live), đỏ trước khi có code. 02/10/2026, mở lại và kiểm chứng lại vì đổi hai chỗ: `live` với sink giả lập ghi `null` ở `played_successfully` và `dropped_stale` (PO yêu cầu không ghi nhận âm thanh giả lập là đã phát); `frames.read` là `null` khi lần chạy không có log khung. Kỳ vọng của test đổi theo, cả bộ 236 passed; spec 4.4 đã sửa
    - [x] Tách phần đọc cấu hình khỏi `configstore` (D-13; PO chấp nhận điểm lệch này cho MVP ngày 29/09, kèm "tách nếu còn thời gian") → 01/10/2026: `src/roadwatch/configread.py` giữ `load_active`, `load_version`, `load_approval`, `read_pointer`, `ConfigError`; `configstore.py` chỉ còn lệnh HITL và xuất lại các hàm đọc, nên `cs.load_active` và `cs.ConfigError` ở CLI và test không đổi. `runtime.py` import `configread`; `live.py` không đổi. Test viết trước, đỏ rồi xanh: `test_the_product_path_loads_neither_sqlite_nor_any_tool_of_c` trong `tests/roadwatch/test_runtime.py` nạp runtime trong một tiến trình mới và kiểm rằng `sqlite3`, `configstore`, `cli`, `rerun`, `evaluate` không bị nạp. Đã cập nhật code-rules mục 1, 3, 9 và dòng D-13 của spec. Câu "Code hiện vẫn import module `configstore` (D-13)" ở `docs/architecture_diagram.md` đã sửa ngày 01/10, sau khi đồng bộ `main` (nhánh `feat/wp-p4-contracts-v1`). Commit `85c58ca`
    - [x] `run --measurements` và `--audio speaker|simulated` (02/10/2026, cho bàn giao B+C, WP-P8) → `src/roadwatch/cli.py`, `runtime.py`, `live.py`. `check-run` không đòi `frames.jsonl`, `perf.jsonl` ở lần chạy mang cờ `measurements_input`; `perf` bỏ qua lần chạy đó; lỗi ở file đầu vào in `error: …` với mã thoát 2 thay cho traceback. Test: `tests/roadwatch/test_handoff.py` (6 test). Chưa review. nhánh `feat/wp-p4-contracts-v1`
  - Kiểm thử và kiểm chứng
    - [x] Test cho D-11, viết trước code → 30/09/2026: `test_report_refuses_a_test_split` trong `tests/roadwatch/test_cli_guards.py`, không đặt trong `test_cli.py` vì người dùng yêu cầu không sửa file đó; đỏ trước khi có code, sau đó xanh. Chưa commit
    - [x] Test cho D-8 theo spec 3.10, viết trước code, trên kho tạm: lần chạy thử (replay và live giả) không đổi `active.json`, không tạo phê duyệt; manifest có cờ và `proposal_id`, `approval_id` là `null`; từ chối split `test_*`; `hitl report` từ chối lần chạy thử của đề xuất khác hoặc sha khác; chạy thường với cấu hình chưa duyệt vẫn bị từ chối (F23) → 30/09/2026: 3 test trong `tests/roadwatch/test_runtime.py` và `test_report_on_a_change_to_a_needs_trial_runs_of_that_very_proposal` trong `tests/roadwatch/test_cli_guards.py` (không đặt trong `test_cli.py`, cùng lý do như trên). Hai test D-8 của runtime và test CLI đỏ trước khi có code; test F23 xanh sẵn, giữ làm test hồi quy. Chưa commit
    - [x] Phần pytest của AC-M9 → 30/09/2026: vòng HITL qua CLI (`test_cli.py`); lần chạy kế tiếp mang `approval_id` mới rồi quay lui về phê duyệt cũ; đường `[A, live]` đòi lần chạy thử live trên đúng máy; F23, F24 ở `test_configstore.py`. `perf` bỏ qua lần chạy `--proposed`, `eval` ghi `flags` để báo cáo loại chúng ra. Kịch bản chạy tay AC-M9 cho reviewer nằm trong mô tả PR
    - [ ] Lệnh kiểm tra ở [code-rules](../../development/code-rules.md) mục 8 xanh, không còn `--ignore` → 30/09/2026: phần RoadWatch xanh, không còn `--ignore` (`python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q` → 133 passed; `ruff check src/ tests/` sạch; `git diff --check` sạch). Còn thiếu: `pytest tests/` lỗi khi thu thập test vì template thiếu `pytest_asyncio` (tiếp theo: WP-C1 của Tuấn); `ruff format --check` báo `test_cli.py` chưa format (file này không được sửa theo yêu cầu người dùng)
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng". Lưu ý cho máy demo (laptop của Khánh): `hitl report` và `activate` từ chối khi working tree bẩn, mà hook AI log luôn sửa `.ai-log/.submitted_count` (file đang được track), nên phải commit file này trước khi làm vòng HITL thật
  - **15% CÒN THIẾU CỦA BT-C ĐỂ ĐẠT 100%** (con số 15% do người dùng ước lượng ngày 30/09/2026, không phải số đo; cập nhật cuối ngày 30/09):
    1. WP-C3 (Fixture và kiểm tra liên luồng): bổ sung các file JSONL hợp lệ và sai format vào `tests/roadwatch/fixtures/` → đã làm ngày 30/09, chờ Khánh review (checklist WP-C3 bên dưới).
    2. WP-P4 (Đóng băng `contracts` v1.0): code ở 1.0.0, fixture và snapshot schema đã sinh lại ngày 01/10 (checklist WP-P4 bên dưới). Còn thiếu: Khánh và Tuấn xác nhận, rồi gắn thẻ git `contracts-v1.0`.
    3. WP-P8 (Tích hợp đầu–cuối trên máy demo): chạy thử replay/live trên video thật với Tuấn và Khánh để lấy hash nghiệm thu AC-M1, AC-M10. Công cụ kiểm đã có (`check-run`, `compare`); còn chờ dữ liệu, model, WAV và cấu hình v0.

### WP-C3 · Fixture và kiểm tra liên luồng
- **Xong khi:** mọi fixture sai đều bị từ chối với đúng lý do, và CI chạy các test này.
- **Kiểm chứng:** reviewer tự thêm một fixture sai mà bạn chưa thấy trước, và thấy nó bị từ chối.
- **Checklist:**
  - Bàn giao
    - [x] `tests/roadwatch/fixtures/`: file JSONL hợp lệ và file sai hợp đồng cho mọi schema (spec 4.6) → 30/09/2026: `valid/replay`, `valid/live` là hai lần chạy thật trên clip tổng hợp (sinh lại bằng `python -m tests.roadwatch.make_fixtures` khi đổi schema); `invalid/` có 12 thư mục, mỗi thư mục một lỗi và một `expect.txt` ghi lý do, phủ đủ 9 schema luồng và mọi loại lỗi của spec 4.6. Chưa commit
    - [x] Kiểm tra liên luồng (D-7) trong `src/roadwatch/contracts/`: mỗi cặp (`input_seq`, `arbiter`) có đúng một trace; `AudioPlan` chỉ trỏ tới `alert_id` có thật → 30/09/2026: `check_links` và `check_streams` trong `contracts/streams.py` (kiểm cả `audio_events`). `read_record(strict=True)` coi trường thừa là lỗi của bên ghi. Thứ tự kiểm theo luồng: `t_consumed_ns` cho nhật ký, `input_seq` cho trace, chỉ `seq` cho `events` (live có nhiều thread ghi). Chưa commit
  - Kiểm thử và kiểm chứng
    - [x] `tests/roadwatch/test_contracts.py` đọc toàn bộ fixture; fixture sai bị từ chối đúng lý do → 30/09/2026: 14 test sinh theo thư mục (2 hợp lệ, 12 sai) cộng 1 test kiểm đủ 9 schema; đỏ trước khi có fixture, sau đó `test_contracts.py` 41 passed. Còn thiếu: CI chưa chạy test RoadWatch (chờ WP-C1). Chưa commit
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng". Cách thêm ca mới: tạo thư mục `tests/roadwatch/fixtures/invalid/<tên>/` chứa file JSONL sai (tên file theo luồng, ví dụ `measurements.jsonl`) và `expect.txt` ghi một đoạn của thông báo lỗi mong đợi; test tự nhận thư mục mới

### WP-P6 · Chốt với mentor
- **Xong khi:** có câu trả lời cho OQ-A1, OQ-A2, OQ-A11. Nếu mentor chưa trả lời thì ghi rõ, và báo cáo tuần 1 chỉ dùng cách diễn đạt "sơ bộ".
- **Kiểm chứng:** reviewer đối chiếu nội dung ghi vào spec với biên bản.
- **Checklist:**
  - Bàn giao
    - [ ] Câu trả lời ghi thẳng vào `docs/specs/roadwatch-architecture.md`, mục 10.3
    - [ ] Biên bản trao đổi với mentor trong `JOURNAL.md` (tuần 1)
  - Kiểm thử và kiểm chứng
    - [ ] Nếu còn câu chưa có trả lời: báo cáo tuần 1 chỉ dùng "sơ bộ"
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-P8 · Tích hợp đầu–cuối trên máy demo
- **Xong khi:** AC-M1 và AC-M10 có biên bản gắn hash.
- **Kiểm chứng:** reviewer lặp lại một lần chạy trong biên bản trên cùng máy và nhận kết quả khớp.
- **Checklist:**
  - Bàn giao
    - [x] 03/10/2026: runtime có callback quan sát record/khung sau khi B tiêu thụ, phục vụ preview lúc inference. Không import web/tool vào runtime, không sửa B/schema. Test `test_preview_observers_do_not_change_recorded_decisions` so sánh đầy đủ số đo, speed, journal, trace, alerts và audio_plan với/không observer: khớp.
    - [ ] Biên bản chạy offline và tái lập, ghi ở mục "Tái lập" của `eval/results/report.md`
    - [ ] Lần chạy `live` và `replay` trên máy demo: `runs/<run_id>/` (không commit; ghi `run_id` và hash làm bằng chứng)
    - [x] Điểm vào cho đầu ra A giao sẵn, phiên mẫu và hướng dẫn bàn giao B+C (PO yêu cầu 02/10/2026; không thay cho hai mục trên) → `run --measurements` ở `src/roadwatch/runtime.py`, `live.py`, `cli.py`; phiên mẫu tổng hợp `tests/roadwatch/fixtures/handoff/` (sinh bằng `python -m tests.roadwatch.make_fixtures handoff`); hướng dẫn ở `README.md`, mục "Chạy B+C và nối A"; spec 5.3 và 4.4 (nhãn [v1.2], chờ PO duyệt chi tiết). Các task ở cột "Cần có" chưa xong: phần này chỉ gồm việc không phụ thuộc chúng. Chưa review. nhánh `feat/wp-p4-contracts-v1`
  - Kiểm thử và kiểm chứng
    - [ ] Máy ở chế độ máy bay; lần chạy có đủ các luồng của spec 4.4 → công cụ đã có 30/09: `python -m src.roadwatch.cli check-run runs/<run_id>` (đủ file theo chế độ, không có cờ `log_incomplete`, từng luồng hợp lệ và khớp nhau); còn thiếu: chạy trên máy demo
    - [ ] `rerun-B --verify` đạt; replay hai lần cho `measurements` đã chuẩn hoá giống nhau (spec 5.4) → công cụ đã có 30/09: `python -m src.roadwatch.cli compare <run_a> <run_b>` báo bản ghi khác đầu tiên, lệch tuyệt đối lớn nhất theo trường số và số lần `status` khác; còn thiếu: chạy trên máy demo
    - [x] Chạy thông B+C bằng dữ liệu mẫu trên máy phát triển (không phải máy demo) → 02/10/2026: `tests/roadwatch/test_handoff.py`, 6 test. Kho tạm dựng bằng lệnh `hitl`; B cho đúng năm cảnh báo dự kiến (Cảnh báo 4,5 s; Khẩn cấp 7,0 s; tắt cảnh báo khoảng cách 19,1 s; Khẩn cấp 20,0 s trong lúc mất tốc độ; phục hồi 23,1 s); `check-run` đạt; `rerun-b --verify` đạt; hai lần chạy cho cùng dữ liệu nghiệp vụ; `live` với loa giả lập ghi `audio_events` và cờ `simulated_audio`; đầu vào sai hợp đồng bị từ chối. Chạy lại cùng chuỗi lệnh bằng CLI thật trên kho tạm, cây sạch (commit `0e2df5a`), venv mới Python 3.11: đạt. Toàn bộ: 236 passed. Cập nhật cùng ngày (commit `b29ba35`): phiên mẫu thêm người và làn, file test viết lại thành 7 test; B vẫn cho đúng năm cảnh báo trên; toàn bộ: 242 passed. Còn thiếu: máy demo, A thật, người nghe xác nhận âm thanh, chế độ máy bay
    - [x] `live` với bộ phát thật của máy phát triển (không phải máy demo; không thay cho việc nghe) → 02/10/2026: kho tạm, cấu hình test ghép mục `audio` của `v0.yaml`, bộ WAV nháp ở `models/phrases/`. `run --mode live` trên phiên mẫu: năm `audio_events` đều `started`, không có `audio_fault`, lần chạy không mang cờ `simulated_audio`, `run_stats.json` ghi `played_successfully: 5`; `check-run` và `rerun-b --verify` đạt. `python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml --play` gọi đủ tám câu, mã thoát 0. Còn thiếu: chưa có người nghe xác nhận âm thanh phát ra đúng và rõ; chưa chạy trên máy demo
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-P4 · Đóng băng `contracts` v1.0
- **Xong khi:** AC-M2 đạt.
- **Kiểm chứng:** hai reviewer xác nhận code A và code B của họ đọc và ghi được v1.0 mà không phải sửa.
- **Checklist:**
  - Bàn giao
    - [x] `src/roadwatch/contracts/` ở phiên bản 1.0 → 01/10/2026: PO quyết nâng ngay (trong phiên làm việc với AI), vì chưa có lần chạy thật nào và bên đọc từ chối bản ghi khác MAJOR. `CONTRACTS_VERSION = "1.0.0"` trong `contracts/base.py`, dùng chung cho `schema_version` của mọi bản ghi luồng và `contracts_version` của `run_manifest` (trước đó là hai số: 0.1.0 và 0.2.0). Hai trường PO quyết thêm trước khi đóng băng: `audio.phrases_sha256` (D-16; live kiểm hash lúc khởi động khi trường có giá trị) và `provisional_keys` ở cấp gốc của `rw.config` (D-17; validator từ chối khoá không trỏ tới trường có thật). Test viết trước, đỏ rồi xanh: `test_contracts_are_frozen_at_1_0_0`, `test_provisional_keys_must_name_fields_of_the_config` (`tests/roadwatch/test_contracts.py`), `test_check_phrases_refuses_a_library_whose_hash_is_not_the_configured_one` (`tests/roadwatch/test_phrases.py`). Hai test sẵn có đổi dữ liệu vì số phiên bản đổi: `test_reader_refuses_other_major` nay đọc bản ghi 0.1.0, `test_reader_ignores_unknown_fields_of_same_major` dùng 1.9.0. `render_phrases` in `phrases_sha256` thay cho `library_sha256`, để chép thẳng vào mục `audio`. Cùng commit với checklist này, nhánh `feat/wp-p4-contracts-v1`
    - [x] `docs/specs/roadwatch-architecture.md`, mục 4: D-3 đã đồng bộ mô tả trong WP-P1; còn D-4 và kiểm chứng trước khi đóng băng → 01/10/2026: sửa 4.4 theo D-4 (đủ trường của `RunManifest`). Đối chiếu từng model với mục 4, tìm thêm D-19 (cấu hình có mục `detector`, không phải `perception.model`; tên và các trường của session manifest), đã sửa 4.4 và 4.5 theo code, không đổi schema. Ghi D-16, D-17 vào 4.5; ghi cách đặt số phiên bản vào 4.6; cập nhật dòng D-8 (đã làm từ WP-C2). Còn thiếu: PO xác nhận D-19 khi review PR. D-2 (replay một thread) thuộc mục 3.1–3.2, không thuộc hợp đồng, chưa sửa. Cùng commit với checklist này
    - [x] JSON Schema xuất ra `docs/specs/schemas/` → 01/10/2026: `docs/specs/schemas/contracts.schema.json` sinh bằng `python -m scripts.roadwatch.export_schemas` (công cụ của PR #3); `--check` đạt; `stream_schema_version` là 1.0.0. File vẫn ghi `status: implementation_snapshot`. Tiếp theo: khi hai reviewer xác nhận, đổi `status` và dòng "Not an approved or frozen v1.0 contract" trong `scripts/roadwatch/export_schemas.py` rồi sinh lại. Không dùng `cli schema --out` cho thư mục này: lệnh đó ghi mỗi schema một file, khác snapshot mà `--check` kiểm
    - [ ] Thẻ git `contracts-v1.0` → còn thiếu: chưa gắn. Tiếp theo: gắn trên commit đã vào `main`, sau khi Khánh và Tuấn xác nhận (PO quyết 01/10). 02/10/2026: code đã lên 1.1.0 (WP-C11). Gắn thẻ ở 1.0.0 (commit `834b86e`) hay ở 1.1.0 là việc PO quyết (OQ-A15)
  - Kiểm thử và kiểm chứng
    - [x] Mọi fixture hợp lệ đều qua, mọi fixture sai đều bị từ chối, test hợp đồng của từng thành phần đạt → 01/10/2026: sinh lại `valid/` và `scenarios/` bằng `python -m tests.roadwatch.make_fixtures`; 12 fixture `invalid/` nâng `schema_version` lên 1.0.0, riêng `frames_other_major` dùng 2.0.0 cho dòng sai MAJOR. `python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q` → 227 passed; `rerun-b --verify` và `check-run` đạt trên `valid/replay`, `valid/live`; `ruff check src/ tests/ scripts/roadwatch` sạch; `check_docs` và `export_schemas --check` đạt. Còn thiếu: CI chưa chạy test RoadWatch (WP-C1). **Rủi ro cho bước review:** code BT-A của Tuấn trên `origin/tuannq`, `origin/khanhtr` nằm ở package riêng `roadwatch/` (có `types.py`, `config.py`, `manifest.py` riêng) và không dùng `src/roadwatch/contracts/`, nên chưa có gì để xác nhận "code A đọc và ghi được v1.0". Tiếp theo: PO và Tuấn chốt cách nối code đó vào `Measurement` (WP-A0)
  - Review và nghiệm thu
    - [ ] Hai reviewer kiểm theo mục "Kiểm chứng"

### WP-P7 · Giới hạn đã biết và demo MVP
- **Xong khi:** mọi AC-M có một trong ba trạng thái (đạt, chưa đạt, chưa kết luận), kèm bằng chứng.
- **Kiểm chứng:** reviewer đối chiếu từng AC-M với bằng chứng ở bảng dưới. Không dòng "đạt" nào được thiếu bằng chứng.
- **Cần có** (cột "Cần có" ở README mục 4.1 lấy đúng từ bảng này):

| Bằng chứng cho WP-P7 | Task cho ra |
|---|---|
| AC-M3, M4, M5, M6: báo cáo `test_small` và các mục đã tổng hợp của `eval/results/report.md` | WP-D6 |
| AC-M1, M10: biên bản chạy offline và tái lập | WP-P8 |
| AC-M2: `contracts` v1.0 | WP-P4 |
| AC-M7: phần B (fixture F1–F16) và phần live (F1, F18) | WP-B9, WP-A6 |
| AC-M8: kết luận kiểm tra lắp đặt | WP-A3 |
| AC-M9: vòng HITL trọn vẹn qua CLI | WP-C2 |
| AC-M12: runtime chạy trên clip thật có âm thanh, bảng B so với baseline | WP-P8, WP-D6 |

  WP-P5 (nhật ký), WP-P6 (chốt với mentor) và WP-D7 (phỏng vấn) không chặn WP-P7. Câu nào của WP-P6 chưa có trả lời thì ghi vào danh sách giới hạn.
- **Checklist:**
  - Bàn giao
    - [ ] Danh sách giới hạn (AC-M11) ở mục "Giới hạn" của `eval/results/report.md`: AC chưa đạt hoặc chưa kết luận, mục "chưa kiểm chứng", F17, giới hạn cam kết âm thanh, trạng thái file Word (OQ-A6), OQ còn mở
    - [ ] Buổi demo hoặc video chạy offline (AC-M12); link hoặc biên bản ghi trong `JOURNAL.md`, tuần 1
  - Kiểm thử và kiểm chứng
    - [ ] Mỗi AC-M có trạng thái, và bằng chứng đúng loại mà spec mục 7 ghi cho AC đó
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-P5 · Nhật ký và deliverables
- **Xong khi:**
  - Tuần 1: mỗi ngày làm việc có dòng WORKLOG của cả bốn người, và JOURNAL tuần 1 đủ các mục của template.
  - Tuần 2–4: đủ deliverables 2, 6, 7 (spec 11.2).
- **Kiểm chứng:** reviewer đối chiếu WORKLOG với các task có trạng thái đổi trong tuần; kiểm deliverables theo `docs/guide/deliverables/checklist.md`.
- **Checklist:**
  - Bàn giao
    - [x] `WORKLOG.md`: các ngày 28/09 và 29/09 → 29/09/2026: đã ghi; commit 8943c1c, 4ed1285
    - [x] Cài AI log trên máy hiện tại, hướng dẫn trong `README.md`; bỏ bộ đếm gửi cục bộ khỏi Git qua `.gitignore` → 29/09/2026: chạy `scripts/setup_hooks.sh`; dùng endpoint/key sẵn có trong `.env`; sao lưu bộ đếm kế thừa trong `.git/` rồi để script khởi tạo lại; HTTP 202 nhận 2 bản ghi thật. Không commit key hay nội dung log; bằng chứng đi cùng commit WP-P5
    - [ ] `JOURNAL.md`, tuần 1
    - [x] `README.md` hoàn chỉnh cho deliverable 2 (tuần 2–4) → 09/10/2026: theo yêu cầu người dùng, viết lại giới thiệu end-to-end, banner SVG và badge/logo stack; hướng dẫn chạy khớp server core và script tải model. Kiểm liên kết bằng `python -m scripts.roadwatch.check_docs`, SVG parse và `git diff --check` đạt; chưa reviewer kiểm deliverable. Không thay cho pitch/video.
    - [ ] `presentation/pitch_deck.pptx`, 10 slide (tuần 2–4)
    - [ ] Video demo ≤ 5 phút; link ghi trong `presentation/README.md` (tuần 2–4)
  - Kiểm thử và kiểm chứng
    - [ ] Các thành viên còn lại tự ghi WORKLOG mỗi ngày họ làm việc
    - [x] Kiểm hai lệnh hook Codex với payload tổng hợp và `AI_LOG_DIR` trỏ thư mục tạm → 29/09/2026: `UserPromptSubmit` và `Stop` đều ghi đúng tool/repo; không đưa bản ghi tổng hợp vào log thật
    - [ ] Người dùng mở Codex tại gốc `P-014`, review/trust hook bằng `/hooks`, gửi prompt mới và kiểm log tăng → còn thiếu: xác nhận hook tự chạy trong phiên Codex thực tế; lệnh hook đã kiểm riêng
  - Review và nghiệm thu
    - [ ] Reviewer kiểm tuần 1 theo mục "Kiểm chứng"
    - [ ] Reviewer kiểm deliverables tuần 2–4

## Tuần 2–4

### WP-C11 · Hợp đồng và điểm nối cho Người và Làn
- **Xong khi:** A có chỗ trong hợp đồng để ghi đối tượng khác (xe, người) kèm vùng rủi ro, và trạng thái làn; B và C đọc, kiểm, ghi log và chạy lại được dữ liệu đó; hành vi MVP không đổi. Luật cảnh báo cho người và cho lệch làn **không** thuộc task này: chúng chờ PO quyết (OQ-A13, OQ-A14, OQ-A15).
- **Kiểm chứng:** reviewer chạy `tests/roadwatch/test_handoff.py`; tự thêm vào phiên mẫu một người trong vùng rủi ro hoặc một đoạn trôi làn rồi thấy quyết định của B không đổi; R-A xác nhận ghi được các trường này từ code A.
- **Checklist:**
  - Bàn giao
    - [x] `src/roadwatch/contracts/streams.py`: `RiskObject`, `RiskZone`, `LaneState`; `Measurement.risk_objects` và `Measurement.lane` (tuỳ chọn, mặc định `null`); `CONTRACTS_VERSION` 1.1.0 → 02/10/2026: luật kiểm: A không nhìn được thì `risk_objects` là `null`, không phải `[]`; không lặp lại xe dẫn đầu; kết quả làn không mới hơn khung của nó; khác `ok` thì không có giá trị và phải có lý do. B và runtime không đọc hai trường. Commit `b29ba35`
    - [x] Spec mục 4.2 (bảng trường, nhãn [v1.2]), 4.6, 3.6 (thứ tự ưu tiên audio đề xuất), 10.3 (OQ-A13, OQ-A14, OQ-A15); requirements file 1, mục 6.3; `docs/specs/schemas/contracts.schema.json` sinh lại → 02/10/2026: cùng commit với checklist này. Còn thiếu: PO duyệt các nội dung [v1.2]
    - [x] Phiên mẫu đủ xe, người và làn: `tests/roadwatch/fixtures/handoff/measurements.jsonl`; file 1.0.0 giữ lại là `measurements-mvp-1.0.0.jsonl` → 02/10/2026: ngoài xe dẫn đầu, phiên mẫu có một xe ở làn bên (9,0–11,9 s, ngoài vùng rủi ro); một người, lúc đầu chưa xác định được vùng (14,0 s), rồi ở trong vùng với TTC dưới ngưỡng Khẩn cấp (15,0–15,9 s); vạch mờ, `lane` là `unreliable` (5,0–5,9 s); vạch phải không đo được (8,0–8,5 s); xe trôi tới cách vạch phải 0,31 m (24–26 s); kết quả làn cũ hơn khung 100 ms ở một nửa số bản ghi. Mọi giá trị là dữ liệu tổng hợp, không phải số đo. Commit `b29ba35`
  - Kiểm thử và kiểm chứng
    - [x] Test hợp đồng viết trước, đỏ rồi xanh → 02/10/2026: `tests/roadwatch/test_contracts.py`: `test_risk_zone_is_a_verdict_with_its_basis_or_a_reason`, `test_risk_objects_are_null_when_a_cannot_see_and_never_repeat_the_lead`, `test_lane_state_says_how_far_each_line_is_or_why_not`, `test_a_measurement_without_the_extension_fields_keeps_its_meaning`
    - [x] Đọc, kiểm, ghi log, chạy lại; B không cảnh báo ngoài ý muốn; file 1.0.0 vẫn chạy → 02/10/2026: `test_people_and_the_lane_are_read_logged_and_replayed_but_b_says_nothing_about_them` trong `tests/roadwatch/test_handoff.py`: dữ liệu người và làn có trong log đúng như đầu vào; `check-run` và `rerun-b --verify` đạt; lần chạy trên file 1.0.0 và trên file 1.1.0 cho cùng nhật ký đầu vào, trace, cảnh báo và kế hoạch audio. Toàn bộ: 242 passed
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-C5 · Docker, `.env.example`, logging
- **Xong khi:** `docker build` chạy được, và lệnh test chạy được trong container.
- **Kiểm chứng:** reviewer build lại từ đầu trên một máy khác.
- **Checklist:**
  - Bàn giao
    - [ ] `Dockerfile` và `docker-compose.yml` cho công cụ và web UI
    - [ ] `.env.example` chỉ còn các biến RoadWatch cần, không chứa bí mật
    - [ ] Logging có cấu trúc cho công cụ trong `src/roadwatch/`
  - Kiểm thử và kiểm chứng
    - [ ] `docker build` chạy được; lệnh test chạy được trong container
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"

### WP-C9 · Live URL
- **Xong khi:** theo phương án PO chọn ở OQ-E1. Nếu chọn không deploy thì lý do được ghi vào spec mục 11.2 và task đóng.
- **Kiểm chứng:** reviewer mở URL từ một máy khác, với dữ liệu mẫu.
- **Checklist:**
  - Bàn giao
    - [ ] Cấu hình deploy trong `deploy/` (tên thư mục chốt sau OQ-E1), và URL ghi trong `README.md` → tiếp theo: hỏi mentor ở WP-P6
  - Kiểm thử và kiểm chứng
    - [ ] URL chạy với dữ liệu mẫu, không cần runtime
  - Review và nghiệm thu
    - [ ] Reviewer kiểm theo mục "Kiểm chứng"
