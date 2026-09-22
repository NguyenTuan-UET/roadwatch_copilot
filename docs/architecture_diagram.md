# SƠ ĐỒ KIẾN TRÚC HỆ THỐNG — TRAFFICEYE EDGE

> **Đây là file kiến trúc duy nhất của dự án.** Muốn biết hệ thống gồm những phần nào và nối với nhau ra sao thì đọc file này; mọi sơ đồ kiến trúc đều nằm ở đây. Đây cũng là file khóa học yêu cầu nộp (`docs/guide/deliverables/checklist.md`).
> **Căn cứ:** [spec](spec/trafficeye-spec.md) quy định hệ thống phải làm gì; [báo cáo kỹ thuật](report/trafficeye-edge-report.md) giải thích vì sao chọn kiến trúc này. Khi kiến trúc đổi thì sửa spec trước, rồi sửa file này.

---

## 0. Bản đồ hệ thống: 11 phân hệ

Đọc mục này trước. Mỗi việc trong `docs/plan/phan-viec/` ghi rõ nó thuộc phân hệ nào. Ai phụ trách phân hệ nào: `docs/plan/timeline.md` mục 5.1.

| Mã | Phân hệ | Làm gì | Chạy ở | Yêu cầu (spec) | Hợp đồng dữ liệu (spec) |
|---|---|---|---|---|---|
| PH1 | Nhận diện và đếm xe | Đọc video từ camera; tìm xe trong từng khung hình (YOLO); bám theo từng xe qua các khung (ByteTrack); đếm xe cắt vạch, theo làn | Edge | 4.1; 4.2 (FR-CNT) | Sự kiện đếm: 6.3 |
| PH2 | Đèn tín hiệu và cấu hình cảnh | Đọc màu đèn thành trạng thái ổn định (đỏ, vàng, xanh, không rõ); nạp và kiểm tra file mô tả nút giao (làn, vạch, vùng); đo từng chu kỳ đèn | Edge | 4.3 (FR-LGT); FR-DEN-4 | Cấu hình cảnh: 6.1; sự kiện `signal_cycle`: 6.3 |
| PH3 | Luật vi phạm | Lớp ngữ cảnh loại các ca không phải vi phạm; các luật tất định: vượt đèn đỏ, đi ngược chiều, sai làn. Kết quả là ứng viên vi phạm kèm mã lý do | Edge | 4.3 (FR-CTX); 4.4; 7 | Giao diện luật: 6.6; ngưỡng: 6.2 |
| PH4 | Bằng chứng và riêng tư | Che biển số và khuôn mặt; đóng gói 3 ảnh và đoạn clip; ký số; đọc biển số xe vi phạm (OCR) | Edge | 4.5 | Manifest gói bằng chứng: 6.4 |
| PH5 | Truyền dữ liệu và quản lý thiết bị | Hàng đợi outbox, gửi bù khi có mạng lại; heartbeat; trạng thái mong muốn; cập nhật phần mềm từ xa (OTA); MQTT | Edge ↔ trung tâm | 4.6 | Sự kiện: 6.3; kênh điều khiển: 6.7 |
| PH6 | Trung tâm | Nhận và lưu sự kiện; đăng nhập và phân quyền; API ứng viên; duyệt 2 bước; nhật ký nối băm; xác minh bằng chứng; xuất hồ sơ | Trung tâm | 3; 4.7 | API: 6.5 |
| PH7 | Phân tích giao thông | Mật độ, hàng chờ, ùn tắc tại từng nút; phân tích tuyến 3 nút theo HCM (mức phục vụ, tràn hàng chờ, nút cổ chai); gợi ý điều phối | Edge và trung tâm | 4.2 (FR-DEN, FR-COR); FR-DSP-1 | Cấu hình tuyến: 6.8; ngưỡng tuyến: 6.2 |
| PH8 | Giao diện | Dashboard Next.js: bản đồ, duyệt bước 1, màn CSGT, trang Tuyến, sức khỏe camera, báo cáo, nhật ký | Trình duyệt | 4.8 | API: 6.5 |
| PH9 | Agent AI | Soạn báo cáo ca trực, giải thích ứng viên. Chỉ đọc số liệu tổng hợp; người duyệt rồi mới phát hành; không quyết định vi phạm | Trung tâm | 4.9 | API: 6.5 |
| PH10 | Đánh giá và dữ liệu | Quay và chuẩn hóa video, lập manifest; gán nhãn; script đo; chỉnh ngưỡng; giữ tập test; báo cáo đánh giá | Ngoài hệ thống chạy thật | 4.12 | `docs/eval/protocol.md` |
| PH11 | Vận hành và hiệu năng | Docker, CI; tăng tốc model (ONNX, TensorRT, INT8); chạy 3 camera; bảo mật production; Live URL; giám sát; chạy thử 24 giờ | Mọi nơi | 4.10; 4.11; 5 (NFR); 8.2 | — |

