"""내부 메모 (변경 add-internal-notes, 최신 목업 "내부 메모").

상담원끼리 남기는 메모다. 고객에게 보내지 않고, 언어 모델 입력·실행 로그에도 넣지 않는다.
수정·삭제 주소는 없다(남긴 사람과 시각이 기록으로 남는다). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import get_conn

router = APIRouter()
MAX_LEN = 2000  # svc.internal_note.body CHECK
MSG_NO_TICKET = "티켓을 찾을 수 없음"
MSG_EMPTY = "메모를 입력하세요"
MSG_TOO_LONG = f"메모는 {MAX_LEN}자 이하로 입력하세요"
MSG_NO_AGENT = "상단에서 상담원을 먼저 고르세요"


class NoteIn(BaseModel):
    body: str


def _exists(conn: Connection, ticket_id: str) -> None:
    if conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone() is None:
        raise HTTPException(404, MSG_NO_TICKET)


@router.get("/tickets/{ticket_id}/notes", response_model=list[schemas.Note], response_model_exclude_unset=True)
def list_notes(ticket_id: str, conn: Connection = Depends(get_conn)) -> list[dict]:
    """메모를 시각순으로(오래된 것이 위)."""
    _exists(conn, ticket_id)
    cur = conn.execute("""SELECT note_id, ticket_id, body, author, created_at_utc FROM svc.internal_note
                           WHERE ticket_id = %s ORDER BY created_at_utc, note_id""", (ticket_id,))
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


@router.post("/tickets/{ticket_id}/notes", status_code=201, response_model=schemas.Note, response_model_exclude_unset=True)
def add_note(ticket_id: str, data: NoteIn, conn: Connection = Depends(get_conn),
             x_agent_id: str | None = Header(default=None)) -> dict:
    """메모 한 줄을 남긴다. 앞뒤 공백은 지우고, 비었거나 2000자를 넘으면 400."""
    body = data.body.strip()
    if not body:
        raise HTTPException(400, MSG_EMPTY)
    if len(body) > MAX_LEN:
        raise HTTPException(400, MSG_TOO_LONG)
    author = (x_agent_id or "").strip()
    if not author:
        raise HTTPException(400, MSG_NO_AGENT)
    _exists(conn, ticket_id)
    cur = conn.execute("""INSERT INTO svc.internal_note (ticket_id, body, author) VALUES (%s, %s, %s)
                          RETURNING note_id, ticket_id, body, author, created_at_utc""", (ticket_id, body, author))
    names = [c.name for c in cur.description]
    return dict(zip(names, cur.fetchone()))
