"""이관 메일 연동 API (변경 add-escalation-mail-live).

- GET  /mail/config            메일 연동이 켜져 있는지, C/S 메일함·부서 도메인·받은 메일함 주소
- POST /mail/poll              받은 메일함을 지금 확인(스케줄러가 주기마다 하는 일과 같음)
- POST /mail/dept-reply-demo   시연용: 부서 메일함에서 C/S로 답장을 SMTP로 보냄. 연결은 다른 메일과 같이 poll이 한다
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, Mail, get_clients, get_conn, get_connect, get_mail
from app.api.tickets import process_dept_reply
from app.mail import build_dept_reply, collect_replies

router = APIRouter()
log = logging.getLogger(__name__)

MSG_OFF = "메일 연동이 꺼져 있음(MAIL_ENABLED)"
MSG_EMPTY = "내용을 입력하세요"
MSG_NOT_ESCALATED = "이관된 문의만 답장할 수 있음"


def _require(mail: Mail) -> None:
    if not mail.enabled:
        raise HTTPException(409, MSG_OFF)


@router.get("/mail/config", response_model=schemas.MailConfig)
def mail_config(mail: Mail = Depends(get_mail)) -> dict:
    s = mail.settings
    return {"enabled": s.mail_enabled, "cs_address": s.mail_cs_address, "dept_domain": s.mail_dept_domain,
            "inbox_url": s.mailpit_public_url, "poll_seconds": s.mail_poll_seconds}


def poll(conn: Connection, mail: Mail) -> dict:
    s = mail.settings
    found = collect_replies(conn, mail.inbox, cs_address=s.mail_cs_address, dept_domain=s.mail_dept_domain,
                            at=datetime.now(timezone.utc))
    for skipped in found.skipped:
        log.info("메일 건너뜀 %s: %s", skipped["subject"], skipped["reason"])
    return {"accepted": found.accepted, "skipped": found.skipped}


@router.post("/mail/poll", response_model=schemas.MailPolled)
def post_poll(background: BackgroundTasks, conn: Connection = Depends(get_conn), connect: Callable = Depends(get_connect),
              clients: Clients = Depends(get_clients), mail: Mail = Depends(get_mail)) -> dict:
    """받은 메일함을 지금 확인한다. 연결된 회신마다 그 하위 문의를 다시 처리한다(화면 [회신 등록]과 같음)."""
    _require(mail)
    try:
        out = poll(conn, mail)
    except Exception as exc:  # noqa: BLE001 — 메일 서버가 꺼져 있어도 API는 503으로 알린다
        raise HTTPException(503, f"받은 메일함을 읽지 못함: {exc}") from exc
    for item in out["accepted"]:
        background.add_task(process_dept_reply, connect, clients, item["sub_ticket_id"], item["run_id"])
    return out


def poll_and_reprocess(connect: Callable, clients: Clients, mail: Mail) -> dict:
    """스케줄러용: 확인하고 다시 처리까지 이 스레드에서 끝낸다."""
    with connect() as conn:
        out = poll(conn, mail)
    for item in out["accepted"]:
        process_dept_reply(connect, clients, item["sub_ticket_id"], item["run_id"])
    return out


class DemoReplyIn(BaseModel):
    sub_ticket_id: str
    body: str | None = None


@router.post("/mail/dept-reply-demo", status_code=202, response_model=schemas.MailDemoSent)
def post_demo_reply(data: DemoReplyIn, conn: Connection = Depends(get_conn), mail: Mail = Depends(get_mail)) -> dict:
    """시연용 부서 답장. 실제 메일 프로그램 대신 부서 메일함 주소로 SMTP 답장을 보낸다. 문의에 연결하는 일은 하지 않는다."""
    _require(mail)
    body = (data.body or "").strip()
    if not body:
        raise HTTPException(400, MSG_EMPTY)
    s = mail.settings
    try:
        message = build_dept_reply(conn, data.sub_ticket_id, body, cs_address=s.mail_cs_address, dept_domain=s.mail_dept_domain)
    except LookupError as exc:
        raise HTTPException(409, MSG_NOT_ESCALATED) from exc
    try:
        mail.sender.send(message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"메일을 보내지 못함: {exc}") from exc
    return {"sent": True, "sender": message["From"], "to": message["To"], "subject": message["Subject"]}
