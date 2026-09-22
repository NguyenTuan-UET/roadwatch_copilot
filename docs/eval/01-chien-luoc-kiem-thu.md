# Chiến Lược Kiểm Thử & Quản Trị Tập Dữ Liệu (Test Strategy)
> Nguồn: Tách từ protocol.md (Mục 0, 1, 2, 3, 5, 8) tuân thủ SDLC Bước QD: Quality Definition.
> Độ dài chuẩn: 150 - 250 dòng.

# Giao thức đánh giá precision — phát hiện vượt đèn đỏ (TrafficEye Edge)

> **Trạng thái:** ĐÃ DUYỆT · v1.0 · 21/09/2026 — PO đã chốt 3 quyết định (mục 11).
> **Phạm vi:** mục 1–12 dành cho vi phạm vượt đèn đỏ. **Mục 13 (phụ lục, chờ duyệt cùng spec v1.0)** mở rộng giao thức cho đi ngược chiều, sai làn, mAP, đếm theo làn, hàng chờ và ùn tắc, OCR, hiệu năng. Chưa có code hệ thống. Script đánh giá `scripts/evaluate.py` và test `tests/test_evaluate.py` chưa được viết (TASK-019 của plan M1, Khánh, hạn 27/09).
> **Quy ước:** **[Kiểm chứng]** = nhận định có nguồn ở mục 12. **[Đề xuất]** = thiết kế hoặc suy luận của team, cần xác nhận bằng dữ liệu. Mọi con số về cỡ mẫu ở mục 7.2 là **tính bằng công thức**, không phải số đo.

---

## 0. Tóm tắt 1 trang

**Vấn đề.** Nếu các ngưỡng (ân hạn, T_c vào vùng giao lộ, số khung xác nhận, ngưỡng tin cậy) được chỉnh trên chính video dùng để đo, precision sẽ bị thổi phồng.
- Dùng sai số kiểm định chéo của một mô hình đã được chỉnh bằng kiểm định chéo cho ra ước lượng lệch đáng kể [Kiểm chứng: Varma & Simon 2006].
- Dùng đi dùng lại một tập holdout để ra quyết định cũng làm nó mất giá trị [Kiểm chứng: Dwork et al. 2015].

**Cách làm, 5 bước:**
1. **Chia theo nhóm, không chia theo khung.** Đơn vị chia là video, phiên quay và địa điểm. Tập test quay mới, **khác nút giao hoặc khác điều kiện**, giống cách UA-DETRAC (train và test ở địa điểm khác nhau) và WILDS (test trên camera chưa từng thấy) [Kiểm chứng].
2. **Chỉnh ngưỡng bằng leave-one-video-out** trên tập tuning/val (đã chốt). Không bao giờ đo trên dữ liệu đã dùng để chỉnh [Kiểm chứng: Varma & Simon 2006; scikit-learn].
3. **Đóng băng** cấu hình (file config + SHA-256 + git tag) vào **11/10/2026** [Đề xuất].
4. **Quay tập test mới sau khi đóng băng.** Hai người gán nhãn độc lập, không xem kết quả hệ thống; nhãn được khóa bằng mã băm trước khi chạy.
5. **Chạy test một lần.** Báo precision kèm khoảng tin cậy Wilson 95% [Kiểm chứng: Brown, Cai & DasGupta 2001], kèm mã băm của config và manifest.

**Con số cần biết (tính toán, không phải số đo):**
- 20 cảnh báo đúng hết thì cận dưới khoảng tin cậy 95% của precision vẫn chỉ là 83,9%.
- Cần ≥ 29 cảnh báo không sai cái nào mới khẳng định được precision ≥ 90%, và ≥ 59 cảnh báo để khẳng định ≥ 95% (một phía, 95%) [Kiểm chứng: quy tắc 3/n, Hanley & Lippman-Hand 1983].
- **Mục tiêu: ≥ 60 cảnh báo trên tập test. Dưới 30 thì con số chỉ mang tính minh họa** [Đề xuất].

**Câu trả lời 30 giây cho giám khảo:** mục 10.1. **Ba quyết định đã chốt:** mục 11.

---

## 1. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Phiên quay (session) | Một đoạn quay liên tục tại một nút giao, một camera, một khung giờ. Là đơn vị nhỏ nhất khi chia dữ liệu |
| Cảnh báo (alert) | Một vi phạm mà hệ thống gửi sang bước duyệt của người |
| Sự kiện thật (GT event) | Một lần mép trước của xe qua vạch dừng, do người gán nhãn xác định |
| Tập phát triển (dev) | Gộp tuning và validation, được chia lại bằng kiểm định chéo theo phiên |
| Custodian | Người giữ tập test, không tham gia chỉnh ngưỡng |
| Mã lý do | A1…E5 trong `docs/spec/false-positives.md` |

