# SƠ ĐỒ KIẾN TRÚC HỆ THỐNG — TRAFFICEYE EDGE

> **Trạng thái:** Bản kiến trúc chuẩn hóa chính thức của dự án TrafficEye Edge  
> **Căn cứ:** [docs/spec/trafficeye-spec.md](spec/trafficeye-spec.md) và [docs/report/trafficeye-edge-report.md](report/trafficeye-edge-report.md)

---

## 1. Kiến trúc tổng quan hệ thống (System Overview)

Hệ thống hoạt động theo mô hình **Edge AI First** kết hợp **Phê duyệt 2 bước có con người kiểm soát (Two-Step HITL)**:
- **Thiết bị biên (Edge Node):** Xử lý toàn bộ video tại chỗ, phát hiện, bám vết, đếm xe và kiểm tra 6 điều kiện vi phạm tất định. Tuyệt đối **không truyền video thô về trung tâm**.
- **Trung tâm (Central Backend):** Tiếp nhận metadata số đếm và các gói bằng chứng đã được ký số; quản lý hàng đợi duyệt vi phạm và xuất biên bản.

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

    subgraph S1 ["📹 1. PHẦN CỨNG TẠI NÚT GIAO"]
        CAM["<b>Camera Nút Giao</b><br/>(Góc nhìn sau đuôi xe)"]:::hwNode
        RTSP["<b>Luồng RTSP 1080p</b><br/>(15-20 FPS)"]:::hwNode
        CAM --> RTSP
    end

    subgraph S2 ["⚡ 2. THIẾT BỊ BIÊN (EDGE NODE: LAPTOP / JETSON ORIN)"]
        DEC["<b>YOLO Vehicle Detector</b><br/>(Xe máy, Ô tô, Buýt, Tải)"]:::aiNode
        TRK["<b>ByteTrack Tracker</b><br/>(Gán & duy trì Track ID)"]:::aiNode
        CNT["<b>Virtual Counting Line</b><br/>(Đếm xe theo làn & hướng)"]:::aiNode
        TLSM["<b>Traffic Light State Machine</b><br/>(Đỏ / Vàng / Xanh / Nhấp nháy)"]:::ruleNode
        V_GATE{"<b>Cổng 6 điều kiện vi phạm</b><br/>(Loại trừ A1-E5)"}:::ruleNode
        BLUR["<b>Privacy Masker</b><br/>(Làm mờ biển số & mặt)"]:::secNode
        SEAL["<b>Evidence Sealer</b><br/>(3 ảnh + clip 4s | Ký Ed25519)"]:::secNode
        OUTBOX[("<b>SQLite Outbox</b><br/>(Lưu đệm offline)")]:::dbNode

        RTSP --> DEC --> TRK --> CNT --> OUTBOX
        RTSP --> TLSM
        TRK --> V_GATE
        TLSM --> V_GATE
        V_GATE -->|Vi phạm hợp lệ| BLUR --> SEAL --> OUTBOX
    end

    subgraph S3 ["🌐 3. ĐƯỜNG TRUYỀN BẢO MẬT"]
        SYNC["<b>HTTPS Sync Worker</b><br/>(Chỉ gửi metadata & bằng chứng)"]:::netNode
        OUTBOX --> SYNC
    end

    subgraph S4 ["🏢 4. HẠ TẦNG TRUNG TÂM (CENTRAL BACKEND)"]
        API["<b>FastAPI Gateway</b><br/>(REST API / WebSocket)"]:::beNode
        VERIFY["<b>Ed25519 Verifier</b><br/>(Xác thực tính toàn vẹn)"]:::beNode
        AUDIT["<b>Audit Trail Logger</b><br/>(Nhật ký truy cập)"]:::beNode
        DB[("<b>PostgreSQL</b><br/>+ Evidence Storage")]:::dbNode

        SYNC --> API
        API --> VERIFY --> DB
        API --> AUDIT
    end

    subgraph S5 ["👥 5. GIAO DIỆN & PHÊ DUYỆT (NEXT.JS DASHBOARD)"]
        DASH["<b>Live Traffic Monitor</b><br/>(Đếm xe, mật độ thời gian thực)"]:::hitlNode
        STEP1["<b>Sơ duyệt Bước 1</b><br/>(Điều hành viên: Bản ẩn 100% biển số)"]:::hitlNode
        STEP2["<b>Thẩm định Bước 2</b><br/>(Cán bộ CSGT: Bản rõ biển số xe vi phạm)"]:::hitlNode
        PORTAL["<b>Cổng Tra Cứu Công Khai</b><br/>(Người dân kiểm tra chữ ký số)"]:::hitlNode
        AGENT["<b>AI Reporting Assistant</b><br/>(LangGraph tổng hợp báo cáo)"]:::aiNode

        DB --> DASH
        DB --> STEP1
        STEP1 -->|Hợp lệ| STEP2
        STEP2 -->|Xuất biên bản phạt| DB
        DB --> PORTAL
        DB --> AGENT
    end

    style S1 fill:#0f172a,stroke:#64748b,stroke-width:2px,color:#cbd5e1
    style S2 fill:#022c44,stroke:#0288d1,stroke-width:2.5px,color:#38bdf8
    style S3 fill:#1c1917,stroke:#facc15,stroke-width:2px,color:#fde047
    style S4 fill:#03291f,stroke:#22c55e,stroke-width:2.5px,color:#4ade80
    style S5 fill:#2a0818,stroke:#fb7185,stroke-width:2.5px,color:#f472b6