Trong sơ đồ mục 1, mỗi khối có ghi mã phân hệ (PH1…PH9):
- khối B (thiết bị biên): PH1–PH5, và phần mật độ, hàng chờ của PH7;
- khối D (trung tâm): PH6, phân tích tuyến của PH7, PH9;
- khối E (giao diện): PH8.

PH10 và PH11 không phải khối chạy trong sơ đồ. Luồng xử lý trên edge ở mục 2; luồng duyệt 2 bước và vòng đời một vi phạm ở mục 3.

---

## 1. Kiến trúc tổng quan hệ thống (System Overview)

Hệ thống hoạt động theo mô hình **Edge AI First** kết hợp **Phê duyệt 2 bước có con người kiểm soát (Two-Step HITL)**:
- **Thiết bị biên (Edge Node):** Xử lý toàn bộ video tại chỗ: phát hiện, bám vết, đếm xe, và chạy các luật vi phạm tất định (vượt đèn đỏ, đi ngược chiều, sai làn đủ 3 kiểu). Tuyệt đối **không truyền video thô về trung tâm**.
- **Trung tâm (Central Backend):** Tiếp nhận metadata số đếm và các gói bằng chứng đã được ký số; quản lý hàng đợi duyệt vi phạm; xuất hồ sơ vi phạm cho quy trình phạt nguội (FR-EXP-1, CP2). Hệ thống chỉ tạo ứng viên; vi phạm chỉ được ghi nhận chính thức khi người duyệt.

