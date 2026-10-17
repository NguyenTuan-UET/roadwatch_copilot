# Quy tắc code RoadWatch

**Phạm vi.** Áp dụng cho `src/roadwatch/`, `tests/roadwatch/` và các script phục vụ RoadWatch.

**Nguồn chuẩn liên quan:**
- Kiến trúc và hợp đồng dữ liệu: [spec](../specs/roadwatch-architecture.md).
- Hiện trạng code trên `main` so với spec: [spec](../specs/roadwatch-architecture.md), mục 12.4.
- Quy tắc tài liệu: [docs-rules.md](docs-rules.md).
- Luật kiến trúc không được phá (ranh giới, guardrail, fail-safe): [AGENTS.md](../../AGENTS.md), mục 1. File này chỉ nói cách viết code để giữ các luật đó.

## 1. Tổ chức code hiện có

**Trên `main`** (bản core demo, từ 07/10/2026):

| Đường dẫn | Trách nhiệm | Phần |
|---|---|---|
| `src/roadwatch/model.py` | Giải mã video bằng ffmpeg về 20 Hz, warp ảnh vào khung model, đóng gói YUV, chạy `models/gr14VinAI.onnx` bằng ONNX Runtime, giữ hàng đợi trạng thái của model | BT-A |
| `src/roadwatch/calibration.py` | Học `fy`; pitch, yaw theo block; phát hiện lắp lại camera | BT-A |
| `src/roadwatch/pipeline.py` | Mỗi khung: warp → model → cập nhật hiệu chuẩn → xe dẫn đầu, khoảng cách | BT-A |
| `src/roadwatch/hud.py` | Vẽ chú thích lên khung hình | BT-A |
| `src/roadwatch/vendor/g01T014VinAI/` | Mã đi kèm (MIT); không sửa, Ruff bỏ qua | BT-A |
| `src/roadwatch/decide.py` | BT-B rút gọn cho demo (spec D-21): hàm thuần, thời gian lấy từ chỉ số khung | BT-B |
| `src/roadwatch/job.py` | Một lần chạy của server demo: video → BT-A → BT-B → video có chú thích, `decisions.json`, `run.json`, `heartbeat.json` | Demo |
| `src/roadwatch/web.py`, `schemas.py`, `openapi.json` | API FastAPI, model Pydantic của API, bản OpenAPI đã commit | Demo |
| `src/roadwatch/ui/` | Màn buồng lái ở `/` (`cockpit.html`, `cockpit.js`, `cockpit.jpg`) và web app ở `/app` (`index.html`, `app.js`, `app.css`, bản đồ 3D `scene3d.js`); file tĩnh ở `/ui/`. HTML, CSS, JS thuần, không build, không CDN | Demo |
| `src/roadwatch/web.html`, `judge.html` | Trang cũ: kỹ sư ở `/engineer`, trình diễn ở `/judge` | Demo |
| `src/roadwatch/__main__.py` | Chạy một video từ dòng lệnh, không cần server | Demo |
| `scripts/roadwatch/` | `download_model.py`, `prune_model.py`, `evaluate.py` (đánh giá BT-A), `export_api_schema.py`, `check_docs.py`, `serve_tunnel.sh` | Công cụ |
| `tests/roadwatch/` | `test_pipeline.py`, `test_decide.py`, `test_job.py`, `test_web.py` | Test |

**Engine MVP theo spec, chưa có trên `main`.** Các module dưới đây nằm ở nhánh `feat/wp-p4-contracts-v1`; hiện trạng và khác biệt với spec ở spec 12.4. Những luật trong file này nhắc tới `contracts`, `decision/`, `runtime`, `factories.py` hay fixture (một phần mục 3, các mục 4, 5, 8, 9) áp dụng khi làm việc với các module đó.

