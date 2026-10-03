# Sơ đồ phối hợp và phụ thuộc task

> Hai sơ đồ dưới đây vẽ lại bảng task ở [README.md](README.md), mục 4. Khi sơ đồ khác bảng thì **bảng thắng**; khi đổi owner hay phụ thuộc, sửa bảng trước rồi sửa sơ đồ trong cùng commit.
>
> Nét liền là việc của bản nộp MVP (tuần 1). Nét đứt là việc tuần 2–4. Mốc N0…N5 định nghĩa ở README mục 0: N0 = 29/09, N5 = 04/10 (nộp MVP).

## 1. Phối hợp bốn người: ai giao sản phẩm gì cho ai

```mermaid
flowchart LR
  subgraph CUONG["Cương · PO/Lead + R-C"]
    C1N["Contracts + fixture<br/>T1 · WP-C3 · WP-P4 · WP-C11"]
    C2N["Kho cấu hình + HITL CLI<br/>T2 · WP-P2 · WP-P3 · WP-C2"]
    C3N["Tích hợp + demo<br/>WP-P8 · WP-P7"]
  end
  subgraph KHANH["Khánh · R-B"]
    K1N["BT-B + câu nói<br/>WP-B0 · WP-B1 · WP-B2 · WP-B9"]
    K2N["Đánh giá hành vi cảnh báo<br/>WP-B8 · WP-C4 · WP-B3"]
  end
  subgraph TUAN["Tuấn · R-A + hỗ trợ backend"]
    T1N["BT-A<br/>WP-A0 · WP-A1 · WP-A2 · WP-A3 · WP-A4 · WP-A5"]
    T2N["Hiệu năng + kiểm tra live<br/>WP-A6"]
    T3N["Hỗ trợ backend<br/>WP-C1 · WP-A12"]
  end
  subgraph LINH["Linh · R-D"]
    L1N["Dữ liệu thực địa<br/>WP-D1 · WP-D2 · WP-D3 · WP-D5"]
    L2N["Gán nhãn + chạy đánh giá<br/>WP-D4 · WP-D12 · WP-D6"]
    L3N["Web UI (tuần 2–4)<br/>WP-C6 · WP-C7"]
  end

  C1N -- "schema + fixture (T1, WP-C3)" --> K1N
  C1N -- "schema + fixture (T1, WP-C3)" --> T1N
  K1N -- "tham số B + legal_table (WP-B1)" --> C2N
  T1N -- "model ONNX + hash (WP-A1)<br/>đề xuất cấu hình A (WP-A2, WP-A4)" --> C2N
  K2N -- "đề xuất cấu hình B + báo cáo tác động (WP-B3)" --> C2N
  C2N -- "máy demo (WP-P2)<br/>cấu hình active (WP-P3)" --> T1N
  C2N -- "cấu hình active (WP-P3)<br/>CLI perf (WP-C2)" --> T2N
  C2N -- "cấu hình active đã duyệt<br/>(sau WP-A4, WP-B3)" --> L2N
  L1N -- "xe, thiết bị, checklist lắp (WP-D1)<br/>clip dev + manifest (WP-D3)<br/>clip xe đứng yên (WP-D5)" --> T1N
  L1N -- "file GPS mẫu (WP-D2)" --> T3N
  L1N -- "phiên dev + test_small, session manifest (WP-D3)" --> L2N
  L1N -- "clip dev + manifest (WP-D3)" --> T2N
  L1N -- "clip dev + manifest (WP-D3)" --> C3N
  T3N -- "CSV GPS chuẩn (WP-A12)" --> L2N
  T3N -- "CSV GPS chuẩn (WP-A12)<br/>job CI (WP-C1)" --> C3N
  K2N -- "τ, lead_max, max_late (WP-B8)<br/>eval + test_runs.jsonl (WP-C4)" --> L2N
  L2N -- "nhãn dev (WP-D4)<br/>run log replay dev (WP-D12)" --> K2N
  K1N -- "WAV câu nói (WP-B2)" --> T2N
  K1N -- "WAV câu nói (WP-B2)" --> C3N
  K1N -- "fixture F1–F16 (WP-B9)" --> C1N
  T1N -- "bảng sai số khoảng cách (WP-A5)" --> L2N
  T2N -- "số hiệu năng + L_alert(B) (WP-A6)" --> L2N
  L2N -- "báo cáo đánh giá (WP-D6)" --> C3N
  T3N -. "API FastAPI (WP-C10)" .-> L3N
  T1N -. "ChangeEvidence (WP-A9)" .-> K1N
  L2N -. "biên bản thử nghe (WP-D9)" .-> K1N
  L1N -. "dữ liệu xe thử 2 (WP-D10)" .-> T1N
  L1N -. "phiên + nhãn test_final đã đóng băng (WP-D10)" .-> L2N

  classDef ext stroke-dasharray: 5 5
  class L3N ext
```

**Đọc sơ đồ:**
- Mọi thay đổi cấu hình của A và B đều đi qua kho cấu hình + HITL của Cương, và người duyệt phải khác người đề xuất. Người khác chỉ nhận **cấu hình active đã duyệt**, không nhận file cấu hình trao tay.
- Linh **tổng hợp** báo cáo đánh giá. Số liệu của từng mục do người làm ra nó chịu trách nhiệm (README, mục 1):
  - bảng sai số từ Tuấn;
  - số hiệu năng từ Tuấn, riêng `L_alert(B)` do Khánh kiểm;
  - so sánh B với baseline từ Khánh.