```mermaid
graph TB
    %% Định nghĩa bảng màu tương phản cao (High Contrast - Tương thích 100% Dark/Light Mode)
    classDef hwNode fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#ffffff;
    classDef aiNode fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#ffffff;
    classDef ruleNode fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#ffffff;
    classDef secNode fill:#451a03,stroke:#fb923c,stroke-width:2px,color:#ffffff;
    classDef dbNode fill:#134e4a,stroke:#2dd4bf,stroke-width:2px,color:#ffffff;
    classDef beNode fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#ffffff;
    classDef hitlNode fill:#4c0519,stroke:#fb7185,stroke-width:2px,color:#ffffff;
    classDef netNode fill:#292524,stroke:#facc15,stroke-width:2px,color:#ffffff;

    subgraph S1 ["📹 A. PHẦN CỨNG TẠI NÚT GIAO"]
        CAM["<b>Camera Nút Giao</b><br/>(Góc nhìn sau đuôi xe)"]:::hwNode
        SIMV["<b>MediaMTX khi demo</b><br/>(phát lặp video đã quay thành RTSP)"]:::hwNode
        RTSP["<b>Luồng RTSP 1080p</b><br/>(15-20 FPS)"]:::hwNode
        CAM --> RTSP
        SIMV -.-> RTSP
    end

    subgraph S2 ["⚡ B. THIẾT BỊ BIÊN (EDGE NODE: LAPTOP / JETSON ORIN)"]
        DEC["PH1 · <b>YOLO Vehicle Detector</b><br/>(Xe máy, Ô tô, Buýt, Tải)"]:::aiNode
        TRK["PH1 · <b>ByteTrack Tracker</b><br/>(Gán & duy trì Track ID)"]:::aiNode
        CNT["PH1 · <b>Virtual Counting Line</b><br/>(Đếm xe theo làn & hướng)"]:::aiNode
        DEN["PH7 · <b>Mật độ & hàng chờ</b><br/>(tại nút, theo chu kỳ đèn)"]:::aiNode
        TLSM["PH2 · <b>Traffic Light State Machine</b><br/>(Đỏ / Vàng / Xanh / Nhấp nháy)"]:::ruleNode
        CYCLE["PH2 · <b>Signal Cycle Estimator</b><br/>(Đo chu kỳ đèn, sự kiện signal_cycle)"]:::ruleNode
        V_GATE{"PH3 · <b>Luật vi phạm dạng plugin</b><br/>(RL 6 điều kiện A1-E5, WW W1-W8, LN L1-L8)"}:::ruleNode
        RB["PH4 · <b>Bộ đệm vòng</b><br/>(giữ vài giây khung hình cho clip)"]:::secNode
        BLUR["PH4 · <b>Privacy Masker</b><br/>(Làm mờ biển số & mặt)"]:::secNode
        SEAL["PH4 · <b>Evidence Sealer</b><br/>(3 ảnh + clip JPEG t-3s đến t+2s, OCR biển xe vi phạm, ký Ed25519)"]:::secNode
        OUTBOX[("PH5 · <b>SQLite Outbox</b><br/>(Lưu đệm offline)")]:::dbNode
        DESIRED["PH5 · <b>Desired State</b><br/>(Hỏi trung tâm mỗi 10 s, chế độ điều khiển tay)"]:::netNode
        HLT["PH5 · <b>Heartbeat & chỉ số</b><br/>(sức khỏe thiết bị)"]:::netNode

        RTSP --> DEC --> TRK --> CNT --> OUTBOX
        TRK --> DEN --> OUTBOX
        RTSP --> TLSM
        RTSP --> RB
        TRK --> V_GATE
        TLSM --> V_GATE
        TLSM --> CYCLE
        TRK --> CYCLE
        CYCLE --> OUTBOX
        DESIRED --> V_GATE
        V_GATE -->|Ứng viên vi phạm| BLUR --> SEAL --> OUTBOX
        RB --> SEAL
    end

    subgraph S3 ["🌐 C. ĐƯỜNG TRUYỀN BẢO MẬT"]
        SYNC["PH5 · <b>HTTPS Sync Worker</b><br/>(Chỉ gửi metadata & bằng chứng)"]:::netNode
        OUTBOX --> SYNC
        HLT --> SYNC
    end

    subgraph S4 ["🏢 D. HẠ TẦNG TRUNG TÂM (CENTRAL BACKEND)"]
        API["PH6 · <b>FastAPI Gateway</b><br/>(REST API, JWT + phân quyền 4 vai trò, SSE bằng vé ngắn hạn)"]:::beNode
        VERIFY["PH6 · <b>Ed25519 Verifier</b><br/>(Xác thực tính toàn vẹn)"]:::beNode
        AUDIT["PH6 · <b>Audit Trail Logger</b><br/>(Nhật ký nối băm, ghi IP thật, trang nhật ký FR-UI-8)"]:::beNode
        DB[("PH6 · <b>PostgreSQL</b><br/>+ kho bằng chứng mã hóa khi lưu")]:::dbNode
        CORRIDOR["PH7 · <b>Corridor & HCM Analyzer</b><br/>(v/c, độ trễ, LOS, tràn hàng chờ, nút cổ chai)"]:::beNode
        AGENT["PH9 · <b>AI Reporting Assistant</b><br/>(LangGraph, chỉ đọc số liệu tổng hợp)"]:::aiNode

        SYNC --> API
        API --> VERIFY --> DB
        API --> AUDIT
        API --> CORRIDOR --> DB
        DB --> AGENT
        API -.->|trạng thái mong muốn, MQTT báo đổi từ CP2| DESIRED
    end

    subgraph S5 ["👥 E. GIAO DIỆN & PHÊ DUYỆT (NEXT.JS DASHBOARD)"]
        DASH["PH8 · <b>Live Traffic & Corridor Dashboard</b><br/>(Đếm xe, mật độ, trang Tuyến 3 nút, sức khỏe camera)"]:::hitlNode
        STEP1["PH8 · <b>Sơ duyệt Bước 1</b><br/>(Điều hành viên: Bản ẩn 100% biển số)"]:::hitlNode
        STEP2["PH8 · <b>Thẩm định Bước 2</b><br/>(Cán bộ CSGT: Bản rõ biển số xe vi phạm)"]:::hitlNode
        PORTAL["PH8 · <b>Cổng Tra Cứu Công Khai</b><br/>(Người dân kiểm tra chữ ký số)"]:::hitlNode

        DB --> DASH
        DB --> STEP1
        STEP1 -->|Hợp lệ| STEP2
        STEP2 -->|Ghi nhận chính thức| DB
        DB --> PORTAL
        AGENT -->|bản nháp báo cáo, người duyệt mới phát hành| DASH
    end

    style S1 fill:#0f172a,stroke:#64748b,stroke-width:2px,color:#cbd5e1
    style S2 fill:#022c44,stroke:#0288d1,stroke-width:2.5px,color:#38bdf8
    style S3 fill:#1c1917,stroke:#facc15,stroke-width:2px,color:#fde047
    style S4 fill:#03291f,stroke:#22c55e,stroke-width:2.5px,color:#4ade80
    style S5 fill:#2a0818,stroke:#fb7185,stroke-width:2.5px,color:#f472b6
```

---

## 2. Luồng xử lý chi tiết tại Biên (Edge Pipeline Flow)