---

## 2. Chia dữ liệu

### 2.1 Vì sao không chia theo khung
Các khung liền kề gần như giống hệt nhau. Nếu chia ngẫu nhiên theo khung, cùng một xe và cùng một pha đèn sẽ xuất hiện ở cả tập chỉnh lẫn tập đo.
- Đây là dạng rò rỉ do dữ liệu train và test không độc lập, nằm trong phân loại rò rỉ của Kapoor & Narayanan [Kiểm chứng].
- Các kỹ sư perception ô tô cũng nêu đúng những dạng này: rò rỉ giữa các khung video liên tiếp, khung trùng lặp, và trùng địa điểm giữa các tập [Kiểm chứng: Babu et al. 2026].

### 2.2 Phân cấp nhóm
`tuyến ⊃ nút giao ⊃ camera/hướng ⊃ phiên quay ⊃ file ⊃ clip`

- Mọi thứ thuộc cùng một phiên luôn nằm cùng một tập.
- Tập test phải khác **điều kiện hoặc ngày quay** với tập phát triển (đã chốt), theo cách làm của UA-DETRAC và WILDS [Kiểm chứng].
- **MVP có 1 tuyến gồm 3 nút giao liên tiếp** (đã chốt Q7 ngày 21/09; 3 camera quay cùng lúc theo FR-MC-1).
- Ba camera phải đồng bộ thời gian: đầu mỗi buổi quay, 3 camera cùng quay màn hình đồng hồ chuẩn (`time.is`), và manifest ghi giờ bắt đầu với sai số ± 1 giây.

### 2.3 Sơ đồ chia cho tuyến 3 nút giao

| Tập | Nguồn | Dùng để | Lịch quay | Ai được xem |
|---|---|---|---|---|
| Phát triển (dev) | Tuyến 3 nút giao MVP (3 camera quay cùng lúc), ít nhất 4 phiên quay ở các ngày và khung giờ khác nhau (có giờ cao điểm); bao phủ đủ các pha đèn và nhiều tình huống | Chỉnh ngưỡng vi phạm và ngưỡng phân tích tuyến bằng leave-one-video-out | Trước 30/09 | Cả team |
| Test dự phòng (sealed) | Cùng tuyến 3 nút, một ngày quay riêng ở tuần 2, custodian niêm phong | Thay test chính nếu lịch trượt; gộp vào test chính nếu thiếu cảnh báo và chưa bị mở | 03/10 | Custodian và 2 người gán nhãn |
| Test chính (prospective) | Cùng tuyến 3 nút, quay **sau** khi đóng băng 11/10; ưu tiên phiên có điều kiện khác (tối hoặc mưa) | Báo cáo, chạy một lần | Chiều 14/10 (sau demo CP1) | Như trên |

Mỗi phiên quay chỉ thuộc về một tập. Không cắt cùng một buổi quay ra cho cả tập phát triển và tập test [Đề xuất].

### 2.4 Chỉnh ngưỡng bằng kiểm định chéo theo nhóm
**Đã chốt:** leave-one-video-out trên tuning/val, với nhóm = video. Phần dưới giải thích biến thể lồng nhau và so sánh các cách chia.

- Vòng ngoài giữ lại một phiên để **đo**.
- Vòng trong chạy leave-one-session-out trên các phiên còn lại để **chọn** ngưỡng.
- Kết quả vòng ngoài ước lượng hiệu năng của **cả quy trình chỉnh**, và gần như không bị lệch [Kiểm chứng: Varma & Simon 2006].
- Công cụ: `LeaveOneGroupOut` hoặc `GroupKFold` của scikit-learn, với nhóm = phiên [Kiểm chứng].

| Cách chia | Ưu điểm | Nhược điểm | Khi nào dùng |
|---|---|---|---|
| 3 tập cố định (tuning / val / test) | Đơn giản, dễ giải thích | Mỗi tập rất nhỏ; kết quả phụ thuộc vào cách chia | Khi có nhiều phiên ở nhiều nút |
| Group k-fold lồng nhau | Dùng hết dữ liệu | Ít nhóm thì các fold lệch nhau; khó giải thích hơn | Khi số phiên đủ lớn để chia k phần cân bằng |
| **Leave-one-out theo nhóm** | Dùng hết dữ liệu; thấy được phương sai giữa các nhóm | Tốn tính toán hơn; mỗi nhóm là một điểm đo nhiều nhiễu | **Khi có ít nhóm — team chốt biến thể theo video** |

