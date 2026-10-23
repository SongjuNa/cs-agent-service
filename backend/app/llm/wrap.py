"""L5 메일 인사말·맺음말 (FR-022, 에이전트 설계서 v1.1 4-7절, 기술 명세서 v1.4 §3-1 L5).

복합 문의 메일의 앞뒤 인사만 쓴다. 단락과 문의 상태 목록은 건드리지 않는다. 실패하면 고정 문구 F-2(부록 A-3).
"""

from __future__ import annotations

from app.llm.client import LlmError, Transport, generate_json
from app.llm.drafts import LANGUAGE_NAMES

L5_PROMPT = "l5_wrap_v1.md"
SCHEMA: dict = {
    "type": "object",
    "properties": {"greeting": {"type": "string"}, "closing": {"type": "string"}},
    "required": ["greeting", "closing"],
}
# 부록 A-3 F-2 (L5 실패)
F2_GREETING = "Dear Customer,\nThank you for your inquiry."
F2_CLOSING = "Please let us know if you have any further questions."


def write_wrap(transport: Transport, language: str, topics: list[str]) -> tuple[str, str, str]:
    """(인사말, 맺음말, 출처 "L5" 또는 "F-2")."""
    fields = {"language_name": LANGUAGE_NAMES.get(language, language), "answered_topics": ", ".join(topics)}
    try:
        data = generate_json(transport, "L5", L5_PROMPT, fields, SCHEMA).data
    except LlmError:
        return F2_GREETING, F2_CLOSING, "F-2"
    greeting, closing = data["greeting"].strip(), data["closing"].strip()
    if not greeting or not closing:
        return F2_GREETING, F2_CLOSING, "F-2"
    return greeting, closing, "L5"
