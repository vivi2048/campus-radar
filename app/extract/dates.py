from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from ..config import LOCAL_TZ
from ..timeutil import to_local

MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
EN_MONTH_PATTERN = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Sept|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?"

CN_DATE_WITH_MONTH_RE = re.compile(
    r"(?:(?P<year>20\d{2})\s*[年./-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*月\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])\s*[日号]?"
)
CN_NUMERIC_DATE_RE = re.compile(
    r"(?<!\d)(?P<year>20\d{2})\s*[-/.]\s*"
    r"(?P<month>1[0-2]|0?[1-9])\s*[-/.]\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])(?!\d)"
)
EN_MONTH_FIRST_RE = re.compile(
    rf"(?<![A-Za-z])(?P<month_name>{EN_MONTH_PATTERN})\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(?P<year>20\d{2}))?",
    re.IGNORECASE,
)
EN_DAY_FIRST_RE = re.compile(
    rf"(?<!\d)(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+"
    rf"(?P<month_name>{EN_MONTH_PATTERN})(?:,?\s*(?P<year>20\d{{2}}))?",
    re.IGNORECASE,
)
TIME_RE = re.compile(
    r"(?<!\d)(?P<h1>[01]?\d|2[0-3])\s*:\s*(?P<m1>[0-5]\d)"
    r"(?:\s*(?:-|–|—|~|～|至|到)\s*(?P<h2>[01]?\d|2[0-3])\s*:\s*(?P<m2>[0-5]\d))?"
)

EN_TIME_RANGE_RE = re.compile(
    r"(?<!\d)(?P<h1>\d{1,2})(?::(?P<m1>[0-5]\d))?\s*"
    r"(?P<ap1>a\.?m\.?|p\.?m\.?)?\s*"
    r"(?:-|–|—|to|until)\s*"
    r"(?P<h2>\d{1,2})(?::(?P<m2>[0-5]\d))?\s*(?P<ap2>a\.?m\.?|p\.?m\.?)",
    re.IGNORECASE,
)
EN_TIME_SINGLE_RE = re.compile(
    r"(?<!\d)(?P<h>\d{1,2})(?::(?P<m>[0-5]\d))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)(?![A-Za-z])",
    re.IGNORECASE,
)
CN_PERIOD_COLON_RE = re.compile(
    r"(?P<period>上午|下午|晚上|傍晚|中午|凌晨|早上|晚)\s*"
    r"(?P<h>\d{1,2})\s*:\s*(?P<m>[0-5]\d)"
)
CN_TIME_POINT_RE = re.compile(
    r"(?P<period>上午|下午|晚上|傍晚|中午|凌晨|早上|晚)?\s*"
    r"(?<![\d.])(?P<h>\d{1,2})\s*[点時时]\s*"
    r"(?:(?P<m>\d{1,2})\s*分?|(?P<half>半))?"
)

DURATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:考试|笔试|测评|作答|答题)(?:时长|时间)(?:为|是)?\s*[:：]?\s*"
        r"(?P<n>\d{1,3}(?:\.\d+)?)\s*(?P<unit>分钟|min(?:ute)?s?|小时|h(?:our)?s?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:时长|duration)\s*(?:(?:为|是)\s*|[A-Za-z]+\s*)?[:：]?\s*"
        r"(?P<n>\d{1,3}(?:\.\d+)?)\s*(?P<unit>分钟|min(?:ute)?s?|小时|h(?:our)?s?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<n>\d{1,3}(?:\.\d+)?)\s*(?P<unit>分钟|min(?:ute)?s?|小时|h(?:our)?s?)"
        r"\s*(?:的)?(?:考试|笔试|测评|作答|答题)",
        re.IGNORECASE,
    ),
)

RELATIVE_DEADLINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:收到|收到本|收到此)?(?:封)?(?:邮件|通知)(?:之)?后\s*"
        r"(?P<n>\d{1,3})\s*(?P<unit>分钟|小时|天)(?:之)?内",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:请|须|需|务必)(?:在|于)?\s*(?P<n>\d{1,3})\s*(?P<unit>分钟|小时|天)(?:之)?内\s*(?:完成|作答|提交)",
        re.IGNORECASE,
    ),
    re.compile(
        r"within\s+(?P<n>\d{1,3})\s+(?P<unit>minutes?|hours?|days?)\s+(?:of\s+)?(?:receiving|this email|the email)",
        re.IGNORECASE,
    ),
)

