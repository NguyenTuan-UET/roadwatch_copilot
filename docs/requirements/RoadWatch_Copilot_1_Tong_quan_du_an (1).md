# RoadWatch Copilot: tổng quan dự án

> **Trợ lý kèm lái cho tài xế mới trên cao tốc.** Hệ thống đo khoảng cách tới xe phía trước và nhắc sớm bằng giọng Việt, chỉ khi thật cần. Thiết bị gắn kính, không can thiệp vào xe, chạy offline.

> **File Word `tai_lieu_viet_bao_cao.docx`** (cùng thư mục) được sinh lại ngày 29/09/2026 từ ba file Markdown trong thư mục này. Khi có khác biệt, các file Markdown là nguồn chuẩn.

| Hạng mục | Thông tin |
|---|---|
| Mã đề | DEV-04 · AI Thiết bị (VinFast) |
| Giai đoạn | Chốt brainstorming (bản 2). Đã chọn người dùng chính, bài toán chủ đạo và cách làm; chưa phân rã chi tiết bài toán con. Cập nhật 28/09/2026: bỏ hồ sơ xe khỏi MVP. Cập nhật 06/10/2026: camera tự hiệu chuẩn, chỉ nhập khoảng cách camera–cản trước (ADR-04, xem [file 3](RoadWatch_Copilot_3_Cau_hinh_lap_dat.md)) |
| Người dùng chính | Tài xế mới: người mới lái và người mới đổi xe |
| Cấu trúc | 3 bài toán chính, 4 bài mở rộng nếu còn thời gian, 5 hướng phát triển |

**Tóm tắt**

- **Vấn đề:** từ 27/8/2026, lỗi không giữ khoảng cách trên cao tốc bị xử phạt. Tài xế mới chưa cảm nhận được khoảng cách ở tốc độ cao. Các giải pháp hiện có thì hoặc nói nhiều, bắt nhìn màn hình, hoặc phải khoan đục xe.
- **Giải pháp:** một bài toán **ĐO** (khoảng cách từ cản trước tới xe phía trước, camera tự hiệu chuẩn, có công bố sai số), một bài toán **NÓI** (khi nào cần nhắc, nhắc câu gì) và một nền tảng **KIỂM CHỨNG** (kỹ sư chỉnh ngưỡng, xem số liệu).
- **Đối thủ:** trực tiếp là SafeGap (ứng dụng điện thoại đo khoảng cách); gián tiếp là Vietmap (mạnh về dữ liệu bản đồ).
- **Khả thi:** làm được trong 4 tuần với “edge mô phỏng” trên laptop, chạy offline.

---

## 1. Bối cảnh và vấn đề

### 1.1 Thực trạng trên cao tốc

- Từ **27/8/2026**, Cục CSGT xử phạt lỗi không giữ khoảng cách trên trục cao tốc Pháp Vân – Cầu Giẽ – Cao Bồ – Mai Sơn – QL45 – Nghi Sơn. Nhiều xe chỉ cách xe trước **10–20 m**, trong khi ngưỡng ở 80–100 km/h là **55–70 m**.
- **Mức phạt** (Nghị định 168/2024): 4–6 triệu đồng, trừ 2 điểm GPLX. Nếu gây tai nạn: 20–22 triệu đồng, trừ 10 điểm.
- **Nghị định 238/2026** (hiệu lực 15/8/2026) bổ sung lỗi chuyển làn không bảo đảm khoảng cách với xe phía trước, phía sau và hai bên.
- CSGT **không xử lý** khi khoảng cách bị thu hẹp đột ngột do xe khác chen làn, xe trước phanh gấp hoặc ùn tắc. Hệ thống cảnh báo cũng phải hiểu các tình huống này để không bắt lỗi oan cho tài xế.
- Thông tư 38/2024 đang được rà soát nên **ngưỡng có thể còn thay đổi**. Hệ thống phải đổi được ngưỡng mà không cần sửa phần mềm.

| Tốc độ | Khoảng cách tối thiểu (TT 38/2024) | Thời gian bám đuôi tương đương |
|---|---|---|
| 60 km/h | 35 m | ≈ 2,1 giây |
| 60–80 km/h | 55 m | ≈ 2,5 giây |
| 80–100 km/h | 70 m | ≈ 2,5 giây |
| 100–120 km/h | 100 m | ≈ 3,0 giây |