Chi phí tính toán gần như không đáng kể nếu **cache** đầu ra detection, tracking và trạng thái đèn cho từng video. Khi đó mỗi lần thử ngưỡng chỉ cần chạy lại lớp quy tắc [Đề xuất].

**Thứ tự bắt buộc: chốt model trước, chỉnh ngưỡng sau** (thêm 22/09):
- Ngưỡng được chọn trên box, lớp và độ liền mạch của track do **một** model sinh ra. Đổi trọng số thì các thứ đó đổi theo. Bộ ngưỡng cũ không còn là bộ tốt nhất, và số dev cũ không còn đúng.
- Vì vậy, khi đổi trọng số (kể cả sau khi tinh chỉnh theo FR-DET-1): xóa cache, chạy lại pipeline trên mọi video dev, rồi chỉnh lại **toàn bộ** ngưỡng. Không được giữ ngưỡng cũ cho model mới.
- Chuỗi "đo cổng → train → chạy lại cache → chỉnh ngưỡng → đóng băng" phải đi tuần tự; thêm người không rút ngắn được chuỗi này.
- Nếu dữ liệu tinh chỉnh lấy khung từ phiên dev thì số leave-one-video-out trên dev sẽ **lạc quan hơn thực tế**, vì detector đã thấy các video đó. Báo cáo phải ghi rõ điều này. Tập test quay sau đóng băng không bị ảnh hưởng, và kiểm trùng ở mục 2.5 vẫn áp dụng cho dữ liệu tinh chỉnh.

Kết quả leave-one-video-out là con số của **tập phát triển**, không thay thế tập test. Đem nó so với kết quả test sẽ thấy độ lệch miền.

### 2.5 Kiểm tra trùng lặp
1. **Trùng file:** tính SHA-256 mọi file video của dev, test và dữ liệu public đã dùng để huấn luyện hoặc tinh chỉnh detector. File trùng thì loại khỏi test.
2. **Gần trùng:** trích 1 khung/giây, tính pHash bằng thư viện `imagehash` (hỗ trợ ahash, phash, dhash, whash) rồi so khoảng cách Hamming [Kiểm chứng]. Không có ngưỡng Hamming chuẩn, nên chọn bằng thử trên dữ liệu của team [Đề xuất]. Cặp nghi trùng thì cho người xem lại.
3. **Diễn giải đúng:** hai phiên khác ngày tại cùng một nút có nền rất giống nhau nên pHash gần nhau; đó **không phải** rò rỉ. Bước 2 chỉ nhằm bắt các clip bị cắt từ cùng một đoạn quay nhưng nằm ở hai tập khác nhau. Vì MVP chỉ có 1 nút giao, pHash giữa các phiên sẽ luôn gần nhau. Ranh giới thật giữa các tập là **phiên quay** (ngày, khung giờ), và phiên quay được ghi trong manifest [Đề xuất].

### 2.6 Chuẩn hóa video (đã duyệt sau design review, H-02)
- Kiểm tra từng video bằng ffprobe, rồi chuyển về 15 FPS cố định (`ffmpeg -fps_mode cfr -r 15`) trước khi gán nhãn.
- Gán nhãn và chạy hệ thống trên **cùng một file**: `video_sha256` trong file nhãn phải trùng SHA-256 trong manifest. Script sẽ kiểm tra điều này (L-01).
- Khi đánh giá, pipeline đọc thẳng file nên không rơi khung. FPS xử lý nằm trong config đóng băng.

---

## 3. Đóng băng và chống dùng nhầm tập test

### 3.1 Đăng ký trước, trước ngày đóng băng [Đề xuất]
Commit một file `eval/preregistration.md` gồm:
- quy tắc khớp cảnh báo với sự kiện (mục 4.3);
- quy ước trùng lặp và ca mơ hồ (mục 4.4, 4.5);
- chỉ số chính và phương pháp khoảng tin cậy;
- danh sách ngưỡng được quét cùng phạm vi quét (mục 7.6);
- các nhóm điều kiện sẽ báo riêng;
- cỡ mẫu mục tiêu;
- nút và điều kiện của tập test.

### 3.2 Đóng băng
- `configs/frozen/rl-v1.yaml` chứa mọi ngưỡng, phiên bản model và cấu hình từng nút (vạch dừng, vùng giao lộ, ROI đèn, ánh xạ đèn với làn, FPS xử lý).
- Ghi SHA-256 của file config và của trọng số model.
- Gắn tag git `eval-freeze-v1` cho commit đó.

