"""상담원 도우미 L11 (변경 add-agent-assistant design 결정 3).

찾은 문서 절 안에서만 한국어로 답하고 출처 번호를 적게 한다. 고치거나 고객에게 보내지 않는다(CLAUDE.md 규칙 3).
호출은 generate_json 하나를 지난다(규칙 2). 지어낸 출처를 막는 일은 지시문이 아니라 이 파일의 코드가 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.llm.client import LlmError, Transport, generate_json
from app.retrieval.docs_free import DocHit

L11_PROMPT = "l11_assist_v2.md"
CALL_NAME = "L11"

NOT_FOUND = "찾지 못했습니다."
NOTE_NO_SOURCE = "근거가 되는 문서를 확정하지 못했습니다"
MAX_FOLLOWUPS = 3
MAX_FOLLOWUP_CHARS = 80
MAX_HISTORY = 6  # 직전 대화 줄 수(구현 선택)

SCHEMA: dict = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "answer": {"type": "string"},
        "used_sources": {"type": "array", "items": {"type": "integer"}},
        "followups": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["found", "answer", "used_sources", "followups"],
}

_NUM = re.compile(r"\d[\d,.]*")
# 답 속 숫자 점검용: 모델 이름·문서 번호·코드 안의 숫자(TG-INV-LSLV0750-iS7, S100, RMA-2026-0123)는 뺀다.
# 글자나 - _ § 바로 뒤에 붙은 숫자는 이름의 일부로 본다
_ANSWER_NUM = re.compile(r"(?<![A-Za-z0-9_\-§])\d[\d,.]*")


def _nums(text: str) -> list[str]:
    return [n.rstrip(".,").replace(",", "") for n in _NUM.findall(text)]


def _answer_nums(text: str) -> list[str]:
    return [n.rstrip(".,").replace(",", "") for n in _ANSWER_NUM.findall(text)]


@dataclass
class AssistResult:
    found: bool = False
    answer: str = NOT_FOUND
    used: list[int] = field(default_factory=list)  # 1부터 시작하는 출처 번호(보낸 것 안에 있는 것만)
    followups: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str | None = None  # LLM_TIMEOUT / LLM_INVALID_OUTPUT …


def _sources_text(hits: list[DocHit]) -> str:
    return "\n\n".join(f"[{i}] {h.doc_id} §{h.section_no} {h.title}\n{h.text}" for i, h in enumerate(hits, 1))


def _history_text(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"{role}: {text}" for role, text in history[-MAX_HISTORY:]) or "(none)"


def answer_question(
    transport: Transport,
    question: str,
    history: list[tuple[str, str]],
    hits: list[DocHit],
) -> AssistResult:
    """찾은 절(hits)로 답을 만든다. 모델이 두 번 실패하면 error를 채워 돌려준다(예외를 올리지 않는다)."""
    if not hits:
        return AssistResult()
    try:
        out = generate_json(
            transport, CALL_NAME, L11_PROMPT,
            {"question": question, "history": _history_text(history), "sources": _sources_text(hits)},
            SCHEMA,
        ).data
    except LlmError as exc:
        return AssistResult(error=exc.error_type)

    # 보낸 번호 밖의 출처는 버린다(지어낸 출처 방지)
    used = list(dict.fromkeys(n for n in out["used_sources"] if 1 <= n <= len(hits)))
    result = AssistResult(
        found=bool(out["found"]),
        answer=out["answer"].strip(),
        used=used,
        followups=[f.strip() for f in out["followups"] if f.strip()][:MAX_FOLLOWUPS],
    )
    result.followups = [f[:MAX_FOLLOWUP_CHARS] for f in result.followups]
    if result.found and not used:  # 출처 없는 답은 돌려주지 않는다
        result.found, result.answer = False, f"{NOT_FOUND} {NOTE_NO_SOURCE}."
        result.followups = []
        return result
    if not result.found:
        result.answer, result.used = result.answer or NOT_FOUND, []
        return result

    # 답에 나온 숫자가 쓴 절에 없으면 알린다(막지 않는다)
    allowed = {n for i in used for n in _nums(hits[i - 1].text)}
    stray = list(dict.fromkeys(n for n in _answer_nums(result.answer) if n not in allowed))
    if stray:
        result.notes.append(f"근거 밖 숫자: {', '.join(stray)}")
    return result
