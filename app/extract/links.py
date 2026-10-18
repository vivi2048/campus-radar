from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from ..mail.mime import EmailLink


@dataclass(frozen=True)
class PlatformRule:
    domain: str
    name: str
    exam_platform: bool = True
    interview_platform: bool = False


PLATFORM_RULES: tuple[PlatformRule, ...] = (
    PlatformRule("nowcoder.com", "牛客网"),
    PlatformRule("acmcoder.com", "赛码网"),
    PlatformRule("beisen.com", "北森"),
    PlatformRule("italent.cn", "北森"),
    PlatformRule("dayee.com", "智鼎测评"),
    PlatformRule("ceping.com", "北森测评"),
    PlatformRule("shl.com", "SHL"),
    PlatformRule("hackerrank.com", "HackerRank"),
    PlatformRule("hackerearth.com", "HackerEarth"),
    PlatformRule("codility.com", "Codility"),
    PlatformRule("codesignal.com", "CodeSignal"),
    PlatformRule("leetcode.cn", "LeetCode"),
    PlatformRule("leetcode.com", "LeetCode"),
    PlatformRule("hirevue.com", "HireVue", exam_platform=True, interview_platform=True),
    PlatformRule("testgorilla.com", "TestGorilla"),
    PlatformRule("coderbyte.com", "Coderbyte"),
    PlatformRule("mokahr.com", "Moka", exam_platform=False),
    PlatformRule("myworkdayjobs.com", "Workday", exam_platform=False),
    PlatformRule("workday.com", "Workday", exam_platform=False),
    PlatformRule("greenhouse.io", "Greenhouse", exam_platform=False),
    PlatformRule("taleo.net", "Oracle Taleo", exam_platform=False),
    PlatformRule("successfactors.com", "SAP SuccessFactors", exam_platform=False),
    PlatformRule("zoom.us", "Zoom", exam_platform=False, interview_platform=True),
    PlatformRule("tencent.com", "腾讯会议", exam_platform=False, interview_platform=True),
    PlatformRule("voovmeeting.com", "腾讯会议", exam_platform=False, interview_platform=True),
    PlatformRule("feishu.cn", "飞书会议", exam_platform=False, interview_platform=True),
    PlatformRule("larkoffice.com", "飞书会议", exam_platform=False, interview_platform=True),
    PlatformRule("larksuite.com", "飞书会议", exam_platform=False, interview_platform=True),
    PlatformRule("dingtalk.com", "钉钉会议", exam_platform=False, interview_platform=True),
    PlatformRule("teams.microsoft.com", "Microsoft Teams", exam_platform=False, interview_platform=True),
    PlatformRule("teams.live.com", "Microsoft Teams", exam_platform=False, interview_platform=True),
    PlatformRule("meet.google.com", "Google Meet", exam_platform=False, interview_platform=True),
    PlatformRule("webex.com", "Webex", exam_platform=False, interview_platform=True),
    PlatformRule("gotomeeting.com", "GoTo Meeting", exam_platform=False, interview_platform=True),
    PlatformRule("bluejeans.com", "BlueJeans", exam_platform=False, interview_platform=True),
    PlatformRule("meeting.huaweicloud.com", "华为云会议", exam_platform=False, interview_platform=True),
    PlatformRule("welink.huaweicloud.com", "WeLink", exam_platform=False, interview_platform=True),
)


