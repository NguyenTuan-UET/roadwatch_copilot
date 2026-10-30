---
doc_id: "RW-PLAN-WARNING"
doc_type: "archive"
status: "archived"
authority_for: []
---

# Kế hoạch code: nhắc giữ khoảng cách (BT-B, không dùng TTC) — đã hoàn thành

Kế hoạch chốt để code lại `src/roadwatch/decide.py` và bản chép trên điện thoại `src/roadwatch/ui/onphone/decide.mjs`. Mọi con số dưới đây là **giá trị thử nghiệm**, chưa phải cấu hình an toàn đã xác nhận; mỗi số được đặt tên hằng ở đầu file code để chỉnh sau khi thử.

## Trạng thái: hoàn thành (18/10/2026, người dùng xác nhận)

- Bước 1–7 ở mục 6 đã làm: `decide.py` và `onphone/decide.mjs` viết lại theo mục 3–4 (`test_decide.py` 14 test; `decide.test.mjs` so 2.400 khung với Python); nối vào `job.py`, `engine.mjs`, API 2.0.0 (mức `chime`), giao diện và `sw.js`; `make_alert_sounds.py` tạo `chime.wav`, `emergency.wav`; `config/proposals/v0.yaml` mục `warning`; spec 3.4–3.7 viết lại và được người dùng duyệt ngày 17/10/2026.
- Âm đang dùng: `info` "Xe phía trước đang gần lại", `warning` "Chú ý giữ khoảng cách xe phía trước" (giọng thu sẵn), `chime` và `emergency` tạo bằng script. Thu lại câu ngắn hơn ("Giãn khoảng cách", "Quá gần") thuộc lộ trình ở README.
- Tài liệu này giữ làm lịch sử thiết kế; luật có hiệu lực nằm ở spec 3.4–3.7 và README mục 3.

**Định vị sản phẩm:** "Nhắc giãn khoảng cách từ sớm, âm báo ngắn khi cần chú ý nhanh, và điều chỉnh nhắc lại theo diễn biến thực tế." Đánh giá bằng số lần báo sai, số lần nhắc lặp và mức báo trước, không hứa dự báo va chạm.

## 0. Các nguồn đã sửa cho khớp

Kế hoạch này bỏ cảnh báo Khẩn cấp theo TTC. Các nguồn dưới đây đã được sửa cho khớp:

| Nguồn | Trước đây | Sau khi sửa |
|---|---|---|
| `AGENTS.md` mục 1, điều 5 | Có guardrail Khẩn cấp theo TTC | Không dùng TTC để quyết định cảnh báo |
| Spec 3.4–3.7 (`docs/specs/roadwatch-architecture.md`) | Emergency theo TTC, ân hạn xe chen, tắt nhắc dưới 60 km/h | Viết lại theo kế hoạch này; người dùng duyệt 17/10/2026 |
| `config/proposals/v0.yaml` mục `ttc`, `dispatch` | Tham số TTC, `cooldown_ms` 10 s | Thay bằng mục `warning` |
| Câu "Sắp xảy ra va chạm" (`decide.py`, `decide.mjs`, `schemas.py`, UI) | Câu của mức `emergency` | Bỏ: `emergency` là 3 tiếng bíp |

Pipeline (BT-A) vẫn tính `ttc_s` để hiển thị và ghi log; chỉ có BT-B không dùng nữa.

## 1. Nguyên tắc không được phá

1. Không nói "sắp va chạm" hay còn bao nhiêu giây. Chỉ báo tình trạng khoảng cách và diễn biến đáng lo.
2. Chỉ xét **xe dẫn đầu đúng đường đi** (đầu ra `lead` của model, `gap_m` từ pipeline), không phải mọi xe trong ảnh.
3. Không tạo đợt mới khi mất dấu ngắn hoặc đổi xe dẫn đầu.
4. Không dùng số đo cũ: khung không có `gap_m` mới trong `max_measurement_age_ms` (500 ms) coi như không có số đo.
5. Không có ân hạn im lặng cố định cho xe vừa xuất hiện ở gần (bỏ `GRACE_S` 4 s hiện có).
6. Xe mình giảm tốc không có nghĩa là đã an toàn: chỉ xét khoảng cách và xu hướng khoảng cách.
7. Không tuyên bố hỗ trợ lúc bò sát khi chưa kiểm chứng khả năng đo ở cự ly gần.
8. Không thấy xe không có nghĩa phía trước trống; tiếng chuông ở tốc độ cao chỉ có nghĩa "chú ý giữ khoảng cách".

