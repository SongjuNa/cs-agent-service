"""하위 문의 동작: 우선순위 조정과 미리 보기(FR-028, SCR-03-P3), 분류 직접 수정(FR-030 처리 6), 이관(FR-033, SCR-03-P4),
이관 부서 회신 등록과 예외 부서 메일 초안(FR-033 처리 8·9) (기술 명세서 v1.4 §8-1)."""

from __future__ import annotations

from datetime import datetime, timezone

from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, Mail, get_clients, get_conn, get_connect, get_mail
from app.api.tickets import process_dept_reply, process_edit
from app.db.edits import Edit, EditError, apply_edit
from app.mail import send_request
from app.sla.adjust import AdjustError, adjust, preview
from app.status.dept_reply import DeptError, register_reply, save_mail_draft
from app.status.escalation import EscalateError, escalate
from app.status.transitions import ConcurrentChange

router = APIRouter()

MSG_NOT_FOUND = "문의를 찾을 수 없음"


class PriorityIn(BaseModel):
    new_priority: str
    reason_kind: str | None = None
    reason_text: str | None = None
    confirm_breach: bool = False          # 즉시 위반 확인(FR-028 예외 3행)
    expected_version: int | None = None   # FR-025 예외 2행


def _error(exc: AdjustError) -> JSONResponse:
    content = {"detail": str(exc)}
    if exc.preview is not None:
        content["preview"] = exc.preview
    return JSONResponse(status_code=exc.status, content=jsonable_encoder(content))


@router.get("/sub-tickets/{sub_ticket_id}/priority", response_model=schemas.AdjustPreview, response_model_exclude_unset=True)
def get_preview(sub_ticket_id: str, new_priority: str, conn: Connection = Depends(get_conn)):
    """저장 없이 이전·새 목표와 즉시 위반 여부(구현 선택, P3 미리 보기)."""
    try:
        return preview(conn, sub_ticket_id, new_priority, datetime.now(timezone.utc))
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except AdjustError as exc:
        return _error(exc)


@router.post("/sub-tickets/{sub_ticket_id}/priority", response_model=schemas.Adjusted, response_model_exclude_unset=True)
def post_priority(sub_ticket_id: str, data: PriorityIn, conn: Connection = Depends(get_conn),
                  x_agent_id: str | None = Header(default=None)):
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    try:
        return adjust(conn, sub_ticket_id, data.new_priority, data.reason_kind, data.reason_text, x_agent_id.strip(),
                      datetime.now(timezone.utc), confirm_breach=data.confirm_breach,
                      expected_version=data.expected_version)
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except ConcurrentChange as exc:
        raise HTTPException(409, str(exc)) from exc
    except AdjustError as exc:
        return _error(exc)


class FieldIn(BaseModel):
    field: str
    value: str | None = None


class EditIn(BaseModel):
    """유형·긴급도·제품·반품 구분·받은 항목(§8-1 PATCH /sub-tickets). 고칠 것만 보낸다."""

    category_code: str | None = None
    urgency_flag: str | None = None
    product_code: str | None = None
    return_kind: str | None = None
    received_fields: list[FieldIn] = []
    expected_version: int | None = None  # FR-025 예외 2행, FR-030 예외 4행


@router.patch("/sub-tickets/{sub_ticket_id}", status_code=202, response_model=schemas.EditAccepted, response_model_exclude_unset=True)
def patch_sub_ticket(sub_ticket_id: str, data: EditIn, background: BackgroundTasks,
                     conn: Connection = Depends(get_conn), connect: Callable = Depends(get_connect),
                     clients: Clients = Depends(get_clients), x_agent_id: str | None = Header(default=None)) -> dict:
    """상담원 수정 → "상담원 수정" 표시, 규칙 단계부터 다시 처리(FR-030 처리 6, AC-030-5, §2-4 부분 재실행)."""
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    edit = Edit(category_code=data.category_code, urgency_flag=data.urgency_flag, product_code=data.product_code,
                return_kind=data.return_kind, received_fields=[f.model_dump() for f in data.received_fields],
                expected_version=data.expected_version)
    try:
        out = apply_edit(conn, sub_ticket_id, edit, x_agent_id.strip(), datetime.now(timezone.utc))
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except EditError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    background.add_task(process_edit, connect, clients, sub_ticket_id, out["run_id"], out["record"])
    return {"sub_ticket_id": sub_ticket_id, "processing": True, "run_id": out["run_id"], "version": out["version"],
            "changes": out["changes"]}


