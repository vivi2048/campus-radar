from __future__ import annotations

import logging
import threading
from pathlib import Path

import pytest

import app.services.accounts as accounts_service
from app.db import Database
from app.llm import LLMError, build_analysis_from_payload
from app.mail.imap import SearchResult
from app.mail.mime import make_message_key, parse_raw_email
from app.security import SecretBox
from app.services.accounts import create_account
from app.services.sync import SyncService
from app.timeutil import utc_now_iso


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
        5: (FIXTURES / "interview_reminder.eml").read_bytes(),
    }
    logger = logging.getLogger("campus-radar-test-sync")
    service = SyncService(
        db,
        vault,
        logger,
        session_factory=lambda account: FakeSession(messages),
    )
    return db, vault, account, service, messages


def test_sync_creates_exam_and_interview_events_and_merges_reminders(sync_setup):
    db, _, account, service, _ = sync_setup
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["scanned"] == 5
    assert result.counts["matched"] == 5
    assert result.counts["created"] == 3
    assert result.counts["created_exams"] == 2
    assert result.counts["created_interviews"] == 1
    assert result.counts["merged"] == 2
    assert result.counts["skipped"] == 0

    events = db.fetch_all("SELECT * FROM events ORDER BY id")
    assert len(events) == 3
    xingye = next(event for event in events if event["company"] == "星野科技")
    assert xingye["kind"] == "exam"
    assert xingye["role"] == "后端开发工程师"
    assert xingye["source_count"] == 2
    assert xingye["exam_start"] == "2026-10-22T19:00+08:00"
    assert xingye["access_code"] == "XINGYE2026"
    assert xingye["needs_review"] == 0

    farhill = next(event for event in events if event["company"] == "远山资本")
    assert farhill["kind"] == "interview"
    assert farhill["role"] == "投资分析师"
    assert farhill["source_count"] == 2
    assert farhill["exam_start"] == "2026-10-23T14:00+08:00"
    assert farhill["exam_url"] == "https://meeting.example.com/abc"

    account_row = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account["id"],))
    assert account_row["last_sync_status"] == "ok"
    assert account_row["last_uid"] == 5
    assert account_row["uidvalidity"] == "42"

    outcomes = {row["message_key"]: row["outcome"] for row in db.fetch_all("SELECT * FROM seen_messages")}
    assert sorted(outcomes.values()) == ["created", "created", "created", "merged", "merged"]


def test_sync_is_idempotent(sync_setup):
    db, _, account, service, _ = sync_setup
    first = service.sync_account(account["id"])
    assert first.success
    second = service.sync_account(account["id"])
    assert second.success
    assert second.counts["created"] == 0
    assert second.counts["merged"] == 0
    count = db.fetch_one("SELECT COUNT(*) AS count FROM events")
    assert count["count"] == 3


def test_rescan_reprocesses_previously_skipped_messages(sync_setup):
    db, _, account, service, _ = sync_setup
    raw = (FIXTURES / "interview_invite.eml").read_bytes()
    parsed = parse_raw_email(raw)
    message_key = make_message_key(parsed, raw)
    db.execute(
        """
        INSERT INTO seen_messages (account_id, message_key, outcome, event_id, seen_at)
        VALUES (?, ?, 'not_exam', NULL, ?)
        """,
        (account["id"], message_key, utc_now_iso()),
    )

    result = service.sync_account(account["id"], rescan=True)
    assert result.success
    assert result.counts["scanned"] == 5
    assert result.counts["reclassified"] == 1
    assert result.counts["created_interviews"] == 1
    farhill = db.fetch_one("SELECT * FROM events WHERE company = '远山资本'")
    assert farhill is not None
    assert farhill["kind"] == "interview"
    assert farhill["exam_start"] == "2026-10-23T14:00+08:00"


def test_llm_is_primary_when_configured(sync_setup):
    db, vault, account, _, _ = sync_setup
    raw = (FIXTURES / "interview_invite.eml").read_bytes()
    payload = {
        "is_event": True,
        "kind": "interview",
        "confidence": 0.91,
        "company": "远山资本",
        "role": "投资分析师",
        "interview_round": "一面",
        "start": "2026-10-24T10:00:00+08:00",
        "time_known": True,
        "platform": "腾讯会议",
        "url": "https://meeting.tencent.com/llm-demo",
        "mode": "online",
        "notes": ["提前进入会议室"],
    }

    class FakeLLM:
        max_calls = 10

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            return build_analysis_from_payload(payload)

    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-primary"),
        session_factory=lambda account: FakeSession({1: raw}),
        llm_factory=lambda: FakeLLM(),
    )
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["llm_called"] == 1
    assert result.counts["llm_matched"] == 1
    assert result.counts["created_interviews"] == 1
    event = db.fetch_one("SELECT * FROM events WHERE company = '远山资本'")
    assert event is not None
    assert event["kind"] == "interview"
    assert event["interview_round"] == "一面"
    assert event["exam_start"] == "2026-10-24T10:00+08:00"
    assert event["platform"] == "腾讯会议"
    assert event["needs_review"] == 1
    assert "大模型识别" in (event["auto_notes"] or "")


