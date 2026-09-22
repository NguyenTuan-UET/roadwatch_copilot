# Đặc tả Hệ thống (Spec) — Phần 5: Quy tắc Chống Báo Giả & Lọc Nhiễu Quang Học
> Nguồn: Kế thừa docs/spec/false-positives.md tuân thủ SDLC Bước 4: Software Design & Rule Engine
> Nhằm đảm bảo Precision >= 95%, xử lý 22 kịch bản nhiễu (A1–E5).

# Các tình huống trông giống vi phạm nhưng không phải vi phạm

> TrafficEye Edge ưu tiên precision cao nhất: mỗi tình huống bị bỏ sót là một nguồn báo nhầm.
> Báo nhầm lỗi vượt đèn đỏ với ô tô đồng nghĩa phạt oan 18–20 triệu đồng và trừ 4 điểm giấy phép lái xe (mức phạt hiện hành, xem nguồn).
> Mã lý do được dùng trong hướng dẫn gán nhãn và phân tích lỗi của `docs/eval/protocol.md`:
> - A1…E5: vượt đèn đỏ;
> - W1…W8: đi ngược chiều;
> - L1…L8: vi phạm làn đường;
> - S1…S6: dừng, đỗ sai.
>
> Cập nhật 21/09:
> - theo design review: điều kiện 3 dùng vùng giao lộ (M-03); điểm đầu xe được ước lượng vì camera nhìn từ phía sau (H-05);
> - theo spec v1.0: thêm mục 3–5 cho đi ngược chiều, vi phạm làn đường, dừng đỗ sai.
>
> Các mục E1–E5 (lỗi tracking, hình học, điều kiện quan sát) áp dụng cho **mọi** loại vi phạm.

## 1. Vượt đèn đỏ — khi nào một xe mới thành "candidate"

Xe chỉ thành candidate khi thỏa **tất cả** các điều kiện sau:

1. **Đèn:** đèn áp dụng cho đúng làn và hướng của xe đang ĐỎ, ổn định ít nhất N khung. Trạng thái KHÔNG RÕ, NHẤP NHÁY hoặc TẮT thì dừng ngay.
2. **Thời điểm:** khi đèn chuyển đỏ cộng thêm ân hạn T_g, mép trước của xe (điểm đầu xe ước lượng, xem E3) vẫn ở trước vạch dừng.
3. **Chuyển động:** sau đó xe qua vạch dừng **và** đi vào **vùng giao lộ** (polygon phủ lòng nút, gồm cả hướng rẽ) trong vòng T_c giây. Điều này chứng minh xe đi tiếp chứ không chỉ nhích.
4. **Chất lượng quan sát:** chỉ có một track ID liền mạch suốt sự kiện, và có detection thật (không nội suy) ở cả hai thời điểm qua vạch.
5. **Không có ngữ cảnh miễn trừ:** không có xe ưu tiên hoặc đoàn xe ưu tiên trong khoảng thời gian đó, không ở chế độ điều khiển tay, làn và hướng không được phép đi khi đỏ, camera không lệch.
6. **Đủ bằng chứng:** có khung thấy đèn đỏ, xe trước vạch, xe sau vạch, biển số đọc được.

Về ân hạn: ở 15 FPS mỗi mốc thời gian đã lệch tới 1 khung (khoảng 67 ms), cộng thêm độ trễ làm mượt trạng thái đèn. Bắt đầu với 0,5–1 s rồi chỉnh trên tập phát triển. Ân hạn dài thì bỏ sót nhiều hơn nhưng ít báo nhầm hơn.

## 2. Vượt đèn đỏ — phân tích từng tình huống

