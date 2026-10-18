from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest

from app.db import Database
from app.extract.classify import Classification
from app.extract.pipeline import Analysis
from app.llm import (
    LLMConfig,
    LLMConfigError,
    LLMError,
    LLMFallback,
    build_analysis_from_payload,
    parse_llm_response,
    save_llm_settings,
    get_llm_settings_view,
    load_llm_config,
)
from app.mail.mime import ParsedEmail
from app.security import SecretBox


def _parsed(subject: str, body: str) -> ParsedEmail:
    return ParsedEmail(
        subject=subject,
        sender_name="招聘团队",
        sender_email="hr@example.com",
        received_at=datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc),
        body_text=body,
        html_text="",
        links=[],
    )


def _rejected(reason: str) -> Analysis:
    return Analysis(
        accepted=False,
        classification=Classification(accepted=False, score=1, rejection_reason=reason),
    )


def test_build_analysis_from_llm_payload():
    analysis = build_analysis_from_payload(
        {
            "is_event": True,
            "kind": "interview",
            "confidence": 0.88,
            "company": "示例科技",
            "role": "后端工程师",
            "interview_round": "一面",
            "start": "2026-10-25T14:00:00+08:00",
            "end": "2026-10-25T15:00:00+08:00",
            "time_known": True,
            "deadline": "2026-10-23",
            "deadline_time_known": False,
            "duration_minutes": 60,
            "platform": "腾讯会议",
            "url": "https://meeting.tencent.com/demo",
            "mode": "online",
            "access_code": "123 456 789",
            "notes": ["提前 10 分钟进入会议室"],
        }
    )
    assert analysis is not None
    assert analysis.kind == "interview"
    assert analysis.fields is not None and analysis.timing is not None
    assert analysis.fields.company == "示例科技"
    assert analysis.fields.interview_round == "一面"
    assert analysis.fields.exam_url == "https://meeting.tencent.com/demo"
    assert analysis.timing.exam_start == "2026-10-25T14:00+08:00"
    assert analysis.timing.deadline == "2026-10-23T23:59+08:00"
    assert analysis.timing.deadline_time_known is False
    assert analysis.needs_review is True
    assert "大模型兜底识别" in (analysis.auto_notes or "")


def test_parse_llm_response_handles_code_fence_and_rejects_noise():
    content = '```json\n{"is_event": true, "kind": "exam", "confidence": 0.9, "company": "A"}\n```'
    analysis = parse_llm_response(content)
    assert analysis is not None
    assert analysis.kind == "exam"
    assert analysis.fields.company == "A"

    assert parse_llm_response('{"is_event": false, "kind": "interview"}') is None
    with pytest.raises(LLMError):
        parse_llm_response("not json")


def test_llm_candidate_filter_allows_unsubscribe_in_exam_invite():
    parsed = _parsed(
        "来自麦当劳的考试邀请",
        "考试时间：2026-10-19 19:00-23:59，考试时长 60 分钟，点击这里取消订阅 unsubscribe。",
    )
    assert LLMFallback.should_consider(
        parsed,
        _rejected("有效信号不足，可能是流程通知或资讯邮件"),
    )


def test_llm_candidate_filter_skips_promotions():
    accepted = _parsed("面试邀请 - 后端工程师", "现邀请你参加视频面试，面试时间：10月25日 14:00。")
    assert LLMFallback.should_consider(accepted, _rejected("有效信号不足"))

    promo = _parsed("招聘日报：最新职位推荐", "本周职位推荐，退订请点击。")
    assert not LLMFallback.should_consider(promo, _rejected("主题是职位推荐或招聘资讯"))

    result = _parsed("面试结果通知", "感谢参加面试，结果已出。")
    assert not LLMFallback.should_consider(result, _rejected("主题是结果通知，不是新的安排"))


def test_llm_settings_encrypt_key_and_clear(tmp_path):
    db = Database(tmp_path / "settings.db")
    db.init()
    vault = SecretBox(tmp_path / ".secret.key")

    view = save_llm_settings(
        db,
        vault,
        {
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "api_key": "sk-test-secret",
            "max_calls_per_sync": 150,
        },
    )
    assert view["active"] is True
    assert view["has_api_key"] is True
    assert "api_key" not in view
    assert view["max_calls_per_sync"] == 150
    stored = db.fetch_one("SELECT value FROM app_settings WHERE key = 'llm_api_key_enc'")
    assert stored and stored["value"] != "sk-test-secret"

    config = load_llm_config(db, vault)
    assert config.api_key == "sk-test-secret"
    assert config.chat_url == "https://api.example.com/v1/chat/completions"

    cleared = save_llm_settings(
        db,
        vault,
        {
            "base_url": "https://api.example.com/v1",
            "model": "demo-model",
            "clear_api_key": True,
            "max_calls_per_sync": 8,
        },
    )
    assert cleared["active"] is False
    assert get_llm_settings_view(db)["has_api_key"] is False


def test_llm_settings_require_endpoint_when_key_present(tmp_path):
    db = Database(tmp_path / "settings.db")
    db.init()
    vault = SecretBox(tmp_path / ".secret.key")
    with pytest.raises(LLMConfigError):
        save_llm_settings(
            db,
            vault,
            {"base_url": "", "model": "", "api_key": "sk-test"},
        )


def test_llm_settings_reject_anthropic_base_url(tmp_path):
    db = Database(tmp_path / "settings.db")
    db.init()
    vault = SecretBox(tmp_path / ".secret.key")
    with pytest.raises(LLMConfigError, match="OpenAI"):
        save_llm_settings(
            db,
            vault,
            {
                "base_url": "https://api.deepseek.com/anthropic/v1",
                "model": "deepseek-flash",
                "api_key": "sk-test",
            },
        )


def test_llm_http_connection_uses_openai_compatible_endpoint(monkeypatch):
    captured: dict = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self, _limit):
            return json.dumps(
                {"choices": [{"message": {"content": '{"ok": true}'}}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("app.llm.urllib.request.urlopen", fake_urlopen)
    fallback = LLMFallback(
        LLMConfig(
            base_url="https://api.example.com/v1",
            model="demo-model",
            api_key="sk-test",
        ),
        logging.getLogger("campus-radar-test-llm"),
    )
    assert "连接成功" in fallback.test_connection()
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer sk-test"
    assert captured["body"]["model"] == "demo-model"
