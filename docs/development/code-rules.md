# Quy tắc code RoadWatch

**Phạm vi.** Áp dụng cho `src/roadwatch/`, `tests/roadwatch/` và các script phục vụ RoadWatch.

**Nguồn chuẩn liên quan:**
- Kiến trúc và hợp đồng dữ liệu: [spec](../specs/roadwatch-architecture.md).
- Tình trạng code và task: [docs/plan/README.md](../plan/README.md).
- Quy tắc tài liệu: [docs-rules.md](docs-rules.md).
- Luật kiến trúc không được phá (ranh giới, guardrail, fail-safe, HITL): [AGENTS.md](../../AGENTS.md), mục 1. File này chỉ nói cách viết code để giữ các luật đó.

## 1. Tổ chức code hiện có

| Đường dẫn | Trách nhiệm | Phần |
|---|---|---|
| `src/roadwatch/contracts/` | Model Pydantic của mọi bản ghi và cấu hình (`base.py`, `streams.py`, `config.py`) | Gốc chung |
| `src/roadwatch/detect.py`, `perception.py` | Detector ONNX, tracker, xe dẫn đầu, khoảng cách, TTC, `observation`, `mount_check` | BT-A |
| `src/roadwatch/decision/` | `join`, năng lực, các đợt cảnh báo, bộ phân xử audio, `DecisionStage`; toàn bộ là hàm thuần | BT-B |
| `src/roadwatch/source.py` | Lịch khung theo PTS, bản ghi giữ chỗ, đọc GPS | BT-C (runtime) |
| `src/roadwatch/runtime.py`, `live.py` | Replay tất định; live nhiều thread, supervisor, audio sink | BT-C (runtime) |
| `src/roadwatch/configread.py` | Đọc cấu hình đã duyệt từ file (`load_active`, `load_version`, `load_approval`, `read_pointer`): phần duy nhất của kho cấu hình mà runtime dùng | BT-C (runtime) |
| `src/roadwatch/configstore.py` | Lệnh HITL của kho cấu hình (SQLite, khoá); xuất lại các hàm đọc để công cụ chỉ cần một module | BT-C (công cụ) |
| `src/roadwatch/rerun.py`, `evaluate.py` | `rerun-B`, khớp nhãn, latency | BT-C (công cụ) |
| `tests/roadwatch/factories.py`, `decision_harness.py` | Hàm dựng dữ liệu và bộ chạy B dùng chung cho test | Test |

**Code mẫu của template môn học không thuộc sản phẩm:** `src/agents/`, `src/api/`, `src/services/`, `src/models/`, `src/config.py`, `src/main.py`, `tests/test_agents/`, `tests/test_api/`, `tests/conftest.py`. Không sửa khi chưa có task, và không import từ `src/roadwatch/`.

## 2. Python và Ruff

- **Python ≥ 3.11.** Căn cứ: `target-version = "py311"` trong `ruff.toml`; CI dùng 3.11. Máy bạn có thể chạy bản mới hơn, nhưng không dùng cú pháp mới hơn 3.11 (ví dụ generic kiểu `def f[T]()`).
- **Lint** theo `ruff.toml`: bật `E`, `F`, `I`, `N`, `W`, `UP`; bỏ `E501`; dài dòng tối đa 120. Chỉ dùng `# noqa` khi có mã luật kèm lý do, như code hiện có: `# noqa: BLE001 - lý do`.
- **Định dạng.** `ruff.toml` có mục `[format]`, nhưng code RoadWatch hiện có **chưa** được định dạng bằng `ruff format` (ngày 29/09: 22/30 file sẽ bị đổi).
  - Không chạy `ruff format` cho cả thư mục trong PR tính năng, vì sẽ trộn thay đổi định dạng với thay đổi logic.
  - Có định dạng toàn bộ hay không là quyết định của PO. Nếu có, làm trong một commit riêng.
