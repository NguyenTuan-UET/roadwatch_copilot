---
doc_id: "RW-ARCH-VIEW"
doc_type: "view"
status: "active"
authority_for: []
---

# RoadWatch Copilot: sơ đồ kiến trúc

> Deliverable 3 của môn học: bản trực quan của sản phẩm đã nộp trên `main`, khớp [README](../README.md). **Nguồn chuẩn** về kiến trúc và hợp đồng dữ liệu là [spec kiến trúc](specs/roadwatch-architecture.md); nếu hai nơi khác nhau thì spec thắng. Điểm khác giữa sản phẩm đã nộp và thiết kế engine đầy đủ của spec: spec 12.4.

**Một câu:** điện thoại gắn kính lái chạy offline ngay trên máy.
- Camera → **BT-A** (CV) đo khoảng cách tới xe dẫn đầu cùng làn.
- → **BT-B** (luật và máy trạng thái theo khoảng cách, không dùng LLM, không dùng TTC) chọn có nhắc hay không, nhắc mức nào.
- → chuông, câu tiếng Việt thu sẵn hoặc tiếng bíp; HUD hiện khoảng cách và thảm làn.

**Chú giải chung:** nét liền là phần đã có trên `main`; nét đứt là đường tùy chọn.

## 1. Thành phần

Hai đường chạy dùng chung một thiết kế: **laptop/server** (Python) và **điện thoại** (JavaScript, chạy offline). Bản JS được kiểm khớp với Python bằng dữ liệu chuẩn xuất từ Python (README mục 6).

```mermaid
flowchart LR
  subgraph IN["Đầu vào"]
    CAM["Camera điện thoại<br/>hoặc video hành trình"]
    GPS["GPS điện thoại<br/>hoặc log GPS (tùy chọn)"]
  end
  subgraph BTA["BT-A · Nhận thức"]
    PREP["Nắn ảnh vào khung model<br/>YUV 6 kênh"]
    CAL["Tự hiệu chuẩn<br/>góc camera, tiêu cự"]
    MODEL["gr14VinAI<br/>ONNX Runtime CPU / WebGPU"]
    LANE["Chọn xe cùng làn<br/>vạch làn hoặc đường đi"]
    KF["Kalman + làm mượt theo thời gian<br/>khoảng cách tới cản trước"]
  end
  subgraph BTB["BT-B · Quyết định"]
    RULE["Ngưỡng theo tốc độ<br/>Thông tư 38/2024"]
    EP["Xác nhận, đợt nhắc,<br/>nhắc lại, kết thúc đợt"]
  end
  subgraph OUT["Đầu ra"]
    HUD["HUD: khoảng cách ± σ, tốc độ, thảm làn"]
    VOICE["Chuông / câu tiếng Việt / ba tiếng bíp"]
    LOG["Video chú thích, decisions.json, run.json"]
  end

  CAM --> PREP --> MODEL --> LANE --> KF --> RULE --> EP
  CAL --> PREP
  MODEL -- "road_transform, pose" --> CAL
  GPS -. "tốc độ xe" .-> RULE
  EP --> HUD
  EP --> VOICE
  EP --> LOG
```

**Đọc sơ đồ:**
- **BT-A** chọn xe dẫn đầu khi `lead_prob ≥ 0,5` và xe nằm trong làn của mình, kể cả khi vào cua; `gap = khoảng cách đã lọc − khoảng cách camera tới cản trước`. Khi chưa hiệu chuẩn xong hoặc ảnh không phủ đủ khung model, không cảnh báo khoảng cách.
- **Tốc độ xe mình** lấy từ GPS khi có, nếu không thì ước lượng từ `pose` của model (spec D-24).
- **BT-B** chỉ dựa trên khoảng cách và xu hướng khoảng cách: nhắc sớm (`info`), cảnh báo (`warning`, đúng mức luật từ 60 km/h), Khẩn cấp (`emergency`, thiếu nhiều hoặc khoảng cách giảm nhanh), chuông (`chime`) khi vùng nhắc sớm vượt tầm đo 100 m. Dưới 20 km/h im lặng. Luật đầy đủ: spec 3.5, 3.7; bảng ngưỡng: README mục 3.

## 2. Trình tự xử lý một khung