| Đường dẫn | Trách nhiệm | Phần |
|---|---|---|
| `src/roadwatch/contracts/` | Model Pydantic của mọi bản ghi và cấu hình (`base.py`, `streams.py`, `config.py`) | Gốc chung |
| `src/roadwatch/decision/` | `join`, năng lực, các đợt cảnh báo, bộ phân xử audio, `DecisionStage`; toàn bộ là hàm thuần | BT-B |
| `src/roadwatch/source.py` | Lịch khung theo PTS, bản ghi giữ chỗ, đọc GPS | Runtime |
| `src/roadwatch/runtime.py`, `live.py` | Replay tất định; live nhiều thread, supervisor, audio sink | Runtime |
| `src/roadwatch/rerun.py`, `evaluate.py` | `rerun-B`, khớp nhãn, latency | Công cụ |
| `tests/roadwatch/factories.py`, `decision_harness.py` | Hàm dựng dữ liệu và bộ chạy B dùng chung cho test | Test |

**Code mẫu của template môn học đã được gỡ khỏi repo (09/10/2026):** `src/agents/`, `src/api/`, `src/services/`, `src/models/`, `src/config.py`, `src/main.py`, `tests/test_agents/`, `tests/test_api/`, `tests/conftest.py`, `Dockerfile` ở gốc và service `backend` trong `docker-compose.yml`.

## 2. Python và Ruff

- **Python ≥ 3.11.** Căn cứ: `target-version = "py311"` trong `ruff.toml`; CI dùng 3.11. Máy bạn có thể chạy bản mới hơn, nhưng không dùng cú pháp mới hơn 3.11 (ví dụ generic kiểu `def f[T]()`).
- **Lint** theo `ruff.toml`: bật `E`, `F`, `I`, `N`, `W`, `UP`; bỏ `E501`; dài dòng tối đa 120. Chỉ dùng `# noqa` khi có mã luật kèm lý do, như code hiện có: `# noqa: BLE001 - lý do`.
- **Định dạng.** `ruff.toml` có mục `[format]`, nhưng code RoadWatch hiện có **chưa** được định dạng bằng `ruff format` (ngày 29/09: 22/30 file sẽ bị đổi).
  - Không chạy `ruff format` cho cả thư mục trong PR tính năng, vì sẽ trộn thay đổi định dạng với thay đổi logic.
  - Có định dạng toàn bộ hay không là quyết định của PO. Nếu có, làm trong một commit riêng.
- **mypy.** `Makefile` có lệnh `typecheck` (mypy), nhưng mypy không nằm trong `requirements.txt` hay CI, nên không phải điều kiện để merge.
- **Import.** Trong package dùng import tương đối (`from .model import MODEL_HZ`). Test import theo kiểu `from src.roadwatch… import …`, như các test hiện có.

## 3. Ranh giới import

| Module | Được import | Không được import |
|---|---|---|
| `model.py`, `calibration.py`, `pipeline.py`, `hud.py` (A, trên `main`) | `numpy`, `cv2`, `onnxruntime`, `vendor/g01T014VinAI`, và các module A khác | `decide`, `job`, `web`, `schemas` |
| `decide.py` (B rút gọn, trên `main`) | Thư viện chuẩn | Mọi module khác của `roadwatch`; mọi I/O và đồng hồ hệ thống |
| `job.py`, `__main__.py`, `web.py`, `schemas.py` (demo, trên `main`) | Các module ở hai dòng trên, `cv2`, `fastapi`, `pydantic` | Không module A hay B nào được import ngược lại các file này |
| `contracts/` | Thư viện chuẩn, `pydantic` | Bất kỳ module nào khác của `roadwatch` |
| `src/roadwatch/` (A) | `numpy`, `cv2`, `onnxruntime`, `src/roadwatch/vendor/g01T014VinAI` (MIT) | `decision/`, `runtime`, công cụ |
| `decision/` (B) | `contracts` và module trong `decision/` | Mọi I/O: file, mạng, đồng hồ hệ thống (`time`, `datetime.now`), số ngẫu nhiên không có seed |
| `source.py` | `contracts`, `numpy`, `cv2` | `decision/`, công cụ |
| `runtime.py`, `live.py` | `contracts`, `source`, `perception`, `decision/` | `sqlite3`, `rerun`, `evaluate`, CLI, web UI |
| `rerun.py`, `evaluate.py`, CLI (công cụ) | Mọi module ở trên | Không module runtime, A hay B nào được import ngược lại công cụ |

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
- **Báo lỗi.** Dùng exception cụ thể (`ConfigError`, `ValueError`). Thông báo phải nói file nào, bản ghi nào, trường nào, giá trị gì, sai vì sao. Khi bọc lỗi thì giữ lỗi gốc bằng `raise … from e`.
- **Không nuốt exception.**
  - Không dùng `except:` trống. Không dùng `except Exception: pass`.
  - Chỉ bắt rộng ở ranh giới thread để **ghi lại** lỗi thành sự kiện, như `guarded()` trong `live.py` ghi lỗi cho `system_fault`. Kèm chú thích lý do.
