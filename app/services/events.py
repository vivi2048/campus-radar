from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time, timedelta
from typing import Any

from ..config import LOCAL_TZ
from ..db import Database
from ..extract.company import canonicalize_company
from ..extract.links import normalize_url
from ..timeutil import local_iso, normalize_optional_iso, utc_now_iso

EVENT_FIELDS = {
    "kind",
    "interview_round",
    "company",
    "role",
    "exam_start",
    "exam_end",
    "exam_time_known",
    "deadline",
    "deadline_time_known",
    "duration_minutes",
    "platform",
    "exam_url",
    "mode",
    "location",
    "access_code",
    "status",
    "ignored",
    "notes",
}
ALLOWED_STATUS = {"pending", "done", "cancelled"}
ALLOWED_MODES = {"online", "offline", "unknown"}
ALLOWED_KINDS = {"exam", "interview"}
AUTO_EDIT_FIELDS = EVENT_FIELDS - {"status", "ignored", "notes"}
MAX_TEXT = 5000


class EventValidationError(ValueError):
    pass


def _as_bool(value: Any) -> bool:
    return bool(int(value)) if isinstance(value, int) else bool(value)


def serialize_event(row: dict[str, Any], *, include_source: bool = False) -> dict[str, Any]:
    event = {
        "id": row["id"],
        "account_id": row.get("account_id"),
        "kind": row.get("kind") or "exam",
        "interview_round": row.get("interview_round") or "",
        "company": row.get("company") or "",
        "role": row.get("role") or "",
        "exam_start": row.get("exam_start"),
        "exam_end": row.get("exam_end"),
        "exam_time_known": _as_bool(row.get("exam_time_known", 1)),
        "deadline": row.get("deadline"),
        "deadline_time_known": _as_bool(row.get("deadline_time_known", 1)),
        "duration_minutes": row.get("duration_minutes"),
        "platform": row.get("platform"),
        "exam_url": row.get("exam_url"),
        "mode": row.get("mode") or "unknown",
        "location": row.get("location"),
        "access_code": row.get("access_code"),
        "status": row.get("status") or "pending",
        "ignored": _as_bool(row.get("ignored", 0)),
        "needs_review": _as_bool(row.get("needs_review", 0)),
        "manually_edited": _as_bool(row.get("manually_edited", 0)),
        "auto_notes": row.get("auto_notes"),
        "notes": row.get("notes"),
        "source_subject": row.get("source_subject"),
        "source_sender": row.get("source_sender"),
        "source_received_at": row.get("source_received_at"),
        "source_count": row.get("source_count") or 1,
        "is_demo": _as_bool(row.get("is_demo", 0)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    if include_source:
        event["source_body"] = row.get("source_body")
    return event


def list_events(db: Database, *, include_ignored: bool = True) -> list[dict[str, Any]]:
    where = "" if include_ignored else "WHERE ignored = 0"
    rows = db.fetch_all(
        f"""
        SELECT * FROM events {where}
        ORDER BY
            CASE WHEN ignored = 1 THEN 1 ELSE 0 END,
            CASE WHEN status != 'pending' THEN 1 ELSE 0 END,
            CASE WHEN exam_start IS NULL THEN 1 ELSE 0 END,
            exam_start ASC,
            created_at DESC
        """
    )
    return [serialize_event(row) for row in rows]


def get_event(db: Database, event_id: int, *, include_source: bool = True) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))
    return serialize_event(row, include_source=include_source) if row else None


def get_raw_event(db: Database, event_id: int) -> dict[str, Any] | None:
    return db.fetch_one("SELECT * FROM events WHERE id = ?", (event_id,))


def delete_event(db: Database, event_id: int) -> bool:
    if not db.fetch_one("SELECT id FROM events WHERE id = ?", (event_id,)):
        return False
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return True


