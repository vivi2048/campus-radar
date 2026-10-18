from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..mail.mime import EmailLink
from .links import has_exam_link, has_interview_link

EXAM_TERM_RE = re.compile(
    r"笔试|测评|在线考试|线上考试|在线笔试|线上笔试|机考|编程测试|编程测评"
    r"|written\s+test|online\s+assessment|coding\s+(?:test|challenge)|assessment|\bexam\b",
    re.IGNORECASE,
)

INTERVIEW_TERM_RE = re.compile(
    r"面试|面谈|面试邀请|面试通知|面试安排|面试提醒|面试邀约|初试|复试|终试"
    r"|interview|phone\s+screen|video\s+interview|onsite\s+interview",
    re.IGNORECASE,
)

EXAM_SUBJECT_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"笔试\s*(?:邀请|通知|安排|提醒|确认|链接|入口|公告)|笔试.{0,5}(?:邀请|通知|安排|提醒)", 8),
    (r"(?:测评|考试)\s*(?:邀请|通知|安排|提醒|确认|链接|入口)", 7),
    (r"(?:在线|线上|远程)\s*(?:笔试|测评|考试)", 6),
    (r"(?:笔试|测评)\s*(?:时间|日期|地点|须知|倒计时)", 5),
    (r"机考|在线编程|编程测试|coding\s+(?:test|challenge)", 6),
    (r"written\s+test|online\s+assessment|(?:test|assessment|exam)\s+invitation", 7),
    (r"assessment|online\s+test|exam", 5),
    (r"笔试|测评|考试", 2),
)

INTERVIEW_SUBJECT_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"(?:面试|面谈)\s*(?:邀请|通知|安排|提醒|确认|邀约)", 8),
    (r"(?:邀请|诚邀|邀约).{0,12}(?:面试|面谈)", 8),
    (r"(?:一面|二面|三面|四面|终面|HR\s*面|hr\s*面|技术面|业务面|主管面|经理面|群面|交叉面|加面|初面|复面)", 7),
    (r"(?:视频|电话|现场|线上|线下|远程).{0,5}(?:面试|面谈|初试|复试|终面|终试)", 6),
    (r"(?:初试|复试|终试)\s*(?:邀请|通知|安排|提醒)", 5),
    (r"interview\s+(?:invitation|invite|schedule|confirmation)", 8),
    (r"(?:invit(?:e|ation)).{0,35}interview", 8),
    (r"interview.{0,25}(?:schedule|arranged|details|time|date)", 6),
    (r"面试|面谈|interview", 3),
)

HARD_REJECT_SUBJECT: tuple[tuple[str, str], ...] = (
    (r"笔经|面经|笔试真题|面试真题|真题|题库|模拟题|练习题|预测题|考试答案|答案分享", "主题看起来是备考资料"),
    (r"面试辅导|面试课程|面试技巧|模拟面试|mock\s+interview|interview\s+questions", "主题看起来是面试辅导或题库内容"),
    (r"面试(?:满意度|体验|调研|问卷|评价)|(?:满意度|调研|问卷|评价).{0,8}面试", "主题是面试问卷或满意度调研"),
    (r"(?:完善|更新|补充).{0,10}(?:网申|简历|应聘资料|申请资料)", "主题是完善应聘资料，不是新的安排"),
    (r"(?:笔试|面试)(?:结果|成绩|反馈|评价)(?:通知|查询|公布|已出)?\s*$", "主题是结果通知，不是新的安排"),
    (r"感谢(?:您|你).{0,6}(?:参加|参与).{0,8}面试|面试(?:已)?通过|通过面试", "主题是面试结果或感谢信"),
    (r"招聘日报|招聘周报|职位推荐|为你推荐|最新职位|内推群|海投", "主题是职位推荐或招聘资讯"),
    (r"广告|促销|优惠|折扣|课程报名|训练营|直播课", "主题看起来是推广内容"),
)