- **Fail-safe** (luật ở [AGENTS.md](../../AGENTS.md) mục 1, bảng nguyên nhân ở spec 3.4). Khi viết code:
  - tính `cap_distance` và `cap_ttc` riêng, mỗi năng lực theo đúng dòng của bảng; không gộp thành một cờ "dữ liệu hỏng" dùng chung;
  - giá trị không dùng được thì để `null` kèm `status` và lý do, không lặng lẽ thay bằng giá trị mặc định;
  - khi sửa code năng lực, test phải có ca năng lực này tắt mà năng lực kia vẫn chạy, ví dụ tốc độ `lost` mà Khẩn cấp vẫn phát khi đủ guardrail.

## 6. Dependency

- **Ưu tiên cái đã có:** thư viện chuẩn, các dependency trong `requirements.txt` (`numpy`, `opencv-python-headless`, `onnxruntime`, `pydantic`, `fastapi`), các hàm sẵn có của engine MVP (chưa có trên `main`):
  - trong `contracts/base.py`: `read_record`, `check_stream`, `canonical_json`, `sha256_hex`, `normalize`;
  - trong test: `factories.py`, `decision_harness.py`.
- **Thêm dependency mới** chỉ khi có lý do cụ thể. PR phải nêu lý do và phương án đã cân nhắc. Gói mới phải chạy offline trên CPU với Python 3.11, được ghi vào file dependency của RoadWatch, và được PO đồng ý.

## 7. Lệnh kiểm tra

Lấy từ `Makefile`, `.github/workflows/ci.yml` và cấu trúc test hiện có:

```bash
ruff check src/roadwatch tests/roadwatch scripts/roadwatch --extend-exclude src/roadwatch/vendor   # Makefile "lint", CI
python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q   # Makefile "test", CI; test model bỏ qua nếu chưa tải gr14VinAI
python -m scripts.roadwatch.export_api_schema --check      # openapi.json khớp schemas.py; CI
node --test "tests/roadwatch/js/*.test.mjs"                # bản JS chạy trên điện thoại khớp Python (dữ liệu chuẩn)
git diff --check                                           # khoảng trắng thừa, dấu xung đột
python -m scripts.roadwatch.check_docs                     # link, ID, metadata, task và phụ thuộc
```

- **Snapshot hợp đồng cho agent.** Chưa có: sinh JSON Schema khi có model Pydantic của `Measurement` 2.0.0 (spec D-10).
- **Test JS (`src/roadwatch/ui/onphone/`)** so với dữ liệu chuẩn trong `tests/roadwatch/fixtures/onphone/`, do `python -m scripts.roadwatch.export_onphone_golden` xuất từ chính code Python (cần model và comma2k19 đoạn 3). Sửa logic Python mà bản JS chép lại (pipeline, calibration, temporal, decide, hud, model) thì xuất lại dữ liệu và sửa bản JS cho khớp. Chưa nằm trong CI.
- **`check_docs` không nằm trong CI** và chưa có test riêng trên `main`: chạy tay trước khi mở PR.
- **`--confcutdir`** có từ khi repo còn `tests/conftest.py` của template. File đó đã gỡ ngày 09/10/2026 nên cờ này không còn tác dụng; giữ lại để lệnh khớp `Makefile` và CI.
- **Dependency và CI hiện hành (09/10/2026, theo yêu cầu người dùng).** `requirements.txt` là file dependency duy nhất của RoadWatch. Hai workflow `ci.yml` và `roadwatch.yml` chỉ kiểm sản phẩm; pytest dùng `--confcutdir=tests/roadwatch`. Code và test của ứng dụng template đã gỡ khỏi repo cùng ngày.
- **`make check` không phải lệnh chỉ kiểm tra:** nó chạy cả `ruff format` và ghi đè file.

## 8. Thay đổi schema, fixture và nơi sử dụng

