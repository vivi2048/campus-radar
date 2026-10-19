from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ..db import Database
from ..llm import LLMError
from ..mail.imap import MailboxError, MailboxSession, MailAccount
from ..mail.mime import make_message_key, parse_raw_email
from ..extract.pipeline import analyze_email
from ..security import CredentialError, SecretBox
from ..timeutil import local_iso, utc_now_iso
from .accounts import build_mail_account
from .events import find_duplicate_event, merge_into_event

MAX_EMAIL_BYTES = 10 * 1024 * 1024
RESCHEDULE_RE = re.compile(r"变更|调整|改期|更新|延期|更改", re.IGNORECASE)
RESCANNABLE_OUTCOMES = {"not_exam", "not_event", "llm_rejected", "error", "llm_error"}

SessionFactory = Callable[[MailAccount], MailboxSession]


@dataclass
class SyncResult:
    success: bool
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class SyncService:
    def __init__(
        self,
        db: Database,
        vault: SecretBox,
        logger: logging.Logger,
        *,
        session_factory: SessionFactory = MailboxSession,
        llm_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.db = db
        self.vault = vault
        self.logger = logger
        self.session_factory = session_factory
        self.llm_factory = llm_factory

    def _set_failed(self, account_id: int, message: str) -> SyncResult:
        self.db.execute(
            """
            UPDATE accounts
            SET last_sync_status = 'error', last_sync_error = ?,
                last_sync_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (message[:1000], utc_now_iso(), utc_now_iso(), account_id),
        )
        return SyncResult(success=False, error=message)

    def sync_account(self, account_id: int, *, rescan: bool = False) -> SyncResult:
        row = self.db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
        if not row:
            return SyncResult(success=False, error="邮箱账号不存在")
        counts = {
            "downloaded": 0,
            "scanned": 0,
            "matched": 0,
            "created": 0,
            "created_exams": 0,
            "created_interviews": 0,
            "reclassified": 0,
            "llm_called": 0,
            "llm_matched": 0,
            "llm_rejected": 0,
            "llm_errors": 0,
            "merged": 0,
            "skipped": 0,
            "errors": 0,
        }
        self.db.execute(
            """
            UPDATE accounts SET last_sync_status = 'syncing', last_sync_error = NULL,
                updated_at = ? WHERE id = ?
            """,
            (utc_now_iso(), account_id),
        )

        try:
            password = self.vault.decrypt(row["password_enc"])
        except CredentialError as exc:
            self.logger.error("Sync account %s failed: credential error", account_id)
            return self._set_failed(account_id, str(exc))
        except Exception:
            self.logger.exception("Sync account %s failed to decrypt credentials", account_id)
            return self._set_failed(account_id, "无法读取已保存的授权码，请重新输入授权码。")

        since = datetime.now(timezone.utc) - timedelta(days=int(row["sync_days"]))
        mail_account = build_mail_account(row, password)
        next_uid = int(row.get("last_uid") or 0)
        uidvalidity: str | None = row.get("uidvalidity")
        llm = None
        if self.llm_factory:
            try:
                llm = self.llm_factory()
            except Exception as exc:
                self.logger.warning(
                    "LLM recognition is unavailable for account %s: %s", account_id, exc
                )
        llm_calls = 0
        try:
            with self.session_factory(mail_account) as session:
                search = session.search(
                    since=since,
                    last_uid=0 if rescan else int(row.get("last_uid") or 0),
                    known_uidvalidity=None if rescan else row.get("uidvalidity"),
                    limit=int(row.get("max_messages") or 300),
                )
                next_uid = max(next_uid, search.top_uid)
                uidvalidity = search.uidvalidity
                for uid in sorted(search.uids, reverse=True):
                    try:
                        raw = session.fetch_raw(uid)
                    except MailboxError:
                        raise
                    counts["downloaded"] += 1
                    if len(raw) > MAX_EMAIL_BYTES:
                        counts["errors"] += 1
                        self._record_seen(account_id, f"uid-too-large-{uid}", "too_large", None)
                        continue
                    message_key: str | None = None
                    try:
                        parsed = parse_raw_email(raw, fallback_received_at=datetime.now(timezone.utc))
                        message_key = make_message_key(parsed, raw)
                        seen = self._seen_row(account_id, message_key)
                        reprocess = bool(
                            seen
                            and rescan
                            and seen.get("event_id") is None
                            and seen.get("outcome") in RESCANNABLE_OUTCOMES
                        )
                        if seen and not reprocess:
                            counts["skipped"] += 1
                            continue
                        counts["scanned"] += 1
                        analysis = analyze_email(parsed)
                        llm_error = False
                        should_consider = False
                        if llm is not None:
                            try:
                                should_consider = llm.should_consider(parsed, analysis)
                            except Exception:
                                should_consider = False
                            max_calls = int(getattr(llm, "max_calls", 0) or 0)
                            if should_consider and llm_calls < max_calls:
                                llm_calls += 1
                                counts["llm_called"] += 1
                                try:
                                    llm_analysis = llm.analyze(parsed)
                                except LLMError as exc:
                                    counts["llm_errors"] += 1
                                    llm_error = True
                                    llm_analysis = None
                                    self.logger.warning(
                                        "LLM recognition failed for account %s: %s",
                                        account_id,
                                        exc,
                                    )
                                if (
                                    llm_analysis
                                    and llm_analysis.accepted
                                    and llm_analysis.fields
                                    and llm_analysis.timing
                                ):
                                    analysis = self._merge_llm_analysis(
                                        llm_analysis, analysis
                                    )
                                    counts["llm_matched"] += 1
                                elif not llm_error:
                                    # A successful LLM rejection is authoritative and
                                    # must veto a local false positive.
                                    counts["llm_rejected"] += 1
                                    counts["skipped"] += 1
                                    self._record_seen(
                                        account_id, message_key, "llm_rejected", None
                                    )
                                    continue
                            elif should_consider and analysis.accepted:
                                note = "本轮大模型调用次数已用完，仅使用本地规则识别，请核对。"
                                analysis = replace(
                                    analysis,
                                    needs_review=True,
                                    auto_notes=(
                                        f"{note}\n{analysis.auto_notes}"
                                        if analysis.auto_notes
                                        else note
                                    ),
                                )
                        if llm_error and analysis.accepted:
                            note = "大模型识别失败，暂用本地规则识别，请核对。"
                            analysis = replace(
                                analysis,
                                needs_review=True,
                                auto_notes=(
                                    f"{note}\n{analysis.auto_notes}"
                                    if analysis.auto_notes
                                    else note
                                ),
                            )
                        if not analysis.accepted or not analysis.fields or not analysis.timing:
                            counts["skipped"] += 1
                            if llm_error:
                                outcome = "llm_error"
                            else:
                                outcome = "not_event"
                            self._record_seen(account_id, message_key, outcome, None)
                            continue
                        counts["matched"] += 1
                        new_values = self._event_values(account_id, parsed, analysis)
                        reschedule = bool(RESCHEDULE_RE.search(f"{parsed.subject}\n{parsed.body_text[:3000]}"))
                        existing = find_duplicate_event(
                            self.db,
                            account_id=account_id,
                            company=new_values["company"],
                            role=new_values["role"],
                            exam_start=new_values["exam_start"],
                            exam_url=new_values["exam_url"],
                            reschedule=reschedule,
                            kind=new_values["kind"],
                            interview_round=new_values["interview_round"],
                        )
                        if existing:
                            merge_into_event(
                                self.db,
                                existing,
                                new_values=new_values,
                                subject=parsed.subject,
                                sender=parsed.from_line,
                                received_at=local_iso(parsed.received_at),
                                body=parsed.body_text,
                                reschedule=reschedule,
                            )
                            counts["merged"] += 1
                            self._record_seen(account_id, message_key, "merged", int(existing["id"]))
                        else:
                            event_id = self._insert_event(new_values)
                            counts["created"] += 1
                            if new_values["kind"] == "interview":
                                counts["created_interviews"] += 1
                            else:
                                counts["created_exams"] += 1
                            self._record_seen(account_id, message_key, "created", event_id)
                        if seen:
                            counts["reclassified"] += 1
                    except Exception:
                        counts["errors"] += 1
                        self.logger.exception("Failed to process one email for account %s", account_id)
                        if message_key:
                            try:
                                self._record_seen(account_id, message_key, "error", None)
                            except Exception:
                                pass
                        continue
        except MailboxError as exc:
            self.logger.warning("Mailbox sync failed for account %s: %s", account_id, exc)
            return self._set_failed(account_id, str(exc))
        except Exception:
            self.logger.exception("Unexpected sync failure for account %s", account_id)
            return self._set_failed(account_id, "同步时发生内部错误，请查看本地日志后重试。")

        now = utc_now_iso()
        self.db.execute(
            """
            UPDATE accounts
            SET last_uid = ?, uidvalidity = ?, last_sync_at = ?,
                last_sync_status = 'ok', last_sync_error = NULL,
                last_sync_counts = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_uid,
                uidvalidity,
                now,
                json.dumps(counts, ensure_ascii=False),
                now,
                account_id,
            ),
        )
        self.logger.info(
            "Sync account %s complete: scanned=%s matched=%s created=%s"
            " (exam=%s interview=%s) merged=%s reclassified=%s"
            " llm_called=%s llm_matched=%s llm_errors=%s errors=%s",
            account_id,
            counts["scanned"],
            counts["matched"],
            counts["created"],
            counts["created_exams"],
            counts["created_interviews"],
            counts["merged"],
            counts["reclassified"],
            counts["llm_called"],
            counts["llm_matched"],
            counts["llm_errors"],
            counts["errors"],
        )
        return SyncResult(success=True, counts=counts)

    def _seen_row(self, account_id: int, message_key: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT outcome, event_id FROM seen_messages WHERE account_id = ? AND message_key = ?",
            (account_id, message_key),
        )

    def _record_seen(
        self, account_id: int, message_key: str, outcome: str, event_id: int | None
    ) -> None:
        self.db.execute(
            """
            INSERT INTO seen_messages (account_id, message_key, outcome, event_id, seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id, message_key) DO UPDATE SET
                outcome = excluded.outcome,
                event_id = COALESCE(excluded.event_id, seen_messages.event_id),
                seen_at = excluded.seen_at
            """,
            (account_id, message_key, outcome, event_id, utc_now_iso()),
        )

    @staticmethod
    def _merge_llm_analysis(primary: Any, fallback: Any) -> Any:
        """Keep LLM fields, but fill gaps from the local rules when possible."""
        if (
            not primary
            or not fallback
            or not primary.accepted
            or not fallback.accepted
            or primary.kind != fallback.kind
            or not primary.fields
            or not fallback.fields
            or not primary.timing
            or not fallback.timing
        ):
            return primary
        fields = replace(
            primary.fields,
            company=primary.fields.company or fallback.fields.company,
            role=primary.fields.role or fallback.fields.role,
            platform=primary.fields.platform or fallback.fields.platform,
            exam_url=primary.fields.exam_url or fallback.fields.exam_url,
            mode=(
                primary.fields.mode
                if primary.fields.mode != "unknown"
                else fallback.fields.mode
            ),
            location=primary.fields.location or fallback.fields.location,
            access_code=primary.fields.access_code or fallback.fields.access_code,
            interview_round=(
                primary.fields.interview_round or fallback.fields.interview_round
            ),
        )
        timing = primary.timing
        start = timing.exam_start
        end = timing.exam_end
        time_known = timing.exam_time_known
        deadline = timing.deadline
        deadline_known = timing.deadline_time_known
        duration = timing.duration_minutes
        start_is_window = timing.start_is_window
        notes = [primary.auto_notes] if primary.auto_notes else []
        if (not start or not time_known) and fallback.timing.exam_start:
            start = fallback.timing.exam_start
            end = fallback.timing.exam_end
            time_known = fallback.timing.exam_time_known
            start_is_window = fallback.timing.start_is_window
            if fallback.timing.start_note:
                notes.append(fallback.timing.start_note)
        if not deadline and fallback.timing.deadline:
            deadline = fallback.timing.deadline
            deadline_known = fallback.timing.deadline_time_known
            if fallback.timing.deadline_note:
                notes.append(fallback.timing.deadline_note)
        if not duration and fallback.timing.duration_minutes:
            duration = fallback.timing.duration_minutes
        auto_notes = "\n".join(dict.fromkeys(part for part in notes if part))
        timing = replace(
            timing,
            exam_start=start,
            exam_end=end,
            exam_time_known=time_known,
            deadline=deadline,
            deadline_time_known=deadline_known,
            duration_minutes=duration,
            start_is_window=start_is_window,
        )
        return replace(
            primary,
            fields=fields,
            timing=timing,
            auto_notes=auto_notes or primary.auto_notes,
        )

    @staticmethod
    def _event_values(account_id: int, parsed: Any, analysis: Any) -> dict[str, Any]:
        fields = analysis.fields
        timing = analysis.timing
        return {
            "account_id": account_id,
            "kind": analysis.kind or "exam",
            "interview_round": fields.interview_round or "",
            "company": fields.company,
            "role": fields.role,
            "exam_start": timing.exam_start,
            "exam_end": timing.exam_end,
            "exam_time_known": int(timing.exam_time_known),
            "deadline": timing.deadline,
            "deadline_time_known": int(timing.deadline_time_known),
            "duration_minutes": timing.duration_minutes,
            "platform": fields.platform,
            "exam_url": fields.exam_url,
            "mode": fields.mode,
            "location": fields.location,
            "access_code": fields.access_code,
            "status": "pending",
            "ignored": 0,
            "needs_review": int(analysis.needs_review),
            "manually_edited": 0,
            "auto_notes": analysis.auto_notes,
            "notes": None,
            "source_subject": parsed.subject,
            "source_sender": parsed.from_line,
            "source_received_at": local_iso(parsed.received_at),
            "source_body": parsed.body_text[:50_000],
            "source_count": 1,
            "is_demo": 0,
        }

    def _insert_event(self, values: dict[str, Any]) -> int:
        now = utc_now_iso()
        return self.db.execute(
            """
            INSERT INTO events (
                account_id, kind, interview_round, company, role, exam_start, exam_end, exam_time_known,
                deadline, deadline_time_known, duration_minutes, platform, exam_url,
                mode, location, access_code, status, ignored, needs_review,
                manually_edited, auto_notes, notes, source_subject, source_sender,
                source_received_at, source_body, source_count, is_demo,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["account_id"],
                values["kind"],
                values["interview_round"],
                values["company"],
                values["role"],
                values["exam_start"],
                values["exam_end"],
                values["exam_time_known"],
                values["deadline"],
                values["deadline_time_known"],
                values["duration_minutes"],
                values["platform"],
                values["exam_url"],
                values["mode"],
                values["location"],
                values["access_code"],
                values["status"],
                values["ignored"],
                values["needs_review"],
                values["manually_edited"],
                values["auto_notes"],
                values["notes"],
                values["source_subject"],
                values["source_sender"],
                values["source_received_at"],
                values["source_body"],
                values["source_count"],
                values["is_demo"],
                now,
                now,
            ),
        )


class SyncManager:
    def __init__(self, db: Database, service: SyncService, logger: logging.Logger) -> None:
        self.db = db
        self.service = service
        self.logger = logger
        self._active: set[int] = set()
        self._lock = threading.Lock()

    def is_active(self, account_id: int) -> bool:
        with self._lock:
            return account_id in self._active

    def active_ids(self) -> set[int]:
        with self._lock:
            return set(self._active)

    def trigger(self, account_id: int, reason: str = "manual", *, rescan: bool = False) -> bool:
        account = self.db.fetch_one("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if not account:
            return False
        with self._lock:
            if account_id in self._active:
                return False
            self._active.add(account_id)
        self.db.execute(
            """
            UPDATE accounts SET last_sync_status = 'syncing', last_sync_error = NULL,
                updated_at = ? WHERE id = ?
            """,
            (utc_now_iso(), account_id),
        )
        thread = threading.Thread(
            target=self._run,
            args=(account_id, reason, rescan),
            name=f"mail-sync-{account_id}",
            daemon=True,
        )
        thread.start()
        return True

    def _run(self, account_id: int, reason: str, rescan: bool = False) -> None:
        try:
            self.logger.info(
                "Starting %s%s sync for account %s",
                reason,
                " rescan" if rescan else "",
                account_id,
            )
            result = self.service.sync_account(account_id, rescan=rescan)
            if not result.success:
                self.logger.warning("Sync failed for account %s: %s", account_id, result.error)
        except Exception:
            self.logger.exception("Unhandled sync thread error for account %s", account_id)
            try:
                self.db.execute(
                    """
                    UPDATE accounts SET last_sync_status = 'error',
                        last_sync_error = '同步线程异常退出，请重试。', last_sync_at = ?,
                        updated_at = ? WHERE id = ?
                    """,
                    (utc_now_iso(), utc_now_iso(), account_id),
                )
            except Exception:
                pass
        finally:
            with self._lock:
                self._active.discard(account_id)


class AutoSyncWorker(threading.Thread):
    def __init__(
        self,
        db: Database,
        manager: SyncManager,
        logger: logging.Logger,
        *,
        interval_minutes: int = 30,
    ) -> None:
        super().__init__(name="campus-radar-auto-sync", daemon=True)
        self.db = db
        self.manager = manager
        self.logger = logger
        self.interval_seconds = max(5, interval_minutes) * 60
        self._stop_event = threading.Event()
        self._check_seconds = 60

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if self._stop_event.wait(10):
            return
        while not self._stop_event.is_set():
            try:
                rows = self.db.fetch_all(
                    "SELECT id, last_sync_at FROM accounts WHERE enabled = 1 AND auto_sync = 1"
                )
                now = datetime.now(timezone.utc)
                for row in rows:
                    account_id = int(row["id"])
                    if self.manager.is_active(account_id):
                        continue
                    last_sync_at = self._parse_time(row.get("last_sync_at"))
                    if last_sync_at and (now - last_sync_at).total_seconds() < self.interval_seconds:
                        continue
                    self.manager.trigger(account_id, reason="auto")
            except Exception:
                self.logger.exception("Auto sync check failed")
            self._stop_event.wait(self._check_seconds)

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
