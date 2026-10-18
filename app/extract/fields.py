from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..mail.mime import EmailLink
from .links import detect_platform, normalize_url, select_exam_link, select_interview_link

GENERIC_COMPANY_RE = re.compile(
    r"校园招聘|春季招聘|秋季招聘|社会招聘|招聘中心|招聘团队|招聘组|招聘助手|招聘"
    r"|人力资源部|人力资源中心|人力资源|人才发展|企业文化|HRBP|HR团队|HR中心|HR"
    r"|Recruiting(?:\s+Team)?|Talent\s+Acquisition|Campus\s+Recruitment|Recruitment|Careers?"
    r"|校招|秋招|春招|内推|笔试助手",
    re.IGNORECASE,
)
EXAM_NOISE_RE = re.compile(
    r"(?:笔试|测评|在线考试|线上考试|在线笔试|线上笔试|机考)(?:的)?(?:邀请|通知|提醒|安排|确认|公告|链接)?"
    r"|(?:视频|电话|现场|线上|线下|远程)?(?:初试|复试|面试|面谈|终面|终试)(?:的)?(?:邀请|通知|提醒|安排|确认|公告|邀约)?",
    re.IGNORECASE,
)
ROLE_HINT_RE = re.compile(
    r"工程师|开发|算法|测试|前端|后端|全栈|客户端|服务端|数据|产品|运营|设计|市场|销售|财务"
    r"|法务|人力|供应链|策略|研究|分析|咨询|管培|培训生|硬件|电气|机械|芯片|嵌入式|安全|风控"
    r"|投资|审计|精算|交互|视觉|品牌|编辑|教师|讲师|专员|经理|顾问|设计师|分析师|研究员|科学家"
    r"|架构师|实习生|管理培训生|engineer|developer|analyst|manager|designer|scientist|consultant"
    r"|specialist|associate|intern|researcher",
    re.IGNORECASE,
)
ROLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:应聘|投递|申请|意向)(?:的)?(?:岗位|职位|职务|角色)\s*[:：]\s*([^\n，。；;]{2,50})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:岗位|职位|职务)(?:名称)?\s*[:：]\s*([^\n，。；;]{2,50})",
        re.IGNORECASE,
    ),
    re.compile(r"(?:Position|Role)\s*[:：]\s*([^\n，。；;]{2,60})", re.IGNORECASE),
    re.compile(
        r"您(?:投递|申请|应聘)的(?:是)?\s*[「『“\"']?(.{2,50}?)[」』”\"']?\s*(?:岗位|职位)",
    ),
    re.compile(
        r"参与\s*([^\n，。；;]{2,40}?)\s*的(?:视频|电话|现场|线上|远程)?(?:面试|初试|复试|终面|面谈)",
    ),
)
COMPANY_LABEL_RE = re.compile(
    r"(?:公司名称|企业名称|所属公司|公司)\s*[:：]\s*([^\n，。；;]{2,45})"
)
COMPANY_AFTER_THANKS_RE = re.compile(
    r"(?:感谢|谢谢)(?:您|你)?(?:投递|申请|应聘)(?:了)?\s*[「『“\"]?(.{2,32}?)[」』”\"]?"
    r"(?:的|公司|，|。|\n|$)"
)
COMPANY_SUFFIX_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,30}?"
    r"(?:股份有限公司|有限公司|集团|银行|证券|研究院|研究所|事务所|大学))"
)
SUBJECT_COMPANY_PREFIX_RE = re.compile(
    r"^(?:关于|有关)?\s*([\u4e00-\u9fa5A-Za-z0-9·（）()]{2,30}?)"
    r"(?=20\d{2}|校园招聘|校招|秋招|春招|招聘|笔试|测评|在线考试|线上考试)"
)
BRACKET_RE = re.compile(r"[【\[「『]([^】\]」』]{2,60})[】\]」』]")
ACCESS_CODE_RE = re.compile(
    r"(?:考试口令|测评口令|考试码|考试邀请码|邀请码|Access\s*Code|Test\s*Code|Exam\s*Code)"
    r"\s*[:：]?\s*[「『“\"']?([A-Za-z0-9][A-Za-z0-9_-]{3,24})",
    re.IGNORECASE,
)
INTERVIEW_ACCESS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:会议号|会议\s*ID|Meeting\s*ID)\s*[:：]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9 _-]{2,40})",
            re.IGNORECASE,
        ),
        "会议号",
    ),
    (
        re.compile(
            r"(?:会议密码|入会密码|Meeting\s*Password|Passcode)\s*[:：]?\s*"
            r"([A-Za-z0-9!@#$%^&*._-]{2,30})",
            re.IGNORECASE,
        ),
        "密码",
    ),
)
INTERVIEW_ROUND_RE = re.compile(
    r"(?:面试轮次|面试阶段|轮次)\s*[:：]\s*([^\n，。；;]{1,20})"
    r"|(第[一二三四五六七八九十\d]+轮(?:面试)?)"
    r"|(?<![A-Za-z统])(HR\s*面|hr\s*面|终面|终试|一面|二面|三面|四面|初面|复面|初试|复试|群面|技术面|专业面|综合面|业务面|主管面|经理面|交叉面|加面)(?=面试|面|试|[\s：:，,、\-—。；;！!]|$)"
    r"|(?<![A-Za-z])(first|second|third|final|technical|behavioral|HR)\s+round(?:\s+interview)?",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(
    r"(?:考试地点|笔试地点|测评地点|面试地点|面试地址|线下地点|考点|考试地址|地址|地点)"
    r"\s*[:：]\s*([^\n]{2,80})"
)
NOTE_CUES_RE = re.compile(
    r"提前\s*\d+\s*分钟|摄像头|麦克风|监控|防作弊|不允许|禁止|计算器|草稿纸|身份证|学生证"
    r"|准考证|浏览器|Chrome|客户端|网络|设备|安静|作答|考试须知|请务必|请确保|请注意"
    r"|开考后|迟到|切屏|离开|自动保存|电量|充电|环境"
    r"|等候室|入会|会议软件|下载|安装|签到|着装|简历|作品集|到访|到场|身份核验"
    r"|面试须知|面试流程|camera|microphone|webcam|headphone|waiting\s+room"
    r"|minutes?\s+early|download|install|on\s+time",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

KNOWN_DOMAINS: tuple[tuple[str, str], ...] = (
    ("bytedance.com", "字节跳动"),
    ("bytedance.net", "字节跳动"),
    ("tencent.com", "腾讯"),
    ("tencent.cn", "腾讯"),
    ("alibaba-inc.com", "阿里巴巴"),
    ("alibaba.com", "阿里巴巴"),
    ("antgroup.com", "蚂蚁集团"),
    ("alipay.com", "蚂蚁集团"),
    ("baidu.com", "百度"),
    ("meituan.com", "美团"),
    ("meituan.net", "美团"),
    ("dianping.com", "美团"),
    ("jd.com", "京东"),
    ("pinduoduo.com", "拼多多"),
    ("temu.com", "拼多多"),
    ("netease.com", "网易"),
    ("corp.netease.com", "网易"),
    ("huawei.com", "华为"),
    ("xiaomi.com", "小米"),
    ("oppo.com", "OPPO"),
    ("oplus.com", "OPPO"),
    ("vivo.com", "vivo"),
    ("kuaishou.com", "快手"),
    ("bilibili.com", "哔哩哔哩"),
    ("didiglobal.com", "滴滴"),
    ("xiaojukeji.com", "滴滴"),
    ("ctrip.com", "携程"),
    ("trip.com", "携程"),
    ("xiaohongshu.com", "小红书"),
    ("nio.com", "蔚来"),
    ("lixiang.com", "理想汽车"),
    ("li-auto.com", "理想汽车"),
    ("xiaopeng.com", "小鹏汽车"),
    ("xpeng.com", "小鹏汽车"),
    ("byd.com", "比亚迪"),
    ("catl.com", "宁德时代"),
    ("dji.com", "大疆"),
    ("zte.com.cn", "中兴通讯"),
    ("chinamobile.com", "中国移动"),
    ("chinatelecom.com.cn", "中国电信"),
    ("chinaunicom.com.cn", "中国联通"),
    ("cmbchina.com", "招商银行"),
    ("icbc.com.cn", "中国工商银行"),
    ("ccb.com", "中国建设银行"),
    ("abchina.com", "中国农业银行"),
    ("boc.cn", "中国银行"),
    ("bankcomm.com", "交通银行"),
    ("citics.com", "中信证券"),
    ("csc108.com", "中信建投证券"),
    ("htsc.com.cn", "华泰证券"),
    ("cicc.com", "中金公司"),
    ("microsoft.com", "微软"),
    ("google.com", "谷歌"),
    ("amazon.com", "亚马逊"),
    ("apple.com", "苹果"),
    ("tesla.com", "特斯拉"),
    ("nvidia.com", "英伟达"),
    ("intel.com", "英特尔"),
    ("qualcomm.com", "高通"),
    ("morganstanley.com", "摩根士丹利"),
    ("goldmansachs.com", "高盛"),
    ("mckinsey.com", "麦肯锡"),
    ("deloitte.com", "德勤"),
    ("pwc.com", "普华永道"),
    ("ey.com", "安永"),
    ("kpmg.com", "毕马威"),
    ("pg.com", "宝洁"),
    ("unilever.com", "联合利华"),
    ("mars.com", "玛氏"),
    ("loreal.com", "欧莱雅"),
    ("coca-cola.com", "可口可乐"),
    ("nike.com", "耐克"),
    ("shopee.com", "Shopee"),
    ("tcl.com", "TCL"),
    ("tcl.com.cn", "TCL"),
    ("hundsun.com", "恒生"),
    ("pku.edu.cn", "北京大学"),
    ("tsinghua.edu.cn", "清华大学"),
)

PLATFORM_NAMES = {
    "牛客网",
    "牛客",
    "赛码网",
    "赛码",
    "北森",
    "北森测评",
    "智鼎",
    "智鼎测评",
    "SHL",
    "HackerRank",
    "HackerEarth",
    "Codility",
    "CodeSignal",
    "LeetCode",
    "HireVue",
    "TestGorilla",
    "Coderbyte",
    "Moka",
    "Workday",
    "Greenhouse",
    "Oracle Taleo",
    "SAP SuccessFactors",
    "Zoom",
    "腾讯会议",
    "飞书会议",
    "钉钉会议",
    "Microsoft Teams",
    "Google Meet",
    "Webex",
    "华为云会议",
    "牛客面试",
    "智联",
    "智联招聘",
    "iTalent",
    "北森",
    "牛客",
    "牛客网",
    "赛码",
    "赛码网",
    "猎聘",
    "BOSS直聘",
    "前程无忧",
    "51job",
}

GENERIC_MAIL_DOMAINS = {
    "qq.com",
    "foxmail.com",
    "163.com",
    "126.com",
    "yeah.net",
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "sina.com",
    "aliyun.com",
}


@dataclass(frozen=True)
class ExtractedFields:
    company: str
    role: str
    platform: str | None
    exam_url: str | None
    mode: str
    location: str | None
    access_code: str | None
    auto_notes: str | None
    interview_round: str | None = None


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _trim_company(value: str) -> str:
    value = _nfkc(value).strip()
    value = value.strip(" \t\r\n【】[]（）()<>《》「」『』“”\"'·-—_|｜,，.。:：;；")
    value = re.sub(r"^(?:关于|有关|来自|至|致)\s*", "", value)
    value = re.sub(r"^(?:欢迎加入|欢迎投递|感谢您投递|感谢投递|您已投递|您投递的)\s*", "", value)
    value = re.sub(r"(?:20\d{2}\s*届?|20\d{2}\s*年)\s*(?:秋季|春季|暑期)?\s*(?:校园招聘|校招|社会招聘)?", "", value)
    for _ in range(3):
        cleaned = GENERIC_COMPANY_RE.sub("", value)
        cleaned = EXAM_NOISE_RE.sub("", cleaned)
        if cleaned == value:
            break
        value = cleaned
    value = re.sub(r"\s*(?:的|校园招聘|校招)$", "", value)
    value = re.sub(r"(?:项目组|项目团队|招聘项目组)$", "", value)
    value = re.sub(r"\s*[|｜]\s*", " / ", value)
    value = value.strip(" \t\r\n【】[]（）()<>《》「」『』“”\"'·-—_|｜,，.。:：;；")
    value = re.sub(r"\s{2,}", " ", value)
    return value[:45]


def valid_company(value: str) -> bool:
    if not value:
        return False
    if len(value) < 2:
        return False
    if value in PLATFORM_NAMES:
        return False
    if re.fullmatch(
        r"在线|线上|线下|远程|笔试|测评|考试|面试|面谈|邀请|通知|提醒|安排|确认|校招|秋招|春招"
        r"|校园|招聘|同学|您好|你好|测评通知|笔试通知|考试通知|面试通知|面试邀请|面试安排|开始|参加|进行|重要",
        value,
        re.IGNORECASE,
    ):
        return False
    if not re.search(r"[A-Za-z\u4e00-\u9fa5]", value):
        return False
    if re.fullmatch(r"[\d\s./年月日号\-]+", value):
        return False
    if re.search(r"(?:工程师|顾问|经理|专员|设计师|分析师|研究员|实习生|培训生|岗位|职位|岗)$", value):
        return False
    if ROLE_HINT_RE.search(value) and not re.search(
        r"公司|集团|银行|证券|研究院|研究所|事务所|科技|咨询|资本|投资|传媒|文化|教育"
        r"|医疗|能源|汽车|航空|物流|零售|地产|大学|部门|中心|事业部",
        value,
    ):
        return False
    if re.search(r"岗位|职位|笔试|测评|考试|面试|面谈|邀请|通知|提醒|同学|您好|你好", value):
        return False
    return True


def _domain_company(sender_email: str) -> str:
    if "@" not in sender_email:
        return ""
    domain = sender_email.rsplit("@", 1)[1].lower().strip()
    if not domain or domain in GENERIC_MAIL_DOMAINS:
        return ""
    for known_domain, company in sorted(KNOWN_DOMAINS, key=lambda item: len(item[0]), reverse=True):
        if domain == known_domain or domain.endswith("." + known_domain):
            return company
    return ""


def extract_company(subject: str, body: str, sender_name: str, sender_email: str) -> str:
    subject = _nfkc(subject)
    body = _nfkc(body)[:30_000]
    candidates: list[tuple[float, str]] = []

    for match in BRACKET_RE.finditer(subject):
        company = _trim_company(match.group(1))
        if valid_company(company):
            candidates.append((4.9, company))

    sender_clean = _trim_company(sender_name)
    if valid_company(sender_clean):
        sender_weight = 4.2 if re.search(
            r"招聘|HR|人力资源|校园|人才|Recruiting|Talent|Careers?",
            sender_name,
            re.IGNORECASE,
        ) else 2.0
        candidates.append((sender_weight, sender_clean))

    domain_company = _domain_company(sender_email)
    if domain_company:
        candidates.append((4.1, domain_company))

    subject_without_brackets = BRACKET_RE.sub(" ", subject)
    prefix_match = SUBJECT_COMPANY_PREFIX_RE.search(subject_without_brackets)
    if prefix_match:
        company = _trim_company(prefix_match.group(1))
        if valid_company(company):
            candidates.append((3.2, company))

    for regex in (COMPANY_LABEL_RE, COMPANY_AFTER_THANKS_RE):
        for match in regex.finditer(body):
            company = _trim_company(match.group(1))
            if valid_company(company):
                candidates.append((3.8, company))

    for match in COMPANY_SUFFIX_RE.finditer(body):
        company = _trim_company(match.group(1))
        if valid_company(company):
            candidates.append((2.4, company))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _trim_role(value: str) -> str:
    value = _nfkc(value).strip()
    value = value.strip(" \t\r\n【】[]（）()<>《》「」『』“”\"'·-—_|｜,，.。:：;；")
    value = re.sub(r"^(?:您|你|投递|投递了|申请|申请了|应聘|应聘了|的|岗位|职位|职务)\s*", "", value)
    value = re.sub(r"^(?:笔试|测评|考试)(?:提醒|邀请|通知|安排)?\s*[:：|｜\-—]\s*", "", value)
    value = re.sub(r"^(?:面试|面谈)(?:提醒|邀请|通知|安排|邀约)?\s*[:：|｜\-—]\s*", "", value)
    value = re.sub(r"^(?:20\d{2}\s*届?|20\d{2}\s*年)\s*(?:秋季|春季|暑期)?\s*(?:校园招聘|校招|提前批|补录)?", "", value)
    value = re.sub(r"(?:的)?(?:笔试|测评|在线考试|线上考试)(?:邀请|通知|提醒|安排)?$", "", value)
    value = re.sub(r"(?:的)?(?:面试|面谈)(?:邀请|通知|提醒|安排|邀约)?$", "", value)
    value = re.sub(r"(?:岗位|职位|职务)$", "", value)
    value = value.strip(" \t\r\n【】[]（）()<>《》「」『』“”\"'·-—_|｜,，.。:：;；")
    value = re.sub(r"\s{2,}", " ", value)
    return value[:60]


def _postprocess_role(value: str, company: str) -> str:
    value = _trim_role(value)
    if company:
        index = value.find(company)
        if 0 <= index <= 12:
            value = _trim_role(value[index + len(company) :])
        elif value.startswith(company):
            value = _trim_role(value[len(company) :])
    value = re.sub(r"^(?:在线|线上|线下)?(?:笔试|测评|考试)(?:提醒|邀请|通知|安排)?\s*[:：]?\s*", "", value)
    value = re.sub(r"^(?:在线|线上|线下|视频|电话|现场)?(?:面试|面谈)(?:提醒|邀请|通知|安排|邀约)?\s*[:：]?\s*", "", value)
    value = re.sub(r"^(?:一面|二面|三面|终面|初面|复面|初试|复试|HR\s*面)\s*[-—–|｜·]\s*", "", value, flags=re.IGNORECASE)
    match = re.match(
        r"^(.{1,55}?(?:工程师|专员|经理|设计师|分析师|研究员|顾问|管培生|培训生|架构师"
        r"|科学家|实习生|开发者|岗(?:位)?))",
        value,
    )
    if match:
        value = match.group(1)
    return _trim_role(value)


def valid_role(value: str) -> bool:
    if not value or len(value) < 2:
        return False
    if not ROLE_HINT_RE.search(value) and not re.search(r"岗(?:位)?$", value):
        return False
    if re.search(r"笔试邀请|测评邀请|考试通知|面试邀请|面试通知|面试安排|校园招聘$|招聘团队$", value):
        return False
    if len(value) > 50:
        return False
    return True


def extract_role(subject: str, body: str, company: str) -> str:
    subject = _nfkc(subject)
    body = _nfkc(body)[:30_000]
    candidates: list[tuple[float, str]] = []

    for pattern in ROLE_PATTERNS:
        for match in pattern.finditer(body):
            role = _postprocess_role(match.group(1), company)
            if valid_role(role):
                candidates.append((5.0, role))

    subject_without_company = BRACKET_RE.sub(" ", subject)
    subject_role = re.search(
        r"([\u4e00-\u9fa5A-Za-z0-9+/.（）() ]{2,24}(?:岗|岗位|职位))\s*"
        r"(?:笔试|测评|在线考试|线上考试|考试)",
        subject_without_company,
    )
    if subject_role:
        role = _postprocess_role(subject_role.group(1), company)
        if valid_role(role):
            candidates.append((4.2, role))

    segments = re.split(r"\s*[-—–|｜·]\s*", subject_without_company)
    for segment in segments:
        role = _postprocess_role(segment, company)
        if valid_role(role):
            candidates.append((3.8, role))
            break

    if not candidates:
        role_match = re.search(
            r"([\u4e00-\u9fa5A-Za-z0-9+/.（）() ]{2,40}?"
            r"(?:工程师|专员|经理|设计师|分析师|研究员|顾问|管培生|培训生|架构师|科学家|实习生|开发者|岗(?:位)?))",
            subject_without_company,
        )
        if role_match:
            role = _postprocess_role(role_match.group(1), company)
            if valid_role(role):
                candidates.append((3.1, role))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def extract_location(body: str) -> str | None:
    for match in LOCATION_RE.finditer(body):
        location = match.group(1).strip()
        location = re.sub(r"\s+", " ", location)
        location = re.split(r"(?:考试时间|笔试时间|面试时间|面谈时间|入场时间|面试形式|交通|联系|电话)", location)[0].strip(" ：:，,。；;")
        if not location or location in {"线上", "在线", "见邮件", "另行通知", "待定"}:
            continue
        if re.fullmatch(r"https?://\S+", location):
            continue
        return location[:100]
    return None


def _mode_and_location(
    body: str, url: str | None, platform: str | None, kind: str = "exam"
) -> tuple[str, str | None]:
    if kind == "interview":
        online_cue = bool(
            re.search(r"线上|在线|远程|居家|视频面试|电话面试|视频面|电话面|视频|电话|online|video|phone", body, re.I)
        )
        offline_cue = bool(
            re.search(r"线下|现场面试|现场面|到访|莅临|公司面试|面试地点|面试地址|onsite", body, re.I)
        )
    else:
        online_cue = bool(re.search(r"线上|在线|远程|居家|网络笔试|online", body, re.I))
        offline_cue = bool(re.search(r"线下|现场笔试|现场考试|考点|考场|莅临", body, re.I))
    location = extract_location(body)
    if location and re.search(r"线上|在线|远程|居家", location):
        location = None
    if offline_cue and not online_cue:
        return "offline", location
    if online_cue:
        return "online", None if offline_cue else location
    if url or platform:
        return "online", None
    if location:
        return "offline", location
    return "unknown", None


def _extract_notes(body: str) -> str | None:
    cleaned = URL_RE.sub("（链接）", _nfkc(body))
    cleaned = re.sub(r"\r\n", "\n", cleaned)
    pieces = re.split(r"(?<=[。；;！!？?])\s*|\n+", cleaned)
    notes: list[str] = []
    for piece in pieces:
        piece = re.sub(r"\s+", " ", piece).strip(" -—–·|｜")
        if len(piece) < 8 or len(piece) > 180:
            continue
        if not NOTE_CUES_RE.search(piece):
            continue
        if re.search(r"退订|unsubscribe|隐私政策|此邮件由系统", piece, re.I):
            continue
        if re.search(r"考试口令|测评口令|邀请码|Access\s*Code|会议号|会议密码|Meeting\s*ID|Passcode", piece, re.I):
            continue
        if piece not in notes:
            notes.append(piece)
        if len(notes) >= 4:
            break
    return "\n".join(notes) if notes else None


def extract_interview_round(subject: str, body: str) -> str | None:
    text = f"{_nfkc(subject)}\n{_nfkc(body)[:5000]}"
    for match in INTERVIEW_ROUND_RE.finditer(text):
        value = next((group for group in match.groups() if group), "").strip()
        value = re.sub(r"\s+", " ", value).strip(" ：:，,。；;-—")
        if not value:
            continue
        if value.lower() in {"hr面", "hr 面"}:
            return "HR 面"
        if re.fullmatch(r"[a-z]+ round(?: interview)?", value, re.I):
            return value[:1].upper() + value[1:].lower()
        return value[:20]
    return None


def extract_interview_access(body: str) -> str | None:
    text = _nfkc(body)
    parts: list[str] = []
    for pattern, label in INTERVIEW_ACCESS_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip(" \t，,。；;")
        value = re.sub(r"\s{2,}", " ", value)
        if not value:
            continue
        part = f"{label} {value}"
        if part not in parts:
            parts.append(part)
    return " · ".join(parts)[:80] if parts else None


def extract_fields(
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    links: list[EmailLink],
    *,
    kind: str = "exam",
) -> ExtractedFields:
    company = extract_company(subject, body, sender_name, sender_email)
    role = extract_role(subject, body, company)
    if kind == "interview":
        selected = select_interview_link(links)
    else:
        selected = select_exam_link(links)
    exam_url = normalize_url(selected.url) if selected else None
    platform = detect_platform(f"{subject}\n{body}", links, selected, kind=kind)
    mode, location = _mode_and_location(body, exam_url, platform, kind)
    if kind == "interview":
        access_code = extract_interview_access(body)
        if not access_code:
            access_match = ACCESS_CODE_RE.search(_nfkc(body))
            access_code = access_match.group(1).strip() if access_match else None
        interview_round = extract_interview_round(subject, body)
    else:
        access_match = ACCESS_CODE_RE.search(_nfkc(body))
        access_code = access_match.group(1).strip() if access_match else None
        interview_round = None
    notes = _extract_notes(body)
    return ExtractedFields(
        company=company,
        role=role,
        platform=platform,
        exam_url=exam_url,
        mode=mode,
        location=location,
        access_code=access_code,
        auto_notes=notes,
        interview_round=interview_round,
    )