EXAM_INVITE_CUE = re.compile(
    r"(?:邀请|诚邀|提醒)(?:您|你)?(?:参加|参与|完成|登录|进入|作答)"
    r"|(?:笔试|测评|考试).{0,8}(?:邀请|入口|链接)"
    r"|(?:邀请|诚邀).{0,12}(?:笔试|测评|考试)"
    r"|请(?:您|你)?(?:于|在|尽快|及时)?.{0,35}(?:参加|完成|参与|登录|进入|点击|作答)"
    r"|(?:参加|完成|参与|进行|开始).{0,12}(?:笔试|测评|在线考试|考试)"
    r"|(?:点击|打开|进入).{0,10}(?:链接|入口|考试系统|测评系统|笔试系统)"
    r"|please.{0,30}(?:complete|take|start|access).{0,30}(?:test|assessment|exam)"
    r"|(?:invited|invitation).{0,40}(?:test|assessment|exam)",
    re.IGNORECASE,
)

INTERVIEW_INVITE_CUE = re.compile(
    r"(?:邀请|诚邀|邀约)(?:您|你)?(?:参加|参与|出席|进行|安排).{0,20}(?:面试|面谈|初试|复试|终面|终试)"
    r"|(?:面试|面谈|初试|复试|终面).{0,12}(?:邀请|邀约|安排|确认)"
    r"|(?:参加|进行|安排|开始).{0,12}(?:面试|面谈|初试|复试|终面|终试)"
    r"|(?:点击|打开|进入|加入).{0,12}(?:面试链接|会议链接|会议室|入会)"
    r"|please.{0,40}(?:attend|join|schedule|confirm).{0,40}interview"
    r"|(?:invite|invited|invitation).{0,45}interview"
    r"|we\s+would\s+like\s+to\s+invite\s+you",
    re.IGNORECASE,
)

EXAM_SCHEDULE_CUE = re.compile(
    r"考试时间|笔试时间|测评时间|作答时间|测试时间|开始时间|开放时间|开考时间"
    r"|考试日期|笔试日期|测评日期|考试安排|笔试安排|有效期至|截止(?:时间|日期|至)"
    r"|assessment\s+date|test\s+date|exam\s+date|start\s+time|deadline|due\s+by|opens?\s+at",
    re.IGNORECASE,
)

INTERVIEW_SCHEDULE_CUE = re.compile(
    r"面试时间|面谈时间|面试日期|面试安排|面试地点|面试地址|面试形式|初试时间|复试时间|终面时间"
    r"|一面时间|二面时间|终面时间|面试将于|面试定于"
    r"|interview\s+(?:time|date|schedule|details)"
    r"|(?:date|time)\s+of\s+(?:the\s+)?interview"
    r"|join\s+the\s+interview|interview\s+(?:on|at)",
    re.IGNORECASE,
)

EXAM_PARTICIPATION_CUE = re.compile(
    r"(?:参加|参与|完成|进行).{0,12}(?:笔试|测评|在线考试|考试)"
    r"|(?:笔试|测评|考试).{0,12}(?:开始|入口|链接|系统)",
    re.IGNORECASE,
)

INTERVIEW_PARTICIPATION_CUE = re.compile(
    r"(?:参加|参与|出席|进行|安排).{0,12}(?:面试|面谈|初试|复试|终面|终试)"
    r"|(?:面试|面谈|初试|复试|终面).{0,12}(?:开始|进行|会议|链接|地点)",
    re.IGNORECASE,
)

HR_CONTEXT = re.compile(
    r"校园招聘|校招|招聘|应聘|候选人|投递|岗位|职位|实习|管培|campus|recruit|career|talent|hiring",
    re.IGNORECASE,
)

