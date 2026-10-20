from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.extract.dates import extract_timings, normalize_timing_text
from app.extract.classify import classify_email
from app.extract.fields import extract_fields
from app.extract.pipeline import analyze_email
from app.mail.mime import EmailLink, ParsedEmail, parse_raw_email

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


def test_exam_address_line_with_url_is_not_location():
    url = "https://exam.nowcoder.com/cts/17529695/summary?id=abc"
    fields = extract_fields(
        "中国电信线上笔试邀请",
        (
            "恭喜您进入中国电信湖北分公司校园招聘线上笔试环节。\n"
            "考试地址：\n"
            f"计算机类：北京时间10月17日 09:00-11:00（周六），笔试地址：{url}"
        ),
        "中国电信招聘",
        "campus@chinatelecom.com.cn",
        [EmailLink(url=url)],
    )
    assert fields.exam_url == url
    assert fields.location is None
    assert fields.mode == "online"

    physical = extract_fields(
        "线下笔试邀请",
        "考试地点：北京市海淀区中关村大街1号 A座 301",
        "示例公司",
        "hr@example.com",
        [],
    )
    assert "中关村大街" in (physical.location or "")


def test_english_assessment_time_and_duration():
    _, analysis = load_pipeline("english_hackerrank.eml")
    assert analysis.accepted
    assert analysis.kind == "exam"
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "Northstar Labs"
    assert fields.role == "Software Engineer"
    assert fields.platform == "HackerRank"
    assert timing.exam_start == "2026-10-24T19:00+08:00"
    assert timing.exam_end == "2026-10-24T20:30+08:00"
    assert timing.duration_minutes == 90


def test_chinese_interview_invitation_extraction():
    parsed, analysis = load_pipeline("interview_invite.eml")
    assert analysis.accepted
    assert analysis.kind == "interview"
    assert analysis.classification.kind == "interview"
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "远山资本"
    assert fields.role == "投资分析师"
    assert fields.exam_url == "https://meeting.example.com/abc"
    assert fields.mode == "online"
    assert timing.exam_start == "2026-10-23T14:00+08:00"
    assert timing.exam_time_known is True
    assert analysis.needs_review is False


def test_english_video_interview_extraction():
    _, analysis = load_pipeline("english_interview.eml")
    assert analysis.accepted
    assert analysis.kind == "interview"
    fields = analysis.fields
    timing = analysis.timing
    assert fields is not None and timing is not None
    assert fields.company == "Northstar Labs"
    assert fields.role == "Software Engineer"
    assert fields.platform == "Zoom"
    assert fields.exam_url == "https://zoom.us/j/1234567890"
    assert "123 456 7890" in (fields.access_code or "")
    assert "246810" in (fields.access_code or "")
    assert fields.mode == "online"
    assert timing.exam_start == "2026-10-26T14:00+08:00"
    assert timing.exam_end == "2026-10-26T15:00+08:00"
    assert timing.duration_minutes == 60
    assert "microphone" in (analysis.auto_notes or "")


@pytest.mark.parametrize(
    "fixture",
    [
        "marketing_questions.eml",
        "exam_result.eml",
        "interview_result.eml",
        "interview_prep.eml",
    ],
)
def test_non_event_emails_are_rejected(fixture: str):
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


def test_effective_time_is_start_and_trailing_deadline_is_not_start():
    text = (
        "本次测试邀请于2026年10月14日 周三 09:01生效，请在60分钟内完成测试。\n"
        "本次测试邀请于2026年10月21日 周三 09:01 截止，请尽快作答。"
    )
    timing = extract_timings(
        text,
        datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc),
    )
    assert timing.exam_start == "2026-10-14T09:01+08:00"
    assert timing.exam_end is None
    assert timing.exam_time_known is True
    assert timing.deadline == "2026-10-21T09:01+08:00"
    assert timing.deadline_time_known is True
    assert timing.duration_minutes == 60
    assert timing.start_is_window is True
    assert "有效窗口" in (timing.start_note or "")


def test_exam_period_range_starts_at_window_open():
    text = (
        "考试期间：（北京时间）2026-10-16 23:41 ~ 2026-10-23 23:41\n"
        "考试时长：60 分钟"
    )
    timing = extract_timings(
        text,
        datetime(2026, 10, 16, 15, 41, tzinfo=timezone.utc),
    )
    assert timing.exam_start == "2026-10-16T23:41+08:00"
    assert timing.exam_end is None
    assert timing.deadline == "2026-10-23T23:41+08:00"
    assert timing.duration_minutes == 60
    assert timing.start_is_window is True


def test_maintenance_window_is_not_used_as_interview_time():
    text = (
        "整场面试时间约为15分钟。\n"
        "请留意另一封在线测评邀请邮件，并于收到邮件的48小时内完成作答。\n"
        "注意：北京时间9月19日 00:00至9月19日09:00 AI面试官将进行产品升级，"
        "AI面试暂时锁定无法作答，请您避开此时间段进行答题。"
    )
    timing = extract_timings(
        text,
        datetime(2026, 10, 15, 6, 3, tzinfo=timezone.utc),
        kind="interview",
    )
    assert timing.exam_start is None
    assert timing.deadline is None
    assert timing.exam_start != "2026-09-19T00:00+08:00"
    assert timing.deadline != "2026-09-19T09:00+08:00"