### 3.3 Cơ chế kỹ thuật: nhiều lớp, chi phí thấp [Đề xuất]

| Lớp | Cơ chế | Chặn được gì |
|---|---|---|
| Con người | Custodian giữ video test ngoài repo, có hai bản sao mã hóa ở hai nơi (M-07); người chỉnh ngưỡng không có bản sao | Nhìn trộm tập test; mất tập test |
| Script chỉnh ngưỡng | `tune` chỉ đọc `eval/manifests/dev.csv`, và từ chối mọi file có SHA-256 nằm trong `eval/manifests/test.csv` | Chép nhầm file test vào dev |
| Script đánh giá (`scripts/evaluate.py`, chưa viết: TASK-019) | Mỗi lần chạy ghi một dòng vào `eval/logs/test_runs.jsonl`: người chạy, thời gian, mã băm của config, manifest, nhãn, file cảnh báo và của chính script. Nếu cùng tập test đã từng chạy bằng config khác thì status là `burned`, kèm cảnh báo. Việc so mã băm config với mã băm lúc gắn tag làm bằng tay hoặc bằng CI | Chạy lén; chỉnh ngưỡng trên test mà không ai biết |
| CI (GitHub Actions) | Báo lỗi nếu nhãn test đổi sau tag khóa nhãn, nếu config đóng băng bị sửa, hoặc nếu `test_runs.jsonl` bị xóa dòng | Sửa lịch sử |
| Báo cáo | Ghi mã băm của config, manifest test, file nhãn, tag, và số lần chạy test | Giám khảo tự kiểm tra được |

Căn cứ:
- MOTChallenge không công bố nhãn test và giới hạn tối đa 4 lần nộp cho mỗi tracker, mỗi lần cách nhau 72 giờ, để ngăn việc chỉnh tham số trên test [Kiểm chứng].
- Các kỹ sư perception ô tô xem kiểm soát rò rỉ là bài toán phối hợp giữa các vai trò, nên cần phân vai rõ ràng [Kiểm chứng: Babu et al. 2026].

Bộ cơ chế này cũng cho giám khảo thấy quy trình làm việc trên GitHub, tức tiêu chí Kỹ thuật.

**Chạy lại bằng đúng config đã đóng băng** (ví dụ khi demo) không làm "cháy" tập test, vì kết quả phải giống hệt. Chỉ có việc **đổi** config sau khi đã xem kết quả mới làm cháy tập test.

### 3.4 Khi tập test "cháy"
Nếu phải đổi bất kỳ ngưỡng nào sau khi đã xem kết quả test:
1. Ghi "test-v1 đã cháy" vào báo cáo, kèm lý do, và giữ nguyên kết quả cũ.
2. Quay tập test-v2 mới rồi lặp lại mục 3.1–3.3.
3. Không báo con số của test-v1 sau khi chỉnh như thể đó là kết quả sạch [Kiểm chứng: Dwork et al. 2015 về rủi ro dùng lại holdout].

---



## 5. Gán nhãn

### 5.1 Nguyên tắc
- Người gán nhãn **không xem kết quả hệ thống**.
- **Tập test:** hai người gán nhãn độc lập toàn bộ [Đã chốt].
- **Tập dev:** một người gán; người thứ hai gán ngẫu nhiên 30% để tính kappa (H-07). Ở clip thử, đo số phút công cho mỗi phút video để chốt số giờ video cần quay.
- Nhãn test phải được khóa (commit + mã băm + tag `labels-lock-test-v1`) **trước** khi chạy hệ thống trên test.
- Người thứ ba (custodian) phân xử các bất đồng và ghi lại lý do.
- Hướng dẫn gán nhãn dựa trên `docs/spec/false-positives.md`: mỗi nhãn `non_violation` hoặc `ambiguous` phải kèm mã lý do A1…E5.

### 5.2 Hai bước gán nhãn
1. **Dòng thời gian đèn (làm tay):** với mỗi hướng, đánh dấu khung chuyển xanh→vàng, vàng→đỏ, đỏ→xanh, cùng các đoạn đèn nhấp nháy, tắt hoặc bị che. Hai người làm độc lập; nếu lệch nhau quá 2 khung thì đưa ra phân xử [Đề xuất].
2. **Sự kiện qua vạch:** chỉ cần xem từ lúc đèn vàng bật tới hết pha đỏ, nhờ vậy giảm khối lượng. Với mỗi xe có mép trước qua vạch dừng, ghi: khung qua vạch, bbox, làn, loại xe, nhãn, mã lý do.