```mermaid
sequenceDiagram
  autonumber
  participant SRC as Camera hoặc video
  participant A as BT-A
  participant B as BT-B
  participant UI as HUD và loa
  Note over SRC,UI: Thời gian lấy từ đồng hồ khung (khoảng 20 Hz), không đọc giờ hệ thống trong BT-B.
  SRC->>A: Khung ảnh (và tốc độ GPS nếu có)
  A->>A: Nắn ảnh theo hiệu chuẩn, chạy gr14VinAI, cập nhật hiệu chuẩn
  A->>A: Chọn xe cùng làn, Kalman, tính gap tới cản trước
  A->>B: gap, tốc độ xe mình, đã hiệu chuẩn hay chưa, khung tin cậy hay không
  B->>B: Tính ngưỡng theo tốc độ, xác nhận mức, cập nhật đợt nhắc
  B->>UI: Mức hiện tại, âm cần phát ở khung này (nếu có), lý do
  opt Có âm cần phát
    UI->>UI: Phát chime, info, warning hoặc emergency
  end
```

- **Chống báo giả:** xe phải được thấy liên tục 0,5 s; mỗi mức giữ 0,5 s (Khẩn cấp 0,2 s) mới phát; mức cao hơn phát ngay; nhắc lại sau 3 s rồi mỗi 10 s khi chưa giãn ra; đợt kết thúc khi rời vùng nhắc 3 s hoặc mất xe 3 s (spec 3.5).

## 3. Ranh giới triển khai

```mermaid
flowchart TB
  subgraph PHONE["Điện thoại · /phone, chạy offline sau lần tải đầu"]
    PJS["onnxruntime-web 1.20.1, WebGPU + graph capture<br/>bản JS của BT-A, BT-B (ui/onphone/)"]
    SW["Service worker, Cache Storage<br/>model và âm báo"]
  end
  subgraph SERVER["Server FastAPI · web.py"]
    API["API, WebSocket/SSE, WebRTC<br/>/app, /phone, /docs, /health"]
    JOB["job.py: BT-A Python + decide.py"]
    RUNS[("runs/: video chú thích, decisions.json, run.json")]
  end
  subgraph HOST["Nơi chạy server"]
    VERCEL["Vercel<br/>c4-app-014.vercel.app"]
    LOCAL["Laptop hoặc Docker<br/>127.0.0.1:8765"]
  end

  API --> JOB --> RUNS
  SERVER --- VERCEL
  SERVER -. "chạy local" .- LOCAL
  PHONE -. "tải app, model, âm báo một lần" .-> API
```

- **Điện thoại** chạy toàn bộ pipeline ngay trên máy; ảnh không rời khỏi máy (README mục 6).
- **Server** phục vụ web app, API và đường gửi ảnh từ điện thoại về server (tùy chọn). Bản triển khai: [c4-app-014.vercel.app](https://c4-app-014.vercel.app/); chạy local hoặc Docker theo README mục 7.

## 4. Thành phần, file code và mục trong spec

| Thành phần | Laptop / server | Điện thoại (`/phone`) | Mục trong spec |
|---|---|---|---|
| Suy luận gr14VinAI | `src/roadwatch/model.py` | `ui/onphone/captured.mjs` (GPU), `inference.mjs` (CPU) | 2, 12.2 (I-26) |
| Nắn ảnh, hiệu chuẩn | `model.py`, `calibration.py` | `ui/onphone/gpuprep.mjs`, `prep.mjs` | 4.2, 12.2 (I-20…I-24) |
| Chọn xe cùng làn, Kalman | `pipeline.py`, `temporal.py` | `ui/onphone/lanes.mjs`, `track.mjs` | 4.2 |
| BT-B | `decide.py` | `ui/onphone/decide.mjs` | 3.5, 3.7, 12.4 (D-21) |
| HUD | `hud.py` | `ui/onphone/geometry.mjs` | — |
| Giao diện, API | `web.py`, `schemas.py`, `ui/` | `phone.html`, `phone.js`, `sw.js` | 11.5, 12.4 (D-25); [roadwatch-api.md](specs/roadwatch-api.md) |

Thiết kế engine đầy đủ (hợp đồng `contracts`, runtime nhiều thread, baseline, bộ phân xử audio, `rerun-B`) có sơ đồ riêng ở spec mục 2; phần này chưa có trên `main` (spec 12.4, D-20).