def test_deadline_for_another_email_is_not_applied():
    text = "请留意另一封在线测评邀请邮件，并于收到邮件的48小时内完成作答。"
    received = datetime(2026, 10, 15, 6, 3, tzinfo=timezone.utc)
    interview = extract_timings(text, received, kind="interview")
    assert interview.exam_start is None
    assert interview.deadline is None

    assessment = extract_timings(text, received, kind="exam")
    assert assessment.exam_start == "2026-10-15T14:03+08:00"
    assert assessment.deadline == "2026-10-17T14:03+08:00"


def test_real_interview_time_survives_nearby_maintenance_window():
    text = (
        "面试时间：2026年10月20日 14:00。\n"
        "注意：北京时间9月19日 00:00至9月19日09:00 系统升级，"
        "AI面试暂时锁定无法作答，请避开此时段。"
    )
    timing = extract_timings(
        text,
        datetime(2026, 10, 15, 6, 3, tzinfo=timezone.utc),
        kind="interview",
    )
    assert timing.exam_start == "2026-10-20T14:00+08:00"
    assert timing.deadline is None


def test_effective_window_marks_event_for_review():
    parsed = ParsedEmail(
        subject="中国外运2027届校园招聘笔试邀请",
        sender_name="中国外运招聘",
        sender_email="campus@sinotrans.com",
        received_at=datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc),
        body_text=(
            "恭喜您通过简历筛选，现邀请您参加中国外运股份有限公司2027届校园招聘笔试。\n"
            "本次测试邀请于2026年10月14日 周三 09:01生效，请在60分钟内完成测试。\n"
            "本次测试邀请于2026年10月21日 周三 09:01 截止，请尽快作答。"
        ),
        html_text="",
        links=[],
    )
    analysis = analyze_email(parsed)
    assert analysis.accepted
    assert analysis.timing is not None
    assert analysis.timing.exam_start == "2026-10-14T09:01+08:00"
    assert analysis.timing.deadline == "2026-10-21T09:01+08:00"
    assert analysis.needs_review is True
    assert "有效窗口" in (analysis.auto_notes or "")


def test_relative_deadline_from_received_time():
    timing = extract_timings("请在收到本邮件后 48 小时内完成在线测评", RECEIVED)
    assert timing.exam_start == "2026-10-18T10:00+08:00"
    assert timing.exam_time_known is True
    assert timing.start_estimated is False
    assert timing.start_is_window is True
    assert timing.deadline == "2026-10-20T10:00+08:00"
    assert timing.deadline_note
    assert "收件时间" in (timing.start_note or "")


def test_natural_days_after_receipt_use_received_time_as_start():
    timing = extract_timings("请在收到笔试题后的3个自然日内完成。", RECEIVED)
    assert timing.exam_start == "2026-10-18T10:00+08:00"
    assert timing.exam_end is None
    assert timing.exam_time_known is True
    assert timing.deadline == "2026-10-21T10:00+08:00"
    assert timing.deadline_time_known is True
    assert timing.start_estimated is False
    assert timing.start_is_window is True
    assert "3 个自然日" in (timing.deadline_note or "")
    assert "收件时间" in (timing.start_note or "")


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
    assert timing.exam_start == "2026-10-18T14:00+08:00"
    assert timing.exam_time_known is True
    assert timing.start_estimated is True
    assert timing.deadline == "2026-10-23T23:59+08:00"


def test_urgent_completion_without_deadline_gets_estimated_slot():
    timing = extract_timings("请尽快完成在线笔试，考试时长 60 分钟", RECEIVED)
    assert timing.exam_start == "2026-10-18T14:00+08:00"
    assert timing.exam_end == "2026-10-18T15:00+08:00"
    assert timing.start_estimated is True
    assert timing.deadline is None


def test_confirmation_deadline_does_not_create_fake_interview_time():
    timing = extract_timings(
        "面试时间待定，请于2026年10月20日前回复确认是否参加",
        RECEIVED,
        kind="interview",
    )
    assert timing.exam_start is None
    assert timing.deadline == "2026-10-20T23:59+08:00"
    assert timing.start_estimated is False


def test_exam_invitation_with_result_words_and_unsubscribe_is_accepted():
    subject = "来自麦当劳的考试邀请"
    body = (
        "感谢您投递麦当劳中国IT 2027届校园招聘软件开发工程师岗位，您已进入测评环节。"
        "笔试成绩将成为是否进入后续面试流程的重要参考。\n"
        "笔试信息\n"
        "考试时间：2026-10-19 19:00-23:59\n"
        "考试时长：60分钟\n"
        "考试链接：https://www.nowcoder.com/test/start/mcd-demo\n"
        "点击这里取消订阅 click to unsubscribe"
    )
    result = classify_email(
        subject,
        body,
        [EmailLink("https://www.nowcoder.com/test/start/mcd-demo", "考试链接")],
        sender_email="mcdchina-no-reply@example.com",
        sender_name="麦当劳招聘",
    )
    assert result.accepted is True
    assert result.kind == "exam"


