from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
APP_VERSION = "1.0.0"
APP_NAME = "exam-radar"
_ENV_PREFIX = "EXAM_RADAR"
_LEGACY_ENV_PREFIX = "EXAMHELPER"


def env_value(name: str, default: str = "") -> str:
    """Read a new-style variable, falling back to the pre-rename name."""
    value = os.getenv(f"{_ENV_PREFIX}_{name}")
    if value is None:
        value = os.getenv(f"{_LEGACY_ENV_PREFIX}_{name}")
    return default if value is None else value


def _env_int(name: str, default: int) -> int:
    raw = env_value(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8000
    auto_sync_minutes: int = 30
    start_scheduler: bool = True
    static_dir: Path = STATIC_DIR
    app_name: str = APP_NAME

    @property
    def db_path(self) -> Path:
        return self.data_dir / "exam-radar.db"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / ".secret.key"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "exam-radar.log"


def migrate_legacy_database(data_dir: Path) -> None:
    """Copy the pre-rename database once, keeping the original as a backup."""
    legacy_path = data_dir / "examhelper.db"
    current_path = data_dir / "exam-radar.db"
    if current_path.exists() or not legacy_path.exists():
        return
    source = sqlite3.connect(legacy_path)
    target = sqlite3.connect(current_path)
    try:
        source.backup(target)
    except Exception:
        source.close()
        target.close()
        current_path.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm"):
            current_path.with_name(current_path.name + suffix).unlink(missing_ok=True)
        raise
    source.close()
    target.close()


def load_settings() -> Settings:
    data_dir = Path(env_value("DATA_DIR", str(BASE_DIR / "data"))).expanduser()
    return Settings(
        data_dir=data_dir.resolve(),
        host=env_value("HOST", "127.0.0.1"),
        port=_env_int("PORT", 8000),
        auto_sync_minutes=max(5, _env_int("AUTO_SYNC_MINUTES", 30)),
        start_scheduler=env_value("DISABLE_SCHEDULER").lower()
        not in {"1", "true", "yes"},
    )
