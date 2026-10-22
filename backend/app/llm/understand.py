"""L1 문의 이해 (FR-004·005·007, 기술 명세서 v1.4 §3-1·§3-2, 에이전트 설계서 v1.1 4-3절).

본문 언어, 문의 유형 10종, 긴급도 6값, 근거 문장, 영어 검색문을 한 번에 받고 코드로 검사한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.llm.client import LlmError, Transport, generate_json, load_prompt

PROMPT_FILE = "l1_understand_v1.md"
CATEGORY_DEFINITIONS_FILE = "l1_category_definitions_v1.md"
URGENCY_CRITERIA_FILE = "l1_urgency_criteria_v1.md"

# 기술 명세서 §3-2 열거값
CATEGORIES = [
    "TECH_SPEC", "INSTALL", "DEFECT", "FW_UPDATE", "MANUAL",
    "COMPLIANCE", "QUOTE", "ORDER_LEAD", "RETURN", "WARRANTY",
]
# 우선순서 (FR-007 처리 3): 앞일수록 높다
URGENCY_ORDER = ["SAFETY", "SITE_DOWN", "PROD_IMPACT", "COMMISSION", "DEADLINE", "NONE"]
# schema.sql svc.ticket.language CHECK의 15개 언어
LANGUAGES = ["ar", "de", "en", "es", "fr", "id", "it", "ja", "pl", "pt", "ru", "th", "tr", "vi", "zh"]

CONFIDENCE_MIN = 0.6  # 기술 명세서 §3-6

FLAG_LANG_UNCERTAIN = "언어 판정 불확실"
FLAG_LOW_CONFIDENCE = "확신 낮음"
FLAG_CLASSIFY_FAILED = "분류 실패"
FLAG_URGENCY_FAILED = "긴급도 판정 실패"
FLAG_MULTI_REQUEST = "복합 문의 가능(FR-006, 2순위)"

SCHEMA: dict = {
    "type": "object",
    "properties": {
        "body_language": {"type": "string", "enum": LANGUAGES},
        "body_language_confidence": {"type": "number"},
        "sub_tickets": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "seq": {"type": "integer"},
                    "category_code": {"type": "string", "enum": CATEGORIES},
                    "category_confidence": {"type": "number"},
                    "evidence_sentences": {"type": "array", "items": {"type": "string"}},
                    "urgency_flag": {"type": "string", "enum": URGENCY_ORDER},
                    "urgency_evidence": {"type": ["string", "null"]},
                    "query_en": {"type": "string"},
                },
                "required": [
                    "seq", "category_code", "category_confidence", "evidence_sentences",
                    "urgency_flag", "urgency_evidence", "query_en",
                ],
            },
        },
    },
    "required": ["body_language", "body_language_confidence", "sub_tickets"],
}


@dataclass
class Understanding:
    """L1 결과를 검사한 뒤의 값. 하위 문의는 1순위에서 1개만 쓴다(config.yaml)."""

    body_language: str
    body_language_uncertain: bool
    category_code: str | None
    category_confidence: float | None
    evidence_sentences: list[str]
    urgency_flag: str
    urgency_evidence: str | None
    query_en: str | None
    flags: list[str] = field(default_factory=list)
    field_names: list[str] = field(default_factory=list)
    prompt_version: str | None = None


def urgency_text(urgency_rows: list[tuple[str, str]]) -> str:
    """{urgency_codebook} 자리에 넣는 글: 6값 설명 원문 + 기준서 v0.3 2장 판단 표."""
    lines = [f"- {code}: {desc}" for code, desc in urgency_rows]
    return "\n".join(lines) + "\n\n" + load_prompt(URGENCY_CRITERIA_FILE).strip()


def higher_urgency(a: str, b: str) -> str:
    return a if URGENCY_ORDER.index(a) <= URGENCY_ORDER.index(b) else b


def merge_same_category(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """같은 유형이 두 번 나오면 하나로 합친다. 근거 문장은 이어 붙이고 긴급도는 높은 쪽(§3-2)."""
    merged: dict[str, dict[str, Any]] = {}
    for req in sorted(requests, key=lambda r: r["seq"]):
        cat = req["category_code"]
        if cat not in merged:
            merged[cat] = dict(req, evidence_sentences=list(req["evidence_sentences"]))
            continue
        kept = merged[cat]
        kept["evidence_sentences"] += [s for s in req["evidence_sentences"] if s not in kept["evidence_sentences"]]
        top = higher_urgency(kept["urgency_flag"], req["urgency_flag"])
        if top != kept["urgency_flag"]:
            kept["urgency_flag"], kept["urgency_evidence"] = req["urgency_flag"], req["urgency_evidence"]
        kept["category_confidence"] = min(kept["category_confidence"], req["category_confidence"])
    return list(merged.values())


def understand(
    transport: Transport,
    body_masked: str,
    channel: str,
    language: str,
    product_family: str | None,
    urgency_rows: list[tuple[str, str]],
) -> Understanding:
    """L1을 부르고 검사한다.

    코드값 밖 응답이 두 번이면(LLM_INVALID_OUTPUT) 값을 비우고 흐름을 계속한다(FR-004 예외, FR-005 처리 3,
    FR-007 처리 4). 시간 초과·그 밖의 오류 두 번은 LlmError를 그대로 올린다(FR-005 예외, 실행 FAILED).
    """
    fields = {
        "category_definitions": load_prompt(CATEGORY_DEFINITIONS_FILE).strip(),
        "urgency_codebook": urgency_text(urgency_rows),
        "channel": channel,
        "language": language,
        "product_family_or_unknown": product_family or "unknown",
        "body_masked": body_masked,
    }
    try:
        result = generate_json(transport, "L1", PROMPT_FILE, fields, SCHEMA)
    except LlmError as exc:
        if exc.error_type != "LLM_INVALID_OUTPUT":
            raise
        return Understanding(
            body_language=language,
            body_language_uncertain=True,
            category_code=None,
            category_confidence=None,
            evidence_sentences=[],
            urgency_flag="NONE",
            urgency_evidence=None,
            query_en=None,
            flags=[FLAG_LANG_UNCERTAIN, FLAG_CLASSIFY_FAILED, FLAG_URGENCY_FAILED],
            field_names=list(fields),
            prompt_version=PROMPT_FILE.removesuffix(".md"),
        )

    data = result.data
    flags: list[str] = []

    body_language = data["body_language"]
    uncertain = data["body_language_confidence"] < CONFIDENCE_MIN
    if uncertain:
        body_language = language
        flags.append(FLAG_LANG_UNCERTAIN)

    requests = merge_same_category(data["sub_tickets"])
    if len(requests) > 1:
        flags.append(FLAG_MULTI_REQUEST)
    first = requests[0]
    if first["category_confidence"] < CONFIDENCE_MIN:
        flags.append(FLAG_LOW_CONFIDENCE)
    # 긴급도는 모든 요청 중 가장 높은 값 (FR-007 처리 3). 다른 요청의 SAFETY를 버리지 않는다
    top = min(requests, key=lambda r: URGENCY_ORDER.index(r["urgency_flag"]))

    return Understanding(
        body_language=body_language,
        body_language_uncertain=uncertain,
        category_code=first["category_code"],
        category_confidence=first["category_confidence"],
        evidence_sentences=first["evidence_sentences"],
        urgency_flag=top["urgency_flag"],
        urgency_evidence=top["urgency_evidence"],
        query_en=first["query_en"],
        flags=flags,
        field_names=result.field_names,
        prompt_version=result.prompt_version,
    )
