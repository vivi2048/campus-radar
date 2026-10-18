from __future__ import annotations

import logging
from pathlib import Path

import pytest

import app.services.accounts as accounts_service
from app.db import Database
from app.mail.imap import SearchResult
from app.security import SecretBox
from app.services.accounts import create_account
from app.services.sync import SyncService


FIXTURES = Path(__file__).parent / "fixtures"


class FakeSession:
    def __init__(self, messages: dict[int, bytes]) -> None:
        self.messages = messages
        self.last_search: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def search(self, **kwargs) -> SearchResult:
        self.last_search = kwargs
        uids = sorted(self.messages)
        return SearchResult(uids=uids, uidvalidity="42", top_uid=max(uids, default=0))

    def fetch_raw(self, uid: int) -> bytes:
        return self.messages[uid]


@pytest.fixture()
def sync_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    db = Database(tmp_path / "sync.db")
    db.init()
    vault = SecretBox(tmp_path / ".secret.key")
    account = create_account(
        db,
        vault,
        {
            "provider": "custom",
            "email": "student@school.edu.cn",
            "username": "student@school.edu.cn",
            "password": "mail-code",
            "imap_host": "imap.school.edu.cn",
            "imap_port": 993,
            "sync_days": 30,
            "auto_sync": False,
        },
    )
    messages = {
        1: (FIXTURES / "xingye_nowcoder.eml").read_bytes(),
        2: (FIXTURES / "xingye_reminder.eml").read_bytes(),
        3: (FIXTURES / "interview_invite.eml").read_bytes(),
        4: (FIXTURES / "offline_exam.eml").read_bytes(),
    }
    logger = logging.getLogger("exam-radar-test-sync")
    service = SyncService(
        db,
        vault,
        logger,
        session_factory=lambda account: FakeSession(messages),
    )
    return db, vault, account, service, messages


def test_sync_creates_one_event_and_merges_reminder(sync_setup):
    db, _, account, service, _ = sync_setup
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["scanned"] == 4
    assert result.counts["matched"] == 3
    assert result.counts["created"] == 2
    assert result.counts["merged"] == 1
    assert result.counts["skipped"] == 1

    events = db.fetch_all("SELECT * FROM events ORDER BY id")
    assert len(events) == 2
    xingye = next(event for event in events if event["company"] == "星野科技")
    assert xingye["role"] == "后端开发工程师"
    assert xingye["source_count"] == 2
    assert xingye["exam_start"] == "2026-10-22T19:00+08:00"
    assert xingye["access_code"] == "XINGYE2026"
    assert xingye["needs_review"] == 0

    account_row = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account["id"],))
    assert account_row["last_sync_status"] == "ok"
    assert account_row["last_uid"] == 4
    assert account_row["uidvalidity"] == "42"

    outcomes = {row["message_key"]: row["outcome"] for row in db.fetch_all("SELECT * FROM seen_messages")}
    assert sorted(outcomes.values()) == ["created", "created", "merged", "not_exam"]


def test_sync_is_idempotent(sync_setup):
    db, _, account, service, _ = sync_setup
    first = service.sync_account(account["id"])
    assert first.success
    second = service.sync_account(account["id"])
    assert second.success
    assert second.counts["created"] == 0
    assert second.counts["merged"] == 0
    count = db.fetch_one("SELECT COUNT(*) AS count FROM events")
    assert count["count"] == 2


def test_sync_marks_error_when_credentials_cannot_decrypt(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    db = Database(tmp_path / "broken.db")
    db.init()
    vault = SecretBox(tmp_path / ".secret.key")
    account = create_account(
        db,
        vault,
        {
            "provider": "custom",
            "email": "student@school.edu.cn",
            "username": "student@school.edu.cn",
            "password": "mail-code",
            "imap_host": "imap.school.edu.cn",
        },
    )
    db.execute("UPDATE accounts SET password_enc = 'not-a-valid-token' WHERE id = ?", (account["id"],))
    service = SyncService(
        db,
        vault,
        logging.getLogger("exam-radar-test-sync-error"),
        session_factory=lambda account: FakeSession({}),
    )
    result = service.sync_account(account["id"])
    assert result.success is False
    assert "重新输入授权码" in (result.error or "")
    row = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account["id"],))
    assert row["last_sync_status"] == "error"


def test_reschedule_email_updates_existing_event(sync_setup):
    db, _, account, service, _ = sync_setup
    assert service.sync_account(account["id"]).success
    reschedule_session = FakeSession(
        {5: (FIXTURES / "xingye_reschedule.eml").read_bytes()}
    )
    reschedule_service = SyncService(
        db,
        service.vault,
        logging.getLogger("exam-radar-test-reschedule"),
        session_factory=lambda account: reschedule_session,
    )
    result = reschedule_service.sync_account(account["id"])
    assert result.success
    assert result.counts["merged"] == 1
    assert result.counts["created"] == 0
    xingye = db.fetch_one("SELECT * FROM events WHERE company = '星野科技'")
    assert xingye["exam_start"] == "2026-10-23T19:00+08:00"
    assert xingye["exam_end"] == "2026-10-23T21:00+08:00"
    assert xingye["source_count"] == 3
    assert db.fetch_one("SELECT COUNT(*) AS count FROM events")["count"] == 2


def test_clearing_exam_start_clears_end(client):
    created = client.post(
        "/api/events",
        json={
            "company": "时间测试公司",
            "exam_start": "2026-11-02T10:00",
            "exam_end": "2026-11-02T12:00",
        },
    ).json()
    updated = client.patch(
        f"/api/events/{created['id']}",
        json={"exam_start": None, "exam_end": None},
    )
    assert updated.status_code == 200
    assert updated.json()["exam_start"] is None
    assert updated.json()["exam_end"] is None
    invalid = client.patch(
        f"/api/events/{created['id']}",
        json={"exam_start": None, "exam_end": "2026-11-02T12:00"},
    )
    assert invalid.status_code == 400
