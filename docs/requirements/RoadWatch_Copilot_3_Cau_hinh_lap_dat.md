# RoadWatch Copilot: lắp đặt camera và hiệu chuẩn tự động (MVP)

> MVP **không có hồ sơ xe**. Camera **tự hiệu chuẩn** khi xe chạy; người dùng chỉ nhập **một** tham số: khoảng cách từ camera tới cản trước. Giá trị các tham số chỉ ghi ở file này; hai file tổng quan và bài toán chính dẫn chiếu tới đây.

Trạng thái: ✅ đã chốt · 🟡 giả định, cần kiểm chứng · ⬜ chưa có (TBD)

---

## 1. Quyết định ADR-04: bỏ hồ sơ xe, camera tự hiệu chuẩn

| | |
|---|---|
| **Ngày** | 28/09/2026; cập nhật 06/10/2026 |
| **Trạng thái** | ✅ Đã chốt (PO) |
| **Bối cảnh** | Người dùng gắn camera hoặc điện thoại mỗi chuyến một kiểu; tiêu cự khác nhau theo thiết bị. Bắt người dùng đo và nhập tham số hình học là không khả thi. |
| **Quyết định** | Phần mềm tự ước lượng tiêu cự, góc lắp (pitch, yaw) và chiều cao camera từ chính video khi xe chạy. Người dùng chỉ nhập khoảng cách camera–cản trước. |
| **Bỏ khỏi MVP** | VehicleProfile và danh mục hãng, mẫu, đời xe; màn hình chọn xe, nhập kích thước xe; nhập tay tham số hình học của camera. |
| **Giữ nguyên** | Người dùng U1b (người mới đổi xe) vẫn là người dùng chính. |
| **Hệ quả** | Phạm vi hỗ trợ là nhóm thiết bị và xe mà hiệu chuẩn tự động đạt sai số cho phép (mục 4). Nhóm không đạt thì **giới hạn phạm vi hỗ trợ**. |

---

## 2. Cách đo

Khoảng cách tính theo **phương ngang**, song song mặt đường theo hướng xe chạy, tới cản trước:

```
khoảng cách giữa hai xe = khoảng_cách_camera − d_cam_cản
```

- `khoảng_cách_camera` lấy từ model openpilot supercombo, chạy trên ảnh đã được warp vào khung ảnh mà model được huấn luyện. Phép warp dùng tiêu cự và góc lắp do hiệu chuẩn tự động ước lượng (spec 4.2).
- Hiệu chuẩn cần xe chạy đủ nhanh và gần như thẳng: khoảng 10 s để học tiêu cự và khoảng 30 s để chốt góc lắp. Trong lúc đó không cảnh báo khoảng cách.
- Camera bị lắp lại hoặc xê dịch thì phần mềm tự phát hiện và hiệu chuẩn lại.
- `d_cam_cản` là sai số cộng: sai 0,3 m thì kết quả lệch đúng 0,3 m ở mọi dải.

**Mong muốn sai số 0,5–1 m** chỉ là mong muốn cần kiểm chứng theo từng dải khoảng cách. Đây **chưa phải kết quả hay cam kết**.

---

## 3. Tham số

| Nhóm | Tham số | Giá trị MVP | Trạng thái | Cách có |
|---|---|---|---|---|
| Lắp đặt | Vị trí lắp | Trong xe, khu vực cạnh gương chiếu hậu, nhìn thẳng ra trước | ✅ | Quy định |
| Lắp đặt | `d_cam_cản`: khoảng cách theo phương ngang từ camera tới cản trước | 1,5 m | 🟡 giả định | Người dùng nhập; nhóm đo thực địa (KS-3) |
| Camera | Tiêu cự, pitch, yaw, chiều cao camera | Tự ước lượng | ✅ | Hiệu chuẩn tự động (spec 4.2); tiêu cự lấy từ thiết bị nếu thiết bị báo được |
| Camera | Thiết bị hoặc nguồn video | TBD | ⬜ | Nhóm chọn |
| Quản lý | Phiên bản và mã hash của cấu hình | Có | ✅ | Ghi vào thông tin mỗi lần chạy để tái lập kết quả |

**Quy tắc**

