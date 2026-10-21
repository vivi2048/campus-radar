from __future__ import annotations

import json
import re
from typing import Any

from ..db import Database
from ..mail.imap import MailAccount, verify_account
from ..mail.providers import Provider, get_provider
from ..security import SecretBox
from ..timeutil import utc_now_iso

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


class AccountError(ValueError):
    pass


def serialize_account(row: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    raw_counts = row.get("last_sync_counts")
    if raw_counts:
        try:
            parsed = json.loads(raw_counts)
            if isinstance(parsed, dict):
                counts = {str(key): int(value) for key, value in parsed.items() if isinstance(value, (int, float))}
        except (TypeError, ValueError):
            counts = {}
    return {
        "id": row["id"],
        "label": row["label"],
        "email": row["email"],
        "provider": row["provider"],
        "imap_host": row["imap_host"],
        "imap_port": row["imap_port"],
        "username": row["username"],
        "folder": row["folder"],
        "sync_days": row["sync_days"],
        "max_messages": row["max_messages"],
        "auto_sync": bool(row["auto_sync"]),
        "enabled": bool(row["enabled"]),
        "last_sync_at": row.get("last_sync_at"),
        "last_sync_status": row.get("last_sync_status") or "idle",
        "last_sync_error": row.get("last_sync_error"),
        "last_sync_counts": counts,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def list_accounts(db: Database) -> list[dict[str, Any]]:
    rows = db.fetch_all("SELECT * FROM accounts ORDER BY created_at ASC")
    return [serialize_account(row) for row in rows]


def get_account(db: Database, account_id: int) -> dict[str, Any] | None:
    row = db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return serialize_account(row) if row else None


def get_raw_account(db: Database, account_id: int) -> dict[str, Any] | None:
    return db.fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,))


def _clean_label(value: Any, provider: Provider, email: str) -> str:
    label = str(value or "").strip()[:80]
    return label or f"{provider.name} · {email}"


def _clean_host(value: Any) -> str:
    host = str(value or "").strip().lower()
    if not host or not HOST_RE.match(host):
        raise AccountError("IMAP 服务器地址格式不正确")
    return host