*Bảng áp dụng cho đường khô ráo, thẳng, tầm nhìn tốt. Khi mưa, sương mù hoặc đèo dốc phải giữ khoảng cách lớn hơn.*

### 1.2 Khó khăn của tài xế mới

- **Khó ước lượng kích thước và khoảng cách:** người mới thường cảm thấy xe to hơn thực tế nên đánh lái quá tay (Báo Pháp Luật TP.HCM).
- **Đổi xe phải làm quen lại:** độ dài phần đầu, phần đuôi và kích thước xe khác nhau giữa sedan, hatchback và SUV (Đánh giá xe).
- **Khoảng cách thật ngắn hơn cảm nhận:** xe có đầu dài hơn thì khoảng cách từ cản trước tới xe phía trước ngắn hơn mức tài xế ước lượng từ ghế lái. Đây là nhận định nhóm tự suy luận, cần kiểm chứng.

### 1.3 Rào cản khi lắp thêm thiết bị

- Giải pháp lắp thêm phổ biến là camera 360: giá 6,5–25 triệu đồng, lắp 2–4 giờ, phải gắn vào gương, cản và đi dây vào hệ thống điện của xe.
- Đã có đại lý từ chối bảo hành cụm gương với lý do gương bị khoan để lắp camera 360 (VnExpress, 6/2024).
- Không phải cách lắp nào cũng làm mất bảo hành. Nhưng chỉ riêng sự e ngại đã đủ khiến nhiều người không lắp thêm gì cả.

### 1.4 Hạn chế của các giải pháp hiện có

| Giải pháp | Hạn chế với tài xế mới |
|---|---|
| Ứng dụng đo khoảng cách trên điện thoại | Phải đặt điện thoại trước vô lăng và nhìn màn hình mới hiểu; nói nhiều |
| Camera hành trình có ADAS cơ bản | Chủ yếu chỉ bíp, không nói nguy cơ là gì, cần làm gì; ngưỡng cứng, dễ báo giả |
| Ứng dụng cảnh báo tốc độ, camera phạt nguội | Chỉ dựa vào GPS và bản đồ, không biết xe phía trước |
| Camera 360 lắp thêm | Chủ yếu dùng ở tốc độ thấp; phải khoan, đi dây; chi phí cao |
| Hệ thống phụ thuộc cloud | Mất tác dụng ở hầm, đèo, vùng mất sóng; có độ trễ |

> **Phản hồi người dùng:** “Sao mình cảm thấy rối quá, nó nói nhiều, làm mình vừa lái vừa nhìn điện thoại, mất tập trung. Nếu tích hợp được với camera hành trình hay HUD thì tốt hơn.”
> *(Phản hồi sơ bộ, cần kiểm chứng thêm qua phỏng vấn.)*

**Kết luận:** vấn đề không chỉ là *phát hiện được nguy cơ* mà còn là *truyền đạt cảnh báo sao cho tài xế không rối thêm*.

---

## 2. Người dùng

| Vai trò | Là ai | Cần gì |
|---|---|---|
| **U1a – Người mới lái** (người dùng chính) | Có bằng hạng B dưới 2 năm, 22–40 tuổi, ít chạy cao tốc | Được nhắc sớm, câu ngắn tiếng Việt nói rõ cần làm gì; im lặng khi mọi thứ ổn; không phải nhìn màn hình |
| **U1b – Người mới đổi xe** (người dùng chính) | Đã lái vài năm nhưng vừa lên SUV, xe 7 chỗ, xe điện, hoặc hay lái xe lạ | Được nhắc đúng lúc khi chưa quen cảm giác khoảng cách của xe mới; gắn, tháo dễ, không để lại dấu. MVP chưa cá nhân hóa hình học theo từng mẫu xe (ADR-04) |
| **U2 – Kỹ sư ADAS** (vai trò vận hành, đề bắt buộc) | Kỹ sư hãng xe hoặc đơn vị tích hợp | Chỉnh ngưỡng có người duyệt (HITL); bộ luật và cấu hình camera, lắp đặt có phiên bản; số liệu và nhật ký sự kiện |

