# Evidence bundle

Bundle được tạo/cập nhật bằng `uv run lab28 evidence` ngày 2026-09-03, sau đó được bổ sung bởi các
live integration journeys, failure injection và load profile. JSON là nguồn kiểm chứng chính; ảnh
chỉ giúp xem nhanh metrics và trace.

| Phạm vi | Artifact |
|---|---|
| IP01 Kafka | `ip01-kafka-consume.json` |
| IP02 Airflow | `ip02-airflow-run.json` |
| IP03 Delta/replay | `ip03-delta-history.json` |
| IP04 Feast | `ip04-feast-online.json` |
| IP05 Qdrant | `ip05-qdrant-search.json` |
| IP06 MLflow | `ip06-mlflow-release.json` |
| IP07 real-vLLM | `ip07-vllm-identity.json` — trung thực `unverified` |
| IP08 Gateway | `ip08-gateway.json` |
| IP09 Metrics | `ip09-prometheus-targets.json`, `ip09-grafana-dashboards.json` |
| IP10 Trace | `ip10-trace.json` |
| Incident | `incident-recovery.json` |
| Performance | `performance-profile.json` |
| Test gates | `test-results.json` |
| Kubernetes/GitOps | `gitops-validation.json` |
| Happy-path IDs | `happy-path-summary.json` |

Ảnh: `screenshots/prometheus-targets.png` và `screenshots/jaeger-trace.png`.

Không có token, password, `.env`, database/cache Docker, model weights hoặc URL tạm có quyền truy
cập trong bundle này.