- **API của server demo** (trên `main`): nguồn chuẩn là `src/roadwatch/schemas.py`, phiên bản ở `API_VERSION`; quy tắc tăng phiên bản ghi ở đầu [roadwatch-api.md](../specs/roadwatch-api.md). Đổi model thì trong cùng PR: chạy `python -m scripts.roadwatch.export_api_schema` để sinh lại `src/roadwatch/openapi.json`, cập nhật bản sao `docs/specs/schemas/roadwatch-api.openapi.json` (script không sinh file này) và sửa `roadwatch-api.md`.
- **Quy tắc phiên bản** (spec 4.6):
  - đổi ngữ nghĩa là MAJOR, kể cả khi giữ nguyên tên và kiểu;
  - thêm trường tuỳ chọn, mặc định `null`, là MINOR;
  - chỉ sửa mô tả là PATCH.
  - Ý nghĩa của trường viết ở `Field(description=…)`.
  - Số phiên bản nằm ở một chỗ: `CONTRACTS_VERSION` trong `contracts/base.py` (1.0.0 từ 01/10, WP-P4; 1.1.0 từ 02/10). Đổi MAJOR thì sinh lại fixture `valid/` và `scenarios/`, sửa `schema_version` trong các fixture `invalid/`, rồi sinh lại snapshot schema (mục 7).
- **Một PR phải gồm đủ:** model, test, fixture (cả loại hợp lệ và loại sai hợp đồng), spec mục 4, **và mọi nơi sử dụng**. Tìm nơi sử dụng bằng `grep -rw <TênModel> src/roadwatch tests/roadwatch`.
- **Fixture** (từ 30/09) nằm ở `tests/roadwatch/fixtures/`:
  - `valid/replay`, `valid/live`: sinh lại bằng `python -m tests.roadwatch.make_fixtures runs`;
  - `scenarios/<ca>/` (từ 01/10, WP-B9): nhật ký đầu vào hợp lệ mô tả một tình huống lỗi của spec 6.2, kèm `scenario.json`. Sinh lại bằng `python -m tests.roadwatch.make_fixtures scenarios`, không sửa tay; hành vi mong đợi của B nằm trong `tests/roadwatch/test_decision.py`, không nằm trong fixture;
  - `invalid/<ca>/`: sửa tay, mỗi thư mục một lỗi, kèm `expect.txt` ghi lý do mong đợi.
  - `handoff/` (từ 02/10, WP-P8): phiên mẫu tổng hợp cho `run --measurements`, gồm `measurements.jsonl` (xe dẫn đầu, đối tượng khác, làn), `gps.csv`, `session.json`, `dataset.json` và `test-config.yaml` (cấu hình đầy đủ cho test). Sinh lại bằng `python -m tests.roadwatch.make_fixtures handoff`, không sửa tay. Riêng `measurements-mvp-1.0.0.jsonl` là file viết ở 1.0.0, giữ nguyên để kiểm tương thích: không sinh lại.
  - `python -m tests.roadwatch.make_fixtures` không kèm tham số sinh lại `valid/`, `scenarios/` và `handoff/`.

  Mọi luồng được `check_streams` (`contracts/streams.py`) kiểm, dùng chung cho test fixture và lệnh `check-run` của CLI.
- **Sau khi đóng băng v1.0:** mọi thay đổi phải có change request và PO duyệt.
- JSON Schema được sinh từ Pydantic, không sửa tay. Đối chiếu literal, kiểu, `required` và khả năng nhận `null` với spec mục 4; các validator nghiệp vụ và bất biến liên luồng cần test riêng. Khi code chưa khớp spec, ghi rõ D-x ở spec mục 12.3 thay vì đổi spec theo snapshot một cách tự động.

Nơi ghi và nơi đọc của engine MVP (29/09; chưa có trên `main`):

