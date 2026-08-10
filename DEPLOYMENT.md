# Thông Tin Deploy — Checkpoint 5

> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị token vào đây.**
> Repo này công khai — dán token vào là mất token.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Nguyễn Hoàng Thảo Tiên |
| Mã học viên | 2A202601650 |
| Repo | https://github.com/tert62/K4-Day12-2A202601650-NguyenHoangThaoTien |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | chưa có — đang dùng phương án dự phòng, xem mục cuối trang |
| Platform | dự kiến Railway (chưa hoàn tất deploy); hiện chạy bằng Docker Compose ở máy |
| Ngày deploy | 2026-08-10 (bản chạy ở máy) |

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | platform tự gán; Dockerfile đọc `${PORT:-8000}` nên không cần cố định |
| `API_TOKEN` | ✅ | sinh bằng `secrets.token_urlsafe(32)`, đặt trong dashboard / file `.env` ở máy — không nằm trong repo |
| `REDIS_URL` | ✅ | ở máy: `redis://redis:6379/0` (tên service trong compose); trên cloud dự kiến dùng Redis add-on của Railway |
| `BUCKET_CAPACITY` | ✅ | 10 |
| `REFILL_PER_MINUTE` | ✅ | 10 |
| `DAILY_BUDGET_USD` | ✅ | 1.0 |
| `LOG_LEVEL` | ✅ | INFO |

## Lệnh Kiểm Tra

Thay `<URL>` bằng Public URL ở trên (bản chạy ở máy: `http://localhost:8000`):

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i <URL>/healthz

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i <URL>/readyz

# 3. Không có token — mong đợi 401 kèm header WWW-Authenticate
curl -i -X POST <URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'

# 4. Có token — mong đợi 200 kèm câu trả lời
curl -i -X POST <URL>/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "X-Client-Id: sv-test" \
  -d '{"message":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST <URL>/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "X-Client-Id: sv-test" \
    -d '{"message":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Chạy lúc 2026-08-10, stack `docker compose up -d` ở máy. Cổng 8000 của máy đang
bị một project khác chiếm nên host port là 8001 (`CHAT_HOST_PORT=8001` trong
`.env`); bên trong container vẫn là 8000.

```
$ docker compose ps
NAME                                               IMAGE                                           COMMAND                  SERVICE   STATUS                    PORTS
k4-day12-2a202601650-nguyenhoangthaotien-chat-1    k4-day12-2a202601650-nguyenhoangthaotien-chat   "sh -c 'exec uvicorn…"   chat      Up 12 seconds (healthy)   0.0.0.0:8001->8000/tcp
k4-day12-2a202601650-nguyenhoangthaotien-redis-1   redis:7-alpine                                  "docker-entrypoint.s…"   redis     Up 1 minute (healthy)     0.0.0.0:6379->6379/tcp

# 1. /healthz
HTTP/1.1 200 OK
{"status":"ok","service":"day12-chat-service","version":"1.0.0"}

# 2. /readyz
HTTP/1.1 200 OK
{"status":"ready","redis":true}

# 3. POST /chat không có token
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"invalid or missing bearer token"}

# 4. POST /chat có token
HTTP/1.1 200 OK
{"reply":"Ngắn gọn: Deploy la gi phụ thuộc vào ba yếu tố — cấu hình qua biến môi trường, health check để orchestrator biết trạng thái, và giới hạn tài nguyên.","client_id":"sv-test","turns_before":0,"usd_cost":2.265e-05,"usage":{"prompt":3,"completion":37}}

# 5. Rate limit, 15 lần liên tiếp (capacity=10)
200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

Log JSON do service ghi ra stdout (một dòng một event, cloud đọc được):

```
{"event": "service_started", "severity": "INFO", "ts": "2026-08-10T07:45:29.868213+00:00", "service": "day12-chat-service", "version": "1.0.0"}
{"event": "chat_completed", "severity": "INFO", "ts": "2026-08-10T07:45:42.032672+00:00", "client_id": "sv-rl", "prompt_tokens": 269, "completion_tokens": 43, "usd_cost": 6.615e-05}
```

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

- `screenshots/compose-ps.png` — stack đang chạy (`docker compose ps`), cả hai container `healthy`
- `screenshots/healthz.png` — kết quả gọi `/healthz`, `/readyz` và `/chat`

---

## Nếu Dùng Phương Án Dự Phòng

Bài này **đang dùng phương án dự phòng**: `LOCAL_FALLBACK=true` trong `.env`,
stack chạy bằng `docker compose up -d` ở máy, CP5 vì vậy tối đa 60% điểm (9/15).

Lý do chưa có Public URL:

```
Chưa hoàn tất bước đăng ký/liên kết tài khoản cloud (Railway) và tạo Redis
add-on, nên chưa có địa chỉ công khai để nộp. Toàn bộ phần còn lại của
checkpoint đã chạy thật ở máy: image multi-stage 334MB, container chạy bằng
user thường uid 10001, HEALTHCHECK của Docker báo `healthy`, /readyz nối được
Redis thật trong compose, và rate limit hoạt động đúng (10 request rồi 429).

Khi deploy xong, chỉ cần làm 3 việc:
  1. thay Public URL ở bảng "Service" bên trên bằng URL thật (https://...)
  2. đặt LOCAL_FALLBACK=false và DEPLOY_API_TOKEN=<token đã set trên dashboard>
     trong .env
  3. chạy lại `pytest tests/test_cp5.py -v`
```
