from __future__ import annotations

from datetime import datetime, timezone

from app.mail.imap import MailAccount, MailboxSession, _parse_uid_search_response


class FakeSearchConnection:
    def __init__(self, payload: bytes, uidvalidity: str = "42") -> None:
        self.payload = payload
        self.uidvalidity = uidvalidity
        self.calls: list[tuple] = []

    def response(self, name: str):
        if name == "UIDVALIDITY":
            return ("UIDVALIDITY", [self.uidvalidity.encode()])
        return (None, [None])

    def uid(self, command: str, *args):
        self.calls.append((command, *args))
        return "OK", [self.payload]


def make_session(payload: bytes) -> tuple[MailboxSession, FakeSearchConnection]:
    session = object.__new__(MailboxSession)
    session.account = MailAccount(
        provider="qq",
        email="student@qq.com",
        username="student@qq.com",
        password="code",
        host="imap.qq.com",
        port=993,
    )
    conn = FakeSearchConnection(payload)
    session.conn = conn  # type: ignore[assignment]
    return session, conn


def test_parse_uid_search_response_handles_byte_tokens_and_multiple_chunks():
    assert _parse_uid_search_response([b"101 102", b"", "103 104"]) == [101, 102, 103, 104]
    assert _parse_uid_search_response([]) == []
    assert _parse_uid_search_response(None) == []


def test_initial_search_uses_unparenthesized_since_and_parses_bytes():
    session, conn = make_session(b"1889 1890 1891 1892 1893 1894 1895")
    result = session.search(
        since=datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc),
        limit=3,
    )
    assert conn.calls == [("search", None, 'SINCE "18-Sep-2026"')]
    assert result.uids == [1893, 1894, 1895]
    assert result.top_uid == 1895
    assert result.uidvalidity == "42"


def test_incremental_search_keeps_only_uids_after_last_uid():
    session, conn = make_session(b"99 100 101 102")
    result = session.search(
        since=datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc),
        last_uid=100,
        known_uidvalidity="42",
    )
    assert conn.calls == [("search", None, "UID 101:*")]
    assert result.uids == [101, 102]
    assert result.top_uid == 102
