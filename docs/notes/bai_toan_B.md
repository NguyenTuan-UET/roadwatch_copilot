# TỔNG QUAN BÀI TOÁN B (BT-B) — BẢN ĐỒ BỘ NÃO QUYẾT ĐỊNH DÀNH CHO LEAD

> **Dành cho:** Cương (PO / Team Lead) & Khánh (Kỹ sư phụ trách BT-B)  
> **Cập nhật:** 02/10/2026 (Chuẩn bị nghiệm thu MVP)  
> **Mục tiêu:** Giải thích bản chất bài toán B một cách trực quan, dễ hiểu nhất; làm rõ 4 trụ cột logic của "Bộ não", các luật an toàn bất khả xâm phạm, và cách phối hợp nhịp nhàng với BT-A và BT-C.

---

## 1. Bản chất cốt lõi: Bài toán B là gì trong RoadWatch Copilot?

Nếu hình dung hệ thống **RoadWatch Copilot** là một con người đang ngồi kèm lái bên cạnh tài xế mới:
* **BT-A (Tuấn — Thị giác máy):** Là **"Đôi mắt"** — nhìn đường, bắt xe dẫn đầu, đo xem xe trước cách bao xa ($d$) và bao nhiêu giây nữa thì đâm ($TTC$).
* **BT-C (Cương — Nền tảng & Điều phối):** Là **"Khung gầm & Hệ thần kinh"** — truyền dẫn dữ liệu từ camera và GPS, ghi hộp đen, nạp cấu hình và phát loa.
* **BT-B (Khánh — Bộ não suy luận):** Chính là **"Ý thức & Phản xạ"** của người kèm lái:
  * Đôi mắt báo về con số: *"Xe trước cách 25m, TTC là 1.6 giây, xe mình đang chạy 90 km/h"*.
  * **Bộ não (BT-B) phải trả lời 3 câu hỏi sống còn:**
    1. *Tình huống này có nguy hiểm không? Theo Luật Giao thông Việt Nam thì xe mình có đang bám quá sát không?*
    2. *Có nên mở mồm nhắc tài xế ngay lúc này không, hay đây chỉ là xe khác tạt đầu thoáng qua một tích tắc?*
    3. *Nếu cần nhắc thì phát câu tiếng Việt nào? Và nếu loa đang bận nói câu khác thì câu này có được cướp lời để ngắt ngang không?*

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             4 TRỤ CỘT CỦA BT-B                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Ghép nối & Đối chiếu luật (Join & Legal Bands): d, v -> Headway, Ngưỡng.│
│ 2. Quản lý năng lực (Capability & Fail-safe): Tắt/bật độc lập cap_d, cap_ttc│
│ 3. Máy trạng thái Đợt cảnh báo (Episodes & FSM): Chống nhấp nháy, Guardrail│
│ 4. Phân xử âm thanh (Audio Arbiter): Ưu tiên câu nguy hiểm, ngắt lời an toàn│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dòng chảy dữ liệu của BT-B: Đầu vào và Đầu ra

BT-B là một **Hộp đen hàm thuần (Pure Function)** nằm giữa đường ống của BT-C. B không làm I/O, không đọc file, không mạng:

```
[ BT-A: Measurement ] ──┐
  (d, TTC, xe dẫn đầu)   │
                         ▼
[ BT-D: SpeedSample ] ──► [ BT-C: join ] ──► [ JoinedInput ]
  (Tốc độ xe GPS)                                   │
                                                    ▼
                                          ┌───────────────────┐
                                          │  BT-B: DECISION   │
                                          │   (Bộ não FSM)    │
                                          └─────────┬─────────┘
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         ▼                                                     ▼
                  [ AlertRecord ]                                        [ AudioPlan ]
          (Ghi nhận quyết định cảnh báo,                         (Lệnh phát âm thanh: câu gì,
            mức độ, lý do, dấu vết suy luận)                       ưu tiên mấy, có ngắt câu cũ không)
```