- **mypy.** `Makefile` có lệnh `typecheck` (mypy), nhưng mypy không nằm trong `requirements.txt` hay CI, nên không phải điều kiện để merge.
- **Import.** Trong package dùng import tương đối (`from .contracts.base import Q`). Test import theo kiểu `from src.roadwatch… import …`, như các test hiện có.

## 3. Ranh giới import

| Module | Được import | Không được import |
|---|---|---|
| `contracts/` | Thư viện chuẩn, `pydantic` | Bất kỳ module nào khác của `roadwatch` |
| `detect.py`, `perception.py` (A) | `contracts`, `numpy`, `cv2`, `onnxruntime` | `decision/`, `runtime`, `configstore`, công cụ |
| `decision/` (B) | `contracts` và module trong `decision/` | Mọi I/O: file, mạng, đồng hồ hệ thống (`time`, `datetime.now`), số ngẫu nhiên không có seed |
| `source.py` | `contracts`, `numpy`, `cv2` | `decision/`, công cụ |
| `runtime.py`, `live.py` | `contracts`, `source`, `perception`, `decision/`, `configread` | `configstore`, `sqlite3`, `rerun`, `evaluate`, CLI, web UI |
| `configread.py` | `contracts`, `yaml` | `configstore`, `sqlite3`, `runtime`, `decision/`, `perception` |
| `configstore.py` | `contracts`, `configread`, `sqlite3`, `yaml` | `runtime`, `decision/`, `perception` |
| `rerun.py`, `evaluate.py`, CLI (công cụ C) | Mọi module ở trên | Không module runtime, A hay B nào được import ngược lại công cụ |

- **Runtime không nạp SQLite hay công cụ C.** Phần đọc cấu hình nằm riêng ở `configread.py`; `configstore.py` (lệnh HITL, SQLite) chỉ dành cho công cụ (D-13). Luật này có test: `test_the_product_path_loads_neither_sqlite_nor_any_tool_of_c` trong `tests/roadwatch/test_runtime.py` nạp `runtime` và `live` trong một tiến trình mới, rồi kiểm rằng `sqlite3`, `configstore`, `cli`, `rerun`, `evaluate` không bị nạp theo.
- **Không bao giờ thêm vào `src/roadwatch/`:** LLM, LangChain, LangGraph, RAG, vector database, dịch vụ cloud (ADR-12, NG12).
- **Khi review PR:** xem các dòng `import` mới có vi phạm bảng trên không.

## 4. Kiểu dữ liệu, đơn vị, đồng hồ

- Mọi hàm public và mọi giao tiếp giữa các thành phần phải có type hints. Dữ liệu đi qua ranh giới thành phần là model trong `contracts`, không phải `dict`.
- **Đơn vị** nằm trong tên trường (spec 4.0): `_m`, `_s`, `_ms`, `_ns`, `_mps`, `_px`, `_hz`.
- **Thời gian** là số nguyên nano giây:
  - `t_*_ns`: đồng hồ phiên.
  - `*_mono_ns`: đồng hồ monotonic, chỉ có ở live (là `null` ở replay).
  - `*_utc_ns`: giờ UTC.
- Không cộng trừ hai mốc thuộc hai đồng hồ khác nhau. Đổi đồng hồ phải qua một hàm có tên rõ ràng, như cách `source.py` đưa giờ GPS về đồng hồ phiên.
- **Đại lượng đo** dùng kiểu `Q`:
  - thiếu dữ liệu thì `value = null` kèm `status` và `reasons`, **không bao giờ dùng 0**;
  - cấm NaN và ±∞;
  - chỉ điền `sigma` khi có phương pháp ước lượng.

## 5. Validation ở biên, lỗi có ngữ cảnh

