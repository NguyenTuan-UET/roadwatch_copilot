## Thay đổi gì

<!-- Mô tả ngắn gọn. Nếu sửa Technical Book, ghi rõ chương nào và vì sao. -->

## Loại thay đổi

- [ ] `fix` — sửa lỗi
- [ ] `feat` — tính năng mới
- [ ] `docs` — **nội dung Technical Book** (`docs/guide/**`) → cần review của @AI20K-Build-Phase/book-maintainers
- [ ] `chore` / `refactor` / `test`

## Checklist

- [ ] Ruff sạch: `ruff check src/roadwatch tests/roadwatch scripts/roadwatch --extend-exclude src/roadwatch/vendor`
- [ ] Pytest xanh: `python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q`
- [ ] Đổi API: đã chạy `python -m scripts.roadwatch.export_api_schema --check`
- [ ] **Không có API key / token / credential** trong diff (kể cả `.env.example`)
- [ ] Nếu đụng `docs/guide/**`: đã kiểm tra nội dung hiển thị đúng và link không chết

<!--
Nhắc: nội dung docs/guide/ merge vào main sẽ được đồng bộ lên
https://phoenix.note.transformerlabs.ai/technical-book
-->
