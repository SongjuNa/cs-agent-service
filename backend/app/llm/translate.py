"""고객 원문의 한국어 번역 L12 (변경 add-body-translation). 상담원이 읽는 참고용이다.

번역문은 고객에게 가는 글, 초안, 다른 모델 호출의 입력에 쓰지 않는다(CLAUDE.md 규칙 3).
모델은 generate_json으로만 부른다. 보내기 직전 가리기는 generate_json이 한다(규칙 2).
"""

from __future__ import annotations

from app.llm.client import Transport, generate_json
from app.llm.drafts import LANGUAGE_NAMES

L12_PROMPT = "l12_translate_v1.md"
L12_SCHEMA = {"type": "object", "properties": {"translation": {"type": "string"}}, "required": ["translation"]}


def translate_body(transport: Transport, language: str, body: str) -> str:
    """원문을 한국어로 옮긴다. 두 번 실패하면 LlmError를 그대로 올린다."""
    fields = {"source_language_name": LANGUAGE_NAMES.get(language, language), "customer_message": body}
    return generate_json(transport, "L12", L12_PROMPT, fields, L12_SCHEMA).data["translation"].strip()
