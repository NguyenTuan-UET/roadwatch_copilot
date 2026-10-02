# Worklog — Team P-014 (RoadWatch Copilot)

> Ghi lại công việc đã làm theo ngày: ai làm gì, kết quả gì.
>
> **Đây là nhật ký, không phải bảng tiến độ.** Cột "Trạng thái" chỉ là ảnh chụp tại ngày ghi. Trạng thái hiện hành, việc còn lại và bước tiếp theo nằm ở [docs/plan/README.md](docs/plan/README.md), mục 4. Cột "Thời gian" để "—" khi không đo.

---

## 2026-10-02

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Codex) | Review tiến độ WP-B0/B1/B2/B3/B8/B9, WP-C1/C2/C3/C4 và phụ thuộc WP-P2/P3/P4/P8 theo yêu cầu | Chưa nghiệm thu; giữ trạng thái trong plan | 02/10/2026: nhánh `feat/wp-b0-b9-c4-decision-eval`, HEAD `cf02f0e`; fetch origin thành công, chưa remote nào chứa HEAD. `python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q -p no:cacheprovider --tb=short`: 222 passed; ruff check phần RoadWatch sạch; ruff format --check báo 5 file. Thu thập test toàn repo lỗi thiếu pytest_asyncio. Chưa có models/phrases, runs, data trên máy này; checklist xác nhận chưa render Piper thật, chưa quét dev và chưa chạy nghiệm thu máy demo. Thiếu CI RoadWatch, quyết định D-16/D-17 và reviewer B mới; không sửa code hay chạy HITL thật | — |
| Cương (dùng Antigravity) | Biên soạn tài liệu phân tích BT-B, BT-C, cập nhật quy trình chuẩn AI và đồng bộ tài liệu | Đã hoàn thành | `QUY_TRINH_PHAT_TRIEN_PHAN_MEM_CHUAN_AI.md`, `doc_indivisual/bai_toan_B.md`, `doc_indivisual/bai_toan_C.md`, 222 test passed | — |

---