### A. Xe không sai: xét theo thời điểm

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| A1 | Qua vạch lúc xanh hoặc vàng, sau đó mới đỏ | Khung bằng chứng chụp lúc đèn đã đỏ, xe đang giữa nút | Mép trước chạm vạch sớm hơn mốc chuyển đỏ | Điều kiện 2. Theo Luật 2024 (Điều 11), xe còn trước vạch khi đèn vàng bật mà vẫn qua thì cũng vi phạm, nhưng đây là vùng xám nên không gắn cờ |
| A2 | Đã vào nút hợp lệ khi đèn chuyển đỏ (chờ rẽ, kẹt trong nút) | Xe đang chạy trong nút lúc đèn đỏ | Xe đã ở sau vạch từ trước pha đỏ | Chỉ tạo vi phạm từ sự kiện *qua vạch* lúc đỏ; track bắt đầu ở giữa nút thì bỏ |
| A3 | Xe dài: container, xe buýt, rơ-moóc, xe bị kéo | Đầu xe qua lúc vàng, đuôi hoặc rơ-moóc (bị nhận thành xe riêng) qua lúc đỏ | Phần qua sau bám liền phần trước, cùng vận tốc | Tính thời điểm theo mép trước (ước lượng theo chiều dài loại xe, xem E3); gộp rơ-moóc hoặc xe bị kéo vào xe kéo |

### B. Xe không sai: xét theo vị trí và chuyển động

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| B1 | Dừng đè vạch, nhích, bị đẩy hoặc trôi qua vạch | Mép trước vượt vạch lúc đỏ | Vận tốc về gần 0 ngay sau vạch, không vào giữa nút | Điều kiện 3 (vào vùng giao lộ + vận tốc tối thiểu). Dừng quá vạch là lỗi khác, ngoài phạm vi |
| B2 | Nhích qua vạch để nhường đường xe ưu tiên | Qua vạch lúc đỏ | Có xe ưu tiên đang tới cùng lúc; xe tấp lề rồi dừng | Có xe ưu tiên trong khoảng ±T giây thì chuyển cho người xem |
| B3 | Xe hướng khác, quay đầu, đường gom, đường song song | Quỹ đạo cắt ngang vạch vẽ trên ảnh | Hướng đi không trùng hướng làn; nằm ngoài vùng làn | Vạch dừng là đoạn có hướng, gắn với từng làn; chỉ tính xe đi từ vùng tiếp cận và đúng chiều; loại đường gom khỏi ROI |
| B4 | Người đi bộ, xe đạp, người dắt xe máy | Qua vạch lúc đỏ; người dắt xe bị nhận là xe máy | Lớp đối tượng khác, tốc độ đi bộ, xe đạp không có biển số | Chỉ xét xe cơ giới có biển số; tốc độ đi bộ thì không gắn cờ |

### C. Luật cho phép đi

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| C1 | Xe ưu tiên làm nhiệm vụ (chữa cháy, cứu thương, công an hoặc quân sự khẩn cấp, cứu nạn) | Qua đỏ, thường ở tốc độ cao | Loại xe đặc thù, đèn ưu tiên nhấp nháy (camera không nghe được còi) | Không bao giờ tự tạo vi phạm. Camera không biết xe có đang làm nhiệm vụ không, nên để người quyết |
| C2 | Xe trong đoàn có công an dẫn đường | Toàn xe thường, không có đèn ưu tiên, nối đuôi nhau qua đỏ | Có xe dẫn đường đi đầu; các xe bám sát, cùng vận tốc | Thấy xe dẫn đường thì mở một khoảng thời gian "đoàn ưu tiên"; candidate trong khoảng đó chuyển cho người xem |
| C3 | Rẽ phải có biển phụ cho phép, hoặc có mũi tên xanh | Qua vạch khi đèn tròn đang đỏ | Làn có biển cho phép và quỹ đạo rẽ phải; hoặc mũi tên xanh sáng cùng lúc đèn đỏ hay vàng | Cấu hình theo **làn + hướng** cho từng nút; xác định hướng từ quỹ đạo; đọc mũi tên như tín hiệu riêng. Rẽ phải từ làn đi thẳng khi đèn đỏ vẫn là vượt đèn đỏ |
| C4 | Hiệu lệnh người điều khiển giao thông; phân luồng tạm thời | Luật đặt hiệu lệnh của người điều khiển trên cả đèn (Điều 11 khoản 2), nhưng camera chỉ thấy cả loạt xe đi khi đèn đỏ | Có người mặc sắc phục, cọc hoặc rào tạm; số xe qua đỏ tăng đột biến | Điều hành viên bật chế độ "điều khiển tay / tạm dừng" cho từng nút; số xe qua đỏ tăng bất thường thì tạm dừng tạo candidate và hỏi điều hành viên |