```

---

## 2. Luồng xử lý chi tiết tại Biên (Edge Pipeline Flow)

Luồng xử lý thời gian thực từ khi nhận khung hình camera đến khi đưa ra quyết định vi phạm hoặc đếm xe:

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
    MASK --> SIGN["Tạo 2 gói bằng chứng + Ký Ed25519 & Băm SHA-256"]:::vioNode
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

    Edge->>BE: Gửi gói bằng chứng đã ký số qua HTTPS
    BE->>BE: Xác thực chữ ký số Ed25519 & Lưu trữ cơ sở dữ liệu
    
    Note over BE,Op: BƯỚC 1: SƠ DUYỆT TRÊN BẢN BẢO VỆ QUYỀN RIÊNG TƯ
    BE->>Op: Đẩy sự kiện vào Hàng đợi sơ duyệt Bước 1
    Op->>BE: Xem bản bằng chứng CHE MỜ 100% BIỂN SỐ & MẶT
    alt Báo nhầm (False Positive)
        Op->>BE: Bác bỏ & Chọn mã lý do (A1-E5) -> Đóng hồ sơ
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
        Police->>BE: Phê duyệt xử phạt -> Xuất biên bản phạt nguội chính thức
    end

    Note over Public,BE: TRA CỨU & XÁC MINH CÔNG KHAI
    Public->>BE: Nhập mã vụ việc / Tải file bằng chứng lên Cổng dịch vụ công
    BE->>Public: Đối soát mã băm SHA-256 & Chữ ký Ed25519 -> Báo cáo tính toàn vẹn 100%
```

---

## 4. Bảng chi tiết các thành phần công nghệ (Component Details)

| Thành phần | Công nghệ / Thư viện | Vai trò và chức năng trong TrafficEye Edge |
|---|---|---|
| **Camera Ingestion** | OpenCV / FFmpeg (RTSP) | Thu nhận luồng video H.264/H.265 (1080p @ 15–20 FPS), tự kết nối lại khi đứt luồng. |
| **Vehicle Detection** | YOLO (tối ưu hóa cho Edge) | Phát hiện 4 loại phương tiện: xe máy, ô tô con, xe buýt, xe tải. |
| **Object Tracking** | ByteTrack | Gán Track ID liên tục, bám vết quỹ đạo chuyển động, xử lý che khuất ngắn hạn. |
| **Counting & Rule Engine** | Hình học phẳng + State Machine | Đếm xe qua vạch ảo theo làn; phân tích máy trạng thái đèn; kiểm tra 6 điều kiện vi phạm tất định. |
| **Privacy & Sealing** | OpenCV + Cryptography | Tự động làm mờ mặt và biển số; tạo 2 gói bằng chứng; băm SHA-256 và ký số Ed25519. |
| **Edge Storage** | SQLite Outbox | Cơ sở dữ liệu hàng đợi cục bộ tại biên, lưu đệm metadata và bằng chứng khi mất kết nối mạng. |
| **Transport Layer** | HTTP Client (TLS 1.3) | Worker chạy nền đồng bộ dữ liệu từ Outbox về Backend qua HTTPS REST API; không truyền video thô. |
| **Central Backend** | FastAPI + SQLAlchemy | RESTful API Gateway, xác thực chữ ký số Ed25519, điều phối hàng đợi duyệt 2 bước, ghi Audit Log. |
| **Database** | PostgreSQL | Lưu trữ metadata lưu lượng xe theo phút, hồ sơ sự kiện vi phạm và nhật ký kiểm toán. |
| **Central Frontend** | Next.js + TailwindCSS | Live Traffic Dashboard, màn hình duyệt Bước 1 (Operator), màn hình thẩm định Bước 2 (CSGT). |
| **Verification Portal** | Next.js (Web công khai) | Cổng thông tin cho người dân đối soát tính toàn vẹn và chữ ký số của hồ sơ phạt nguội. |
| **AI Reporting Agent** | LangGraph + OpenAI/Gemini | Trợ lý phân tích dữ liệu lưu lượng từ PostgreSQL và tự động soạn thảo báo cáo giao thông bằng ngôn ngữ tự nhiên. |
