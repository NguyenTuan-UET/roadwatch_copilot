# Giao Thức Đánh Giá Wilson 95% & Kiểm Định Chất Lượng
> Nguồn: Tách từ protocol.md (Mục 4, 6, 7, 10, 11, 13) tuân thủ SDLC Bước QD & Bước 7.
> Mục tiêu cốt lõi: Chứng minh Precision phát hiện vi phạm >= 95.0% với Wilson Score 95% CI.

## 4. Định nghĩa đo

### 4.1 Đơn vị đo
Một **sự kiện** = một xe, một hướng hoặc làn, một lần mép trước của xe qua vạch dừng. Không đo theo khung.

### 4.2 Hệ thống phải xuất gì cho mỗi cảnh báo
Bắt buộc, vì script đọc (định dạng JSON Lines): `alert_id, video_id, frame, bbox [x1, y1, x2, y2], confidence`. Nên có thêm: `track_id, light_state, red_onset_frame, config_hash`.

Candidate bị loại cũng được ghi lại, kèm mã lý do, để phục vụ phân tích lỗi.

### 4.3 Quy tắc khớp (đã chốt; sẽ là hằng số trong `scripts/evaluate.py`)
Một cảnh báo khớp với một sự kiện thật khi là **cùng xe trong cửa sổ thời gian cố định**:
- cùng video;
- thời điểm qua vạch lệch nhau không quá **1,0 s** (`MATCH_WINDOW_S`);
- IoU giữa bbox của cảnh báo và bbox thật, mỗi bên lấy tại khung qua vạch của mình, ≥ **0,3** (`MATCH_IOU_MIN`).

Cách ghép:
- Xét cảnh báo theo confidence giảm dần, như PASCAL VOC [Kiểm chứng].
- Mỗi cảnh báo lấy sự kiện có IoU cao nhất trong số các sự kiện thỏa điều kiện.
- Nếu sự kiện đó đã có cảnh báo thì cảnh báo mới là **trùng lặp**, không được chuyển sang sự kiện bên cạnh. Nhờ vậy một cảnh báo trùng không bao giờ biến thành TP [Đề xuất].
- Muốn đổi hai hằng số trên thì phải commit, không đổi theo từng lần chạy.
- **Kiểm tra trước khi đóng băng (M-02):** trên tập dev, xem bao nhiêu cặp đúng bị rớt ngưỡng IoU, ví dụ khi hai người gán nhãn cùng một xe. Nếu con số đáng kể, cảnh báo sẽ gửi kèm quỹ đạo ngắn và IoU được so **tại cùng một khung**. Mọi thay đổi ghi vào bản đăng ký trước.
- Cảnh báo không khớp với sự kiện nào → **FP**.
- Sự kiện thật không có cảnh báo nào khớp → **FN**.
- Bài toán phát hiện sự kiện không có TN có nghĩa. Thay vào đó dùng số báo nhầm theo giờ (mục 7.3).

### 4.4 Trùng lặp (đã chốt)
- Các cảnh báo trùng cho cùng một xe (thường do tracker đổi ID) được **gộp làm một** và ghi là **lỗi tracking**, không tính là FP.
- Quy ước này khác PASCAL VOC, nơi trùng lặp bị tính là báo nhầm [Kiểm chứng]. Vì vậy số trùng lặp (`duplicates_merged_tracking_errors`) luôn được báo ngay cạnh precision.
- Cảnh báo trùng cho một xe không có nhãn cũng được gộp theo cùng quy tắc "cùng xe".

### 4.5 Ca mơ hồ (đã chốt)
Nhãn thật có 3 giá trị: `violation`, `non_violation` (kèm mã lý do) và `ambiguous`.
- Cảnh báo rơi vào ca mơ hồ **không tính vào precision** mà được **báo riêng** (`ambiguous_alerts`). Người đọc tự tính được cận xấu nhất: TP / (TP + FP + số cảnh báo mơ hồ).
- Với recall, sự kiện mơ hồ không tính là FN.
- Mẫu âm khó (`non_violation` kèm mã A1…E5) nằm trong tập test. Cảnh báo rơi vào mẫu âm khó là FP, kèm mã lý do (`fp_by_reason`).

---