- Tài xế chỉ nhập `d_cam_cản`; không có màn hình hiệu chuẩn.
- Số đo chưa tin cậy (đang hiệu chuẩn, vừa phát hiện lắp lại) thì không phát cảnh báo khoảng cách, chỉ báo trạng thái suy giảm.
- Thay đổi cấu hình kỹ thuật đi theo quy trình duyệt đã thống nhất: kỹ sư đề xuất, người duyệt phê duyệt rồi mới áp dụng; có phiên bản; quay lui được.

---

## 4. Khảo sát chọn xe thử nghiệm

### 4.1 Doanh số bán mới

**Năm 2025**, top 10 mẫu xe theo số VAMA, VinFast và TC Motor, do Thanh Niên tổng hợp ngày 14/01/2026:

| # | Mẫu xe | Số xe |
|---|---|---|
| 1 | VinFast VF 3 (minicar điện) | 44.585 |
| 2 | VinFast VF 5 (A-SUV điện) | 43.913 |
| 3 | VinFast Limo Green (MPV điện, dòng xe dịch vụ) | 27.127 |
| 4 | VinFast VF 6 | 23.291 |
| 5 | Mitsubishi Xpander | 19.891 |
| 6 | Ford Ranger | 18.692 |
| 7 | Mazda CX-5 | 17.262 |
| 8 | Mitsubishi Xforce | 15.254 |
| 9 | Toyota Yaris Cross | 14.601 |
| 10 | Toyota Vios | 13.424 |

- Theo số VinFast công bố, tổng năm 2025 là 175.099 xe. Herio Green (12.568 xe) được tính **riêng**, không nằm trong số của VF 5.
- Các hãng thành viên VAMA bán tổng cộng 375.736 xe trong năm 2025.

**8 tháng đầu năm 2026** (số VinFast, Thanh Niên đăng ngày 12/09/2026):

| Mẫu xe | Lũy kế 8 tháng | Ghi chú |
|---|---|---|
| VF 3 | 35.798 | |
| Limo Green | 34.991 | |
| VF 5 | 27.948 | Số tháng 8 ghi rõ là **đã gồm** Herio Green. Cách tính khác với năm 2025, nên không cộng thẳng hai năm |
| VF 6 | 15.943 | |

Tổng VinFast 8 tháng đầu 2026 là 154.073 xe.

### 4.2 Số xe đang lưu hành (khác với doanh số bán mới)

- **Cục Đăng kiểm Việt Nam:** trang thống kê, khi truy cập ngày 28/09/2026, hiển thị mặc định số liệu tháng 9/2022 là 4.937.988 ô tô đang lưu hành. Trang **không** chia theo hãng hay mẫu xe.
- **Cục CSGT:** số ô tô đăng ký mới là 491.394 xe năm 2024; 624.300 xe năm 2025 (công bố ngày 26/12/2025); 513.679 xe trong 9 tháng đầu năm 2026.
- **Không tìm thấy nguồn chính thức nào công bố số xe đang lưu hành theo từng mẫu xe.**

**Hệ quả:** VF 3 và VF 5 dẫn đầu doanh số bán mới năm 2025 và 8 tháng đầu năm 2026. Nhưng không thể kết luận hai mẫu này chiếm đa số xe đang lưu hành.
- Suy luận từ các số ở trên (không phải số chính thức): đội xe hiện hữu chủ yếu là xe đăng ký trước năm 2025, thuộc nhiều hãng và mẫu khác nhau.
- Limo Green và Herio Green là dòng xe dịch vụ, không gần với người dùng chính (tài xế mới).

### 4.3 Đề xuất

- **Xe thử 1 (ưu tiên): VF 3 hoặc VF 5, nếu nhóm tiếp cận được thực tế.** Đây là hai mẫu bán mới nhiều nhất năm 2025 và 8 tháng đầu năm 2026; người mua xe mới là nhóm gần với U1b.
- **Xe thử 2: một mẫu khác kiểu dáng mà nhóm tiếp cận được**, ví dụ sedan hạng B hoặc MPV có trong top 10 năm 2025, để đo phạm vi áp dụng của hiệu chuẩn tự động.
- Các mẫu xe trên khác nhau nhiều về hình dáng (minicar, A-SUV, sedan, MPV). Vì vậy `d_cam_cản` **phải đo trên từng xe thử**, không suy ra từ kích thước tổng thể của xe.
- **Chưa xác minh:** nhóm tiếp cận được những xe nào (xem KS-1).

