# Live integration matrix results

Ngày kiểm tra: **2026-09-03 (Asia/Saigon)**. Stack Compose `full` được build và chờ healthy trước
khi chạy. Nguồn chi tiết là `evidence/integration-report.json`, các file `evidence/ip*.json` và ảnh
trong `evidence/screenshots/`.

## Kết quả pytest live

| Phạm vi | Lệnh | Kết quả |
|---|---|---|
| IT-J1 golden path | `uv run pytest integration-tests/test_j1_golden_path.py -q` | **PASS — 12 passed, 3 skipped** (GPU) |
| IT-J2 idempotent replay | `uv run pytest integration-tests/test_j2_idempotent_replay.py -q` | **PASS — 9 passed** |
| IT-J3 promotion/rollback | `uv run pytest integration-tests/test_j3_promotion_rollback.py -q` | **PASS — 6 passed, 3 skipped** (GPU) |
| Toàn bộ local/non-GPU | `uv run pytest integration-tests -m "not gpu and not langsmith" -q` | **PASS — 56 passed, 16 deselected in 235.45s** |

## Ma trận journey/gate

| Journey / gate | Trạng thái | Evidence |
|---|---|---|
| IT-J1 golden path | **PASS (local leg)** | `ip01`, `ip02`, `ip03`, `ip04`, `ip05` |
| IT-J2 idempotent replay | **PASS** | `evidence/ip03-delta-history.json` — MERGE và time travel |
| IT-J3 promotion/rollback | **PASS** | `evidence/ip06-mlflow-release.json` |
| IT-J4 degraded/recovery | **PASS** | `evidence/incident-recovery.json` |
| IT-J5 trace/metrics continuity | **PASS (local Jaeger/Prometheus)** | `evidence/ip09-*.json`, `evidence/ip10-trace.json` |
| Gateway rate limit | **PASS** | 30 request: 10 accepted, 20 HTTP 429 |
| Prometheus targets/alerts | **PASS** | 9 target bắt buộc `up`; 2 alert rule `ok` |
| Trace span coverage | **PASS (non-GPU leg)** | 11 span; gateway → API → Kafka → Airflow → Spark |
| GPU / real-vLLM | **PASS — 15/15** | Endpoint thật 2× Tesla T4, vLLM 0.26.0, `Qwen/Qwen3-1.7B`; `ip07-vllm-identity.json` ghi `reachable: true` với 111 metric `vllm:*`; `/ready` báo `ready` với cả 5 component; `ip09` 10/10 target up với URL endpoint đã redact. Chi tiết và mười lỗi nền tảng gate này phơi ra: `submission/GPU-GATE.md` |
| LangSmith external export | **PASS** | `evidence/ip10-langsmith-export.json`: project thật được tìm thấy; 12 spans gửi qua `otlphttp/langsmith`, 0 failed-span series; test marker `langsmith` 1 passed |

Các test bị marker `gpu` loại khỏi full suite đều phụ thuộc endpoint vLLM thật. Cả LangSmith và GPU
đã chạy bằng tài nguyên thật ngoài repo; không mock endpoint hay credential để biến gate thành PASS, và
phần chưa hoàn tất được ghi là chưa hoàn tất kèm lý do.

`evidence/integration-report.json` là một readiness snapshot bảo thủ: nó chỉ probe trực tiếp sáu
điểm nên IP02/IP08/IP09/IP10 vẫn là `unverified` dù các live test chuyên biệt đã PASS. IP07 làm
`ready` tổng thể bằng `false`; đây là trạng thái trung thực của máy không có GPU endpoint.
