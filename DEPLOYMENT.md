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
| Public URL | https://day12-chat-7erl.onrender.com |
| Platform | Render — Blueprint từ `render.yaml`, region `oregon`, plan `free` |
| Ngày deploy | 2026-08-10 |

Kiến trúc: Render đọc `render.yaml` ở gốc repo và tạo hai resource trong cùng
một Blueprint —

- **`day12-chat`** (Web Service, `runtime: docker`, build từ `Dockerfile`
  multi-stage, `healthCheckPath: /healthz`)
- **`day12-chat-redis`** (Key Value — tên mới của Render Redis, plan free)

`REDIS_URL` không được viết ra ở đâu cả: `render.yaml` khai
`fromService: { name: day12-chat-redis, type: redis, property: connectionString }`
nên Render tự nội suy connection string lúc deploy. Còn `API_TOKEN` khai
`sync: false` — Render không lưu giá trị vào repo mà hỏi lúc apply Blueprint.

Lưu ý về free tier: web service **tự ngủ sau ~15 phút không có request**, và
request đánh thức mất 30–60 giây. Lần gọi đầu tiên chậm là bình thường, không
phải lỗi — `tests/test_cp5.py` đã tính tới điều này (`FIRST_CALL_TIMEOUT = 60`).

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | Render tự inject (`10000`); Dockerfile đọc `${PORT:-8000}` nên không cần khai trong `render.yaml` |
| `API_TOKEN` | ✅ | `sync: false` trong `render.yaml` — giá trị chỉ nằm trên Render, sinh bằng `secrets.token_urlsafe(32)` |
| `REDIS_URL` | ✅ | `fromService` → connection string của Key Value `day12-chat-redis`, Render tự nội suy |
| `BUCKET_CAPACITY` | ✅ | 10 |
| `REFILL_PER_MINUTE` | ✅ | 10 |
| `DAILY_BUDGET_USD` | ✅ | 1.0 |
| `LOG_LEVEL` | ✅ | INFO |

Ở máy, `.env` (gitignored) giữ thêm `DEPLOY_API_TOKEN` — đúng giá trị `API_TOKEN`
trên Render — để `tests/test_cp5.py` gọi được `/chat` có xác thực.

## Lệnh Kiểm Tra

```bash
URL=https://day12-chat-7erl.onrender.com

# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i $URL/healthz

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Key Value)
curl -i $URL/readyz

# 3. Không có token — mong đợi 401 kèm header WWW-Authenticate
curl -i -X POST $URL/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'

# 4. Có token — mong đợi 200 kèm câu trả lời
curl -i -X POST $URL/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEPLOY_API_TOKEN" \
  -H "X-Client-Id: sv-render" \
  -d '{"message":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST $URL/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $DEPLOY_API_TOKEN" \
    -H "X-Client-Id: sv-render-rl" \
    -d '{"message":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Chạy lúc 2026-08-10 08:46 UTC, gọi qua Internet vào Public URL. `HTTP/2` vì
Render terminate TLS và phục vụ qua HTTP/2.

```
$ render services
NAME                TYPE           ID
day12-chat-redis    Key Value      red-d9sop47avr4c73bnh93g
day12-chat          Web Service    srv-d9sopofavr4c73bnif70

$ render keyvalues list
NAME                PLAN    REGION    STATUS       ID
day12-chat-redis    free    oregon    available    red-d9sop47avr4c73bnh93g

$ render deploys list day12-chat
STATUS    COMMIT                                      FINISHED                ID
Live      070996a8efdc8c5e5db510eced2646b219683ffe    2026-08-10T08:45:56Z    dep-d9sov6f10e5c73aajni0

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
{"reply": "Ngắn gọn: Deploy la gi phụ thuộc vào ba yếu tố — cấu hìn...", "client_id": "sv-render", "turns_before": 4, "usd_cost": 4.23e-05, "usage": {"prompt": 94, "completion": 47}}

# 5. Rate limit, 15 lần liên tiếp (capacity=10)
200 200 200 200 200 200 200 200 200 200 429 429 429 429 429

