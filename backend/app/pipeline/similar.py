"""처리 흐름 Q8b 유사 해결사례 (기술 명세서 v1.4 §4-7, 변경 add-similar-cases). 고장 진단(Q8a) 바로 뒤, 하위 문의마다."""

from __future__ import annotations

from psycopg import Connection

from app.llm.embed import Embedder
from app.pipeline.state import SubTicketState
from app.retrieval.cases import CaseIndex, similar_cases


def add_similar_cases(conn: Connection, embedder: Embedder, ticket_id: str, sub: SubTicketState,
                      index: CaseIndex | None = None) -> None:
    """질문 글은 Q8a와 같이 L1 영어 검색문 + 에러 코드, 검색문이 없으면 근거 문장(design 결정 2)."""
    query = sub.query_en or " ".join(sub.evidence_sentences) or None
    row = conn.execute("SELECT source_ticket_id FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    result = similar_cases(conn, embedder, sub.category_code, sub.product_family, sub.error_code, query,
                           row[0] if row else None, index)
    sub.similar_cases = result.as_output() if result else None
