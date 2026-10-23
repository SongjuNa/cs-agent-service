"""접수와 상세 (기술 명세서 v1.4 §2-4, §8-1 POST /tickets, GET /tickets/{id})."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api.deps import Clients, get_clients, get_conn, get_connect
from app.db.detail import ticket_detail
from app.db.replies import ReplyError, record_reply
from app.db.store import IntakeError, create_ticket, save_outcome, start_run, ticket_input
from app.pipeline.graph import RunOutcome, run_ticket
from app.pipeline.reprocess import reextract
from app.pipeline.runlog import RunLog

router = APIRouter()


class TicketIn(BaseModel):
    """접수 입력: gold.v_inputs의 입력 열 + 제목·출처(svc.ticket 열)."""

    channel: str
    customer_id: str
    product_code: str | None = None
    language: str
    inquiry_body: str
    received_at_utc: datetime | None = None
    inquiry_subject: str | None = None
    source: str = "SIMULATOR"
    source_ticket_id: str | None = None


MSG_REPROCESS_FAILED = "자동 처리 실패. 다시 처리"  # FR-032 예외 4행


class ReplyIn(BaseModel):
    """고객 회신 입력 (기술 명세서 §8-1 body, language, received_at, target_sub_ticket_ids)."""

    body: str
    language: str | None = None
    received_at: datetime | None = None
    target_sub_ticket_ids: list[str] | None = None


def process_ticket(connect: Callable, clients: Clients, ticket_id: str, trigger: str = "INTAKE") -> None:
    """백그라운드 처리: 실행 기록을 열고 처리 흐름을 돌려 결과를 저장한다(§2-4).

    trigger: 접수는 INTAKE, 다시 처리는 RETRY. 다시 처리도 새 run이고 이전 run은 남는다(FR-036 처리 5).
    """
    with connect() as conn:
        run_id = start_run(conn, ticket_id, None, trigger)  # 티켓 그래프 실행(schema.sql agent_run 주석)
        runlog = RunLog.from_settings()
        try:
            with conn.transaction():  # 처리 흐름은 읽기만 한다. 오류가 나도 연결을 깨끗이 둔다
                outcome = run_ticket(conn, clients.transport(), clients.embedder(), ticket_input(conn, ticket_id),
                                     runlog=runlog)
        except Exception as exc:  # noqa: BLE001 — 어떤 오류든 실행 실패로 남긴다
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc),
                                 runlog=runlog)
        save_outcome(conn, run_id, ticket_id, outcome)


def reprocess_reply(connect: Callable, clients: Clients, ticket_id: str, reply_id: int, target_ids: list[str]) -> None:
    """고객 회신 재처리: 대상 문의를 Q1부터(§2-4). 실패해도 회신과 전이는 그대로 둔다(FR-032 예외 4행)."""
    with connect() as conn:
        run_id = start_run(conn, ticket_id, target_ids[0] if len(target_ids) == 1 else None, "CUSTOMER_REPLY")
        runlog = RunLog.from_settings()
        try:
            with conn.transaction():
                outcome = run_ticket(conn, clients.transport(), clients.embedder(),
                                     {"ticket_id": ticket_id, "target_ids": target_ids}, understand_fn=reextract,
                                     runlog=runlog)
        except Exception as exc:  # noqa: BLE001
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc),
                                 runlog=runlog)
        if outcome.run_status != "SUCCESS":
            outcome.message = MSG_REPROCESS_FAILED
        save_outcome(conn, run_id, ticket_id, outcome, reply_id=reply_id)


@router.post("/tickets", status_code=201)
def post_ticket(data: TicketIn, background: BackgroundTasks, conn: Connection = Depends(get_conn),
                connect: Callable = Depends(get_connect), clients: Clients = Depends(get_clients)) -> dict:
    try:
        ticket_id = create_ticket(conn, data.model_dump())
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc
    background.add_task(process_ticket, connect, clients, ticket_id)
    return {"ticket_id": ticket_id, "processing": True}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, conn: Connection = Depends(get_conn)) -> dict:
    detail = ticket_detail(conn, ticket_id)
    if detail is None:
        raise HTTPException(404, "문의를 찾을 수 없음")
    return detail


@router.post("/tickets/{ticket_id}/replies", status_code=201)
def post_reply(ticket_id: str, data: ReplyIn, background: BackgroundTasks,
               x_agent_id: str | None = Header(default=None), conn: Connection = Depends(get_conn),
               connect: Callable = Depends(get_connect), clients: Clients = Depends(get_clients)) -> dict:
    """고객 회신 입력(FR-032): 저장·전이 뒤 대상 문의를 백그라운드로 다시 처리한다."""
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    try:
        out = record_reply(conn, ticket_id, data.body, data.language, data.received_at,
                           data.target_sub_ticket_ids, x_agent_id.strip())
    except LookupError as exc:
        raise HTTPException(404, "문의를 찾을 수 없음") from exc
    except ReplyError as exc:
        raise HTTPException(400, str(exc)) from exc
    if out["reprocess"]:
        background.add_task(reprocess_reply, connect, clients, ticket_id, out["message_id"], out["reprocess"])
    return {**out, "processing": bool(out["reprocess"])}