**Khách hàng về sau** (không phải người dùng của demo): hãng xe và đại lý (bán như phụ kiện chính hãng), trường dạy lái, người thân của người mới lái, doanh nghiệp vận tải.

---

## 3. Pain point

| Mã | Pain point | Mức độ |
|---|---|---|
| **P1** | Chưa cảm nhận được khoảng cách và độ dài đầu xe ở tốc độ cao, nên bám sát vô ý và dễ bị phạt | Rất cao |
| **P2** | Phát hiện nguy hiểm phía trước muộn (xe trước phanh gấp, gặp đuôi dòng ùn tắc) | Rất cao |
| P3 | Chưa cảm nhận bề ngang xe trong làn | Cao |
| **P4** | Muốn lắp thêm hỗ trợ nhưng sợ khoan đục, đi dây làm mất bảo hành | Cao |
| P5 | Thiết bị, ứng dụng hiện có không biết kích thước xe mình. *MVP không giải quyết: đã bỏ hồ sơ xe (ADR-04)* | TB–Cao |
| **P6** | Cảnh báo dồn dập, nói nhiều, phải nhìn màn hình | Rất cao |
| **P7** | Cảnh báo máy móc, thiếu ngữ cảnh; bị chen làn vẫn kêu | Cao |
| **P8** | Chỉ kêu khi đã vi phạm, không nhắc sớm | Cao |
| P9 | Không có người kèm, không biết mình có tiến bộ không | TB |
| **P10** | Phụ thuộc mạng, có độ trễ | Cao |
| P11 | Hiểu nhầm là xe tự lái nên ỷ lại | Cao |
| P12 | (Kỹ sư) Ngưỡng cứng, khó cập nhật theo luật và theo mẫu xe | Cao |
| P13 | (Kỹ sư) Thiếu dữ liệu, số liệu đánh giá của Việt Nam | Cao |
| P14 | (Kỹ sư) Không bền trước lỗi đầu vào và khi gắn lệch | TB–Cao |

**Giả định cần kiểm chứng qua phỏng vấn** (5–8 người mới lái, 3–5 người vừa đổi xe):

- Được nhắc bằng giọng nói có làm họ yên tâm hơn không.
- Họ thích nhắc sớm hay nhắc khi đã dưới ngưỡng.
- Nỗi lo bảo hành có phải lý do thật khiến họ không lắp thêm thiết bị.
- Họ muốn nhận cảnh báo qua camera hành trình hoặc HUD hay qua điện thoại.
- Họ sẵn sàng trả bao nhiêu.

---

## 4. Đối thủ và định vị

| Giải pháp | Làm tốt | Chưa giải quyết cho tài xế mới |
|---|---|---|
| **SafeGap** (ứng dụng điện thoại), đối thủ trực tiếp | Đo khoảng cách theo TT 38 trên điện thoại, giọng nói, lệch làn, biển tốc độ, chế độ mưa; web miễn phí, bản PRO cho Android | Tự công bố sai số khoảng 10–20%; không thấy công bố cơ chế chống cảnh báo mệt mỏi hay chế độ người mới; phải đặt điện thoại trước vô lăng |
| **Vietmap** (camera hành trình, Vietmap Live – MiMi AI), đối thủ gián tiếp | Dữ liệu bản đồ lớn (khoảng 3.000 camera, hơn 10.000 biển tốc độ), khoảng 1.800 đại lý | Cảnh báo chủ yếu theo vị trí |
| **Camera 360 lắp thêm** | Nhìn quanh xe khi đỗ, khi đi chậm | Không giúp ở cao tốc; phải khoan, đi dây; 6,5–25 triệu đồng |
| **Ứng dụng cảnh báo tốc độ** (GOFA, Wyn, GSpeed, Waze) | Rẻ, nhắc tốc độ và camera phạt nguội | Không nhìn đường |

**Định vị:** người kèm lái cho tài xế mới trên cao tốc. Thiết bị nhắc sớm bằng giọng Việt, chỉ khi cần, không khoan đục xe.

**Khác SafeGap ở 6 điểm** (phải chứng minh bằng demo và số liệu):