### D. Hệ thống đọc sai trạng thái đèn

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| D1 | Đèn hỏng, đèn tắt, vàng nhấp nháy; mỗi hướng hay mỗi làn có pha riêng | Bộ đọc gán "đỏ" sai, hoặc đọc đèn tròn thay vì mũi tên của làn | Đèn không có màu; vàng chớp theo chu kỳ; nhiều đầu đèn cho nhiều làn | Máy trạng thái có NHẤP NHÁY, TẮT, KHÔNG RÕ và các trạng thái này chặn gắn cờ; chỉ nhận chuyển pha hợp lệ (xanh → vàng → đỏ); cấu hình đầu đèn nào điều khiển làn nào |
| D2 | Nhìn nhầm đèn của hướng khác | Đèn hướng cắt ngang đang đỏ nằm gần đèn của mình trong khung hình | Vị trí và hướng mặt đèn khác; đổi pha ngược với đèn của mình | ROI cố định cho từng đầu đèn; kiểm tra chéo: hai hướng xung đột không thể cùng xanh |
| D3 | Đèn hậu, đèn phanh, LED quảng cáo, vệt phản chiếu đỏ | Đốm đỏ bị hiểu là đèn đỏ | Nằm ngoài ROI, di chuyển theo xe, hình dạng khác bóng đèn | Chỉ đọc trong ROI; kiểm tra cả 3 bóng (đỏ sáng thì vàng và xanh phải tắt); lọc theo thời gian |
| D4 | Đèn LED nhấp nháy theo tần số điện, camera bắt trúng lúc bóng tắt | Camera chụp đúng lúc bóng tắt, tạo mốc chuyển pha giả | Trạng thái nhảy lẻ 1–2 khung rồi trở lại | Bỏ phiếu đa số trong cửa sổ trượt; bỏ qua trạng thái kéo dài ít hơn N khung |
| D5 | Đèn hoặc vạch dừng bị xe lớn che | Bộ đọc giữ trạng thái cũ, hoặc đoán | ROI của đèn bị khung xe phủ lên | ROI bị che thì trạng thái là KHÔNG RÕ; không nội suy qua đoạn có thể có chuyển pha |
| D6 | Lệch đồng bộ giữa đèn và khung hình | Xe qua lúc vàng bị ghép với mốc "đỏ" | Chỉ xảy ra khi lấy trạng thái đèn từ nguồn ngoài | Đồng bộ giờ và ghi độ lệch vào manifest; ân hạn lớn hơn độ lệch tối đa; nếu có hai nguồn thì bắt buộc hai nguồn khớp |

### E. Lỗi tracking, hình học và điều kiện quan sát

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| E1 | Tracker đổi ID giữa hai xe | Xe A đứng trước vạch và xe B đã qua vạch bị ghép thành "một xe vượt đèn" | Quỹ đạo nhảy đột ngột về vị trí, kích thước, ngoại hình; vận tốc vô lý về vật lý | Kiểm tra track có liền mạch trong suốt sự kiện không; có dấu hiệu đứt thì bỏ |
| E2 | Xe bị che đúng lúc qua vạch | Thời điểm qua vạch do tracker nội suy | Không có detection thật quanh thời điểm qua vạch | Điều kiện 4 |
| E3 | Điểm tham chiếu sai do góc nhìn; vạch sơn mờ, hiệu chuẩn sai | Camera nhìn từ phía sau nên cạnh dưới bbox là **đuôi xe**: đầu xe đã qua vạch từ lúc vàng nhưng đuôi qua lúc đỏ. Xe cao hoặc nhìn chéo làm đáy bbox lệch khỏi vị trí bánh xe | Sai số tăng theo chiều dài xe, chiều cao xe và góc nhìn | Ước lượng điểm đầu xe = điểm đuôi + chiều dài theo loại xe, tính dọc hướng làn trên mặt đường (homography); vẽ vạch thủ công trên ảnh tham chiếu; thêm biên an toàn sau vạch; đưa các ca đầu xe qua lúc vàng vào mẫu âm khó của tập dev |
| E4 | Camera rung hoặc lệch góc dần theo thời gian | Vạch đã cấu hình đứng yên còn khung hình dịch đi | Toàn bộ nền (vạch sơn, cột, lề) dịch cùng lúc | Định kỳ so với ảnh hiệu chuẩn; lệch quá ngưỡng thì tắt gắn cờ camera đó và báo điều hành viên |
| E5 | Ban đêm, mưa, chói, lóa đèn pha | Detection và tracking kém; đèn tín hiệu bị lóa hoặc phản chiếu trên đường ướt | Độ tin cậy và độ tương phản thấp | Cổng chất lượng: dưới ngưỡng thì chỉ ghi "cần xem"; báo precision riêng theo ngày, đêm, mưa |

