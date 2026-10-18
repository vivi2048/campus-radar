from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..mail.mime import EmailLink
from .links import has_exam_link

EXAM_TERM_RE = re.compile(
    r"笔试|测评|在线考试|线上考试|在线笔试|线上笔试|机考|编程测试|编程测评"
    r"|written\s+test|online\s+assessment|coding\s+(?:test|challenge)|assessment|\bexam\b",
    re.IGNORECASE,
)

SUBJECT_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"笔试\s*(?:邀请|通知|安排|提醒|确认|链接|入口|公告)|笔试.{0,5}(?:邀请|通知|安排|提醒)", 8),
    (r"(?:测评|考试)\s*(?:邀请|通知|安排|提醒|确认|链接|入口)", 7),
    (r"(?:在线|线上|远程)\s*(?:笔试|测评|考试)", 6),
    (r"(?:笔试|测评)\s*(?:时间|日期|地点|须知|倒计时)", 5),
    (r"机考|在线编程|编程测试|coding\s+(?:test|challenge)", 6),
    (r"written\s+test|online\s+assessment|(?:test|assessment|exam)\s+invitation", 7),
    (r"assessment|online\s+test|exam", 5),
    (r"笔试|测评|考试", 2),
)

HARD_REJECT_SUBJECT: tuple[tuple[str, str], ...] = (
    (r"笔经|面经|笔试真题|真题|题库|模拟题|练习题|预测题|考试答案|答案分享", "主题看起来是备考资料"),
    (r"面试(?:邀请|通知|安排|提醒)|面试结果|面试反馈", "主题是面试安排，不是笔试"),
    (r"招聘日报|招聘周报|职位推荐|为你推荐|最新职位|内推群|海投", "主题是职位推荐或招聘资讯"),
    (r"广告|促销|优惠|折扣|课程报名|训练营|直播课", "主题看起来是推广内容"),
)

INVITE_CUE = re.compile(
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

SCHEDULE_CUE = re.compile(
    r"考试时间|笔试时间|测评时间|作答时间|测试时间|开始时间|开放时间|开考时间"
    r"|考试日期|笔试日期|测评日期|考试安排|笔试安排|有效期至|截止(?:时间|日期|至)"
    r"|assessment\s+date|test\s+date|exam\s+date|start\s+time|deadline|due\s+by|opens?\s+at",
    re.IGNORECASE,
)

PARTICIPATION_CUE = re.compile(
    r"(?:参加|参与|完成|进行).{0,12}(?:笔试|测评|在线考试|考试)"
    r"|(?:笔试|测评|考试).{0,12}(?:开始|入口|链接|系统)",
    re.IGNORECASE,
)

HR_CONTEXT = re.compile(
    r"校园招聘|校招|招聘|应聘|候选人|投递|岗位|职位|实习|管培|campus|recruit|career|talent|hiring",
    re.IGNORECASE,
)

NEGATIVE_PATTERNS: tuple[tuple[str, int, str], ...] = (
    (r"笔试\s*(?:结果|成绩|通过|未通过|已通过|查询)", 7, "内容像是在通知笔试结果"),
    (r"(?:感谢|谢谢)(?:您|你)?(?:参加|参与).{0,16}(?:笔试|测评|考试)", 8, "内容像是在感谢已完成考试"),
    (r"已(?:完成|参加).{0,10}(?:笔试|测评)", 5, "内容提到考试已完成"),
    (r"笔试(?:时间|安排)(?:汇总|一览|日历)|考试日历|笔试时间表", 5, "内容像是笔试资讯汇总"),
    (r"模拟|练习|样题|sample\s+test|practice\s+test|mock\s+test", 6, "内容像是模拟练习"),
    (r"退订|unsubscribe|订阅偏好|邮件订阅", 2, "内容包含订阅退订信息"),
)


@dataclass
class Classification:
    accepted: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    subject_strength: int = 0
    has_invite_cue: bool = False
    has_schedule_cue: bool = False
    has_exam_link: bool = False


def normalize_for_rules(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text)


def _subject_strength(subject: str) -> tuple[int, str | None]:
    for pattern, weight in SUBJECT_PATTERNS:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            return weight, match.group(0)
    return 0, None


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
    reasons: list[str] = []

    for pattern, reason in HARD_REJECT_SUBJECT:
        if re.search(pattern, subject, re.IGNORECASE):
            return Classification(
                accepted=False,
                score=0,
                rejection_reason=reason,
                reasons=[f"排除：{reason}"],
            )

    if not EXAM_TERM_RE.search(combined):
        return Classification(accepted=False, score=0, rejection_reason="没有发现笔试或测评相关词")

    subject_strength, subject_hit = _subject_strength(subject)
    invite = bool(INVITE_CUE.search(combined))
    schedule = bool(SCHEDULE_CUE.search(combined))
    exam_link = has_exam_link(links)
    participation = bool(PARTICIPATION_CUE.search(combined))
    hr_context = bool(HR_CONTEXT.search(combined)) or bool(re.search(r"recruit|talent|career|hr", sender_email, re.I))
    has_subject_term = bool(EXAM_TERM_RE.search(subject))
    has_body_term = bool(EXAM_TERM_RE.search(body))

    score = float(subject_strength)
    if subject_hit:
        reasons.append(f"主题命中「{subject_hit.strip()}」")
    if invite:
        score += 3.0
        reasons.append("正文包含参加/作答指引")
    if schedule:
        score += 2.0
        reasons.append("包含考试时间或截止安排")
    if exam_link:
        score += 2.0
        reasons.append("识别到考试平台链接")
    if participation:
        score += 1.0
    if hr_context:
        score += 0.8
    if has_body_term and (invite or schedule):
        score += 0.7
    elif has_body_term:
        score += 0.2

    for pattern, penalty, reason in NEGATIVE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            score -= penalty
            reasons.append(f"减分：{reason}")

    if subject_strength == 0 and not has_subject_term and not (invite and has_body_term):
        return Classification(
            accepted=False,
            score=score,
            rejection_reason="主题没有指向笔试，正文也缺少明确的参加指引",
            reasons=reasons,
            subject_strength=subject_strength,
            has_invite_cue=invite,
            has_schedule_cue=schedule,
            has_exam_link=exam_link,
        )

    if score < 4.0:
        return Classification(
            accepted=False,
            score=score,
            rejection_reason="笔试信号不足，可能是流程通知或资讯邮件",
            reasons=reasons,
            subject_strength=subject_strength,
            has_invite_cue=invite,
            has_schedule_cue=schedule,
            has_exam_link=exam_link,
        )

    if not (subject_strength >= 4 or invite or schedule or exam_link):
        return Classification(
            accepted=False,
            score=score,
            rejection_reason="没有发现具体的考试安排",
            reasons=reasons,
            subject_strength=subject_strength,
        )

    reasons.append(f"综合评分 {score:.1f}")
    return Classification(
        accepted=True,
        score=score,
        reasons=reasons,
        subject_strength=subject_strength,
        has_invite_cue=invite,
        has_schedule_cue=schedule,
        has_exam_link=exam_link,
    )