### 4.4 Việc còn mở: khảo sát thực địa

Chưa có số đo thực địa nào. Các giá trị dưới đây phải đo, không ước lượng.

| Mã | Việc | Cần có | Xong khi | Trạng thái |
|---|---|---|---|---|
| KS-1 | Xác định xe nhóm tiếp cận được: mẫu, đời, và chủ xe đồng ý cho gắn camera, quay | Danh sách xe | Có ít nhất 2 xe khác kiểu dáng | ⬜ |
| KS-3 | Đo `d_cam_cản` theo phương ngang trên từng xe thử | Thước, dây dọi hoặc vạch kẻ trên nền | Có số đo; chốt hoặc sửa giả định 1,5 m | ⬜ |
| KS-6 | Chụp xe đứng yên ở các khoảng cách đo bằng thước (10, 20, 40, 60 m, xa hơn nếu an toàn) trên mỗi xe thử | Bãi trống an toàn, thước dây | Có bảng sai số theo dải cho từng xe | ⬜ |

### 4.5 Kiểm chứng phạm vi áp dụng

- Trên mỗi xe thử, chỉ nhập `d_cam_cản` của xe đó, để phần mềm tự hiệu chuẩn, rồi đo sai số theo dải 0–30 / 30–60 / 60–100 m. So với KITTI raw (khoảng cách LiDAR).
- Ngưỡng sai số cho phép theo từng dải: ⬜ TBD, chốt với mentor sau khi có số đo đầu tiên.
- Xe hoặc nhóm xe không đạt thì ghi là “ngoài phạm vi hỗ trợ” trong tài liệu và demo.

---

## 5. Nguồn

- VinFast, thông cáo doanh số 2025: [vinfastauto.com](https://vinfastauto.com/vn_vi/vinfast-lap-ky-luc-ban-giao-xe-o-to-dien-tai-viet-nam-2025). Trang chặn truy cập tự động nên số liệu được đối chiếu qua [Tuổi Trẻ, 14/01/2026](https://tuoitre.vn/khoahocphothong/vinfast-lap-ky-luc-ban-giao-175-099-xe-o-to-dien-tai-viet-nam-nam-2025-104263734.htm).
- Top 10 mẫu xe năm 2025 (VAMA, VinFast, TC Motor): [Thanh Niên, 14/01/2026](https://thanhnien.vn/10-o-to-ban-chay-nhat-viet-nam-nam-2025-o-to-dien-vinfast-ap-dao-185260113213157679.htm).
- VAMA năm 2025: [VietnamNet](https://vietnamnet.vn/thanh-vien-vama-ban-375-736-xe-trong-nam-2025-2481622.html); báo cáo gốc tại [vama.org.vn](http://vama.org.vn/vn/bao-cao-ban-hang.html).
- VinFast tháng 8 và 8 tháng đầu năm 2026: [Thanh Niên, 12/09/2026](https://thanhnien.vn/vinfast-ban-giao-hon-20000-o-to-dien-tai-viet-nam-trong-thang-82026-185260911193400578.htm).
- Cục Đăng kiểm Việt Nam, thống kê phương tiện: [vr.org.vn](https://www.vr.org.vn/thong-ke/Pages/tong-hop-so-lieu-phuong-tien-giao-thong-trong-ca-nuoc.aspx).
- Cục CSGT, đăng ký mới năm 2025: [Thanh tra, 26/12/2025](https://thanhtra.com.vn/tieu-dung-AA9F50895/du-lieu-cuc-canh-sat-giao-thong-cong-bo-o-to-dang-ky-moi-tang-27-fd5a0425f.html). Đăng ký mới 9 tháng đầu năm 2026: [Tuổi Trẻ, 24/09/2026](https://tuoitre.vn/ca-nuoc-co-hon-33-trieu-xe-duoc-dang-ky-moi-trong-9-thang-dau-nam-2026-100260924115759761.htm).

*Tạo ngày 28/09/2026.*