## 3. Đi ngược chiều (WW)

### 3.1 Khi nào thành candidate

Luật **chỉ áp dụng ở phần đường có một hướng đi rõ ràng**: làn có `direction`, hoặc vùng trong `wrong_way_zones` của cấu hình cảnh (đường một chiều, phần đường có dải phân cách hoặc vạch liền giữa hai chiều). Xe thành candidate khi thỏa **tất cả** các điều kiện:

1. **Vị trí:** điểm tiếp đất của xe nằm trong phần đường nói trên.
2. **Hướng:** hướng chuyển động lệch hơn `min_angle_deg` (khởi điểm 135°) so với hướng được phép, trong ít nhất `min_windows` cửa sổ `window_s` giây liên tiếp.
3. **Quãng đường:** tổng quãng đi ngược ≥ `min_distance_m`, tính trên mặt đường bằng homography.
4. **Tốc độ:** ≥ `min_speed_kmh`, để loại người dắt xe và xe lùi một đoạn ngắn.
5. **Chất lượng quan sát:** một track ID liền mạch, có detection thật ở đầu và cuối đoạn đi ngược.
6. **Không có ngữ cảnh miễn trừ:** không có xe ưu tiên, không ở chế độ điều khiển tay hoặc phân luồng tạm.

Bằng chứng gồm các khung ở đầu, giữa và cuối đoạn đi ngược (có vẽ mũi tên hướng được phép), cộng ảnh biển số.

### 3.2 Các tình huống trông giống nhưng không phải

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| W1 | Lùi xe một đoạn ngắn (ra khỏi chỗ đỗ, lùi để quay đầu) | Quỹ đạo ngược hướng làn | Quãng đường ngắn, tốc độ rất thấp, thường dừng trước và sau | Ngưỡng quãng đường và tốc độ tối thiểu. Lùi xe là lỗi khác, nằm ngoài phạm vi |
| W2 | Người dắt hoặc đẩy xe máy đi ngược chiều sát lề | Xe máy di chuyển ngược chiều | Tốc độ đi bộ (dưới khoảng 6 km/h); có người đi cạnh xe thay vì ngồi trên xe | Ngưỡng tốc độ; có `person` đi cạnh xe ở tốc độ đi bộ thì không gắn cờ |
| W3 | Quay đầu hợp lệ ở nơi cho phép | Có một đoạn quỹ đạo ngược chiều sau khi quay | Quỹ đạo hình vòng cung, bắt đầu từ vùng quay đầu | Khai báo vùng quay đầu; quỹ đạo vòng cung xuất phát từ vùng này thì bỏ |
| W4 | Tracker đổi ID giữa hai xe đi hai hướng | Track "nhảy" ngược hướng | Vị trí, kích thước, ngoại hình đổi đột ngột | Kiểm tra track liền mạch như E1; có dấu hiệu đứt thì bỏ |
| W5 | Nhiễu phối cảnh ở vùng xa: bbox nhỏ rung | Vector chuyển động ngắn đổi hướng liên tục | Chỉ xảy ra ở vùng xa; quãng đường thật trên mặt đường rất nhỏ | Tính quãng đường trên mặt đường; bỏ vùng quá xa khỏi ROI |
| W6 | Phân luồng tạm, thi công, CSGT cho đi hai chiều | Nhiều xe cùng đi "ngược" | Có rào chắn, cọc tiêu, người điều khiển; nhiều xe ngược cùng lúc | Chế độ điều khiển tay; số ca ngược tăng đột biến thì tạm dừng tạo candidate và hỏi điều hành viên |
| W7 | Cấu hình hướng sai, hoặc đường hai chiều không có vạch hay dải phân chia | Hầu như mọi xe đi một chiều đều bị coi là ngược | Tỉ lệ ca rất cao; không có vạch hay dải phân cách | Chỉ áp dụng ở phần đường có một hướng rõ ràng; kiểm tra cấu hình bằng clip thử trước khi bật luật |
| W8 | Xe trên vỉa hè, lối vào nhà, bãi đỗ cạnh đường | Có chuyển động ngược nằm trong khung hình | Nằm ngoài phần đường xe chạy | Chỉ xét trong polygon làn và `wrong_way_zones` |