## 2. Các mức và âm thanh

Giữ ba tên mức đang có (`info`, `warning`, `emergency`) để không phải đổi UI, CSS, bộ đếm và API. Thêm một mức `chime`. Nghĩa và âm thanh đổi như sau:

| Mức (`say`) | Khi nào | Âm thanh | Độ dài | File |
|---|---|---|---|---|
| `chime` | Trên 100 km/h, vừa xác nhận xe dẫn đầu (nhắc phòng ngừa) | Một tiếng chuông nhẹ "ding" (tần số khoảng 880 Hz, tắt dần) | khoảng 0,3 s | `chime.wav` (tạo bằng script) |
| `info` | Vào vùng nhắc sớm, còn dư khoảng cách | Giọng: "Giãn khoảng cách" | khoảng 0,8 s | `info.wav` (thu lại giọng) |
| `warning` | Dưới khoảng cách cơ sở | Hai tiếng bíp vừa, rồi giọng: "Quá gần" | khoảng 1,0 s | `warning.wav` (bíp ghép giọng) |
| `emergency` | Thiếu nhiều, hoặc khoảng cách giảm nhanh, ở mọi tốc độ | Ba tiếng bíp nhanh, cao, không lời | khoảng 0,45 s | `emergency.wav` (tạo bằng script) |

Quy tắc phát:
- Mức cao hơn **cắt** âm đang phát (ví dụ `emergency` cắt `info` đang đọc dở). Mức thấp hơn không cắt mức cao hơn.
- Nhắc lại dùng đúng âm của mức hiện tại.
- Rút ngắn câu thay vì đọc nhanh hơn.
- Âm bíp và chuông tạo bằng script Python dùng thư viện chuẩn (`wave`, `math`): không cần thu âm, nhẹ, chạy offline. Vẫn đi qua `/api/phrases/{kind}` và `<audio>` như hiện tại, nên `phone.js` không cần code phát âm mới.

## 3. Ngưỡng theo dải tốc độ

Ký hiệu:
- `v`: tốc độ xe mình (m/s);
- `d`: khoảng cách theo Thông tư 38 (bảng `LEGAL` hiện có);
- `gap`: khoảng cách cản trước tới xe dẫn đầu.

| Dải | Nhắc sớm (`info`) | Cảnh báo (`warning`) | Thiếu nhiều (`emergency`) |
|---|---|---|---|
| Đứng yên, `v < 5 km/h` | không phát | không phát | không phát |
| Bò chậm, 5–20 km/h | giai đoạn 1: không phát (xem mục 8) | không phát | không phát |
| 20–60 km/h | `gap < v × 3 s` | `gap < v × 2 s` | `gap < 0,5 × ngưỡng warning`, hoặc giảm nhanh |
| 60–100 km/h | `gap < d × 1,15 + v × 0,3 s` | `gap < d` | như trên |
| Trên 100 km/h | `chime` khi xác nhận xe dẫn đầu | `gap < v × 2 s` | như trên |

Ví dụ:

| Tốc độ | Nhắc sớm | Cảnh báo | Thiếu nhiều |
|---|---|---|---|
| 50 km/h | 42 m | 28 m | 14 m |
| 80 km/h | 70 m | 55 m | 27,5 m |
| 100 km/h | 89 m | 70 m | 35 m |
| 110 km/h | `chime` | 61 m | 30,5 m |

