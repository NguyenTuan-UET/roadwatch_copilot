# RoadWatch Copilot: các bài toán chính

> **Mục tiêu:** giúp tài xế mới giữ khoảng cách an toàn trên cao tốc. Hệ thống **đo** khoảng cách từ cản trước tới xe phía trước bằng camera tự hiệu chuẩn, có công bố sai số, và **chỉ nhắc khi thật cần**, bằng giọng Việt. Hệ thống chỉ cảnh báo, không can thiệp vào xe, chạy offline.

---

## Bức tranh tổng thể 

```
  Camera gắn kính ──►  BT-A: ĐO  ──►  BT-B: NÓI  ──►  Tài xế mới
  + cam–cản trước     "xe trước        "có cần nhắc?     (giọng Việt / bíp)
  + tốc độ GPS         cách bao xa?"    nhắc câu gì?"
                         │                  │
                         └──────┬───────────┘
                                ▼
                   BT-C: VẬN HÀNH & KIỂM CHỨNG
              (kỹ sư chỉnh ngưỡng, nhật ký, số liệu)
```

**Một bài để ĐO, một bài để NÓI, một nền tảng để KIỂM CHỨNG.** Phần nhận diện xe dùng giải pháp có sẵn. Nhóm dồn sức vào BT-A và BT-B.

---

## BT-A. Đo khoảng cách tới xe phía trước bằng camera gắn kính

**Câu hỏi cần trả lời:** xe phía trước cách **đầu xe mình** bao nhiêu mét, và đang lại gần nhanh cỡ nào?

| | |
|---|---|
| **Đầu vào** | Video camera trước; khoảng cách camera tới cản trước do người dùng nhập (xem [file 3](RoadWatch_Copilot_3_Cau_hinh_lap_dat.md)); tốc độ từ GPS |
| **Đầu ra** | Khoảng cách (m); thời gian bám đuôi (giây); thời gian tới va chạm (TTC); làn; trạng thái hiệu chuẩn; độ tin cậy của số đo |
| **Không cần gán nhãn huấn luyện** | Dùng model gr14VinAI có sẵn (MIT), không huấn luyện lại |

**Các bước**

1. **Hiệu chuẩn tự động:** khi xe chạy, phần mềm tự ước lượng tiêu cự, góc lắp (pitch, yaw) và chiều cao camera. Camera bị lắp lại thì tự phát hiện và hiệu chuẩn lại. Tài xế chỉ nhập khoảng cách camera–cản trước.
2. **Đưa ảnh về khung của model:** warp mỗi khung theo kết quả hiệu chuẩn, để model nhìn thấy ảnh giống lúc được huấn luyện, dù camera là loại nào.
3. **Chạy gr14VinAI:** model cho xe dẫn đầu (khoảng cách, tốc độ, vị trí ngang), vạch làn và chuyển động của xe mình.
4. **Khoảng cách tới cản trước** = khoảng cách từ camera − khoảng cách camera tới cản trước.
5. **TTC** = khoảng cách / tốc độ áp sát. Khi tiêu cự còn sai, khoảng cách và tốc độ lệch cùng tỉ lệ nên TTC gần như không đổi (cần kiểm chứng).

**Khó ở đâu:** tiêu cự và góc lắp sai thì ảnh đưa vào model khác ảnh lúc huấn luyện, và mọi số đo bằng mét đều lệch theo. Hiệu chuẩn cần xe chạy đủ nhanh, gần như thẳng; trong khoảng 30 s đầu chưa có cảnh báo khoảng cách.

**Đo bằng gì:**
- Sai số hiệu chuẩn trên video đã biết tiêu cự và góc lắp (comma `calib_challenge`, KITTI).
- Sai số khoảng cách theo dải 0–30 / 30–60 / 60–100 m, so với thước dây và với các bộ dữ liệu KITTI, DDAD (có khoảng cách thật đo bằng LiDAR).
- Chạy trên ≥ 2 mẫu xe để xác định phạm vi áp dụng; nhóm không đạt sai số cho phép thì giới hạn phạm vi hỗ trợ.
- Mong muốn sai số 0,5–1 m chỉ là giả định cần kiểm chứng theo từng dải, chưa phải kết quả hay cam kết.

---

## BT-B. Quyết định cảnh báo và nói với tài xế mới *(trọng tâm)*

**Câu hỏi cần trả lời:** với số đo này, **có cần nói không, nói ở mức nào, nói câu gì?**

| | |
|---|---|
| **Đầu vào** | Đầu ra của BT-A; tốc độ xe; bảng ngưỡng Thông tư 38 (lưu trong tệp cấu hình); chế độ người lái (người mới hoặc đã quen xe) |
| **Đầu ra** | Im lặng, hoặc một câu tiếng Việt ngắn, hoặc một tiếng bíp khẩn |

**Ba mức cảnh báo**

| Mức | Khi nào | Nói gì |
|---|---|---|
| Thông tin (nhắc sớm) | Khoảng cách đang thu hẹp, dự báo sắp xuống dưới ngưỡng | Nói nhẹ: “Xe trước đang gần lại” |
| Cảnh báo | Đã dưới mức an toàn theo tốc độ | “Giãn thêm khoảng cách” |
| Khẩn cấp | TTC thấp, nguy cơ va chạm | Bíp ngay, kèm “Phanh! Xe trước” |

**Luật điều phối**