## 7. Báo cáo

### 7.1 Chỉ số chính
- **Precision = TP / (TP + FP)**, không gồm ca mơ hồ, kèm khoảng tin cậy **Wilson 95%** do script tính. Brown, Cai & DasGupta khuyến nghị Wilson khi mẫu nhỏ và nhận xét Clopper-Pearson rộng quá mức cần thiết [Kiểm chứng]. Clopper-Pearson là tùy chọn, chưa có trong script.
- Recall, kèm Wilson 95%.
- Bảng TP / FP / FN; số cảnh báo trùng; số cảnh báo rơi vào ca mơ hồ.
- **Tỉ lệ che lọt (H-04):** soát tay các gói bằng chứng của tập test, đếm biển số và khuôn mặt không được che trên bản điều hành viên và bản CSGT; báo tỉ lệ kèm Wilson 95%.
- **Độ chính xác đếm xe (M-01):** đếm tay 2 đoạn, mỗi đoạn 10 phút, trên tập test theo loại xe và hướng; báo sai số tuyệt đối và sai số phần trăm.

### 7.2 Cỡ mẫu (tính bằng công thức, không phải số đo)

| Số cảnh báo (n) | Số FP | Precision quan sát | Wilson 95% | Clopper-Pearson 95% |
|---|---|---|---|---|
| 20 | 0 | 100% | 83,9–100% | 83,2–100% |
| 20 | 1 | 95% | 76,4–99,1% | 75,1–99,9% |
| 40 | 0 | 100% | 91,2–100% | 91,2–100% |
| 40 | 2 | 95% | 83,5–98,6% | 83,1–99,4% |
| 60 | 0 | 100% | 94,0–100% | 94,0–100% |
| 60 | 3 | 95% | 86,3–98,3% | 86,1–99,0% |
| 100 | 5 | 95% | 88,8–97,8% | 88,7–98,4% |
| 200 | 10 | 95% | 91,0–97,3% | 91,0–97,6% |

- **Khi không có FP nào** trong n cảnh báo, cận dưới một phía 95% của precision là 0,05^(1/n), xấp xỉ 1 − 3/n (quy tắc 3) [Kiểm chứng: Hanley & Lippman-Hand 1983]. Cần n ≥ 29 để khẳng định precision ≥ 90%, và n ≥ 59 để khẳng định ≥ 95%.
- **Để nửa độ rộng khoảng Wilson ≤ 10 điểm %:** cần n ≥ 24 nếu precision quanh 95%, hoặc n ≥ 34 nếu quanh 90%. **Để ≤ 5 điểm %:** cần n ≥ 82, hoặc n ≥ 141.
- **Mục tiêu:** ≥ 60 cảnh báo trên tập test. **Dưới 30** thì ghi rõ "chỉ minh họa, không đủ để kết luận" [Đề xuất].
- **Số giờ video cần** ≈ n mục tiêu ÷ (số vi phạm thật mỗi giờ × recall). Tỉ lệ vi phạm mỗi giờ hiện **chưa biết**; sẽ đo bằng đếm tay trên video thử ở tuần 1. *Ví dụ giả định, không phải số đo:* nếu có 20 vi phạm/giờ và recall 0,7 thì cần khoảng 4,3 giờ video test.
- **Giới hạn:** khoảng tin cậy nhị thức giả định các cảnh báo độc lập với nhau. Cảnh báo trong cùng một phiên có tương quan, nên độ bất định thật lớn hơn. Vì vậy báo thêm precision theo từng phiên [Đề xuất].

Bảng trên được tính bằng Wilson và Clopper-Pearson chính xác, đã tự kiểm tra với giá trị đã biết (9/10). Hàm Wilson dùng cho báo cáo sẽ nằm trong `scripts/evaluate.py`; `tests/test_evaluate.py` phải kiểm lại đúng giá trị 9/10 này.

### 7.3 Chỉ số theo góc nhìn điều hành viên
**Số báo nhầm mỗi giờ mỗi camera** = FP / số giờ-camera của tập test. Chỉ số này cùng tư duy với tỉ lệ báo nhầm theo thời gian (RFA) trong đánh giá phát hiện sự kiện giám sát của TRECVID [Kiểm chứng].

