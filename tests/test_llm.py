from __future__ import annotations

import io
import json
import logging
import urllib.error
from datetime import datetime, timezone

import pytest

from app.db import Database
from app.extract.classify import Classification
from app.extract.pipeline import Analysis
from app.llm import (
    INITIAL_MAX_TOKENS,
    RETRY_MAX_TOKENS,
    ChatResponse,
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
    assert "大模型识别" in (analysis.auto_notes or "")


def test_payload_category_gate_rejects_non_actionable_mail():
    base = {
        "category": "marketing",
        "actionable": False,
        "is_event": False,
        "kind": "exam",
        "confidence": 0.99,
        "company": "示例教育",
    }
    assert build_analysis_from_payload(base) is None

    result = {
        **base,
        "category": "result",
        "actionable": True,
        "is_event": True,
    }
    assert build_analysis_from_payload(result) is None

    invite = {
        **base,
        "category": "exam_invite",
        "actionable": True,
        "is_event": True,
        "start": "2026-10-20T19:00:00+08:00",
        "time_known": True,
    }
    assert build_analysis_from_payload(invite) is not None
    assert build_analysis_from_payload({**invite, "category": "考试邀请"}) is not None
    assert build_analysis_from_payload({**invite, "category": "广告"}) is None


def test_evidence_reparses_start_and_deadline_locally():
    parsed = _parsed(
        "考试邀请",
        "考试时间：2026年10月22日 19:00，请准时参加。"
        "截止时间：2026年10月20日 18:00。",
    )
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.9,
            "company": "示例科技",
            "start": "2026-10-20T10:00:00+08:00",
            "time_known": True,
            "deadline": "2026-10-19T10:00:00+08:00",
            "deadline_time_known": True,
            "evidence": {
                "start": "考试时间：2026年10月22日 19:00",
                "deadline": "截止时间：2026年10月20日 18:00",
            },
        },
        parsed,
    )
    assert analysis is not None and analysis.timing is not None
    assert analysis.timing.exam_start == "2026-10-22T19:00+08:00"
    assert analysis.timing.deadline == "2026-10-20T18:00+08:00"


def test_evidence_deadline_window_uses_closing_time():
    parsed = _parsed(
        "测评邀请",
        "本次测试邀请于2026年09月30日 11:59生效，"
        "于2026年10月07日 12:00失效。",
    )
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.9,
            "company": "示例科技",
            "start": "2026-09-30T11:59:00+08:00",
            "time_known": True,
            "deadline": "2026-10-07T12:00:00+08:00",
            "deadline_time_known": True,
            "evidence": {
                "start": "本次测试邀请于2026年09月30日 11:59生效",
                "deadline": (
                    "本次测试邀请于2026年09月30日 11:59生效，"
                    "于2026年10月07日 12:00失效"
                ),
            },
        },
        parsed,
    )
    assert analysis is not None and analysis.timing is not None
    assert analysis.timing.deadline == "2026-10-07T12:00+08:00"


def test_evidence_opening_only_keeps_model_deadline():
    parsed = _parsed(
        "笔试邀请",
        "本次测试邀请于2026年10月14日 09:01生效，请在60分钟内完成测试。",
    )
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.9,
            "company": "示例科技",
            "start": "2026-10-14T09:01:00+08:00",
            "time_known": True,
            "deadline": "2026-10-21T09:01:00+08:00",
            "deadline_time_known": True,
            "evidence": {
                "start": "本次测试邀请于2026年10月14日 09:01生效",
                "deadline": "本次测试邀请于2026年10月14日 09:01生效",
            },
        },
        parsed,
    )
    assert analysis is not None and analysis.timing is not None
    assert analysis.timing.deadline == "2026-10-21T09:01+08:00"


def test_evidence_exam_range_uses_window_close():
    parsed = _parsed(
        "笔试邀请",
        "考试时间：2026-09-29 00:00:00 ~ 2026-09-30 00:00:00，考试时长120分钟。",
    )
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.9,
            "company": "示例科技",
            "start": "2026-09-29T00:00:00+08:00",
            "time_known": True,
            "deadline": "2026-09-30T00:00:00+08:00",
            "deadline_time_known": True,
            "duration_minutes": 120,
            "start_is_window": True,
            "evidence": {
                "start": "考试时间：2026-09-29 00:00:00",
                "deadline": (
                    "考试时间：2026-09-29 00:00:00 ~ "
                    "2026-09-30 00:00:00"
                ),
            },
        },
        parsed,
    )
    assert analysis is not None and analysis.timing is not None
    assert analysis.timing.exam_start == "2026-09-29T00:00+08:00"
    assert analysis.timing.deadline == "2026-09-30T00:00+08:00"


def test_llm_sanitizes_full_line_url_and_location():
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.9,
            "company": "中国电信",
            "start": "2026-10-17T09:00:00+08:00",
            "time_known": True,
            "url": (
                "计算机类：北京时间10月17日 09:00-11:00（周六），"
                "笔试地址：https://exam.nowcoder.com/cts/17529695/summary?id=abc"
            ),
            "location": (
                "计算机类：北京时间10月17日 09:00-11:00（周六），"
                "笔试地址：https://exam.nowcoder.com/cts/17529695/summary?id=abc"
            ),
        }
    )
    assert analysis is not None and analysis.fields is not None
    assert analysis.fields.exam_url == (
        "https://exam.nowcoder.com/cts/17529695/summary?id=abc"
    )
    assert analysis.fields.location is None


