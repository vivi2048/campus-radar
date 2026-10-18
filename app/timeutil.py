from __future__ import annotations

from datetime import datetime, timezone

from .config import LOCAL_TZ

MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def to_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(LOCAL_TZ)


def local_iso(value: datetime) -> str:
    return to_local(value).isoformat(timespec="minutes")


def imap_date(value: datetime) -> str:
    return f"{value.day:02d}-{MONTHS[value.month - 1]}-{value.year}"


def parse_local_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return to_local(parsed)


def normalize_optional_iso(value: str | None, *, date_only_time: str = "00:00") -> str | None:
    """Accept an ISO/datetime-local string and return a Beijing offset ISO string."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) == 10:
        value = f"{value}T{date_only_time}"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("时间格式不正确") from exc
    return local_iso(parsed)