EXAM_NEGATIVE_PATTERNS: tuple[tuple[str, int, str], ...] = (
    (r"笔试\s*(?:结果|成绩|通过|未通过|已通过|查询)", 7, "内容像是在通知笔试结果"),
    (r"(?:感谢|谢谢)(?:您|你)?(?:参加|参与).{0,16}(?:笔试|测评|考试)", 8, "内容像是在感谢已完成考试"),
    (r"已(?:完成|参加).{0,10}(?:笔试|测评)", 5, "内容提到考试已完成"),
    (r"笔试(?:时间|安排)(?:汇总|一览|日历)|考试日历|笔试时间表", 5, "内容像是笔试资讯汇总"),
    (r"模拟|练习|样题|sample\s+test|practice\s+test|mock\s+test", 6, "内容像是模拟练习"),
    (r"退订|unsubscribe|订阅偏好|邮件订阅", 2, "内容包含订阅退订信息"),
)

INTERVIEW_NEGATIVE_PATTERNS: tuple[tuple[str, int, str], ...] = (
    (r"面试\s*(?:结果|成绩|反馈|评价)|面试(?:已)?结束", 8, "内容像是在通知面试结果"),
    (r"(?:感谢|谢谢)(?:您|你)?(?:参加|参与).{0,16}(?:面试|面谈)", 8, "内容像是在感谢已完成面试"),
    (r"很抱歉|遗憾.{0,10}(?:无法|不能).{0,10}(?:安排|提供).{0,10}(?:后续|面试)", 8, "内容像是在结束流程"),
    (r"(?:感谢|谢谢)(?:您|你).{0,10}(?:参加|参与|关注).{0,20}(?:校园招聘|校招).{0,40}(?:无法|抱歉|调剂|人才)", 8, "内容像是在结束招聘流程"),
    (r"人才(?:库|调剂池)|不再推进|未通过", 4, "内容包含流程结果信息"),
    (r"面试(?:满意度|体验|调研|问卷|评价)|填写.{0,8}问卷|本次面试.{0,8}(?:评价|反馈)", 8, "内容像是面试问卷或调研"),
    (r"面试已经开始|轮到你面试|请立即前往.{0,30}面试", 6, "内容像是面试开始后的即时通知"),
    (r"(?:完善|更新|补充).{0,10}(?:网申|简历|资料)", 7, "内容是在要求完善应聘资料"),
    (r"面经|面试真题|面试题库|面试技巧|面试辅导|模拟面试|mock\s+interview", 7, "内容像是面试准备资料"),
    (r"退订|unsubscribe|订阅偏好|邮件订阅", 2, "内容包含订阅退订信息"),
)


@dataclass
class Classification:
    accepted: bool
    score: float
    kind: str = ""
    reasons: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    subject_strength: int = 0
    has_invite_cue: bool = False
    has_schedule_cue: bool = False
    has_event_link: bool = False


def normalize_for_rules(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text)


def _subject_strength(
    subject: str, patterns: tuple[tuple[str, int], ...]
) -> tuple[int, str | None]:
    for pattern, weight in patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            return weight, match.group(0)
    return 0, None


