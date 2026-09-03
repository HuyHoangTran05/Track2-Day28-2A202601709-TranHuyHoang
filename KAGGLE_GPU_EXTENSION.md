# Optional extension — Kaggle T4 + vLLM

Extension này dành cho học viên đã hoàn thành core. Kaggle GPU chỉ giải quyết tài
nguyên inference LLM; nó không tự giải quyết Kafka, Docker, state persistence,
network tunnel, quota, reproducibility hoặc failure recovery.

## Khi nào nên dùng

- Muốn thử OpenAI-compatible LLM serving với vLLM.
- Kaggle đang cấp T4 và session còn quota.
- Core tests/readiness đã pass ở local hoặc browser workspace.

Không dùng P100 làm baseline. [Kaggle thông báo P100 nghỉ ngày
2026-09-15](https://www.kaggle.com/product-announcements/735239) và T4x2 vẫn được
duy trì; availability/quota vẫn có thể thay đổi theo tài khoản.

## Notebook cells gợi ý

Kiểm tra GPU trước:

```bash
!nvidia-smi
!pip install -q "vllm==0.26.0"
```

Chạy model nhỏ phù hợp T4:

```bash
!vllm serve Qwen/Qwen3-4B-Instruct-2507 \
  --host 0.0.0.0 --port 8000 \
  --dtype half --max-model-len 4096 \
  --gpu-memory-utilization 0.85
```

Lệnh bám theo [`vllm serve` 0.26.0](https://docs.vllm.ai/en/v0.26.0/cli/serve/)
và [model card Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

Kiểm tra endpoint trong cùng session:

```bash
!curl -s http://127.0.0.1:8000/v1/models
```

## Ba lỗi thật gặp khi dựng endpoint này

Không phải lý thuyết — đây là những gì đã chặn endpoint chạy thật trên T4:

1. **`torchcodec` cài sẵn của Kaggle build theo CUDA 13.** vLLM import nó và chết ngay
   khi khởi động với `OSError: libnvrtc.so.13: cannot open shared object file`. vLLM bắt
   `ImportError` nhưng không bắt `OSError`, nên `pip uninstall -y torchcodec` là cách
   thoát: thiếu package thành `ImportError` và vLLM bỏ qua nhánh audio/video.
2. **Qwen3 là model hybrid reasoning.** Mặc định nó nhồi `<think>...</think>` vào
   `content`, làm mọi assertion về grounding vỡ. Serve với `--reasoning-parser qwen3` để
   vLLM tách chuỗi suy luận sang `reasoning_content`.
3. **Reasoning ăn hết ngân sách token.** Với `LAB28_VLLM_MAX_TOKENS=320`, phần suy luận
   dùng hết quota và `content` trả về **rỗng**. Ngân sách phải đủ cho cả suy luận lẫn câu
   trả lời; 1024 là mức đã đo đủ cho Qwen3-1.7B.

## Session Kaggle tự tắt theo *thay đổi*, không theo lệnh

Kaggle tắt interactive session sau ~40 phút không có **thay đổi** trong notebook. Chạy
lệnh trong console **không** được tính, nên một suite test dài hơn thế sẽ mất endpoint
giữa đường (`530` từ Cloudflare). Thêm/sửa một cell định kỳ mới reset được đồng hồ đó.

## Prometheus phải scrape được endpoint ở xa

Target vLLM không nằm cố định trên máy: qua tunnel thì hostname được cấp theo từng
session. `monitoring/prometheus.yml` vì thế dùng `file_sd_configs`, và target được sinh
lúc chạy:

```text
LAB28_VLLM_BASE_URL=https://<host>/v1 uv run python scripts/render_vllm_target.py
docker compose --env-file ports.template --profile full up -d --wait api prometheus
curl -s -X POST http://localhost:9090/-/reload
```

File `monitoring/targets/vllm.json` đã được gitignore vì nó chứa hostname tạm;
`monitoring/targets/vllm.json.example` là bản mẫu cho endpoint local. Evidence do suite
ghi ra cũng redact hostname này thành `<vllm-endpoint-host>`: URL tunnel là một
capability, ai giữ cũng gọi được model.

## Bài tập Operator

Viết một adapter thay CPU classifier nhưng vẫn trả contract có output, model
identifier/version, latency và trace ID. So sánh P50/P95, memory và failure mode.
Không hard-code URL tunnel hay token vào notebook/repository.

## Giới hạn cần ghi trong ADR

- Session và GPU quota có thể hết giữa buổi.
- Tunnel public tạo thêm rủi ro security và latency.
- Model download làm cold start lâu; cần cache/preflight.
- Hai T4 không tự động tăng tốc nếu không cấu hình tensor parallel phù hợp.
- Kết quả extension không phải bằng chứng Kafka/Delta/MLflow core đã hoạt động.

## LangSmith exporter tùy chọn

Không ghi key vào Compose hoặc Git. Khi có credential thật, nạp biến môi trường ở shell rồi dùng
override chỉ dành cho live gate:

```text
docker compose -f compose.yaml -f compose.langsmith.yaml --profile full up -d --build
uv run pytest integration-tests/test_trace_span_coverage.py -m langsmith -q
```

`LANGSMITH_WORKSPACE_ID` cần thiết với key dùng được cho nhiều workspace. Collector gửi cùng luồng
OTLP tới Jaeger và LangSmith; file override không được dùng khi thiếu credential.