1. **Đầu vào của B ([JoinedInput](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/contracts/streams.py)):** Do BT-C chuẩn bị sẵn gồm: số đo của A + vận tốc GPS + sự kiện hệ thống (`SystemEvent`) + nhịp thời gian (`tick`).
2. **Đầu ra của B:**
   * [AlertRecord](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/contracts/streams.py): Bản ghi lưu vết kiểm toán (audit trail), phục vụ chấm điểm và vẽ biểu đồ.
   * [AudioPlan](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/contracts/streams.py): Kế hoạch âm thanh gửi sang `audio sink` để phát file WAV ra loa máy tính.

---

## 3. Bốn trụ cột kỹ thuật của BT-B (Giải thích chi tiết)

Mã nguồn của BT-B nằm tại `src/roadwatch/decision/`:

### 3.1. Trụ cột 1: Ghép nối & Tra bảng pháp lý ([join.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/join.py))
* **Nhiệm vụ:** Lấy khoảng cách $d$ từ camera ghép với vận tốc xe $v$ từ GPS.
* **Tra cứu Thông tư 31/2019/TT-BGTVT:** Luật Việt Nam quy định khoảng cách an toàn tối thiểu trên cao tốc theo tốc độ:
  * Tốc độ $v \le 60\text{ km/h}$: Ngưỡng an toàn tối thiểu là $35\text{ m}$.
  * $60 < v \le 80\text{ km/h}$: Ngưỡng an toàn là $55\text{ m}$.
  * $80 < v \le 100\text{ km/h}$: Ngưỡng an toàn là $70\text{ m}$.
  * $100 < v \le 120\text{ km/h}$: Ngưỡng an toàn là $100\text{ m}$.
* **Quy tắc thời gian (Cut-off):** Tốc độ GPS nhận sau thời điểm chụp ảnh thì không được dùng cho ảnh đó. Nếu mất GPS quá lâu $\rightarrow$ chuyển trạng thái GPS sang `lost`.

### 3.2. Trụ cột 2: Quản lý năng lực độc lập & Fail-safe ([capability.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/capability.py))
Hệ thống có **2 năng lực cảnh báo độc lập**:
1. `cap_distance`: Cảnh báo giữ khoảng cách (cần cả Camera và GPS).
2. `cap_ttc`: Cảnh báo nguy cơ va chạm khẩn cấp (chỉ cần Camera đo $TTC$, **hoàn toàn không cần GPS**).

> **Luật sắt Fail-safe:** Không có chuyện "lỗi một tí là tắt ngấm cả hệ thống". Năng lực nào hỏng thì chỉ tắt đúng năng lực đó:
* **Mất GPS (`speed: lost`):** Tắt `cap_distance`. Nhưng **`cap_ttc` vẫn bật bình thường**! Nếu xe trước phanh gấp, hệ thống vẫn hét lên cảnh báo cứu mạng tài xế.
* **GPS bị trễ nhẹ (`speed: stale`):** Không tắt năng lực nào, chỉ tạm thời không cảnh báo khoảng cách ở khung hình đó.
* **Camera bị lệch/nghiêng (`mount: suspect`):** Tắt `cap_distance` (vì đo khoảng cách bị sai), nhưng vẫn giữ `cap_ttc` nếu bám được theo vạch làn.

### 3.3. Trụ cột 3: Máy trạng thái "Đợt cảnh báo" & Chống nhấp nháy ([episodes.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/episodes.py))
Nếu cứ thấy xe trước vi phạm là loa kêu, tài xế sẽ bị "khủng bố màng nhĩ" và tắt máy. Do đó, BT-B gom các cảnh báo vào các **"Đợt" (Episodes)** qua máy trạng thái (FSM):

```
       [IDLE] (Bình thường, an toàn)
         │
         ▼ (Vi phạm khoảng cách / TTC)
      [PENDING] (Chờ xác nhận trong T_confirm, ví dụ 0.8s)
         │
         ▼ (Vi phạm kéo dài liên tục)
      [ALERTED / ACTIVE] ──► PHÁT LOA CẢNH BÁO ĐÚNG 1 LẦN!
         │
         ▼ (Xe trước bắt đầu đi xa ra)
     [CLEARING] (Đếm lùi thời gian an toàn T_clear, ví dụ 2.0s)
         │
         ▼ (An toàn liên tục đủ T_clear)
       [IDLE] (Đóng đợt thành công -> Sẵn sàng cho lần báo tiếp theo)
```