EXAM_PREFIX_RULES: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"考试时间|笔试时间|测评时间|作答时间|测试时间", re.I), 8),
    (re.compile(r"考试日期|笔试日期|测评日期", re.I), 8),
    (re.compile(r"开始时间|开考时间|开放时间|作答开始|开始作答", re.I), 7),
    (re.compile(r"考试安排|笔试安排|测评安排|时间安排", re.I), 5),
    (re.compile(r"assessment\s+date|test\s+date|exam\s+date|start\s+time|opens?\s+at", re.I), 8),
    (re.compile(r"正式考试|在线考试|线上考试|在线笔试", re.I), 3),
)
DEADLINE_PREFIX_RULES: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"截止(?:时间|日期|至)?|报名截止|确认截止|作答截止|提交截止", re.I), 9),
    (re.compile(r"有效期至|失效时间|到期时间|链接有效期", re.I), 9),
    (re.compile(r"最晚(?:于|到)?|deadline|due\s+date|complete\s+by|no\s+later\s+than", re.I), 7),
    (re.compile(r"请于|请在|务必于|须于|需于", re.I), 1.5),
)
EXAM_SUFFIX_RULES: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"(?:参加|完成|进行|开始).{0,10}(?:笔试|测评|在线考试|考试)", re.I), 4.5),
    (re.compile(r"(?:笔试|测评|考试).{0,8}(?:开始|开考|进行)", re.I), 4),
    (re.compile(r"准时(?:参加|开始|登录|进入)", re.I), 4),
)
DEADLINE_SUFFIX_RULES: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"(?:之)?前\s*(?:完成|提交|确认|回复|答复|反馈|告知|接受|登录|进入|作答|关闭|截止)", re.I), 8),
    (re.compile(r"(?:之)?前(?=[，。；;\n]|$)", re.I), 6),
    (re.compile(r"(?:deadline|due|before|no later than)", re.I), 5),
)
WINDOW_CONNECTOR_RE = re.compile(r"^\s*(?:至|到|—|–|~|～|to)\s*$", re.I)


@dataclass(frozen=True)
class DateMention:
    start: int
    end: int
    year: int | None
    month: int
    day: int
    raw: str
    explicit_year: bool


@dataclass(frozen=True)
class TimeMention:
    start: int
    end: int
    hour: int
    minute: int
    end_hour: int | None
    end_minute: int | None
    raw: str


@dataclass
class TimingCandidate:
    kind: str
    start_dt: datetime
    end_dt: datetime | None
    time_known: bool
    date_mention: DateMention
    time_mention: TimeMention | None
    exam_score: float = 0.0
    deadline_score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    promoted_deadline: bool = False

    @property
    def span_start(self) -> int:
        return self.date_mention.start

    @property
    def span_end(self) -> int:
        if self.time_mention:
            return max(self.date_mention.end, self.time_mention.end)
        return self.date_mention.end


@dataclass(frozen=True)
class TimingExtraction:
    exam_start: str | None
    exam_end: str | None
    exam_time_known: bool
    deadline: str | None
    deadline_time_known: bool
    duration_minutes: int | None
    deadline_note: str | None = None


def normalize_timing_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = EN_TIME_RANGE_RE.sub(_replace_en_range, text)
    text = EN_TIME_SINGLE_RE.sub(_replace_en_single, text)
    text = CN_PERIOD_COLON_RE.sub(_replace_cn_period_colon, text)
    text = CN_TIME_POINT_RE.sub(_replace_cn_point, text)
    return text


def _period_hour(hour: int, marker: str | None) -> int:
    marker = (marker or "").lower().replace(".", "")
    if marker in {"pm", "p", "下午", "晚上", "傍晚", "晚"}:
        if marker in {"晚上", "晚"} and hour == 12:
            return 0
        return hour + 12 if hour < 12 else hour
    if marker == "中午":
        return hour + 12 if hour < 11 else hour
    if marker in {"am", "a"}:
        return 0 if hour == 12 else hour
    if marker == "凌晨":
        return 0 if hour == 12 else hour
    return hour


def _replace_en_range(match: re.Match[str]) -> str:
    ap = (match.group("ap2") or match.group("ap1") or "").lower().replace(".", "")
    h1 = _period_hour(int(match.group("h1")), ap)
    h2 = _period_hour(int(match.group("h2")), ap)
    m1 = match.group("m1") or "00"
    m2 = match.group("m2") or "00"
    return f"{h1:02d}:{m1}-{h2:02d}:{m2}"