Luồng xử lý thời gian thực từ khi nhận khung hình camera đến khi đưa ra quyết định vi phạm hoặc đếm xe. Sơ đồ lấy **luật vượt đèn đỏ** làm ví dụ. Đi ngược chiều và sai làn dùng cùng khung (lớp ngữ cảnh, mã lý do, gói bằng chứng), chỉ khác điều kiện của luật (spec mục 7).

```mermaid
graph TD
    classDef startNode fill:#1e293b,stroke:#94a3b8,stroke-width:2px,color:#ffffff;
    classDef procNode fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#ffffff;
    classDef decideNode fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#ffffff;
    classDef passNode fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#ffffff;
    classDef vioNode fill:#4c0519,stroke:#fb7185,stroke-width:2px,color:#ffffff;

    IN["Khung hình Video RTSP"]:::startNode --> DET["YOLO Detection (Bounding Box)"]:::procNode
    DET --> TRK["ByteTrack (Cập nhật Track ID & Quỹ đạo)"]:::procNode
    
    TRK --> CHK_CNT{"Xe cắt qua vạch đếm ảo?"}:::decideNode
    CHK_CNT -->|Có| COUNT["Cộng dồn số đếm xe theo làn"]:::passNode
    COUNT --> OUTBOX_CNT[("Ghi metadata vào SQLite Outbox")]:::passNode

    TRK --> TL_IN["ROI Đèn Tín Hiệu"]:::procNode
    TL_IN --> TL_STATE["Máy trạng thái đèn: RED / YELLOW / GREEN"]:::procNode
    
    TL_STATE --> CHK_RED{"Đèn ĐỎ ổn định & Xe qua vạch?"}:::decideNode
    CHK_RED -->|Không| NORMAL["Phương tiện bình thường"]:::passNode
    CHK_RED -->|Có| GATE{"Kiểm tra 6 điều kiện tất định<br/>1. Đèn đúng làn đang đỏ<br/>2. Qua vạch sau ân hạn Tg<br/>3. Đi sâu vào giao lộ Tc<br/>4. Track ID duy nhất<br/>5. Không có xe ưu tiên<br/>6. Đủ bằng chứng nhận diện"}:::decideNode
    
    GATE -->|Không đạt 1 trong 6| DROP["Loại bỏ (Báo nhầm A1-E5)"]:::passNode
    GATE -->|Đạt cả 6 điều kiện| MASK["Làm mờ biển số & mặt người xung quanh"]:::vioNode
    MASK --> SIGN["Bản điều hành viên + bản CSGT gửi đi, bản đầy đủ giữ trên thiết bị + Ký Ed25519 & Băm SHA-256"]:::vioNode
    SIGN --> OUTBOX_VIO[("Lưu gói bằng chứng vào SQLite Outbox")]:::vioNode
```

---

## 3. Luồng phê duyệt 2 bước có con người kiểm soát (Two-Step HITL Flow)

Quy trình đảm bảo tính pháp lý, bảo vệ quyền riêng tư và loại bỏ triệt để phạt oan:

```mermaid
sequenceDiagram
    autonumber
    actor Edge as Thiết Bị Biên (Edge Node)
    participant BE as Central Backend (FastAPI + PostgreSQL)
    actor Op as Điều Hành Viên (Bước 1)
    actor Police as Cán Bộ CSGT (Bước 2)
    actor Public as Người Dân / Toà Án

    Edge->>BE: Gửi sự kiện + gói bằng chứng đã ký số qua HTTPS (thử lại tới khi có xác nhận)
    BE->>BE: Xác thực chữ ký Ed25519, chống trùng theo event_id, lưu cơ sở dữ liệu
    
    Note over BE,Op: BƯỚC 1: SƠ DUYỆT TRÊN BẢN BẢO VỆ QUYỀN RIÊNG TƯ
    BE->>Op: Đẩy sự kiện vào Hàng đợi sơ duyệt Bước 1
    Op->>BE: Xem bản bằng chứng CHE MỜ 100% BIỂN SỐ & MẶT
    alt Báo nhầm (False Positive)
        Op->>BE: Bác bỏ & Chọn mã lý do (A1-E5) -> Đóng hồ sơ, xóa gói bằng chứng theo chính sách lưu giữ
    else Vi phạm thực tế
        Op->>BE: Xác nhận hợp lệ -> Chuyển tiếp sang Bước 2
    end

    Note over BE,Police: BƯỚC 2: THẨM ĐỊNH & XỬ PHẠT CHÍNH THỨC
    BE->>Police: Kích hoạt hồ sơ trên Hàng đợi thẩm định CSGT
    Police->>BE: Mở xem bản bằng chứng HIỆN BIỂN SỐ XE VI PHẠM
    BE->>BE: Ghi nhận Audit Log bắt buộc (User, IP, Timestamp)
    alt Không đủ yếu tố xử phạt
        Police->>BE: Bác bỏ hồ sơ vi phạm
    else Đủ căn cứ pháp lý
        Police->>BE: Phê duyệt -> Ghi nhận chính thức, xuất hồ sơ cho quy trình phạt nguội (FR-EXP-1, CP2)
    end

    Note over Public,BE: TRA CỨU & XÁC MINH CÔNG KHAI
    Public->>BE: Nhập mã vụ việc / Tải file bằng chứng lên Cổng dịch vụ công
    BE->>Public: Đối soát mã băm SHA-256 & Chữ ký Ed25519 -> Báo cáo tính toàn vẹn 100%
```