TRACKING_HOST_PREFIXES = ("click.", "click-", "track.", "trk.")
TRACKING_HOST_MARKERS = (
    "sendgrid",
    "mailchimp",
    "list-manage",
    "mandrillapp",
    "hubspotlinks",
    "exacttarget",
    "mktomail",
    "clickdimensions",
    "customeriomail",
    "campaign-archive",
)
TRACKING_PATH_MARKERS = (
    "unsubscribe",
    "opt-out",
    "optout",
    "preference",
    "view-in-browser",
    "viewinbrowser",
    "view-online",
    "privacy",
    "terms",
    "social",
    "facebook.com",
    "twitter.com",
    "linkedin.com",
    "instagram.com",
    "weibo.com",
)
EXAM_URL_CUES = re.compile(
    r"(?:^|[/._-])(assessment|exam|test|tests|oa|coding|challenge|invite|start)(?:[/._?&=-]|$)",
    re.IGNORECASE,
)
EXAM_ANCHOR_CUES = re.compile(
    r"(?:开始|进入|参加|前往|打开|点击|登录).{0,8}(?:考试|测评|笔试|作答)"
    r"|(?:考试|测评|笔试|作答).{0,8}(?:链接|入口|系统|平台|专区)"
    r"|(?:start|begin|enter|take).{0,8}(?:test|exam|assessment)",
    re.IGNORECASE,
)
INTERVIEW_URL_CUES = re.compile(
    r"(?:^|[/._-])(interview|meeting|meet|join|video|conference|call|schedule)(?:[/._?&=-]|$)",
    re.IGNORECASE,
)
INTERVIEW_ANCHOR_CUES = re.compile(
    r"(?:面试|面谈|视频|电话).{0,10}(?:链接|入口|会议|房间|会议室)"
    r"|(?:接受|确认|预约|参加).{0,4}(?:面试|面谈)"
    r"|(?:加入|进入|点击|打开|签到).{0,10}(?:会议|面试|会议室)"
    r"|(?:join|enter|open|accept).{0,12}(?:meeting|interview|room)"
    r"|(?:meeting|interview)\s+link",
    re.IGNORECASE,
)
INTERVIEW_HOST_CUES = re.compile(
    r"(?:^|\.)(?:meeting|meet|interview|video|conference|call|vc)\.",
    re.IGNORECASE,
)
GENERIC_TARGET_CUES = re.compile(r"点击|进入|前往|打开|链接|入口|click|start|enter", re.IGNORECASE)
BAD_URL_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".ico")
REDIRECT_KEYS = ("url", "target", "u", "redirect", "redirect_url", "destination")


@dataclass(frozen=True)
class SelectedLink:
    url: str
    platform: str | None
    score: int


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _unwrap_redirect(url: str) -> str:
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in REDIRECT_KEYS:
            for candidate in query.get(key, []):
                if candidate.lower().startswith(("http://", "https://")):
                    return candidate
    except Exception:
        pass
    return url


def normalize_url(url: str) -> str:
    url = html.unescape(url or "").strip()
    return _unwrap_redirect(url).strip()


def _platform_rule(url: str) -> PlatformRule | None:
    host = _host(url)
    if not host:
        return None
    for rule in PLATFORM_RULES:
        if host == rule.domain or host.endswith("." + rule.domain):
            return rule
    return None