def test_llm_window_start_does_not_fabricate_end():
    parsed = _parsed(
        "笔试邀请",
        "本次测试邀请于2026年10月14日 09:01生效，请在60分钟内完成测试。"
        "本次测试邀请于2026年10月21日 09:01截止。",
    )
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.95,
            "company": "中国外运",
            "start": "2026-10-14T09:01:00+08:00",
            "end": None,
            "time_known": True,
            "start_is_window": True,
            "deadline": "2026-10-21T09:01:00+08:00",
            "deadline_time_known": True,
            "duration_minutes": 60,
            "evidence": {
                "start": "本次测试邀请于2026年10月14日 09:01生效",
                "deadline": "本次测试邀请于2026年10月21日 09:01截止",
            },
        },
        parsed,
    )
    assert analysis is not None and analysis.timing is not None
    assert analysis.timing.exam_start == "2026-10-14T09:01+08:00"
    assert analysis.timing.exam_end is None
    assert analysis.timing.deadline == "2026-10-21T09:01+08:00"
    assert analysis.timing.start_is_window is True


def test_missing_time_evidence_is_flagged_for_review():
    parsed = _parsed("考试邀请", "请参加本周的在线测评。")
    analysis = build_analysis_from_payload(
        {
            "category": "exam_invite",
            "actionable": True,
            "is_event": True,
            "kind": "exam",
            "confidence": 0.8,
            "company": "示例科技",
            "start": "2026-10-20T19:00:00+08:00",
            "time_known": True,
        },
        parsed,
    )
    assert analysis is not None
    assert "缺少可核对" in (analysis.auto_notes or "")


def test_parse_llm_response_handles_code_fence_and_rejects_noise():
    content = '```json\n{"is_event": true, "kind": "exam", "confidence": 0.9, "company": "A"}\n```'
    analysis = parse_llm_response(content)
    assert analysis is not None
    assert analysis.kind == "exam"
    assert analysis.fields.company == "A"

    assert parse_llm_response('{"is_event": false, "kind": "interview"}') is None
    with pytest.raises(LLMError):
        parse_llm_response("not json")


def test_llm_retries_with_larger_budget_when_reasoning_truncates(monkeypatch):
    fallback = LLMFallback(
        LLMConfig(
            base_url="https://api.example.com/v1",
            model="reasoning-model",
            api_key="sk-test",
        ),
        logging.getLogger("campus-radar-test-llm-retry"),
    )
    calls: list[int] = []
    payload = {
        "category": "exam_invite",
        "actionable": True,
        "is_event": True,
        "kind": "exam",
        "confidence": 0.9,
        "company": "示例科技",
        "start": "2026-10-22T19:00:00+08:00",
        "time_known": True,
    }

    def fake_chat(messages, *, max_tokens):
        calls.append(max_tokens)
        if len(calls) == 1:
            return ChatResponse(
                content="",
                finish_reason="length",
                reasoning_chars=7000,
                completion_tokens=INITIAL_MAX_TOKENS,
            )
        return ChatResponse(content=json.dumps(payload), finish_reason="stop")

    monkeypatch.setattr(fallback, "_chat", fake_chat)
    analysis = fallback.analyze(_parsed("考试邀请", "考试时间：2026年10月22日 19:00"))
    assert analysis is not None
    assert calls == [INITIAL_MAX_TOKENS, RETRY_MAX_TOKENS]


def test_llm_does_not_treat_reasoning_as_answer(monkeypatch):
    fallback = LLMFallback(
        LLMConfig(
            base_url="https://api.example.com/v1",
            model="reasoning-model",
            api_key="sk-test",
        ),
        logging.getLogger("campus-radar-test-llm-reasoning"),
    )
    calls: list[int] = []

    def fake_chat(messages, *, max_tokens):
        calls.append(max_tokens)
        return ChatResponse(
            content="",
            finish_reason="stop",
            reasoning_chars=1200,
        )

    monkeypatch.setattr(fallback, "_chat", fake_chat)
    with pytest.raises(LLMError, match="空内容"):
        fallback.analyze(_parsed("考试邀请", "考试时间：2026年10月22日 19:00"))
    assert calls == [INITIAL_MAX_TOKENS, RETRY_MAX_TOKENS]


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


def test_llm_candidate_filter_gives_locally_accepted_promo_a_second_look():
    accepted = Analysis(
        accepted=True,
        classification=Classification(accepted=True, score=5),
    )
    promo = _parsed(
        "招聘日报：最新职位推荐",
        "本周职位推荐，包含面试机会和最新职位，退订请点击。",
    )
    assert LLMFallback.should_consider(promo, accepted)


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
            "concurrency": 6,
        },
    )
    assert view["active"] is True
    assert view["has_api_key"] is True
    assert "api_key" not in view
    assert view["max_calls_per_sync"] == 150
    assert view["concurrency"] == 6
    stored = db.fetch_one("SELECT value FROM app_settings WHERE key = 'llm_api_key_enc'")
    assert stored and stored["value"] != "sk-test-secret"

    config = load_llm_config(db, vault)
    assert config.api_key == "sk-test-secret"
    assert config.concurrency == 6
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
    assert get_llm_settings_view(db)["concurrency"] == 4


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
                {
                    "choices": [
                        {
                            "message": {"content": '{"ok": true}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"completion_tokens": 12},
                }
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
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_llm_json_mode_falls_back_when_endpoint_rejects_it(monkeypatch):
    bodies: list[dict] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self, _limit):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": '{"ok": true}'},
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        bodies.append(body)
        if len(bodies) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"error":"response_format is not supported"}'),
            )
        return FakeResponse()

    monkeypatch.setattr("app.llm.urllib.request.urlopen", fake_urlopen)
    fallback = LLMFallback(
        LLMConfig(
            base_url="https://api.example.com/v1",
            model="demo-model",
            api_key="sk-test",
        ),
        logging.getLogger("campus-radar-test-llm-json-fallback"),
    )
    assert "连接成功" in fallback.test_connection()
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