1. **Đo có kiểm chứng:** khoảng cách tính tới cản trước, camera tự hiệu chuẩn; công bố sai số theo dải khoảng cách và phạm vi xe áp dụng.
2. **Nhắc sớm** theo xu hướng khoảng cách, trước khi xuống dưới ngưỡng.
3. **Chế độ người mới:** biên an toàn rộng hơn, câu nói rõ cần làm gì, tự bớt nói khi người lái đã ổn định.
4. **Điều phối có số liệu:** so số cảnh báo khi có và không có điều phối; ân hạn khi bị chen làn.
5. **Không bắt nhìn màn hình:** âm thanh là kênh chính, thiết bị có hình thức camera hành trình.
6. **Vai trò kỹ sư:** chỉnh ngưỡng có duyệt, cập nhật khi luật thay đổi.

---

## 5. Phát biểu bài toán và ranh giới

**Phát biểu:** Xây dựng trợ lý kèm lái cho tài xế mới, chạy trên thiết bị gắn kính không can thiệp xe. Hệ thống dùng camera trước, lắp ở vị trí quy định và tự hiệu chuẩn, để theo dõi khoảng cách với xe phía trước trên cao tốc, nhắc sớm khi khoảng cách đang thu hẹp và cảnh báo khi có nguy cơ va chạm, bằng câu tiếng Việt ngắn, phân cấp theo mức nguy hiểm và ít làm phiền.

**Giá trị cốt lõi:** như có một người lái lâu năm ngồi ghế phụ: nói đúng điều cần nói, sớm một nhịp, và chỉ khi thật cần.

**Ranh giới:**

- **Chỉ cảnh báo:** không tự lái, không phanh, không đánh lái.
- **Không can thiệp xe:** không khoan, không đi dây, không đọc dữ liệu từ xe; tháo ra không để lại dấu.
- **Không phải thiết bị đo phục vụ xử phạt:** khoảng cách là ước lượng có sai số.
- **Chạy offline** hoàn toàn; chỉ cảnh báo khi tín hiệu đủ tin cậy.

---

## 6. Cấu trúc bài toán

### 6.1 Bức tranh tổng thể

```
                   ┌──────────────────────── LÀM TRONG 4 TUẦN ────────────────────────┐
  Camera gắn kính  │                                                                  │
  + cam–cản ─────►│  BT-A: ĐO  ─────────►  BT-B: NÓI  ─────────►  Tài xế mới         │
  + tốc độ GPS     │  khoảng cách,          có cần nhắc?           (giọng Việt,       │
                   │  TTC, độ tin cậy       nhắc câu gì?           chỉ cảnh báo)      │
                   │        │                    │                                    │
                   │        └────────┬───────────┘                                    │
                   │                 ▼                                                │
                   │   BT-C: VẬN HÀNH & KIỂM CHỨNG (kỹ sư, HITL, số liệu, offline)    │
                   └──────────────────────────────────────────────────────────────────┘
       Nếu còn thời gian: MR-1..4  │  Hướng phát triển: PT-1..5 (cắm vào BT-B, không làm lại)
```

### 6.2 Ba bài toán chính (sẽ làm)

| Mã | Bài toán | Loại | Pain point | Chi tiết |
|---|---|---|---|---|
| **BT-A** | Đo khoảng cách tới xe phía trước bằng camera gắn kính | Bài toán lõi 1 | P1, P2, P14 | Hiệu chuẩn camera tự động, model gr14VinAI có sẵn (xe dẫn đầu, làn), khoảng cách, TTC |
| **BT-B** | Quyết định cảnh báo và nói với tài xế mới | Bài toán lõi 2, **trọng tâm** | P6, P7, P8, P11 | Ngưỡng TT 38 trong cấu hình, nhắc sớm, ân hạn khi bị chen hoặc ùn tắc, 3 mức cảnh báo, chế độ người mới, giọng Việt offline |
| **BT-C** | Vận hành, cấu hình và kiểm chứng | Nền tảng, đề bắt buộc | P10, P12, P13, P14 | 2 vai trò, HITL, nhật ký sự kiện, bảng số liệu, xử lý khung hình lỗi, guardrail |

Mô tả chi tiết đầu vào, đầu ra, cách làm và cách đo của từng bài nằm ở file **“RoadWatch Copilot – Các bài toán chính”**.

### 6.3 Làm nếu còn thời gian

