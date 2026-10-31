"""상담원 도우미: 문서 근거로 묻고 출처가 붙은 답을 받는다 (변경 add-agent-assistant, FR-초안-07).

답은 화면에만 보이고 초안·메시지·고객 발송에 쓰이지 않는다(CLAUDE.md 규칙 3). 아무것도 저장하지 않는다(규칙 4).
질문과 이어 묻기 대화는 임베딩과 모델에 보내기 직전 가린다(규칙 2, embed_texts·generate_json이 한다).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, get_clients, get_conn
from app.llm.assist import MAX_HISTORY, NOT_FOUND, answer_question
from app.llm.client import LlmError
from app.retrieval.docs_free import DocHit, search_docs

router = APIRouter()
log = logging.getLogger(__name__)

MAX_QUESTION = 500
MSG_EMPTY = "질문을 입력하세요"
MSG_TOO_LONG = f"질문은 {MAX_QUESTION}자 이하로 입력하세요"
NOTE_SEARCH_FAILED = "검색하지 못했습니다. 잠시 뒤 다시 시도하세요"
NOTE_NO_INDEX = "문서 색인이 아직 없습니다"
NOTE_ANSWER_FAILED = "답을 만들지 못했습니다. 아래 문서를 직접 확인하세요"


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class AskIn(BaseModel):
    question: str = ""
    product_code: str | None = None
    history: list[HistoryItem] = []


def _source(no: int, hit: DocHit) -> dict:
    return {"no": no, "chunk_id": hit.chunk_id, "doc_id": hit.doc_id, "section_no": hit.section_no, "title": hit.title}


@router.post("/assist/ask", response_model=schemas.AssistAnswer, response_model_exclude_unset=True)
def ask(body: AskIn, conn: Connection = Depends(get_conn), clients: Clients = Depends(get_clients)) -> dict:
    question = body.question.strip()
    if not question:
        raise HTTPException(400, MSG_EMPTY)
    if len(question) > MAX_QUESTION:
        raise HTTPException(400, MSG_TOO_LONG)
    history = [(h.role, h.text.strip()) for h in body.history[-MAX_HISTORY:] if h.text.strip()]

    try:
        hits = search_docs(conn, clients.embedder(), question, (body.product_code or "").strip() or None)
    except LlmError as exc:
        log.warning("assist search failed: %s", exc.error_type)
        note = NOTE_NO_INDEX if "색인" in str(exc) else NOTE_SEARCH_FAILED
        return {"found": False, "answer": NOT_FOUND, "sources": [], "followups": [], "notes": [note]}

    try:
        transport = clients.transport()
    except LlmError as exc:  # 키가 없을 때
        log.warning("assist transport unavailable: %s", exc.error_type)
        transport = None
    result = answer_question(transport, question, history, hits) if transport is not None else None

    if result is None or result.error:  # 모델이 실패하면 답 없이 찾은 절 목록만(design 결정 3 "실패")
        if result is not None:
            log.warning("assist answer failed: %s", result.error)
        return {"found": False, "answer": "", "sources": [_source(i, h) for i, h in enumerate(hits, 1)],
                "followups": [], "notes": [NOTE_ANSWER_FAILED]}

    sources = [_source(k, hits[i - 1]) for k, i in enumerate(result.used, 1)] if result.found else []
    return {"found": result.found, "answer": result.answer, "sources": sources,
            "followups": result.followups if result.found else [], "notes": result.notes}
