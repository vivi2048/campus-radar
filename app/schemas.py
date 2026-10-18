from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str = "exam"
    interview_round: str | None = None
    company: str = ""
    role: str = ""
    exam_start: str | None = None
    exam_end: str | None = None
    exam_time_known: bool = True
    deadline: str | None = None
    deadline_time_known: bool = True
    duration_minutes: int | None = None
    platform: str | None = None
    exam_url: str | None = None
    mode: str = "unknown"
    location: str | None = None
    access_code: str | None = None
    status: str = "pending"
    ignored: bool = False
    notes: str | None = None
    auto_notes: str | None = None


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str | None = None
    interview_round: str | None = None
    company: str | None = None
    role: str | None = None
    exam_start: str | None = None
    exam_end: str | None = None
    exam_time_known: bool | None = None
    deadline: str | None = None
    deadline_time_known: bool | None = None
    duration_minutes: int | None = None
    platform: str | None = None
    exam_url: str | None = None
    mode: str | None = None
    location: str | None = None
    access_code: str | None = None
    status: str | None = None
    ignored: bool | None = None
    notes: str | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    clear_api_key: bool = False
    max_calls_per_sync: int = 10


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = ""
    email: str = ""
    password: str = ""
    label: str = ""
    username: str = ""
    imap_host: str = ""
    imap_port: int = 993
    folder: str = "INBOX"
    sync_days: int = 30
    auto_sync: bool = True


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    password: str | None = None
    folder: str | None = None
    sync_days: int | None = None
    auto_sync: bool | None = None
    enabled: bool | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)
