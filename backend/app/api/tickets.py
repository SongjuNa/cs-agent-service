"""접수와 상세 (기술 명세서 v1.4 §2-4, §8-1 POST /tickets, GET /tickets/{id})."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api.deps import Clients, get_clients, get_conn, get_connect
from app.db.detail import ticket_detail
from app.db.store import IntakeError, create_ticket, save_outcome, start_run, ticket_input
from app.pipeline.graph import RunOutcome, run_ticket

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


def process_ticket(connect: Callable, clients: Clients, ticket_id: str) -> None:
    """백그라운드 처리: 실행 기록을 열고 처리 흐름을 돌려 결과를 저장한다(§2-4)."""
    with connect() as conn:
        sub_ticket_id = f"{ticket_id}-1"
        run_id = start_run(conn, ticket_id, sub_ticket_id, "INTAKE")
        try:
            with conn.transaction():  # 처리 흐름은 읽기만 한다. 오류가 나도 연결을 깨끗이 둔다
                outcome = run_ticket(conn, clients.transport(), clients.embedder(), ticket_input(conn, ticket_id))
        except Exception as exc:  # noqa: BLE001 — 어떤 오류든 실행 실패로 남긴다
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc))
        save_outcome(conn, run_id, ticket_id, outcome)


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