- **Biên** là nơi dữ liệu đi vào hệ thống: đọc JSONL (`read_record`), nạp cấu hình (validator của `RwConfig`), tham số CLI, file ngoài (video, GPS CSV, manifest, nhãn). Kiểm tra ở biên; bên trong hàm thuần thì tin vào kiểu dữ liệu.
- **Báo lỗi.** Dùng exception cụ thể (`ConfigError`, `HitlError`, `ValueError`). Thông báo phải nói file nào, bản ghi nào, trường nào, giá trị gì, sai vì sao. Khi bọc lỗi thì giữ lỗi gốc bằng `raise … from e`.
- **Không nuốt exception.**
  - Không dùng `except:` trống. Không dùng `except Exception: pass`.
  - Chỉ bắt rộng ở ranh giới thread để **ghi lại** lỗi thành sự kiện, như `guarded()` trong `live.py` ghi lỗi cho `system_fault`. Kèm chú thích lý do.
- **Fail-safe** (luật ở [AGENTS.md](../../AGENTS.md) mục 1, bảng nguyên nhân ở spec 3.4). Khi viết code:
  - tính `cap_distance` và `cap_ttc` riêng, mỗi năng lực theo đúng dòng của bảng; không gộp thành một cờ "dữ liệu hỏng" dùng chung;
  - giá trị không dùng được thì để `null` kèm `status` và lý do, không lặng lẽ thay bằng giá trị mặc định;
  - khi sửa code năng lực, test phải có ca năng lực này tắt mà năng lực kia vẫn chạy, ví dụ tốc độ `lost` mà Khẩn cấp vẫn phát khi đủ guardrail.

## 6. Kho cấu hình trong test và thử nghiệm

| | Kho thật | Kho tạm |
|---|---|---|
| Là gì | Thư mục `configs/` trên máy demo, mà các lần chạy dùng cho báo cáo và nghiệm thu | Thư mục tạm: `tmp_path` của pytest, hoặc một thư mục nháp ngoài repo |
| Danh tính | Tên thật trong `roles.json` (WP-P2) | Tên giả, ví dụ `po`, `lead`, `eng` như test hiện có |
| Được làm gì | Chỉ con người có tên trong `roles.json` chạy `approve`, `activate`, `rollback` | Được chạy trọn vòng HITL, kể cả cho crash giữa chừng, như `test_configstore.py` và `test_cli.py` |

- Test và script không bao giờ trỏ `--root` hay `config_root` vào kho thật.
- `configs/` không bao giờ được commit (`.gitignore`).

## 7. Dependency

- **Ưu tiên cái đã có:** thư viện chuẩn, các dependency đang dùng (`numpy`, `opencv-python`, `onnxruntime`, `pydantic`, `pyyaml`), các hàm sẵn có:
  - trong `contracts/base.py`: `read_record`, `check_stream`, `canonical_json`, `sha256_hex`, `normalize`;
  - trong test: `factories.py`, `decision_harness.py`.
- **Thêm dependency mới** chỉ khi có lý do cụ thể. PR phải nêu lý do và phương án đã cân nhắc. Gói mới phải chạy offline trên CPU với Python 3.11, được ghi vào file dependency của RoadWatch (WP-C1), và được PO đồng ý.

## 8. Lệnh kiểm tra

Lấy từ `Makefile`, `.github/workflows/ci.yml` và cấu trúc test hiện có:

```bash
ruff check src/ tests/                                     # Makefile "lint", CI
ruff check src/roadwatch tests/roadwatch                   # chỉ phần RoadWatch
python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q
pytest tests/ -v                                           # Makefile "test", CI
git diff --check                                           # khoảng trắng thừa, dấu xung đột
```

- **Chạy riêng test RoadWatch.** `--confcutdir` ngăn pytest nạp `tests/conftest.py` của template, vốn cần `pytest-asyncio` và app mẫu.
- **Chạy cả repo.** `pytest tests/` cần cả dependency của template (`requirements.txt`) lẫn của RoadWatch. CI hiện chỉ cài `requirements.txt`, nên phần RoadWatch sẽ lỗi trên CI cho tới khi WP-C1 xong.
- **`make check` không phải lệnh chỉ kiểm tra:** nó chạy cả `ruff format` và ghi đè file.
- **Test đỏ có chủ đích và kết quả chạy gần nhất** được ghi ở [docs/plan/README.md](../plan/README.md), mục 3.