| Schema | Ghi ở | Đọc ở |
|---|---|---|
| `FrameMeta` | `source.py`, `runtime.py` | `runtime.py`, `evaluate.py` |
| `SpeedSample` | `source.py` | `decision/join.py`, `runtime.py`, `live.py`, `rerun.py` |
| `Measurement` | `src/roadwatch/` | `decision/`, `runtime.py`, `rerun.py`, `evaluate.py` |
| `DecisionInput` | `runtime.py` (nhật ký), `decision/stage.py` | `rerun.py`, `evaluate.py` |
| `DecisionTrace`, `AlertDecision`, `AudioPlan` | `decision/` | `runtime.py`, `live.py`, `evaluate.py` |
| `AudioEvent` | `runtime.py` (dùng ở live) | `evaluate.py` |
| `SystemEvent` | `runtime.py`, `live.py` | `decision/capability.py`, `rerun.py` |
| `RunManifest` | `runtime.py` | `rerun.py`, `evaluate.py`, `cli.py` (`check-run`) |
| `SessionManifest`, `EventLabel` | Dữ liệu của R-D | `source.py`, `runtime.py`, `evaluate.py`, `cli.py` (`run`, `eval`), `scripts/roadwatch/sweep_b.py` |
| `RwConfig` | `contracts/config.py` | `runtime.py`, `live.py`, `decision/`, `rerun.py`, `scripts/roadwatch/` (`sweep_b.py`, `render_phrases.py`) |

## 9. Test theo hành vi và rủi ro

- **Tên test mô tả hành vi**, ví dụ `test_emergency_is_not_blocked_by_distance_confirmation_or_cooldown`. Tên hoặc docstring nêu luật nào trong spec mà test bảo vệ.
- **Ba loại bằng chứng:**

| Loại | Là gì | Chạy ở đâu |
|---|---|---|
| Fixture / unit test | Hàm thuần với fixture hoặc dữ liệu tổng hợp (`factories.py`, `decision_harness.py`, `tests/roadwatch/fixtures/`) | pytest, CI |
| Integration test | Nhiều thành phần chạy cùng nhau: replay trên video tổng hợp với detector giả | pytest, CI |
| Dữ liệu thực địa | Clip và GPS thực địa; các lần chạy trên máy demo | Theo spec mục 5 và 7. Không chạy trên CI; dữ liệu không commit |

- **Mỗi AC-\* dùng đúng loại bằng chứng mà spec mục 7 ghi cho nó**, ở cột "Cách kiểm chứng": không thiếu, và không thêm điều kiện ngoài spec. Ví dụ: AC-M2 chỉ cần bộ pytest của `contracts`; AC-M5, AC-M6 cần dữ liệu thực địa; AC-M7 cần cả pytest lẫn biên bản kiểm tra live. Muốn đổi loại bằng chứng của một AC thì đề xuất sửa spec, không tự đặt ở đây hay trong task.
- **Test qua chưa phải là nghiệm thu.** Kể cả khi AC chỉ cần pytest, AC đó chỉ đạt khi reviewer đã kiểm theo cột "Cách kiểm chứng" của spec mục 7.
- **Độ sâu theo rủi ro:**
  - **Luật an toàn và tính đúng**: guardrail (3.7), fail-safe (3.4), luật `null` không phải 0, tái lập (5.4). Cần test kịch bản hoặc test thuộc tính. Khi đổi logic của các luật này, thử cố ý làm hỏng luật để chắc test bắt được, rồi khôi phục.
  - **Logic thường**: TDD như bình thường.
  - **Thay đổi tài liệu hoặc sửa nhỏ không đổi hành vi**: không cần thử làm hỏng luật.
- **Không nới lỏng assert của test sẵn có để cho qua.** Nếu kỳ vọng của test sai thì sửa test, ghi lý do trong PR, và reviewer phải đồng ý.

## 10. Branch, PR, review

