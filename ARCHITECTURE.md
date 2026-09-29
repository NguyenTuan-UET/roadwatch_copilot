# Kiến trúc RoadWatch Copilot

Trang này chỉ là lối vào: repo **không** duy trì một bản mô tả kiến trúc độc lập ở đây.

| Cần gì | Đọc ở đâu |
|---|---|
| Kiến trúc, hợp đồng dữ liệu, ADR, tiêu chí nghiệm thu, câu hỏi mở. **Đây là nguồn chuẩn** | [docs/specs/roadwatch-architecture.md](docs/specs/roadwatch-architecture.md) |
| Sơ đồ trực quan: thành phần, trình tự xử lý, HITL, ranh giới triển khai. Bản tóm tắt dẫn chiếu tới spec | [docs/architecture_diagram.md](docs/architecture_diagram.md) |
| Bài toán và phạm vi | [docs/requirements/](docs/requirements/) |
| Phân việc, trạng thái task, tình trạng code | [docs/plan/README.md](docs/plan/README.md) |

**Tóm tắt một câu.** Runtime chạy offline trên CPU laptop:
- camera → BT-A (CV) đo khoảng cách và TTC;
- → BT-B (luật và máy trạng thái, không dùng LLM) quyết định có cảnh báo không;
- → câu tiếng Việt thu sẵn.

BT-C lo cấu hình có người duyệt (HITL), log và đánh giá.

**Khác với template môn học.** Bản `ARCHITECTURE.md` trước đây là khung của template AI20K (Next.js, LangGraph, LLM, vector store). RoadWatch **không** dùng các thành phần đó (spec: ADR-12, NG12). Code mẫu của template vẫn còn trong `src/agents/`, `src/api/`, `src/services/`, `src/models/`, `src/config.py`, `src/main.py`; phần này không thuộc sản phẩm RoadWatch.