## 9. Thay đổi schema, fixture và nơi sử dụng

- **Quy tắc phiên bản** (spec 4.6):
  - đổi ngữ nghĩa là MAJOR, kể cả khi giữ nguyên tên và kiểu;
  - thêm trường tuỳ chọn, mặc định `null`, là MINOR;
  - chỉ sửa mô tả là PATCH.
  - Ý nghĩa của trường viết ở `Field(description=…)`.
- **Một PR phải gồm đủ:** model, test, fixture (cả loại hợp lệ và loại sai hợp đồng), spec mục 4, **và mọi nơi sử dụng**. Tìm nơi sử dụng bằng `grep -rw <TênModel> src/roadwatch tests/roadwatch`.
- **Fixture** (từ 30/09, WP-C3) nằm ở `tests/roadwatch/fixtures/`:
  - `valid/replay`, `valid/live`: sinh lại bằng `python -m tests.roadwatch.make_fixtures runs`;
  - `scenarios/<ca>/` (từ 01/10, WP-B9): nhật ký đầu vào hợp lệ mô tả một tình huống lỗi của spec 6.2, kèm `scenario.json`. Sinh lại bằng `python -m tests.roadwatch.make_fixtures scenarios`, không sửa tay; hành vi mong đợi của B nằm trong `tests/roadwatch/test_decision.py`, không nằm trong fixture;
  - `invalid/<ca>/`: sửa tay, mỗi thư mục một lỗi, kèm `expect.txt` ghi lý do mong đợi.
  - `python -m tests.roadwatch.make_fixtures` không kèm tham số sinh lại cả `valid/` lẫn `scenarios/`.

  Mọi luồng được `check_streams` (`contracts/streams.py`) kiểm, dùng chung cho test fixture và lệnh `check-run` của CLI.
- **Sau khi đóng băng v1.0:** mọi thay đổi phải có change request và PO duyệt.

Nơi ghi và nơi đọc hiện tại (29/09):

| Schema | Ghi ở | Đọc ở |
|---|---|---|
| `FrameMeta` | `source.py`, `runtime.py` | `runtime.py`, `evaluate.py` |
| `SpeedSample` | `source.py` | `decision/join.py`, `runtime.py`, `live.py`, `rerun.py` |
| `Measurement` | `perception.py` | `decision/`, `runtime.py`, `rerun.py`, `evaluate.py` |
| `DecisionInput` | `runtime.py` (nhật ký), `decision/stage.py` | `rerun.py`, `evaluate.py` |
| `DecisionTrace`, `AlertDecision`, `AudioPlan` | `decision/` | `runtime.py`, `live.py`, `evaluate.py` |
| `AudioEvent` | `runtime.py` (dùng ở live) | `evaluate.py` |
| `SystemEvent` | `runtime.py`, `live.py` | `decision/capability.py`, `rerun.py` |
| `RunManifest` | `runtime.py` | `rerun.py`, `evaluate.py`, `cli.py` (`hitl report`, `check-run`) |
| `SessionManifest`, `EventLabel` | Dữ liệu của R-D | `source.py`, `runtime.py`, `evaluate.py`, `cli.py` (`run`, `eval`), `scripts/roadwatch/sweep_b.py` |
| `RwConfig`, `Approval`, `ActivePointer` | `configstore.py` | `configread.py`, `runtime.py`, `live.py`, `perception.py`, `decision/`, `rerun.py`, `scripts/roadwatch/` (`sweep_b.py`, `render_phrases.py`) |

## 10. Test theo hành vi và rủi ro

- **Tên test mô tả hành vi**, ví dụ `test_emergency_is_not_blocked_by_distance_confirmation_or_cooldown`. Tên hoặc docstring nêu luật nào trong spec mà test bảo vệ.
- **Ba loại bằng chứng:**

