from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    email TEXT NOT NULL,
    provider TEXT NOT NULL,
    imap_host TEXT NOT NULL,
    imap_port INTEGER NOT NULL,
    username TEXT NOT NULL,
    password_enc TEXT NOT NULL,
    folder TEXT NOT NULL DEFAULT 'INBOX',
    sync_days INTEGER NOT NULL DEFAULT 30,
    max_messages INTEGER NOT NULL DEFAULT 300,
    auto_sync INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_uid INTEGER NOT NULL DEFAULT 0,
    uidvalidity TEXT,
    last_sync_at TEXT,
    last_sync_status TEXT NOT NULL DEFAULT 'idle',
    last_sync_error TEXT,
    last_sync_counts TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_mailbox
    ON accounts (username, imap_host);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    company TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    exam_start TEXT,
    exam_end TEXT,
    exam_time_known INTEGER NOT NULL DEFAULT 1,
    deadline TEXT,
    deadline_time_known INTEGER NOT NULL DEFAULT 1,
    duration_minutes INTEGER,
    platform TEXT,
    exam_url TEXT,
    mode TEXT NOT NULL DEFAULT 'unknown',
    location TEXT,
    access_code TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
    ignored INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    manually_edited INTEGER NOT NULL DEFAULT 0,
    auto_notes TEXT,
    notes TEXT,
    source_subject TEXT,
    source_sender TEXT,
    source_received_at TEXT,
    source_body TEXT,
    source_count INTEGER NOT NULL DEFAULT 1,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_exam_start ON events (exam_start);
CREATE INDEX IF NOT EXISTS idx_events_status ON events (status, ignored);
CREATE INDEX IF NOT EXISTS idx_events_account ON events (account_id);

CREATE TABLE IF NOT EXISTS seen_messages (
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    message_key TEXT NOT NULL,
    outcome TEXT NOT NULL,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (account_id, message_key)
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return int(cursor.lastrowid)