- Nhắc sớm dựa trên xu hướng khoảng cách, không đợi đến khi đã vi phạm.
- **Ân hạn khi bị chen làn:** xe dẫn đầu vừa mới xuất hiện thì chưa nhắc ngay.
- **Ùn tắc** (dưới 60 km/h): tắt nhắc khoảng cách theo luật, nhưng vẫn giữ cảnh báo va chạm.
- Mỗi xe và mỗi loại cảnh báo có thời gian chờ trước khi nhắc lại. Luôn ưu tiên mức cao nhất. Chỉ nói khi số đo đủ tin cậy.
- **Chế độ người mới:** biên an toàn rộng hơn, câu nói rõ cần làm gì. Khi người lái đã ổn định thì tự bớt nói.
- Không bao giờ bắt tài xế nhìn màn hình.

**Công cụ:** máy trạng thái viết bằng Python; Piper TTS giọng vi_VN chạy offline, câu được sinh sẵn.

**Đo bằng gì:**
- Số cảnh báo **không khớp** sự kiện đã gán nhãn, khi **có và không có** điều phối. Mục tiêu đề xuất là giảm ít nhất 50%.
- Tỷ lệ bắt được sự kiện nguy hiểm (recall toàn hệ thống), không được giảm khi bật điều phối.
- Báo cáo riêng: số cảnh báo lặp trong cùng sự kiện, tổng số cảnh báo mỗi giờ. Định nghĩa và quy tắc khớp nhãn: [spec kiến trúc, mục 5.2](../specs/roadwatch-architecture.md).
- Nhắc sớm được trước bao nhiêu giây.

---

## BT-C. Vận hành, cấu hình và kiểm chứng *(nền tảng, đề bắt buộc)*

| | |
|---|---|
| **Làm gì** | Đăng nhập 2 vai trò (tài xế, kỹ sư ADAS); kỹ sư đổi ngưỡng và cấu hình kỹ thuật (camera, lắp đặt), có người duyệt mới áp dụng (HITL); nhật ký sự kiện kèm lý do vì sao nói hoặc không nói; bảng số liệu; xử lý khung hình lỗi; guardrail “chỉ cảnh báo” |
| **Chạy ở đâu** | Toàn bộ offline trên laptop (“edge mô phỏng”): ONNX Runtime trên CPU với số luồng giới hạn; đo FPS và độ trễ P50/P95 |
| **Công cụ** | FastAPI kèm giao diện web chạy cục bộ; SQLite; tệp YAML có phiên bản |
| **Khó ở đâu** | Không khó, là kỹ thuật phần mềm thông thường. Nhưng thiếu phần này thì không đạt đề |

---

## Ví dụ: một tình huống đi qua cả 3 bài toán

*Số liệu minh họa, chưa phải số đo.* Chị Lan lái xe với tốc độ 90 km/h; ngưỡng an toàn ở tốc độ này là 70 m.

| Bước | Xảy ra gì |
|---|---|
| **BT-A** | Camera đã tự hiệu chuẩn sau 30 s chạy. Model cho xe trước cách camera 76,5 m; camera cách cản trước 1,5 m (giả định). Khoảng cách = 76,5 − 1,5 = **75 m**, đang giảm dần |
| **BT-B** | 75 m vẫn trên ngưỡng 70 m nhưng đang giảm, dự báo 3 giây nữa sẽ xuống dưới ngưỡng. Hệ thống phát **mức Thông tin**: “Xe trước đang gần lại” |
| **BT-B** | Một xe khác chen vào, khoảng cách tụt còn 35 m. Đây là xe dẫn đầu mới nên áp dụng **ân hạn**, chưa nói gì. Sau 4 giây mà khoảng cách không giãn ra thì mới nhắc “Giãn thêm khoảng cách” |
| **BT-C** | Nhật ký ghi lại: lúc nào nói, lúc nào không nói và vì sao. Kỹ sư xem lại và có thể chỉnh thời gian ân hạn, nhưng phải qua bước duyệt |

**Vì sao xa thì khó:** ở xa, xe trước chỉ chiếm vài pixel nên số đo nhiễu hơn. Vì vậy sai số phải công bố theo từng dải, và BT-B nhắc theo xu hướng, có vùng trễ quanh ngưỡng, thay vì tin tuyệt đối vào một con số.

---

## Kết quả cần chứng minh khi demo

1. **Đo có kiểm chứng:** bảng sai số theo dải khoảng cách và sai số hiệu chuẩn tự động trên ≥ 2 mẫu xe; công bố phạm vi xe áp dụng.
2. **Ít nói hơn mà không bỏ sót:** số cảnh báo không khớp sự kiện khi có và không có BT-B; tỷ lệ bắt được sự kiện nguy hiểm.
3. **Chạy được trên edge:** tắt mạng vẫn chạy; FPS và độ trễ P50/P95.

## Lộ trình 4 tuần

Hạn nộp MVP là cuối tuần 1; tuần 2–4 là phần mở rộng. Lộ trình chi tiết chỉ ghi ở một chỗ: [file tổng quan, mục 10](<RoadWatch_Copilot_1_Tong_quan_du_an (1).md>).

---

**Câu chốt:** *“Nhận diện xe đã có sẵn. Nhóm tập trung vào hai việc còn thiếu: đo khoảng cách tới xe phía trước có công bố sai số, và chỉ lên tiếng khi thật cần.”*
