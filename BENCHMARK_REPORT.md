# Benchmark & Observability Report — Day 14

**Họ tên** Chu Nguyễn Tùng Dương (MSSV 2A202604016)

**Ngày chạy CP7–CP8** 26/11/2026 (UTC+7)

**Môi trường** Windows 11, Intel Core i5-13500H, Ubuntu trên WSL2. Docker báo 4 vCPU và 3,83 GiB RAM. Agent và trình tạo tải ở CP7 chạy trực tiếp trong WSL2.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
| --- | --- | --- |
| p95 latency của `POST /ask` | ≤ 500 ms | Mục tiêu là ít nhất 95% phản hồi thành công hoàn tất trong nửa giây. Theo dõi thêm p99 để thấy nhóm request rất chậm. |
| Error rate của `POST /ask` | ≤ 2% | Ngưỡng mặc định của bài load test, tương đương ít nhất 98% request trả HTTP 200. |
| Accuracy trên golden dataset | ≥ 85% trong CI | Yêu cầu tối thiểu của Exercise 7.3 để chặn thay đổi làm giảm chất lượng. Eval cuối sau khi sửa KB dùng ngưỡng 100% và kiểm tra regression theo từng ID. |

Hai ngưỡng hiệu năng lấy từ mặc định của script. Script tính percentile cho các phản hồi HTTP 200 và tính error rate trên toàn bộ request được đo. [Script load test](06-lab-complete/benchmark-observability/develop/load_test.py), [hướng dẫn lab](CODE_LAB.md)

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Mỗi lượt đo gửi 300 request tới v2 trên cổng 8002 trước khi bổ sung hai tài liệu KB và histogram độ dài câu hỏi. Tất cả lượt giữ `MOCK_LATENCY_MS=120`, `MOCK_JITTER_MS=60`, `MOCK_RETRIEVAL_MS=20`, `MOCK_SLOW_MS=1500` và `MOCK_ERROR_RATE=0.01`. Bảng 2.1 dùng `MOCK_SLOW_RATE=0.03`. Script loại request warm-up khỏi kết quả.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4,29 | 193,0 | 242,8 | 1.683,2 | 1,33% | PASS |
| 10 | 36,05 | 195,5 | 225,6 | 1.697,7 | 0,67% | PASS |
| 50 | 108,23 | 220,4 | 308,6 | 1.747,0 | 0,67% | PASS |
| 100 | 70,64 | 489,5 | 2.947,2 | 3.148,8 | 2,00% | FAIL |

Dữ liệu gốc của bốn lượt. [Concurrency 1](reports/load_v2_c1.json), [concurrency 10](reports/load_v2_c10.json), [concurrency 50](reports/load_v2_c50.json), [concurrency 100](reports/load_v2_c100.json)

RPS tăng từ 4,29 đến 108,23 ở concurrency 50 rồi giảm còn 70,64 ở concurrency 100. Ở mức 100, p95 tăng lên 2.947,2 ms và vượt ngưỡng 500 ms, trong khi tỷ lệ lỗi chạm đúng ngưỡng 2,00% (6/300). Kết quả phù hợp với hiện tượng bão hòa khi client và server local phải xử lý nhiều yêu cầu đồng thời. Cần profiling để xác định độ trễ phát sinh ở client, hàng đợi kết nối hay server. Với bốn mức đã đo, concurrency 50 có RPS cao nhất trong các mức đạt SLO.

### 2.2 Tail latency

Mỗi lượt gửi 300 request ở concurrency 20 và chỉ thay `MOCK_SLOW_RATE`. Các tham số mock còn lại giữ như mục 2.1. [Rate 0](reports/load_v2_slow_0.json), [rate 0.03](reports/load_v2_slow_0.03.json), [rate 0.1](reports/load_v2_slow_0.1.json)

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
| --- | ---: | ---: | ---: |
| 0 | 210,9 | 261,4 | 279,0 |
| 0.03 (mặc định) | 244,7 | 286,3 | 1.692,7 |
| 0.1 | 361,5 | 1.701,8 | 1.726,6 |

Khi slow rate tăng từ 0 lên 0,03, avg chỉ tăng 33,8 ms, trong khi p99 tăng 1.413,7 ms. Nhóm chậm chiếm ít request nên ảnh hưởng nhỏ lên trung bình và hiện rõ ở p99. Ở slow rate 0,1, p95 đã rơi vào nhóm request chậm và vượt 500 ms, trong khi avg vẫn dưới 500 ms. Dùng p95 làm ngưỡng trải nghiệm chính và quan sát p99 để phát hiện nhóm chậm hiếm gặp.

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Ba lượt dùng cùng model `mock-llm-small`, cùng 23 câu và các tham số `MOCK_SLOW_RATE=0`, `MOCK_ERROR_RATE=0`. Golden dataset giữ nguyên. V1 chạy trên cổng 8001. V2 chạy trên cổng 8002, rồi được khởi động lại sau khi thêm hai tài liệu vào KB. Các giá trị chi phí là ước tính của mock. [Eval v1](reports/eval_v1.json), [eval v2](reports/eval_v2.json), [eval v2 sau sửa](reports/eval_v2_fixed.json), [golden dataset](06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau sửa KB |
| --- | ---: | ---: | ---: |
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 58,0 | 109,1 | 114,7 |
| Tổng cost (USD) | 0,000417 | 0,000762 | 0,000799 |
| Cost / câu đúng (USD) | 0,00041655 | 0,00003627 | 0,00003475 |
| p50 (ms) | 162,2 | 193,8 | 200,3 |
| p95 (ms) | 185,2 | 214,6 | 248,8 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%) |

