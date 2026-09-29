# RoadWatch Copilot: sơ đồ kiến trúc

> Deliverable 3 của môn học: bản trực quan tóm tắt. **Nguồn chuẩn** về kiến trúc và hợp đồng dữ liệu là [spec kiến trúc](specs/roadwatch-architecture.md); nếu hai nơi khác nhau thì spec thắng.
>
> **Mức độ chốt:**
> - Sơ đồ vẽ theo thiết kế của spec: v1.0 đã được PO duyệt ngày 28/09; các phần gắn nhãn [v1.1] đang chờ duyệt (web UI thuộc ADR-13).
> - Sơ đồ **không** cho biết code đã làm tới đâu. Tình trạng code thực tế nằm ở [kế hoạch, mục 3](plan/README.md).

**Một câu:** thiết bị gắn kính chạy offline trên CPU laptop.
- Camera → **BT-A** (CV) đo khoảng cách và TTC tới xe phía trước.
- → **BT-B** (luật và máy trạng thái, không dùng LLM) chọn có nói hay không, nói câu gì.
- → loa phát câu tiếng Việt thu sẵn.
- **BT-C** giữ cấu hình có phiên bản và có người duyệt (HITL), ghi log và chạy đánh giá.

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
    VER[("versions/ · approvals/")]
  end
  subgraph RT["Runtime: 1 process"]
    SV["source.video<br/>khung theo lịch process_hz"]
    SG["source.gps<br/>mẫu theo t_recv"]
    PA["perception = BT-A<br/>detector ONNX → tracker → xe dẫn đầu<br/>distance_m · ttc_s · observation · mount_check"]
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
- **Nhật ký đầu vào.** Mọi đầu vào của `decision` được ghi vào nhật ký đầu vào **trước khi xử lý**, đúng thứ tự xử lý. Có bốn loại: số đo, tốc độ, sự kiện hệ thống, và tick do chính `decision` sinh theo đồng hồ phiên. Nhờ vậy `rerun-B` tái lập được B mà không cần chạy lại A (spec 3.3, 5.4).
- **Logger.** Đường chấm tới logger nghĩa là mọi thread ghi bản ghi qua hàng đợi log. Tràn log thì lần chạy bị đánh dấu không hợp lệ để đánh giá, nhưng đường nóng không bị chặn (spec 3.2).
- **Hàng đợi.**
  - Ở live, hàng đợi khung, số đo và GPS khi đầy thì bỏ bản ghi cũ nhất và ghi một `SystemEvent`: `frame_dropped`, `measurement_dropped` hoặc `speed_dropped`.
  - Ở replay thì không bỏ gì (spec 3.2). Code hiện chạy replay tuần tự trong một thread (D-2).
- **Ra loa.** Ở live, chỉ bộ quyết định chính được nối ra loa. Mặc định là B; trường `active_arbiter` trong `run_manifest` cho biết bộ nào. Bộ còn lại chạy shadow qua bộ phân xử mô phỏng (spec 2).
- **Supervisor.** Khi thấy thread chết hoặc treo, supervisor gửi `system_fault` vào `decision`; `decision` tắt cả hai năng lực cảnh báo. Nếu chính `decision` chết, supervisor tự phát câu "Hệ thống cảnh báo tạm dừng", nhưng chỉ khi audio còn chạy (spec 3.8, F19).

### 1b. Công cụ BT-C và web UI

```mermaid
flowchart LR
  RUNS[("runs/#lt;run_id#gt;/")]
  HB[/"heartbeat.json"/]
  LBL[("Nhãn + dataset manifest")]
  subgraph CFG["configs/: kho cấu hình"]
    VER[("versions/ · reports/ · approvals/")]
    ACT[/"active.json"/]
    SQL[("hitl.sqlite")]
  end
  subgraph TOOLS["BT-C: công cụ CLI, process riêng"]
    RR["rerun-B<br/>đọc nhật ký đầu vào"]
    EV["Đánh giá<br/>khớp nhãn · recall · latency"]
    H["HITL<br/>propose · report · approve · activate · rollback · recover"]
  end
  UI["Web UI cục bộ<br/>(tuần 2–4)"]
  ENG(("Kỹ sư"))
  APR(("Người duyệt"))

  RUNS --> RR
  VER -. "cấu hình gốc hoặc cấu hình đề xuất" .-> RR
  RR -- "lần chạy mới: decisions · alerts · audio_plan" --> EV
  RUNS --> EV
  LBL --> EV
  EV -- "số liệu cho báo cáo tác động" --> H
  ENG -- "propose · report · activate" --> H
  APR -- "approve · rollback" --> H
  H -- "khoá + compare-and-swap + os.replace" --> CFG
  ENG -.-> UI
  APR -.-> UI
  UI -. "đọc" .-> RUNS
  UI -. "đọc" .-> HB
  UI -. "cùng hàm configstore" .-> H

  classDef ext stroke-dasharray: 5 5
  class UI ext
```