- **Phiên `test_small` và `test_final` chỉ đi từ dữ liệu thực địa sang gán nhãn và chạy đánh giá của Linh** (WP-D4, WP-D6; WP-D10, WP-D11). Tuấn và Khánh chỉ nhận phiên `dev`; từ tuần 2, Tuấn nhận thêm dữ liệu xe thử 2, không nhận `test_final`. Cương kiểm các phiên này bằng script chỉ in metadata, không mở nội dung ([linh.md: WP-D3, WP-D10](phan-viec/linh.md)).
- Sơ đồ chỉ vẽ sản phẩm bàn giao, không vẽ quan hệ review. Reviewer của từng task ghi ở README, mục 4.

## 2. Phụ thuộc task tuần 1 và đường găng

```mermaid
flowchart LR
  subgraph N0["N0 · T3 29/09"]
    P1["WP-P1 duyệt tài liệu · Cương"]
    P2["WP-P2 người duyệt, máy demo · Cương"]
  end
  subgraph N1["N1 · T4 30/09"]
    A0["WP-A0 tiếp nhận BT-A · Tuấn"]
    B0["WP-B0 tiếp nhận BT-B · Khánh"]
    B1["WP-B1 bảng pháp lý, tham số B · Khánh"]
    C1["WP-C1 CI · Tuấn"]
    D1["WP-D1 xe, quy trình quay · Linh"]
    D2["WP-D2 app GPS, quy trình đồng bộ · Linh"]
  end
  subgraph N2["N2 · T5 01/10"]
    A1["WP-A1 model ONNX · Tuấn"]
    B2["WP-B2 câu nói WAV · Khánh"]
    P3["WP-P3 cấu hình v0 được duyệt · Cương"]
    C2["WP-C2 CLI · Cương"]
    A2["WP-A2 hiệu chỉnh camera · Tuấn"]
    A12["WP-A12 chuyển đổi GPS · Tuấn"]
    D3["WP-D3 quay ≥ 2 phiên + manifest · Linh"]
    B8["WP-B8 phương pháp đánh giá · Khánh"]
    P6["WP-P6 chốt với mentor · Cương"]
  end
  subgraph N3["N3 · T6 02/10"]
    D5["WP-D5 clip xe đứng yên · Linh"]
    A3["WP-A3 kiểm tra lắp đặt · Tuấn"]
    C3["WP-C3 fixture JSONL · Cương"]
    B9["WP-B9 fixture F1–F16 · Khánh"]
    A4["WP-A4 tinh chỉnh perception · Tuấn"]
    A5["WP-A5 kiểm chứng khoảng cách · Tuấn"]
    D4["WP-D4 gán nhãn · Linh"]
    D12["WP-D12 replay bộ dev · Linh"]
    C4["WP-C4 loại phiên GPS kém · Khánh"]
  end
  subgraph N4["N4 · T7 03/10"]
    B3["WP-B3 tinh chỉnh B · Khánh"]
    A6["WP-A6 hiệu năng, live · Tuấn"]
    P8["WP-P8 tích hợp đầu–cuối · Cương"]
  end
  subgraph N5["N5 · CN 04/10: nộp MVP"]
    D6["WP-D6 chạy test_small, báo cáo · Linh"]
    P4["WP-P4 đóng băng contracts v1.0 · Cương"]
    P7["WP-P7 giới hạn, demo · Cương"]
  end

  P1 --> P2
  P1 --> A0
  P1 --> B0
  P2 --> A1
  B1 --> B2
  B1 --> P3
  A1 --> P3
  P2 --> P3
  D1 --> D2
  P2 --> C2
  D1 --> A2
  P3 --> A2
  D2 --> A12
  D1 --> D3
  D2 --> D3
  B0 --> B8
  D1 --> D5
  D3 --> A3
  D5 --> A3
  B0 --> B9
  D3 --> A4
  A1 --> A4
  A2 --> A4
  D5 --> A5
  A1 --> A5
  A2 --> A5
  D3 --> D4
  B8 --> D4
  D3 --> D12
  A12 --> D12
  A4 --> D12
  D4 --> B3
  D12 --> B3
  B8 --> B3
  D3 --> A6
  A12 --> A6
  A1 --> A6
  B2 --> A6
  C2 --> A6
  P3 --> A6
  D3 --> P8
  A12 --> P8
  A1 --> P8
  B2 --> P8
  P3 --> P8
  D4 --> D6
  B3 --> D6
  A5 --> D6
  A6 --> D6
  C4 --> D6
  C3 --> P4
  B9 --> P4
  D6 --> P7
  P8 --> P7
  P4 --> P7
  B9 --> P7
  A3 --> P7
  A6 --> P7
  C2 --> P7

  classDef crit stroke:#c0392b,stroke-width:3px
  class D1,D2,D3,D4,D12,B3,D6,P7 crit
```

**Đọc sơ đồ:**
- **Mỗi mũi tên** là một dòng trong cột "Cần có" của README mục 4.1.
- **WP-P7** chỉ cần các task cho ra bằng chứng của AC-M1…M12 ([cuong.md: WP-P7](phan-viec/cuong.md)); không cần WP-P5, WP-P6, WP-D7.
- **Không vẽ** WP-P5 (việc liên tục) và WP-D7 (không chặn MVP).
- **Viền đỏ là đường găng:** WP-D1 → WP-D2 → WP-D3 → WP-D4 và WP-D12 → WP-B3 → WP-D6 → WP-P7.
  - Chuỗi này đi qua dữ liệu thực địa: có dữ liệu thì mới có nhãn và các lần chạy trên bộ dev; có nhãn và các lần chạy đó thì mới tinh chỉnh được B; tinh chỉnh B xong mới chạy được `test_small`.
  - Mọi task nằm trên đường găng đều không còn ngày dự phòng. Phương án khi trễ: README, mục 5.
