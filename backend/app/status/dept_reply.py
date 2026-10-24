"""이관 부서 회신 등록과 예외 부서 고객 메일 (명세서 v1.5 FR-033 처리 8·9, FR-031 처리 9, 기술 명세서 v1.4 §8-1).

회신 등록: ESCALATION_NOTE RECEIVED(sender DEPT) 한 행 + 전이 DEPT_REPLY, 그 하위 문의를 다시 처리할 run(DEPT_REPLY)을 연다.
예외 부서(FIELD_SVC, SALES_OPS) 메일: FINAL_REPLY DRAFT(sender DEPT)를 만든다. 발송은 `store.send_draft`가 DEPT_MAIL_SENT로 한다.
이 모듈은 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection

from app.db.store import add_step, finish_run, start_run
from app.masking import mask_text
from app.status.transitions import ConcurrentChange, transition

EXCEPTION_DEPTS = ("FIELD_SVC", "SALES_OPS")  # FR-033 처리 9
REPLY_LANGUAGE = "ko"  # 부서와 C/S 사이 글(C-163, 이관 메모 C-155와 같음)

MSG_EMPTY = "내용을 입력하세요"                                  # FR-033 예외 4행
MSG_WRONG_DEPT = "이관받은 부서만 회신할 수 있음"                 # 구현 선택 C-166
MSG_NOT_ESCALATED = "이관된 문의만 회신할 수 있음"                # 구현 선택 C-166
MSG_NOT_EXCEPTION = "고객 메일은 FIELD_SVC·SALES_OPS만 보낼 수 있음"  # 구현 선택 C-166


class DeptError(Exception):
    """회신·메일 거부. status는 API 응답 코드."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def _locked(conn: Connection, sub_ticket_id: str) -> tuple[str, str, int, str | None, str]:
    row = conn.execute("""SELECT ticket_id, status, version, escalated_to, (SELECT language FROM svc.ticket t
                                  WHERE t.ticket_id = s.ticket_id) FROM svc.sub_ticket s
                           WHERE sub_ticket_id = %s FOR UPDATE""", (sub_ticket_id,)).fetchone()
    if row is None:
        raise LookupError(sub_ticket_id)
    return row


def _refuse_not_escalated(conn: Connection, ticket_id: str, sub_ticket_id: str, status: str, event: str) -> None:
    """ESCALATED가 아니면 거부하고 실행 로그에 남긴다(FR-025 예외 1행, 이관 거부 C-157과 같은 모양)."""
    run_id = start_run(conn, ticket_id, sub_ticket_id, "AGENT_EDIT")
    with conn.transaction():
        add_step(conn, run_id, "T6", input_={"event_kind": event, "to_status": "IN_PROGRESS", "from_status": status},
                 result="FAILED", error_kind="VALIDATION", error=MSG_NOT_ESCALATED)
        finish_run(conn, run_id, "PARTIAL", "T6")
    raise DeptError(MSG_NOT_ESCALATED, 409)


def register_reply(conn: Connection, sub_ticket_id: str, body: str | None, agent_id: str, agent_dept: str | None,
                   at: datetime, expected_version: int | None = None) -> dict[str, Any]:
    """[회신 등록]: 검사 순서 본문 → 문의 → 버전 → 부서 → 상태(design 결정 1). 다시 처리 run 번호를 돌려준다."""
    body = (body or "").strip()
    if not body:
        raise DeptError(MSG_EMPTY, 400)
    with conn.transaction():
        ticket_id, status, version, escalated_to, _ = _locked(conn, sub_ticket_id)
        if expected_version is not None and expected_version != version:
            raise ConcurrentChange()
        if not escalated_to or (agent_dept or "").strip() != escalated_to:
            raise DeptError(MSG_WRONG_DEPT, 403)
        if status == "ESCALATED":
            (message_id,) = conn.execute(
                """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                       language, body, sent_by_name, mask_count)
                   VALUES (%s, %s, 'DEPT', 'ESCALATION_NOTE', 'RECEIVED', %s, %s, %s, %s, %s) RETURNING message_id""",
                (ticket_id, sub_ticket_id, at, REPLY_LANGUAGE, body, agent_id, mask_text(body)[1])).fetchone()
            transition(conn, sub_ticket_id, "IN_PROGRESS", "DEPT_REPLY", at, agent_id)
            run_id = start_run(conn, ticket_id, sub_ticket_id, "DEPT_REPLY")  # §2-4 새 run
    if status != "ESCALATED":
        _refuse_not_escalated(conn, ticket_id, sub_ticket_id, status, "DEPT_REPLY")
    return {"sub_ticket_id": sub_ticket_id, "status": "IN_PROGRESS", "reply_message_id": message_id, "run_id": run_id,
            "processing": True}


def check_mail_dept(escalated_to: str | None, agent_dept: str | None) -> None:
    """예외 부서 메일을 쓸 수 있는 부서인가(초안 만들 때·임시 저장·발송 때, §8-1, C-166)."""
    dept = (agent_dept or "").strip()
    if dept not in EXCEPTION_DEPTS:
        raise DeptError(MSG_NOT_EXCEPTION, 403)
    if dept != escalated_to:
        raise DeptError(MSG_WRONG_DEPT, 403)


def mail_dept_of(conn: Connection, sub_ticket_id: str) -> str | None:
    return conn.execute("SELECT escalated_to FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_ticket_id,)).fetchone()[0]


def save_mail_draft(conn: Connection, sub_ticket_id: str, body: str | None, agent_id: str, agent_dept: str | None,
                    at: datetime) -> dict[str, Any]:
    """예외 부서 고객 메일 초안: FINAL_REPLY DRAFT(sender DEPT). 안 보낸 초안이 있으면 그 본문을 바꾼다(C-165)."""
    body = (body or "").strip()
    if not body:
        raise DeptError(MSG_EMPTY, 400)
    with conn.transaction():
        ticket_id, status, _, escalated_to, language = _locked(conn, sub_ticket_id)
        check_mail_dept(escalated_to, agent_dept)
        if status != "ESCALATED":
            raise DeptError(MSG_NOT_ESCALATED, 409)
        row = conn.execute("""SELECT message_id FROM svc.ticket_message WHERE sub_ticket_id = %s AND sender = 'DEPT'
                                 AND message_type = 'FINAL_REPLY' AND message_status = 'DRAFT' AND superseded_at IS NULL
                               ORDER BY message_id DESC LIMIT 1""", (sub_ticket_id,)).fetchone()
        if row:
            conn.execute("UPDATE svc.ticket_message SET body = %s, mask_count = %s WHERE message_id = %s",
                         (body, mask_text(body)[1], row[0]))
            message_id = row[0]
        else:
            (message_id,) = conn.execute(
                """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                       language, body, sent_by_name, mask_count)
                   VALUES (%s, %s, 'DEPT', 'FINAL_REPLY', 'DRAFT', %s, %s, %s, %s, %s) RETURNING message_id""",
                (ticket_id, sub_ticket_id, at, language, body, agent_id, mask_text(body)[1])).fetchone()
    return {"sub_ticket_id": sub_ticket_id, "message_id": message_id}