| ID v2 trả lời sai ban đầu | Keyword bị thiếu | Nội dung đã bổ sung vào KB |
| --- | --- | --- |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Mô tả API key và JWT, gồm cách server xác minh chữ ký và thời điểm hết hạn của JWT. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Mô tả cách Kubernetes HPA thay đổi số pod theo CPU, bộ nhớ hoặc custom metrics như RPS. |

Hai tài liệu được thêm vào KB bản develop và đồng bộ sang production. Eval cuối so với `eval_v2.json` và ghi nhận 0 câu đúng bị chuyển thành sai. [KB develop](06-lab-complete/benchmark-observability/develop/utils/mock_llm.py), [KB production](06-lab-complete/benchmark-observability/production/utils/mock_llm.py), [kết quả đối chiếu](reports/eval_v2_fixed.json)

Bước retrieval của v2 thêm ngữ cảnh vào prompt. So với v1, v2 dùng nhiều token và có p95 cao hơn trong lượt eval. V2 sau sửa tốn 0,000799 USD cho cả bộ câu hỏi, nhưng chi phí trên một câu đúng giảm từ 0,00041655 USD của v1 còn 0,00003475 USD vì số câu đúng tăng từ 1 lên 23.

### Quality gate trong CI

Job pull request có thể khởi động v2 với `LLM_MODEL=mock-llm-small`, `MOCK_SLOW_RATE=0` và `MOCK_ERROR_RATE=0`, đợi `/health` trả 200 rồi chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85`. Có thể truyền `--baseline` trỏ tới kết quả của phiên bản đã duyệt trên cùng dataset để chặn regression từng câu. Script trả exit code 1 khi accuracy thấp hơn 85% hoặc có regression, khiến job thất bại. Cấu hình job làm required status check để chặn merge khi thất bại. [Script eval](06-lab-complete/benchmark-observability/develop/eval/run_eval.py)

## 4. Observability stack (production)

### 4.1 Screenshot

- Dashboard Grafana trong lượt chạy 3 replica. [Ảnh Grafana](screenshots/grafana-dashboard.png)
- Trace chậm và trace lỗi. [Ảnh trace chậm](screenshots/jaeger-slow-trace.png) · [Ảnh trace lỗi](screenshots/jaeger-error-trace.png)
- Trang Prometheus hiển thị `AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing. [Ảnh Prometheus](screenshots/prometheus-alert-firing.png)

Lúc 17:20:58, Prometheus đo `POST /ask` trên cửa sổ 1 phút với avg khoảng **234 ms** và p95 khoảng **294 ms**. p95 cao hơn avg khoảng 61 ms. Grafana đọc thời gian agent xử lý qua histogram của Prometheus, còn Locust đo thời gian HTTP qua Nginx suốt cả lượt chạy nên hai kết quả có thể khác.

Ba replica nhận khoảng **20,79**, **20,71** và **20,61 request/s** cho `/ask` tại cùng thời điểm, gần như chia đều. Input khoảng **4.790 token/s**, gồm system prompt, câu hỏi và ngữ cảnh retrieval, trong khi output khoảng **2.518 token/s** chỉ gồm câu trả lời. `GET /metrics` qua Nginx cổng 8080 trả **404** theo cấu hình. Prometheus scrape trực tiếp các agent trên mạng Compose. [Cấu hình Nginx](06-lab-complete/benchmark-observability/production/nginx/nginx.conf)

### 4.2 Thí nghiệm lỗi có chủ đích

| # | Thay đổi | Alert firing | Thời gian đến firing | Panel phản ánh |
| --- | --- | --- | --- | --- |
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | Khoảng 87 giây | Error rate và request theo status |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | Khoảng 137 giây | Latency p95 |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy riêng. Alert cost đã firing ở model nhỏ dưới tải trước A/B. | — | LLM cost burn rate |
| D | `docker pause` một instance | Chưa chạy riêng. Rule `AgentInstanceDown` có kiểm thử bằng `promtool`. | — | Instances up |
| E | `AGENT_VERSION=v1` | Chất lượng giảm xuống 1/23 trong eval CP7. Chưa chạy riêng trên stack. | — | Eval theo phiên bản |

