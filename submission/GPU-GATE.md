# Gate GPU / real-vLLM

Gate này chỉ chuyển sang xanh khi có endpoint vLLM **thật**. Bản ghi dưới đây là những gì đã
chạy được, những gì chưa, và các lỗi mà chính gate này phơi ra trong nền tảng.

## Endpoint đã dùng

| Hạng mục | Giá trị |
|---|---|
| Phần cứng | 2× Tesla T4 (Kaggle interactive session), driver 580.159.04, CUDA 13.0 |
| Server | vLLM 0.26.0, `--dtype half`, `--max-model-len 4096`, `--gpu-memory-utilization 0.85` |
| Model | `Qwen/Qwen3-1.7B` — trùng `LAB28_VLLM_MODEL_ID` mặc định và tag đã ghi trong MLflow |
| Reasoning | `--reasoning-parser qwen3` |
| Kết nối | tunnel HTTPS tạm; hostname **không** được commit, evidence redact thành `<vllm-endpoint-host>` |

`evidence/ip07-vllm-identity.json` là bằng chứng máy đọc được: `reachable: true`,
`version: 0.26.0`, `served_models: ["Qwen/Qwen3-1.7B"]`, kèm danh sách metric `vllm:*` —
đây là ba thứ mà một server OpenAI-compatible giả không tạo ra được.

Lần đầu tiên trong bài, `/ready` trả **`ready`** với cả năm component:

```text
kafka   True  1 broker(s); 4 declared topics present
mlflow  True  lab28-rag-release v2 is champion
qdrant  True  21 points; ok
vllm    True  vLLM identity confirmed
feast   True  ok
```

Prometheus đồng thời scrape được endpoint thật: **10/10 target `up`**, không còn target down.

## Kết quả test có gate `gpu`

| Module | Kết quả |
|---|---|
| `test_j3_promotion_rollback.py` + `test_prometheus_targets.py` | **4 passed**, 11 deselected, 99.86s |
| `test_j4_degraded_recovery.py` | **4 passed**, 9 deselected, 349.19s |
| `test_j1_golden_path.py` | **2 passed, 1 chưa xanh** — test grounding fail vì lỗi số 7/8 bên dưới |
| `test_j5_trace_metrics_continuity.py`, `test_trace_span_coverage.py` | **chưa hoàn tất** — 4 test |

Tổng: **10/15 test `gpu` đã pass thật**. Năm test còn lại đều cần một DAG run end-to-end, và
chúng chưa chạy xong vì giới hạn của chính máy này chứ không vì assertion: Docker engine sập
giữa lượt (`500` trên mọi route), producer Kafka của API treo sau đó (lỗi số 7), và session
Kaggle tự tắt sau ~40 phút không có thay đổi trong notebook nên endpoint GPU mất giữa đường.
Không test nào bị nới assertion hay skip để tránh; trạng thái ghi đúng là chưa xong.

## Lỗi thật mà gate này phơi ra

Mười lỗi dưới đây tồn tại từ trước nhưng bị che vì 15 test `gpu` luôn bị skip khi không có
endpoint. Trừ lỗi số 8 được ghi lại thành khuyến nghị, tất cả đã được sửa ở tầng cấu hình,
không phải bằng cách sửa assertion.

1. **Airflow metadata dùng SQLite với `LocalExecutor`.** Dưới một loạt DAG run, writer gặp
   `sqlite3.OperationalError: database is locked` và **scheduler chết**; task cuối không bao
   giờ được xếp lịch, và mọi run sau đó tắc sau `MAX_ACTIVE_RUNS_PER_DAG=1`. SQLite được
   Airflow ghi rõ là chỉ dùng cho `SequentialExecutor`. Đã thêm service Postgres cho metadata.
2. **Spark Connect mặc định `local[*]`** nên chiếm cả 16 core; Kafka nằm cùng máy và mất
   broker heartbeat (`request timeout 2000ms`), Airflow cùng readiness probe bò chậm. Đặt
   `spark.master=local[8]` + driver 2g. `local[4]` đã đo là quá ít: merge tăng từ 98s lên 227s.
3. **`dag-processor` chết vì `ValueError: write to closed file`** trong chính pipeline log của
   nó. `airflow standalone` không giám sát các thành phần con, nên không còn gì parse DAG, DAG
   thành stale và API trả **404** — trong khi healthcheck vẫn báo `healthy` vì nó chỉ hỏi
   endpoint có trả lời hay không. Healthcheck giờ đọc verdict **từng thành phần** của
   `/api/v2/monitor/health`. Lưu ý còn lại: Docker không tự restart container `unhealthy`, nên
   đây là tín hiệu để người vận hành hành động, chưa phải tự chữa; Airflow không nằm trong
   manifest triển khai nên chưa tách thành các service riêng.
4. **Prometheus hard-code target `host.docker.internal:8001`.** Endpoint thật không nằm trên
   máy đó. Chuyển sang `file_sd_configs`, target sinh lúc chạy bằng
   `scripts/render_vllm_target.py`, file đã gitignore vì chứa hostname tạm.
5. **`readinessProbe` trong `deploy/kubernetes/base/api.yaml` không đặt `timeoutSeconds`**,
   tức mặc định 1s — nhỏ hơn độ trễ thật đo được của `/ready` (1.6–2.7s khi phải probe endpoint
   ở xa). Trên cluster thật probe này sẽ fail dù pod đang trả lời đúng. Đã đặt `timeoutSeconds: 5`.
