# Ảnh chụp bằng chứng chạy thật

Service đã deploy lên Railway, Public URL:
**https://chat-production-620e.up.railway.app** (xem `DEPLOYMENT.md`).

| Ảnh | Nội dung |
|-----|----------|
| `railway-status.png` | Project `day12-chat-2A202601650` trên Railway: service `chat` **Online** kèm Public URL, service `Redis` (`redis:8.2.1`, volume 500MB) **Online**, domain `chat-production-620e.up.railway.app` → target port 8000, sync `ACTIVE` |
| `healthz.png` | Gọi thật qua Internet vào Public URL: `/healthz` 200, `/readyz` 200 (`redis: true`), `/chat` 401 kèm `WWW-Authenticate: Bearer` khi thiếu token, `/chat` 200 khi có token, 15 request liên tiếp cho `10× 200` rồi `5× 429`, và header `retry-after` của response 429. Chú ý `HTTP/2` — Railway phục vụ qua TLS + HTTP/2 |
| `compose-ps.png` | Bản chạy ở máy bằng `docker compose` (giữ lại làm bằng chứng CP2): image multi-stage 334MB, `id` trong container = `uid=10001(appuser)`, cả `chat` và `redis` đều `healthy` |

Các ảnh này được **render lại từ output nguyên văn** của những lệnh đã thật sự
chạy lúc 2026-08-10, không phải ảnh chụp cửa sổ terminal hay dashboard.
