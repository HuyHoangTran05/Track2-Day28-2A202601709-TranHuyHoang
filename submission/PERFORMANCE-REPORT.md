# Performance profile

Ngày đo: **2026-09-03** trên Windows, Docker Desktop, 16 logical CPU. Mỗi lượt gửi 200 request.
Số liệu máy đọc được nằm trong `evidence/performance-profile.json`.

## Kết quả

Latency bên dưới tính trên mọi response; bảng sau đó tách riêng response HTTP 200 để tránh các
HTTP 429 trả nhanh làm P50 trông tốt giả tạo.

| Đường đo | Workers | HTTP status | P50 | P95 | P99 | Non-2xx |
|---|---:|---|---:|---:|---:|---:|
| Gateway `GET /ready` | 8 | 200: 8, 503: 12, 429: 180 | 6.83 ms | 16.17 ms | 5611.67 ms | 96.0% |
| Gateway `GET /ready` | 16 | 200: 13, 429: 187 | 7.28 ms | 760.97 ms | 986.13 ms | 93.5% |
| API trực tiếp `GET /ready` | 8 | 200: 200 | 457.70 ms | 639.50 ms | 689.31 ms | 0% |
| API trực tiếp `GET /ready` | 16 | 200: 200 | 1946.57 ms | 9233.92 ms | 9474.45 ms | 0% |

Successful-only latency qua gateway:

| Workers | P50 | P95 | P99 |
|---:|---:|---:|---:|
| 8 | 5561.59 ms | 5636.26 ms | 5636.26 ms |
| 16 | 920.74 ms | 1013.81 ms | 1013.81 ms |

## Diễn giải bottleneck

Gateway được cấu hình token bucket 10 request/giây, vì vậy tỷ lệ 429 cao là **kết quả đúng của
policy**, không phải capacity của API. Lượt 8 workers còn có 12 HTTP 503 khi các readiness fan-out
đồng thời làm dependency probe quá tải; các response 200 chậm khoảng 5.6 giây cho thấy tail latency
bị che bởi hàng loạt 429 rất nhanh.

Khi bỏ gateway và gọi thẳng API, 200/200 request đều thành công nhưng tăng workers từ 8 lên 16 làm
P50 tăng khoảng 4.25 lần và P95 tăng khoảng 14.4 lần. Bottleneck thực tế của `/ready` là fan-out tuần
tự/đồng thời đến Kafka, MLflow, Qdrant, vLLM và Feast cùng giới hạn tài nguyên của các container, chứ
không phải Kafka data path.

## Giới hạn kết luận

`POST /api/v1/ask` không được gán số liệu vì không có real-vLLM GPU endpoint; gate này giữ
`UNVERIFIED`. Số đo laptop chỉ dùng để phát hiện xu hướng và kiểm tra rate-limit/degraded behavior,
không đại diện production capacity. Cải tiến tiếp theo là cache ngắn kết quả readiness, giới hạn
concurrency cho probe, đo từng component histogram và chạy soak test trên GPU endpoint thật.
