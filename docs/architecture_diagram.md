---
doc_id: "RW-ARCH-VIEW"
doc_type: "view"
status: "active"
authority_for: []
---

# RoadWatch Copilot: sơ đồ kiến trúc

> Deliverable 3 của môn học: bản trực quan tóm tắt. **Nguồn chuẩn** về kiến trúc và hợp đồng dữ liệu là [spec kiến trúc](specs/roadwatch-architecture.md); nếu hai nơi khác nhau thì spec thắng.
>
> **Mức độ chốt:**
> - Sơ đồ vẽ theo thiết kế của spec: v1.0 đã được PO duyệt ngày 28/09; v1.1 được PO duyệt ngày 29/09 (web UI thuộc ADR-13).
> - Sơ đồ **không** cho biết code đã làm tới đâu. Tình trạng code thực tế nằm ở [spec](specs/roadwatch-architecture.md), mục 12.4.

**Một câu:** thiết bị gắn kính (điện thoại) chạy offline ngay trên máy.
- Camera → **BT-A** (CV) đo khoảng cách tới xe phía trước.
- → **BT-B** (luật và máy trạng thái, không dùng LLM) chọn có nói hay không, nói câu gì.
- → loa phát câu tiếng Việt thu sẵn.

**Chú giải chung:**
- Nét liền: phần của bản nộp MVP (tuần 1).
- Nét đứt: phần mở rộng tuần 2–4, đường dự phòng, hoặc việc chưa quyết.

## 1. Thành phần

### 1a. Runtime: thread, hàng đợi, file

```mermaid
flowchart TB
  subgraph DATA["Dữ liệu vào: file cục bộ"]
    VID[("Video cao tốc")]
    SESS[("Session manifest")]
    GPSF[("GPS CSV chuẩn")]
  end
  subgraph CFG["configs/: đọc một lần khi khởi động"]
    ACT[/"active.json"/]
    VER[("versions/")]
  end
  subgraph RT["Runtime: 1 process"]
    SV["source.video<br/>khung theo lịch process_hz"]
    SG["source.gps<br/>mẫu theo t_recv"]
    PA["perception = BT-A<br/>tự hiệu chuẩn → warp → gr14VinAI → xe dẫn đầu<br/>distance_m · ttc_s · calibration · observation · mount_check"]
    subgraph DEC["decision: hàm thuần"]
      JN["Nhật ký đầu vào"]
      J["join<br/>tốc độ · ngưỡng · headway"]
      B["BT-B<br/>năng lực · các đợt · guardrail"]
      BL["Baseline<br/>sườn lên"]
      ARB["Phân xử audio của B"]
      ARL["Phân xử audio của baseline<br/>(mô phỏng)"]
    end
    SNK["audio sink<br/>(chỉ live)"]
    SUP["supervisor<br/>nhịp tim · hang_timeout"]
    LOG["logger"]
  end
  DRV(("Tài xế"))
  RUNS[("runs/#lt;run_id#gt;/<br/>JSONL · run_manifest.json")]
  HB[/"heartbeat.json (chỉ live)"/]

  VID --> SV
  SESS --> SV
  SESS --> SG
  GPSF --> SG
  CFG -- "kiểm hash, phê duyệt;<br/>đóng băng" --> RT
  SV -- "FrameMeta + ảnh<br/>hàng đợi khung (sức chứa 1)" --> PA
  PA -- "Measurement<br/>hàng đợi số đo" --> JN
  SG -- "SpeedSample<br/>hàng đợi GPS" --> JN
  SUP -- "SystemEvent" --> JN
  JN -- "tick theo đồng hồ phiên" --> JN
  JN --> J
  J --> B
  J --> BL
  B -- "AlertDecision" --> ARB
  BL -- "AlertDecision" --> ARL
  ARB -- "AudioPlan started → lệnh phát" --> SNK
  SNK -- "câu nói" --> DRV
  SUP -. "system_off khi decision chết (F19)" .-> SNK
  SV & PA & DEC & SNK & SUP -.-> LOG
  LOG --> RUNS
  SUP --> HB
```