def _replace_en_single(match: re.Match[str]) -> str:
    hour = _period_hour(int(match.group("h")), match.group("ap"))
    return f"{hour:02d}:{match.group('m') or '00'}"


def _replace_cn_period_colon(match: re.Match[str]) -> str:
    hour = _period_hour(int(match.group("h")), match.group("period"))
    return f"{hour:02d}:{match.group('m')}"


def _replace_cn_point(match: re.Match[str]) -> str:
    hour = int(match.group("h"))
    if hour > 24:
        return match.group(0)
    minute = 30 if match.group("half") else int(match.group("m") or 0)
    if minute > 59:
        return match.group(0)
    hour = _period_hour(hour, match.group("period"))
    if hour == 24:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _find_date_mentions(text: str) -> list[DateMention]:
    mentions: list[DateMention] = []
    for pattern in (CN_DATE_WITH_MONTH_RE, CN_NUMERIC_DATE_RE):
        for match in pattern.finditer(text):
            year = int(match.group("year")) if match.group("year") else None
            month = int(match.group("month"))
            day = int(match.group("day"))
            mentions.append(
                DateMention(
                    start=match.start(),
                    end=match.end(),
                    year=year,
                    month=month,
                    day=day,
                    raw=match.group(0),
                    explicit_year=year is not None,
                )
            )
    for pattern in (EN_MONTH_FIRST_RE, EN_DAY_FIRST_RE):
        for match in pattern.finditer(text):
            month = MONTH_NAMES.get(match.group("month_name").lower().rstrip("."))
            if not month:
                continue
            year = int(match.group("year")) if match.group("year") else None
            mentions.append(
                DateMention(
                    start=match.start(),
                    end=match.end(),
                    year=year,
                    month=month,
                    day=int(match.group("day")),
                    raw=match.group(0),
                    explicit_year=year is not None,
                )
            )

    mentions.sort(key=lambda item: (item.start, -(item.end - item.start), item.explicit_year))
    accepted: list[DateMention] = []
    last_end = -1
    for mention in mentions:
        if mention.start < last_end:
            continue
        if not _valid_month_day(mention.month, mention.day):
            continue
        accepted.append(mention)
        last_end = mention.end
    return accepted


def _valid_month_day(month: int, day: int) -> bool:
    try:
        date(2000 if month == 2 and day == 29 else 2026, month, day)
        return True
    except ValueError:
        return False


def _find_time_mentions(text: str) -> list[TimeMention]:
    mentions: list[TimeMention] = []
    for match in TIME_RE.finditer(text):
        start = time(int(match.group("h1")), int(match.group("m1")))
        end_hour = int(match.group("h2")) if match.group("h2") else None
        end_minute = int(match.group("m2")) if match.group("m2") else None
        end = time(end_hour, end_minute) if end_hour is not None and end_minute is not None else None
        if end and end < start:
            # "下午 2:30-4:30" leaves only the first half in 24-hour form.
            adjusted_hour = end.hour + 12 if end.hour < 12 else end.hour
            adjusted = time(adjusted_hour, end.minute)
            if adjusted > start and (adjusted.hour * 60 + adjusted.minute) - (start.hour * 60 + start.minute) <= 8 * 60:
                end = adjusted
                end_hour, end_minute = end.hour, end.minute
            else:
                end = None
                end_hour = end_minute = None
        mentions.append(
            TimeMention(
                start=match.start(),
                end=match.end(),
                hour=start.hour,
                minute=start.minute,
                end_hour=end.hour if end else None,
                end_minute=end.minute if end else None,
                raw=match.group(0),
            )
        )
    return mentions


def _infer_year(month: int, day: int, received_at: datetime, explicit_year: int | None) -> int | None:
    if explicit_year:
        return explicit_year
    local_received = to_local(received_at)
    try:
        candidate = date(local_received.year, month, day)
    except ValueError:
        return None
    if candidate < local_received.date() - timedelta(days=45):
        return local_received.year + 1
    return local_received.year