### 3.3 Căn cứ pháp lý

- **Luật TTATGTĐB 2024:** người lái phải đi đúng phần đường, làn đường.
- **Nghị định 168/2024/NĐ-CP**, lỗi đi ngược chiều của đường một chiều hoặc đi ngược chiều trên đường có biển "Cấm đi ngược chiều":
  - ô tô: 18–20 triệu đồng;
  - xe mô tô, xe gắn máy: 4–6 triệu đồng;
  - trên đường cao tốc mức phạt cao hơn (xem nguồn).

## 4. Vi phạm làn đường (LN)

### 4.1 Khi nào thành candidate

Có ba kiểu. Kiểu nào được bật tùy vào vạch sơn và biển báo thực tế tại từng nút, khai báo trong mục `rules` của cấu hình cảnh. Mọi kiểu đều cần thêm điều kiện 5 và 6 của mục 3.1 (chất lượng quan sát, không có ngữ cảnh miễn trừ).

- **LN-a — sai làn theo loại xe.** Loại xe không nằm trong `allowed_classes` của làn, **và**:
  - xe ở trong làn ≥ `min_dwell_s` giây và đi được ≥ `min_distance_m` mét;
  - phiếu bầu lớp của track ≥ `min_class_vote`.
- **LN-b — chuyển làn qua vạch liền.** Điểm tiếp đất của xe đi **hết** qua một đoạn vạch có `type: solid` sang làn bên cạnh, rồi ở lại làn mới ≥ `min_dwell_after_s` giây.
- **LN-c — đi sai hướng theo mũi tên của làn.** Xe ổn định trong làn A ở vạch dừng (≥ `min_entry_frames` khung), nhưng rời vùng giao lộ qua một cạnh `exits` có hướng không nằm trong `allowed_exits` của làn A.

### 4.2 Các tình huống trông giống nhưng không phải

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| L1 | Xe cắt ngang một làn để rẽ, hoặc vào/ra lề ở đoạn vạch đứt | Có mặt trong làn không dành cho mình | Chỉ đi ngang qua; thời gian và quãng đường trong làn ngắn | LN-a yêu cầu thời gian và quãng đường tối thiểu; đoạn vạch đứt được phép chuyển làn |
| L2 | Nhận sai lớp xe (ô tô con ↔ xe tải nhỏ, xe máy ↔ xe đạp điện) | Sai lớp nên trông như vào sai làn | Phiếu bầu lớp dao động giữa các khung | Ngưỡng `min_class_vote`; lớp không ổn định thì không gắn cờ LN-a |
| L3 | Xe buýt, xe ưu tiên đi vào làn mà biển báo cho phép | Loại xe khác nằm trong làn | Biển làn cho phép xe buýt hoặc xe ưu tiên | Khai báo `allowed_classes` đúng theo biển; xe ưu tiên được miễn trừ |
| L4 | Tránh vật cản, xe hỏng, tai nạn; làn bị chặn | Vượt vạch liền hoặc đi sai làn | Có vật cản phía trước; nhiều xe cùng tránh ở một chỗ | Nhiều xe cùng vượt tại một điểm trong thời gian ngắn thì chuyển cho người xem; điều hành viên có thể tạm dừng luật cho làn đó |
| L5 | Bánh xe chỉ đè lên vạch rồi trở lại làn cũ | Có chạm vạch liền | Điểm tiếp đất không sang hẳn làn khác | LN-b yêu cầu sang hẳn làn mới và ở lại đủ lâu |
| L6 | Vạch mờ, bị che, hoặc lệch cấu hình do camera rung | Xe "vượt" một vạch không có thật | Vạch trong cấu hình không khớp vạch thật trên ảnh | Kiểm tra định kỳ với ảnh hiệu chuẩn như E4; đoạn vạch đã mờ thì không khai báo là `solid` |
| L7 | Làn của xe ở vạch dừng không rõ vì xe nằm giữa hai làn | Làn vào bị gán sai nên hướng đi bị coi là "sai" (LN-c) | Điểm tiếp đất nằm sát ranh giới hai làn | LN-c chỉ xét khi xe ổn định trong một làn đủ số khung ở vạch dừng |
| L8 | CSGT phân luồng, cho rẽ ở làn khác trong thời gian ngắn | Hướng đi không khớp mũi tên | Có người điều khiển; nhiều xe cùng đi như vậy | Chế độ điều khiển tay; số ca tăng đột biến thì tạm dừng và hỏi điều hành viên (như C4) |

