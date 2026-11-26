# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-pattern trong bản develop

1. Dòng 17–18 gán API key và URL cơ sở dữ liệu trực tiếp trong code. Commit cũng lưu các giá trị này trong lịch sử Git.
2. Dòng 33–38 in câu hỏi, câu trả lời và cả key bằng `print()`. Log có thể làm lộ dữ liệu người dùng hoặc thông tin xác thực.
3. App chỉ khai báo `/` và `/ask`. Thiếu `/health` nên nền tảng thiếu endpoint để kiểm tra tiến trình.
4. Dòng 51–52 bind vào localhost và cố định cổng 8000. Cloud hoặc container cần bind trên giao diện mạng phù hợp và đọc cổng từ môi trường.
5. Dòng 53 luôn bật `reload=True`. Trình theo dõi tệp và việc tự khởi động lại thích hợp khi sửa code trên máy local.
6. App thiếu FastAPI lifespan để cập nhật trạng thái sẵn sàng và dọn tài nguyên khi dừng. [Mã develop](01-localhost-vs-production/develop/app.py)

### Exercise 1.2 — Chạy bản develop

Lần chạy local gọi `POST /ask?question=hello` và nhận phản hồi từ mock LLM. Dòng access log xác nhận mã HTTP.

```text
INFO: 127.0.0.1:36344 - "POST /ask?question=hello HTTP/1.1" 200 OK
```

`GET /health` trả 404. Log debug có dòng in key mẫu. Khi đặt `PORT=9000`, app vẫn chạy trên cổng 8000 và Uvicorn bật chế độ reload.

### Exercise 1.3 — So sánh hai bản

| Hạng mục | Develop | Production | Ý nghĩa |
| --- | --- | --- | --- |
| Cấu hình | Hardcode key, localhost và cổng 8000 | `config.py` đọc `HOST`, `PORT`, `DEBUG` và các key từ môi trường. `app.py` dòng 197–198 dùng `settings.port` và `settings.debug` | Cùng mã nguồn chạy được ở local, Docker hoặc cloud. Có thể đổi cấu hình mà không sửa code. |
| Health check | Thiếu `/health` và `/ready` | `/health` báo liveness và uptime. `/ready` đọc cờ sẵn sàng của lifespan | Nền tảng có thể dùng probe riêng để kiểm tra tiến trình và quyết định thời điểm chuyển traffic. |
| Log | `print()` key và nội dung yêu cầu | Log có mức độ và trường sự kiện như độ dài câu hỏi, độ dài phản hồi | Có thể lọc theo sự kiện và điều tra lỗi mà không đưa key vào log ứng dụng. |
| Shutdown | Thiếu bước dọn tài nguyên của app | FastAPI lifespan hạ cờ readiness và ghi log hoàn tất shutdown | Dành thời gian cho request đang xử lý và tạo điểm để đóng kết nối. |

