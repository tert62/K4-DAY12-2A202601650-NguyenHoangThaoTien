"""CP1 — Cấu hình theo 12-Factor.

Nguyên tắc: **không có giá trị cấu hình nào nằm trong code**. Tất cả đến từ
biến môi trường, để cùng một image chạy được ở laptop, staging và production
mà không phải sửa một dòng code nào.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toàn bộ cấu hình của service.

    pydantic-settings tự đọc biến môi trường theo tên trường (không phân biệt
    hoa thường), nên trường ``api_token`` lấy giá trị từ biến ``API_TOKEN``.

    Vì sao ``api_token`` không được có giá trị mặc định? Vì mặc định nghĩa là
    app vẫn khởi động khi bạn quên set secret trên cloud — và bạn chỉ phát
    hiện ra khi ai đó đã gọi API miễn phí bằng token mặc định đó. Không mặc
    định = fail fast ngay lúc khởi động.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cổng HTTP — trên cloud, platform tự gán qua biến PORT
    port: int = 8000

    # Secret: KHÔNG có mặc định, thiếu env là ValidationError ngay lúc import
    api_token: str

    redis_url: str = "redis://localhost:6379/0"

    # Token bucket
    bucket_capacity: int = 10
    refill_per_minute: int = 10

    # Cost guard
    daily_budget_usd: float = 1.0

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Đọc cấu hình một lần rồi cache lại (đọc env mỗi request là lãng phí)."""
    return Settings()
