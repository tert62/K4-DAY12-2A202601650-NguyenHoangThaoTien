"""CP1 — Structured logging.

`print("client abc hỏi gì đó")` là log cho người đọc. Cloud (Railway, Render,
Cloud Run, Datadog...) đọc log bằng máy: một dòng = một JSON object thì mới
lọc/đếm/cảnh báo được. Đây là khác biệt lớn giữa localhost và production.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """CHO SẴN — thời điểm hiện tại theo ISO-8601, múi giờ UTC."""
    return datetime.now(timezone.utc).isoformat()


def emit(event: str, severity: str = "INFO", **fields) -> str:
    """Ghi một dòng log JSON ra stdout, trả về chính dòng đó.

    ``severity`` viết hoa vì đó là tên khóa Google Cloud Logging hiểu được để
    tô màu và lọc. Không dùng ``indent``: cloud gom log theo dòng, một event
    xuống dòng là một log bị vỡ thành nhiều bản ghi rác.

    Ví dụ:
        >>> emit("chat_completed", client_id="sv01", usd_cost=0.0001)
        '{"event": "chat_completed", "severity": "INFO", "ts": "...", ...}'
    """
    record = {
        "event": event,
        "severity": severity.upper(),
        "ts": utc_now_iso(),
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False)
    # flush ngay: stdout của container thường bị buffer, log mất khi crash
    print(line, file=sys.stdout, flush=True)
    return line
