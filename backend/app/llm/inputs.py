"""언어 모델 입력 입구 (FR-038, 기술 명세서 v1.4 §7 위치 (1)).

모든 호출(L1~L8)은 입력을 보내기 직전에 prepare_llm_input을 지난다.
- 모든 글을 가린다(mask_fields).
- 보낸 사람 연락처(ticket)와 고객사 대표 연락처(customer) 열은 입력에 넣지 않는다 → 있으면 거부.
- 넣은 항목 이름 목록을 돌려줘 실행 로그에 남길 수 있게 한다(§6-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.masking import MaskingError, mask_fields

# 명세서 FR-038 처리 5·7 (ticket), 에이전트 설계서 v1.1 4-2절 공통 규칙 7 (customer)
CONTACT_FIELDS = frozenset(
    {
        "contact_name",
        "contact_email",
        "contact_phone",
        "primary_contact_name",
        "primary_contact_email",
        "primary_contact_phone",
    }
)


@dataclass(frozen=True)
class LlmInput:
    fields: dict[str, Any]
    mask_count: int
    field_names: list[str] = field(default_factory=list)


def prepare_llm_input(fields: dict[str, Any]) -> LlmInput:
    """언어 모델에 보낼 입력을 만든다. 연락처 항목이 있거나 가리기에 실패하면 MaskingError(VALIDATION)."""
    if not isinstance(fields, dict):
        raise MaskingError("LLM 입력은 사전(dict)이어야 한다")
    forbidden = sorted(CONTACT_FIELDS.intersection(fields))
    if forbidden:
        raise MaskingError(f"연락처 항목은 LLM 입력에 넣을 수 없다: {', '.join(forbidden)}")
    masked, count = mask_fields(fields)
    return LlmInput(fields=masked, mask_count=count, field_names=list(fields.keys()))
