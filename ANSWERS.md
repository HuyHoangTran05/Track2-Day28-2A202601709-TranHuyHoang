# Answers and reflection — Day 28 Track 2

## Hình thức và phạm vi đóng góp

Bài được thực hiện **cá nhân** bởi **Trần Huy Hoàng** trên nhánh
`ca-nhan-tran-huy-hoang`. Vì làm cá nhân, tôi đã lần lượt đi qua đầy đủ các vai trò:

- **Ingestion & Orchestration:** kiểm tra contract HTTP → Kafka, propagation của
  `traceparent`/`idempotency-key`, retry, replay và ranh giới Kafka → Airflow.
- **Data & ML:** triển khai nguồn MERGE replay-safe, kiểm tra Delta version/time travel,
  request Feast và provenance/promotion/rollback của MLflow.
- **Serving & Retrieval:** kiểm tra deterministic vector IDs, retrieval contract,
  model identity và chính sách degraded.
- **Platform & Observability:** kiểm tra Envoy, readiness, Prometheus/Grafana, OTLP/Jaeger,
  Kubernetes và GitOps manifests.
- **Presenter / Incident Commander:** lập chỉ mục evidence, chạy failure injection,
  profiling, ghi lại dấu hiệu, nguyên nhân và recovery proof.

## Phần khó nhất

Khó nhất là giữ cùng một định danh xuyên qua cả luồng đồng bộ và bất đồng bộ. HTTP request
có trace context riêng, Kafka có delivery riêng, còn Delta cần khóa logic ổn định để replay
không tạo thêm hàng. Nếu dùng `event_id` để dedupe thì mỗi lần delivery lại thành một fact
mới; nếu bỏ `traceparent` thì dữ liệu vẫn đúng nhưng trace bị đứt. Cách làm là tách rõ:

- `idempotency_key` xác định cùng một fact nghiệp vụ;
- `event_id` xác định từng delivery và là tie-breaker khi timestamp bằng nhau;
- `traceparent` chỉ dùng cho correlation và được truyền nguyên dạng khi có active trace.

## Trade-off đã chọn

1. **At-least-once + idempotent MERGE thay vì cố exactly-once toàn hệ thống.** Đây là cách
   dễ quan sát và khôi phục hơn khi Kafka/Airflow retry. Đổi lại, mọi consumer ghi state phải
   tôn trọng cùng idempotency contract.
2. **Optional Feast failure → `degraded`; Qdrant/Kafka failure → fail closed cho readiness.**
   Feature cá nhân hóa thiếu vẫn có thể trả lời có cảnh báo, nhưng retrieval hoặc ingestion
   mất thì pod không nên nhận luồng tương ứng.
3. **Pin model/revision và deterministic vector ID.** Tốn công quản lý version nhưng cho kết
   quả tái lập, không tăng point count khi index lại và đủ provenance để rollback.
4. **Evidence lấy từ control-plane API và test assertions.** Việc này chậm hơn chụp một màn
   hình “xanh”, nhưng evidence có ID/version, máy đọc được và có thể tái kiểm tra.
5. **Không giả lập gate GPU/LangSmith.** Khi không có endpoint/credential thật, trạng thái
   phải là `UNVERIFIED`; local Jaeger vẫn chứng minh trace leg nội bộ nhưng không thay thế
   bằng chứng LangSmith hay real-vLLM.

## Production gaps

- Secret manager, rotation, mTLS và policy mạng/egress cần được triển khai thật; repo chỉ
  giữ contract và không chứa credential.
- Compose dùng single-instance services; production cần HA Kafka, replicated object store,
  backup/restore đã diễn tập và multi-AZ placement.
- Cần schema registry/compatibility gate, quota theo tenant và audit retention policy.
- Cần autoscaling dựa trên queue/latency, capacity test dài hạn và memory-leak/soak test;
  profile trên laptop không được xem là production capacity.
- Cần ký image/SBOM, vulnerability scanning, admission policy và promotion qua môi trường.
- Real-vLLM cần endpoint GPU ổn định, authentication, model cache và cold-start runbook.
- LangSmith export cần credential do lớp cấp; local trace backend không chứng minh external
  export khi credential vắng mặt.

## Điều sẽ cải tiến

Nếu có thêm thời gian, tôi sẽ bổ sung một CI workflow chia thành ba gate: fast/offline,
Compose integration, và GPU/LangSmith theo môi trường; xuất JUnit + evidence manifest có
checksum; thêm soak test cho `/api/v1/ask`; và tự động đối chiếu run ID, trace ID, Delta
version, MLflow version giữa các evidence file để phát hiện một bundle bị ghép từ nhiều lần
chạy khác nhau.
