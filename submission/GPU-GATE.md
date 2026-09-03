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
| `test_j1_golden_path.py`, `test_j5_trace_metrics_continuity.py`, `test_trace_span_coverage.py` | **chưa hoàn tất** — 7 test |

Tổng: **8/15 test `gpu` đã pass thật**. Bảy test còn lại đều là loại cần một DAG run
end-to-end; chúng chưa chạy xong vì Docker Desktop trên máy này treo ở tầng engine
(`500 Internal Server Error` trên mọi route của engine API) giữa lượt chạy. Không có test
nào trong số đó bị nới assertion hay đánh dấu skip để tránh; trạng thái ghi đúng là chưa xong.

## Lỗi thật mà gate này phơi ra

Sáu lỗi dưới đây tồn tại từ trước nhưng bị che vì 15 test `gpu` luôn bị skip khi không có
endpoint. Tất cả đã được sửa ở tầng cấu hình, không phải bằng cách sửa assertion.

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