* **Chống nhấp nháy (Anti-flickering / Chattering):**
  * Khi xe trước vừa ngấp nghé ở ngưỡng $70\text{ m}$ (lúc $69\text{ m}$, lúc $71\text{ m}$), FSM có dải trễ hysteresis ($h$) và thời gian xác nhận $T_{\text{confirm}}$. Hệ thống chỉ phát cảnh báo khi vi phạm thực sự kéo dài, không kêu lắt nhắt như baseline.
* **Guardrail Khẩn cấp (Phải báo ngay lập tức):**
  * Riêng với cảnh báo Khẩn cấp ($TTC \le 1.8\text{ s}$), khi đủ 3 điều kiện: `cap_ttc = on`, TTC `status = ok` và $TTC \le 1.8\text{ s}$, **bỏ qua mọi thời gian chờ $T_{\text{confirm}}$**, hệ thống **phát loa Khẩn cấp ngay ở khung hình đó**! Không tham số nào được phép trì hoãn.
* **Xử lý dữ liệu chập chờn (`HOLD` & OQ-A5):**
  * Khi camera bị chớp mắt/mất frame trong lúc đang rời đợt (`CLEARING`), hệ thống **không được reset đồng hồ về 0**, mà tiếp tục đếm cộng dồn để đóng dứt điểm đợt cũ. Nhờ vậy, nếu 10 giây sau xe trước lại phanh gấp lần 2, hệ thống sẽ phát cảnh báo ngay mà không bị câm nín!

### 3.4. Trụ cột 4: Bộ phân xử âm thanh ([arbiter.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/arbiter.py))
Tài xế chỉ có 1 đôi tai, loa chỉ phát được 1 câu tại một thời điểm. Ai được nói? Ai phải nhường?
* **Cơ chế:** 1 câu đang phát trên loa (`PLAYING`) và 1 ô chờ (`PENDING SLOT`) cho câu tiếp theo.
* **Quy tắc ngắt lời (Preemption):**
  * Câu mức **Khẩn cấp** (Ưu tiên 1) có quyền **ngắt ngang lập tức** câu Cảnh báo khoảng cách (Ưu tiên 2) đang phát dở.
  * Các câu thông báo trạng thái (Ưu tiên 3, 4: *"Mất GPS"*, *"Tắt cảnh báo khoảng cách"*) **tuyệt đối không bao giờ được ngắt lời** các câu cảnh báo nguy hiểm!
  * Lệnh trong ô chờ quá hạn (`max_cmd_age`) mà chưa được phát sẽ bị hủy bỏ (tránh việc xe đã an toàn rồi mà loa mới muộn màng kêu "Phanh lại").

---

## 4. Tám câu nói tiếng Việt chuẩn của BT-B

Khánh sử dụng Piper TTS (giọng `vi_VN-vais1000-medium`) để sinh 8 file WAV trong `assets/audio/`:

| Mã câu | Nội dung tiếng Việt phát ra loa | Mức ưu tiên | Tình huống kích hoạt |
|---|---|:---:|---|
| `emergency` | *"Nguy hiểm, phanh lại!"* (kèm tiếng bíp dồn dập) | **1 (Cao nhất)** | Nguy cơ va chạm khẩn cấp ($TTC \le 1.8\text{ s}$). |
| `distance_warn` | *"Chú ý giữ khoảng cách!"* | **2** | Bám đuôi xe trước dưới ngưỡng luật định quá $T_{\text{confirm}}$. |
| `system_fault` | *"Hệ thống trợ lái gặp sự cố"* | **3** | Runtime hoặc thread bị chết, supervisor kích hoạt. |
| `cap_ttc_off` | *"Tắt cảnh báo va chạm"* | **4** | Tốc độ xử lý quá thấp ($< 6\text{ Hz}$) hoặc camera mất dấu hoàn toàn. |
| `cap_dist_off` | *"Tắt cảnh báo khoảng cách"* | **4** | Mất GPS hoặc camera bị lệch góc lắp đặt. |
| `cap_all_off` | *"Tạm dừng cảnh báo"* | **4** | Mất cả camera lẫn GPS. |
| `recovered` | *"Hệ thống hoạt động trở lại"* | **6** | Các cảm biến phục hồi bình thường sau sự cố. |
| `reminder` | *"Cảnh báo vẫn chưa hoạt động đầy đủ"* | **7 (Thấp nhất)** | Nhắc lại định kỳ nếu hệ thống vẫn đang trong trạng thái suy giảm. |

