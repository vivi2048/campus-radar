from __future__ import annotations

import imaplib
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..timeutil import imap_date

imaplib.Commands["ID"] = ("AUTH", "SELECTED")


class MailboxError(Exception):
    """A safe, user-facing mailbox connection error."""


@dataclass(frozen=True)
class MailAccount:
    provider: str
    email: str
    username: str
    password: str
    host: str
    port: int
    folder: str = "INBOX"


@dataclass(frozen=True)
class SearchResult:
    uids: list[int]
    uidvalidity: str | None
    top_uid: int


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "") + '"'


def _parse_uid_search_response(data: list[object] | tuple[object, ...] | None) -> list[int]:
    """Parse SEARCH responses, whose UID tokens arrive as bytes from imaplib."""
    found: set[int] = set()
    for chunk in data or []:
        if isinstance(chunk, bytes):
            tokens = chunk.split()
        elif isinstance(chunk, str):
            tokens = chunk.split()
        else:
            continue
        for token in tokens:
            try:
                found.add(int(token))
            except (TypeError, ValueError):
                continue
    return sorted(found)


def _humanize_error(exc: Exception, provider: str) -> str:
    raw = str(exc)
    lowered = raw.lower()

    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in lowered:
        return "连接邮箱超时，请检查网络，或稍后重试。"
    if isinstance(exc, socket.gaierror) or "name or service not known" in lowered:
        return "找不到 IMAP 服务器，请检查服务器地址和网络。"
    if "certificate" in lowered or isinstance(exc, ssl.SSLError):
        return "IMAP 服务器的 TLS 证书验证失败，请确认服务器地址是否正确。"
    if any(
        cue in lowered
        for cue in (
            "authenticationfailed",
            "authentication failed",
            "invalid credentials",
            "login fail",
            "login failed",
            "auth failed",
            "unsafe login",
        )
    ):
        if provider in {"qq"}:
            return "QQ 邮箱认证失败。请确认已开启 IMAP 服务，并填写授权码而不是 QQ 密码。"
        if provider in {"163", "126"}:
            return "网易邮箱认证失败。请确认已开启 IMAP 服务并使用客户端授权码；首次使用可能需要在网页端完成短信验证。"
        if provider == "gmail":
            return "Gmail 认证失败。请确认已开启两步验证，并使用 Google 应用专用密码。"
        return "邮箱认证失败，请检查账号、密码或授权码，并确认邮箱已开启 IMAP。"
    if "unsafe login" in lowered:
        return "邮箱服务商拒绝了客户端登录，请完成网页端的短信验证或安全验证后重试。"
    if "select" in lowered or "mailbox" in lowered or "does not exist" in lowered:
        return "找不到指定的邮件文件夹，请检查文件夹名称（默认是 INBOX）。"
    if "too many" in lowered or "rate" in lowered:
        return "邮箱服务器限制了登录频率，请稍后再试。"
    if isinstance(exc, imaplib.IMAP4.error):
        cleaned = re.sub(r"\s+", " ", raw).strip()
        cleaned = cleaned[:240]
        return f"邮箱服务器返回错误：{cleaned}" if cleaned else "邮箱服务器返回未知错误。"
    return "无法连接邮箱，请检查网络和 IMAP 设置后重试。"


class MailboxSession:
    def __init__(self, account: MailAccount, timeout: int = 30) -> None:
        self.account = account
        self.timeout = timeout
        self.conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "MailboxSession":
        account = self.account
        try:
            context = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(account.host, account.port, ssl_context=context, timeout=self.timeout)
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, account.provider)) from exc

        try:
            conn.login(account.username, account.password)
        except Exception as exc:
            try:
                conn.logout()
            except Exception:
                pass
            raise MailboxError(_humanize_error(exc, account.provider)) from exc

        if account.provider in {"163", "126"}:
            self._identify(conn)

        self.conn = conn
        try:
            typ, _ = conn.select(_quote(account.folder or "INBOX"), readonly=True)
            if typ != "OK":
                raise MailboxError("找不到指定的邮件文件夹，请检查文件夹名称（默认是 INBOX）。")
        except MailboxError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise MailboxError(_humanize_error(exc, account.provider)) from exc
        return self

    def _identify(self, conn: imaplib.IMAP4_SSL) -> None:
        # NetEase requires an IMAP ID command before selecting the mailbox.
        try:
            payload = '("name" "exam-radar" "version" "1.0" "vendor" "local")'
            typ, data = conn._simple_command("ID", payload)
            conn._untagged_response(typ, data, "ID")
        except Exception:
            pass

    def uidvalidity(self) -> str | None:
        if not self.conn:
            return None
        try:
            typ, data = self.conn.response("UIDVALIDITY")
            if typ == "UIDVALIDITY" and data:
                value = data[0]
                return value.decode("ascii", "ignore") if isinstance(value, bytes) else str(value)
        except Exception:
            pass
        return None

    def search(
        self,
        *,
        since: datetime,
        last_uid: int = 0,
        known_uidvalidity: str | None = None,
        limit: int = 300,
    ) -> SearchResult:
        if not self.conn:
            raise MailboxError("邮箱连接尚未建立。")
        uidvalidity = self.uidvalidity()
        incremental = bool(
            last_uid > 0
            and uidvalidity
            and known_uidvalidity
            and uidvalidity == str(known_uidvalidity)
        )
        try:
            if incremental:
                typ, data = self.conn.uid("search", None, f"UID {last_uid + 1}:*")
            else:
                # Some IMAP servers (notably QQ) ignore the date criterion when
                # the search expression is wrapped in an extra pair of parens.
                typ, data = self.conn.uid("search", None, f'SINCE "{imap_date(since)}"')
            if typ != "OK":
                raise MailboxError("邮箱服务器拒绝了邮件搜索请求。")
            uids = _parse_uid_search_response(data)
            if incremental:
                uids = [uid for uid in uids if uid > last_uid]
            top_uid = max(uids, default=last_uid)
            if limit > 0 and len(uids) > limit:
                uids = uids[-limit:]
                top_uid = max(uids)
            return SearchResult(uids=uids, uidvalidity=uidvalidity, top_uid=top_uid)
        except MailboxError:
            raise
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, self.account.provider)) from exc

    def fetch_raw(self, uid: int) -> bytes:
        if not self.conn:
            raise MailboxError("邮箱连接尚未建立。")
        try:
            typ, data = self.conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            if typ != "OK" or not data:
                raise MailboxError("读取邮件内容失败，邮件可能已被移动或删除。")
            for item in data:
                if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
                    return bytes(item[1])
            raise MailboxError("邮箱服务器没有返回可读取的邮件内容。")
        except MailboxError:
            raise
        except Exception as exc:
            raise MailboxError(_humanize_error(exc, self.account.provider)) from exc

    def close(self) -> None:
        conn = self.conn
        self.conn = None
        if not conn:
            return
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def verify_account(account: MailAccount) -> None:
    with MailboxSession(account):
        pass