| Mã | Bài toán | Vì sao chưa làm ngay |
|---|---|---|
| MR-1 | Vị trí xe trong làn theo bề ngang xe (lệch làn, đè vạch) | Vạch làn mờ, không có tín hiệu xi-nhan nên dễ báo sai. Được ưu tiên số 1. MVP không có hồ sơ xe nên bề ngang xe phải lấy từ cấu hình |
| MR-2 | Tổng kết sau chuyến cho tài xế mới | Rẻ, dùng lại nhật ký của BT-C. Cần tránh giọng chấm điểm, bắt lỗi |
| MR-3 | Nhận biết biển báo tốc độ bằng camera | Đề bài có nhắc, nhưng đối thủ đã làm; cần dữ liệu biển báo Việt Nam |
| MR-4 | Tối ưu hiệu năng edge (lượng tử hóa INT8) | Chưa có thiết bị thật nên số đo chỉ mang tính tham khảo |

**Cập nhật 02/10/2026 (PO):** MR-1 (lệch làn) và cảnh báo va chạm với người hoặc xe trong vùng rủi ro được đưa vào phần chuẩn bị cho tuần 2–4. Tuần 1 chỉ chuẩn bị hợp đồng dữ liệu và điểm nối giữa A và B; luật cảnh báo, ngưỡng và câu nói chưa được quyết. Chi tiết: spec mục 4.2 và mục 10.3 (OQ-A13, OQ-A14, OQ-A15).

### 6.4 Hướng phát triển

| Mã | Hướng | Ghi chú |
|---|---|---|
| PT-1 | Khe hở và không gian phía trước ở tốc độ thấp (phố, ngõ hẹp) | Mở rộng chủ đề “kích thước xe”; camera gắn kính không thấy vùng sát thân xe |
| PT-2 | Camera phụ không dây, không khoan: điểm mù, chuyển làn (NĐ 238/2026), đỗ xe | Cần thêm phần cứng |
| PT-3 | Biển báo theo bản đồ và GPS | Thế mạnh của Vietmap, nên tính hướng hợp tác |
| PT-4 | Hiển thị qua HUD, tích hợp vào camera hành trình có sẵn | Đáp ứng phản hồi “nếu tích hợp được với camera hành trình hay HUD” |
| PT-5 | Người thân kèm lái từ xa, đội xe, cập nhật từ xa (OTA), phần cứng Jetson thật | Hướng thương mại; cần hạ tầng và cơ chế đồng ý chia sẻ dữ liệu |

### 6.5 Đối chiếu với đánh số trong bản Word cũ (trước 28/09/2026)

| Bản Word | File này |
|---|---|
| BT1 + phần đo của BT2 + phần lắp đặt không can thiệp của BT5 | **BT-A** |
| Phần hồ sơ xe của BT5 | Bỏ khỏi MVP (ADR-04) |
| Phần luật của BT2 + BT3 | **BT-B** |
| BT4 | **BT-C** |
| BT6, BT7, BT8, BT9 | MR-1, MR-2, MR-3, MR-4 |
| BT10, BT11, BT12 | PT-1, PT-2, PT-3 |
| BT13 | PT-4, PT-5 |

---

## 7. Cách làm và độ khả thi

### 7.1 Edge mô phỏng (khi chưa có thiết bị)

- Toàn bộ chạy trên laptop, không dùng cloud. Khi demo bật chế độ máy bay.
- Mô hình xuất ONNX, chạy ONNX Runtime trên CPU với số luồng cố định.
- Video phát lại đúng tốc độ khung hình như luồng camera, kèm luồng tốc độ lấy từ nhật ký GPS.
- Đo FPS và độ trễ P50/P95, ghi kèm cấu hình máy. Mục tiêu đề xuất: ≥ 10 FPS, độ trễ tới lúc phát âm dưới 300 ms.
- Hình thức sản phẩm hướng tới: thiết bị gắn kính kiểu camera hành trình, cắm tẩu hoặc USB.

### 7.2 Độ khả thi

