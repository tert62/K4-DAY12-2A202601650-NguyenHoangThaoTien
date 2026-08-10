# Ảnh chụp bằng chứng chạy thật

Service đã deploy lên **Render** (free tier), Public URL:
**https://day12-chat-7erl.onrender.com** — xem `DEPLOYMENT.md`.

| Ảnh | Nội dung |
|-----|----------|
| `render-status.png` | `day12-chat` (Web Service) **Live** và `day12-chat-redis` (Key Value, plan free, region oregon) **available**; deploy `dep-d9sov6f10e5c73aajni0` từ commit `070996a` |
| `healthz.png` | Gọi thật qua Internet vào Public URL: `/healthz` 200, `/readyz` 200 (`redis: true`), `/chat` 401 kèm `WWW-Authenticate: Bearer` khi thiếu token, `/chat` 200 khi có token, 15 request liên tiếp cho `10× 200` rồi `5× 429`, và header `retry-after` của response 429. Chú ý `HTTP/2` — Render terminate TLS và phục vụ qua HTTP/2 |
| `compose-ps.png` | Bản chạy ở máy bằng `docker compose` (giữ lại làm bằng chứng CP2): image multi-stage 334MB, `id` trong container = `uid=10001(appuser)`, cả `chat` và `redis` đều `healthy` |

Các ảnh này được **render lại từ output nguyên văn** của những lệnh đã thật sự
chạy lúc 2026-08-10, không phải ảnh chụp cửa sổ terminal hay dashboard.

> Trước Render tôi có deploy thành công một bản trên Railway (`/readyz` 200 qua
> URL công khai), sau đó xóa để không tiêu credit dùng thử khi chuyển sang
> Render free. Lỗi `$PORT` gặp ở bản đó được ghi lại trong `DEPLOYMENT.md` và
> câu 10 của `exercises.md`.