def is_tracking_link(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    host = (parsed.hostname or "").lower()
    lower = url.lower()
    if not parsed.scheme.startswith("http") or not host:
        return True
    if lower.split("?")[0].endswith(BAD_URL_EXTENSIONS):
        return True
    if any(host.startswith(prefix) for prefix in TRACKING_HOST_PREFIXES):
        return True
    if any(marker in host for marker in TRACKING_HOST_MARKERS):
        return True
    path_and_query = (parsed.path + "?" + parsed.query).lower()
    if any(marker in path_and_query for marker in TRACKING_PATH_MARKERS):
        return True
    return False


def score_assessment_link(link: EmailLink) -> int:
    url = normalize_url(link.url)
    if is_tracking_link(url):
        return -20
    rule = _platform_rule(url)
    score = 0
    if rule:
        score += 8 if rule.exam_platform else 3
    try:
        path_query = urlparse(url).path + "?" + urlparse(url).query
    except ValueError:
        path_query = ""
    if EXAM_URL_CUES.search(path_query):
        score += 3
    if link.text and EXAM_ANCHOR_CUES.search(link.text):
        score += 4
    elif link.text and GENERIC_TARGET_CUES.search(link.text):
        score += 1
    lower = url.lower()
    if any(token in lower for token in ("career", "jobs", "apply", "application")):
        score -= 2
    return score


def select_exam_link(links: list[EmailLink]) -> SelectedLink | None:
    scored: list[SelectedLink] = []
    seen: set[str] = set()
    for link in links:
        url = normalize_url(link.url)
        if not url or url in seen:
            continue
        seen.add(url)
        score = score_assessment_link(EmailLink(url=url, text=link.text))
        if score < 3:
            continue
        rule = _platform_rule(url)
        scored.append(SelectedLink(url=url, platform=rule.name if rule else None, score=score))
    if not scored:
        return None
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[0]


def has_exam_link(links: list[EmailLink]) -> bool:
    return any(score_assessment_link(link) >= 5 for link in links)


def score_interview_link(link: EmailLink) -> int:
    url = normalize_url(link.url)
    if is_tracking_link(url):
        return -20
    rule = _platform_rule(url)
    score = 0
    if rule:
        if rule.interview_platform:
            score += 8
        elif rule.exam_platform:
            score += 3
    try:
        parsed = urlparse(url)
    except ValueError:
        parsed = None
    path_query = (parsed.path + "?" + parsed.query) if parsed else ""
    host = (parsed.hostname or "") if parsed else ""
    if INTERVIEW_URL_CUES.search(path_query):
        score += 3
    if INTERVIEW_HOST_CUES.search(host):
        score += 3
    if link.text and INTERVIEW_ANCHOR_CUES.search(link.text):
        score += 4
    elif link.text and GENERIC_TARGET_CUES.search(link.text):
        score += 1
    lower = url.lower()
    if any(token in lower for token in ("download", "support", "faq", "help-center")):
        score -= 6
    if any(token in lower for token in ("career", "jobs", "apply", "application", "privacy")):
        score -= 2
    return score


def select_interview_link(links: list[EmailLink]) -> SelectedLink | None:
    scored: list[SelectedLink] = []
    seen: set[str] = set()
    for link in links:
        url = normalize_url(link.url)
        if not url or url in seen:
            continue
        seen.add(url)
        score = score_interview_link(EmailLink(url=url, text=link.text))
        if score < 3:
            continue
        rule = _platform_rule(url)
        scored.append(SelectedLink(url=url, platform=rule.name if rule else None, score=score))
    if not scored:
        return None
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[0]


def has_interview_link(links: list[EmailLink]) -> bool:
    return any(score_interview_link(link) >= 5 for link in links)


def detect_platform(
    text: str,
    links: list[EmailLink],
    selected: SelectedLink | None = None,
    *,
    kind: str = "exam",
) -> str | None:
    if selected:
        if selected.platform:
            return selected.platform
        rule = _platform_rule(selected.url)
        if rule:
            return rule.name
    for link in links:
        rule = _platform_rule(normalize_url(link.url))
        if not rule:
            continue
        if kind == "interview" and rule.interview_platform:
            return rule.name
        if kind == "exam" and rule.exam_platform:
            return rule.name
    body = text or ""
    if kind == "interview":
        interview_checks = (
            (r"腾讯会议|Tencent\s+Meeting|VooV\s+Meeting", "腾讯会议"),
            (r"飞书(?:会议)?|Feishu|Lark\s+Meeting", "飞书会议"),
            (r"钉钉(?:会议)?|DingTalk", "钉钉会议"),
            (r"\bZoom\b", "Zoom"),
            (r"Microsoft\s+Teams|\bTeams\b", "Microsoft Teams"),
            (r"Google\s+Meet", "Google Meet"),
            (r"\bWebex\b", "Webex"),
            (r"牛客(?:面试|网)?", "牛客网"),
            (r"\bHireVue\b", "HireVue"),
        )
        for pattern, name in interview_checks:
            if re.search(pattern, body, re.IGNORECASE):
                return name
        return None
    checks = (
        (r"牛客(?:网)?", "牛客网"),
        (r"赛码(?:网)?", "赛码网"),
        (r"北森", "北森"),
        (r"智鼎", "智鼎测评"),
        (r"\bSHL\b", "SHL"),
        (r"\bHackerRank\b", "HackerRank"),
        (r"\bHackerEarth\b", "HackerEarth"),
        (r"\bCodility\b", "Codility"),
        (r"\bCodeSignal\b", "CodeSignal"),
        (r"\bLeetCode\b", "LeetCode"),
        (r"\bHireVue\b", "HireVue"),
        (r"\bTestGorilla\b", "TestGorilla"),
        (r"\bCoderbyte\b", "Coderbyte"),
        (r"\bMoka\b", "Moka"),
    )
    for pattern, name in checks:
        if re.search(pattern, body, re.IGNORECASE):
            return name
    return None
