"""고객 원문 한국어 번역 (변경 add-body-translation). 상담원이 읽는 참고용이며 저장은 svc.ticket.body_ko 한 곳이다.

이미 저장돼 있으면 모델을 부르지 않는다(다시 열어도 같은 번역). 번역문은 고객 발송·초안·다른 모델 호출에 쓰지 않는다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api import schemas
from app.api.deps import Clients, get_clients, get_conn
from app.llm.client import LlmError
from app.llm.translate import translate_body

router = APIRouter()
log = logging.getLogger(__name__)

MSG_NO_TICKET = "티켓을 찾을 수 없음"
MSG_FAILED = "번역하지 못했습니다. 잠시 뒤 다시 시도하세요"


@router.post("/tickets/{ticket_id}/translate", response_model=schemas.Translated, response_model_exclude_unset=True)
def translate(ticket_id: str, conn: Connection = Depends(get_conn), clients: Clients = Depends(get_clients)) -> dict:
    row = conn.execute("SELECT inquiry_body, coalesce(body_language, language), body_ko FROM svc.ticket WHERE ticket_id = %s",
                       (ticket_id,)).fetchone()
    if row is None:
        raise HTTPException(404, MSG_NO_TICKET)
    body, language, saved = row
    if saved:
        return {"ticket_id": ticket_id, "body_ko": saved, "cached": True}
    try:
        text = translate_body(clients.transport(), language, body)
    except LlmError:
        log.warning("번역 실패: %s", ticket_id)
        raise HTTPException(502, MSG_FAILED) from None
    if not text:
        raise HTTPException(502, MSG_FAILED)
    with conn.transaction():  # 동시에 눌렀을 때 먼저 저장된 값을 덮어쓰지 않는다
        conn.execute("UPDATE svc.ticket SET body_ko = %s WHERE ticket_id = %s AND body_ko IS NULL", (text, ticket_id))
    final = conn.execute("SELECT body_ko FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()[0]
    return {"ticket_id": ticket_id, "body_ko": final, "cached": False}