class EscalateIn(BaseModel):
    """이관 팝업 P4(§8-1): 부서·사유 코드 필수, 메모 선택."""

    dept: str | None = None
    reason_code: str | None = None
    memo: str | None = None
    expected_version: int | None = None  # FR-025 예외 2행
    send_mail: bool = False  # 이관 요청을 메일로도 보낸다. 메일 연동(MAIL_ENABLED)이 켜져 있으면 실제로 보낸다(add-escalation-mail-live)


@router.post("/sub-tickets/{sub_ticket_id}/escalate", response_model=schemas.Escalated, response_model_exclude_unset=True)
def post_escalate(sub_ticket_id: str, data: EscalateIn, conn: Connection = Depends(get_conn),
                  mail: Mail = Depends(get_mail), x_agent_id: str | None = Header(default=None)) -> dict:
    """이관 확정 → ESCALATED, ESCALATION_NOTE SENT(FR-033 처리 1~4). 이관 안내 초안은 만들지 않는다(처리 5).

    send_mail이고 메일 연동이 켜져 있으면 부서 메일함으로 요청 메일을 실제로 보낸다(add-escalation-mail-live).
    메일이 실패해도 이관은 확정하고, 이관 메모의 via_mail을 false로 써서 이력이 "메일 발송"이라고 하지 않게 한다.
    """
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    sent: dict = {}
    mailer = None
    if data.send_mail and mail.enabled:
        s = mail.settings

        def mailer() -> bool:
            result = send_request(conn, mail.sender, sub_ticket_id, data.memo, sender=s.mail_cs_address,
                                  dept_domain=s.mail_dept_domain, app_base_url=s.app_base_url)
            sent.update(result.as_dict())
            return result.sent
    try:
        out = escalate(conn, sub_ticket_id, data.dept, data.reason_code, data.memo, x_agent_id.strip(),
                       datetime.now(timezone.utc), expected_version=data.expected_version, send_mail=data.send_mail,
                       mailer=mailer)
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except ConcurrentChange as exc:
        raise HTTPException(409, str(exc)) from exc
    except EscalateError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    if sent:
        out["mail"] = sent
    return out


class DeptBodyIn(BaseModel):
    """[회신 등록]·예외 부서 메일 본문(§8-1 body)."""

    body: str | None = None
    expected_version: int | None = None  # FR-025 예외 2행
    via_mail: bool = False  # 부서가 메일로 회신해 온 것으로 기록한다(add-escalation-mail)


def _agent(x_agent_id: str | None) -> str:
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    return x_agent_id.strip()


@router.post("/sub-tickets/{sub_ticket_id}/dept-reply", status_code=202, response_model=schemas.DeptReplyAccepted, response_model_exclude_unset=True)
def post_dept_reply(sub_ticket_id: str, data: DeptBodyIn, background: BackgroundTasks,
                    conn: Connection = Depends(get_conn), connect: Callable = Depends(get_connect),
                    clients: Clients = Depends(get_clients), x_agent_id: str | None = Header(default=None),
                    x_agent_dept: str | None = Header(default=None)) -> dict:
    """이관 부서 [회신 등록] → ESCALATION_NOTE RECEIVED, IN_PROGRESS, 그 하위 문의 다시 처리(FR-033 처리 8, §2-4)."""
    agent = _agent(x_agent_id)
    try:
        out = register_reply(conn, sub_ticket_id, data.body, agent, x_agent_dept, datetime.now(timezone.utc),
                             expected_version=data.expected_version, via_mail=data.via_mail)
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except ConcurrentChange as exc:
        raise HTTPException(409, str(exc)) from exc
    except DeptError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    background.add_task(process_dept_reply, connect, clients, sub_ticket_id, out["run_id"])
    return out


@router.post("/sub-tickets/{sub_ticket_id}/dept-mail", status_code=201, response_model=schemas.DeptMailSaved, response_model_exclude_unset=True)
def post_dept_mail(sub_ticket_id: str, data: DeptBodyIn, conn: Connection = Depends(get_conn),
                   x_agent_id: str | None = Header(default=None), x_agent_dept: str | None = Header(default=None)) -> dict:
    """예외 부서 고객 메일 초안(FINAL_REPLY DRAFT, sender DEPT). 승인은 `POST /messages/{id}/send`(FR-031 처리 9)."""
    agent = _agent(x_agent_id)
    try:
        return save_mail_draft(conn, sub_ticket_id, data.body, agent, x_agent_dept, datetime.now(timezone.utc))
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except DeptError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