**Đọc sơ đồ:**
- **Nhật ký đầu vào.** Mọi đầu vào của `decision` được ghi vào nhật ký đầu vào **trước khi xử lý**, đúng thứ tự xử lý. Có bốn loại: số đo, tốc độ, sự kiện hệ thống, và tick do chính `decision` sinh theo đồng hồ phiên. Nhờ vậy tái lập được B mà không cần chạy lại A (spec 3.3, 5.4).
- **Logger.** Đường chấm tới logger nghĩa là mọi thread ghi bản ghi qua hàng đợi log. Tràn log thì lần chạy bị đánh dấu không hợp lệ để đánh giá, nhưng đường nóng không bị chặn (spec 3.2).
- **Hàng đợi.**
  - Ở live, hàng đợi khung, số đo và GPS khi đầy thì bỏ bản ghi cũ nhất và ghi một `SystemEvent`: `frame_dropped`, `measurement_dropped` hoặc `speed_dropped`.
  - Ở replay thì không bỏ gì (spec 3.2). Code hiện chạy replay tuần tự trong một thread (D-2).
- **Ra loa.** Ở live, chỉ bộ quyết định chính được nối ra loa. Mặc định là B; trường `active_arbiter` trong `run_manifest` cho biết bộ nào. Bộ còn lại chạy shadow qua bộ phân xử mô phỏng (spec 2).
- **Supervisor.** Khi thấy thread chết hoặc treo, supervisor gửi `system_fault` vào `decision`; `decision` tắt cả hai năng lực cảnh báo. Nếu chính `decision` chết, supervisor tự phát câu "Hệ thống cảnh báo tạm dừng", nhưng chỉ khi audio còn chạy (spec 3.8, F19).

### 1b. Web UI

```mermaid
flowchart LR
  RUNS[("runs/#lt;run_id#gt;/")]
  HB[/"heartbeat.json"/]
  UI["Web UI cục bộ<br/>(tuần 2–4)"]
  ENG(("Kỹ sư"))

  ENG -.-> UI
  UI -. "đọc" .-> RUNS
  UI -. "đọc" .-> HB

  classDef ext stroke-dasharray: 5 5
  class UI ext
```

- **Web UI** thuộc tuần 2–4 (ADR-13, PO duyệt 29/09); chỉ đọc kết quả lần chạy, không sửa cấu hình.

## 2. Trình tự một lần xử lý (live, B là bộ quyết định chính)

```mermaid
sequenceDiagram
  autonumber
  participant SG as source.gps
  participant SV as source.video
  participant PA as perception (BT-A)
  participant DE as decision (join · BT-B · baseline · phân xử)
  participant SK as audio sink
  participant LG as logger
  Note over SG,LG: Mọi mốc t_* theo đồng hồ phiên. Ngoài ra chỉ có các mốc *_mono_ns dùng để đo latency ở live.
  SG->>DE: SpeedSample khi tới t_recv (hàng đợi GPS)
  DE->>LG: SpeedSample và DecisionInput kind=speed
  SV->>SV: Mốc s_n: lấy khung có PTS lớn nhất và không vượt s_n
  SV->>LG: FrameMeta
  SV->>PA: FrameMeta + ảnh (hàng đợi khung, sức chứa 1)
  opt Hàng đợi khung đầy (chỉ live)
    SV->>LG: SystemEvent frame_dropped
  end
  PA->>PA: Warp theo hiệu chuẩn, gr14VinAI, cập nhật hiệu chuẩn, distance_m, ttc_s, observation, mount_check
  PA->>LG: Measurement (t_k)
  PA->>DE: Measurement qua hàng đợi số đo
  DE->>DE: Ghi nhật ký đầu vào với t_consumed, kiểm tuổi số đo
  DE->>DE: join chỉ dùng tốc độ có t_recv không vượt t_k, rồi tính độ mới, ngưỡng, headway
  DE->>DE: BT-B xét năng lực, các đợt cảnh báo, guardrail. Baseline xét sườn lên
  DE->>LG: DecisionTrace cho B và cho baseline, perf (chỉ live)
  opt Có cảnh báo hoặc lời báo trạng thái
    DE->>LG: AlertDecision và AudioPlan của từng bộ
    alt AudioPlan của B là started
      DE->>SK: Lệnh phát (alert_id, phrase_id, hạn)
      alt Còn hạn
        SK->>SK: Phát WAV thu sẵn
        SK->>LG: AudioEvent started
      else Quá hạn
        SK->>LG: AudioEvent dropped_stale (một vi phạm latency)
      end
    end
  end
  loop Mỗi tick_period
    DE->>DE: Tick: xét hết hạn, HOLD, debounce, nhắc lại
    DE->>LG: DecisionInput kind=tick
  end
```

