from __future__ import annotations

import sqlite3

from app.config import load_settings, migrate_legacy_database


def _write_marker_db(path, value):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        conn.execute("INSERT INTO marker (value) VALUES (?)", (value,))


def test_legacy_database_is_copied_without_removing_original(tmp_path):
    legacy = tmp_path / "examhelper.db"
    _write_marker_db(legacy, "kept")

    migrate_legacy_database(tmp_path)

    current = tmp_path / "campus-radar.db"
    assert legacy.exists()
    with sqlite3.connect(current) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("kept",)


def test_newest_legacy_database_wins(tmp_path):
    _write_marker_db(tmp_path / "examhelper.db", "old")
    _write_marker_db(tmp_path / "exam-radar.db", "new")

    migrate_legacy_database(tmp_path)

    with sqlite3.connect(tmp_path / "campus-radar.db") as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("new",)


def test_environment_prefix_fallback_order(monkeypatch):
    for name in ("CAMPUS_RADAR_PORT", "EXAM_RADAR_PORT", "EXAMHELPER_PORT"):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("EXAMHELPER_PORT", "9123")
    assert load_settings().port == 9123

    monkeypatch.setenv("EXAM_RADAR_PORT", "9124")
    assert load_settings().port == 9124

    monkeypatch.setenv("CAMPUS_RADAR_PORT", "9125")
    assert load_settings().port == 9125