**Vòng đời một vi phạm** (trạng thái lưu ở PH6):

```mermaid
stateDiagram-v2
  [*] --> Candidate: edge tạo ứng viên
  Candidate --> OperatorRejected: điều hành viên bác bỏ
  Candidate --> OperatorConfirmed: điều hành viên xác nhận
  OperatorConfirmed --> CsgtRejected: CSGT bác bỏ
  OperatorConfirmed --> Confirmed: CSGT xác nhận (ghi nhận chính thức)
  OperatorRejected --> [*]: xóa gói bằng chứng
  CsgtRejected --> [*]: xóa gói bằng chứng
  Confirmed --> [*]: lưu theo thời hạn quy định
```

---

## 4. Bảng chi tiết các thành phần công nghệ (Component Details)

| Thành phần | Công nghệ / Thư viện | Vai trò và chức năng trong TrafficEye Edge |
|---|---|---|
| **Camera Ingestion** | OpenCV / FFmpeg (RTSP) | Thu nhận luồng video H.264/H.265 (1080p @ 15–20 FPS), tự kết nối lại khi đứt luồng. |
| **Vehicle Detection** | YOLO (tối ưu hóa cho Edge) | Phát hiện 4 loại phương tiện: xe máy, ô tô con, xe buýt, xe tải. |
| **Object Tracking** | ByteTrack | Gán Track ID liên tục, bám vết quỹ đạo chuyển động, xử lý che khuất ngắn hạn. |
| **Counting & Rule Engine** | Hình học phẳng + State Machine | Đếm xe qua vạch ảo theo làn; máy trạng thái đèn; lớp ngữ cảnh có mã lý do; các luật vi phạm tất định dạng plugin (RL, WW, LN). Cấu hình cảnh được kiểm tra hình học khi nạp (spec 6.1). |
| **Privacy & Sealing** | OpenCV + Cryptography | Tự động làm mờ mặt và biển số. Tạo bản điều hành viên và bản CSGT để gửi đi; bản đầy đủ niêm phong, giữ trên thiết bị. Băm SHA-256 và ký số Ed25519. Tỉ lệ biển số, khuôn mặt bị lọt được đo kèm Wilson 95% (spec FR-PRV). |
| **Edge Storage** | SQLite Outbox | Cơ sở dữ liệu hàng đợi cục bộ tại biên, lưu đệm metadata và bằng chứng khi mất kết nối mạng. |
| **Transport Layer** | HTTPS (M1 chạy HTTP trên localhost; TLS qua reverse proxy từ CP2). Từ CP2, MQTT chỉ làm kênh điều khiển | Worker chạy nền đồng bộ dữ liệu từ Outbox về Backend qua HTTPS REST API; không truyền video thô. |
| **Central Backend** | FastAPI + SQLAlchemy | RESTful API Gateway, xác thực chữ ký số Ed25519, điều phối hàng đợi duyệt 2 bước, ghi Audit Log. |
| **Database** | PostgreSQL | Lưu trữ metadata lưu lượng xe theo phút, hồ sơ sự kiện vi phạm và nhật ký kiểm toán. |
| **Central Frontend** | Next.js + TailwindCSS | Live Traffic Dashboard, màn hình duyệt Bước 1 (Operator), màn hình thẩm định Bước 2 (CSGT). |
| **Verification Portal** | Next.js (Web công khai) | Cổng thông tin cho người dân đối soát tính toàn vẹn và chữ ký số của hồ sơ phạt nguội. |
| **AI Reporting Agent** | LangGraph | Công cụ chỉ đọc số liệu tổng hợp, không trả biển số hay ảnh. Soạn bản nháp báo cáo; người duyệt mới phát hành (`interrupt()`). Không gọi được LLM thì sinh báo cáo theo mẫu. Agent không quyết định vi phạm (spec FR-AGT-1). |