def test_llm_event_fills_missing_time_from_local_rules(sync_setup):
    db, vault, account, _, _ = sync_setup
    raw = (FIXTURES / "interview_invite.eml").read_bytes()
    payload = {
        "is_event": True,
        "kind": "interview",
        "confidence": 0.9,
        "company": "远山资本",
        "role": "投资分析师",
        "start": None,
        "time_known": False,
        "notes": ["大模型没有给出具体时间"],
    }

    class NoTimeLLM:
        max_calls = 10

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            return build_analysis_from_payload(payload)

    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-merge"),
        session_factory=lambda account: FakeSession({1: raw}),
        llm_factory=lambda: NoTimeLLM(),
    )
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["llm_matched"] == 1
    event = db.fetch_one("SELECT * FROM events WHERE company = '远山资本'")
    assert event is not None
    assert event["exam_start"] == "2026-10-23T14:00+08:00"
    assert event["exam_time_known"] == 1
    assert "大模型识别" in (event["auto_notes"] or "")


def test_llm_rejection_vetoes_locally_accepted_event(sync_setup):
    db, vault, account, _, _ = sync_setup
    raw = (FIXTURES / "interview_invite.eml").read_bytes()

    class RejectingLLM:
        max_calls = 10

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            return None

    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-veto"),
        session_factory=lambda account: FakeSession({1: raw}),
        llm_factory=lambda: RejectingLLM(),
    )
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["llm_called"] == 1
    assert result.counts["llm_rejected"] == 1
    assert result.counts["created"] == 0
    assert result.counts["matched"] == 0
    assert db.fetch_one("SELECT * FROM events WHERE company = '远山资本'") is None
    outcome = db.fetch_one("SELECT outcome FROM seen_messages")
    assert outcome is not None and outcome["outcome"] == "llm_rejected"


def test_llm_error_falls_back_to_local_rules(sync_setup):
    db, vault, account, _, _ = sync_setup
    raw = (FIXTURES / "interview_invite.eml").read_bytes()

    class BrokenLLM:
        max_calls = 10

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            raise LLMError("temporary failure")

    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-error"),
        session_factory=lambda account: FakeSession({1: raw}),
        llm_factory=lambda: BrokenLLM(),
    )
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["llm_called"] == 1
    assert result.counts["llm_errors"] == 1
    assert result.counts["llm_matched"] == 0
    assert result.counts["created"] == 1
    event = db.fetch_one("SELECT * FROM events WHERE company = '远山资本'")
    assert event is not None
    assert event["exam_start"] == "2026-10-23T14:00+08:00"
    assert event["needs_review"] == 1
    assert "大模型识别失败" in (event["auto_notes"] or "")


def test_llm_calls_run_in_parallel_with_configured_concurrency(sync_setup):
    db, vault, account, _, messages = sync_setup

    class ParallelLLM:
        max_calls = 10
        concurrency = 3

        def __init__(self):
            self._lock = threading.Lock()
            self._release = threading.Event()
            self.active = 0
            self.max_active = 0

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                if self.active >= self.concurrency:
                    self._release.set()
            self._release.wait(timeout=2)
            with self._lock:
                self.active -= 1
            return None

    llm = ParallelLLM()
    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-concurrency"),
        session_factory=lambda account: FakeSession(messages),
        llm_factory=lambda: llm,
    )
    result = service.sync_account(account["id"])
    assert result.success
    assert result.counts["llm_called"] == 5
    assert llm.max_active == 3
    assert result.counts["llm_rejected"] == 5


def test_llm_rejection_is_not_reprocessed_on_next_sync(sync_setup):
    db, vault, account, _, _ = sync_setup
    raw = (FIXTURES / "marketing_questions.eml").read_bytes()

    class RejectingLLM:
        max_calls = 10

        def should_consider(self, parsed, analysis):
            return True

        def analyze(self, parsed):
            return None

    service = SyncService(
        db,
        vault,
        logging.getLogger("campus-radar-test-llm-reject"),
        session_factory=lambda account: FakeSession({1: raw}),
        llm_factory=lambda: RejectingLLM(),
    )
    first = service.sync_account(account["id"])
    assert first.success
    assert first.counts["llm_called"] == 1
    assert first.counts["llm_rejected"] == 1
    assert first.counts["created"] == 0
    outcome = db.fetch_one("SELECT outcome FROM seen_messages")
    assert outcome is not None and outcome["outcome"] == "llm_rejected"

    second = service.sync_account(account["id"])
    assert second.success
    assert second.counts["llm_called"] == 0
    assert second.counts["scanned"] == 0


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
        logging.getLogger("campus-radar-test-sync-error"),
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
        {6: (FIXTURES / "xingye_reschedule.eml").read_bytes()}
    )
    reschedule_service = SyncService(
        db,
        service.vault,
        logging.getLogger("campus-radar-test-reschedule"),
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
    assert db.fetch_one("SELECT COUNT(*) AS count FROM events")["count"] == 3


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