Ghi chú:
- **Hệ số 1,15 (vùng đệm 15 %)** lấy từ đánh giá thực địa: 83 % số khung lệch ≤ 15 % so với radar (`eval/README.md`). Đây là vùng đệm tạm, **không** phải độ chắc chắn của từng phép đo.
- **`v × 0,3 s`** bù độ trễ xử lý và phát âm, theo mục tiêu P95 < 300 ms.
- **Luật chung cho tốc độ cao:** nếu ngưỡng nhắc sớm tính ra vượt `MAX_RANGE_M = 100` (giới hạn đo của model), dùng `chime` khi xác nhận xe thay cho `info`. Ở trên 100 km/h, `d = 100` nên luôn rơi vào trường hợp này.
- **Cặp 3 s / 2 s cho dải dưới 60 km/h** là đề xuất thiết kế cần kiểm chứng. Mốc 2 s tham khảo hướng dẫn giữ khoảng cách (Highway Code); đây không phải quy định Việt Nam, cũng không bảo đảm dừng kịp.
- **Giảm nhanh:** độ dốc khoảng cách (trung bình trượt hàm mũ như `slope` hiện có) ≤ −5 m/s giữ liên tục 0,5 s, khi `gap` đang dưới ngưỡng nhắc sớm. Đây là xu hướng khoảng cách, không phải TTC, và không đọc ra cho người lái.

## 4. Luồng một đợt nhắc

Mỗi đợt là một xe dẫn đầu đang ở trong vùng nhắc. Trạng thái cần giữ: mức hiện tại, mức đã phát cao nhất, thời điểm phát gần nhất, số lần đã nhắc ở mức hiện tại.

1. **Xác nhận xe dẫn đầu:** có `gap` liên tục `T_LEAD_OK = 0,5 s` (status không `unreliable`). Trên 100 km/h thì phát `chime` một lần cho đợt.
2. **Vào vùng:** điều kiện của một mức giữ liên tục `T_CONFIRM = 0,5 s` (`emergency`: 0,2 s) thì phát mức đó **một lần**.
3. **Lên mức:** phát ngay khi mức cao hơn được xác nhận (bước 2); không bị chặn vì vừa phát câu khác.
4. **Nhắc lần hai:** sau `REPEAT_FIRST = 3 s` vẫn ở cùng mức và **chưa cải thiện** (độ dốc ≤ +0,5 m/s) thì nhắc lại một lần.
5. **Các lần sau:** cách nhau `REPEAT_NEXT = 10 s`, chỉ khi vẫn chưa cải thiện. Đây là giá trị thử, cần thử với người dùng để cân bằng giữa nhắc thói quen bám gần và gây phiền.
6. **Đang phục hồi** (độ dốc > +0,5 m/s): không nhắc lặp, vẫn theo dõi. Xuống mức thì không phát gì, UI vẫn hiện mức hiện tại.
7. **Xấu đi** (lên mức, hoặc giảm nhanh): báo ngay, không chờ đủ 3 s.
8. **Kết thúc đợt:**
   - `gap ≥ ngưỡng nhắc sớm + 3 m` liên tục `T_CLEAR = 3 s`; một khung nhảy lên không kết thúc đợt;
   - hoặc mất xe dẫn đầu quá `T_LOST = 3 s`.
9. **Mất dấu ngắn** (≤ `T_LOST`) rồi thấy lại, kể cả khi khoảng cách nhảy (đổi xe): **cùng đợt**, không phát lại `chime` hay `info`. Nếu thấy lại mà đã ở mức cao hơn thì áp dụng bước 3.
10. **Xe mới xuất hiện đã rất gần:** không có ân hạn. Qua bước 1 và 2 là phát ngay mức tương ứng, kể cả `emergency` ở 50 km/h.
11. **Đứng yên:** không phát gì mới. Đợt vẫn giữ nguyên, để lúc xe chạy lại không phát lại từ đầu.

Chưa hiệu chuẩn camera (`calibrated = False`): không phát gì, giữ như hiện tại.

## 5. Thay đổi giao diện code

`Decider.step` bỏ tham số TTC:

```python
def step(self, t, gap, ego_mps, calibrated, ok=True) -> Decision
```