- **Chỉ các công cụ BT-C đụng SQLite.** Runtime chỉ đọc `active.json`, `versions/` và `approvals/` (spec 2, luật ranh giới 4). Code hiện vẫn import module `configstore` (D-13).
- **`reports/` và `roles.json`.** Code có hai file này nhưng spec 3.10 chưa liệt kê (D-12).
- **Web UI** thuộc tuần 2–4 (ADR-13, chờ duyệt). Web UI không có đường HITL riêng; mọi lệnh đi qua cùng các hàm mà CLI dùng.

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
  PA->>PA: Detector ONNX, tracker, chọn xe dẫn đầu, distance_m, ttc_s, observation, mount_check
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
- **`rerun-B`** đọc nhật ký đầu vào như đã ghi, rồi gọi lại `decision` để sinh `decisions`, `alerts`, `audio_plan`.
- **Guardrail Khẩn cấp:** khi `cap_ttc = on`, TTC `ok` và TTC không vượt ngưỡng thì B phát Khẩn cấp ngay tại khung đó. Không tham số nào được chặn hay hoãn cảnh báo này (spec 3.7). Việc có phát lại trong cùng một đợt hay không (đợt kéo dài, phục hồi từ `HOLD_E`, lệnh đầu bị huỷ trước khi phát) đang chờ PO chọn: spec 3.7, OQ-B12.

## 3. Trình tự HITL: từ đề xuất tới lần chạy sau

```mermaid
sequenceDiagram
  autonumber
  actor KS as Kỹ sư đề xuất
  participant CLI as CLI hitl (configstore)
  participant BC as Công cụ báo cáo (rerun-B, replay, live)
  actor ND as Người duyệt
  participant KHO as configs/ (versions, reports, approvals, active.json, SQLite)
  participant RT as Runtime (lần chạy sau)

  KS->>CLI: propose (file YAML cấu hình mới)
  CLI->>CLI: Validator: biên cứng, ngưỡng không thấp hơn bảng pháp lý, có legal_ref
  alt Không hợp lệ
    CLI-->>KS: Từ chối, nêu trường sai
  else Hợp lệ
    CLI->>KHO: versions/#lt;sha#gt;.yaml và đề xuất trong SQLite
  end
  KS->>CLI: report cho đề xuất
  CLI->>BC: Chạy trên bộ dev theo affects: [B] rerun-B, [A] replay, [A, live] thêm một lần live
  opt [A] hoặc [A, live], chạy thử cấu hình đề xuất (OQ-B13, CHỜ PO DUYỆT)
    BC->>KHO: Chỉ đọc versions/#lt;sha#gt;.yaml của đề xuất. Không ghi active.json, approvals hay SQLite
    BC->>BC: replay --proposed trên dev, live --proposed trên máy demo. run_manifest có cờ proposed_config và proposal_id, approval_id là null
  end
  BC-->>CLI: Số liệu trước và sau
  alt Working tree bẩn, thiếu lần live bắt buộc, dùng split test_* (D-11), hoặc lần chạy thử không khớp proposal_id và sha cấu hình
    CLI-->>KS: Từ chối báo cáo
  else Hợp lệ
    CLI->>KHO: reports/#lt;sha#gt;.json gắn hash cấu hình gốc, dataset, code, model, ONNX Runtime
  end
  ND->>CLI: approve (đề xuất, báo cáo)
  alt Người duyệt trùng người đề xuất, hoặc không có tên trong roles.json
    CLI-->>ND: Từ chối
  else Hợp lệ
    CLI->>KHO: approvals/#lt;approval_id#gt;.json (bất biến)
  end
  KS->>CLI: activate #lt;approval_id#gt;
  CLI->>KHO: Giữ khoá .hitl.lock và phục hồi bản pending cũ nếu có
  alt active.json đã đổi sau báo cáo, code hoặc dataset hoặc model không khớp, hoặc tree bẩn
    CLI-->>KS: Từ chối. Chạy report --rebase rồi duyệt lại
  else Hợp lệ
    CLI->>KHO: Ghi pending, os.replace active.json (điểm commit), đánh dấu committed
  end
  RT->>KHO: Lần chạy sau đọc active.json, version, approval (một lần)
  alt Hash sai, thiếu phê duyệt, hoặc người duyệt trùng người đề xuất
    RT-->>KS: Từ chối khởi động (F23)
  else Hợp lệ
    RT->>RT: Chạy với cấu hình đóng băng. run_manifest ghi approval_id
  end
  Note over CLI,KHO: Quay lui (rollback) do người duyệt chạy, dùng lại một phê duyệt đã từng active, vẫn qua khoá và compare-and-swap. Bị ngắt giữa chừng thì recover hoàn tất hoặc huỷ bản pending (F24).
```

