# Failure injection and recovery record

## Sự cố đã tạo

Kịch bản: **dừng Feast**, một optional dependency, bằng `docker compose stop feast`. Script
`scripts/capture_incident.py` luôn khởi động lại service trong `finally`, không xóa volume, database,
`.lab28/` hoặc replay DLQ.

- Inject lúc: `2026-09-03T09:26:28.400909+00:00`
- Quan sát lúc: `2026-09-03T09:26:34.985844+00:00`
- Khôi phục xong lúc: `2026-09-03T09:26:49.081382+00:00`
- Bằng chứng đầy đủ: `evidence/incident-recovery.json`

## Dấu hiệu quan sát

Trước sự cố, Feast là `ready: true`. Trong outage, probe chuyển thành `ready: false` với
`unreachable: ConnectError`; trace quan sát là `1db5e124a9a73e7ff368ba41aa812586`. Readiness tổng
thể vẫn mang nhãn `degraded` vì vLLM optional vốn chưa có endpoint trên máy này; dấu hiệu phân biệt
sự cố là Feast xuất hiện thêm trong danh sách component lỗi, không phải chỉ nhìn nhãn tổng.

State trước inject:

- Delta feedback: version 9, 19 rows
- Delta documents: version 6, 17 rows
- Qdrant: 17 points

## Nguyên nhân

Feast container bị dừng có chủ đích nên API không kết nối được online feature server. Chính sách
readiness xem Feast là optional: hệ thống phải báo suy giảm rõ ràng thay vì che lỗi hoặc fail toàn bộ
các đường dữ liệu không phụ thuộc feature cá nhân hóa.

## Khôi phục và chứng minh không mất dữ liệu

Chạy `docker compose start feast`, đợi health probe thành công rồi gọi lại `/ready`. Feast trở về
`ready: true` với detail `ok`; trace recovery là `3995cd1b319e75bd3f4bbbd278b94bc3`.

State sau recovery giữ nguyên Delta feedback version 9/19 rows, documents version 6/17 rows và
Qdrant 17 points. Hai assertion cuối trong evidence đều là:

- `no_data_loss: true`
- `no_duplicate_rows: true`

Vì baseline/final vẫn thiếu real-vLLM, nhãn tổng hợp hợp lệ ở cả hai mốc là `degraded`; recovery
được xác nhận bằng trạng thái riêng của Feast và state checksum/count, không bằng cách sửa giả nhãn.