---

## 5. Bản đồ mã nguồn & Bộ test của BT-B

Toàn bộ logic của BT-B được bảo vệ bởi **85 unit test** và **15 kịch bản lỗi (F1–F18)** trong [tests/roadwatch/test_decision.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/tests/roadwatch/test_decision.py):

| File mã nguồn | Vai trò chính | Spec mục | Vùng test tương ứng |
|---|---|:---:|---|
| [join.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/join.py) | Cắt mốc thời gian, tra bảng Thông tư 31, headway | 3.3 | `test_speed_sample_*`, `test_legal_band_*` |
| [capability.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/capability.py) | Tính toán 2 năng lực, debounce câu thông báo $T_{\text{notify}}$ | 3.4 | `test_mount_*`, `test_system_fault_*` |
| [episodes.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/episodes.py) | FSM đợt khoảng cách & khẩn cấp, `HOLD`, xử lý OQ-A5 | 3.5 | `test_sustained_violation_*`, `test_hold_*` |
| [arbiter.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/arbiter.py) | Bộ phân xử audio thuần, hàng đợi ô chờ | 3.6 | `test_emergency_preempts_*`, `test_pending_slot_*` |
| [stage.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/decision/stage.py) | Ghép nối 4 module thành pipeline Decision hoàn chỉnh; Baseline | 3.4, 3.7 | `test_guardrail_property_*`, `test_s1_…s7` |
| [evaluate.py](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/src/roadwatch/evaluate.py) | Đối chiếu nhãn thực tế, tính F1-score, đo độ trễ $\mathcal{L}_{\text{alert}}$ | 5.1, 5.2 | `tests/roadwatch/test_rerun_eval.py` |

---

## 6. Hiện trạng thực tế & Các việc Lead cần chốt cho BT-B

* **Tiến độ kỹ thuật:**
  * Toàn bộ mã nguồn cốt lõi của BT-B đã viết xong và được kiểm chứng.
  * Đã giải quyết 5 lỗi kiến trúc nghiêm trọng khi tiếp nhận (D-14, D-15, I-16, D-18 và OQ-A5).
  * Bộ test đạt **227 passed** (kết hợp cùng contracts v1.0).
* **Ba việc còn lại của BT-B để hoàn tất nghiệm thu:**
  1. **Render file âm thanh (WP-B2):** Chạy script `render_phrases.py` để xuất 8 file WAV chuẩn bỏ vào thư mục âm thanh.
  2. **Review chéo cho Cương:** Khánh thực hiện review và bấm nghiệm thu cho task [WP-C3](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/docs/plan/phan-viec/cuong.md#wp-c3--fixture-va-kiem-tra-lien-luong) (Fixtures) và [WP-P4](file:///c:/Users/cuong/OneDrive/Documents/PH%C3%81T%20TRI%E1%BB%82N%20B%E1%BA%A2N%20TH%C3%82N/PROJECT__CODE/PJVinAIGr14/P-014/docs/plan/phan-viec/cuong.md#wp-p4--dong-bang-contracts-v10) (Đóng băng Contracts v1.0).
  3. **Đánh giá trên tập dữ liệu thật (WP-B3, WP-B8):** Sau khi Linh đi quay cao tốc về (WP-D3), dùng công cụ `roadwatch eval` để tính toán chỉ số F1 và chứng minh thuật toán của BT-B thông minh hơn bộ quy tắc thô sơ (Baseline).

---

### Tóm lại câu "thần chú" cho Lead khi nhìn vào BT-B:
> **BT-B là Hàm Thuần ra quyết định thông minh:** Nhận số đo của A + GPS của D $\rightarrow$ Tra luật giao thông $\rightarrow$ Lọc qua máy trạng thái FSM chống nhấp nháy $\rightarrow$ Đảm bảo Guardrail khẩn cấp nổ ngay lập tức $\rightarrow$ Phân xử âm thanh câu nào được nói ra loa!