### 7.4 Tỉ lệ vi phạm thật và mẫu âm khó
Precision phụ thuộc vào tỉ lệ dương tính trong dữ liệu. Với dữ liệu mất cân bằng, đường precision-recall phản ánh hiệu năng đúng hơn đường ROC [Kiểm chứng: Saito & Rehmsmeier 2015].

Báo cáo phải ghi:
- số vi phạm thật mỗi giờ trong tập test;
- số ca "trông giống vi phạm" (mẫu âm khó, theo mã A1…E5) có trong tập test.

Nên chủ động quay ở nút hoặc khung giờ có nhiều ca khó: xe ưu tiên, làn rẽ phải có biển, giờ kẹt xe [Đề xuất].

### 7.5 Precision theo điều kiện
Báo precision, kèm khoảng tin cậy, theo ngày / đêm / mưa và theo từng nút. Nhóm nào có ít hơn 10 cảnh báo thì chỉ báo số đếm, không báo phần trăm [Đề xuất].

### 7.6 Phân tích độ nhạy và đường precision-recall
- Danh sách ngưỡng được quét và phạm vi quét phải được **đăng ký trước** (mục 3.1).
- Trên tập test, vẽ precision và recall theo từng ngưỡng (ân hạn, T_c vào vùng giao lộ, số khung xác nhận, ngưỡng tin cậy) và đánh dấu điểm đã đóng băng. Phần này chỉ **mô tả**, không dùng để chọn lại ngưỡng. Chọn lại ngưỡng đồng nghĩa với tập test đã cháy (mục 3.4).
- scikit-learn cũng cảnh báo không được dùng cùng một dữ liệu để vừa huấn luyện vừa chỉnh ngưỡng quyết định [Kiểm chứng].

### 7.7 Hạn chế đã biết (bắt buộc)
Cỡ mẫu; **chỉ 1 nút giao** (chưa đo được khả năng tổng quát sang nút khác); các điều kiện chưa thử; nguồn video (mô phỏng bằng video quay sẵn); phương pháp gán nhãn; tương quan giữa các cảnh báo trong cùng phiên.