### 5.3 Đo độ đồng thuận
- Lập danh sách **hợp** các lần qua vạch mà ít nhất một người đã đánh dấu. Mỗi người gán nhãn **toàn bộ** danh sách này (lượt hai cho những ca mình chưa đánh dấu), không xem nhãn của người kia.
- Tính Cohen's kappa trên 3 nhãn, kèm bảng bất đồng. Thang diễn giải gốc của Cohen có thể quá dễ dãi với các ứng dụng có hậu quả lớn [Kiểm chứng: McHugh 2012].
- Ngưỡng để đi tiếp: κ ≥ 0,8 trên clip gán nhãn thử. Nếu thấp hơn thì sửa hướng dẫn và gán lại [Đề xuất].

### 5.4 Khi người gán nhãn bỏ sót vi phạm thật
Sau khi chạy test, một người xem lại các FP (bước này không thể giấu kết quả cảnh báo). Nếu một FP hóa ra là vi phạm thật bị sót:
- **không** sửa số chính;
- báo thêm một con số "sau phân xử", kèm số nhãn đã bị đổi [Đề xuất].

Nhờ vậy số chính luôn nghiêng về phía thận trọng.

---

## 6. Tách nguồn lỗi theo thành phần

| Thành phần | Cách đo | Chỉ số |
|---|---|---|
| (a) Trạng thái đèn | So dòng thời gian đèn của hệ thống với nhãn làm tay | Độ chính xác theo khung; sai số mốc chuyển pha (ms); số lần mốc chuyển đỏ lệch nhiều hơn khoảng ân hạn |
| (b) Phát hiện và tracking | Xem từng FP và FN; kiểm tra track có liền mạch từ vùng tiếp cận tới vùng giao lộ không | Tỉ lệ sự kiện thật được một track liền mạch bao phủ; số FP do đổi ID; số FP do bị che |
| (c) Logic quy tắc | Chạy lại lớp quy tắc bằng **trạng thái đèn thật** (oracle) thay cho trạng thái của hệ thống | FP biến mất → lỗi do đèn. FP còn lại → lỗi do tracking hoặc do quy tắc; phân biệt tiếp bằng mã lý do |

- Mỗi FP được gán đúng một nguyên nhân chính theo mã lý do. Phân tích lỗi theo loại giúp biết nên sửa chỗ nào, giống cách Hoiem et al. phân tích lỗi của detector [Kiểm chứng].
- Chạy oracle cho đèn là [Đề xuất]. Cách này rẻ vì nhãn đèn đã có sẵn từ bước 5.2.

---



## 8. Cấu trúc thư mục đề xuất

```text
data/eval/                      # KHÔNG commit (.gitignore đã có data/)
  dev/<session_id>/<video_id>.mp4
  test/<session_id>/<video_id>.mp4   # bản gốc chỉ custodian giữ
configs/
  frozen/rl-v1.yaml             # config đóng băng; mã băm ghi trong báo cáo
eval/
  preregistration.md            # đăng ký trước (mục 3.1)
  manifests/
    dev.csv                     # bắt buộc: video_id, camera_id, fps, duration_s; thêm: sha256, location, condition
    test.csv                    # tạo khi quay xong test
  splits/
    lovo_folds.json             # các fold leave-one-video-out
  labels/
    dev/<video_id>.json         # dòng thời gian đèn + sự kiện qua vạch
    test/<video_id>.json        # khóa bằng tag labels-lock-test-v1
  cache/                        # KHÔNG commit: đầu ra detection/tracking/đèn
  logs/
    test_runs.jsonl             # scripts/evaluate.py ghi mỗi lần chạy test (dev_runs.jsonl cho dev); chỉ ghi thêm
  results/
    report.md                   # deliverable #10 (khung có sẵn từ template khóa học)
    test-v1/                    # metrics.json, fp_list.csv, pr_curve.png
docs/
  eval/protocol.md              # file này
  eval/report-template.md
  spec/false-positives.md       # mã lý do A1…E5
```

Khung một file nhãn: mỗi video một file; bbox tính bằng pixel theo dạng [x1, y1, x2, y2]; `light_phases` dùng cho phân tích lỗi, script đánh giá không đọc phần này.

```json
{
  "video_id": "C-2026-10-14-sang-01",
  "video_sha256": "<sha256>",
  "annotator": "<mã người gán nhãn>",
  "light_phases": [
    {"approach": "N", "head": "N-chinh", "state": "RED", "start_frame": 0, "end_frame": 0}
  ],
  "crossings": [
    {"id": "c001", "approach": "N", "lane": 2, "frame": 0, "bbox": [0, 0, 0, 0],
     "class": "motorbike", "label": "violation", "reason_code": null, "note": ""}
  ]
}
```

---

