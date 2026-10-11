# gr14VinAI — phục dựng kiến trúc 707 đầu ra

`src/model.py` dựng mạng PyTorch có gradient từ đúng đồ thị trong `../P-014/models/gr14VinAI.onnx`. Giữ nguyên node, kết nối, tensor trọng số và hợp đồng ONNX; không thay bằng mạng khoảng cách ba đầu ra.

Đây là **phục dựng từ artifact ONNX ngày 10/10/2026**. Không khôi phục được lịch sử train, dữ liệu train gốc, optimizer, loss hay checkpoint trước đây từ artifact này. Trọng số nguồn khớp bản supercombo được tỉa trong P-014; repo này không tạo bằng chứng cho một lần train đã mất. Các lần fine-tune mới có checkpoint, hash dữ liệu và log riêng.

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-train.txt
```

Đã kiểm tra bằng Python 3.13, PyTorch CPU. Muốn train GPU, cài bản PyTorch phù hợp rồi dùng `--device cuda`.

## Kiến trúc và hợp đồng

| Tensor | Shape | Kiểu |
|---|---|---|
| `new_img` | `[2,6,128,256]` | uint8 |
| `state_img_q` | `[2,5,6,128,256]` | uint8 |
| `outputs` | `[1,707]` | float32 |
| `next_state_img_q` | `[2,5,6,128,256]` | uint8 |

Hai ảnh của `new_img` là khung chính và khung rộng của **cùng thời điểm**, không phải frame trước/frame hiện tại. Mỗi ảnh gồm bốn pha pixel Y và hai plane U,V. Ảnh phải được warp theo camera như luồng P-014; cache `[N,12,128,256]` của mạng ba đầu ra không dùng trực tiếp. Chuỗi chạy ở 20 Hz, đưa `next_state_img_q` lại vào `state_img_q`; reset queue về 0 ở đầu clip. Không tự thay queue của frame giữa clip bằng 0.

Đồ thị gồm 224 node: Conv/Gemm, các nhánh có residual và GELU, xử lý hai khung nhìn, đặc trưng chuẩn hóa và các head được giữ lại. `inspect` in số node/operator/tham số thực tế từ file nguồn; không suy ra kiến trúc bằng tên model.

| Nhóm trong `outputs` | Slice Python | Nội dung raw |
|---|---|---|
| `pose` | `0:12` | Mean và log-standard-deviation cho 6 giá trị |
| `road_transform` | `12:24` | Mean và log-standard-deviation cho 6 giá trị |
| `lane_lines` | `24:552` | Mean và log-standard-deviation cho 4×33×2 giá trị |
| `lane_lines_prob` | `552:560` | 8 logits |
| `lead` | `560:704` | Mean và log-standard-deviation cho 3×6×4 giá trị |
| `lead_prob` | `704:707` | 3 logits |

TTC/hiệu chuẩn vẫn là hậu xử lý của RoadWatch, không được đưa vào đồ thị train. Bộ decoder cũ của P-014 tiếp tục đọc được artifact xuất ra.

## Kiểm tra và xuất lại

```bash
python src/train.py inspect
python src/train.py verify --samples 3
python src/train.py export --out model/restored/gr14VinAI.onnx
```

`--source /duong/dan/model.onnx` đặt **trước** subcommand để chỉ định nguồn khác. Nguồn mặc định là `../P-014/models/gr14VinAI.onnx`.

`verify` kiểm queue chính xác, so PyTorch FP32 với cùng đồ thị ONNX đã chuyển FP32, đồng thời kiểm ONNX xuất lại chưa train so với artifact nguồn. Nguồn lưu trọng số FP16; phép train tính FP32 để hỗ trợ autograd ổn định. Báo cáo tách sai khác FP16/FP32 khỏi sai khác dựng đồ thị. Export giữ dtype gốc, không xuất mạng khác có tên output giống nhau. Trước fine-tune, các tensor trọng số và node của bản export khớp nguồn. Không ghi đè nguồn hoặc output đã có.

## Fine-tune mới

Dữ liệu train và validation là hai file NPZ riêng, mỗi file có đúng bốn array:

| Array | Shape | Yêu cầu |
|---|---|---|
| `new_img` | `[N,2,6,128,256]` | uint8, đã warp/pack đúng |
| `state_img_q` | `[N,2,5,6,128,256]` | uint8, queue đúng trước mỗi frame |
| `targets` | `[N,707]` | float, mục tiêu theo layout raw ở bảng trên |
| `target_mask` | `[N,707]` | bool, chỉ True nơi có nhãn |

Mỗi mẫu cần ít nhất một nhãn hữu hạn. Vị trí không có nhãn đặt mask False, có thể để target NaN; không coi thiếu nhãn là 0. Loss là Smooth L1 trên các vị trí có nhãn, không phải khẳng định về loss gốc đã mất. Ví dụ nhãn khoảng cách cho lựa chọn lead đầu tiên ứng với mean raw index 560; phải thống nhất mốc đo của nhãn với model. Nhãn xác suất muốn dùng loss trên raw cần đổi thành logits hữu hạn; huấn luyện phân loại chuyên biệt cần loss BCE phù hợp thay vì tự coi logits là xác suất. Không huấn luyện những head không có nhãn.

```bash
python src/train.py train --train-data data/train707.npz --val-data data/val707.npz \
  --epochs 10 --lr 0.00001 --out-dir results/train707
python src/train.py export --checkpoint results/train707/best.pt \
  --out model/restored/gr14VinAI-finetuned.onnx
```

Checkpoint tốt nhất được chọn theo validation. Thư mục kết quả phải mới; dữ liệu train và val trùng hash bị từ chối. Người tạo dữ liệu phải tách video/phiên để tránh rò rỉ giữa hai tập. `training.json` ghi nguồn, hash dữ liệu, seed, tham số, số bước và trạng thái thật; `epochs.jsonl` ghi loss từng epoch. Export sau train ghi hash checkpoint trong metadata và file JSON đi kèm. Không sửa model nguồn trong P-014.

Chưa có dữ liệu train707/val707 thực tế trong repo. Test gradient dùng mẫu tổng hợp tạm để kiểm kỹ thuật, không phải đo chất lượng hay chứng minh huấn luyện thực địa. Muốn train từ đầu cần kiến trúc chưa fusion và quy trình khởi tạo/loss thích hợp; công cụ này hỗ trợ fine-tune đồ thị đã fusion từ artifact có sẵn.

## Code ba đầu ra được giữ riêng

`src/distance_model.py`, `src/train_distance.py`, model/checkpoint ở `model/gr14VinAI.*` và `src/app.py` thuộc model ba đầu ra trước đây (`input_imgs` → `has_target`, `distance_m`, `lane_left_m`). Các tool benchmark/eval cũ tiếp tục import `train_distance`. Báo cáo trong `report/` thuộc model đó, không dùng làm số đo của bản 707 đầu ra. Chạy lại bộ đó bằng `python src/train_distance.py ...`.

## Kiểm thử

```bash
pip install pytest opencv-python-headless Pillow
python -m pytest src/test_restored_model.py src/test_gr14vinai.py src/test_preprocess_dataset.py -q
```

Test mới đối chiếu đồ thị/trọng số, forward, queue, gradient, một bước optimizer và ONNX sau cập nhật. Test giao diện cũ cần Gradio, cài riêng nếu dùng `src/app.py`.