def _clean_port(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise AccountError("IMAP 端口格式不正确") from exc
    if port < 1 or port > 65535:
        raise AccountError("IMAP 端口需在 1 到 65535 之间")
    return port


def _clean_folder(value: Any) -> str:
    folder = str(value or "INBOX").strip()
    folder = folder.replace("\r", "").replace("\n", "").replace('"', "")
    if not folder:
        folder = "INBOX"
    if len(folder) > 100:
        raise AccountError("邮件文件夹名称过长")
    return folder


def _clean_sync_days(value: Any) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise AccountError("同步天数格式不正确") from exc
    if days < 1 or days > 365:
        raise AccountError("同步天数需在 1 到 365 天之间")
    return days


def _provider_connection(provider: Provider, payload: dict[str, Any]) -> tuple[str, int]:
    if provider.custom:
        return _clean_host(payload.get("imap_host")), _clean_port(payload.get("imap_port", 993))
    return provider.host, provider.port


def build_mail_account(row: dict[str, Any], password: str) -> MailAccount:
    return MailAccount(
        provider=row["provider"],
        email=row["email"],
        username=row["username"],
        password=password,
        host=row["imap_host"],
        port=int(row["imap_port"]),
        folder=row["folder"],
    )


def create_account(
    db: Database,
    vault: SecretBox,
    payload: dict[str, Any],
    *,
    verify: bool = True,
) -> dict[str, Any]:
    provider_id = str(payload.get("provider") or "").strip()
    provider = get_provider(provider_id)
    if not provider:
        raise AccountError("请选择有效的邮箱类型")

    email = str(payload.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AccountError("请输入有效的邮箱地址")
    username = str(payload.get("username") or email).strip()
    if not username:
        raise AccountError("请输入 IMAP 登录账号")

    password = str(payload.get("password") or "").strip()
    if not password:
        raise AccountError("请输入授权码或密码")
    if len(password) > 512:
        raise AccountError("授权码过长")

    host, port = _provider_connection(provider, payload)
    folder = _clean_folder(payload.get("folder"))
    sync_days = _clean_sync_days(payload.get("sync_days", 30))
    auto_sync = bool(payload.get("auto_sync", True))
    label = _clean_label(payload.get("label"), provider, email)

    duplicate = db.fetch_one(
        "SELECT id FROM accounts WHERE username = ? AND imap_host = ?",
        (username, host),
    )
    if duplicate:
        raise AccountError("这个邮箱账号已经添加过了")

    mail_account = MailAccount(
        provider=provider_id,
        email=email,
        username=username,
        password=password,
        host=host,
        port=port,
        folder=folder,
    )
    if verify:
        verify_account(mail_account)

    now = utc_now_iso()
    account_id = db.execute(
        """
        INSERT INTO accounts (
            label, email, provider, imap_host, imap_port, username, password_enc,
            folder, sync_days, max_messages, auto_sync, enabled, last_uid,
            uidvalidity, last_sync_at, last_sync_status, last_sync_error,
            last_sync_counts, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 300, ?, 1, 0, NULL, NULL, 'idle', NULL,
                  NULL, ?, ?)
        """,
        (
            label,
            email,
            provider_id,
            host,
            port,
            username,
            vault.encrypt(password),
            folder,
            sync_days,
            int(auto_sync),
            now,
            now,
        ),
    )
    row = get_raw_account(db, account_id)
    if not row:
        raise AccountError("保存邮箱账号失败")
    return serialize_account(row)


def update_account(
    db: Database,
    vault: SecretBox,
    account_id: int,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    row = get_raw_account(db, account_id)
    if not row:
        return None

    updates: dict[str, Any] = {}
    if "label" in payload:
        provider = get_provider(row["provider"])
        if not provider:
            raise AccountError("邮箱配置异常，请重新添加账号")
        updates["label"] = _clean_label(payload.get("label"), provider, row["email"])
    if "auto_sync" in payload:
        updates["auto_sync"] = int(bool(payload.get("auto_sync")))
    if "enabled" in payload:
        updates["enabled"] = int(bool(payload.get("enabled")))
    if "sync_days" in payload:
        updates["sync_days"] = _clean_sync_days(payload.get("sync_days"))

    folder = row["folder"]
    if "folder" in payload:
        folder = _clean_folder(payload.get("folder"))
        updates["folder"] = folder

    new_password = str(payload.get("password") or "").strip()
    needs_verify = bool(new_password) or folder != row["folder"]
    if needs_verify:
        existing_password = ""
        if not new_password:
            try:
                existing_password = vault.decrypt(row["password_enc"])
            except Exception:
                raise AccountError("无法读取已保存的授权码，请重新输入授权码")
        candidate_password = new_password or existing_password
        mail_account = build_mail_account({**row, "folder": folder}, candidate_password)
        verify_account(mail_account)
    if new_password:
        if len(new_password) > 512:
            raise AccountError("授权码过长")
        updates["password_enc"] = vault.encrypt(new_password)
        updates["last_sync_status"] = "idle"
        updates["last_sync_error"] = None

    if not updates:
        return serialize_account(row)
    updates["updated_at"] = utc_now_iso()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    db.execute(
        f"UPDATE accounts SET {assignments} WHERE id = ?",
        (*updates.values(), account_id),
    )
    updated = get_raw_account(db, account_id)
    return serialize_account(updated) if updated else None


def test_account_connection(db: Database, vault: SecretBox, account_id: int) -> str:
    row = get_raw_account(db, account_id)
    if not row:
        raise AccountError("邮箱账号不存在")
    try:
        password = vault.decrypt(row["password_enc"])
    except Exception as exc:
        raise AccountError(str(exc)) from exc
    verify_account(build_mail_account(row, password))
    return "连接正常"


def delete_account(db: Database, account_id: int) -> bool:
    row = get_raw_account(db, account_id)
    if not row:
        return False
    db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    return True


def clear_account_mail_data(
    db: Database, account_id: int, *, reset_cursor: bool = False
) -> dict[str, int] | None:
    """Delete every recognized record for one mailbox, keeping the account."""
    with db.connection() as conn:
        row = conn.execute(
            "SELECT id FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not row:
            return None
        event_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM events WHERE account_id = ?",
                (account_id,),
            ).fetchone()["count"]
        )
        message_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM seen_messages WHERE account_id = ?",
                (account_id,),
            ).fetchone()["count"]
        )
        conn.execute(
            "DELETE FROM seen_messages WHERE account_id = ?", (account_id,)
        )
        conn.execute("DELETE FROM events WHERE account_id = ?", (account_id,))
        if reset_cursor:
            conn.execute(
                """
                UPDATE accounts
                SET last_sync_counts = NULL, last_uid = 0, uidvalidity = NULL,
                    last_sync_at = NULL, last_sync_status = 'idle',
                    last_sync_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (utc_now_iso(), account_id),
            )
        else:
            conn.execute(
                "UPDATE accounts SET last_sync_counts = NULL, updated_at = ? WHERE id = ?",
                (utc_now_iso(), account_id),
            )
    return {"events": event_count, "messages": message_count}