| Hạng mục | Khả thi | Ghi chú |
|---|---|---|
| Xe dẫn đầu, làn | Cao | Model gr14VinAI có sẵn |
| TTC, nhắc sớm | Cao | Không cần khoảng cách tuyệt đối |
| Khoảng cách 55–100 m | Trung bình | Sai số tăng theo khoảng cách (Stein 2003: khoảng 5% ở 45 m, 10% ở 90 m) |
| Hiệu chuẩn tự động, chỉ nhập khoảng cách camera–cản trước | Cao | Dùng model có sẵn, không cần huấn luyện; cần video có đáp án để kiểm chứng |
| Điều phối, giọng Việt | Cao | Luật và máy trạng thái; Piper TTS vi_VN chạy offline |
| Vận hành, HITL | Cao | Kỹ thuật phần mềm thông thường |
| Chạy trên Jetson thật | Thấp | Thay bằng edge mô phỏng |

**Kết luận:** làm được trong 4 tuần với bốn điều kiện: chỉ một kịch bản cao tốc, camera tự hiệu chuẩn, chấp nhận khoảng cách là ước lượng có sai số, và chứng minh edge bằng cách chạy cục bộ offline.

### 7.3 Học từ các giải pháp tham khảo

| Nguồn | Học gì | Không lấy gì |
|---|---|---|
| SafeGap | Tự hiệu chỉnh góc khi chạy thẳng; chế độ mưa; tự công bố sai số | Không sao chép; chỉ dùng làm mốc so sánh |
| open-adas | Tốc độ lấy từ GPS; hiệu chỉnh phối cảnh; dùng vùng làn để chọn xe | Mã phụ thuộc TensorRT 5/6 đã cũ |
| ADAS Indian Roads | Theo dõi ID, TTC, bỏ phiếu chống nhấp nháy, ROI hình thang, ONNX INT8 | Đầu ra là lệnh lái; giấy phép AGPL |
| Nhóm 776 (khóa trước) | Bíp cho mức khẩn cấp, giọng nói cho ngữ cảnh; thư viện câu thu sẵn; hai màn hình | Không demo trên cloud; không dàn trải |
| Model RoadWatch tự train | Warp ảnh vào khung model; hiệu chuẩn góc lắp khi chạy | Phần điều khiển xe; phần cứng xe |

---

## 8. Dữ liệu và kiểm chứng

**Dữ liệu**

- **Video cao tốc tự quay kèm GPS:** người ngồi ghế phụ quay; quay trên ≥ 2 mẫu xe để kiểm chứng phạm vi áp dụng của hiệu chuẩn tự động ([file 3](RoadWatch_Copilot_3_Cau_hinh_lap_dat.md)).
- **Ảnh xe đứng yên** ở các khoảng cách đo bằng thước dây (10, 20, 40, 60 m), dùng để đánh giá sai số.
- **Bộ dữ liệu có khoảng cách thật từ LiDAR:** KITTI (khoảng 80 m), DDAD (đến 250 m), dùng để kiểm chứng thuật toán đo.
- **30–50 đoạn clip gán nhãn sự kiện nguy hiểm:** bám sát, phanh gấp, bị chen, ùn tắc.

**Chỉ số**

| Chỉ số | Mục tiêu đề xuất |
|---|---|
| Sai số khoảng cách theo dải 0–30 / 30–60 / 60–100 m, trên ≥ 2 mẫu xe | Công bố trung thực, so với Stein 2003. Mong muốn 0,5–1 m chỉ là giả định cần kiểm chứng theo từng dải, chưa phải cam kết |
| Số cảnh báo **không khớp** sự kiện đã gán nhãn, có và không có BT-B | Giảm ≥ 50% (mục tiêu đề xuất) |
| Tỷ lệ bắt được sự kiện nguy hiểm (recall toàn hệ thống, tính cả lúc hệ thống suy giảm) | Không giảm khi bật điều phối |
| Số cảnh báo lặp trong cùng sự kiện; tổng số cảnh báo mỗi giờ | Báo cáo riêng, chưa đặt mục tiêu |
| Nhắc sớm trước bao nhiêu giây | Đo và báo cáo |
| Độ trễ P50/P95, FPS | ≥ 10 FPS, dưới 300 ms |

*Các mục tiêu trên là đề xuất, sẽ chốt với mentor sau khi có số đo đầu tiên.*

---

## 9. Rủi ro chính

