from __future__ import annotations

import sqlite3

from app.config import load_settings, migrate_legacy_database


def test_legacy_database_is_copied_without_removing_original(tmp_path):
    legacy = tmp_path / "examhelper.db"
    with sqlite3.connect(legacy) as conn:
        conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        conn.execute("INSERT INTO marker (value) VALUES ('kept')")

    migrate_legacy_database(tmp_path)

    current = tmp_path / "exam-radar.db"
    assert legacy.exists()
    with sqlite3.connect(current) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("kept",)


def test_legacy_env_names_still_work(monkeypatch):
    monkeypatch.setenv("EXAMHELPER_PORT", "9123")
    monkeypatch.delenv("EXAM_RADAR_PORT", raising=False)
    assert load_settings().port == 9123

    monkeypatch.setenv("EXAM_RADAR_PORT", "9124")
    assert load_settings().port == 9124