def _score_candidate(
    *,
    kind: str,
    subject: str,
    body: str,
    combined: str,
    subject_patterns: tuple[tuple[str, int], ...],
    term_re: re.Pattern[str],
    invite_cue: re.Pattern[str],
    schedule_cue: re.Pattern[str],
    participation_cue: re.Pattern[str],
    negative_patterns: tuple[tuple[str, int, str], ...],
    has_link: bool,
    sender_email: str,
    missing_term_reason: str,
) -> Classification:
    reasons: list[str] = []
    if not term_re.search(combined):
        return Classification(
            accepted=False,
            score=0,
            kind=kind,
            rejection_reason=missing_term_reason,
        )

    subject_strength, subject_hit = _subject_strength(subject, subject_patterns)
    invite = bool(invite_cue.search(combined))
    schedule = bool(schedule_cue.search(combined))
    participation = bool(participation_cue.search(combined))
    hr_context = bool(HR_CONTEXT.search(combined)) or bool(
        re.search(r"recruit|talent|career|hr", sender_email, re.I)
    )
    has_subject_term = bool(term_re.search(subject))
    has_body_term = bool(term_re.search(body))

    score = float(subject_strength)
    if subject_hit:
        reasons.append(f"主题命中「{subject_hit.strip()}」")
    if invite:
        score += 3.0
        reasons.append("正文包含参加或确认安排")
    if schedule:
        score += 2.0
        reasons.append("包含具体时间或截止安排")
    if has_link:
        score += 2.0
        reasons.append("识别到平台入口链接")
    if participation:
        score += 1.0
    if hr_context:
        score += 0.8
    if has_body_term and (invite or schedule):
        score += 0.7
    elif has_body_term:
        score += 0.2

    for pattern, penalty, reason in negative_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            score -= penalty
            reasons.append(f"减分：{reason}")

    if subject_strength == 0 and not has_subject_term and not (invite and has_body_term):
        return Classification(
            accepted=False,
            score=score,
            kind=kind,
            rejection_reason="主题没有指向这类安排，正文也缺少明确指引",
            reasons=reasons,
            subject_strength=subject_strength,
            has_invite_cue=invite,
            has_schedule_cue=schedule,
            has_event_link=has_link,
        )

    if score < 4.0:
        return Classification(
            accepted=False,
            score=score,
            kind=kind,
            rejection_reason="有效信号不足，可能是流程通知或资讯邮件",
            reasons=reasons,
            subject_strength=subject_strength,
            has_invite_cue=invite,
            has_schedule_cue=schedule,
            has_event_link=has_link,
        )

    if not (subject_strength >= 4 or invite or schedule or has_link):
        return Classification(
            accepted=False,
            score=score,
            kind=kind,
            rejection_reason="没有发现具体的安排信息",
            reasons=reasons,
            subject_strength=subject_strength,
            has_invite_cue=invite,
            has_schedule_cue=schedule,
            has_event_link=has_link,
        )

    reasons.append(f"综合评分 {score:.1f}")
    return Classification(
        accepted=True,
        score=score,
        kind=kind,
        reasons=reasons,
        subject_strength=subject_strength,
        has_invite_cue=invite,
        has_schedule_cue=schedule,
        has_event_link=has_link,
    )


def classify_email(
    subject: str,
    body: str,
    links: list[EmailLink],
    sender_email: str = "",
    sender_name: str = "",
) -> Classification:
    subject = normalize_for_rules(subject)
    body = normalize_for_rules(body)[:30_000]
    combined = f"{subject}\n{body}"

    for pattern, reason in HARD_REJECT_SUBJECT:
        if re.search(pattern, subject, re.IGNORECASE):
            return Classification(
                accepted=False,
                score=0,
                rejection_reason=reason,
                reasons=[f"排除：{reason}"],
            )

    exam = _score_candidate(
        kind="exam",
        subject=subject,
        body=body,
        combined=combined,
        subject_patterns=EXAM_SUBJECT_PATTERNS,
        term_re=EXAM_TERM_RE,
        invite_cue=EXAM_INVITE_CUE,
        schedule_cue=EXAM_SCHEDULE_CUE,
        participation_cue=EXAM_PARTICIPATION_CUE,
        negative_patterns=EXAM_NEGATIVE_PATTERNS,
        has_link=has_exam_link(links),
        sender_email=sender_email,
        missing_term_reason="没有发现笔试或测评相关词",
    )
    interview = _score_candidate(
        kind="interview",
        subject=subject,
        body=body,
        combined=combined,
        subject_patterns=INTERVIEW_SUBJECT_PATTERNS,
        term_re=INTERVIEW_TERM_RE,
        invite_cue=INTERVIEW_INVITE_CUE,
        schedule_cue=INTERVIEW_SCHEDULE_CUE,
        participation_cue=INTERVIEW_PARTICIPATION_CUE,
        negative_patterns=INTERVIEW_NEGATIVE_PATTERNS,
        has_link=has_interview_link(links),
        sender_email=sender_email,
        missing_term_reason="没有发现面试相关词",
    )

    if interview.accepted and (
        not exam.accepted
        or interview.subject_strength > exam.subject_strength
        or (
            interview.subject_strength == exam.subject_strength
            and interview.score > exam.score
        )
    ):
        return interview
    if exam.accepted:
        return exam
    if interview.accepted:
        return interview
    return interview if interview.score > exam.score else exam
