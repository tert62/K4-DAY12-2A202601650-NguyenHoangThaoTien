# Ảnh chụp bằng chứng chạy thật

Bài này dùng **phương án dự phòng** (`LOCAL_FALLBACK=true`): stack chạy bằng
`docker compose up -d` ở máy, chưa có Public URL trên cloud. Xem `DEPLOYMENT.md`.

| Ảnh | Nội dung |
|-----|----------|
| `compose-ps.png` | `docker compose ps` — cả `chat` và `redis` đều `healthy`; dung lượng image multi-stage (334MB); `id` trong container = `uid=10001(appuser)`, không phải root |
| `healthz.png` | `/healthz` 200, `/readyz` 200 (`redis: true`), `/chat` 401 kèm `WWW-Authenticate: Bearer` khi thiếu token, `/chat` 200 khi có token, và 15 request liên tiếp cho ra `10× 200` rồi `5× 429` |

Hai ảnh này được **render lại từ output thật** của các lệnh đã chạy lúc
2026-08-10 (không phải ảnh chụp cửa sổ terminal). Nội dung là output nguyên
văn. Sau khi deploy lên cloud thành công, nên thay bằng ảnh chụp dashboard
của platform và ảnh gọi `/healthz` qua URL công khai.