## 2026-10-01

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Codex) | WP-P1: review PR #3 tại head `fe1ec62`, base `64fd76f` trên bản sao tạm | Có phát hiện P2; chưa sửa hoặc đăng review lên GitHub | 106 test RoadWatch đạt; check_docs, snapshot, 2 unittest, ruff check và diff check đạt. Tái hiện: thay WP-P1 ở plan 4.3 bằng WP-P999 thì check_docs vẫn trả về danh sách lỗi rỗng. Ruff 0.16.9 báo 1 file test cần format. Chưa xác minh Checks/approval GitHub; không nghiệm thu toàn bộ WP-P1 | — |
| Cương (dùng Codex) | WP-P1: theo yêu cầu, thêm quy tắc kiểm GitHub đầu phiên, cập nhật nguồn chuẩn an toàn và chỉ push nhánh task | Chờ review; chưa commit/push | `AGENTS.md`, code-rules mục 11, checklist và plan 4.3. Fetch thành công; `origin/main` tại `b6e560a` có PR #3 chưa tích hợp vào nhánh hiện tại. Giữ nguyên việc dở; chưa merge. Kiểm diff và khoảng trắng; không đổi runtime hoặc sơ đồ | — |
| Cương (dùng Claude Code) | Theo chỉ định của PO: làm thay Khánh các task BT-B. WP-B0 (tiếp nhận), WP-B9 (phương án (b) của OQ-B12, S1–S7, fixture F1–F18, test OQ-A5), WP-B1 (bảng pháp lý và phần B của cấu hình v0), WP-B2 (script câu nói), WP-B8 và WP-C4 (đánh giá), chuẩn bị WP-B3 (công cụ quét) | 🟡 chờ review; PO chưa chỉ định reviewer mới cho các task B. Chưa có file WAV; WP-B3 chờ dữ liệu `dev` | Sửa 3 lỗi của B (D-14, D-15, I-16) và bổ sung `eval` (D-9, D-18), test viết trước. Test OQ-A5: **không có giới hạn trên**, 2 test để `xfail` chờ PO. Đề xuất [v1.2] cho OQ-B4, OQ-B5, OQ-A3, OQ-A5, I-12, I-13, D-16, D-17 ở spec, PO chưa quyết. RoadWatch 212 passed, 2 xfailed; `ruff check src/ tests/ scripts/roadwatch` sạch; hơn 80 lần cố ý làm hỏng luật đều bị test bắt. `src/roadwatch/decision/`, `evaluate.py`, `cli.py`, `runtime.py`, `scripts/roadwatch/`, `config/proposals/v0.yaml`, `tests/roadwatch/`, spec, `khanh.md`, plan mục 3, 4.1, 4.3, code-rules mục 9, `eval/results/report.md` mục 6. Về sau trong ngày đã commit, xem dòng cuối của ngày | — |
| Cương (dùng Claude Code) | WP-C2: tách phần đọc cấu hình khỏi kho HITL (D-13, PO chấp nhận ngày 29/09 kèm "tách nếu còn thời gian") | 🟡 chờ Tuấn review | `src/roadwatch/configread.py` (mới), `configstore.py`, `runtime.py`; test viết trước kiểm rằng runtime không nạp `sqlite3` hay công cụ C. RoadWatch 213 passed, 2 xfailed; `ruff` sạch; hai fixture lần chạy vẫn qua `rerun-b --verify`. code-rules mục 1, 3, 9; spec dòng D-13; `cuong.md`; plan mục 3 và 4.3. Fetch đầu phiên: `origin/main` vẫn ở `b6e560a`; `origin/khanhtr` có 2 commit mới (`fb86ae9`, `9fe2885`) đưa code BT-A của Tuấn vào thư mục `roadwatch/`, chưa vào `main`. Về sau trong ngày đã commit, xem dòng dưới | — |
| Cương (dùng Claude Code) | WP-B9, WP-B8: PO quyết trong phiên. OQ-A5: thêm luật "`HOLD` khi đợt đang rời". OQ-A3: dùng τ 0,5; `lead_max` 3,0 s; `max_late` 2,0 s cho `dev`, chưa chốt cho `test_small`. Commit toàn bộ việc trong ngày | 🟡 chờ review; chưa push | Luật OQ-A5 ở `src/roadwatch/decision/episodes.py`, test viết trước (7 test đỏ rồi xanh), spec 3.5 và 10.3. RoadWatch 222 passed, không còn `xfail`; kiểm lại trên bản checkout sạch của commit cũng 222 passed. Nhánh `feat/wp-b0-b9-c4-decision-eval`: `1325e86` (WP-B9, WP-B1), `87b0814` (WP-B8, WP-C4, công cụ WP-B3), `85c58ca` (WP-B2, D-13), `cf02f0e` (tài liệu). Sự cố: công cụ tự kiểm "cố ý làm hỏng luật" một lần không ghi lại được file gốc (`OSError 22`, thư mục OneDrive) và để sót một dòng sai trong `episodes.py`; lần chạy test cuối bắt được, đã khôi phục và gia cố công cụ trước khi commit. `WORKLOG.md` này và các sửa của phiên Codex chưa commit | — |

---

