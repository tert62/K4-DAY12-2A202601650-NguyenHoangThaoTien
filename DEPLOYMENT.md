# Thông Tin Deploy — Checkpoint 5

> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị token vào đây.**
> Repo này công khai — dán token vào là mất token.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Nguyễn Hoàng Thảo Tiên |
| Mã học viên | 2A202601650 |
| Repo | https://github.com/tert62/K4-DAY12-2A202601650-NguyenHoangThaoTien |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://chat-production-620e.up.railway.app |
| Platform | Railway — project `day12-chat-2A202601650`, environment `production`, region `sfo` |
| Ngày deploy | 2026-08-10 |

Kiến trúc trên Railway: hai service trong cùng project — `chat` (build từ
`Dockerfile`, multi-stage) và `Redis` (add-on `redis:8.2.1`, có volume 500MB).
Hai service nói với nhau qua private network `redis.railway.internal`, nên
Redis **không** mở ra Internet.

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | đặt `8000`, và service domain trỏ target port 8000 |
| `API_TOKEN` | ✅ | token riêng cho production (khác token chạy ở máy), sinh bằng `secrets.token_urlsafe(32)`, set qua `railway variables --set-from-stdin` nên không lọt vào shell history hay repo |
| `REDIS_URL` | ✅ | service reference `${{Redis.REDIS_URL}}` — Railway tự nội suy sang URL private của add-on, giá trị không nằm ở đâu trong repo |
| `BUCKET_CAPACITY` | ✅ | 10 |
| `REFILL_PER_MINUTE` | ✅ | 10 |
| `DAILY_BUDGET_USD` | ✅ | 1.0 |
| `LOG_LEVEL` | ✅ | INFO |

Ở máy, `.env` (gitignored) giữ thêm `DEPLOY_API_TOKEN` — đúng giá trị
`API_TOKEN` trên Railway — để `tests/test_cp5.py` gọi được `/chat` có xác thực.

## Lệnh Kiểm Tra

```bash
URL=https://chat-production-620e.up.railway.app

# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i $URL/healthz

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i $URL/readyz

# 3. Không có token — mong đợi 401 kèm header WWW-Authenticate
curl -i -X POST $URL/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'

# 4. Có token — mong đợi 200 kèm câu trả lời
curl -i -X POST $URL/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEPLOY_API_TOKEN" \
  -H "X-Client-Id: sv-cloud" \
  -d '{"message":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST $URL/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DEPLOY_API_TOKEN" \
    -H "X-Client-Id: sv-cloud-rl" \
    -d '{"message":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Chạy lúc 2026-08-10 08:12 UTC, gọi qua Internet vào Public URL ở trên.
Chú ý `HTTP/2` — Railway terminate TLS và phục vụ qua HTTP/2.

```
$ railway status
Project:     day12-chat-2A202601650
Environment: production
chat
    status:        ● Online
    url:           https://chat-production-620e.up.railway.app
    region:        sfo

# 1. /healthz
HTTP/2 200
{"status":"ok","service":"day12-chat-service","version":"1.0.0"}

# 2. /readyz
HTTP/2 200
{"status":"ready","redis":true}

# 3. POST /chat không có token
HTTP/2 401
www-authenticate: Bearer
{"detail":"invalid or missing bearer token"}

# 4. POST /chat có token
HTTP/2 200
{"reply":"Ngắn gọn: Deploy la gi phụ thuộc vào ba yếu tố — cấu hình qua biến môi trường, health check để orchestrator biết trạng thái, và giới hạn tài nguyên.","client_id":"sv-cloud","turns_before":0,"usd_cost":2.265e-05,"usage":{"prompt":3,"completion":37}}

# 5. Rate limit, 15 lần liên tiếp (capacity=10, refill 10/phút)
200 200 200 200 200 200 200 200 200 200 429 429 429 200 429

# 6. Header của response 429
HTTP/2 429
retry-after: 6
{"detail":"rate limit exceeded"}

# 7. State nằm ở Redis, không ở process: gọi lại cùng client_id
turns_before = 2
```

Về cái `200` ở lần thứ 14 trong mục 5: đó **không** phải lỗi. 15 request HTTPS
tuần tự từ Việt Nam sang region `sfo` mất tổng cộng hơn 6 giây, và với
`refill_per_minute=10` thì đúng 6 giây là xô có thêm 1 token. Request thứ 14
tiêu token vừa nhỏ vào, request 15 lại cạn nên trả 429. `retry-after: 6` ở mục
6 chính là con số đó. Chạy ở localhost thì 15 request xong trong ~100ms nên
không kịp refill, và kết quả là `10× 200` rồi `5× 429` liền mạch.

Log JSON service ghi ra stdout (Railway đọc được, lọc được theo field):

```
{"event": "service_started", "severity": "INFO", "ts": "2026-08-10T08:11:02.451+00:00", "service": "day12-chat-service", "version": "1.0.0"}
{"event": "chat_completed", "severity": "INFO", "ts": "2026-08-10T08:12:18.907+00:00", "client_id": "sv-cloud", "prompt_tokens": 3, "completion_tokens": 37, "usd_cost": 2.265e-05}
```

## Lỗi Đã Gặp Khi Deploy

Lần deploy đầu **thất bại** ở bước health check, dù build thành công. Log của
container:

```
Starting Container
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

Nguyên nhân: `railway.toml` có `startCommand = "uvicorn ... --port $PORT"`.
Railway thực thi `startCommand` **không qua shell**, nên `$PORT` được truyền
nguyên văn thành chuỗi 5 ký tự thay vì được nội suy. Container crash-loop, và
health check `/healthz` trả service unavailable cho tới khi hết
`healthcheckTimeout`.

Cách sửa (đã commit vào `railway.toml`):

```toml
startCommand = "sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'"
healthcheckTimeout = 120
```

`sh -c` để có shell nội suy biến; `exec` để uvicorn thay thế shell và giữ
**PID 1**, nhờ đó SIGTERM của Railway lúc deploy bản mới tới đúng process và
graceful shutdown ở CP4 mới có tác dụng. `healthcheckTimeout` nâng từ 30s lên
120s cho lần khởi động lạnh đầu tiên trên free tier.

## Ảnh Chụp Màn Hình

- `screenshots/railway-status.png` — service `chat` **Online** trên Railway
  kèm Public URL, và service `Redis` add-on
- `screenshots/healthz.png` — gọi thật qua Internet: `/healthz`, `/readyz`,
  `/chat` (401 rồi 200), rate limit và `retry-after`
- `screenshots/compose-ps.png` — bản chạy ở máy bằng `docker compose`, giữ lại
  làm bằng chứng cho CP2 (image 334MB, `uid=10001(appuser)`, cả hai container
  `healthy`)
