"""초안 다루기: 임시 저장, 대역 다시 만들기, 다시 검증, 승인·발송 (FR-031, FR-039, FR-049, 기술 명세서 v1.4 §8-1).

발송은 SENT 행을 새로 쓰는 이 API와 자동 발송(status/autosend.py)만 한다(CLAUDE.md 규칙 3, 변경 add-auto-send). 발송 뒤 상태 전이는 FR-025·FR-031 처리 4.
예외 부서 메일(sender DEPT)은 자체 대조·대역·검증 없이 본문만 저장·발송하고 DEPT_MAIL_SENT로 전이한다(FR-031 처리 9, D34).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
import psycopg
from psycopg import Connection, errors
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, get_clients, get_conn
from app.db.sendcheck import send_issues
from app.db.store import (add_self_check, add_step, body_sha, check_body, draft_object, draft_sources, finish_run,
                          insert_gloss, intake_step, load_draft, save_verify, send_draft, start_run, update_draft_body)
from app.llm.drafts import FLAG_GLOSS_FAILED, write_gloss
from app.llm.verify import KIND_NAMES, verify_draft
from app.llm.client import RecordingTransport
from app.pipeline.reprocess import dept_reply_text
from app.pipeline.runlog import RunLog
from app.status.dept_reply import DeptError, check_mail_dept, mail_dept_of
from app.status.transitions import ConcurrentChange

router = APIRouter()

MSG_SENT = "이미 발송된 초안"
MSG_SAVE_FAILED = "저장하지 못함. 다시 시도"
MSG_DEPT_NO_VERIFY = "부서 메일은 검증하지 않음"  # FR-031 처리 9, 구현 선택 C-165


class BodyIn(BaseModel):
    body: str


class SendIn(BaseModel):
    final_body: str
    override_check: bool = False
    expected_version: int | None = None  # 상세를 읽을 때의 version (FR-025 예외 2행)


def _draft(conn: Connection, message_id: int) -> dict:
    draft = load_draft(conn, message_id)
    if draft is None:
        raise HTTPException(404, "초안을 찾을 수 없음")
    return draft


def _dept_check(conn: Connection, draft: dict, x_agent_dept: str | None) -> None:
    """예외 부서 메일이면 고른 부서가 이관받은 예외 부서인지 본다(§8-1 "초안 만들 때와 send 때 모두", C-166)."""
    try:
        check_mail_dept(mail_dept_of(conn, draft["sub_ticket_id"]), x_agent_dept)
    except DeptError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


def _make_gloss(conn: Connection, clients: Clients, draft: dict, run_id: int) -> bool:
    """L7 대역을 다시 만들어 새 행으로 남긴다. 성공하면 True."""
    obj = draft_object(conn, draft)
    obj.gloss = None
    runlog = RunLog.from_settings()  # 노드가 아닌 동작도 같은 기록으로 시간·사용량을 남긴다(§6-5)

    def make(_):
        return write_gloss(RecordingTransport(clients.transport(), runlog), obj)

    try:
        obj = runlog.timed("gloss", make)(None)
    except Exception:  # noqa: BLE001 — 키 없음 등도 대역 실패로 본다
        obj.flags.append(FLAG_GLOSS_FAILED)
    with conn.transaction():
        if obj.gloss:
            insert_gloss(conn, draft["message_id"], obj.gloss)
        add_step(conn, run_id, "Q13", output={"message_id": draft["message_id"], "gloss": obj.gloss is not None},
                 result="SUCCESS" if obj.gloss else "FAILED", **runlog.step_fields("Q13"))
    return obj.gloss is not None


@router.put("/messages/{message_id}", response_model=schemas.Saved, response_model_exclude_unset=True)
def put_message(message_id: int, data: BodyIn, conn: Connection = Depends(get_conn),
                clients: Clients = Depends(get_clients), x_agent_dept: str | None = Header(default=None)) -> dict:
    """임시 저장: DRAFT 본문만 바꾸고 대역을 다시 만든다. 검증은 다시 부르지 않는다(추가 결정 가3).

    예외 부서 메일은 자체 대조 없이 본문과 대역만(C-165).
    """
    draft = _draft(conn, message_id)
    if draft["message_status"] != "DRAFT":
        raise HTTPException(409, MSG_SENT)
    if not data.body.strip():
        raise HTTPException(400, "내용을 입력하세요")
    dept = draft["sender"] == "DEPT"
    if dept:
        _dept_check(conn, draft, x_agent_dept)
    try:
        run_id = start_run(conn, draft["ticket_id"], draft["sub_ticket_id"], "AGENT_EDIT")
        with conn.transaction():
            update_draft_body(conn, message_id, data.body)
            if not dept:  # 부서 메일은 Q11을 거치지 않는다(FR-031 처리 9)
                check = check_body(conn, draft["message_type"], draft["sub_ticket_id"], data.body)  # 고친 본문의 ① 대조(코드)
                add_self_check(conn, run_id, draft["sub_ticket_id"], "DRAFT_CHECK", check["passed"],
                               {**check, "body_sha256": body_sha(data.body)}, message_id)
                add_step(conn, run_id, "Q11", output=check)
    except psycopg.Error as exc:  # 화면 정의서 v2 P8
        raise HTTPException(500, MSG_SAVE_FAILED) from exc
    draft["body"] = data.body
    gloss_ok = _make_gloss(conn, clients, draft, run_id)
    with conn.transaction():
        finish_run(conn, run_id, "SUCCESS" if gloss_ok else "PARTIAL", "Q13")
    return {"message_id": message_id, "gloss": gloss_ok}


@router.post("/messages/{message_id}/gloss", response_model=schemas.Saved, response_model_exclude_unset=True)
def post_gloss(message_id: int, conn: Connection = Depends(get_conn), clients: Clients = Depends(get_clients)) -> dict:
    """대역 다시 만들기(FR-039 예외 1행)."""
    draft = _draft(conn, message_id)
    run_id = start_run(conn, draft["ticket_id"], draft["sub_ticket_id"], "RETRY")
    ok = _make_gloss(conn, clients, draft, run_id)
    with conn.transaction():
        finish_run(conn, run_id, "SUCCESS" if ok else "FAILED", "Q13")
    if not ok:
        raise HTTPException(502, "대역을 만들지 못함")
    return {"message_id": message_id, "gloss": True}


@router.post("/messages/{message_id}/verify", response_model=schemas.Verified, response_model_exclude_unset=True)
def post_verify(message_id: int, conn: Connection = Depends(get_conn), clients: Clients = Depends(get_clients)) -> dict:
    """다시 검증(FR-049): L8 1회, 결과는 VERIFY 새 행."""
    draft = _draft(conn, message_id)
    if draft["sender"] == "DEPT":
        raise HTTPException(400, MSG_DEPT_NO_VERIFY)
    run_id = start_run(conn, draft["ticket_id"], draft["sub_ticket_id"], "RETRY")
    sources, lookups, _, evidence = draft_sources(conn, draft["sub_ticket_id"])
    runlog = RunLog.from_settings()

    def check(_):
        return verify_draft(RecordingTransport(clients.transport(), runlog), draft_object(conn, draft), evidence,
                            sources, lookups, dept_reply=dept_reply_text(conn, draft["sub_ticket_id"]))

    try:
        result = runlog.timed("verify", check)(None)
    except Exception as exc:  # noqa: BLE001 — 키 없음 등. 검증 실패 행으로 남긴다
        from app.llm.verify import VerifyResult
        result = VerifyResult(error=getattr(exc, "error_type", "UNKNOWN"))
    with conn.transaction():
        save_verify(conn, run_id, draft["sub_ticket_id"], message_id, draft["body"], result)
        add_step(conn, run_id, "Q14", output={"message_id": message_id, "state": result.state},
                 result="FAILED" if result.error else "SUCCESS", **runlog.step_fields("Q14"))
        finish_run(conn, run_id, "FAILED" if result.error else "SUCCESS", "Q14")
    return {"message_id": message_id, "state": result.state, "mark": result.mark()}


@router.post("/messages/{message_id}/send", response_model=schemas.Sent, response_model_exclude_unset=True)
def post_send(message_id: int, data: SendIn, conn: Connection = Depends(get_conn),
              x_agent_id: str | None = Header(default=None), x_agent_dept: str | None = Header(default=None)):
    """승인·발송(FR-031 처리 1·2·3·5). 확인이 필요한 것이 있으면 409 + 목록, override_check로 다시 보내면 발송."""
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    if not data.final_body.strip():
        raise HTTPException(400, "내용을 입력하세요")
    draft = _draft(conn, message_id)
    if draft["message_status"] != "DRAFT":
        raise HTTPException(409, MSG_SENT)

    if draft["sender"] == "DEPT":  # 예외 부서 메일: 대조·검증 없이(FR-031 처리 9, D34)
        _dept_check(conn, draft, x_agent_dept)
        issues, notes = [], []
    else:
        issues, notes = send_issues(conn, draft, data.final_body)
    if issues and not data.override_check:
        return JSONResponse(status_code=409, content={"detail": "확인 필요", "issues": issues, "notes": notes})
    try:
        sent_id, refused = send_draft(conn, draft, data.final_body, x_agent_id.strip(),
                                      bool(issues) and data.override_check, expected_version=data.expected_version)
    except errors.UniqueViolation as exc:  # 같은 초안의 두 번째 SENT (FR-031 예외 4행)
        raise HTTPException(409, MSG_SENT) from exc
    except ConcurrentChange as exc:  # FR-025 예외 2행
        raise HTTPException(409, str(exc)) from exc
    if refused:  # 발송은 기록, 상태는 그대로 (FR-031 예외 3행)
        notes = [*notes, refused]
    return {"sent_message_id": sent_id, "override_check": bool(issues) and data.override_check, "notes": notes,
            "status_changed": refused is None}


