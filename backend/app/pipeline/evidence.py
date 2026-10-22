"""처리 흐름 Q8 문서 검색 → Q9 숫자 조회 (기술 명세서 v1.4 §2-2). 하위 문의마다 근거 후보와 조회값을 붙인다."""

from __future__ import annotations

from psycopg import Connection

from app.llm.embed import Embedder
from app.pipeline.state import SubTicketState, TicketState
from app.retrieval.numbers import lookup_numbers
from app.retrieval.search import search_evidence


def _provided(sub: SubTicketState, name: str) -> str | None:
    for pf in sub.provided_fields:
        if pf.field == name and pf.value_norm:
            return pf.value_norm
    return None


def add_evidence(conn: Connection, embedder: Embedder, state: TicketState) -> TicketState:
    for sub in state.sub_tickets:
        # 검색문은 L1의 영어 검색문(§4-3 방식 A). 분류 실패로 없으면 근거 문장으로 대신한다
        query = sub.query_en or " ".join(sub.evidence_sentences) or None
        found = search_evidence(
            conn, embedder, query, sub.category_code, sub.product_code, sub.product_family,
            [sub.error_code, sub.current_fw],
        )
        numbers = lookup_numbers(
            conn, sub.category_code, sub.product_code, state.received_at,
            quantity=_provided(sub, "quantity"), current_fw=sub.current_fw,
            doc_candidates=found.candidates, required_date=_provided(sub, "required_date"),
        )
        sub.doc_candidates = found.candidates
        sub.lookups = numbers.lookups
        sub.flags += [f for f in found.flags + numbers.flags if f not in sub.flags]
    return state
