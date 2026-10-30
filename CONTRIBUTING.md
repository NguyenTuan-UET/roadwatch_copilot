# Đóng góp cho RoadWatch Copilot

Đọc [AGENTS.md](AGENTS.md) trước khi thay đổi code hoặc tài liệu.

## Quy trình

1. Tạo nhánh từ `main`: `git checkout -b feat/ten-thay-doi`
2. Commit theo [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`
3. Chạy các lệnh kiểm tra ở [code-rules](docs/development/code-rules.md), mục 8,
   trước khi push. Repo không có CI nên phải chạy tay.
4. Mở PR vào `main`, ghi rõ đã kiểm chứng thế nào và còn thiếu gì.

## Không commit thông tin bí mật

Tuyệt đối không commit API key, token hay credential, kể cả trong
`.env.example`, comment hay tài liệu.

- `.env.example` chỉ chứa **placeholder**.
- Giá trị thật đặt trong `.env`, file này đã nằm trong `.gitignore`.
- Nếu lỡ commit, key coi như đã lộ và **phải được xoay (rotate)**; xóa commit
  thôi là chưa đủ.

## Quy tắc ứng xử

Tham gia repo này đồng nghĩa với việc bạn đồng ý tuân thủ
[Quy tắc ứng xử](CODE_OF_CONDUCT.md).
