# ═══════════════════════════════════════════════════════════════════
# CP2 — Containerization (bản production-ready)
#
# Multi-stage: stage `builder` cài dependency vào một virtualenv riêng,
# stage `runtime` chỉ copy virtualenv đó sang. Compiler, header file và
# cache của pip nằm lại ở builder, không đi vào image cuối.
#
# Build:  docker build -t day12-chat:prod .
#         docker images day12-chat:prod
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Virtualenv độc lập để stage sau copy nguyên khối, không phải dò
# site-packages của hệ thống
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependency đi trước source code: sửa một dòng trong app/ thì layer này
# vẫn còn trong cache, không phải cài lại toàn bộ thư viện
COPY requirements.txt ./
RUN pip install -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# User thường: thoát được khỏi app cũng chỉ là uid 10001, không phải root
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser utils/ ./utils/

USER appuser

EXPOSE 8000

# Không có curl trong image slim → dùng luôn Python có sẵn.
# Đọc $PORT để healthcheck vẫn đúng khi platform gán cổng khác.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, sys, urllib.request; url = 'http://127.0.0.1:' + os.getenv('PORT', '8000') + '/healthz'; sys.exit(0 if urllib.request.urlopen(url, timeout=3).status == 200 else 1)"

# Shell form + exec: ${PORT} được shell nội suy, còn `exec` giữ uvicorn ở
# PID 1 để SIGTERM của orchestrator tới đúng process (graceful shutdown)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
