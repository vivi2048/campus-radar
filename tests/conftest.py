from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Avoid touching the real local data directory when app.main is imported in tests.
os.environ.setdefault("CAMPUS_RADAR_DATA_DIR", tempfile.mkdtemp(prefix="campus-radar-test-"))
os.environ["CAMPUS_RADAR_DISABLE_SCHEDULER"] = "1"

import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, start_scheduler=False)


@pytest.fixture()
def client(settings: Settings):
    from fastapi.testclient import TestClient

    app = create_app(settings)
    with TestClient(app) as test_client:
        test_client.headers["X-Campus-Radar-Request"] = "1"
        yield test_client