- Lần chạy đang diễn ra không bị ảnh hưởng, vì cấu hình đã đóng băng từ lúc bắt đầu (spec 3.10).
- **Chạy thử cấu hình đề xuất** (khối `opt`) là đề xuất đang chờ PO duyệt (spec 3.10, OQ-B13). Lần chạy thử không kích hoạt gì, chỉ dùng cho báo cáo tác động, không bao giờ là bằng chứng nghiệm thu. Chạy thường vẫn từ chối cấu hình chưa duyệt (F23).
- Công cụ AI hỗ trợ lập trình không được chạy `approve`, `activate` hay `rollback` trên kho cấu hình thật ([AGENTS.md](../AGENTS.md), mục 1).

## 4. Ranh giới triển khai

```mermaid
flowchart TB
  subgraph LAP["Laptop (máy demo hoặc máy phát triển), offline"]
    subgraph PRT["Process runtime · tuần 1"]
      RTN["source · BT-A · decision · audio sink · logger · supervisor"]
    end
    subgraph PCLI["Process công cụ CLI · tuần 1"]
      CLI["roadwatch run · rerun-b · eval · perf · hitl · schema"]
    end
    subgraph PWEB["Process web UI · tuần 2–4"]
      WEB["FastAPI cục bộ<br/>màn hình kỹ sư · màn hình tài xế"]
    end
    subgraph FS["File cục bộ, không commit"]
      DATA[("data/: video, GPS, manifest, nhãn")]
      MOD[("models/: ONNX, WAV câu nói")]
      CONF[("configs/: versions, reports, approvals, active.json, hitl.sqlite")]
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
  CONF -- "chỉ đọc file, không đọc SQLite" --> RTN
  RTN --> RUNS
  RTN --> SPK
  RUNS --> CLI
  DATA --> CLI
  CLI -- "HITL: khoá + os.replace" --> CONF
  RUNS -.-> WEB
  WEB -. "cùng hàm configstore" .-> CONF
  CODE -. "cài đặt" .-> RTN
  CODE -. "cài đặt" .-> CLI
  WEB -. "?" .-> NET

  style PWEB stroke-dasharray: 5 5
  classDef ext stroke-dasharray: 5 5
  class WEB,NET ext
```

- **Runtime** chạy offline hoàn toàn và không phụ thuộc công cụ CLI hay web UI. Số đo hiệu năng dùng để nghiệm thu chỉ lấy trên máy demo đã chốt (WP-P2).
- **`configs/`** trên máy demo là kho cấu hình thật. Test và thử nghiệm dùng kho tạm ([quy tắc code](development/code-rules.md), mục 6).
- **Web UI** thuộc tuần 2–4 (ADR-13, chờ duyệt); công nghệ phía giao diện chờ OQ-E2.
- **Live URL** chưa quyết (OQ-E1).

## 5. Thành phần và mục tương ứng trong spec

| Thành phần | Làm gì | Mục trong spec |
|---|---|---|
| `source` | Phát video theo lịch `process_hz`, GPS theo `t_recv`, bản ghi giữ chỗ khi biết chắc không có khung | 2, 3.1, 3.3 |
| BT-A perception | Phát hiện, theo dõi, chọn xe dẫn đầu, khoảng cách theo cấu hình lắp cố định, TTC, kiểm tra ảnh và lắp đặt | 2, 4.2 |
| `join` | Ghép số đo với tốc độ theo mốc cắt thông tin; độ mới của tốc độ, ngưỡng, headway | 3.3 |
| BT-B decision | Năng lực cảnh báo, các đợt cảnh báo có `HOLD`, guardrail Khẩn cấp, lời báo trạng thái | 3.4–3.7 |
| Baseline | Cảnh báo theo sườn lên, cùng đầu vào với B, để so sánh | 2, 5.5 |
| Phân xử audio + audio sink | Một câu đang phát, một ô chờ; chỉ cảnh báo nguy hiểm mới được ngắt câu đang phát; sink bỏ lệnh quá hạn | 3.6 |
| Supervisor, logger | Nhịp tim, `system_fault`, `heartbeat.json`; ghi JSONL không chặn đường nóng | 3.2, 3.8 |
| Kho cấu hình + HITL | Phiên bản bất biến, người duyệt khác người đề xuất, khoá + compare-and-swap, quay lui | 3.10 |
| `rerun-B`, đánh giá | Tái lập B, khớp nhãn, recall toàn hệ thống; latency của B báo cáo riêng | 5 |
| Web UI (tuần 2–4) | Màn hình kỹ sư và màn hình trạng thái cho tài xế; gọi chung hàm HITL với CLI | 11.5 |
