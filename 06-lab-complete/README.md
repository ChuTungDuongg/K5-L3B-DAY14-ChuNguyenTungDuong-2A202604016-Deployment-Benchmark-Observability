# Part 6 — Production-ready AI Agent

Bản thực hành đã hoàn thiện các module trong **app/** và cấu hình Docker/Compose.
Hợp đồng API và script chấm gốc được giữ nguyên. API dùng mock LLM, không gọi dịch vụ LLM tính phí.

## Chạy và tự kiểm tra

Từ thư mục gốc repo, mở terminal Ubuntu đã có môi trường Python:

```bash
cd "$LAB_ROOT/06-lab-complete"
docker compose -p k5-day14-part6 up -d --build --wait
docker compose -p k5-day14-part6 ps
```

Stack có một container agent (2 worker Uvicorn) và một container Redis.
Cấu hình local trong .env đang dùng key demo **day14-lab-key**; file .env không được commit.
Nếu clone sang máy khác, tạo .env từ .env.example rồi tự chọn key local.

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
curl -i -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -i -X POST http://localhost:8000/ask -H 'X-API-Key: day14-lab-key' -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS http://localhost:8000/usage -H 'X-API-Key: day14-lab-key'
```

Theo thứ tự: health 200, ready 200, thiếu key 401, có key 200, rồi JSON chi phí.
Trong Part 6, key sai cũng trả 401.

## Kiểm tra từng tính năng

- **Readiness:** dừng Redis bằng lệnh dưới đây, /health vẫn 200 còn /ready trả 503.
  Bật lại Redis thì /ready trở về 200.

```bash
docker compose -p k5-day14-part6 stop redis
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
docker compose -p k5-day14-part6 start redis
```

- **Rate limit:** dùng cùng API key gọi /ask liên tiếp; vượt 10 request trong 60 giây
  sẽ nhận 429 và Retry-After. Các lần gọi trước đó trong cửa sổ 60 giây cũng được tính.
  Restart agent không làm mất bộ đếm vì state nằm trong Redis.
- **Cost guard:** kiểm tra ngân sách trước khi gọi LLM, ghi chi phí sau khi gọi.
  Bộ đếm chi phí được tăng nguyên tử trong Redis, chia theo ngày/tháng UTC.
  Giá token là giá mô phỏng trong bài, token count được ước lượng từ số từ.
- **Demo 402:** cấu hình riêng một API key thử nghiệm với ngân sách ngày bằng 0:

```bash
AGENT_API_KEY=day14-budget-demo DAILY_BUDGET_USD=0 docker compose -p k5-day14-part6 up -d --wait
curl -i -X POST http://localhost:8000/ask -H 'X-API-Key: day14-budget-demo' -H 'Content-Type: application/json' -d '{"question":"Hello"}'
docker compose -p k5-day14-part6 up -d --wait
```

Lệnh cuối khôi phục cấu hình từ .env / môi trường terminal ban đầu.
- **Log:** xem JSON bằng docker compose -p k5-day14-part6 logs agent.
  API key và nội dung câu hỏi không được ghi vào log ứng dụng.
- **Shutdown:** Uvicorn dùng 2 worker và nhận SIGTERM trực tiếp ở PID 1.
  Uvicorn chờ request đang chạy trước khi gọi phần cleanup trong lifespan.
- **Dữ liệu Redis:** Compose bật AOF và volume redis_data; không tự xoá volume khi down.
  Chỉ xoá volume khi chủ động muốn reset dữ liệu.

## Kiểm tra đầy đủ

```bash
source "$LAB_ROOT/.venv/bin/activate"
python check_production_ready.py
```

Kết quả đã chạy ngày 2026-11-26: **PASS 12/12, 43/43 checks passed**.
Bản log đầy đủ tại **../.local-lab/part6-check.log**. Script chấm không được sửa.
Kiểm tra bổ sung: 20 request đồng thời qua 2 worker cho 10 mã 200 và 10 mã 429;
ngân sách tháng bằng 0 với ngân sách ngày 1000 trả 402.

PASS 12/12 ở đây bao gồm cấu hình sẵn sàng deploy. Chưa tạo URL cloud; CP6 là bước
deploy thư mục này cùng Redis và tự kiểm tra URL public.

## Cách đọc code

- **app/main.py:** các endpoint, middleware log JSON, lifecycle.
- **app/config.py:** đọc environment / .env.
- **app/auth.py:** kiểm tra X-API-Key.
- **app/redis_client.py:** tạo client kết nối lười; readiness ping Redis.
- **app/rate_limiter.py:** Redis sorted set + Lua, sliding window 60 giây.
- **app/cost_guard.py:** chi phí theo API key đã băm, ngày/tháng; bộ đếm nanodollar.

## Checklist Deliverable

- [ ] Dockerfile (multi-stage, < 500 MB)
- [ ] docker-compose.yml (agent + redis)
- [ ] .dockerignore
- [ ] Health check endpoint (`GET /health`)
- [ ] Readiness endpoint (`GET /ready`)
- [ ] API Key authentication
- [ ] Rate limiting
- [ ] Cost guard
- [ ] Config từ environment variables
- [ ] Structured logging
- [ ] Graceful shutdown
- [ ] Public URL ready (Railway / Render config)

---

## Script chấm dựa vào những tiêu chí dưới đây

Script tự khởi động agent của bạn, gọi API thật, build và chạy Docker image. Để chấm được, agent phải tuân theo các quy ước sau:

| Hạng mục | Yêu cầu |
|----------|---------|
| Điểm vào | `app/main.py` có biến `app` (FastAPI), chạy được bằng `uvicorn app.main:app --workers 2` từ thư mục này |
| `GET /health` | Luôn trả **200** khi process còn chạy, kể cả khi Redis chưa kết nối được |
| `GET /ready` | **200** khi sẵn sàng; **503** khi Redis (`REDIS_URL`) không kết nối được |
| `POST /ask` | Body JSON `{"question": "..."}` (được phép có thêm `user_id`) → **200** |
| API key | Header `X-API-Key` phải trùng biến `AGENT_API_KEY`; thiếu hoặc sai → **401** |
| Rate limit | Tối đa `RATE_LIMIT_PER_MINUTE` request / 60 giây cho mỗi API key; vượt → **429** (nên có header `Retry-After`). State lưu trong **Redis**, vẫn còn sau khi restart agent |
| Cost guard | Tổng chi phí vượt `DAILY_BUDGET_USD` (hoặc `MONTHLY_BUDGET_USD`) → **402** |
| Biến môi trường | Đọc từ env: `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`, `PORT`, `ENVIRONMENT`. Liệt kê đủ trong `.env.example`. Script chạy với `ENVIRONMENT=staging` |
| Log | Mỗi dòng log của app là **1 JSON object hợp lệ** (log của uvicorn không tính) |
| Graceful shutdown | Nhận SIGTERM khi đang có request → request đó vẫn trả 200, process tự thoát với exit code 0. Trong Docker, `docker stop` phải xong trong < 10 giây |
| Docker image | Multi-stage, base slim, user non-root, có `HEALTHCHECK`, < 500 MB. `CMD` lắng nghe theo biến `PORT` (mặc định 8000), uvicorn là PID 1. Container khởi động được khi **không có** Redis |
| Compose | Một service build từ `Dockerfile` + một service dùng image `redis:*`; agent có `REDIS_URL` trỏ tới service Redis và `depends_on` nó |
| `.dockerignore` | Loại trừ `.env`, `__pycache__`, `venv` |
| Deploy config | `railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`) **hoặc** `render.yaml` (`type: web`, `healthCheckPath: /health`, secret dùng `generateValue` / `sync: false`) |

---

## Các thành phần

```
06-lab-complete/
├── app/
│   ├── main.py           # /health, /ready, nối auth + rate limit + cost guard vào /ask, log JSON, shutdown
│   ├── config.py         # đọc cấu hình từ biến môi trường
│   ├── auth.py           # verify_api_key → 401
│   ├── rate_limiter.py   # check_rate_limit → 429 (Redis)
│   ├── cost_guard.py     # check_budget → 402, record_cost (Redis)
│   └── redis_client.py   # kết nối Redis + redis_healthy() cho /ready
├── utils/mock_llm.py     # Mock LLM — có sẵn, không cần sửa
├── Dockerfile            # viết lại thành multi-stage production
├── docker-compose.yml    # thêm redis
├── .dockerignore         # TODO
├── .env.example          # liệt kê đủ biến
├── railway.toml          # (hoặc render.yaml)
├── render.yaml           # (hoặc railway.toml)
├── requirements.txt      # Có sẵn
├── check_production_ready.py   # Script chấm — không sửa
└── benchmark-observability/    # Part 7 — làm sau khi xong Part 6
```

**Gợi ý thứ tự làm:** `/health` → `config.py` → log JSON → `auth.py` → `redis_client.py` + `/ready` → `rate_limiter.py` → `cost_guard.py` → graceful shutdown → `Dockerfile` + `.dockerignore` → `docker-compose.yml` → `railway.toml` / `render.yaml`. Hướng dẫn từng bước: [CODE_LAB.md — Part 6](../CODE_LAB.md#part-6-final-project-60-phút).

---

## Chạy local

```bash
pip install -r requirements.txt
test -f .env || cp .env.example .env

# Chạy nhanh không cần Docker (cần Redis riêng nếu muốn test rate limit thật)
AGENT_API_KEY=dev-key python -m uvicorn app.main:app --port "${PORT:-8000}" --workers 2

# Chạy cả agent + redis
docker compose up --build

curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
     -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{"question": "What is deployment?"}'
```

---

## Chấm bài

```bash
python check_production_ready.py                 # chấm đầy đủ — cần Docker đang chạy
python check_production_ready.py --skip-docker   # chế độ nhanh khi đang làm (bỏ build image)
python check_production_ready.py --static-only   # chỉ đọc file, không chạy agent
python check_production_ready.py --public-url https://your-app.railway.app   # thêm kiểm tra URL đã deploy
```

- Kết quả in theo từng tiêu chí: ✅ đạt · ❌ chưa đạt · ⚠️ chưa kiểm tra được.
- **Chỉ PASS khi cả 12 tiêu chí ✅.** Mục ⚠️ (vd máy chưa bật Docker) cũng tính là chưa đạt, nên khi nộp bài phải chạy chế độ đầy đủ.
- Lần đầu chạy, script build Docker image nên mất vài phút. Bài test stateless cần Redis: script dùng `REDIS_URL` nếu có, không thì tự bật container `redis:7-alpine` tạm thời.

---

## Deploy

**Railway**

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway up
railway domain        # nhận public URL
```

**Render:** push repo lên GitHub → Render Dashboard → New → Blueprint → chọn repo (Render đọc `render.yaml`) → điền secret → Deploy.

Sau khi deploy: `python check_production_ready.py --public-url <URL>` và ghi URL vào `DEPLOYMENT.md` (xem [DAY14_DELIVERY_CHECKLIST.md](../DAY14_DELIVERY_CHECKLIST.md)).

---

## Part 7 — Benchmark & Observability

Agent đã chạy được, bước tiếp theo là đo xem nó **nhanh** và **đúng** tới đâu, rồi **giám sát** khi chạy thật:

```bash
cd benchmark-observability
```

| Thư mục | Nội dung |
|---------|----------|
| `develop/` | Agent có `/metrics`, load test (p50/p95/p99, SLO), eval trên golden dataset + quality gate |
| `production/` | Docker Compose: agent x2 + Nginx + Prometheus + Grafana + Jaeger + Locust, 4 alert rules |

Hướng dẫn đầy đủ: [benchmark-observability/README.md](benchmark-observability/README.md). Nộp kèm `BENCHMARK_REPORT.md` theo [mẫu](benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md).