def _nearest_time(date_mention: DateMention, times: list[TimeMention], used: set[int]) -> int | None:
    best_index: int | None = None
    best_key: tuple[int, int] | None = None
    for index, time_mention in enumerate(times):
        if index in used:
            continue
        if time_mention.start >= date_mention.end:
            gap = time_mention.start - date_mention.end
            direction = 0
        else:
            gap = date_mention.start - time_mention.end
            direction = 1
        if gap > 60:
            continue
        key = (gap, direction)
        if best_key is None or key < best_key:
            best_key = key
            best_index = index
    return best_index


def _last_rule_score(
    prefix: str,
    suffix: str,
    prefix_rules: tuple[tuple[re.Pattern[str], float], ...],
    suffix_rules: tuple[tuple[re.Pattern[str], float], ...],
) -> float:
    best = 0.0
    for pattern, weight in prefix_rules:
        if pattern.search(prefix):
            best = max(best, weight)
    for pattern, weight in suffix_rules:
        if pattern.search(suffix):
            best = max(best, weight)
    return best


def _context_scores(
    text: str,
    candidate: TimingCandidate,
    subject_len: int,
) -> None:
    start = candidate.span_start
    end = candidate.span_end
    prefix = text[max(0, start - 65) : start]
    suffix = text[end : end + 45]

    exam_score = _last_rule_score(prefix, suffix, EXAM_PREFIX_RULES, EXAM_SUFFIX_RULES)
    deadline_score = _last_rule_score(prefix, suffix, DEADLINE_PREFIX_RULES, DEADLINE_SUFFIX_RULES)
    if start < subject_len and re.search(r"笔试|测评|考试|assessment|test|exam", text[:subject_len], re.I):
        exam_score += 3.5
        candidate.reasons.append("日期出现在笔试相关主题中")

    polite_before = bool(re.search(r"请(?:于|在)?|务必(?:于)?|须于|需于", prefix))
    before_marker = bool(re.search(r"(?:之)?前(?=\s*(?:完成|提交|确认|登录|进入|作答|关闭)|[，。；;\n])", suffix))
    if polite_before and before_marker:
        deadline_score += 4
        candidate.reasons.append("带有请于……前完成的截止语义")

    if deadline_score >= 5 and deadline_score >= exam_score + 0.5:
        candidate.kind = "deadline"
    elif exam_score >= 3:
        candidate.kind = "exam"
    else:
        candidate.kind = "unknown"

    candidate.exam_score = exam_score
    candidate.deadline_score = deadline_score