Chạy A và B cùng lúc trên 3 replica, dùng Locust 65 user trong 4 phút. Thời gian tính từ khi đổi cấu hình đến lần lấy mẫu đầu tiên thấy trạng thái firing. Prometheus được hỏi mỗi 5 giây, nên thời gian là gần đúng. Khi chụp ảnh, tỷ lệ 5xx khoảng **18,9%** và p95 khoảng **1,899 giây**. Rule lỗi yêu cầu tỷ lệ 5xx vượt 5% trong 1 phút, còn rule latency yêu cầu p95 vượt 1 giây trong 2 phút. Alert cost đã firing trước A/B khi chạy tải scale với model nhỏ, do chi phí mock quy đổi theo giờ vượt 2 USD. `promtool test rules` trả `SUCCESS`. [Rule Prometheus](06-lab-complete/benchmark-observability/production/prometheus/alert_rules.yml)

Để phát hiện kiểu sự cố ở E, chạy eval định kỳ và trước mỗi lần deploy. Gắn kết quả với phiên bản agent và cảnh báo khi accuracy giảm. Request có thể vẫn trả HTTP 200 trong khi câu trả lời thiếu kiến thức.

### 4.3 Debug bằng trace

Trace chậm `89f0dcf2e341b5330b3c3ce12db69105` dài **1.719,121 ms**. Span `chat mock-llm-small` chiếm **1.699,381 ms**, khoảng **98,9%**. Dòng log có cùng `trace_id`.

```json
{"ts":"2026-11-26T10:23:47.631878+00:00","level":"INFO","service":"observable-agent","instance":"ee1ace6a7c3c","event":"llm_call","trace_id":"89f0dcf2e341b5330b3c3ce12db69105","span_id":"ef4df8d38e3d0291","request_id":"a0e9adc01eea","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":4.7e-05,"llm_ms":1698.7}
```

Trace lỗi `d26a9eae09f780e8db6a08f9b06f0c20` dài **111,090 ms**. Span `chat mock-llm-small` dài **89,584 ms**, ghi event `exception`. Request kết thúc với HTTP **503**.

```json
{"ts":"2026-11-26T10:21:55.375592+00:00","level":"INFO","service":"observable-agent","instance":"d19fc1bf75b6","event":"llm_error","trace_id":"d26a9eae09f780e8db6a08f9b06f0c20","span_id":"0bc482d31c2d6b73","request_id":"f3043284c0a7","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 58,26 | 200 | 770 | 1.700 | 75 / 6.926 |
| 3 | 57,03 | 200 | 1.300 | 1.700 | 70 / 6.796 |

Bảng lấy dòng `/ask` trong CSV. Tính cả `/health`, throughput lần lượt là **63,91** và **62,67 request/s**. [CSV 1 replica](benchmark-results/scale_1_stats.csv) · [CSV 3 replica](benchmark-results/scale_3_stats.csv)

Trong hai lượt này, scale lên 3 replica giữ p50/p99 gần như nguyên và p95 tăng từ 770 lên 1.300 ms. Locust giữ 100 user và có khoảng nghỉ giữa các request. LLM giả lập có độ trễ và lỗi ngẫu nhiên. Hai lần chạy cho thấy thêm replica ở mức tải này chưa cải thiện p95. Cần đo lặp lại và đối chiếu CPU, in-flight và latency LLM để xác định nút thắt.

## 6. Kết luận

1. p95 và p99 cho thấy tình trạng request chậm theo các tỷ lệ khác nhau. Ở slow rate 0,03, p95 vẫn đạt ngưỡng, còn p99 đã vượt 1.600 ms.
2. RPS cần được đọc cùng percentile và tỷ lệ lỗi. Trong lượt local này, tăng concurrency từ 50 lên 100 làm throughput giảm và p95 vượt SLO.
3. Chất lượng cần phép đo riêng. HTTP 200 chỉ xác nhận request hoàn tất, nên một thay đổi phiên bản vẫn có thể làm câu trả lời sai mà các alert latency và error rate không phát hiện được. Eval trên cùng golden dataset, so sánh theo phiên bản và giữ quality gate trên pull request giúp phát hiện regression đó.

Ở Exercise 7.1, `http_requests_total` là Counter, `agent_in_flight_requests` là Gauge và `http_request_duration_seconds` là Histogram. Dùng route template làm label và gom URL lạ vào `unmatched` để giữ số time series hữu hạn. Nếu dùng từng URL thật, bot có thể tạo hàng nghìn series từ các đường dẫn khác nhau, làm tăng RAM và chi phí truy vấn của Prometheus. Histogram `agent_question_length_chars` gom độ dài theo bucket. TestClient đã xác nhận một request 13 ký tự được ghi vào metric này. [Metric develop](06-lab-complete/benchmark-observability/develop/app.py#L65)

Khi triển khai thật, nên theo dõi điểm eval định kỳ theo phiên bản và phát cảnh báo khi chất lượng giảm sau deploy. Với retrieval, tỷ lệ request tìm được tài liệu và p95 của bước truy xuất giúp phân biệt lỗi tìm ngữ cảnh với độ trễ từ LLM.