Làn được phép rẽ phải khi đèn đỏ (C3) cũng phải khai báo đúng trong `allowed_exits` và `right_turn_on_red`, để LN-c và luật vượt đèn đỏ không mâu thuẫn nhau.

### 4.3 Căn cứ pháp lý

- **Luật TTATGTĐB 2024, Điều 13:**
  - trên đường có nhiều làn cùng chiều, người lái phải đi trong một làn;
  - chỉ chuyển làn ở nơi cho phép, mỗi lần chỉ sang một làn liền kề, phải có tín hiệu báo trước;
  - người lái loại xe không được phép đi vào làn dành riêng cho loại xe khác thì không được đi vào làn đó.
- **Nghị định 168/2024/NĐ-CP**, lỗi đi không đúng phần đường hoặc làn đường quy định:
  - ô tô: 4–6 triệu đồng, trừ 2 điểm giấy phép lái xe;
  - xe mô tô, xe gắn máy: 600–800 nghìn đồng.
- Chuyển làn không đúng nơi cho phép, hoặc không có tín hiệu báo trước, cũng bị xử phạt theo Nghị định 168/2024 (xem nguồn).

## 5. Dừng, đỗ sai (ST) — COULD

### 5.1 Khi nào thành candidate

- Xe đứng yên (tốc độ dưới ngưỡng) trong một vùng `no_stop_zones` ≥ T giây, **và**
- đèn của hướng đi đó đang XANH, **và**
- phía trước xe không có hàng chờ.

Hai điều kiện sau dùng để loại xe dừng do đèn đỏ hoặc do ùn tắc.

### 5.2 Các tình huống trông giống nhưng không phải

| Mã | Tình huống | Vì sao trông giống | Dấu hiệu phân biệt | Cách loại trừ |
|---|---|---|---|---|
| S1 | Dừng chờ đèn đỏ, hoặc đứng trong hàng chờ | Đứng yên lâu trong vùng | Đèn đang đỏ, hoặc phía trước có xe đứng | Chỉ xét khi đèn XANH và phía trước trống |
| S2 | Ùn tắc chung, mọi làn đều chậm | Nhiều xe đứng yên trong vùng giao lộ | Mật độ cao ở mọi làn | Mức ùn tắc ≥ 2 thì không gắn cờ |
| S3 | Dừng nhường người đi bộ hoặc xe ưu tiên | Dừng vài giây trong vùng cấm | Có người trên vạch sang đường, hoặc có xe ưu tiên | Có người trên vạch sang đường hoặc xe ưu tiên thì bỏ |
| S4 | Xe chờ rẽ trái trong giao lộ, đã vào hợp lệ | Đứng yên giữa giao lộ | Đã vào giao lộ khi đèn xanh, đang chờ khoảng trống | Xe vào khi đèn xanh và đang ở vùng chờ rẽ thì bỏ (như A2) |
| S5 | Xe hỏng, gặp sự cố | Đứng yên rất lâu | Có đèn khẩn cấp (camera khó thấy); không di chuyển rất lâu | Camera không phân biệt được, nên chuyển người xem, không tự gắn cờ |
| S6 | Xe buýt đón, trả khách tại điểm dừng được phép | Dừng sát giao lộ | Là xe buýt, có biển điểm dừng | Không khai báo vùng điểm dừng xe buýt là vùng cấm |

### 5.3 Căn cứ pháp lý

**Nghị định 168/2024/NĐ-CP:**
- cấm dừng, đỗ xe tại nơi đường bộ giao nhau, hoặc trong phạm vi 05 mét tính từ mép đường giao nhau; ô tô bị phạt 800 nghìn – 1 triệu đồng;
- phần đường dành cho người đi bộ qua đường cũng là nơi cấm dừng, đỗ.

