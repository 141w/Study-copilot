"""UTC datetime serialization helpers.

DB columns store **naive UTC** (e.g. `datetime.now(UTC).replace(tzinfo=None)`).
Frontend `new Date('2026-09-13 10:06:47')` without a zone is parsed as **local**,
which shifts relative time by the UTC offset (e.g. +8h in CST).

Always emit ISO-8601 with an explicit `Z` so JS treats the value as UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime


def isoformat_utc(dt: datetime | str | None) -> str | None:
    """Serialize a datetime as ISO-8601 UTC with trailing Z.

    接受 datetime 或已是字符串的值（字符串原样返回，避免对已序列化字段二次处理报错）。
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        # Naive values in this codebase are UTC
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
