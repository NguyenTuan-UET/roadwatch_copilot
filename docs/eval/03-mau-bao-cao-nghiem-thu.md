# Báo cáo đánh giá — Hệ thống TrafficEye Edge

> Mẫu theo `docs/eval/protocol.md`. Điền xong thì dán vào hoặc liên kết từ `eval/results/report.md` (deliverable #10).
> Mọi ô `<...>` phải được điền bằng số đo thật. Không có số thì ghi "chưa đo", không ước lượng.

## 0. Thông tin lần chạy

| Trường | Giá trị |
|---|---|
| Ngày chạy | `<YYYY-MM-DD HH:MM>` |
| Người chạy | `<tên>` |
| Tag đóng băng / commit | `eval-freeze-v1` / `<commit>` |
| SHA-256 config vi phạm | `<sha256 của configs/frozen/rl-v1.yaml>` |
| SHA-256 config tuyến | `<sha256 của configs/frozen/corridor-v1.yaml>` |
| SHA-256 trọng số model | `<sha256>` |
| SHA-256 manifest test | `<sha256>` |
| SHA-256 file nhãn test / tag khóa nhãn | `<sha256>` / `labels-lock-test-v1` |
| Commit đăng ký trước | `<commit của eval/preregistration.md>` |
| Video | 15 FPS cố định; 3 camera đồng bộ giờ time.is (± 1s); `video_sha256` trong nhãn khớp manifest: có / không |
| Tuyến đánh giá | `<corridor_id, gồm 3 camera: cam-01, cam-02, cam-03>` |
| Loại vi phạm được đánh giá | `<red_light, wrong_way, lane_class, lane_solid_line, lane_exit>` (chỉ các luật đã đóng băng trước 11/10) |
| Cửa sổ ghép theo loại (đăng ký trước) | `<RL 1,0 s; WW 3,0 s; LN 2,0 s; ...>` |
| Lần chạy test thứ / status trong log | `<1>` / fresh · rerun_same_config · burned (theo `eval/logs/test_runs.jsonl`) |
| Trạng thái tập test | Nguyên vẹn / Đã cháy — lý do: `<...>` |

## 1. Kết quả chính — vượt đèn đỏ

| Chỉ số | Giá trị | Wilson 95% | n |
|---|---|---|---|
| Precision (không gồm ca mơ hồ) | `<..>` | `<..>` | `<TP + FP>` |
| Recall | `<..>` | `<..>` | `<TP + FN>` |
| Báo nhầm / giờ / camera | `<..>` | — | `<số giờ-camera>` |

Báo riêng:
- Cảnh báo rơi vào ca mơ hồ: `<..>`. Cận xấu nhất của precision là TP / (TP + FP + số này) = `<..>`.
- Cảnh báo trùng do đổi ID, đã gộp và ghi là lỗi tracking: `<..>`.

Mức kết luận theo cỡ mẫu (đánh dấu một ô):
- [ ] n ≥ 60 — đạt mục tiêu
- [ ] 30 ≤ n < 60 — kết luận thận trọng
- [ ] n < 30 — **chỉ minh họa, không đủ để kết luận**

## 2. Dữ liệu test

| Phiên | Nút | Điều kiện | Thời lượng (giờ) | Số pha đỏ | Vi phạm thật | Mẫu âm khó (mã) | Ca mơ hồ |
|---|---|---|---|---|---|---|---|
| `<..>` | `<..>` | ngày / đêm / mưa | `<..>` | `<..>` | `<..>` | `<ví dụ C1×2, B1×5>` | `<..>` |
| **Tổng** | | | `<..>` | `<..>` | `<..>` | `<..>` | `<..>` |

Tỉ lệ vi phạm thật: `<..>` vi phạm / giờ-camera. Kiểm tra trùng lặp (SHA-256 + pHash) với dev và dữ liệu public: `<kết quả>`.

## 3. Bảng nhầm lẫn

| | Có sự kiện thật | Không có sự kiện thật |
|---|---|---|
| **Có cảnh báo** | TP = `<..>` | FP = `<..>` (có nhãn `non_violation` `<..>`, không có nhãn `<..>`) |
| **Không có cảnh báo** | FN = `<..>` | không định nghĩa (bài toán phát hiện sự kiện) |

Không nằm trong bảng: cảnh báo rơi vào ca mơ hồ `<..>`; cảnh báo trùng đã gộp `<..>`.

## 4. Precision theo điều kiện

| Nhóm | Cảnh báo | TP | FP | Precision | Wilson 95% |
|---|---|---|---|---|---|
| Ngày | | | | | |
| Đêm | | | | | |
| Mưa | | | | | |
| Nút `<..>` | | | | | |

Nhóm có ít hơn 10 cảnh báo thì chỉ ghi số đếm, không ghi phần trăm. Có thêm bảng precision theo từng phiên để thấy mức tương quan trong phiên.

## 5. Độ nhạy theo ngưỡng (chỉ mô tả)

Danh sách ngưỡng và phạm vi quét đã đăng ký trước ở commit `<..>`.

| Ngưỡng | Giá trị đóng băng | Phạm vi quét | Precision (thấp / đóng băng / cao) | Recall (thấp / đóng băng / cao) |
|---|---|---|---|---|
| Ân hạn T_g | | | | |
| Vùng giao lộ / T_c | | | | |
| Số khung xác nhận đèn N | | | | |
| Ngưỡng tin cậy detection | | | | |

Đường precision-recall: `eval/results/test-v1/pr_curve.png` (đánh dấu điểm đóng băng). **Phần này không dùng để chọn lại ngưỡng.**

## 6. Nguồn lỗi

| Nguyên nhân chính | Mã lý do | Số FP | % FP |
|---|---|---|---|
| Trạng thái đèn | D1–D6 | | |
| Phát hiện / tracking | E1, E2, E5 | | |
| Hình học / hiệu chuẩn | E3, E4 | | |
| Logic quy tắc thời điểm và vị trí | A1–A3, B1–B4 | | |
| Ngữ cảnh pháp lý chưa xử lý | C1–C4 | | |
| Không có nhãn (ngoài các đoạn đã gán nhãn) | `unlabelled` | | |

- Oracle đèn: precision khi thay trạng thái đèn của hệ thống bằng nhãn làm tay = `<..>` (so với `<..>`).
- Trạng thái đèn: độ chính xác theo khung `<..>`; sai số mốc chuyển pha trung vị / lớn nhất `<..>` / `<..>` ms; số lần mốc chuyển đỏ lệch hơn ân hạn `<..>`.
- Tracking: tỉ lệ sự kiện thật được một track liền mạch bao phủ `<..>`.

## 7. Độ tin cậy của nhãn

| Hạng mục | Cohen's kappa | Đồng thuận thô | Số ca phân xử |
|---|---|---|---|
| Dòng thời gian đèn | | | |
| Sự kiện qua vạch | | | |

Số nhãn bị đổi sau khi xem lại FP: `<..>` (không ảnh hưởng số chính). Precision sau phân xử: `<..>`.

## 8. So với tập phát triển

| | Leave-one-video-out trên dev | Test |
|---|---|---|
| Precision | | |
| Recall | | |
| Báo nhầm / giờ / camera | | |

Chênh lệch và giải thích (độ lệch miền: nút mới, đêm/mưa, mật độ xe): `<..>`

## 9. Quyền riêng tư: tỉ lệ che lọt

Soát tay mọi gói bằng chứng của tập test (protocol mục 7.1).

| Bản | Biển số + khuôn mặt cần che | Số bị lọt | Tỉ lệ lọt | Wilson 95% |
|---|---|---|---|---|
| Bản điều hành viên (che mọi xe) | | | | |
| Bản CSGT (mọi xe trừ xe vi phạm) | | | | |

Bản CSGT mà chính xe vi phạm bị che nhầm, khiến bằng chứng không dùng được: `<..>`.

## 10. Đếm xe

Đếm tay 2 đoạn, mỗi đoạn 10 phút, trên tập test (protocol mục 7.1).

| Đoạn | Loại xe / hướng | Đếm tay | Hệ thống | Sai số tuyệt đối | Sai số % |
|---|---|---|---|---|---|
| `<..>` | `<xe máy / đi thẳng>` | | | | |
| **Tổng** | | | | MAE = `<..>` | MAPE = `<..>` |

Ô có đếm tay bằng 0 thì không tính sai số %.

## 11. Các loại vi phạm khác (protocol mục 13.1)

Mỗi loại một dòng; không gộp thành một con số chung.

| Loại | Cảnh báo | TP | FP | FN | Precision | Wilson 95% | Recall | Báo nhầm / giờ / camera | Mức kết luận |
|---|---|---|---|---|---|---|---|---|---|
| Vượt đèn đỏ (chi tiết ở mục 1) | | | | | | | | | |
| Đi ngược chiều | | | | | | | | | |
| Sai làn — LN-a (theo loại xe) | | | | | | | | | |
| Sai làn — LN-b (qua vạch liền) | | | | | | | | | |
| Sai làn — LN-c (sai hướng theo mũi tên) | | | | | | | | | |
| Dừng, đỗ sai (nếu có làm) | | | | | | | | | |

**Mức kết luận:**
- n ≥ 60: đạt mục tiêu;
- 30 ≤ n < 60: kết luận thận trọng;
- n < 30: chỉ minh họa.

Nguồn lỗi theo các mã W1–W8, L1–L8, S1–S6 trình bày theo cùng khung bảng ở mục 6.

## 12. mAP (FR-EVAL-1)

| Tập khung | Số khung | mAP50 | mAP50-95 | AP50 car | AP50 motorcycle | AP50 bus | AP50 truck |
|---|---|---|---|---|---|---|---|
| Dev | | | | | | | |
| Test (gán nhãn không dùng model gợi ý) | | | | | | | |

**Theo định dạng model** (cùng bộ khung test):

| Định dạng | Kích thước (MB) | FPS đầu–cuối | Độ trễ p95 (ms) | mAP50 test | Chênh lệch so với FP32 |
|---|---|---|---|---|---|
| PyTorch FP32 | | | | | — |
| ONNX FP32 | | | | | |
| TensorRT FP16 | | | | | |
| INT8 | | | | | |

Máy chạy, driver, phiên bản thư viện: `<..>`

## 13. Hàng chờ và ùn tắc (FR-EVAL-4)

- **Hàng chờ:** `<N>` chu kỳ đèn; sai số tuyệt đối trung bình `<..>` xe.
- **Mức ùn tắc:** `<N>` phút; tỉ lệ khớp `<..>`; kappa có trọng số `<..>`.
- **Sự kiện ùn tắc:**
  - phát hiện được `<..>` / `<..>` đoạn "ùn tắc";
  - báo nhầm `<..>` trên `<..>` đoạn "thông thoáng".

## 14. Đo theo chu kỳ đèn và sự kiện tuyến (FR-EVAL-8)

### 14.1 Đo chu kỳ đèn và năng lực thoát xe

| Nút | Camera | Số chu kỳ đánh giá | Sai số trung vị chu kỳ $C$ (s) | Sai số trung vị thời gian xanh $g$ (s) | Sai số tốc độ thoát bão hòa $s$ (%) | Sai số số xe thoát mỗi chu kỳ (%) |
|---|---|---|---|---|---|---|
| Nút A | cam-01 | `<≥ 20>` | `<..>` (mục tiêu ≤ 1s) | `<..>` (mục tiêu ≤ 1s) | `<..>` (mục tiêu ≤ 15%) | `<..>` (mục tiêu ≤ 10%) |
| Nút B | cam-02 | `<≥ 20>` | `<..>` | `<..>` | `<..>` | `<..>` |
| Nút C | cam-03 | `<≥ 20>` | `<..>` | `<..>` | `<..>` | `<..>` |

### 14.2 Sự kiện chu kỳ thất bại và tràn hàng chờ

| Sự kiện | Số ca thật | Cảnh báo | TP | FP | FN | Precision | Wilson 95% | Recall | Mức kết luận |
|---|---|---|---|---|---|---|---|---|---|
| Chu kỳ thất bại (`cycle failure`) | `<≥ 30>` | | | | | | | | |
| Tràn hàng chờ (`spillback`) | `<..>` | | | | | | | | `<n ≥ 60 / 30–59 / < 30 minh họa>` |

*Ghi chú:* Độ trễ điều khiển $d = d_1 + d_2$ và mức phục vụ (LOS) A–F được tính toán theo công thức Highway Capacity Manual (HCM 2010/2016) kết hợp hệ số PCU TCVN 13592:2022 Bảng 3; không có nhãn đo thực địa trực tiếp để tính sai số.

## 15. OCR biển số (FR-EVAL-6)

| Nhóm | Số ca vi phạm đã xác nhận | Khớp hoàn toàn | Đúng theo ký tự | Chuyển người đọc |
|---|---|---|---|---|
| Biển 1 dòng | | | | |
| Biển 2 dòng (xe máy) | | | | |
| **Tổng** | | | | |

## 16. Hạn chế đã biết

- Cỡ mẫu: `<n cảnh báo, mức kết luận ở mục 1 và 11>`
- Tuyến và camera: 1 tuyến gồm 3 nút giao liên tiếp (cam-01, cam-02, cam-03).
- Điều kiện chưa thử: `<..>`
- Nguồn video: mô phỏng bằng video quay sẵn phát qua RTSP, không phải camera trực tiếp tại thiết bị edge.
- Ước tính độ trễ và LOS: theo công thức HCM, chưa đối chiếu đo đạc thực địa chuyên sâu.
- Tương quan trong phiên: khoảng tin cậy nhị thức có thể hẹp hơn thực tế.
- Nhãn: `<κ, số ca phân xử, ca mơ hồ>`

## Phụ lục

**A. Danh sách FP**

| alert_id | Phiên | Thời điểm | Mã lý do | Ghi chú | Bằng chứng (bản đã che biển số) |
|---|---|---|---|---|---|
| | | | | | |

**B. Trích `eval/logs/test_runs.jsonl`**

```text
<các dòng log của lần chạy>
```

**C. Lệnh tái lập**

```text
# Đánh giá vi phạm và đếm
python scripts/evaluate.py --split test --config configs/frozen/rl-v1.yaml

# Đánh giá chu kỳ đèn và sự kiện tuyến (FR-EVAL-8)
python scripts/evaluate_corridor.py --split test --config configs/frozen/corridor-v1.yaml
```