| Loại | Là gì | Chạy ở đâu |
|---|---|---|
| Fixture / unit test | Hàm thuần với fixture hoặc dữ liệu tổng hợp (`factories.py`, `decision_harness.py`, `tests/roadwatch/fixtures/`) | pytest, CI |
| Integration test | Nhiều thành phần chạy cùng nhau: replay trên video tổng hợp với detector giả; vòng CLI hay HITL trong kho tạm | pytest, CI |
| Dữ liệu thực địa | Clip và GPS thực địa; các lần chạy trên máy demo | Theo mục "Kiểm chứng" của task. Không chạy trên CI; dữ liệu không commit |

- **Mỗi AC-\* dùng đúng loại bằng chứng mà spec mục 7 ghi cho nó**, ở cột "Cách kiểm chứng": không thiếu, và không thêm điều kiện ngoài spec. Ví dụ: AC-M2 chỉ cần bộ pytest của `contracts`; AC-M9 cần kịch bản CLI cùng pytest; AC-M5, AC-M6 cần dữ liệu thực địa; AC-M7 cần cả pytest lẫn biên bản kiểm tra live. Muốn đổi loại bằng chứng của một AC thì đề xuất sửa spec, không tự đặt ở đây hay trong task.
- **Test qua chưa phải là nghiệm thu.** Kể cả khi AC chỉ cần pytest, AC đó chỉ đạt khi reviewer đã kiểm theo mục "Kiểm chứng" của task.
- **Độ sâu theo rủi ro:**
  - **Luật an toàn và tính đúng**: guardrail (3.7), fail-safe (3.4), HITL (3.10), luật `null` không phải 0, tái lập (5.4). Cần test kịch bản hoặc test thuộc tính. Khi đổi logic của các luật này, thử cố ý làm hỏng luật để chắc test bắt được, rồi khôi phục.
  - **Logic thường**: TDD như bình thường.
  - **Thay đổi tài liệu hoặc sửa nhỏ không đổi hành vi**: không cần thử làm hỏng luật.
- **Không nới lỏng assert của test sẵn có để cho qua.** Nếu kỳ vọng của test sai thì sửa test, ghi lý do trong PR, và reviewer phải đồng ý.

## 11. Branch, PR, review

- **Nhánh tích hợp** do PO chốt ([review-v1.1.md](../plan/review-v1.1.md), mục 5). Kiểm tra trạng thái thực tế trên remote mỗi phiên; không suy ra từ mô tả lịch sử trong tài liệu. Quy trình dưới đây dùng `origin/main`; nếu PO chỉ định nhánh tích hợp khác thì thay đúng tên đã xác nhận.
- **Đầu mỗi phiên và trước khi tiếp tục code sau khi có cập nhật từ nhóm:**
  1. Chạy `git status --short --branch`, `git branch --show-current` và `git remote -v` để biết nhánh, remote và việc đang dở. Chạy `git fetch origin`; lệnh này tải commit và cập nhật remote-tracking refs, chưa đổi file làm việc. Nếu fetch thất bại, báo chưa xác minh được bản mới nhất; dừng triển khai phụ thuộc tài liệu đó, trừ khi người dùng cho phép làm offline rõ ràng.
  2. Xem `git log --oneline HEAD..origin/main` và `git diff --stat HEAD...origin/main`; đọc diff mới của `AGENTS.md`, quy tắc, requirements, spec, plan, checklist và code liên quan task. Khi cần đọc bản mới trước khi tích hợp, dùng `git show origin/main:<đường-dẫn>`. Chỉ lấy nội dung đã merge vào nhánh tích hợp và đã được duyệt theo quy định làm căn cứ; PR còn mở là đề xuất.
  3. Nếu working tree sạch: task mới tạo nhánh từ `origin/main`; task đang làm tích hợp `origin/main` vào nhánh task bằng merge (fast-forward khi có thể). Không rebase nhánh đã chia sẻ. Nếu có thay đổi chưa commit, không tự stash, commit hộ hoặc ghi đè; báo file đang dở và xin cách xử lý khi chúng cản trở đồng bộ. Có thể dùng worktree riêng từ `origin/main` cho task độc lập, nhưng không coi đó là đã đồng bộ nhánh cũ. Nếu xung đột chưa rõ ý định hai phía, dừng để hỏi tác giả trước khi tiếp tục triển khai.
  4. Sau đồng bộ, đọc lại quy tắc và nguồn chuẩn liên quan task, kiểm phụ thuộc và báo ngắn: nhánh đang làm, SHA của `origin/main` đã kiểm tra, thay đổi ảnh hưởng task, đã tích hợp hay còn vướng. Không chỉ đọc bản remote rồi tiếp tục code trên nền cũ khi thay đổi liên quan chưa được tích hợp.
- **Push chỉ lên nhánh làm việc.** Trước mỗi push, kiểm tra lại nhánh hiện tại và đích push. Không push trực tiếp vào `main`, `master` hoặc nhánh tích hợp khác, kể cả dùng refspec `HEAD:main`; không dùng `--all`, `--mirror`, force-push hay bỏ hook bằng `--no-verify`. Dùng đích tường minh `git push -u origin HEAD:refs/heads/<nhánh-task>` sau khi thay placeholder bằng tên nhánh đã kiểm tra. Nếu đang ở nhánh tích hợp hoặc detached HEAD thì tạo/chuyển sang nhánh task trước khi sửa và commit. Thay đổi vào nhánh tích hợp qua PR và review; agent không tự merge PR nếu người dùng chưa yêu cầu rõ.
- **Nhánh làm việc:** mỗi task một nhánh `feat/<wp>-<mô-tả>`, ví dụ `feat/wp-c2-cli`. Commit theo Conventional Commits và ghi ID task, ví dụ `feat(roadwatch): WP-C2 hitl report từ chối split test_*`. ID task là mối nối giữa code, checklist và bằng chứng; không tạo file Markdown riêng cho từng file code.
- **Tiến độ đi cùng code.** Commit hoặc PR mang code cũng mang cập nhật checklist của task (file phân việc) và dòng của task ở plan, mục 4.3. Sửa lại phần đã đánh dấu xong thì mở lại checkbox bị ảnh hưởng trong cùng PR.
- **Mô tả PR** gồm:
  - ID task;
  - thay đổi gì, theo mục nào của spec;
  - đã kiểm chứng thế nào: lệnh và kết quả;
  - giới hạn còn lại;
  - reviewer theo bảng ở plan.
- **PR template.** `.github/PULL_REQUEST_TEMPLATE.md` là mẫu của repo template: checklist của nó dùng `ruff check .` và `pytest`. Với RoadWatch thì chạy các lệnh ở mục 8.
- **Review.** Reviewer chạy đúng mục "Kiểm chứng" của task. Chỉ reviewer được đổi trạng thái sang ✅. Reviewer luôn khác owner.
- **CODEOWNERS.** `.github/CODEOWNERS` của template gán mọi đường dẫn cho nhóm maintainer của môn học. PO đã kiểm ngày 29/09: nhóm tự merge PR vào `main` được, không phải chờ họ duyệt. Không sửa file này, vì nó thuộc quyền của môn học.
- **Bảo vệ thay đổi của người khác:**
  - không force-push, rebase hay reset nhánh chung hoặc nhánh của người khác;
  - không xoá hay ghi đè file chưa commit mà bạn không tạo;
  - xem `git status` và hỏi chủ file trước khi `stash`, `checkout --` hay `reset`;
  - khi giải xung đột, giữ ý định của cả hai phía và hỏi tác giả.
- **Không bao giờ commit:** `models/`, `runs/`, `configs/`, `data/`, `.env`, video, GPS log.
