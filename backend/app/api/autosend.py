"""자동 처리 규칙과 사후 검수 (변경 add-auto-send). 판정·실행은 app/status/autosend.py, 규칙은 app/rules/autosend.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn
from app.rules.autosend import ALWAYS_HUMAN, AUTO_CATS, CHANNELS, CATEGORY_NAMES
from app.status.autosend import AUTO_AGENT, AutoError, load_rules, review, save_rules

router = APIRouter()
MSG_NO_AGENT = "상단에서 상담원을 먼저 고르세요"
MSG_NOT_FOUND = "문의를 찾을 수 없음"


def _agent(x_agent_id: str | None) -> str:
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, MSG_NO_AGENT)
    return x_agent_id.strip()


def _view(conn: Connection) -> dict:
    rules = load_rules(conn)
    auto_total, pending = conn.execute(
        """SELECT count(DISTINCT m.sub_ticket_id), count(DISTINCT m.sub_ticket_id) FILTER (WHERE r.message_id IS NULL)
             FROM svc.ticket_message m LEFT JOIN svc.auto_review r ON r.message_id = m.message_id
            WHERE m.sender = 'SYSTEM' AND m.sent_by_name = %s AND m.message_type = 'FINAL_REPLY' AND m.message_status = 'SENT'""",
        (AUTO_AGENT,)).fetchone()
    total = conn.execute("SELECT count(*) FROM svc.sub_ticket").fetchone()[0]
    return {**rules, "always_human": list(ALWAYS_HUMAN), "auto_cats": list(AUTO_CATS), "channel_list": list(CHANNELS),
            "category_names": CATEGORY_NAMES, "stats": {"auto_total": auto_total, "auto_pending": pending, "total": total}}


@router.get("/auto-rules", response_model=schemas.AutoRules, response_model_exclude_unset=True)
def get_rules(conn: Connection = Depends(get_conn)) -> dict:
    """자동 처리 설정과 지금까지 자동 발송한 건수."""
    return _view(conn)


@router.put("/auto-rules", response_model=schemas.AutoRules, response_model_exclude_unset=True)
def put_rules(data: schemas.AutoRulesIn, conn: Connection = Depends(get_conn), x_agent_id: str | None = Header(default=None)) -> dict:
    """설정을 저장한다. 항상 사람이 확인하는 유형을 자동 대상으로 바꾸려 하면 400."""
    agent = _agent(x_agent_id)
    try:
        save_rules(conn, data.model_dump(), agent)
    except AutoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return _view(conn)


@router.post("/sub-tickets/{sub_ticket_id}/auto-review", response_model=schemas.AutoReviewed, response_model_exclude_unset=True)
def post_review(sub_ticket_id: str, conn: Connection = Depends(get_conn), x_agent_id: str | None = Header(default=None)) -> dict:
    """자동 발송된 문의의 사후 검수를 끝냈다고 기록한다(한 번만)."""
    agent = _agent(x_agent_id)
    if conn.execute("SELECT 1 FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_ticket_id,)).fetchone() is None:
        raise HTTPException(404, MSG_NOT_FOUND)
    try:
        return review(conn, sub_ticket_id, agent)
    except AutoError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
