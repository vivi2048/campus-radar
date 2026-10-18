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

    accounts = client.get("/api/accounts").json()
    assert len(accounts) == 1

    updated = client.patch(
        f"/api/accounts/{account['id']}",
        json={"auto_sync": False, "label": "招聘邮箱"},
    )
    assert updated.status_code == 200
    assert updated.json()["auto_sync"] is False
    assert updated.json()["label"] == "招聘邮箱"

    assert client.post(f"/api/accounts/{account['id']}/sync").status_code == 202
    assert client.post(f"/api/accounts/{account['id']}/rescan").status_code == 202
    assert client.post("/api/sync-all").status_code == 202

    deleted = client.delete(f"/api/accounts/{account['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/accounts").json() == []


def test_mutations_require_ui_header(client):
    client.headers.pop("X-Campus-Radar-Request", None)
    response = client.post("/api/demo")
    assert response.status_code == 403
    assert response.json()["detail"] == "请求来源校验失败"