`Decision` giữ các trường hiện có (`level`, `say`, `reason`, `threshold_m`, `raw`). Thêm `episode: bool` nếu UI cần biết đang trong đợt. `threshold_m` là ngưỡng `warning` của tốc độ hiện tại, hoặc `None` khi đứng yên hay bò chậm. Câu `reason` phải giống hệt nhau giữa Python và JS, vì test JS so từng khung với dữ liệu chuẩn.

## 6. Việc cần làm, theo thứ tự

Mỗi bước code theo TDD (code-rules): viết test trước.

**Bước 1: `src/roadwatch/decide.py` và `tests/roadwatch/test_decide.py`.** Viết lại theo mục 3–4, xóa nhánh TTC, `GRACE_S`, `CUT_IN_DROP_M` và luật "dưới 60 km/h tắt nhắc". Test cần có:
- [x] Ngưỡng ở 50, 80, 100, 110 km/h khớp bảng ví dụ mục 3.
- [x] Đứng yên sát xe trước: không phát gì trong 60 s.
- [x] 50 km/h, khoảng cách giảm dần từ 60 m: phát `info` rồi `warning` rồi `emergency`; mỗi mức một lần khi mới vào.
- [x] 50 km/h, xe xuất hiện ở 10 m: `emergency` trong vòng 0,5 s (chỉ thời gian xác nhận xe `T_LEAD_OK`), không có ân hạn.
- [x] 110 km/h, xe xuất hiện ở 95 m: đúng một `chime`. Mất dấu 1 s rồi thấy lại: không có `chime` thứ hai. Mất 5 s: đợt mới, có `chime`.
- [x] Bám gần không cải thiện: nhắc lần hai sau 3 s, rồi cách nhau 10 s. Đang phục hồi: không nhắc lặp.
- [x] Giảm nhanh (−6 m/s) khi đang ở `info`: lên `emergency` ngay, không chờ 3 s.
- [x] Một khung nhảy lên trên ngưỡng giữa đợt: đợt không kết thúc, không phát lại khi quay xuống.
- [x] Không phụ thuộc tốc độ khung: chạy ở 12 khung/s và 20 khung/s cho cùng thời điểm phát (sai lệch < 0,2 s), giống test `test_info_does_not_depend_on_the_frame_rate` hiện có.
- [x] Chưa hiệu chuẩn: không phát gì.

**Bước 2: bản JS cho điện thoại.**
- Chép logic sang `src/roadwatch/ui/onphone/decide.mjs`.
- Sửa kịch bản `decide_seq` trong `scripts/roadwatch/export_onphone_golden.py` để chạm đủ các luật ở bước 1, rồi xuất lại `tests/roadwatch/fixtures/onphone/decide.json`.
- Sửa lời gọi `dec.step(...)` trong `tests/roadwatch/js/decide.test.mjs` theo chữ ký mới.

**Bước 3: nối vào luồng chạy.**
- `src/roadwatch/job.py:302` và `src/roadwatch/ui/onphone/engine.mjs:189`: đổi lời gọi `step` (bỏ `ttc_s`).
- Thêm `chime` vào bộ đếm `said`.

**Bước 4: âm thanh.**
- Script mới `scripts/roadwatch/make_alert_sounds.py`, chỉ dùng thư viện chuẩn: tạo `chime.wav`, `emergency.wav` (3 bíp) và phần bíp của `warning.wav` vào `models/phrases-demo/`.
- Thu giọng "Giãn khoảng cách" (`info.wav`) và "Quá gần" (ghép sau 2 bíp thành `warning.wav`).
- `.gitignore`: thêm `!models/phrases-demo/chime.wav`.
- `src/roadwatch/ui/sw.js`: thêm `/api/phrases/chime` vào `SHELL` và tăng tên cache (`roadwatch-shell-v2`) để máy đã cài nhận âm mới.

