# Test and validation results

Thời điểm chạy: **2026-09-03 (Asia/Saigon)**
Môi trường: Windows, CPython 3.11.15, `uv` 0.11.12, Docker Engine 29.5.3.

| Gate | Lệnh | Kết quả |
|---|---|---|
| Fast code suite | `uv run pytest starter-tests tests -q` | PASS — 87 passed in 4.83s |
| Lint | `uv run ruff check .` | PASS — All checks passed |
| Integration matrix contract | `uv run python scripts/verify_matrix.py` | PASS — 245 checks passed |
| Cross-platform contract | `uv run python scripts/check_portability.py` | PASS |
| Kubernetes/GitOps manifests | `uv run python scripts/validate_manifests.py` | PASS |
| Local Kubernetes discovery | `kubectl cluster-info`; query Argo/Gateway API resources | Cluster reachable; Argo CD và Gateway API CRD không được cài |
| Compose Core config | `docker compose --env-file ports.template config --quiet` | PASS (exit 0) |
| Compose Full config | `docker compose --env-file ports.template --profile full config --quiet` | PASS (exit 0) |

Kết quả live integration được ghi riêng trong `submission/INTEGRATION-RESULTS.md`. Bản máy đọc
được của các gate chính nằm tại `evidence/test-results.json`. GPU và LangSmith chỉ được đánh dấu
verified khi có endpoint vLLM thật và credential thật; không dùng mock để thay thế.
