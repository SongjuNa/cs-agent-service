"""접수와 상세 (기술 명세서 v1.4 §2-4, §8-1 POST /tickets, GET /tickets/{id})."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, get_clients, get_conn, get_connect
from app.db.detail import ticket_detail
from app.db.inbox import InboxQuery, inbox
from app.db.runs import latest_pipeline_run
from app.db.replies import ReplyError, record_reply
from app.db.timeline import timeline
from app.db.store import IntakeError, create_ticket, save_outcome, start_run, ticket_input
from app.pipeline.graph import RunOutcome, run_ticket
from app.pipeline.reprocess import keep_agent_edits, reextract, reuse, with_dept_reply
from app.pipeline.runlog import RunLog
from app.status.autosend import auto_send_ticket

router = APIRouter()
log = logging.getLogger(__name__)


class TicketIn(BaseModel):
    """접수 입력: gold.v_inputs의 입력 열 + 제목·출처(svc.ticket 열)."""

    channel: str | None = None  # 빠진 칸도 항목별 오류로 돌려준다(FR-001 처리 1)
    customer_id: str | None = None
    product_code: str | None = None
    language: str | None = None
    inquiry_body: str | None = None
    received_at_utc: datetime | None = None
    inquiry_subject: str | None = None
    source: str | None = None  # SIMULATOR / LOAD / REPLAY. 비우면 원본 번호로 정한다
    source_ticket_id: str | None = None
    contact_name: str | None = None  # 보낸 사람 연락처 원문(FR-001 입력 표 v1.5 가-7). 처리 흐름에는 넣지 않는다
    contact_email: str | None = None
    contact_phone: str | None = None


MSG_NO_TICKET = "티켓을 찾을 수 없음"  # FR-030 예외 1행
MSG_REPROCESS_FAILED = "자동 처리 실패. 다시 처리"  # FR-032 예외 4행


class ReplyIn(BaseModel):
    """고객 회신 입력 (기술 명세서 §8-1 body, language, received_at, target_sub_ticket_ids)."""

    body: str
    language: str | None = None
    received_at: datetime | None = None
    target_sub_ticket_ids: list[str] | None = None


def process_ticket(connect: Callable, clients: Clients, ticket_id: str, trigger: str = "INTAKE",
                   run_id: int | None = None) -> None:
    """백그라운드 처리: 실행 기록을 열고 처리 흐름을 돌려 결과를 저장한다(§2-4).

    trigger: 접수는 INTAKE, 다시 처리는 RETRY. 다시 처리도 새 run이고 이전 run은 남는다(FR-036 처리 5).
    다시 처리는 상담원이 고친 값을 이어 받는다(reprocess.keep_agent_edits, C-112).
    run_id: 요청이 미리 연 실행(다시 시도는 응답 전에 열어 화면이 바로 "처리 중"을 본다).
    """
    with connect() as conn:
        if run_id is None:
            run_id = start_run(conn, ticket_id, None, trigger)  # 티켓 그래프 실행(테이블 정의서 agent_run.ticket_id)
        runlog = RunLog.from_settings()
        try:
            with conn.transaction():  # 처리 흐름은 읽기만 한다. 오류가 나도 연결을 깨끗이 둔다
                outcome = run_ticket(conn, clients.transport(), clients.embedder(), ticket_input(conn, ticket_id),
                                     understand_fn=keep_agent_edits if trigger == "RETRY" else None, runlog=runlog)
        except Exception as exc:  # noqa: BLE001 — 어떤 오류든 실행 실패로 남긴다
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc),
                                 runlog=runlog)
        save_outcome(conn, run_id, ticket_id, outcome)
        if outcome.run_status in ("SUCCESS", "PARTIAL"):  # 자동 발송(변경 add-auto-send): 실패해도 처리 결과는 그대로
            try:
                auto_send_ticket(conn, ticket_id)
            except Exception:  # noqa: BLE001
                log.exception("자동 발송 검토 실패: %s", ticket_id)


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


@router.post("/tickets", status_code=201, response_model=schemas.Accepted, response_model_exclude_unset=True)
def post_ticket(data: TicketIn, background: BackgroundTasks, conn: Connection = Depends(get_conn),
                connect: Callable = Depends(get_connect), clients: Clients = Depends(get_clients)) -> dict:
    try:
        ticket_id = create_ticket(conn, data.model_dump())
    except IntakeError as exc:  # 항목별 오류(FR-001 처리 1, 화면 정의서 v1 SCR-01-11)
        raise HTTPException(400, {"message": str(exc), "errors": [{"field": f, "message": m} for f, m in exc.errors]}) from exc
    background.add_task(process_ticket, connect, clients, ticket_id)
    return {"ticket_id": ticket_id, "processing": True}


def process_edit(connect: Callable, clients: Clients, sub_ticket_id: str, run_id: int, record: dict) -> None:
    """상담원 수정 뒤 그 하위 문의를 규칙 단계(Q2)부터 다시 돌린다(FR-030 처리 6, §2-4 부분 재실행)."""
    ticket_id = sub_ticket_id.rsplit("-", 1)[0]
    with connect() as conn:
        runlog = RunLog.from_settings()
        try:
            with conn.transaction():
                outcome = run_ticket(conn, clients.transport(), clients.embedder(),
                                     {"ticket_id": ticket_id, "target_ids": [sub_ticket_id], "agent_edit": record},
                                     understand_fn=reuse, runlog=runlog)
        except Exception as exc:  # noqa: BLE001
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc),
                                 runlog=runlog)
        save_outcome(conn, run_id, ticket_id, outcome, edit=record)


def process_dept_reply(connect: Callable, clients: Clients, sub_ticket_id: str, run_id: int) -> None:
    """이관 부서 회신 뒤 그 하위 문의를 다시 처리해 회신을 반영한 답변 초안을 만든다(FR-033 처리 8, §2-4, C-160)."""
    ticket_id = sub_ticket_id.rsplit("-", 1)[0]
    with connect() as conn:
        runlog = RunLog.from_settings()
        try:
            with conn.transaction():
                outcome = run_ticket(conn, clients.transport(), clients.embedder(),
                                     {"ticket_id": ticket_id, "target_ids": [sub_ticket_id]},
                                     understand_fn=with_dept_reply, runlog=runlog)
        except Exception as exc:  # noqa: BLE001
            outcome = RunOutcome(None, "FAILED", error_type=getattr(exc, "error_type", "UNKNOWN"), message=str(exc),
                                 runlog=runlog)
        if outcome.run_status != "SUCCESS":
            outcome.message = MSG_REPROCESS_FAILED
        save_outcome(conn, run_id, ticket_id, outcome)


MSG_PROCESSING = "처리 중"
MSG_NOTHING_TO_RETRY = "다시 처리할 실행이 없음"
MSG_CLOSED = "종료된 문의입니다"  # 화면 정의서 v1 SCR-03-P8


@router.post("/tickets/{ticket_id}/reprocess", status_code=202, response_model=schemas.Accepted, response_model_exclude_unset=True)
def reprocess(ticket_id: str, background: BackgroundTasks, conn: Connection = Depends(get_conn),
              connect: Callable = Depends(get_connect), clients: Clients = Depends(get_clients)) -> dict:
    """다시 시도·다시 처리: 같은 티켓을 새 run(RETRY)에서 처음부터 다시 돌린다(AC-001-4, FR-030 처리 5, §2-4).

    처리 중이 아니면 언제나 연다. 이전 DRAFT는 저장 때 superseded가 되고 발송한 메시지는 그대로다(C-98 해소).
    """
    run = latest_pipeline_run(conn, ticket_id)
    if run is None:
        if conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone() is None:
            raise HTTPException(404, MSG_NO_TICKET)
        raise HTTPException(409, MSG_NOTHING_TO_RETRY)
    if run["busy"]:
        raise HTTPException(409, MSG_PROCESSING)
    open_count = conn.execute("SELECT count(*) FILTER (WHERE status <> 'CLOSED') FROM svc.sub_ticket WHERE ticket_id = %s",
                              (ticket_id,)).fetchone()[0]
    if not open_count:  # 화면 정의서 v1 SCR-03 ⑥ 종료 "버튼 전부 비활성"
        raise HTTPException(409, MSG_CLOSED)
    with conn.transaction():  # 같은 티켓의 다시 시도가 겹치지 않게 잠그고 실행을 먼저 연다
        conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s FOR UPDATE", (ticket_id,))
        if latest_pipeline_run(conn, ticket_id)["busy"]:
            raise HTTPException(409, MSG_PROCESSING)
        run_id = start_run(conn, ticket_id, None, "RETRY")
    background.add_task(process_ticket, connect, clients, ticket_id, "RETRY", run_id)
    return {"ticket_id": ticket_id, "processing": True, "run_id": run_id}


def _list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@router.get("/tickets", response_model=schemas.Inbox, response_model_exclude_unset=True)
def list_tickets(dept: str | None = None, status: str | None = None, priority: str | None = None,
                 alert: str | None = None, channel: str | None = None, needs_info: bool = False,
                 has_draft: bool = False, composite: bool = False, q: str | None = None,
                 include_closed: bool = False, page: int = Query(1, ge=1), size: int = Query(50, ge=1),
                 sort: str | None = None, as_of: datetime | None = None, assignee: str | None = None,
                 turn: str | None = None, depth: str | None = None, me: str | None = None,
                 auto: bool = False, conn: Connection = Depends(get_conn)) -> dict:
    """접수함(FR-029, §8-1). 여러 값은 쉼표로(status=NEW,IN_PROGRESS).

    assignee: 담당 상담원 이름, turn: ME·DEPT·CUSTOMER·DONE, depth: DEEP·NORMAL·QUICK,
    me: counts.mine을 셀 상담원 이름(변경 add-inbox-turn-depth), auto: 자동 발송한 줄만(변경 add-auto-send-views)."""
    return inbox(conn, InboxQuery(dept=(dept or "").strip() or None, status=_list(status), priority=_list(priority),
                                  alert=_list(alert), channel=_list(channel), needs_info=needs_info,
                                  has_draft=has_draft, composite=composite, q=q, include_closed=include_closed,
                                  page=page, size=size, sort=sort, as_of=as_of,
                                  assignee=(assignee or "").strip() or None, turn=_list(turn), depth=_list(depth),
                                  me=(me or "").strip() or None, auto=auto))


@router.get("/tickets/{ticket_id}", response_model=schemas.Detail, response_model_exclude_unset=True)
def get_ticket(ticket_id: str, conn: Connection = Depends(get_conn), as_of: datetime | None = None,
               x_agent_dept: str | None = Header(default=None)) -> dict:
    # as_of: SLA 두 시계의 기준 시각(접수함·나의 업무 현황과 같은 뜻, 비우면 지금). 화면의 "스냅샷" 기준 시각용(구현 선택)
    detail = ticket_detail(conn, ticket_id, agent_dept=(x_agent_dept or "").strip() or None,  # 부서별 작성 영역(C-164)
                           as_of=as_of)
    if detail is None:
        raise HTTPException(404, MSG_NO_TICKET)
    return detail


@router.get("/tickets/{ticket_id}/timeline", response_model=list[schemas.TimelineItem], response_model_exclude_unset=True)
def get_timeline(ticket_id: str, conn: Connection = Depends(get_conn)) -> list[dict]:
    """메시지·상태 변경·경고·조정을 시각순으로(FR-030 처리 4, §8-1)."""
    rows = timeline(conn, ticket_id)
    if rows is None:
        raise HTTPException(404, MSG_NO_TICKET)
    return rows


@router.post("/tickets/{ticket_id}/replies", status_code=201, response_model=schemas.ReplyAccepted, response_model_exclude_unset=True)
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
