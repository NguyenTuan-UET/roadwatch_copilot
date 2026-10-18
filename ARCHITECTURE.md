# Kiến trúc RoadWatch Copilot

Trang này chỉ là lối vào: repo **không** duy trì một bản mô tả kiến trúc độc lập ở đây.

| Cần gì | Đọc ở đâu |
|---|---|
| Bài toán, phạm vi, kết quả, cài đặt và triển khai | [README.md](README.md) |
| Sơ đồ trực quan: thành phần, luồng xử lý, ranh giới triển khai | [docs/architecture_diagram.md](docs/architecture_diagram.md) |
| Kiến trúc, hợp đồng dữ liệu, ADR, tiêu chí nghiệm thu, câu hỏi mở. **Đây là nguồn chuẩn** | [docs/specs/roadwatch-architecture.md](docs/specs/roadwatch-architecture.md) |
| API của server | [docs/specs/roadwatch-api.md](docs/specs/roadwatch-api.md) |

**Tóm tắt một câu.** Runtime chạy offline ngay trên thiết bị (điện thoại):
- camera → BT-A (CV) đo khoảng cách tới xe dẫn đầu cùng làn;
- → BT-B (luật và máy trạng thái theo khoảng cách, không dùng LLM, không dùng TTC) quyết định có cảnh báo không;
- → chuông, câu tiếng Việt thu sẵn hoặc tiếng bíp.

**Thiết kế và code.** `main` có bản sản phẩm đã nộp: BT-A, BT-B rút gọn, server FastAPI (triển khai tại [c4-app-014.vercel.app](https://c4-app-014.vercel.app/)) và pipeline JS chạy offline trên điện thoại. Phần engine đầy đủ của spec (hợp đồng `contracts`, runtime nhiều thread, `rerun-B`) chưa có trên `main`: xem spec 12.4.

**Khác với template môn học.** Bản `ARCHITECTURE.md` trước đây là khung của template AI20K (Next.js, LangGraph, LLM, vector store). RoadWatch **không** dùng các thành phần đó (spec: ADR-12, NG12). Code mẫu của template đã được gỡ khỏi repo ngày 09/10/2026.