| Rủi ro | Cách giảm |
|---|---|
| Trùng tính năng với SafeGap | Tập trung vào 6 điểm khác biệt; có demo so sánh kèm số liệu |
| Khoảng cách xa sai số lớn | Nhắc theo giây và theo dải; dùng xu hướng; có vùng trễ quanh ngưỡng |
| Camera bị lắp lại hoặc xê dịch | Phần mềm tự phát hiện và hiệu chuẩn lại; trong lúc đó không cảnh báo khoảng cách, báo trạng thái suy giảm |
| Hiệu chuẩn tự động không đạt trên một số mẫu xe hoặc thiết bị | Kiểm chứng trên ≥ 2 mẫu xe; nhóm xe không đạt sai số cho phép thì giới hạn phạm vi hỗ trợ, không bổ sung lại hồ sơ xe |
| Video công khai không có tốc độ xe | Tự quay kèm GPS |
| Không có thiết bị edge | Edge mô phỏng; giữ định dạng ONNX |
| Luật thay đổi | Ngưỡng nằm trong cấu hình có phiên bản, đổi qua HITL |
| An toàn khi quay video | Người ngồi ghế phụ quay; người lái không thao tác |

---

## 10. Phạm vi demo và lộ trình

Dự án 4 tuần. **Hạn nộp MVP là cuối tuần 1**; tuần 2–4 là phần mở rộng.

**Bản nộp MVP (cuối tuần 1)**

- Demo chạy offline trên video cao tốc: xe dẫn đầu, khoảng cách với camera tự hiệu chuẩn, TTC, cảnh báo bằng câu thu sẵn, trạng thái suy giảm.
- Đánh giá sơ bộ BT-B so với baseline trên một bộ kiểm thử nhỏ giữ riêng, với ít nhất một cơ chế điều phối chứng minh được giá trị.
- Kiểm chứng sơ bộ khoảng cách trên cấu hình demo, chỉ ở các dải đã đo được.
- Số đo hiệu năng trên máy demo: throughput và độ trễ P95, báo cáo riêng.
- HITL qua dòng lệnh (CLI): đề xuất, báo cáo tác động, người khác duyệt, kích hoạt, quay lui.
- Danh sách giới hạn đã biết.

**Có trong demo cuối (tuần 4)**

- Hiệu chuẩn camera tự động; cấu hình có phiên bản, ghi vào thông tin mỗi lần chạy; bảng sai số theo dải trên các xe thử.
- Video cao tốc chạy offline.
- Nhắc sớm khi khoảng cách thu hẹp; tình huống bị chen làn; xe trước phanh gấp.
- Chế độ người mới và chế độ quen xe.
- Màn hình kỹ sư đổi ngưỡng có duyệt.
- Bảng so sánh khi có và không có điều phối; số đo độ trễ.

| Tuần | Việc | Kết quả |
|---|---|---|
| 1 · **MVP nộp** | Ngày 1: chốt hợp đồng dữ liệu tối thiểu (v0.1) và fixture cho trường hợp bình thường và lỗi. Đầu tuần: khảo sát thực địa trên xe demo (chiều cao camera, khoảng cách tới cản, góc lắp, thông số camera); quay video cao tốc kèm GPS; kiểm chứng phương pháp kiểm tra lắp đặt. BT-A: phát hiện, theo dõi, khoảng cách, TTC có kiểm tra độ tin cậy. BT-B: mức Cảnh báo và Khẩn cấp, một cơ chế điều phối chống nhấp nháy (vùng trễ quanh ngưỡng, thời gian xác nhận, mỗi đợt nhắc một lần), trạng thái suy giảm, baseline chạy song song. BT-C: nhật ký, chạy lại BT-B trên nhật ký, HITL qua CLI. Chụp xe đứng yên ở các khoảng cách đo bằng thước; gán nhãn bộ phát triển và một bộ kiểm thử nhỏ giữ riêng. Cuối tuần: chạy bộ kiểm thử nhỏ đúng một lần, đo hiệu năng, lập danh sách giới hạn | Bản nộp MVP; hợp đồng dữ liệu v1.0 đóng băng |
| 2 | Mở rộng BT-A: khử méo ống kính, làn từ model, bằng chứng chen làn. Mở rộng BT-B: nhắc sớm theo xu hướng, ân hạn khi bị chen, ùn tắc, chế độ người mới. Thử nghiệm ngưỡng độ mới của GPS. BT-C: màn hình kỹ sư, màn hình trạng thái cho tài xế. Quay và gán nhãn thêm dữ liệu | Luồng sự kiện nguy cơ đầy đủ |
| 3 | Tinh chỉnh trên bộ phát triển qua HITL; thử nghe với người mới lái (chốt câu nói, chu kỳ nhắc); kiểm chứng phạm vi áp dụng trên xe thử 2; kiểm thử các tình huống lỗi | Demo tài xế đầy đủ |
| 4 | Đánh giá cuối một lần trên bộ kiểm thử mới giữ riêng, với cấu hình đóng băng; so sánh có và không có BT-B; báo cáo hiệu năng; quay video demo. Nếu dư thời gian: MR-1, MR-2 | Bảng số liệu, video demo, danh sách yêu cầu chưa đạt |