# 6. Header của response 429 (burst liền mạch)
HTTP/2 429
retry-after: 2
{"detail":"rate limit exceeded"}
```

`turns_before: 4` ở mục 4 là bằng chứng state nằm trong Key Value chứ không
trong RAM của process: đó là lịch sử của những lần gọi trước cùng
`X-Client-Id: sv-render`, và service đã bị tạo lại vài lần giữa các lần gọi đó.

## Lỗi Đã Gặp Khi Deploy

Hai lỗi thật, cả hai đều bắt đầu bằng một build màu xanh.

### 1. Railway (bản deploy đầu, sau đã bỏ): `$PORT` không được nội suy

Deploy fail ở health check. Log container:

```
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

`railway.toml` có `startCommand = "uvicorn ... --port $PORT"`, mà Railway thực
thi `startCommand` **không qua shell** nên `$PORT` được truyền nguyên văn.
Điểm khó thấy: `CMD` trong Dockerfile viết đúng dạng shell form, nhưng
`startCommand` **ghi đè** `CMD` nên phần đúng đó không bao giờ chạy — vì thế bản
`docker compose` ở máy vẫn hoạt động hoàn hảo. Đã sửa trong `railway.toml`:
`sh -c 'exec uvicorn ... --port ${PORT:-8000}'`.

Bản Railway đã chạy được thật (URL công khai, `/readyz` 200), sau đó **xóa** để
không tiêu credit dùng thử khi chuyển sang Render free.

### 2. Render: thiếu `API_TOKEN` → fail fast đúng như thiết kế

Blueprint tạo xong cả hai resource, deploy `Live`, `/healthz` trả 200 — nhưng
`/readyz` và `/chat` có token đều trả **500**. Log:

```
pydantic_core.ValidationError: 1 validation error for Settings
api_token
  Field required [type=missing, input_value={'port': '10000', 'redis_...0', 'log_level': 'INFO'}]
```

Ô nhập `API_TOKEN` (do `sync: false`) không được lưu giá trị lúc apply
Blueprint. Đọc env var qua Render API xác nhận service chỉ có 5 biến và
`API_TOKEN` **hoàn toàn không tồn tại** — không phải gõ sai tên.

Điều đáng chú ý là **hình dạng của lỗi**, vì nó khớp chính xác với thiết kế:

| Endpoint | Kết quả | Vì sao |
|---|---|---|
| `/healthz` | 200 | không gọi `get_settings()` — probe phải nhẹ (CP1) |
| `/chat` không token | 401 | `verify_bearer_token` chặn trước khi đọc settings |
| `/readyz` | 500 | `get_store()` → `get_settings()` → `Settings()` raise |
| `/chat` có token | 500 | cùng nguyên nhân |

Sửa bằng `PUT /v1/services/{id}/env-vars/API_TOKEN` rồi redeploy → tất cả 200.

Bài học: `api_token` không có giá trị mặc định nên service **từ chối phục vụ**
thay vì chạy tiếp với một token đoán được. Nếu để mặc định `"changeme"`, lúc đó
service đã Live, `/readyz` xanh, dashboard xanh — và bất kỳ ai đọc source trong
repo public này cũng gọi được `/chat`. Đây đúng là tình huống câu 1 của
`exercises.md` mô tả, chỉ khác là nó xảy ra thật.

## Ảnh Chụp Màn Hình

- `screenshots/render-status.png` — `day12-chat` **Live** + Key Value
  `day12-chat-redis` **available** (oregon, free), deploy `dep-d9sov6f10e5c73aajni0`
- `screenshots/healthz.png` — gọi thật qua Internet: `/healthz`, `/readyz`,
  `/chat` (401 rồi 200), rate limit và header `retry-after`
- `screenshots/compose-ps.png` — bản chạy ở máy bằng `docker compose`, giữ lại
  làm bằng chứng cho CP2 (image 334MB, `uid=10001(appuser)`, hai container `healthy`)