## 2026-09-30

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Codex) | Theo yêu cầu: lưu bản kỹ thuật và bản đơn giản về hợp đồng đầu vào/đầu ra; tham chiếu WP-P4, không thực hiện đóng băng schema | Tài liệu diễn giải, chưa nghiệm thu hợp đồng | [Hợp đồng bàn giao](docs/plan/hop-dong-dau-vao-dau-ra.md); đối chiếu spec và code, kiểm liên kết nội bộ và khoảng trắng. Không đổi trạng thái task trong plan. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-C2: viết `cli.py` gồm `run`, `rerun-b`, `eval`, `perf`, `schema`, `hitl` (8 lệnh con); `hitl report` chặn split `test_*` (D-11) và chặn đổi mục `[A]` cho tới khi có D-8 | 🟡 chờ Tuấn review; còn D-8, `run_stats.json` | `src/roadwatch/cli.py`, `configstore.proposal_config`, `tests/roadwatch/test_cli_guards.py`; `test_cli.py` 2 passed, không sửa test; RoadWatch 108 passed; `ruff` sạch. Cập nhật `cuong.md` (WP-C2), plan mục 3 và 4.3, `doc_indivisual/bai_toan_C.md`. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-C2, WP-C3, hỗ trợ WP-P8 và WP-P3: `run --proposed` (D-8) và `hitl report` cho đường `[A]`, `[A, live]`; fixture JSONL hợp lệ và sai hợp đồng, kiểm tra liên luồng (D-7); lệnh `check-run` (AC-M1) và `compare` (AC-M10); test khởi tạo cấu hình đầu tiên qua CLI thay script bootstrap | 🟡 chờ review (Tuấn: WP-C2, Khánh: WP-C3); `run_stats.json` chờ PO định nghĩa | `src/roadwatch/cli.py`, `runtime.py`, `rerun.py`, `contracts/`, `tests/roadwatch/fixtures/`, `make_fixtures.py`, test mới trong `test_runtime.py`, `test_contracts.py`, `test_rerun_eval.py`, `test_cli_guards.py`; RoadWatch 129 passed, `ruff check` sạch. Spec 4.4, code-rules mục 9, `cuong.md`, plan mục 3, 4.1, 4.3. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-C2: `run_stats.json` theo nội dung PO chốt; 2 test AC-M9 (lần chạy sau mang `approval_id` mới rồi quay lui; đường `[A, live]`); `perf` bỏ qua lần chạy `--proposed`, `eval` ghi `flags`. WP-P3: PO bỏ `hitl_bootstrap.py`, đóng OQ-B3 | 🟡 chờ review (Tuấn: WP-C2, Khánh: WP-C3) | `runtime.py`, `evaluate.py`, `cli.py`, fixture sinh lại; spec 4.4 và 10.1, `review-v1.1.md`, `cuong.md`, plan 4.3; RoadWatch 133 passed, `ruff check` sạch. Nhánh `feat/wp-c2-c3-cli-fixtures` | — |

---