**Bước 5: API và giao diện.**
- `src/roadwatch/schemas.py`: thêm `chime` vào `Level`, sửa mô tả các mức (bỏ "Sắp xảy ra va chạm").
- Chạy `python -m scripts.roadwatch.export_api_schema`, chép sang `docs/specs/schemas/roadwatch-api.openapi.json` và sửa `docs/specs/roadwatch-api.md`.
- Sửa `PHRASES` trong `decide.py` và `decide.mjs`:
  - `chime`: "(chuông)"
  - `info`: "Giãn khoảng cách"
  - `warning`: "Quá gần"
  - `emergency`: "(bíp khẩn)"
- Rà chữ "va chạm" và TTC trong UI: `judge.html`, `web.html`, `ui/app.js`, `ui/phone.js`, `ui/index.html`.

**Bước 6: cấu hình và tài liệu.**
- `config/proposals/v0.yaml`:
  - bỏ mục `ttc`;
  - thay `dispatch` bằng các tham số ở mục 3–4 (`t_lead_ok_ms`, `t_confirm_ms`, `repeat_first_ms`, `repeat_next_ms`, `t_clear_ms`, `t_lost_ms`, `close_fast_mps`, `notice_buffer_frac`, `latency_s`, `max_range_m`);
  - tất cả các tham số này vào `provisional_keys`.
- Sửa các nguồn ở mục 0. Thêm dòng vào `docs/worklog.md`.

**Bước 7: kiểm chứng.**
- `pytest tests/roadwatch`, `node --test tests/roadwatch/js`, `ruff`, `export_api_schema --check`, `check_docs` (lệnh ở code-rules mục 7).
- Chạy lại các video có sẵn (Chạy video) và một lượt trên iPhone. Đếm cho từng video:
  - số lần phát theo mức;
  - số lần nhắc lặp mỗi phút;
  - số lần phát khi không có xe dẫn đầu thật (báo sai);
  - thời điểm phát đầu tiên so với lúc khoảng cách xuống dưới `d` (mức báo trước).

## 7. Tham số thử nghiệm (đặt thành hằng ở đầu `decide.py`)

| Hằng | Giá trị | Ý nghĩa |
|---|---|---|
| `V_STOP_KMH` | 5 | dưới mức này coi là đứng yên |
| `V_CRAWL_KMH` | 20 | 5–20 km/h là bò chậm |
| `NOTICE_S`, `WARN_S` | 3,0; 2,0 | khoảng thời gian dùng cho dải 20–60 km/h và cho `warning` trên 100 km/h |
| `SHORT_FRAC` | 0,5 | "thiếu nhiều" = dưới nửa ngưỡng `warning` |
| `BUFFER_FRAC` | 0,15 | vùng đệm nhắc sớm cho dải 60–100 km/h |
| `LATENCY_S` | 0,3 | bù độ trễ |
| `MAX_RANGE_M` | 100 | giới hạn đo; vượt thì dùng `chime` |
| `T_LEAD_OK`, `T_CONFIRM`, `T_CONFIRM_E` | 0,5; 0,5; 0,2 s | xác nhận xe, xác nhận mức |
| `REPEAT_FIRST`, `REPEAT_NEXT` | 3; 10 s | nhắc lần hai, các lần sau |
| `IMPROVE_MPS`, `CLOSE_FAST_MPS` | +0,5; −5 m/s | đang phục hồi; giảm nhanh |
| `T_CLEAR`, `CLEAR_HYST_M`, `T_LOST` | 3 s; 3 m; 3 s | kết thúc đợt; mất dấu |

## 8. Để sau (chưa làm trong lần này)

- **Bò chậm, 5–20 km/h:** cần một khoảng cách tối thiểu riêng, nhưng chưa có bằng chứng về độ chính xác khi đo ở cự ly gần. Cần đo trước (so radar ở dưới 15 m), rồi mới bật quy tắc "vẫn nhắc nếu tiếp tục tiến sát". Tới lúc đó không quảng cáo tính năng này.
- **Vùng đệm theo sai số từng dải khoảng cách:** thay hệ số 15 % chung bằng bảng sai số theo dải (0–20, 20–40, … m) từ `eval/`, khi có đủ khung trong mỗi dải.
- **Nhịp nhắc sau lần hai:** chốt bằng thử nghiệm với người lái.