## 6. Hai kết luận thiết kế (áp dụng cho mọi loại vi phạm)

- **Hai loại nguyên nhân cần hai cơ chế.**
  - Xe không sai (nhóm A–C, và phần lớn các mã W, L, S): xử lý bằng quy tắc cố định và cấu hình cho từng nút. Những gì camera không thể biết thì chuyển cho người xem.
  - Hệ thống nhìn sai (nhóm D–E, và W4, W5, L2, L6): xử lý bằng cổng chất lượng. Không chắc thì im lặng, không bao giờ "đoán là vi phạm".
- **Mỗi lần loại trừ phải kèm mã lý do.** Nhờ vậy đo được quy tắc nào đang làm mất recall nhiều nhất, và có thể cho giám khảo xem hệ thống đã tự từ chối những trường hợp nào, vì lý do gì.

Mức phạt trong tài liệu này lấy từ các nguồn tổng hợp Nghị định 168/2024/NĐ-CP. Phải đối chiếu nguyên văn Nghị định trước khi đưa lên slide.

## Nguồn

- [Luật TTATGTĐB 2024 số 36/2024/QH15](https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Luat-trat-tu-an-toan-giao-thong-duong-bo-2024-so-36-2024-QH15-444251.aspx)
- [Tuổi Trẻ — Sửa đổi quy định về đèn xanh, đèn vàng từ 1/1/2025](https://tuoitre.vn/tu-1-1-sua-doi-quy-dinh-ve-den-xanh-den-vang-20250101212304966.htm)
- [Báo Hải Phòng — Quy định về xe ưu tiên theo Luật 2024](https://baohaiphong.vn/quy-dinh-ve-xe-uu-tien-theo-luat-trat-tu-an-toan-giao-thong-duong-bo-nam-2024-505122.html)
- [VnExpress — Rẽ phải ở làn đi thẳng khi đèn đỏ là lỗi vượt đèn đỏ](https://vnexpress.net/luat-su-re-phai-o-lan-di-thang-khi-den-do-la-pham-loi-vuot-den-do-5005383.html)
- [LuatVietnam — Các trường hợp được rẽ phải khi đèn đỏ](https://luatvietnam.vn/tin-phap-luat/khi-nao-gap-den-do-van-duoc-re-phai-230-26100-article.html)
- [LSVN — Mức phạt rẽ phải khi đèn đỏ](https://lsvn.vn/muc-phat-hanh-vi-re-phai-khi-den-do-va-dung-den-do-chan-loi-re-phai-a154106.html)
- [Chính phủ — Luật TTATGTĐB 2024 quy định sử dụng làn đường (Điều 13)](https://xaydungchinhsach.chinhphu.vn/luat-trat-tu-an-toan-giao-thong-duong-bo-quy-dinh-su-dung-lan-duong-119241218175948161.htm)
- [Chính phủ — Mức phạt đi ngược chiều theo Nghị định 168/2024](https://xaydungchinhsach.chinhphu.vn/muc-phat-moi-voi-nguoi-dieu-khien-xe-o-to-xe-may-di-nguoc-chieu-tu-1-1-2025-119241231112057474.htm)
- [Chính phủ — Toàn văn Nghị định 168/2024/NĐ-CP](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-168-2024-nd-cp-quy-dinh-xu-phat-vi-pham-hanh-chinh-ve-trat-tu-atgt-duong-bo-119241231164556785.htm)
- [Thư viện Pháp luật — Mức phạt chuyển làn không đúng quy định theo Nghị định 168](https://thuvienphapluat.vn/banan/tin-tuc/muc-phat-loi-chuyen-lan-duong-khong-dung-quy-dinh-moi-nhat-theo-nghi-dinh-168-13039)
- [VNLawFirm — Lỗi đi không đúng phần đường hoặc làn đường](https://vnlawfirm.vn/loi-di-khong-dung-phan-duong-hoac-lan-duong-phat-bao-nhieu/)
- [VNLawFirm — Dừng, đỗ xe tại nơi đường bộ giao nhau](https://vnlawfirm.vn/dung-xe-do-xe-tai-vi-tri-noi-duong-bo-giao-nhau-bi-phat-bao-nhieu/)