6. **Deadline chờ DAG 300s trong suite** nhỏ hơn thời lượng thật khi Spark driver còn lạnh.
   Đo được: ~101s với driver warm, ~7 phút cho run đầu sau khi driver restart. Nâng lên 600s.

7. **Producer Kafka của API không tự hồi phục.** Sau khi Docker engine trên máy này sập và
   quay lại, mọi `POST /api/v1/documents` trả `503 dependency_unavailable — Kafka delivery
   failed: 1 message(s) undelivered`, kéo dài tới khi restart process; offset `data.raw` không
   tăng. Kafka lúc đó hoàn toàn bình thường: partition có leader, ISR đủ, broker không bị
   fence, `Produce` API dùng được. Vậy lỗi nằm ở handle producer dài hạn, không ở broker.
8. **`/ready` báo `kafka: True` trong suốt sự cố đó.** `probe_kafka` tạo một `AdminClient`
   **mới** mỗi lần gọi, nên nó kiểm tra một kết nối khác với kết nối mà đường ghi thật sự dùng.
   Kết quả: readiness xanh trong khi ingest chết hoàn toàn, và triệu chứng nổi lên ở chỗ khác —
   test grounding của J1 fail vì document của nó không bao giờ vào được index. Đây là lỗi
   **chưa sửa**: cách đúng là readiness phải phản ánh trạng thái của chính publisher mà ứng dụng
   dùng (ví dụ latch lỗi delivery gần nhất, xoá khi có delivery thành công) thay vì mở một
   kết nối sạch để tự trấn an. Việc này cần thay đổi cách app giữ và chia sẻ publisher, nên
   được ghi lại thành khuyến nghị chứ không sửa vội ở cuối buổi.
9. **`dagbag_import_timeout` mặc định 30s là quá ngắn cho DAG folder bind-mount.** Module DAG
   chỉ import stdlib và `airflow.sdk`, nhưng dưới tải thì worker vẫn không import kịp; task
   báo `Dag not found during start up` rồi `UP_FOR_RESCHEDULE` mãi, và triệu chứng đọc ra
   giống "pipeline treo". Đã nâng lên 120s.
10. **Consumer bị revoke assignment giữa batch.** Với `session.timeout.ms=45000`, khi Spark
    merge đang chiếm CPU thì group coordinator trả lời chậm và broker thu hồi assignment —
    `session timed out (in join-state steady) ... without a successful response from the group
    coordinator` — làm mất batch đang xử lý và buộc retry. Drain là job batch, không có ai
    tranh partition, nên chờ mới là hành vi đúng: nâng lên 120s kèm `heartbeat.interval.ms`
    tường minh.

Ngoài ra, ba lỗi phía Kaggle được ghi trong `KAGGLE_GPU_EXTENSION.md`: `torchcodec` build theo
CUDA 13 làm vLLM chết khi khởi động, Qwen3 nhồi `<think>` vào `content`, và reasoning ăn hết
`max_tokens=320` khiến câu trả lời rỗng.

## Một thay đổi đã được rút lại

Ban đầu Envoy được chuyển sang health-check `/ready` để pod unready bị loại khỏi rotation, và
điều đó làm hai test J4 pass. Nhưng đo trên chính topology này thì nó khiến gateway **flap**:
mỗi lần một dependency probe chớp tắt — Kafka mất heartbeat dưới tải Spark — pod duy nhất bị
loại và biên trả 503 cứng, làm vỡ cả suite không-GPU vốn đang xanh.

Đối chiếu hợp đồng thì thay đổi đó cũng sai chỗ: `contracts/integration-matrix.yaml` khai
`IT-J4-degraded-recovery` phủ **IP02, IP04, IP05, IP07 — không có IP08**, và `health_signal`
của IP08 không hứa loại pod unready. Test `test_the_gateway_stops_routing_to_a_pod_that_is_not_ready`
vì thế assert hành vi ngoài phạm vi nó khai, và chưa từng chạy trong lịch sử repo vì luôn bị
gate `gpu` skip.

Đã trả `envoy.yaml` về routing theo `/health` (giữ lại phần nới `timeout: 5s`,
`unhealthy_threshold: 2` vì đó vẫn là cải thiện thật), và viết lại test thành
`test_the_gateway_reports_the_unready_pods_own_dependency_breakdown` — assert đúng điều nền
tảng bảo đảm: caller nhận breakdown dependency của chính pod thay vì `no healthy upstream`.
Docstring `conftest.py` và docstring module J4 cũng được sửa cho khớp, vì chúng đang phát biểu
hành vi ejection không tồn tại.

## Cách chạy lại

```text
LAB28_VLLM_BASE_URL=https://<host>/v1 uv run python scripts/render_vllm_target.py
export LAB28_VLLM_BASE_URL=https://<host>/v1 LAB28_VLLM_REQUIRE_REAL=true LAB28_VLLM_MAX_TOKENS=1024
docker compose --env-file ports.template --profile full up -d --wait api prometheus
curl -s -X POST http://localhost:9090/-/reload
uv run pytest integration-tests -m gpu -q
```

`LAB28_VLLM_MAX_TOKENS` phải đủ cho cả phần suy luận lẫn câu trả lời khi dùng model reasoning.
`LAB28_VLLM_REQUIRE_REAL=true` làm endpoint trở thành probe bắt buộc, nên suite không-GPU phải
chạy ở cấu hình mặc định của repo (`REQUIRE_REAL=false`), nơi thiếu vLLM chỉ là `degraded`.