## 2026-09-29

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Agent (theo yêu cầu người dùng) | WP-P5: cài đặt AI log theo AI20K Agent Template | 🟡 cần người dùng trust hook Codex | Cài lại pre-push hook bằng script có sẵn; giữ cấu hình endpoint/key trong `.env` và giới hạn quyền đọc file. Bỏ `.submitted_count` khỏi Git vì bản clone mang bộ đếm 225 trong khi chỉ có 1 log; sao lưu bộ đếm trong `.git/`, để script khởi tạo lại. Hai sự kiện hook Codex đã kiểm riêng trên thư mục tạm; log thật gồm 2 bản ghi đã được máy chủ nhận HTTP 202; lần gửi tiếp theo không gửi trùng. README ghi cách mở đúng workspace và trust hook. Commit cài AI log WP-P5 trên `khanhtr` | — |
| Agent (theo yêu cầu người dùng) | WP-P1: chuẩn hóa tài liệu để agent đọc; metadata, luật đang có hiệu lực, literal hợp đồng, snapshot Pydantic và kiểm tra tài liệu chạy lại được | 🟡 chờ reviewer | `docs/development/docs-rules.md` mục 7; spec mục 3.7 và 4; `scripts/roadwatch/`; schema sinh tự động; `tests/roadwatch/test_documentation.py`. Kiểm tài liệu/schema/lint và diff sạch; 106 test RoadWatch đạt; test công cụ kiểm 10 lỗi giả. Dùng môi trường tạm có pytest, không đổi dependency dự án. Mermaid không đổi, chưa render lại. Commit chuẩn hóa WP-P1 trên `khanhtr`; GitHub CLI chưa đăng nhập để tạo PR | — |
| Cương (dùng Claude Code) | WP-P1: soạn bộ tài liệu v1.1 cho nhóm 4 người. Bỏ đề xuất LLM agent theo ADR-12; phân công mới; sơ đồ kiến trúc và sơ đồ phối hợp; quy tắc code, quy tắc tài liệu, quy tắc theo dõi tiến độ | 🟡 chờ PO duyệt | `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, `docs/architecture_diagram.md`, `docs/development/`, `docs/plan/`, spec (các phần [v1.1]). **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1: thêm checklist ba nhóm (bàn giao, kiểm thử và kiểm chứng, review và nghiệm thu) cho cả 49 task; plan chỉ còn giữ trạng thái tổng và liên kết | 🟡 chờ PO duyệt | `docs/plan/phan-viec/*.md`, `docs/plan/README.md` (mục 0, 4.3), `AGENTS.md`, code-rules, docs-rules. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1: xử lý 7 phát hiện review. Sửa luật fail-safe, luật bằng chứng AC, giữ kín `test_small` và `test_final`, phụ thuộc WP-P7, nhãn `test_final`. Hai đề xuất hành vi chờ PO: guardrail khi đợt tiếp diễn (OQ-B12), chạy thử cấu hình đề xuất (OQ-B13) | 🟡 chờ PO duyệt | Spec (3.5, 3.7, 3.10, 4.4, 6.2, 10.1, D-8), `AGENTS.md`, code-rules, docs-rules, `docs/architecture_diagram.md`, `docs/plan/`. **Chưa commit** | — |
| Cương (dùng Claude Code) | WP-P1, WP-P2: PO duyệt bộ tài liệu v1.1 và chốt 19 quyết định; hạn nộp MVP 04/10/2026, nén lịch còn N0…N5; OQ-B12 chọn (b), OQ-B13 duyệt; máy demo là laptop của Cương. OQ-A6: sinh lại file Word từ ba file requirements | 🟡 chờ ba reviewer xác nhận | Spec (header, 3.5, 3.7, 3.10, ADR-13, 10, 11.5, 12), `docs/plan/`, `README.md`, `docs/architecture_diagram.md`, `.gitignore`, `docs/requirements/tai_lieu_viet_bao_cao.docx`. **Chưa commit** | — |

**Tổng kết ngày:**
- Bộ tài liệu đã sẵn sàng cho review; danh sách quyết định chờ PO ở `docs/plan/review-v1.1.md`, mục 5.
- Code sản phẩm vẫn tạm dừng.

---

## 2026-09-28

| Member | Task | Trạng thái | Output | Thời gian |
|--------|------|------------|--------|-----------|
| Cương (dùng Claude Code) | Thiết kế kiến trúc và hợp đồng dữ liệu RoadWatch | Spec v1.0 được PO duyệt | `docs/specs/roadwatch-architecture.md`, commit 3f76f09 | — |
| Cương (dùng Claude Code) | Code nền T1–T7 theo kế hoạch ban đầu: contracts, BT-B, kho cấu hình và HITL, source, BT-A, runtime, `rerun-B` và đánh giá | Đã có code và unit test, **chưa nghiệm thu** | Commit 348a6b4…9ba15a3; 104 unit test qua | — |
| Cương (dùng Claude Code) | WP-C2: bắt đầu CLI, viết test trước | 🟡 | `tests/roadwatch/test_cli.py`, **chưa commit** | — |

**Tổng kết ngày:** PO dừng việc viết code để ưu tiên hoàn thiện kiến trúc và tài liệu cho cả nhóm cùng triển khai.

---

<!-- Mỗi phiên làm việc: thêm một block ngày ở trên cùng. Trạng thái hiện hành luôn cập nhật ở docs/plan/README.md, mục 4 và 4.3. -->