Bộ dữ liệu tách theo phiên quay, không theo clip. Sau khi nộp MVP, bộ kiểm thử nhỏ của tuần 1 được gộp vào bộ phát triển; bộ kiểm thử của tuần 4 phải là các phiên quay mới, chưa dùng để tinh chỉnh.

---

## 11. Cần mentor xác nhận và bước tiếp theo

**Cần mentor xác nhận**

1. Thu hẹp về một người dùng chính (tài xế mới), với kỹ sư ADAS là vai trò vận hành bắt buộc.
2. Giữ kịch bản cao tốc làm chủ đạo dù SafeGap đã có tính năng tương tự.
3. Gom thành 3 bài toán chính: BT-A đo, BT-B nói, BT-C kiểm chứng.
4. MR-1 (làn) và MR-3 (biển tốc độ) để ở nhóm “nếu còn thời gian” đã đủ yêu cầu Cơ bản của đề chưa.
5. Chứng minh edge bằng edge mô phỏng và video tự quay.

**Làm ngay**

- Phỏng vấn tài xế mới và người vừa đổi xe.
- Cài thử SafeGap.
- Xin đường dẫn “app Lili” để bổ sung vào phân tích đối thủ.
- Khảo sát thực địa trên xe thử để đo khoảng cách camera–cản trước ([file 3](RoadWatch_Copilot_3_Cau_hinh_lap_dat.md)).
- Quay video cao tốc kèm GPS.
- Dựng khung pipeline chạy offline.

---

## Phụ lục: nguồn tham khảo

**Pháp lý:** Thông tư 38/2024/TT-BGTVT (Điều 11); Nghị định 168/2024/NĐ-CP (Điều 6); Nghị định 238/2026/NĐ-CP; Công văn 8948/VPCP-CN (1/9/2026); Tuổi Trẻ, VnExpress, VOV Giao thông, VTV (8–9/2026).

**Người dùng và thị trường:** Báo Pháp Luật TP.HCM (mẹo căn thân xe cho tài xế mới); Đánh giá xe (lái xe lạ); VnExpress 6/2024 (tranh cãi bảo hành khi lắp phụ kiện); báo giá camera 360 năm 2026; TNB Auto (phụ kiện xe điện và bảo hành).

**Đối thủ:** SafeGap (safegap.me, lxat.thainguyen.app); Vietmap (vietmap.vn/camera-hanh-trinh); VIETMAP LIVE – MiMi AI (App Store); Dân trí 12/2025 (tổng hợp ứng dụng cảnh báo).

**Kỹ thuật:**

- Stein, Mano, Shashua (2003), *Vision-based ACC with a single camera: bounds on range and range rate accuracy*.
- Han et al. (2016), *Vehicle distance estimation using a mono-camera for FCW/AEB systems*.
- Zhu & Fang (ICCV 2019), *Learning Object-Specific Distance From a Monocular Image*.
- open-adas (vietanhdev); ADAS Object Detection for Indian Roads; nhóm 776 (AI·20K Demo Day); Piper TTS vi_VN.

**Dữ liệu:** KITTI; DDAD (Toyota Research Institute); Object-specific Distance Dataset (Zhu & Fang); nuScenes; BDD100K.

*Thông tin cập nhật đến 28/09/2026.*
