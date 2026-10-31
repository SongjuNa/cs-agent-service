"""자동 발송 판정 (변경 add-auto-send, 최신 목업 lib/auto.ts). 간단한 문의는 검증을 통과하면 사람 승인 없이 보내고,
복잡하거나 고위험인 문의는 상담원이 확인한다.

순수 함수다. 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1). 모든 조건을 만족해야 자동 발송이고, 하나라도 걸리면 막는다.
항상 사람이 확인하는 유형·긴급도·우선순위는 설정으로 풀 수 없다(코드로 고정).
"""

from __future__ import annotations

import copy
from typing import Any

ALWAYS_HUMAN = ("DEFECT", "INSTALL", "RETURN", "WARRANTY", "QUOTE", "ORDER_LEAD")  # 어떤 설정으로도 자동 발송하지 않는다
AUTO_CATS = ("MANUAL", "TECH_SPEC", "FW_UPDATE", "COMPLIANCE")  # 켜고 끌 수 있는 유형(근거 문서를 그대로 보내는 문의)
CHANNELS = ("EMAIL", "WEB_FORM", "PHONE", "CHAT", "PARTNER_PORTAL")
AUTO_PRIORITIES = ("P3", "P4")
URGENT = ("SAFETY", "SITE_DOWN")
DEFAULT_RULES: dict[str, Any] = {
    "enabled": True,
    "cats": {"MANUAL": True, "TECH_SPEC": True, "FW_UPDATE": True, "COMPLIANCE": False},
    "channels": {"EMAIL": True, "WEB_FORM": True, "PHONE": False, "CHAT": True, "PARTNER_PORTAL": True},
}
CATEGORY_NAMES = {"MANUAL": "매뉴얼", "TECH_SPEC": "기술 사양", "FW_UPDATE": "펌웨어", "COMPLIANCE": "인증·규격", "DEFECT": "고장·불량",
                  "INSTALL": "설치", "RETURN": "반품", "WARRANTY": "보증", "QUOTE": "견적", "ORDER_LEAD": "주문·납기"}


def normalize(value: dict[str, Any] | None) -> dict[str, Any]:
    """저장된 설정을 기본값 위에 얹는다. 모르는 키는 버리고, 항상 사람 확인 유형은 넣지 않는다."""
    rules = copy.deepcopy(DEFAULT_RULES)
    if not isinstance(value, dict):
        return rules
    rules["enabled"] = bool(value.get("enabled", rules["enabled"]))
    for c, v in (value.get("cats") or {}).items():
        if c in AUTO_CATS:
            rules["cats"][c] = bool(v)
    for ch, v in (value.get("channels") or {}).items():
        if ch in CHANNELS:
            rules["channels"][ch] = bool(v)
    return rules


def validate(value: Any) -> list[str]:
    """설정 저장 요청의 문제를 문장으로 돌려준다(비어 있으면 통과)."""
    if not isinstance(value, dict):
        return ["설정 형식이 올바르지 않습니다"]
    errors: list[str] = []
    if not isinstance(value.get("enabled"), bool):
        errors.append("켜짐 여부(enabled)가 필요합니다")
    for c, v in (value.get("cats") or {}).items():
        if c in ALWAYS_HUMAN and v:
            errors.append(f"{CATEGORY_NAMES.get(c, c)} 유형은 항상 사람이 확인하므로 자동 대상으로 바꿀 수 없습니다")
        elif c not in AUTO_CATS and c not in ALWAYS_HUMAN:
            errors.append(f"알 수 없는 유형: {c}")
    for ch in (value.get("channels") or {}):
        if ch not in CHANNELS:
            errors.append(f"알 수 없는 채널: {ch}")
    return errors


def verdict(f: dict[str, Any], rules: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """(자동 여부, 통과한 것, 막는 것). f는 문의 한 줄과 초안 검토 결과:
    channel, category_code, priority, urgency_flag, inquiry_count, status, has_blocking_missing, has_evidence,
    has_draft, issues(발송 검사에서 걸린 문장 목록), failed_checks(걸린 자체 검사 수), verify_passed.
    """
    passed: list[str] = []
    blocked: list[str] = []

    def chk(ok: bool, yes: str, no: str) -> None:
        (passed if ok else blocked).append(yes if ok else no)

    if not rules.get("enabled"):
        return False, passed, ["자동 처리가 꺼져 있음"]
    cat = f.get("category_code")
    name = CATEGORY_NAMES.get(cat, cat or "유형 미정")
    chk(rules["channels"].get(f.get("channel"), False), "채널 자동 처리 켜짐", "이 채널은 자동 처리 꺼짐")
    chk(cat not in ALWAYS_HUMAN, f"{name} 유형", f"{name}(고위험 유형)은 항상 사람이 확인")
    if cat not in ALWAYS_HUMAN:
        chk(bool(rules["cats"].get(cat)), "자동 대상 유형", f"{name}(자동 대상 아님)")
    chk(f.get("priority") in AUTO_PRIORITIES, f"우선순위 {f.get('priority')}", f"우선순위 {f.get('priority') or '미정'}는 사람이 확인")
    chk(f.get("urgency_flag") not in URGENT, "긴급도 일반", "안전·설비 정지 문의")
    chk((f.get("inquiry_count") or 1) <= 1, "단일 문의", "복합 문의는 사람이 확인")
    chk(f.get("status") in ("NEW", "IN_PROGRESS"), "처리 가능한 상태", "이미 처리 흐름이 진행된 건")
    chk(not f.get("has_blocking_missing"), "필수 정보 있음", "막는 정보 누락")
    chk(bool(f.get("has_evidence")), "근거 문서 있음", "근거 문서 없음")
    chk(bool(f.get("has_draft")), "답변 초안 있음", "답변 초안 없음")
    if f.get("has_draft"):
        issues = f.get("issues") or []
        chk(not issues, "발송 전 확인할 것 없음", f"확인이 필요한 것: {' / '.join(issues)}")
        chk(not f.get("failed_checks"), "자체 검사 통과", f"자체 검사 {f.get('failed_checks')}개 걸림")
        chk(bool(f.get("verify_passed")), "검증 통과", "검증을 통과하지 못했거나 하지 않음")
    return not blocked, passed, blocked
