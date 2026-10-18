from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from email.parser import BytesParser
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from ..timeutil import LOCAL_TZ


URL_RE = re.compile(r"https?://[^\s<>\"'\u3000]+", re.IGNORECASE)
TRAILING_URL_CHARS = "。，、；;,.!?)）]】}>'\""


@dataclass(frozen=True)
class EmailLink:
    url: str
    text: str = ""


@dataclass
class ParsedEmail:
    subject: str
    sender_name: str
    sender_email: str
    received_at: datetime
    body_text: str
    html_text: str
    links: list[EmailLink] = field(default_factory=list)
    message_id: str = ""

    @property
    def from_line(self) -> str:
        if self.sender_name and self.sender_email:
            return f"{self.sender_name} <{self.sender_email}>"
        return self.sender_name or self.sender_email


def _decode_bytes(payload: bytes, declared: str | None = None) -> str:
    encodings: list[str] = []
    normalized = (declared or "").lower().strip()
    if normalized and normalized not in {"unknown-8bit", "x-unknown", "us-ascii", "ascii", "iso-8859-1", "latin-1"}:
        encodings.append(normalized)
    if normalized in {"us-ascii", "ascii", "iso-8859-1", "latin-1"}:
        encodings.append("utf-8")
    encodings.extend(["utf-8", "gb18030"])
    if normalized:
        encodings.append(normalized)
    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return payload.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", errors="replace")


def _decode_header(value: Any) -> str:
    if value is None:
        return ""
    try:
        chunks = decode_header(str(value))
    except Exception:
        return str(value)
    output: list[str] = []
    for chunk, charset in chunks:
        if isinstance(chunk, bytes):
            output.append(_decode_bytes(chunk, charset))
        else:
            output.append(chunk)
    return "".join(output).strip()


class _HTMLContentExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "head", "title", "noscript", "svg"}
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "tr",
        "li",
        "ul",
        "ol",
        "table",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
    }
    CELL_TAGS = {"td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[EmailLink] = []
        self._skip_depth = 0
        self._anchors: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value:
                    href = value.strip()
                    break
            self._anchors.append({"href": href, "text": []})
        if tag == "br":
            self.parts.append("\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in self.CELL_TAGS:
            self.parts.append("\t")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br" and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._anchors:
            anchor = self._anchors.pop()
            self._register_link(anchor.get("href", ""), "".join(anchor.get("text", [])))
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in self.CELL_TAGS:
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.parts.append(data)
        if self._anchors:
            self._anchors[-1]["text"].append(data)

    def _register_link(self, href: str, text: str) -> None:
        href = href.strip()
        if not href:
            return
        clean_text = re.sub(r"\s+", " ", text).strip()
        self.links.append(EmailLink(url=href, text=clean_text))

    def result(self) -> tuple[str, list[EmailLink]]:
        text = "".join(self.parts)
        return text, self.links


def _clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("\u200b", "")
    lines = []
    for line in value.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text_and_links(html: str) -> tuple[str, list[EmailLink]]:
    parser = _HTMLContentExtractor()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    text, links = parser.result()
    return _clean_text(text), links


def _clean_url(url: str) -> str:
    url = url.strip()
    while url and url[-1] in TRAILING_URL_CHARS:
        if url[-1] == ")" and url.count("(") >= url.count(")"):
            break
        url = url[:-1]
    return url


def extract_plain_links(text: str) -> list[EmailLink]:
    links: list[EmailLink] = []
    for match in URL_RE.finditer(text or ""):
        url = _clean_url(match.group(0))
        if url:
            links.append(EmailLink(url=url))
    return links


def parse_raw_email(raw: bytes, fallback_received_at: datetime | None = None) -> ParsedEmail:
    message = BytesParser(policy=default_policy).parsebytes(raw)
    subject = _decode_header(message.get("Subject")).replace("\r", " ").replace("\n", " ").strip()[:500]
    if not subject:
        subject = "（无主题）"

    raw_from = _decode_header(message.get("From"))
    sender_name, sender_email = parseaddr(raw_from)
    sender_name = re.sub(r"\s+", " ", sender_name).strip()[:160]
    sender_email = sender_email.strip()[:254]

    received_at = fallback_received_at or datetime.now(timezone.utc)
    if message.get("Date"):
        try:
            parsed_date = parsedate_to_datetime(str(message.get("Date")))
            if parsed_date is not None:
                received_at = parsed_date if parsed_date.tzinfo else parsed_date.replace(tzinfo=LOCAL_TZ)
        except (TypeError, ValueError, OverflowError):
            pass
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    received_at = received_at.astimezone(timezone.utc)

    plain_parts: list[str] = []
    html_parts: list[str] = []
    links: list[EmailLink] = []

    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type().lower()
        if content_type not in {"text/plain", "text/html"}:
            continue
        if (part.get_content_disposition() or "").lower() == "attachment":
            continue
        if part.get_filename():
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)):
            continue
        text = _decode_bytes(bytes(payload), part.get_content_charset())
        if content_type == "text/html":
            html_text, html_links = html_to_text_and_links(text)
            if html_text:
                html_parts.append(html_text)
            links.extend(html_links)
        else:
            cleaned = _clean_text(text)
            if cleaned:
                plain_parts.append(cleaned)
                links.extend(extract_plain_links(cleaned))

    plain_text = _clean_text("\n\n".join(plain_parts))
    html_text = _clean_text("\n\n".join(html_parts))
    if plain_text and len(plain_text) >= 60:
        body_text = plain_text
    elif html_text:
        body_text = html_text
    else:
        body_text = plain_text

    deduped: dict[str, EmailLink] = {}
    for link in links:
        url = _clean_url(link.url)
        if not url.lower().startswith(("http://", "https://")):
            continue
        existing = deduped.get(url)
        if existing is None or (not existing.text and link.text):
            deduped[url] = EmailLink(url=url, text=link.text.strip()[:300])
    body_text = body_text[:100_000]
    html_text = html_text[:100_000]

    return ParsedEmail(
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        received_at=received_at,
        body_text=body_text,
        html_text=html_text,
        links=list(deduped.values()),
        message_id=str(message.get("Message-ID", "")).strip()[:998],
    )


def make_message_key(parsed: ParsedEmail, raw: bytes) -> str:
    if parsed.message_id:
        seed = parsed.message_id
    else:
        seed = "\x1f".join(
            [
                parsed.subject,
                parsed.from_line,
                parsed.received_at.isoformat(),
                hashlib.sha256(raw[:4096]).hexdigest(),
            ]
        )
    return hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:48]
