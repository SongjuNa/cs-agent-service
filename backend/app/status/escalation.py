"""이관 확정 (명세서 v1.5 FR-033 처리 1~7, 기술 명세서 v1.4 §6-4·§8-1 `POST /sub-tickets/{id}/escalate`).

IN_PROGRESS인 하위 문의를 ESCALATED로 바꾸고 이관 부서·사유를 쓰며, 이관 메모를 ESCALATION_NOTE SENT로 남긴다.
원래 담당 부서는 그대로 두고, 그래프는 다시 돌리지 않는다. 고객 이관 안내 초안은 만들지 않는다(처리 5).
이 모듈은 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection

from app.db.store import add_step, finish_run, start_run
from app.masking import mask_text
from app.status.transitions import ConcurrentChange, transition

# schema.sql sub_ticket.escalation_reason CHECK 11값(화면 정의서 v1 CP-6)
REASONS = ("ONSITE_REQUIRED", "QUALITY_RETURN", "RMA_REQUIRED", "COMMERCIAL_TERMS", "CAUSE_ANALYSIS",
           "FW_UPDATE_FAILURE", "SPEC_INTERPRETATION", "P1", "OUT_OF_SCOPE_TEST", "CUSTOM_SPEC", "SAFETY")
NOTE_LANGUAGE = "ko"  # 상담원 사이 글(C-155)

MSG_NO_REASON = "이관 사유를 고르세요"                      # FR-033 예외 1행
MSG_ALREADY = "이미 이관됨({dept})"                         # 예외 2행
MSG_SAME_DEPT = "같은 부서로는 이관할 수 없음"               # 예외 3행
MSG_NOT_IN_PROGRESS = "처리 중인 문의만 이관할 수 있음"       # 처리 1, 화면 정의서 v1 P4
MSG_BAD_DEPT = "이관 부서를 고르세요"                       # 구현 선택(목록 밖·빈 값)
MSG_BAD_REASON = "이관 사유 코드가 목록에 없음"              # 구현 선택


class EscalateError(Exception):
    """이관 거부. status는 API 응답 코드."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def escalate(conn: Connection, sub_ticket_id: str, dept: str | None, reason_code: str | None, memo: str | None,
             agent_id: str, at: datetime, expected_version: int | None = None) -> dict[str, Any]:
    """검사 순서: 사유 → 이미 이관 → 처리 중 → 부서(design 결정 1). 한 트랜잭션으로 쓰고, 처리 중이 아니면 거부를 실행 로그에 남긴다."""
    reason_code, dept, memo = (reason_code or "").strip(), (dept or "").strip(), (memo or "").strip()
    if not reason_code:
        raise EscalateError(MSG_NO_REASON, 400)
    if reason_code not in REASONS:
        raise EscalateError(MSG_BAD_REASON, 400)
    with conn.transaction():
        row = conn.execute(
            """SELECT ticket_id, status, version, assigned_dept, escalated_to FROM svc.sub_ticket
                WHERE sub_ticket_id = %s FOR UPDATE""", (sub_ticket_id,)).fetchone()
        if row is None:
            raise LookupError(sub_ticket_id)
        ticket_id, status, version, assigned, escalated_to = row
        if expected_version is not None and expected_version != version:
            raise ConcurrentChange()
        if status == "ESCALATED":
            raise EscalateError(MSG_ALREADY.format(dept=escalated_to or "?"), 409)
        if status == "IN_PROGRESS":
            if not dept or not conn.execute("SELECT 1 FROM ref.department WHERE dept_code = %s", (dept,)).fetchone():
                raise EscalateError(MSG_BAD_DEPT, 400)
            if dept == assigned:
                raise EscalateError(MSG_SAME_DEPT, 400)
            conn.execute("""UPDATE svc.sub_ticket SET escalated = true, escalated_to = %s, escalation_reason = %s
                             WHERE sub_ticket_id = %s""", (dept, reason_code, sub_ticket_id))
            transition(conn, sub_ticket_id, "ESCALATED", "ESCALATE", at, agent_id, reason=reason_code)
            body = memo or f"이관: {dept} ({reason_code})"  # 본문 1자 이상(C-154)
            (message_id,) = conn.execute(
                """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                       language, body, sent_by_name, mask_count)
                   VALUES (%s, %s, 'AGENT', 'ESCALATION_NOTE', 'SENT', %s, %s, %s, %s, %s) RETURNING message_id""",
                (ticket_id, sub_ticket_id, at, NOTE_LANGUAGE, body, agent_id, mask_text(body)[1])).fetchone()
            version = conn.execute("SELECT version FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                   (sub_ticket_id,)).fetchone()[0]
    if status != "IN_PROGRESS":  # 허용되지 않은 전이: 거부하고 실행 로그에 남긴다(FR-025 예외 1행, 발송 API와 같은 모양)
        run_id = start_run(conn, ticket_id, sub_ticket_id, "AGENT_EDIT")
        with conn.transaction():
            add_step(conn, run_id, "T6", input_={"event_kind": "ESCALATE", "to_status": "ESCALATED", "from_status": status},
                     result="FAILED", error_kind="VALIDATION", error=MSG_NOT_IN_PROGRESS)
            finish_run(conn, run_id, "PARTIAL", "T6")
        raise EscalateError(MSG_NOT_IN_PROGRESS, 409)
    return {"sub_ticket_id": sub_ticket_id, "status": "ESCALATED", "escalated_to": dept, "escalation_reason": reason_code,
            "assigned_dept": assigned, "note_message_id": message_id, "version": version}