def test_info_session_thank_you_and_offer_are_rejected():
    samples = [
        (
            "【10月12日 19:00】赛美特集团2027届第二批次校招空宣，岗位薪资福利揭秘",
            "赛美特集团校园招聘空中宣讲会，将于今晚 7 点开始。",
        ),
        (
            "【帆软招聘】帆软校园招聘简历投递成功通知",
            "感谢您投递帆软校园招聘，我们已经收到您的简历。",
        ),
        (
            "感谢您投递本公司职位",
            "感谢您投递我公司的软件开发工程师职位，我们已经收到您的简历。",
        ),
        (
            "孙华峰欢迎加入ThunderSoft",
            "恭喜你通过面试，现向你发出正式 Offer，请在 10 月 14 日前接受。",
        ),
        (
            "途虎养车 | 笔试意向调研",
            "请填写问卷，反馈你希望参加笔试的时间段。",
        ),
        (
            "【新凯来招聘-在线笔试场次预约邀请】请您反馈可以参加的笔试场次",
            "请于截止时间前反馈可以参加的笔试场次。",
        ),
    ]
    for subject, body in samples:
        assert classify_email(subject, body, []).accepted is False


def test_interview_time_and_confirmation_deadline():
    text = "面试时间：2026年10月23日下午2:00\n请于10月21日18:00前回复邮件确认是否参加面试"
    timing = extract_timings(text, RECEIVED, kind="interview")
    assert timing.exam_start == "2026-10-23T14:00+08:00"
    assert timing.deadline == "2026-10-21T18:00+08:00"
    assert timing.exam_time_known is True


def test_interview_survey_and_profile_requests_are_rejected():
    survey = classify_email(
        "【恒生校招面试满意度调研】诚邀你对本次面试进行评价",
        "感谢你参加面试，现邀请你对此次面试做出评价。",
        [],
    )
    assert survey.accepted is False
    profile = classify_email(
        "北京某公司邀请完善校招网申资料",
        "为尽快推进面试流程，现邀请你更新并补充应聘资料。",
        [],
    )
    assert profile.accepted is False


def test_interview_relative_validity_window():
    timing = extract_timings(
        "面试有效期：收到通知起3天内有效",
        RECEIVED,
        kind="interview",
    )
    assert timing.deadline == "2026-10-21T10:00+08:00"


def test_received_email_possessive_and_bare_day_windows():
    first = extract_timings("请于收到邮件的48小时内完成在线测评", RECEIVED)
    assert first.deadline == "2026-10-20T10:00+08:00"
    assert first.exam_start == "2026-10-18T10:00+08:00"

    second = extract_timings("请于2天内点击链接进行网络测评", RECEIVED)
    assert second.deadline == "2026-10-20T10:00+08:00"
    assert second.exam_start == "2026-10-18T10:00+08:00"

    third = extract_timings("请在2天内一次性完成在线测评", RECEIVED)
    assert third.deadline == "2026-10-20T10:00+08:00"
    assert third.exam_start == "2026-10-18T10:00+08:00"
    assert third.start_is_window is True


def test_deadline_window_uses_closing_time():
    timing = extract_timings(
        "本次测试邀请于2026年09月30日 11:59生效，"
        "于2026年10月07日 12:00失效。",
        RECEIVED,
    )
    assert timing.deadline == "2026-10-07T12:00+08:00"
    assert timing.deadline_time_known is True

    ranged = extract_timings(
        "考试时间：2026-10-19 19:00:00-2026-10-19 23:59:59",
        RECEIVED,
    )
    assert ranged.exam_start == "2026-10-19T19:00+08:00"
    assert ranged.deadline == "2026-10-19T23:59+08:00"


def test_24_oclock_is_end_of_day():
    timing = extract_timings(
        "截止时间：请务必于北京时间2026年10月22日晚24点前确认是否参加笔试",
        RECEIVED,
    )
    assert timing.deadline == "2026-10-22T23:59+08:00"
    assert timing.deadline_time_known is True


def test_interview_waiting_threshold_is_not_duration():
    timing = extract_timings(
        "面试时间：2026-10-10 10:00\n"
        "如果超过面试约定时间 5 分钟面试官仍未上线，请与 HR 联系。",
        RECEIVED,
        kind="interview",
    )
    assert timing.exam_start == "2026-10-10T10:00+08:00"
    assert timing.duration_minutes is None


def test_ai_interview_round_from_subject():
    fields = extract_fields(
        "【宁德时代】2027届校园招聘AI面试邀请",
        "现邀请您参与完成AI面试，整场面试时间约为15分钟。",
        "CATL",
        "catl@example.com",
        [],
        kind="interview",
    )
    assert fields.interview_round == "AI面试"


def test_normalize_time_variants():
    prepared = normalize_timing_text("下午2:30-4:30，晚上7点开始，7:00 PM-8:30 PM")
    assert "14:30-4:30" in prepared
    assert "19:00" in prepared
    assert "19:00-20:30" in prepared
