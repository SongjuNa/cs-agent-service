"""자동 발송 판정 규칙 (변경 add-auto-send 결정 2). DB 없이 조건 하나씩 본다."""

import copy

import pytest

from app.rules.autosend import ALWAYS_HUMAN, AUTO_CATS, DEFAULT_RULES, normalize, validate, verdict

OK = {"channel": "EMAIL", "category_code": "MANUAL", "priority": "P4", "urgency_flag": "NONE", "inquiry_count": 1,
      "status": "IN_PROGRESS", "has_blocking_missing": False, "has_evidence": True, "has_draft": True, "issues": [],
      "failed_checks": 0, "verify_passed": True}


def rules(**over):
    r = copy.deepcopy(DEFAULT_RULES)
    r.update(over)
    return r


def test_all_conditions_met_is_auto():
    auto, passed, blocked = verdict(OK, rules())
    assert auto and not blocked and "검증 통과" in passed


@pytest.mark.parametrize("change,reason", [
    ({"category_code": "QUOTE"}, "고위험 유형"), ({"category_code": "DEFECT"}, "고위험 유형"), ({"category_code": "COMPLIANCE"}, "자동 대상 아님"),
    ({"priority": "P1"}, "사람이 확인"), ({"priority": "P2"}, "사람이 확인"), ({"priority": None}, "사람이 확인"),
    ({"urgency_flag": "SAFETY"}, "안전·설비 정지"), ({"urgency_flag": "SITE_DOWN"}, "안전·설비 정지"),
    ({"inquiry_count": 2}, "복합 문의"), ({"status": "ESCALATED"}, "이미 처리 흐름"), ({"status": "RESOLVED"}, "이미 처리 흐름"),
    ({"has_blocking_missing": True}, "막는 정보 누락"), ({"has_evidence": False}, "근거 문서 없음"), ({"has_draft": False}, "답변 초안 없음"),
    ({"issues": ["근거 밖 인용/숫자 1곳"]}, "확인이 필요한 것"), ({"failed_checks": 2}, "자체 검사"), ({"verify_passed": False}, "검증"),
    ({"channel": "PHONE"}, "자동 처리 꺼짐"),
])
def test_each_blocker_blocks(change, reason):
    auto, _, blocked = verdict({**OK, **change}, rules())
    assert not auto and any(reason in b for b in blocked), blocked


def test_switch_off_blocks_everything_and_toggles_work():
    assert verdict(OK, rules(enabled=False)) == (False, [], ["자동 처리가 꺼져 있음"])
    off = rules()
    off["cats"]["MANUAL"] = False
    assert not verdict(OK, off)[0]
    chan = rules()
    chan["channels"]["EMAIL"] = False
    assert not verdict(OK, chan)[0]


def test_always_human_categories_cannot_be_enabled():
    """항상 사람이 확인하는 유형은 설정에 넣어도 자동 대상이 되지 않고, 저장 요청은 거부된다."""
    for c in ALWAYS_HUMAN:
        assert c not in AUTO_CATS and c not in DEFAULT_RULES["cats"]
        assert not normalize({"enabled": True, "cats": {c: True}})["cats"].get(c)
        assert not verdict({**OK, "category_code": c}, normalize({"enabled": True, "cats": {c: True}}))[0]
        assert validate({"enabled": True, "cats": {c: True}})


def test_validate_and_normalize():
    assert validate({"enabled": True, "cats": {"MANUAL": False}, "channels": {"EMAIL": False}}) == []
    assert validate({"cats": {}}) and validate("x") and validate({"enabled": True, "cats": {"NOPE": True}}) and validate({"enabled": True, "channels": {"FAX": True}})
    n = normalize({"enabled": False, "cats": {"MANUAL": False, "NOPE": True}, "channels": {"FAX": True}})
    assert n["enabled"] is False and n["cats"]["MANUAL"] is False and "NOPE" not in n["cats"] and "FAX" not in n["channels"]
    assert normalize(None) == DEFAULT_RULES