def extract_timings(text: str, received_at: datetime) -> TimingExtraction:
    prepared = normalize_timing_text(text)
    subject_len = prepared.find("\n")
    if subject_len < 0:
        subject_len = len(prepared)
    local_received = to_local(received_at)
    dates = _find_date_mentions(prepared)
    times = _find_time_mentions(prepared)

    raw_candidates: list[TimingCandidate] = []
    used_times: set[int] = set()
    for date_mention in dates:
        year = _infer_year(date_mention.month, date_mention.day, local_received, date_mention.year)
        if not year:
            continue
        time_index = _nearest_time(date_mention, times, used_times)
        time_mention = times[time_index] if time_index is not None else None
        if time_mention:
            used_times.add(time_index)  # type: ignore[arg-type]
        try:
            start_dt = datetime.combine(
                date(year, date_mention.month, date_mention.day),
                time(time_mention.hour, time_mention.minute) if time_mention else time(0, 0),
                tzinfo=LOCAL_TZ,
            )
        except ValueError:
            continue
        end_dt: datetime | None = None
        if time_mention and time_mention.end_hour is not None and time_mention.end_minute is not None:
            end_dt = datetime.combine(
                date(year, date_mention.month, date_mention.day),
                time(time_mention.end_hour, time_mention.end_minute),
                tzinfo=LOCAL_TZ,
            )
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
        candidate = TimingCandidate(
            kind="unknown",
            start_dt=start_dt,
            end_dt=end_dt,
            time_known=time_mention is not None,
            date_mention=date_mention,
            time_mention=time_mention,
        )
        _context_scores(prepared, candidate, subject_len)
        raw_candidates.append(candidate)

    # A date range such as "10月20日 10:00 至 10月22日 22:00" becomes a start
    # time plus a completion deadline.
    raw_candidates.sort(key=lambda item: item.span_start)
    for index, first in enumerate(raw_candidates):
        if first.kind == "deadline":
            continue
        for second in raw_candidates[index + 1 : index + 3]:
            if second.kind == "deadline" or second.start_dt <= first.start_dt:
                continue
            between = prepared[first.span_end : second.span_start]
            if WINDOW_CONNECTOR_RE.match(between):
                second.kind = "deadline"
                second.deadline_score = max(second.deadline_score, 8.0)
                second.promoted_deadline = True
                second.reasons.append("识别到考试时间窗口的结束时间")
                break

    exam_candidates = [item for item in raw_candidates if item.kind == "exam"]
    deadline_candidates = [item for item in raw_candidates if item.kind == "deadline"]

    def exam_rank(item: TimingCandidate) -> tuple[float, int, int, float]:
        is_future = 1 if item.start_dt.date() >= local_received.date() else 0
        return (item.exam_score, 1 if item.time_known else 0, is_future, -item.start_dt.timestamp())

    def deadline_rank(item: TimingCandidate) -> tuple[float, int, float]:
        is_future = 1 if item.start_dt.date() >= local_received.date() else 0
        return (item.deadline_score, is_future, -item.start_dt.timestamp())

    chosen_exam = max(exam_candidates, key=exam_rank) if exam_candidates else None
    chosen_deadline = max(deadline_candidates, key=deadline_rank) if deadline_candidates else None

    exam_start: str | None = None
    exam_end: str | None = None
    exam_time_known = False
    if chosen_exam:
        exam_start = chosen_exam.start_dt.isoformat(timespec="minutes")
        exam_time_known = chosen_exam.time_known
        if chosen_exam.end_dt:
            exam_end = chosen_exam.end_dt.isoformat(timespec="minutes")

    deadline: str | None = None
    deadline_time_known = False
    deadline_note: str | None = None
    if chosen_deadline:
        if chosen_deadline.time_known:
            deadline = chosen_deadline.start_dt.isoformat(timespec="minutes")
        else:
            deadline = datetime.combine(
                chosen_deadline.start_dt.date(), time(23, 59), tzinfo=LOCAL_TZ
            ).isoformat(timespec="minutes")
        deadline_time_known = chosen_deadline.time_known
    else:
        relative = _extract_relative_deadline(prepared, local_received)
        if relative:
            deadline, note = relative
            deadline_time_known = True
            deadline_note = note

    duration = _extract_duration(prepared)
    if chosen_exam and exam_start and exam_time_known and exam_end:
        duration = duration or _minutes_between(chosen_exam.start_dt, chosen_exam.end_dt)
    if duration and chosen_exam and exam_time_known:
        if not exam_end:
            exam_end = (chosen_exam.start_dt + timedelta(minutes=duration)).isoformat(timespec="minutes")
        elif chosen_exam.end_dt is None:
            exam_end = (chosen_exam.start_dt + timedelta(minutes=duration)).isoformat(timespec="minutes")

    return TimingExtraction(
        exam_start=exam_start,
        exam_end=exam_end,
        exam_time_known=exam_time_known,
        deadline=deadline,
        deadline_time_known=deadline_time_known,
        duration_minutes=duration,
        deadline_note=deadline_note,
    )


def _minutes_between(start: datetime, end: datetime | None) -> int | None:
    if not end:
        return None
    minutes = int((end - start).total_seconds() // 60)
    if 5 <= minutes <= 480:
        return minutes
    return None


def _extract_duration(text: str) -> int | None:
    for pattern in DURATION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        amount = float(match.group("n"))
        unit = match.group("unit").lower()
        if unit.startswith("小时") or unit.startswith("h"):
            minutes = int(amount * 60)
        else:
            minutes = int(amount)
        if 5 <= minutes <= 480:
            return minutes
    return None


def _extract_relative_deadline(
    text: str, received_at: datetime
) -> tuple[str, str] | None:
    for pattern in RELATIVE_DEADLINE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        amount = int(match.group("n"))
        unit = match.group("unit").lower()
        if unit.startswith("分钟") or unit.startswith("minute"):
            delta = timedelta(minutes=amount)
        elif unit.startswith("小时") or unit.startswith("hour"):
            delta = timedelta(hours=amount)
        else:
            delta = timedelta(days=amount)
        if delta > timedelta(days=60):
            continue
        deadline = received_at + delta
        note = f"邮件要求收到后 {amount} {match.group('unit')}内完成，截止时间按邮件收件时间推算。"
        return deadline.isoformat(timespec="minutes"), note
    return None
