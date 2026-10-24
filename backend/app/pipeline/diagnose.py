"""처리 흐름 Q8a 고장 진단 (기술 명세서 v1.4 §2-1, §4-6). 하위 문의마다 진단 후보를 붙인다."""

from __future__ import annotations

from psycopg import Connection

from app.llm.embed import Embedder
from app.pipeline.state import SubTicketState
from app.retrieval.fault import SymptomVectors, diagnose


def add_diagnosis(conn: Connection, embedder: Embedder, sub: SubTicketState,
                  vectors: SymptomVectors | None = None) -> None:
    """질문 글은 L1 영어 검색문 + 에러 코드(§4-6 2번). 검색문이 없으면 근거 문장(C-140)."""
    query = sub.query_en or " ".join(sub.evidence_sentences) or None
    result = diagnose(conn, embedder, sub.category_code, sub.product_family, sub.product_code, sub.error_code,
                      query, vectors)
    sub.fault_candidates = result.candidates if result else []
    sub.diagnosis = result.as_output() if result else None
