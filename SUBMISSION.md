# Submission — Day 28 Track 2

## Thông tin nộp bài

- Người thực hiện: **Trần Huy Hoàng — 2A202601709**
- Hình thức: **cá nhân**
- Nhánh nộp: [`ca-nhan-tran-huy-hoang`](https://github.com/HuyHoangTran05/Track2-Day28-2A202601709-TranHuyHoang/tree/ca-nhan-tran-huy-hoang)
- Ngày kiểm chứng: **2026-09-03 (Asia/Saigon)**
- Reflection và các vai trò đã đảm nhiệm: [`ANSWERS.md`](ANSWERS.md)

## Checklist bắt buộc

- [x] Evidence bundle do `uv run lab28 evidence` tạo: [`evidence/`](evidence/README.md)
- [x] Đủ evidence IP01–IP10: [`evidence/integration-report.json`](evidence/integration-report.json)
- [x] Kết quả kiểm thử mã và integration matrix: [`submission/TEST-RESULTS.md`](submission/TEST-RESULTS.md), [`submission/INTEGRATION-RESULTS.md`](submission/INTEGRATION-RESULTS.md)
- [x] Luồng đúng và replay-safe: [`evidence/happy-path-summary.json`](evidence/happy-path-summary.json), [`evidence/ip03-delta-history.json`](evidence/ip03-delta-history.json)
- [x] Metrics và alert rules: [`evidence/ip09-prometheus-targets.json`](evidence/ip09-prometheus-targets.json), [`ảnh Prometheus`](evidence/screenshots/prometheus-targets.png)
- [x] Trace continuity: [`evidence/ip10-trace.json`](evidence/ip10-trace.json), [`ảnh Jaeger`](evidence/screenshots/jaeger-trace.png)
- [x] Failure injection, dấu hiệu, nguyên nhân và recovery: [`submission/INCIDENT-REPORT.md`](submission/INCIDENT-REPORT.md)
- [x] Load profile P50/P95/P99 và phân tích bottleneck: [`submission/PERFORMANCE-REPORT.md`](submission/PERFORMANCE-REPORT.md)
- [x] Architecture/ownership diagram: [`docs/images/lab28-architecture-overview.png`](docs/images/lab28-architecture-overview.png), [`docs/team-role-cards.md`](docs/team-role-cards.md)
- [x] Kubernetes/GitOps static validation và trạng thái live drift trung thực: [`evidence/gitops-validation.json`](evidence/gitops-validation.json), [`runbooks/gitops-rollback.md`](runbooks/gitops-rollback.md)
- [x] Kiểm tra không nộp secret, `.env`, `.lab28/`, database/cache hoặc model weights.

## Kết quả chính

| Gate | Kết quả |
|---|---|
| Fast suite | **PASS — 87 passed** |
| Integration không GPU/LangSmith | **PASS — 56 passed, 16 deselected** |
| IT-J1 golden path | **PASS — 12 passed, 3 GPU checks skipped** |
| IT-J2 replay-safe | **PASS — 9 passed** |
| Matrix contract | **PASS — 245 checks** |
| Ruff / portability / manifests / Compose config | **PASS** |
| Argo CD live drift/self-heal | **UNVERIFIED** — cluster không cài Argo CD/Gateway API CRD |
| Real-vLLM/GPU | **PASS một phần — 10/15 test có gate `gpu`** — endpoint thật trên 2× Tesla T4 (vLLM 0.26.0, `Qwen/Qwen3-1.7B`); `/ready` báo `ready` với cả 5 component và `vLLM identity confirmed`. Năm test còn lại (J1 grounding, J5, trace-coverage) chưa chạy xong vì giới hạn của máy chứ không vì assertion. Xem [`submission/GPU-GATE.md`](submission/GPU-GATE.md) |
| LangSmith export | **PASS — 1 passed** — project thật được tìm thấy, collector đã gửi 12 spans và không có failed-span series |

`integration-report.json` giữ `ready: false` khi IP07 real-vLLM chưa được xác minh trong cùng process, và giữ
IP02/IP08/IP09/IP10 ở trạng thái `unverified` vì lệnh `lab28 evidence` không tự gọi các hệ thống đó.
Các điểm này được xác minh riêng bằng live integration tests và evidence tương ứng; không sửa giả
trạng thái của report.

## Lệnh tái kiểm tra

```text
uv run ruff check .
uv run python scripts/verify_matrix.py
uv run python scripts/check_portability.py
uv run python scripts/validate_manifests.py
uv run pytest starter-tests tests -q
docker compose --env-file ports.template --profile full up -d --build
uv run pytest integration-tests -m "not gpu and not langsmith" -q
uv run lab28 evidence
```

Gate GPU cần thêm endpoint thật; quy trình dựng nó và các lỗi đã gặp nằm trong
[`KAGGLE_GPU_EXTENSION.md`](KAGGLE_GPU_EXTENSION.md):

```text
LAB28_VLLM_BASE_URL=https://<host>/v1 uv run python scripts/render_vllm_target.py
LAB28_VLLM_BASE_URL=https://<host>/v1 LAB28_VLLM_REQUIRE_REAL=true LAB28_VLLM_MAX_TOKENS=1024   docker compose --env-file ports.template --profile full up -d --wait api prometheus
LAB28_VLLM_BASE_URL=https://<host>/v1 LAB28_VLLM_REQUIRE_REAL=true LAB28_VLLM_MAX_TOKENS=1024   uv run pytest integration-tests -m gpu -q
```

GPU và LangSmith là gate theo môi trường, và cả hai đã chạy bằng tài nguyên thật: LangSmith bằng
credential lưu ngoài repo, GPU bằng endpoint vLLM thật trên T4. Phần chưa hoàn tất được ghi đúng là
chưa hoàn tất, kèm lý do; không có gate nào được làm xanh bằng mock.
