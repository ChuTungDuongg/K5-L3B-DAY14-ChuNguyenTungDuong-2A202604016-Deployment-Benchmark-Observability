# CP6 — Triển khai agent Part 6

## URL công khai

Agent chạy trên Railway, project `remarkable-art`, môi trường `production`, gói Trial. Redis chạy riêng trong cùng project và dùng mạng nội bộ. [Public health check](https://k5-l3b-day14-chunguyentungduong-2a202604016-depl-production.up.railway.app/health) · [Railway deployment](https://railway.com/project/e4071fa1-df08-4370-8c63-feeac995aca0/service/e55d28f0-8432-4758-9161-c24e218d55dc?id=55060103-59a6-4b8a-8e3e-2d6ebadec32f)

```text
https://k5-l3b-day14-chunguyentungduong-2a202604016-depl-production.up.railway.app
```

Lượt build từ GitHub trên `remarkable-art` lấy Dockerfile ví dụ Go ở gốc repo và gặp lỗi thiếu `go.mod`. Lượt triển khai thành công dùng Railway CLI để tải bản agent Python trong `06-lab-complete/` từ máy local, với **Root Directory** của service là `/06-lab-complete`. [Deploy từ thư mục local](https://docs.railway.com/cli/deploying)

## Cấu hình trên Railway

Agent dùng [Dockerfile Part 6](06-lab-complete/Dockerfile), healthcheck `/health` với timeout 60 giây, restart **On Failure** tối đa 3 lần, và domain HTTPS trỏ tới cổng `8000`. Lượt deploy áp dụng các thiết lập trên service. [Healthcheck trên Railway](https://docs.railway.com/deployments/healthchecks) · [Restart policy](https://docs.railway.com/deployments/restart-policy)

| Biến | Giá trị triển khai |
| --- | --- |
| `PORT` | `8000` |
| `ENVIRONMENT` | `production` |
| `REDIS_URL` | Tham chiếu `${{Redis.REDIS_URL}}` đến Redis nội bộ. Đã kiểm tra Redis không có TCP proxy public. |
| `AGENT_API_KEY` | Key riêng được tạo cho service và lưu trong Railway Variables. |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `MONTHLY_BUDGET_USD` | `10.0` |
| `LOG_LEVEL` | `INFO` |

## Kiểm thử URL công khai

Trong Bash hoặc WSL, nhập giá trị `AGENT_API_KEY` của service khi terminal hỏi. `read -s` ẩn key lúc nhập, còn `curl -H @-` đọc header qua stdin.

```bash
BASE='https://k5-l3b-day14-chunguyentungduong-2a202604016-depl-production.up.railway.app'
set +x
read -rs -p 'AGENT_API_KEY: ' AGENT_API_KEY
printf '\n'

curl --proto '=https' -sS -o /dev/null -w 'GET /health %{http_code}\n' "$BASE/health"
curl --proto '=https' -sS -o /dev/null -w 'GET /ready %{http_code}\n' "$BASE/ready"
curl --proto '=https' -sS -o /dev/null -w 'POST /ask thiếu key %{http_code}\n' \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}' "$BASE/ask"
printf 'X-API-Key: %s\n' "$AGENT_API_KEY" | \
  curl --proto '=https' -sS -o /dev/null -w 'POST /ask có key %{http_code}\n' \
    -H @- -H 'Content-Type: application/json' -d '{"question":"Hello"}' "$BASE/ask"
unset AGENT_API_KEY
```

| Ca kiểm thử | HTTP quan sát ngày 26/11/2026 |
| --- | ---: |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu key | 401 |
| `POST /ask` có key hợp lệ | 200 |

`/health` kiểm tra tiến trình HTTP. `/ready` kiểm tra thêm kết nối Redis. Bộ chấm chạy với `--public-url` cũng xác nhận endpoint public và đạt **12/12 tiêu chí, 44/44 kiểm tra**. [Kết quả chấm](MISSION_ANSWERS.md#part-6--final-project)

## Ảnh bằng chứng

- Sơ đồ project với agent và Redis đều Online. [Dashboard Railway](screenshots/dashboard.png)
- Deployment Active và có tên miền HTTPS. [Deployment thành công](screenshots/running.png)
- Output thực tế của bốn request curl, mở từ file log để chụp ảnh. [Kết quả HTTP](screenshots/test.png)

## Render dự phòng

[Render Blueprint](06-lab-complete/render.yaml) khai báo Web Service Docker và Key Value tương thích Redis ở cùng region Singapore, cả hai dùng gói Free. Web service lấy URL nội bộ qua `fromService.connectionString` và Render sinh key cho agent. Để dùng phương án này, chọn **New → Blueprint**, chọn nhánh GitHub đã có bản lab hoàn chỉnh, đặt **Blueprint Path** là `06-lab-complete/render.yaml` rồi kiểm tra hai tài nguyên Free trước khi deploy. Lượt deploy của bài dùng Railway. [Thiết lập Blueprint](https://render.com/docs/infrastructure-as-code#setup) · [Giới hạn gói Free](https://render.com/docs/free)