def _clean_optional_text(value: Any, limit: int = MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _normalize_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    url = normalize_url(text)
    if not re.match(r"^https?://[^\s]+$", url, re.IGNORECASE):
        raise EventValidationError("链接必须以 http:// 或 https:// 开头")
    return url[:2048]


def _normalize_duration(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise EventValidationError("时长必须是分钟数") from exc
    if minutes < 1 or minutes > 1440:
        raise EventValidationError("时长需在 1 到 1440 分钟之间")
    return minutes


def _normalize_time_pair(
    start: Any,
    end: Any,
) -> tuple[str | None, str | None]:
    try:
        normalized_start = normalize_optional_iso(None if start in (None, "") else str(start))
        normalized_end = normalize_optional_iso(None if end in (None, "") else str(end))
    except ValueError as exc:
        raise EventValidationError(str(exc)) from exc
    if normalized_start and normalized_end:
        start_dt = datetime.fromisoformat(normalized_start)
        end_dt = datetime.fromisoformat(normalized_end)
        if end_dt < start_dt:
            raise EventValidationError("结束时间不能早于开始时间")
    return normalized_start, normalized_end


def _validate_status(value: Any) -> str:
    status = str(value or "pending")
    if status not in ALLOWED_STATUS:
        raise EventValidationError("无效的状态")
    return status


def _validate_mode(value: Any) -> str:
    mode = str(value or "unknown")
    if mode not in ALLOWED_MODES:
        raise EventValidationError("无效的形式")
    return mode


def _validate_kind(value: Any) -> str:
    kind = str(value or "exam")
    if kind not in ALLOWED_KINDS:
        raise EventValidationError("无效的记录类型")
    return kind


def _normalize_round(value: Any, kind: str) -> str | None:
    if kind != "interview":
        return None
    return _clean_optional_text(value, 20)


def _compute_needs_review(company: str, exam_start: str | None, exam_time_known: bool) -> bool:
    return bool(not company or not exam_start or not exam_time_known)


def create_manual_event(db: Database, payload: dict[str, Any]) -> dict[str, Any]:
    company = str(payload.get("company") or "").strip()[:100]
    if not company:
        raise EventValidationError("请填写公司名称")
    kind = _validate_kind(payload.get("kind"))
    interview_round = _normalize_round(payload.get("interview_round"), kind)
    exam_start, exam_end = _normalize_time_pair(payload.get("exam_start"), payload.get("exam_end"))
    if exam_end and not exam_start:
        raise EventValidationError("填写结束时间前，请先填写开始时间")
    deadline, _ = _normalize_time_pair(payload.get("deadline"), None)
    exam_time_known = bool(payload.get("exam_time_known", True)) and bool(exam_start)
    deadline_time_known = bool(payload.get("deadline_time_known", True)) and bool(deadline)
    company = company[:100]
    now = utc_now_iso()
    event_id = db.execute(
        """
        INSERT INTO events (
            account_id, kind, interview_round, company, role, exam_start, exam_end, exam_time_known,
            deadline, deadline_time_known, duration_minutes, platform, exam_url,
            mode, location, access_code, status, ignored, needs_review,
            manually_edited, auto_notes, notes, source_subject, source_sender,
            source_received_at, source_body, source_count, is_demo,
            created_at, updated_at
        ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1,
                  NULL, ?, NULL, NULL, NULL, NULL, 1, 0, ?, ?)
        """,
        (
            kind,
            interview_round or "",
            company,
            _clean_optional_text(payload.get("role"), 100) or "",
            exam_start,
            exam_end,
            int(exam_time_known),
            deadline,
            int(deadline_time_known),
            _normalize_duration(payload.get("duration_minutes")),
            _clean_optional_text(payload.get("platform"), 100),
            _normalize_url(payload.get("exam_url")),
            _validate_mode(payload.get("mode")),
            _clean_optional_text(payload.get("location"), 200),
            _clean_optional_text(payload.get("access_code"), 80),
            _validate_status(payload.get("status")),
            int(_compute_needs_review(company, exam_start, exam_time_known)),
            _clean_optional_text(payload.get("notes")),
            now,
            now,
        ),
    )
    return get_event(db, event_id)  # type: ignore[return-value]


def update_event(db: Database, event_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
    row = get_raw_event(db, event_id)
    if not row:
        return None
    if not changes:
        return serialize_event(row, include_source=True)

    unknown = set(changes) - EVENT_FIELDS
    if unknown:
        raise EventValidationError(f"不支持修改字段：{', '.join(sorted(unknown))}")

    values: dict[str, Any] = {}
    manual_fields = set(changes) & AUTO_EDIT_FIELDS

    if "kind" in changes or "interview_round" in changes:
        final_kind = _validate_kind(changes.get("kind", row.get("kind") or "exam"))
        if "kind" in changes:
            values["kind"] = final_kind
        if final_kind == "interview":
            if "interview_round" in changes:
                values["interview_round"] = _normalize_round(
                    changes.get("interview_round"), final_kind
                ) or ""
        else:
            values["interview_round"] = ""
    if "company" in changes:
        company = str(changes["company"] or "").strip()[:100]
        if not company:
            raise EventValidationError("公司名称不能为空")
        values["company"] = company
    if "role" in changes:
        values["role"] = _clean_optional_text(changes["role"], 100) or ""
    if "exam_start" in changes or "exam_end" in changes:
        raw_start = changes.get("exam_start", row.get("exam_start"))
        raw_end = changes.get("exam_end", row.get("exam_end"))
        if "exam_start" in changes and changes.get("exam_start") in (None, "") and changes.get("exam_end"):
            raise EventValidationError("请先填写开始时间，再填写结束时间")
        if "exam_start" in changes and changes.get("exam_start") in (None, ""):
            raw_end = None
        exam_start, exam_end = _normalize_time_pair(raw_start, raw_end)
        if exam_end and not exam_start:
            raise EventValidationError("填写结束时间前，请先填写开始时间")
        values["exam_start"] = exam_start
        values["exam_end"] = exam_end
    if "exam_time_known" in changes:
        values["exam_time_known"] = int(bool(changes["exam_time_known"]))
    if "deadline" in changes:
        deadline, _ = _normalize_time_pair(changes.get("deadline"), None)
        values["deadline"] = deadline
    if "deadline_time_known" in changes:
        values["deadline_time_known"] = int(bool(changes["deadline_time_known"]))
    if "duration_minutes" in changes:
        values["duration_minutes"] = _normalize_duration(changes.get("duration_minutes"))
    if "platform" in changes:
        values["platform"] = _clean_optional_text(changes.get("platform"), 100)
    if "exam_url" in changes:
        values["exam_url"] = _normalize_url(changes.get("exam_url"))
    if "mode" in changes:
        values["mode"] = _validate_mode(changes.get("mode"))
    if "location" in changes:
        values["location"] = _clean_optional_text(changes.get("location"), 200)
    if "access_code" in changes:
        values["access_code"] = _clean_optional_text(changes.get("access_code"), 80)
    if "status" in changes:
        values["status"] = _validate_status(changes.get("status"))
    if "ignored" in changes:
        values["ignored"] = int(bool(changes.get("ignored")))
    if "notes" in changes:
        values["notes"] = _clean_optional_text(changes.get("notes"))

    merged = {**row, **values}
    if "exam_start" in values and "exam_time_known" not in changes and changes.get("exam_start"):
        values["exam_time_known"] = int(bool(values["exam_start"]))
        merged["exam_time_known"] = values["exam_time_known"]
    if "deadline" in values and "deadline_time_known" not in changes and changes.get("deadline"):
        values["deadline_time_known"] = int(bool(values["deadline"]))
        merged["deadline_time_known"] = values["deadline_time_known"]
    if not any(key in values for key in ("exam_start", "exam_time_known")):
        pass
    values["needs_review"] = int(
        _compute_needs_review(
            str(merged.get("company") or ""),
            merged.get("exam_start"),
            bool(merged.get("exam_time_known")),
        )
    )
    if manual_fields:
        values["manually_edited"] = 1
    values["updated_at"] = utc_now_iso()

    assignments = ", ".join(f"{column} = ?" for column in values)
    db.execute(
        f"UPDATE events SET {assignments} WHERE id = ?",
        (*values.values(), event_id),
    )
    return get_event(db, event_id)


def set_event_status(db: Database, event_id: int, status: str) -> dict[str, Any] | None:
    if status not in ALLOWED_STATUS:
        raise EventValidationError("无效的状态")
    if not get_raw_event(db, event_id):
        return None
    db.execute(
        "UPDATE events SET status = ?, updated_at = ? WHERE id = ?",
        (status, utc_now_iso(), event_id),
    )
    return get_event(db, event_id)


def _norm_company(value: str | None) -> str:
    text = canonicalize_company(value or "").casefold()
    return re.sub(r"[\s·,，.。()（）/|｜&]+", "", text)


def _norm_role(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\s·,，.。()（）岗位职位]", "", text)


def _norm_round(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = re.sub(r"(?:第|轮次|面试|面谈|\s|[-—–|｜·:：])", "", text)
    return text


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)


def find_duplicate_event(
    db: Database,
    *,
    account_id: int,
    company: str,
    role: str,
    exam_start: str | None,
    exam_url: str | None,
    reschedule: bool = False,
    kind: str = "exam",
    interview_round: str | None = None,
) -> dict[str, Any] | None:
    rows = db.fetch_all(
        "SELECT * FROM events WHERE account_id = ? ORDER BY id DESC",
        (account_id,),
    )
    company_key = _norm_company(company)
    role_key = _norm_role(role)
    round_key = _norm_round(interview_round)
    start_dt = _parse_iso(exam_start)
    for row in rows:
        if (row.get("kind") or "exam") != kind:
            continue
        row_round = _norm_round(row.get("interview_round"))
        if kind == "interview" and round_key and row_round and round_key != row_round:
            continue
        row_start = _parse_iso(row.get("exam_start"))
        if exam_url and row.get("exam_url") == exam_url:
            if (
                not reschedule
                and start_dt
                and row_start
                and abs((start_dt - row_start).total_seconds()) > 36 * 3600
            ):
                continue
            if company_key and row.get("company") and _norm_company(row["company"]) != company_key:
                continue
            return row
        if not company_key or not row.get("company"):
            continue
        if _norm_company(row["company"]) != company_key:
            continue
        if role_key and row.get("role") and _norm_role(row["role"]) != role_key:
            continue
        if start_dt and row_start:
            if start_dt.date() == row_start.date():
                if (
                    start_dt.hour != 0
                    and row_start.hour != 0
                    and abs((start_dt - row_start).total_seconds()) > 3 * 3600
                ):
                    continue
                return row
            if reschedule and abs((start_dt - row_start).total_seconds()) <= 45 * 24 * 3600:
                return row
            continue
        if reschedule:
            return row
    return None


def merge_into_event(
    db: Database,
    row: dict[str, Any],
    *,
    new_values: dict[str, Any],
    subject: str,
    sender: str,
    received_at: str,
    body: str,
    reschedule: bool,
) -> int:
    updates: dict[str, Any] = {
        "source_subject": subject,
        "source_sender": sender,
        "source_received_at": received_at,
        "source_body": body[:50_000],
        "source_count": int(row.get("source_count") or 1) + 1,
        "updated_at": utc_now_iso(),
    }

    if not row.get("manually_edited"):
        checks = (
            "company",
            "role",
            "interview_round",
            "platform",
            "exam_url",
            "location",
            "access_code",
        )
        for key in checks:
            if not row.get(key) and new_values.get(key):
                updates[key] = new_values[key]
        if reschedule and new_values.get("exam_start"):
            updates["exam_start"] = new_values["exam_start"]
            updates["exam_end"] = new_values.get("exam_end")
            updates["exam_time_known"] = new_values.get("exam_time_known", 1)
        elif not row.get("exam_start") and new_values.get("exam_start"):
            updates["exam_start"] = new_values["exam_start"]
            updates["exam_end"] = new_values.get("exam_end")
            updates["exam_time_known"] = new_values.get("exam_time_known", 1)
        elif not row.get("exam_end") and new_values.get("exam_end"):
            updates["exam_end"] = new_values["exam_end"]
        if reschedule and new_values.get("deadline"):
            updates["deadline"] = new_values["deadline"]
            updates["deadline_time_known"] = new_values.get("deadline_time_known", 1)
        elif not row.get("deadline") and new_values.get("deadline"):
            updates["deadline"] = new_values["deadline"]
            updates["deadline_time_known"] = new_values.get("deadline_time_known", 1)
        if not row.get("duration_minutes") and new_values.get("duration_minutes"):
            updates["duration_minutes"] = new_values["duration_minutes"]
        if row.get("mode") in {"unknown", None} and new_values.get("mode") not in {"unknown", None}:
            updates["mode"] = new_values["mode"]
        notes = [part for part in (row.get("auto_notes"), new_values.get("auto_notes")) if part]
        if notes:
            unique: list[str] = []
            for part in "\n".join(notes).splitlines():
                if part.strip() and part.strip() not in unique:
                    unique.append(part.strip())
            updates["auto_notes"] = "\n".join(unique[:8])
        company = updates.get("company", row.get("company") or "")
        exam_start = updates.get("exam_start", row.get("exam_start"))
        time_known = updates.get("exam_time_known", row.get("exam_time_known", 1))
        updates["needs_review"] = int(_compute_needs_review(company, exam_start, bool(time_known)))

    assignments = ", ".join(f"{column} = ?" for column in updates)
    db.execute(
        f"UPDATE events SET {assignments} WHERE id = ?",
        (*updates.values(), row["id"]),
    )
    return int(row["id"])


def seed_demo(db: Database) -> int:
    existing = db.fetch_one("SELECT COUNT(*) AS count FROM events WHERE is_demo = 1")
    if existing and existing["count"]:
        return 0
    now = datetime.now(LOCAL_TZ).replace(second=0, microsecond=0)
    base = now.date()
    rows = [
        {
            "company": "字节跳动",
            "role": "后端开发工程师",
            "day_offset": 2,
            "hour": 19,
            "end_hour": 21,
            "deadline_day": 2,
            "deadline_hour": 18,
            "platform": "牛客网",
            "mode": "online",
            "url": "https://www.nowcoder.com/",
            "access_code": "DEMO2026",
            "notes": "请提前 30 分钟登录考试系统，并确保摄像头与麦克风可用。",
            "subject": "【字节跳动】2027届校园招聘-后端开发工程师-笔试邀请",
            "sender": "字节跳动招聘 <campus@bytedance.com>",
            "extra": "考试过程中请勿切换页面。",
        },
        {
            "company": "腾讯",
            "role": "产品经理",
            "day_offset": 4,
            "hour": 10,
            "end_hour": 11,
            "end_minute": 30,
            "deadline_day": 3,
            "deadline_hour": 22,
            "platform": "赛码网",
            "mode": "online",
            "url": "https://www.acmcoder.com/",
            "access_code": None,
            "notes": "建议使用最新版 Chrome 浏览器完成测评。",
            "subject": "腾讯 2027 校园招聘在线测评通知",
            "sender": "腾讯招聘 <campus@tencent.com>",
            "extra": "考试时长 90 分钟。",
        },
        {
            "company": "美团",
            "role": "数据分析师",
            "day_offset": 7,
            "hour": 15,
            "end_hour": 17,
            "deadline_day": 7,
            "deadline_hour": 14,
            "platform": "北森",
            "mode": "online",
            "url": None,
            "access_code": None,
            "notes": "请准备好身份证件，考试开始前会进行身份核验。",
            "subject": "【美团】在线笔试邀请 - 数据分析师",
            "sender": "美团校园招聘 <campus@meituan.com>",
            "extra": "考试入口将在开考前 30 分钟开放。",
        },
        {
            "company": "快手",
            "role": "前端开发工程师",
            "day_offset": -2,
            "hour": 19,
            "end_hour": 20,
            "deadline_day": -2,
            "deadline_hour": 18,
            "platform": "HackerRank",
            "mode": "online",
            "url": "https://www.hackerrank.com/",
            "access_code": None,
            "notes": "本场考试已结束，可标记为完成归档。",
            "subject": "【快手】前端开发工程师笔试提醒",
            "sender": "快手招聘 <campus@kuaishou.com>",
            "extra": "",
            "status": "done",
            "needs_review": False,
        },
        {
            "company": "小红书",
            "role": "内容运营",
            "day_offset": 5,
            "hour": None,
            "end_hour": None,
            "deadline_day": 5,
            "deadline_hour": None,
            "platform": "在线考试系统",
            "mode": "online",
            "url": None,
            "access_code": None,
            "notes": "考试时间将在确认邮件中另行通知。",
            "subject": "【小红书】2027届校园招聘测评邀请",
            "sender": "小红书招聘 <campus@xiaohongshu.com>",
            "extra": "请于 10 月 23 日前留意下一封包含考试链接的邮件。",
            "time_known": False,
            "needs_review": True,
        },
        {
            "kind": "interview",
            "interview_round": "一面",
            "company": "百度",
            "role": "产品运营",
            "day_offset": 3,
            "hour": 15,
            "end_hour": 16,
            "deadline_day": 1,
            "deadline_hour": 18,
            "platform": "腾讯会议",
            "mode": "online",
            "url": "https://meeting.tencent.com/demo",
            "access_code": "会议号 123 456 789",
            "notes": "请提前 10 分钟进入会议等候室，确认摄像头和麦克风正常。",
            "subject": "【百度】产品运营一面面试邀请",
            "sender": "百度招聘 <campus@baidu.com>",
            "extra": "面试形式：视频面试\n面试官：业务负责人",
        },
        {
            "kind": "interview",
            "interview_round": "二面",
            "company": "招商银行",
            "role": "数据工程师",
            "day_offset": 6,
            "hour": 10,
            "end_hour": 11,
            "end_minute": 30,
            "deadline_day": 5,
            "deadline_hour": 20,
            "platform": "现场",
            "mode": "offline",
            "url": None,
            "access_code": None,
            "location": "深圳市福田区深南大道招商银行大厦",
            "notes": "请携带身份证件，提前 20 分钟到场签到。",
            "subject": "【招商银行】数据工程师二面面试通知",
            "sender": "招商银行招聘 <campus@cmbchina.com>",
            "extra": "面试地点：深圳市福田区深南大道招商银行大厦",
        },
    ]

    inserted = 0
    now_iso = utc_now_iso()
    for item in rows:
        event_day = base + timedelta(days=item["day_offset"])
        time_known = item.get("time_known", True)
        if time_known and item["hour"] is not None:
            start = datetime.combine(event_day, time(item["hour"], 0), tzinfo=LOCAL_TZ)
            end = datetime.combine(
                event_day,
                time(item.get("end_hour") or item["hour"] + 2, item.get("end_minute", 0)),
                tzinfo=LOCAL_TZ,
            )
            exam_start = local_iso(start)
            exam_end = local_iso(end)
            duration = int((end - start).total_seconds() // 60)
        else:
            exam_start = local_iso(datetime.combine(event_day, time(0, 0), tzinfo=LOCAL_TZ))
            exam_end = None
            duration = None
        deadline_day = base + timedelta(days=item["deadline_day"])
        if item.get("deadline_hour") is not None:
            deadline_dt = datetime.combine(
                deadline_day, time(item["deadline_hour"], 0), tzinfo=LOCAL_TZ
            )
            deadline_time_known = True
        else:
            deadline_dt = datetime.combine(deadline_day, time(23, 59), tzinfo=LOCAL_TZ)
            deadline_time_known = False
        deadline = local_iso(deadline_dt)
        chinese_date = f"{event_day.month}月{event_day.day}日"
        time_text = (
            f"{item['hour']:02d}:00-{item.get('end_hour') or item['hour'] + 2:02d}:{item.get('end_minute', 0):02d}"
            if time_known
            else "时间待确认"
        )
        kind = item.get("kind", "exam")
        is_interview = kind == "interview"
        event_label = "面试" if is_interview else "在线笔试"
        time_label = "面试时间" if is_interview else "考试时间"
        platform_label = "面试平台" if is_interview else "考试平台"
        link_label = "面试链接" if is_interview else "考试链接"
        code_label = "会议信息" if is_interview else "考试口令"
        location_line = (
            f"面试地点：{item['location']}\n" if item.get("location") else ""
        )
        source_body = (
            f"同学你好：\n\n感谢你投递{item['company']}「{item['role']}」岗位，"
            f"现邀请你参加{event_label}。\n\n"
            f"{time_label}：{chinese_date} {time_text}（北京时间）\n"
            f"{platform_label}：{item['platform']}\n"
            f"{link_label}：{item['url'] + chr(10) if item['url'] else ''}"
            f"{code_label + '：' + item['access_code'] + chr(10) if item['access_code'] else ''}"
            f"{location_line}"
            f"{item['extra']}\n\n{item['notes']}\n\n此为示例数据，不对应真实安排。"
        )
        event_id = db.execute(
            """
            INSERT INTO events (
                account_id, kind, interview_round, company, role, exam_start, exam_end, exam_time_known,
                deadline, deadline_time_known, duration_minutes, platform, exam_url,
                mode, location, access_code, status, ignored, needs_review,
                manually_edited, auto_notes, notes, source_subject, source_sender,
                source_received_at, source_body, source_count, is_demo,
                created_at, updated_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0,
                      NULL, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                kind,
                item.get("interview_round", ""),
                item["company"],
                item["role"],
                exam_start,
                exam_end,
                int(time_known),
                deadline,
                int(deadline_time_known),
                duration,
                item["platform"],
                item["url"],
                item["mode"],
                item.get("location"),
                item["access_code"],
                item.get("status", "pending"),
                int(item.get("needs_review", False)),
                item["notes"],
                item["subject"],
                item["sender"],
                local_iso(now - timedelta(days=1)),
                source_body,
                now_iso,
                now_iso,
            ),
        )
        if event_id:
            inserted += 1
    return inserted


def clear_demo(db: Database) -> int:
    row = db.fetch_one("SELECT COUNT(*) AS count FROM events WHERE is_demo = 1")
    count = int(row["count"]) if row else 0
    if count:
        db.execute("DELETE FROM events WHERE is_demo = 1")
    return count

