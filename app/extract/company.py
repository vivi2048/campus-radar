from __future__ import annotations

import re
import unicodedata

_BRACKETED_RE = re.compile(r"[（(【\[][^（）()【】\[\]]{0,60}[）)】\]]")
_UNCLOSED_BRACKET_RE = re.compile(r"[（(【\[][^）)】\]]*$")
_LEADING_NOISE_RE = re.compile(
    r"^(?:欢迎参加|诚邀您参加|邀请您参加|来自|关于)\s*"
)
_TRAILING_INVITE_RE = re.compile(
    r"\s*(?:诚邀|邀请|邀|欢迎)(?:您|你)?(?:参加|加入|参与|莅临)?.*$"
)
_EVENT_NOISE_RE = re.compile(
    r"\s*(?:在线|线上|远程|现场)?(?:笔试|测评|面试|考试|招聘|校招|空宣|宣讲会).*$",
    re.IGNORECASE,
)
_LEGAL_SUFFIX_RE = re.compile(
    r"\s*(?:股份有限公司|有限责任公司|有限公司|股份公司|公司"
    r"|Corporation|Corp\.?|Inc\.?|Ltd\.?|LLC)\s*$",
    re.IGNORECASE,
)
_GENERIC_RE = re.compile(
    r"^(?:我司|贵司|公司|招聘|校招|hr|人力资源部?)$",
    re.IGNORECASE,
)

_ALIASES = {
    "中国第一汽车": "中国一汽",
    "中国第一汽车集团": "中国一汽",
    "一汽集团": "中国一汽",
    "东风汽车集团": "东风汽车",
    "宁德时代新能源科技": "宁德时代",
    "中国联通集团": "中国联通",
    "中国移动通信集团": "中国移动",
    "北京中软融鑫计算机系统工程": "中软融鑫",
    "南京中科创达软件科技": "中科创达",
    "中科创达软件科技": "中科创达",
    "杭州迪普科技": "迪普科技",
    "新华三技术": "新华三",
    "CVTE视源股份": "CVTE",
    "TCL实业": "TCL",
}
_PREFIX_ALIASES = (
    ("中国电信", "中国电信"),
    ("中国联通", "中国联通"),
    ("中国移动", "中国移动"),
)


def canonicalize_company(value: str) -> str:
    """Reduce a legal entity or signature line to a stable display name."""
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"https?://\S+", " ", text)

    previous = None
    while previous != text:
        previous = text
        text = _BRACKETED_RE.sub(" ", text)
    text = _UNCLOSED_BRACKET_RE.sub(" ", text)

    text = _LEADING_NOISE_RE.sub("", text)
    text = _TRAILING_INVITE_RE.sub("", text)
    text = _EVENT_NOISE_RE.sub("", text)
    text = re.sub(r"\s*[|｜]\s*", " / ", text)
    text = re.sub(r"[ \t]+", " ", text).strip(" \t\r\n·,，.。:：;；-—_")
    if not text:
        return ""

    for _ in range(4):
        cleaned = _LEGAL_SUFFIX_RE.sub("", text).strip()
        if cleaned == text:
            break
        text = cleaned

    key = re.sub(r"\s+", "", text)
    text = _ALIASES.get(key, text)
    for prefix, canonical in _PREFIX_ALIASES:
        if text.startswith(prefix):
            text = canonical
            break

    text = text.strip(" \t\r\n·,，.。:：;；-—_")
    if _GENERIC_RE.fullmatch(text):
        return ""
    return text[:100]
