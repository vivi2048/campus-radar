from __future__ import annotations


def test_meta_and_providers(client):
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["app_name"] == "campus-radar"
    providers = client.get("/api/providers")
    assert providers.status_code == 200
    ids = {provider["id"] for provider in providers.json()}
    assert {"qq", "163", "126", "gmail", "custom"} <= ids


def test_demo_events_detail_edit_and_clear(client):
    response = client.post("/api/demo")
    assert response.status_code == 201
    assert response.json()["inserted"] == 7
    events = client.get("/api/events").json()
    assert len(events) == 7
    assert any(event["is_demo"] for event in events)
    interviews = [event for event in events if event["kind"] == "interview"]
    assert len(interviews) == 2
    assert {event["interview_round"] for event in interviews} == {"一面", "二面"}
    first = events[0]
    detail = client.get(f"/api/events/{first['id']}")
    assert detail.status_code == 200
    assert detail.json()["source_body"]

    response = client.patch(
        f"/api/events/{first['id']}",
        json={
            "company": "改写后的公司",
            "exam_start": "2026-12-01T19:00",
            "exam_end": "2026-12-01T21:00",
            "exam_time_known": True,
            "notes": "带上身份证",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["company"] == "改写后的公司"
    assert updated["exam_start"] == "2026-12-01T19:00+08:00"
    assert updated["notes"] == "带上身份证"
    assert updated["manually_edited"] is True

    cleared = client.delete("/api/demo")
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 7
    assert client.get("/api/events").json() == []


def test_manual_event_create_and_validation(client):
    response = client.post(
        "/api/events",
        json={
            "company": "示例公司",
            "role": "算法工程师",
            "exam_start": "2026-11-01T10:00",
            "duration_minutes": 90,
            "platform": "牛客网",
            "exam_url": "https://www.nowcoder.com/",
        },
    )
    assert response.status_code == 201
    event = response.json()
    assert event["company"] == "示例公司"
    assert event["exam_start"] == "2026-11-01T10:00+08:00"
    assert event["source_subject"] is None
    assert event["manually_edited"] is True

    invalid_company = client.post("/api/events", json={"company": ""})
    assert invalid_company.status_code == 400
    invalid_url = client.post(
        "/api/events",
        json={"company": "示例公司", "exam_url": "javascript:alert(1)"},
    )
    assert invalid_url.status_code == 400
    invalid_time = client.patch(
        f"/api/events/{event['id']}",
        json={"exam_end": "2026-10-01T10:00"},
    )
    assert invalid_time.status_code == 400

    deleted = client.delete(f"/api/events/{event['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/events/{event['id']}").status_code == 404


def test_manual_interview_event_create_and_kind_switch(client):
    response = client.post(
        "/api/events",
        json={
            "kind": "interview",
            "interview_round": "一面",
            "company": "示例公司",
            "role": "产品经理",
            "exam_start": "2026-11-03T14:00",
            "duration_minutes": 45,
            "platform": "腾讯会议",
            "exam_url": "https://meeting.tencent.com/demo",
            "access_code": "会议号 123 456 789",
        },
    )
    assert response.status_code == 201
    event = response.json()
    assert event["kind"] == "interview"
    assert event["interview_round"] == "一面"
    assert event["duration_minutes"] == 45

    switched = client.patch(f"/api/events/{event['id']}", json={"kind": "exam"})
    assert switched.status_code == 200
    assert switched.json()["kind"] == "exam"
    assert switched.json()["interview_round"] == ""

    invalid = client.post(
        "/api/events",
        json={"company": "示例公司", "kind": "other"},
    )
    assert invalid.status_code == 400


def test_ignore_state_is_cleared_when_status_changes(client):
    response = client.post("/api/events", json={"company": "忽略测试"})
    assert response.status_code == 201
    event = response.json()

    ignored = client.patch(f"/api/events/{event['id']}", json={"ignored": True})
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "cancelled"
    assert ignored.json()["ignored"] is False

    done = client.patch(f"/api/events/{event['id']}", json={"status": "done"})
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["ignored"] is False

    cancelled = client.patch(f"/api/events/{event['id']}", json={"status": "cancelled"})
    assert cancelled.json()["status"] == "cancelled"
    pending = client.patch(f"/api/events/{event['id']}", json={"status": "pending"})
    assert pending.json()["status"] == "pending"
    assert pending.json()["ignored"] is False


def test_unknown_event_returns_404(client):
    assert client.get("/api/events/9999").status_code == 404
    assert client.patch("/api/events/9999", json={"company": "X"}).status_code == 404
    assert client.delete("/api/events/9999").status_code == 404


def test_account_creation_is_rejected_without_network(client, monkeypatch):
    import app.services.accounts as accounts_service
    from app.mail.imap import MailboxError

    def fake_verify(_):
        raise MailboxError("QQ 邮箱认证失败。请确认已开启 IMAP 服务，并填写授权码而不是 QQ 密码。")

    monkeypatch.setattr(accounts_service, "verify_account", fake_verify)
    response = client.post(
        "/api/accounts",
        json={
            "provider": "qq",
            "email": "student@qq.com",
            "password": "wrong-code",
        },
    )
    assert response.status_code == 400
    assert "授权码" in response.json()["detail"]


def test_account_creation_defaults_to_seven_sync_days(client, monkeypatch):
    import app.services.accounts as accounts_service

    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    monkeypatch.setattr(client.app.state.sync_manager, "trigger", lambda *args, **kwargs: True)

    response = client.post(
        "/api/accounts",
        json={
            "provider": "qq",
            "email": "student@qq.com",
            "password": "test-auth-code",
        },
    )
    assert response.status_code == 201
    account = response.json()["account"]
    assert account["sync_days"] == 7

    assert client.delete(f"/api/accounts/{account['id']}").status_code == 200


def test_account_crud_without_network(client, monkeypatch, settings):
    import app.services.accounts as accounts_service

    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    app = client.app
    manager = app.state.sync_manager
    monkeypatch.setattr(manager, "trigger", lambda *args, **kwargs: True)

    response = client.post(
        "/api/accounts",
        json={
            "provider": "qq",
            "email": "student@qq.com",
            "password": "test-auth-code",
            "label": "主邮箱",
            "sync_days": 14,
        },
    )
    assert response.status_code == 201
    account = response.json()["account"]
    assert account["email"] == "student@qq.com"
    assert "password" not in account
    assert account["last_sync_status"] == "idle"
    assert account["sync_days"] == 14

    accounts = client.get("/api/accounts").json()
    assert len(accounts) == 1

    updated = client.patch(
        f"/api/accounts/{account['id']}",
        json={"auto_sync": False, "label": "招聘邮箱", "sync_days": 60},
    )
    assert updated.status_code == 200
    assert updated.json()["auto_sync"] is False
    assert updated.json()["label"] == "招聘邮箱"
    assert updated.json()["sync_days"] == 60

    assert client.post(f"/api/accounts/{account['id']}/sync").status_code == 202
    assert client.post(f"/api/accounts/{account['id']}/rescan").status_code == 202
    assert client.post("/api/sync-all").status_code == 202

    deleted = client.delete(f"/api/accounts/{account['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/accounts").json() == []


def test_clear_account_messages_keeps_account_and_other_mailboxes(
    client, monkeypatch
):
    import app.services.accounts as accounts_service

    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    monkeypatch.setattr(
        client.app.state.sync_manager, "trigger", lambda *args, **kwargs: True
    )

    def create_account(email: str) -> dict:
        response = client.post(
            "/api/accounts",
            json={
                "provider": "qq",
                "email": email,
                "password": "test-auth-code",
            },
        )
        assert response.status_code == 201
        return response.json()["account"]

    first = create_account("first@qq.com")
    second = create_account("second@qq.com")
    db = client.app.state.db
    now = "2026-10-21T00:00:00+00:00"
    db.execute(
        "UPDATE accounts SET last_uid = 42, uidvalidity = 'v1', "
        "last_sync_status = 'ok', last_sync_at = ?, last_sync_counts = '{}' "
        "WHERE id = ?",
        (now, first["id"]),
    )
    first_event = db.execute(
        "INSERT INTO events (account_id, kind, company, created_at, updated_at) "
        "VALUES (?, 'exam', '甲公司', ?, ?)",
        (first["id"], now, now),
    )
    db.execute(
        "INSERT INTO events (account_id, kind, company, created_at, updated_at) "
        "VALUES (?, 'interview', '乙公司', ?, ?)",
        (second["id"], now, now),
    )
    db.execute(
        "INSERT INTO events (kind, company, created_at, updated_at) "
        "VALUES ('exam', '手动记录', ?, ?)",
        (now, now),
    )
    db.execute(
        "INSERT INTO seen_messages (account_id, message_key, outcome, event_id, seen_at) "
        "VALUES (?, 'first-message', 'created', ?, ?)",
        (first["id"], first_event, now),
    )
    db.execute(
        "INSERT INTO seen_messages (account_id, message_key, outcome, event_id, seen_at) "
        "VALUES (?, 'second-message', 'created', NULL, ?)",
        (second["id"], now),
    )

    cleared = client.delete(f"/api/accounts/{first['id']}/messages")
    assert cleared.status_code == 200
    assert cleared.json() == {
        "cleared": True,
        "reset_cursor": False,
        "events": 1,
        "messages": 1,
    }

    accounts = client.get("/api/accounts").json()
    assert {account["id"] for account in accounts} == {first["id"], second["id"]}
    events = client.get("/api/events").json()
    assert {event["company"] for event in events} == {"乙公司", "手动记录"}
    seen = db.fetch_all("SELECT account_id, message_key FROM seen_messages")
    assert seen == [{"account_id": second["id"], "message_key": "second-message"}]
    first_row = db.fetch_one(
        "SELECT last_uid, uidvalidity, last_sync_status, last_sync_counts "
        "FROM accounts WHERE id = ?",
        (first["id"],),
    )
    assert first_row == {
        "last_uid": 42,
        "uidvalidity": "v1",
        "last_sync_status": "ok",
        "last_sync_counts": None,
    }

    assert client.delete("/api/accounts/9999/messages").status_code == 404


def test_clear_account_messages_can_reset_sync_cursor(client, monkeypatch):
    import app.services.accounts as accounts_service

    monkeypatch.setattr(accounts_service, "verify_account", lambda account: None)
    monkeypatch.setattr(
        client.app.state.sync_manager, "trigger", lambda *args, **kwargs: True
    )
    response = client.post(
        "/api/accounts",
        json={
            "provider": "qq",
            "email": "reset@qq.com",
            "password": "test-auth-code",
        },
    )
    assert response.status_code == 201
    account = response.json()["account"]
    db = client.app.state.db
    now = "2026-10-21T00:00:00+00:00"
    db.execute(
        "UPDATE accounts SET last_uid = 42, uidvalidity = 'v1', "
        "last_sync_status = 'ok', last_sync_at = ?, "
        "last_sync_counts = '{\"created\": 1}' WHERE id = ?",
        (now, account["id"]),
    )
    event_id = db.execute(
        "INSERT INTO events (account_id, kind, company, created_at, updated_at) "
        "VALUES (?, 'exam', '甲公司', ?, ?)",
        (account["id"], now, now),
    )
    db.execute(
        "INSERT INTO seen_messages (account_id, message_key, outcome, event_id, seen_at) "
        "VALUES (?, 'reset-message', 'created', ?, ?)",
        (account["id"], event_id, now),
    )

    cleared = client.delete(
        f"/api/accounts/{account['id']}/messages?reset_cursor=true"
    )
    assert cleared.status_code == 200
    assert cleared.json() == {
        "cleared": True,
        "reset_cursor": True,
        "events": 1,
        "messages": 1,
    }
    row = db.fetch_one(
        "SELECT last_uid, uidvalidity, last_sync_status, last_sync_at, "
        "last_sync_counts FROM accounts WHERE id = ?",
        (account["id"],),
    )
    assert row == {
        "last_uid": 0,
        "uidvalidity": None,
        "last_sync_status": "idle",
        "last_sync_at": None,
        "last_sync_counts": None,
    }


def test_ai_settings_api_encrypts_key_and_clear(client):
    default = client.get("/api/ai-settings")
    assert default.status_code == 200
    assert default.json()["active"] is False
    assert default.json()["has_api_key"] is False

    response = client.put(
        "/api/ai-settings",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "api_key": "sk-test-secret",
            "max_calls_per_sync": 6,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["has_api_key"] is True
    assert "api_key" not in data
    stored = client.app.state.db.fetch_one(
        "SELECT value FROM app_settings WHERE key = 'llm_api_key_enc'"
    )
    assert stored and stored["value"] != "sk-test-secret"

    invalid = client.put(
        "/api/ai-settings",
        json={"base_url": "", "model": "", "api_key": "sk-another"},
    )
    assert invalid.status_code == 400

    cleared = client.put(
        "/api/ai-settings",
        json={
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "clear_api_key": True,
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["active"] is False
    assert cleared.json()["has_api_key"] is False

    unavailable = client.post("/api/ai-settings/test")
    assert unavailable.status_code == 400


def test_mutations_require_ui_header(client):
    client.headers.pop("X-Campus-Radar-Request", None)
    response = client.post("/api/demo")
    assert response.status_code == 403
    assert response.json()["detail"] == "请求来源校验失败"