Mẫu báo cáo nằm ở `docs/eval/report-template.md`. Báo cáo hoàn chỉnh được dán vào hoặc liên kết từ `eval/results/report.md` (deliverable #10 của khóa).

---



## 11. Ba quyết định đã chốt (PO, 21/09/2026)

1. **Chia dữ liệu:** theo video, phiên quay và địa điểm. Tập test quay mới sau khi đóng băng, khác địa điểm hoặc điều kiện. Chỉnh ngưỡng bằng leave-one-video-out trên tuning/val.
2. **Đo:**
   - đơn vị là sự kiện vi phạm;
   - khớp theo cùng phương tiện trong cửa sổ thời gian cố định (mục 4.3);
   - cảnh báo trùng do đổi ID được gộp và ghi là lỗi tracking (mục 4.4);
   - nhãn có 3 loại, ca mơ hồ báo riêng (mục 4.5);
   - mẫu âm khó nằm trong tập test.
3. **Gán nhãn và đóng băng:**
   - hai người gán nhãn độc lập, không xem kết quả hệ thống; đo kappa; người thứ ba phân xử;
   - đóng băng bằng git tag + mã băm config + mã băm manifest test;
   - chạy test một lần; chỉnh lại sau khi đã xem kết quả thì tập test coi như cháy.

**Phân vai:** người chỉnh ngưỡng không được đọc thư mục test; người giữ test không chỉnh ngưỡng.

**Chốt thêm ngày 21/09:**
- ngày đóng băng là **11/10**; sau mốc này chỉ đổi kiến trúc hoặc công nghệ lớn khi có lý do kỹ thuật rõ ràng;
- MVP có **1 nút giao**; phát triển bằng video quay sẵn trước, rồi mới tích hợp camera thật;
- khi tích hợp, nguồn camera **bắt buộc là video liên tục**, không dùng ảnh tĩnh.

**Chốt sau design review (21/09):**
- chuẩn hóa video 15 FPS cố định (mục 2.6);
- đo thêm tỉ lệ che lọt và độ chính xác đếm xe (mục 7.1);
- tập dev gán đôi 30% (mục 5.1);
- kiểm tra quy tắc ghép trước khi đóng băng (mục 4.3);
- hai bản sao mã hóa của tập test (mục 3.3).

**Việc còn mở:** chọn nút giao cụ thể (theo tiêu chí C-01 trong design review) và lịch quay.

---

## 12. Nguồn

1. Varma S., Simon R. *Bias in error estimation when using cross-validation for model selection.* BMC Bioinformatics 7:91, 2006. https://pubmed.ncbi.nlm.nih.gov/16504092/
2. Dwork C., Feldman V., Hardt M., Pitassi T., Reingold O., Roth A. *The reusable holdout: Preserving validity in adaptive data analysis.* Science 349(6248):636–638, 2015. https://www.science.org/doi/10.1126/science.aaa9375
3. Kapoor S., Narayanan A. *Leakage and the reproducibility crisis in machine-learning-based science.* Patterns 4(9), 2023. https://www.cell.com/patterns/fulltext/S2666-3899(23)00159-9
4. Babu M. A. A. et al. *Data Leakage in Automotive Perception: Practitioners' Insights.* arXiv:2604.06899, 2026. https://arxiv.org/abs/2604.06899
5. Wen L. et al. *UA-DETRAC: A New Benchmark and Protocol for Multi-Object Detection and Tracking.* arXiv:1511.04136. https://arxiv.org/abs/1511.04136
6. Dendorfer P. et al. *MOTChallenge: A Benchmark for Single-Camera Multiple Target Tracking.* arXiv:2010.07548; chính sách nộp bài: https://github.com/dendorferpatrick/MOTChallengeEvalKit/blob/master/MOT/README.md
7. Koh P. W. et al. *WILDS: A Benchmark of in-the-Wild Distribution Shifts.* ICML 2021, arXiv:2012.07421. https://arxiv.org/abs/2012.07421
8. scikit-learn: *Cross-validation* (dữ liệu theo nhóm, GroupKFold, LeaveOneGroupOut) https://scikit-learn.org/stable/modules/cross_validation.html ; *Tuning the decision threshold for class prediction* https://scikit-learn.org/stable/modules/classification_threshold.html
9. Brown L. D., Cai T. T., DasGupta A. *Interval Estimation for a Binomial Proportion.* Statistical Science 16(2), 2001. https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.full
10. Hanley J. A., Lippman-Hand A. *If nothing goes wrong, is everything all right? Interpreting zero numerators.* JAMA 249(13):1743–1745, 1983. https://jhanley.biostat.mcgill.ca/c607/ch08/zero_numerator.pdf
11. PASCAL VOC Development Kit (nhiều phát hiện cho cùng một đối tượng tính là báo nhầm). https://host.robots.ox.ac.uk/pascal/VOC/voc2006/htmldoc/index.html
12. McHugh M. L. *Interrater reliability: the kappa statistic.* Biochemia Medica 22(3):276–282, 2012. https://www.biochemia-medica.com/en/journal/22/3/10.11613/BM.2012.031
13. Saito T., Rehmsmeier M. *The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets.* PLOS ONE 10(3):e0118432, 2015. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0118432
14. Hoiem D., Chodpathumwan Y., Dai Q. *Diagnosing Error in Object Detectors.* ECCV 2012. https://dhoiem.cs.illinois.edu/publications/eccv2012_detanalysis_derek.pdf
15. TRECVID Surveillance Event Detection — NDCR và tỉ lệ báo nhầm theo thời gian (RFA): CRIM notebook paper 2011 https://www-nlpir.nist.gov/projects/tvpubs/tv11.papers/crim.sed.pdf ; tổng quan TRECVID 2022 (ActEV đo Pmiss tại RFA cố định) https://arxiv.org/abs/2306.13118
16. `imagehash` — thư viện perceptual hashing cho Python. https://github.com/JohannesBuchner/imagehash

---

## 13. Phụ lục — Đánh giá mở rộng theo spec v1.0 (phạm vi RL + WW + LN đã chốt ngày 21/09; toàn văn spec duyệt tại M0)

Phụ lục này mở rộng giao thức cho các loại vi phạm và các metric mới của spec (`docs/spec/trafficeye-spec.md`, FR-EVAL-1…7). Mọi nguyên tắc ở mục 2–7 giữ nguyên:
- chia dữ liệu theo phiên quay;
- đóng băng ngày 11/10;
- tập test chỉ chạy một lần;
- gán nhãn mù;
- báo kèm Wilson 95%.

### 13.1 Nhiều loại vi phạm trên cùng tập dữ liệu

- **Một lượt xem, mọi loại sự kiện.** Tập dev và tập test giữ nguyên. Người gán nhãn đánh dấu mọi sự kiện vượt đèn đỏ, đi ngược chiều, sai làn (đủ 3 kiểu) và dừng đỗ sai trong cùng một lượt xem.
- **File nhãn thêm trường `type`.** Mỗi phần tử trong `crossings[]` có thêm `type` ∈ `red_light`, `wrong_way`, `lane_class`, `lane_solid_line`, `lane_exit`, `illegal_stop`. Thiếu trường này thì coi là `red_light`, để nhãn cũ vẫn dùng được.
- **Sai làn đủ 3 kiểu, đều MUST (chốt Q8 ngày 21/09):**
  - `LN-a` (`lane_class`): đi không đúng làn dành cho loại xe quy định.
  - `LN-b` (`lane_solid_line`): chuyển làn đè/qua vạch liền.
  - `LN-c` (`lane_exit`): đi sai hướng theo mũi tên chỉ hướng của làn.
- **Quy tắc ghép theo từng loại**, đăng ký trước trong `eval/preregistration.md` trước ngày 11/10:
  - cùng video, cùng loại; |Δt| không vượt cửa sổ của loại đó; IoU ≥ 0,3 tại khung gần nhất;
  - cửa sổ khởi điểm: vượt đèn đỏ 1,0 giây; đi ngược chiều 3,0 giây; sai làn (cả 3 kiểu LN-a, LN-b, LN-c) 2,0 giây; dừng đỗ sai 5,0 giây;
  - lý do: với ba loại sau, lúc "vi phạm trở nên rõ" kéo dài hơn so với vượt đèn đỏ;
  - cửa sổ được chốt lại sau khi kiểm tra quy tắc ghép trên dev (M-02).
- **Báo cáo riêng từng loại và từng kiểu sai làn:** precision, recall, số báo nhầm/giờ/camera.
  - Không gộp thành một con số precision chung, vì loại dễ sẽ che mất loại khó; sai làn phải báo riêng từng kiểu `LN-a`, `LN-b`, `LN-c`.
  - Loại nào có dưới 30 cảnh báo thì chỉ mang tính minh họa (mục 7.2).
- **Script:** `scripts/evaluate.py` sẽ thêm tham số `--type`, hoặc tự tách kết quả theo `type`. Việc này là một task trong plan M2/M3; phần Wilson và phần log giữ nguyên.

### 13.2 mAP (FR-EVAL-1)

- **Tập khung dev** (khoảng 200 khung):
  - lấy đều 1 khung mỗi 3–5 giây từ các phiên dev, phủ ngày, đêm, lúc đông và lúc thưa xe;
  - gán box cho 4 lớp xe; lớp `person` (dùng để che mặt) báo riêng;
  - dùng để chọn model và độ phân giải; được phép để model gợi ý box rồi sửa tay.
- **Tập khung test** (khoảng 150 khung):
  - lấy từ các phiên test, sau khi đã khóa nhãn sự kiện;
  - gán nhãn **từ đầu, không dùng model gợi ý**, để kết quả không nghiêng về phía model;
  - người gán là hai người gán nhãn mù (TV2, TV3); TV4 phân xử.
- **Metric:**
  - mAP50, mAP50-95 và AP từng lớp, tính trên model đã đóng băng;
  - dùng cùng một bộ khung cho mọi định dạng (FP32, FP16, INT8) để đo độ lệch giữa các định dạng;
  - nếu công cụ hỗ trợ, báo AP theo nhóm kích thước box (nhỏ, vừa, lớn), vì xe máy ở xa có box rất nhỏ.

### 13.3 Đếm theo làn (FR-EVAL-2)

Mở rộng M-01:
- Đếm tay 2 đoạn × 10 phút trên tập test, và 2 đoạn trên dev để chỉnh.
- Mỗi đoạn đếm theo làn × loại xe × hướng.
- Báo sai số tuyệt đối và sai số %. Ô nào đếm tay bằng 0 thì không tính sai số %.

### 13.4 Hàng chờ và mức ùn tắc (FR-EVAL-4)

- **Hàng chờ:**
  - chọn ngẫu nhiên ít nhất 20 chu kỳ đèn trên tập test; danh sách chu kỳ được đăng ký trước;
  - với mỗi chu kỳ, người đếm số xe đứng yên liên tiếp từ vạch dừng tại lúc đèn chuyển xanh;
  - báo sai số tuyệt đối trung bình.
- **Mức ùn tắc:**
  - lấy mẫu ít nhất 30 phút;
  - người đánh giá gán mức 0–3 theo hướng dẫn có ảnh mẫu;
  - báo tỉ lệ khớp và kappa có trọng số.
- **Sự kiện ùn tắc:** trên các đoạn đã gán nhãn "ùn tắc" hoặc "thông thoáng", báo tỉ lệ phát hiện và tỉ lệ báo nhầm.

### 13.5 OCR (FR-EVAL-6)

- Tính trên mọi ca vi phạm được xác nhận của tập test:
  - tỉ lệ khớp hoàn toàn với biển số do người đọc từ bản CSGT;
  - tỉ lệ đúng theo từng ký tự;
  - tỉ lệ phải chuyển cho người đọc.
- Biển số chỉ dùng trong phạm vi đánh giá; không đưa lên slide ở dạng rõ.

### 13.6 Hiệu năng (FR-EVAL-7)

- **Chế độ file:** chạy toàn bộ video test với mọi luật bật. Báo FPS trung bình, và độ trễ p95 từ khung sự kiện tới lúc vào outbox.
- **Chế độ RTSP:** chạy thêm 30 phút để đo số khung bị rơi.
- Ghi rõ máy chạy, phiên bản driver và định dạng model.

### 13.7 Vai trò và chống rò rỉ

Giữ nguyên:
- TV1 không đọc thư mục test.
- TV4 không chỉnh ngưỡng.
- TV2 và TV3 không xem kết quả hệ thống trên tập test trước khi nhãn được khóa.
- Luật nào chưa được đóng băng trước 11/10 thì không được đánh giá trên tập test; chỉ được trình diễn.

Từ 22/09, mã vai ứng với người thật: TV1 = Cường, TV2 = Tuấn, TV3 = Linh, TV4 = Khánh. Cách vận hành các quy tắc trên với 4 người: `docs/plan/timeline.md` mục 5.2.

### 13.8 Đo theo chu kỳ đèn và sự kiện tuyến (FR-EVAL-8)

Chỉnh trên dev, đóng băng cùng ngày 11/10 (`configs/frozen/corridor-v1.yaml`), chạy tập test đúng một lần.

| Hạng mục đo | So sánh với | Mục tiêu |
|---|---|---|
| Độ dài chu kỳ $C$ và thời gian xanh thực tế $g$ | Nhãn đèn làm tay (đã có sẵn từ luật vượt đèn đỏ) | Sai số trung vị ≤ 1 giây |
| Tốc độ thoát bão hòa $s$ | Đếm tay kèm bấm giờ trong pha xanh, ≥ 20 chu kỳ mỗi nút | Sai số ≤ 15% |
| Số xe thoát mỗi chu kỳ | Đếm tay, ≥ 20 chu kỳ mỗi nút | Sai số ≤ 10% |
| Nhận diện chu kỳ thất bại (`cycle failure`) | Nhãn tay, ≥ 30 chu kỳ | Precision và recall |
| Sự kiện tràn hàng chờ (`spillback`) | Đoạn người gán nhãn, lệch cho phép ± 1 chu kỳ | Precision và recall; n < 30 thì ghi "chỉ minh họa" |

**Hạn chế:** Độ trễ và mức phục vụ (LOS) là ước tính theo công thức Highway Capacity Manual (HCM 2010/2016), không có nhãn thật trên đường để đối chiếu. Điều này được ghi rõ trong mục hạn chế của báo cáo.
