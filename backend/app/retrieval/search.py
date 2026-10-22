"""문서 근거 검색 (FR-016, 기술 명세서 v1.4 §4-3, §4-4). 처리 흐름의 Q8.

꼬리표로 범위를 좁히고, 정책 우선 문서 → 유형별 우선 종류 → 범위 전체 순으로 넓힌다.
점수 = 코사인 유사도 + 0.2 × 정확 문자열(에러 코드, 펌웨어 버전) 포함. 상위 5개.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from psycopg import Connection

from app.llm.client import LlmError
from app.llm.embed import Embedder, embed_texts
from app.pipeline.state import DocCandidate

log = logging.getLogger(__name__)

TOP_K = 5  # §4-4 4번 (제안, T27)
EXACT_BONUS = 0.2  # §4-4 3번 (제안)

PRIORITY_TYPES = {  # §4-4 2번 표
    "TECH_SPEC": ["DS"], "COMPLIANCE": ["DS"],
    "DEFECT": ["TG"],
    "INSTALL": ["IG", "TG"],
    "FW_UPDATE": ["RN"],
    "MANUAL": ["IG", "TG", "RN", "DS", "MG"],
    "QUOTE": ["POL"], "ORDER_LEAD": ["POL"], "RETURN": ["POL"], "WARRANTY": ["POL"],
}
PRIORITY_POLICY = {  # §4-4 2번 표 "(POL-ORDER 우선)" 등
    "QUOTE": "POL-ORDER", "ORDER_LEAD": "POL-ORDER", "RETURN": "POL-RETURN", "WARRANTY": "POL-WARRANTY",
}

FLAG_NO_PRODUCT_DOCS = "제품 문서 미검색"
FLAG_NO_EVIDENCE = "근거 없음"
FLAG_SEARCH_FAILED = "검색 실패"


@dataclass
class EvidenceResult:
    candidates: list[DocCandidate] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _scope(product_code: str | None, family: str | None) -> tuple[str, list]:
    """범위 조건 (FR-016 처리 1, 예외 1행)."""
    parts, params = ["doc_type = 'POL'"], []
    if family:
        parts.append("(doc_type = 'FAQ' AND family = %s)")
        params.append(family)
    if product_code:
        parts.append("product_code = %s")
        params.append(product_code)
    return "(" + " OR ".join(parts) + ")", params


def _stages(category_code: str | None) -> list[tuple[str, list]]:
    stages: list[tuple[str, list]] = []
    if category_code in PRIORITY_POLICY:
        stages.append(("doc_id = %s", [PRIORITY_POLICY[category_code]]))
    if category_code in PRIORITY_TYPES:
        stages.append(("doc_type = ANY(%s)", [PRIORITY_TYPES[category_code]]))
    stages.append(("TRUE", []))
    return stages


def search_evidence(
    conn: Connection,
    embedder: Embedder,
    query_text: str | None,
    category_code: str | None,
    product_code: str | None,
    product_family: str | None,
    exact_terms: list[str | None] | None = None,
) -> EvidenceResult:
    result = EvidenceResult()
    if not product_code:
        result.flags.append(FLAG_NO_PRODUCT_DOCS)
    scope, scope_params = _scope(product_code, product_family)
    terms = [t for t in (exact_terms or []) if t]

    def fail(reason: str) -> EvidenceResult:
        log.warning("search failed: %s", reason)
        result.flags += [FLAG_SEARCH_FAILED, FLAG_NO_EVIDENCE]
        return result

    missing = conn.execute(
        f"SELECT count(*) FROM ref.doc_chunk WHERE {scope} AND embedding IS NULL", scope_params
    ).fetchone()[0]
    if missing or not query_text:
        return fail("색인 없음" if missing else "검색문 없음")
    try:
        (vector,) = embed_texts(embedder, "Q8", [query_text], "query")
    except LlmError as exc:
        return fail(exc.error_type)
    qvec = "[" + ",".join(map(str, vector)) + "]"

    for condition, params in _stages(category_code):
        try:
            rows = conn.execute(
                f"""SELECT chunk_id, doc_id, section_no, section_title, text,
                           1 - (embedding <=> %s::vector) AS similarity
                      FROM ref.doc_chunk
                     WHERE {scope} AND {condition}""",
                [qvec, *scope_params, *params],
            ).fetchall()
        except Exception as exc:  # 벡터 차원이 다른 색인 등
            conn.rollback()
            return fail(str(exc))
        if not rows:
            continue  # 앞 단계에 후보가 없을 때만 넓힌다(§4-4 2번, 기준 점수 T27 전)
        scored = []
        for chunk_id, doc_id, section_no, title, text, similarity in rows:
            bonus = EXACT_BONUS if any(t in text for t in terms) else 0.0
            scored.append(DocCandidate(chunk_id=chunk_id, doc_id=doc_id, section_no=section_no, title=title,
                                       score=round(float(similarity) + bonus, 6)))
        scored.sort(key=lambda c: (-c.score, c.chunk_id))
        result.candidates = scored[:TOP_K]
        return result

    result.flags.append(FLAG_NO_EVIDENCE)
    return result