- **Replay** gọi đúng các hàm trên nhưng:
  - không chờ theo thời gian thực và không bỏ bản ghi nào;
  - `t_consumed = t_k`;
  - không có audio sink, `perf` hay `audio_events` (spec 3.3, 5.3).
- **Guardrail Khẩn cấp:** khi `cap_ttc = on`, `ttc_s` `ok` và không vượt ngưỡng, B phát ngay ở khung bắt đầu đợt. Trong cùng đợt, chỉ phát lại khi chưa lệnh Khẩn cấp nào `started`, lệnh gần nhất bị huỷ hoặc hết hạn và không còn lệnh đang chờ. Không tham số nào được chặn hai trường hợp bắt buộc phát; không nhắc theo chu kỳ (spec 3.7, OQ-B12).

## 3. Ranh giới triển khai

```mermaid
flowchart TB
  subgraph LAP["Laptop (máy demo hoặc máy phát triển), offline"]
    subgraph PRT["Process runtime · tuần 1"]
      RTN["source · BT-A · decision · audio sink · logger · supervisor"]
    end
    subgraph PWEB["Process web UI · tuần 2–4"]
      WEB["FastAPI cục bộ<br/>màn hình kỹ sư · màn hình tài xế"]
    end
    subgraph FS["File cục bộ, không commit"]
      DATA[("data/: video, GPS, manifest, nhãn")]
      MOD[("models/: ONNX, WAV câu nói")]
      CONF[("configs/: cấu hình")]
      RUNS[("runs/: JSONL, run_manifest, heartbeat.json")]
    end
    SPK(("Loa"))
  end
  subgraph GIT["Git repo"]
    CODE["src/roadwatch · tests/roadwatch · docs"]
  end
  NET["Live URL<br/>chưa quyết (OQ-E1)"]

  DATA --> RTN
  MOD --> RTN
  CONF -- "chỉ đọc" --> RTN
  RTN --> RUNS
  RTN --> SPK
  RUNS -.-> WEB
  CODE -. "cài đặt" .-> RTN
  WEB -. "?" .-> NET

  style PWEB stroke-dasharray: 5 5
  classDef ext stroke-dasharray: 5 5
  class WEB,NET ext
```

- **Runtime** chạy offline hoàn toàn và không phụ thuộc web UI. Số đo hiệu năng dùng để nghiệm thu chỉ lấy trên máy demo đã chốt (WP-P2).
- **Web UI** thuộc tuần 2–4 (ADR-13); giao diện là HTML render từ FastAPI (OQ-E2).
- **Live URL** chưa quyết (OQ-E1).

## 4. Thành phần và mục tương ứng trong spec

| Thành phần | Làm gì | Mục trong spec |
|---|---|---|
| `source` | Phát video theo lịch `process_hz`, GPS theo `t_recv`, bản ghi giữ chỗ khi biết chắc không có khung | 2, 3.1, 3.3 |
| BT-A perception | Tự hiệu chuẩn camera, warp, gr14VinAI, xe dẫn đầu, khoảng cách, làn, kiểm tra ảnh, phát hiện lắp lại | 2, 4.2 |
| `join` | Ghép số đo với tốc độ theo mốc cắt thông tin; độ mới của tốc độ, ngưỡng, headway | 3.3 |
| BT-B decision | Năng lực cảnh báo, các đợt cảnh báo có `HOLD`, guardrail Khẩn cấp, lời báo trạng thái | 3.4–3.7 |
| Baseline | Cảnh báo theo sườn lên, cùng đầu vào với B, để so sánh | 2, 5.5 |
| Phân xử audio + audio sink | Một câu đang phát, một ô chờ; chỉ cảnh báo nguy hiểm mới được ngắt câu đang phát; sink bỏ lệnh quá hạn | 3.6 |
| Supervisor, logger | Nhịp tim, `system_fault`, `heartbeat.json`; ghi JSONL không chặn đường nóng | 3.2, 3.8 |
| Web UI (tuần 2–4) | Màn hình kỹ sư và màn hình trạng thái cho tài xế | 11.5 |
