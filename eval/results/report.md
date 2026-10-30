# Evaluation Report

> Báo cáo đánh giá chất lượng sản phẩm.

---

## 1. Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Response accuracy | >80% | — | ⏳ |
| Response latency | <3s | — | ⏳ |
| User satisfaction | >4/5 | — | ⏳ |
| Test coverage | >60% | — | ⏳ |

## 2. Test Results

### Unit Tests
```
pytest tests/ -v
# Paste output here
```

### Integration Tests
```
# Mô tả test scenarios và kết quả
```

## 3. User Feedback

| User | Feedback | Rating |
|------|----------|--------|
| [User 1] | [feedback] | [1-5] |
| [User 2] | [feedback] | [1-5] |

## 4. Demo Results

- Ngày demo: [YYYY-MM-DD]
- Người tham gia: [số người]
- Feedback chung: [tóm tắt]
- Issues phát hiện: [danh sách]

## 5. Action Items

- [ ] [Cần cải thiện 1]
- [ ] [Cần cải thiện 2]

---

## 6. B so với baseline (RoadWatch, spec 5.5)

> Khung do WP-B8 soạn ngày 01/10/2026. **Chưa có số liệu nào**: mọi ô "—" chờ lần chạy `test_small` duy nhất (WP-D6). Người chịu trách nhiệm phương pháp của mục này: R-B.
>
> **Ghi chú 09/10/2026:** lệnh `eval` dưới đây thuộc engine MVP (`src/roadwatch/cli.py`), chưa có trên `main` (spec 12.4). Số liệu BT-A hiện có nằm ở [bt_a_eval.md](bt_a_eval.md).

**Cách lấy số.** Mọi số trong mục này chép nguyên từ báo cáo của lệnh dưới đây, không tính tay:

```bash
python -m src.roadwatch.cli eval runs/<run_id> runs/<run_id> --labels <nhãn>.jsonl --sessions <session>.json <session>.json --lead-max-s <s> --max-late-s <s> --tau <iou> --max-sync-uncertainty-ms <ms>
```

- τ, `lead_max`, `max_late`: giá trị PO duyệt ở OQ-A3. Mục tiêu độ bất định đồng bộ: giá trị chốt theo spec 5.1.
- Chỉ dùng lần chạy `replay` với cấu hình đã duyệt và đang active. Lần chạy có cờ `proposed_config` không được dùng.
- Nhãn ghép với lần chạy theo `clip_id` = `session_id`.

### 6.1 Số liệu gắn với phiên bản nào

| Mục | Giá trị | Trường trong báo cáo `eval` |
|---|---|---|
| Cấu hình và phê duyệt | — | `per_run[].provenance.config_sha256`, `approval_id` |
| Commit code; cây làm việc có sạch không | — | `per_run[].provenance.code_commit`, `code_dirty` |
| Model, ONNX Runtime, `contracts` | — | `per_run[].provenance.model_sha256`, `ort_version`, `contracts_version` |
| Video, GPS, session manifest (hash) | — | `per_run[].provenance.inputs` |
| File nhãn (hash) | — | `labels_sha256` |
| τ, `lead_max`, `max_late`, mục tiêu đồng bộ | — | `params` |

### 6.2 Chỉ số chính

Tính ở tầng `audio_plan`, trên các phiên đạt điều kiện của spec 5.1.

| Chỉ số | B | Baseline | Trường |
|---|---|---|---|
| Số phiên, số giờ, số sự kiện `must_alert` | — | (chung) | `main.runs`, `main.hours`, `main.events_must_alert` |
| Cảnh báo không khớp | — | — | `main.<arbiter>.unmatched` |
| Mức giảm cảnh báo không khớp so với baseline (mục tiêu đề xuất ≥ 50%, OQ-A1) | — | | `main.unmatched_reduction` |
| Recall toàn hệ thống | — | — | `main.<arbiter>.recall` |

Kết luận cho AC-M5: — (ghi "sơ bộ" nếu số sự kiện dưới ngưỡng của OQ-A1).

### 6.3 Chỉ số phụ

| Chỉ số | B | Baseline | Trường |
|---|---|---|---|
| Cảnh báo lặp | — | — | `main.<arbiter>.repeated` |
| Cảnh báo khớp lần đầu | — | — | `main.<arbiter>.first_match` |
| Cảnh báo mỗi giờ | — | — | `main.<arbiter>.alerts_per_hour` |
| Thông báo trạng thái mỗi giờ (theo từng phiên) | — | — | `per_run[].<arbiter>.status_msgs_per_hour` |
| `object_unresolved` | — | — | `main.<arbiter>.object_unresolved` |
| Cảnh báo phát trong đoạn `congestion` | — | — | `main.<arbiter>.in_congestion` |
| Lead time: n, P50, nhỏ nhất, lớn nhất (giây) | — | — | `main.<arbiter>.lead_time_s` |
| `perceived_delay` P50 và P95 theo mức (ms) | — | | `main.B.perceived_delay_ms` |
| Tầng `decision`: số lệnh nguy hiểm đã quyết | — | — | `main.<arbiter>.decided_hazards` |
| Kết cục ở bộ phân xử: `started`, `preempted`, `cancelled`, `expired` (theo từng phiên) | — | — | `per_run[].<arbiter>.plan_outcomes` |

### 6.4 Bỏ sót của B (spec 5.2)

| Loại | Số sự kiện | Trường |
|---|---|---|
| Bỏ sót khi đủ năng lực | — | `main.B.misses.missed_while_capable` |
| Bỏ sót khi suy giảm | — | `main.B.misses.missed_while_degraded` |
| Theo từng lý do suy giảm | — | `main.B.misses.degraded_reasons` |

### 6.5 Sự kiện có kết quả khác nhau giữa B và baseline

Nguồn: `per_run[].events_differ`.

| Phiên | `event_id` | B bắt được | Baseline bắt được | Nhận xét |
|---|---|---|---|---|
| — | — | — | — | — |

### 6.6 Phiên bị loại khỏi chỉ số chính, nhãn không được tính

Nguồn: `excluded[]` và `labels_without_run`.

| Phiên | Lý do bị loại | Không khớp: B, baseline | Recall: B, baseline |
|---|---|---|---|
| — | — | — | — |

Nhãn có `clip_id` không khớp lần chạy nào: —

### 6.7 Mọi lần chạy trên `test_*`

Chép **toàn bộ** các dòng của `eval/test_runs.jsonl`, kể cả lần chạy hỏng (spec 5.5).

| `run_id` | `split` | `session_id` | `mode` | `config_sha256` | `approval_id` | `error` |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |
