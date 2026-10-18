from __future__ import annotations

import pytest

from app.extract.company import canonicalize_company
from app.extract.fields import extract_company
from app.llm import build_analysis_from_payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("新凯来公司诚邀您参加", "新凯来"),
        ("宁德时代（CATL）", "宁德时代"),
        ("宁德时代新能源科技股份有限公司", "宁德时代"),
        ("中国第一汽车股份有限公司（中国一汽）", "中国一汽"),
        ("东风汽车集团股份有限公司（东风汽车研发", "东风汽车"),
        ("北京中软融鑫计算机系统工程有限公司", "中软融鑫"),
        ("杭州迪普科技股份有限公司", "迪普科技"),
        ("新华三技术有限公司", "新华三"),
        ("Northstar Labs", "Northstar Labs"),
        ("星野科技", "星野科技"),
        ("我司", ""),
    ],
)
def test_canonicalize_company(raw: str, expected: str):
    assert canonicalize_company(raw) == expected


def test_local_company_extraction_is_canonical():
    company = extract_company(
        "【宁德时代】2027届校园招聘AI面试邀请",
        "同学你好，现邀请你参加面试。",
        "宁德时代（CATL）招聘",
        "hr@catl.com",
    )
    assert company == "宁德时代"


def test_llm_payload_company_is_canonical():
    analysis = build_analysis_from_payload(
        {
            "is_event": True,
            "kind": "interview",
            "confidence": 0.9,
            "company": "中国第一汽车股份有限公司（中国一汽）",
            "start": "2026-10-25T14:00:00+08:00",
            "time_known": True,
        }
    )
    assert analysis is not None
    assert analysis.fields is not None
    assert analysis.fields.company == "中国一汽"