- **Nhánh tích hợp** do PO chốt. Kiểm tra trạng thái thực tế trên remote mỗi phiên; không suy ra từ mô tả lịch sử trong tài liệu. Quy trình dưới đây dùng `origin/main`; nếu PO chỉ định nhánh tích hợp khác thì thay đúng tên đã xác nhận.
- **Đầu mỗi phiên và trước khi tiếp tục code sau khi có cập nhật từ nhóm:**
  1. Chạy `git status --short --branch`, `git branch --show-current` và `git remote -v` để biết nhánh, remote và việc đang dở. Chạy `git fetch origin`; lệnh này tải commit và cập nhật remote-tracking refs, chưa đổi file làm việc. Nếu fetch thất bại, báo chưa xác minh được bản mới nhất; dừng triển khai phụ thuộc tài liệu đó, trừ khi người dùng cho phép làm offline rõ ràng.
  2. Xem `git log --oneline HEAD..origin/main` và `git diff --stat HEAD...origin/main`; đọc diff mới của `AGENTS.md`, quy tắc, requirements, spec và code liên quan task. Khi cần đọc bản mới trước khi tích hợp, dùng `git show origin/main:<đường-dẫn>`. Chỉ lấy nội dung đã merge vào nhánh tích hợp và đã được duyệt theo quy định làm căn cứ; PR còn mở là đề xuất.
  3. Nếu working tree sạch: task mới tạo nhánh từ `origin/main`; task đang làm tích hợp `origin/main` vào nhánh task bằng merge (fast-forward khi có thể). Không rebase nhánh đã chia sẻ. Nếu có thay đổi chưa commit, không tự stash, commit hộ hoặc ghi đè; báo file đang dở và xin cách xử lý khi chúng cản trở đồng bộ. Có thể dùng worktree riêng từ `origin/main` cho task độc lập, nhưng không coi đó là đã đồng bộ nhánh cũ. Nếu xung đột chưa rõ ý định hai phía, dừng để hỏi tác giả trước khi tiếp tục triển khai.
  4. Sau đồng bộ, đọc lại quy tắc và nguồn chuẩn liên quan task, kiểm phụ thuộc và báo ngắn: nhánh đang làm, SHA của `origin/main` đã kiểm tra, thay đổi ảnh hưởng task, đã tích hợp hay còn vướng. Không chỉ đọc bản remote rồi tiếp tục code trên nền cũ khi thay đổi liên quan chưa được tích hợp.
- **Push chỉ lên nhánh làm việc.** Trước mỗi push, kiểm tra lại nhánh hiện tại và đích push. Không push trực tiếp vào `main`, `master` hoặc nhánh tích hợp khác, kể cả dùng refspec `HEAD:main`; không dùng `--all`, `--mirror`, force-push hay bỏ hook bằng `--no-verify`. Dùng đích tường minh `git push -u origin HEAD:refs/heads/<nhánh-task>` sau khi thay placeholder bằng tên nhánh đã kiểm tra. Nếu đang ở nhánh tích hợp hoặc detached HEAD thì tạo/chuyển sang nhánh task trước khi sửa và commit. Thay đổi vào nhánh tích hợp qua PR và review; agent không tự merge PR nếu người dùng chưa yêu cầu rõ.
- **Nhánh làm việc:** mỗi task một nhánh `feat/<wp>-<mô-tả>`, ví dụ `feat/wp-b9-scenarios`. Commit theo Conventional Commits và ghi ID task, ví dụ `feat(roadwatch): WP-B9 thêm kịch bản lỗi`. ID task là mối nối giữa code và bằng chứng; không tạo file Markdown riêng cho từng file code.
- **Mô tả PR** gồm:
  - ID task;
  - thay đổi gì, theo mục nào của spec;
  - đã kiểm chứng thế nào: lệnh và kết quả;
  - giới hạn còn lại;
  - reviewer (khác người viết).
- **PR template.** `.github/PULL_REQUEST_TEMPLATE.md` là mẫu của repo template: checklist của nó dùng `ruff check .` và `pytest`. Với RoadWatch thì chạy các lệnh ở mục 7.
- **Review.** Reviewer chạy lại các lệnh kiểm tra ở mục 7, và kiểm theo spec mục 7 khi PR liên quan một AC. Reviewer luôn khác người viết.
- **CODEOWNERS.** `.github/CODEOWNERS` của template gán mọi đường dẫn cho nhóm maintainer của môn học. PO đã kiểm ngày 29/09: nhóm tự merge PR vào `main` được, không phải chờ họ duyệt. Không sửa file này, vì nó thuộc quyền của môn học.
- **Bảo vệ thay đổi của người khác:**
  - không force-push, rebase hay reset nhánh chung hoặc nhánh của người khác;
  - không xoá hay ghi đè file chưa commit mà bạn không tạo;
  - xem `git status` và hỏi chủ file trước khi `stash`, `checkout --` hay `reset`;
  - khi giải xung đột, giữ ý định của cả hai phía và hỏi tác giả.
- **Không bao giờ commit:** `models/`, `runs/`, `configs/`, `data/`, `.env`, video, GPS log.