Ở bản production, `GET /health` trả 200 và `PORT=9000` được áp dụng. Khi nhấn `Ctrl+C`, Uvicorn và app ghi các bước shutdown đến khi hoàn tất, sau đó terminal in traceback do ngắt bàn phím. [Mã production](01-localhost-vs-production/production/app.py#L193), [cấu hình production](01-localhost-vs-production/production/config.py#L16)

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

1. Base image trong Dockerfile develop là `python:3.11`, gồm môi trường Python 3.11 và các gói hệ thống của image đầy đủ.
2. `WORKDIR /app` đặt thư mục hiện hành cho các bước build tiếp theo và lệnh mặc định của container.
3. Copy `requirements.txt` và cài dependencies trước khi copy mã nguồn. Khi chỉ sửa mã ứng dụng, Docker có thể dùng lại layer cài dependencies.
4. `ENTRYPOINT` đặt chương trình chính chạy khi container khởi động. Với dạng exec của cả hai chỉ thị, `CMD` cung cấp đối số mặc định cho `ENTRYPOINT`. Khi thiếu `ENTRYPOINT`, `CMD` là lệnh mặc định, có thể thay bằng lệnh sau tên image trong `docker run`. Image develop dùng `CMD ["python", "app.py"]`. [Dockerfile develop](02-docker/develop/Dockerfile)

### Exercise 2.2 — Chạy container develop

| Request tới container qua cổng 8000 | Mã HTTP | Phản hồi |
| --- | --- | --- |
| `GET /health` | 200 | `{"status":"ok","uptime_seconds":12.7,"container":true}` |
| `POST /ask?question=Hello` | 200 | Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận. |

### Exercise 2.3 — Multi-stage build và kích thước image

Stage `builder` dùng `python:3.11-slim`, cài `gcc` và `libpq-dev` rồi cài các package Python vào `/root/.local`. Stage `runtime` cũng dùng base slim, copy package đã cài và mã app, rồi chạy bằng user `appuser`. Các công cụ build nằm ở stage đầu nên không chiếm dung lượng trong image runtime. [Dockerfile production](02-docker/production/Dockerfile)

| Chỉ số từ danh sách image Docker | Develop | Advanced | Mức giảm |
| --- | ---: | ---: | ---: |
| Dung lượng đĩa | 1,67 GB (khoảng 1.670 MB) | 240 MB | 85,6% |
| Content size | 426 MB | 57,4 MB | 86,5% |

Mức giảm được tính bằng `(develop − advanced) / develop × 100%` trên cùng một cột đo của Docker, với 1 GB bằng 1.000 MB. Các giá trị phần trăm là xấp xỉ vì Docker đã làm tròn số hiển thị.

### Exercise 2.4 — Docker Compose qua Nginx

```text
Client → Nginx (:80) → agent (:8000)
                         ├─ Redis (:6379)
                         └─ Qdrant (:6333)
```

Cả bốn service chia sẻ mạng `internal`. Nginx nhận kết nối từ host và forward tới agent. Compose cấp URL nội bộ của Redis (cache/session) và Qdrant (vector database) cho agent qua DNS theo tên service. Compose đợi Redis và Qdrant báo healthy trước khi khởi động agent. [Compose production](02-docker/production/docker-compose.yml), [cấu hình Nginx](02-docker/production/nginx/nginx.conf)

Lần chạy stack có `agent`, `redis`, `qdrant` và `nginx`. Qua `http://localhost`, `GET /health` và `POST /ask` đều trả HTTP 200.

## Part 3 — Cloud Deployment

### Exercise 3.1–3.2 — Trạng thái và cấu hình

Agent Part 6 đã chạy trên Railway, project `remarkable-art` trong môi trường `production`. Bốn request qua HTTPS lần lượt cho kết quả `GET /health` 200, `GET /ready` 200, `POST /ask` thiếu key 401 và có key 200. [URL công khai](https://k5-l3b-day14-chunguyentungduong-2a202604016-depl-production.up.railway.app/health) · [Cấu hình và kết quả kiểm thử](DEPLOYMENT.md)

| Hạng mục | Railway | Render |
| --- | --- | --- |
| Build và chạy | `railway.toml` mô tả cấu hình Dockerfile. Lượt deploy dùng CLI và đặt Root Directory của service thành `/06-lab-complete`. | Blueprint YAML khai báo web service chạy Docker. `rootDir` trỏ tới Part 6, `dockerContext` là thư mục đó. |
| Health và restart | `healthcheckPath` là `/health`, timeout 60 giây. Khai báo `ON_FAILURE` với tối đa 3 lần thử lại. | `healthCheckPath` là `/health`. Blueprint không đặt chính sách restart tương ứng. |
| Môi trường | Đặt `AGENT_API_KEY` trong Variables, `REDIS_URL` tham chiếu Redis của cùng môi trường. | Blueprint dùng `generateValue` cho API key và lấy URL nội bộ của Key Value qua `fromService.connectionString`. Web service và Key Value cùng region Singapore, gói Free. |

Hai file dùng cùng Dockerfile của Part 6. TOML mô tả cấu hình build và deploy cho service Railway, còn Redis được tạo riêng trong project. Blueprint khai báo cả web service và Key Value, nối hai service qua tham chiếu biến môi trường. Cả hai cần Redis để `/ready` trả 200. [Cấu hình Railway](06-lab-complete/railway.toml), [Blueprint Render](06-lab-complete/render.yaml)

### Exercise 3.3 — Pipeline Cloud Run

1. Cloud Build cài dependencies và chạy `pytest tests/` trên Python 3.11.
2. Bước build tạo Docker image với hai tag `$COMMIT_SHA` và `latest`. Bước push đẩy cả hai tag vào registry.
3. Bước deploy dùng tag của commit để cập nhật service Cloud Run ở `asia-southeast1`, đặt thu phóng từ 1 đến 10 instance và tham chiếu Secret Manager.
4. Manifest `service.yaml` khai báo riêng cấu hình service, gồm cổng 8000, giới hạn 80 request đồng thời mỗi instance, startup probe `/ready` và liveness probe `/health`. [Cloud Build](03-cloud-deployment/production-cloud-run/cloudbuild.yaml), [manifest Cloud Run](03-cloud-deployment/production-cloud-run/service.yaml)

## Part 4 — API Security

### Exercise 4.1 — API key

Dependency `verify_api_key` đọc header `X-API-Key` và so với `AGENT_API_KEY` của bản develop trước khi chạy handler `/ask`. Thiếu key trả 401. Theo mã nguồn, key sai trả 403. Để đổi key ở bản mẫu, cập nhật biến môi trường, khởi động lại app rồi cập nhật key phía client. [API key auth trong mã develop](04-api-gateway/develop/app.py#L35)

### Exercise 4.2 — JWT

Ở bản production, `POST /auth/token` xác thực đăng nhập và cấp JWT ký bằng HS256. JWT chứa định danh người dùng, role và hạn 60 phút. Client gửi `Authorization: Bearer <token>`. Dependency `verify_token` xác minh chữ ký và hạn trước khi endpoint nhận thông tin người dùng. Lần chạy local lấy được token của tài khoản `student` và gọi `/ask` thành công, với `usage.requests_remaining` bằng 9. [Endpoint cấp token](04-api-gateway/production/app.py#L105), [mã xác minh JWT](04-api-gateway/production/auth.py#L35)

### Exercise 4.3 — Rate limit và kết quả HTTP

Limiter dùng sliding window 60 giây. Mỗi user có một deque lưu timestamp. Trước khi nhận request mới, limiter gỡ timestamp ngoài cửa sổ và trả 429 kèm `Retry-After` nếu đã chạm ngưỡng. Role `user` có 10 request/phút. Role `admin` dùng limiter riêng với 100 request/phút. Bộ đếm của ví dụ này nằm trong RAM từng process. [Rate limiter](04-api-gateway/production/rate_limiter.py)

Các đoạn trích dưới đây lấy từ lần chạy local. Dòng 401 và nội dung lỗi là của bản develop.

```text
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Bản production với JWT của `student` trả `HTTP/1.1 200 OK`. Phản hồi có `question` là `Hello` và `usage.requests_remaining` là `9`. Vòng lặp in hai dòng sau tại ngưỡng rate limit.

```text
Request 10: 200
Request 11: 429
```

Bảng tổng hợp các lần kiểm tra.

| Tình huống | Mã HTTP | Quan sát |
| --- | ---: | --- |
| Develop · `POST /ask` thiếu `X-API-Key` | 401 | Xác thực từ chối yêu cầu |
| Develop · `POST /ask` có API key đúng | 200 | Nhận câu trả lời |
| Production · `POST /ask` với JWT của `student` | 200 | `usage.requests_remaining` = 9 |
| Production · request 1–10 trong vòng lặp | 200 | 10 request thành công |
| Production · request 11–20 trong vòng lặp | 429 | 10 request bị giới hạn |

### Exercise 4.4 — Cost guard

Với bài tập ngân sách 10 USD mỗi tháng cho mỗi user, có thể lưu tổng chi theo khóa Redis gồm ID user và tháng UTC. Trước khi gọi LLM, kiểm tra tổng đã dùng cộng chi phí ước tính. Dành trước khoản chi và cập nhật số dư trong cùng một thao tác nguyên tử để hai request đồng thời không cùng chi vượt ngân sách. Đặt TTL tới đầu tháng tiếp theo và đối soát với chi phí thực tế sau khi có phản hồi.

Ví dụ Part 4 hiện theo dõi chi phí theo ngày trong RAM. Chưa có bản kiểm tra ngân sách tháng độc lập cho exercise này. Bản Part 6 lưu tổng ngày/tháng trong Redis theo định danh API key, đặt thời điểm hết hạn theo UTC, kiểm tra số đã chi trước khi gọi mock LLM và ghi chi phí sau đó. Codex đã kiểm tra ở Part 6 bằng ngân sách tháng 0 và ngân sách ngày 1.000 USD. `/ask` trả HTTP 402. Rate limit giới hạn tần suất gọi, còn cost guard giới hạn tiền đã chi. [Cost guard Part 4](04-api-gateway/production/cost_guard.py), [cost guard Part 6](06-lab-complete/app/cost_guard.py)

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Liveness và readiness

Qua Nginx ở cổng 8080, cả `GET /health` và `GET /ready` trả HTTP 200 khi stack chạy với Redis. `/health` cho biết tiến trình còn phản hồi. Nếu Redis đã kết nối lúc khởi động rồi mất kết nối, bản scaling trả trạng thái `degraded` trong body và giữ mã 200. `/ready` kiểm tra Redis để quyết định có thể nhận traffic và trả 503 khi lần ping đó lỗi. [Mã probe scaling](05-scaling-reliability/production/app.py#L187)

### Exercise 5.2 — Graceful shutdown

Khi Uvicorn nhận `SIGTERM`, server ngừng nhận kết nối, chờ request đang xử lý trong giới hạn shutdown rồi gọi FastAPI lifespan để dọn tài nguyên. Bản develop của Part 5 theo dõi số request đang xử lý và có bước hạ cờ readiness trong lifespan. Kết quả `Ctrl+C` ở Part 1 cho thấy các bước shutdown của bản đó. Kiểm tra bằng `docker stop` ở Part 6 hoàn tất trong 0,8 giây với exit code 0. Chưa xác nhận ca gửi `SIGTERM` giữa một request trong stack Part 5. [Lifespan của bản develop](05-scaling-reliability/develop/app.py#L41)

### Exercise 5.3 — Session dùng chung qua Redis

Mỗi agent đọc và ghi cùng khóa `session:<session_id>`. Redis giữ session JSON trong 3.600 giây kể từ lần ghi gần nhất, tối đa 20 tin nhắn mỗi session. Vì các container dùng chung Redis, request sau có thể đến agent khác và vẫn đọc được lịch sử. Chế độ dự phòng trong RAM của ví dụ chỉ giữ state trong một instance và mất lịch sử khi instance đó bị xóa. [Mã lưu session](05-scaling-reliability/production/app.py#L59)

### Exercise 5.4–5.5 — Phân tải và kiểm tra stateless

Stack đã chạy với ba container agent, một Nginx và một Redis. Request tới `http://localhost:8080/chat` được proxy qua Nginx. Nginx ghi upstream ở header `X-Served-By`, còn response JSON có trường `served_by` để nhận diện instance ứng dụng. [Compose scaling](05-scaling-reliability/production/docker-compose.yml), [cấu hình Nginx](05-scaling-reliability/production/nginx.conf)

`test_stateless.py` gửi 5 request trong cùng một session và ghi nhận cả 3 instance đã xử lý request. Đọc lại history nhận đủ 10 tin nhắn từ Redis, gồm 5 câu hỏi và 5 câu trả lời. Kết quả xác nhận các instance chia sẻ state. Script thực tế kiểm tra chuyển instance giữa các request. Ca tắt một container giữa phiên chưa được xác nhận. [Script kiểm tra stateless](05-scaling-reliability/production/test_stateless.py)

## Part 6 — Final Project

### Output kiểm tra Part 6 do Codex chạy với Docker và URL public

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 44/44 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

## AI log

### 2026-11-26 — Hoàn thiện Part 6

- **Yêu cầu:** người học đề nghị Codex điền các hàm còn thiếu để tự kiểm tra health và các tính năng, sau đó nghe giải thích.
- **AI đã thực hiện:** viết config, API key auth, Redis client, /health, /ready, rate limit dùng Redis, cost guard ngày/tháng, log JSON, lifecycle; hoàn thiện Dockerfile multi-stage, Compose với Redis có volume/AOF, .dockerignore, .env.example và cấu hình Railway/Render.
- **Kiểm tra do Codex chạy:** script gốc trong WSL2, đầy đủ runtime và Docker: PASS 12/12, 43/43 checks passed. Script đo image 63 MB; Docker stop exit code 0 trong 0.8 giây.
- **Kiểm tra bổ sung do Codex chạy:** 20 request đồng thời qua 2 worker: 10 mã 200, 10 mã 429. Monthly budget 0 và daily budget 1000: HTTP 402.
- **Script chấm:** giữ nguyên nội dung.
- **Người học tự kiểm tra trên bản vừa hoàn thiện:** chưa xác nhận; người học sẽ tự gọi API, xem log, thử Redis mất kết nối, API key, rate limit, cost guard và chạy lại script chấm. Không ghi nhận các kiểm tra của AI thành thao tác tự thực hiện của người học.
- **Tình trạng ở lần kiểm tra này:** bản Docker cục bộ đã đạt 43/43. Sau khi deploy cloud, lượt kiểm tra mới đạt 44/44.

### 2026-11-26 — Tổng hợp Part 1–5

- **Yêu cầu:** hoàn thiện câu trả lời cho các exercise từ mã mẫu, hướng dẫn lab và kết quả local đã ghi nhận.
- **AI đã thực hiện:** đối chiếu yêu cầu với mã nguồn, soạn câu trả lời, tính mức giảm dung lượng image và tóm tắt kết quả đã có.
- **Người học đã tự kiểm tra:** chạy hai bản Part 1, build và gọi container develop rồi test Compose qua Nginx ở Part 2, xác thực API key/JWT và chạy 20 request ở Part 4, chạy stack ba agent và kiểm tra history ở Part 5.
- **Trạng thái kiểm tra:** Part 4 ghi các đoạn trích và bảng tổng hợp từ lần chạy local. Bài kiểm tra ngân sách tháng độc lập ở Part 4 và bài tắt instance giữa phiên ở Part 5 chưa được xác nhận.

### 2026-11-26 — Deploy, benchmark và observability

- **Yêu cầu** Hoàn thiện các checkpoint cuối và giải thích kết quả.
- **Người học đã thực hiện** Đăng nhập Railway và tạo project liên kết với repo trên GitHub.
- **AI đã thực hiện** Đọc log lỗi build, chỉnh thư mục build, tạo Redis và deploy agent qua Railway CLI. Chạy bốn request HTTPS và chạy lại bộ chấm có `--public-url`, đạt 12/12 tiêu chí và 44/44 kiểm tra.
- **AI đã thực hiện** Chạy load test, eval và Locust trên máy lab. Bổ sung tài liệu JWT và Kubernetes HPA vào knowledge base, thêm histogram độ dài câu hỏi. Dùng Grafana, Prometheus và Jaeger để thu ảnh, đối chiếu số liệu và log. Eval cuối đạt 23/23, không có regression.
- **Nguồn số liệu** File JSON, CSV và ảnh được tạo từ các lần chạy trên máy lab. Golden dataset và script chấm giữ nguyên. [Báo cáo benchmark](BENCHMARK_REPORT.md) · [Kết quả triển khai](DEPLOYMENT.md)
