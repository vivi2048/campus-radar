from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.extract.dates import extract_timings, normalize_timing_text
from app.extract.pipeline import analyze_email
from app.mail.mime import parse_raw_email

FIXTURES = Path(__file__).parent / "fixtures"
RECEIVED = datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)


def load_pipeline(name: str):
    parsed = parse_raw_email((FIXTURES / name).read_bytes())
    return parsed, analyze_email(parsed)


def test_chinese_nowcoder_invitation_full_extraction():
    parsed, analysis = load_pipeline("xingye_nowcoder.eml")
    assert analysis.accepted
    assert parsed.subject.startswith("【星野科技】")
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "星野科技"
    assert fields.role == "后端开发工程师"
    assert fields.platform == "牛客网"
    assert fields.exam_url == "https://www.nowcoder.com/test/start/abc123"
    assert fields.mode == "online"
    assert fields.access_code == "XINGYE2026"
    assert timing.exam_start == "2026-10-22T19:00+08:00"
    assert timing.exam_end == "2026-10-22T21:00+08:00"
    assert timing.exam_time_known is True
    assert timing.duration_minutes == 120
    assert analysis.needs_review is False
    assert "摄像头" in (analysis.auto_notes or "")


def test_relative_deadline_and_missing_company_marks_review():
    parsed, analysis = load_pipeline("yunfan_relative.eml")
    assert analysis.accepted
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "云帆咨询"
    assert fields.role == "管理培训生"
    assert timing.exam_start is None
    assert timing.deadline is not None
    assert timing.deadline.startswith("2026-10-18T10:00")
    assert analysis.needs_review is True
    assert "48" in (analysis.auto_notes or "")


def test_offline_exam_afternoon_range_and_confirmation_deadline():
    _, analysis = load_pipeline("offline_exam.eml")
    assert analysis.accepted
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "青禾银行"
    assert fields.role == "金融科技岗"
    assert fields.mode == "offline"
    assert "金融大街" in (fields.location or "")
    assert timing.exam_start == "2026-10-25T14:30+08:00"
    assert timing.exam_end == "2026-10-25T16:30+08:00"
    assert timing.deadline == "2026-10-23T23:59+08:00"
    assert timing.duration_minutes == 120


def test_english_assessment_time_and_duration():
    _, analysis = load_pipeline("english_hackerrank.eml")
    assert analysis.accepted
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "Northstar Labs"
    assert fields.role == "Software Engineer"
    assert fields.platform == "HackerRank"
    assert timing.exam_start == "2026-10-24T19:00+08:00"
    assert timing.exam_end == "2026-10-24T20:30+08:00"
    assert timing.duration_minutes == 90


@pytest.mark.parametrize(
    "fixture",
    ["interview_invite.eml", "marketing_questions.eml", "exam_result.eml"],
)
def test_non_exam_emails_are_rejected(fixture: str):
    _, analysis = load_pipeline(fixture)
    assert analysis.accepted is False


def test_reminder_extracts_clean_role():
    _, analysis = load_pipeline("xingye_reminder.eml")
    assert analysis.accepted
    assert analysis.fields is not None
    assert analysis.fields.company == "星野科技"
    assert analysis.fields.role == "后端开发工程师"


def test_exam_window_start_and_deadline():
    text = "测评有效期：2026年10月20日 10:00 至 2026年10月22日 22:00"
    timing = extract_timings(text, RECEIVED)
    assert timing.exam_start == "2026-10-20T10:00+08:00"
    assert timing.deadline == "2026-10-22T22:00+08:00"
    assert timing.exam_time_known is True


def test_relative_deadline_from_received_time():
    timing = extract_timings("请在收到本邮件后 48 小时内完成在线测评", RECEIVED)
    assert timing.exam_start is None
    assert timing.deadline == "2026-10-20T10:00+08:00"
    assert timing.deadline_note


def test_chinese_time_immediately_after_colon():
    text = "笔试时间：19:00-21:00\n考试日期：2026年10月22日"
    timing = extract_timings(text, RECEIVED)
    assert timing.exam_start == "2026-10-22T19:00+08:00"
    assert timing.exam_end == "2026-10-22T21:00+08:00"


def test_deadline_without_exam_time():
    timing = extract_timings(
        "请于 2026年10月23日 23:59 前完成本次在线测评",
        RECEIVED,
    )
    assert timing.exam_start is None
    assert timing.deadline == "2026-10-23T23:59+08:00"


def test_normalize_time_variants():
    prepared = normalize_timing_text("下午2:30-4:30，晚上7点开始，7:00 PM-8:30 PM")
    assert "14:30-4:30" in prepared
    assert "19:00" in prepared
    assert "19:00-20:30" in prepared
