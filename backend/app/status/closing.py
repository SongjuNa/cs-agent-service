"""168시간 무응답 자동 종료 (명세서 v1.5 FR-025 처리 4·4-1, D20, D22, 기술 명세서 v1.4 §6-4 주기 점검 3·4).

기준 시각(as_of)을 받아 스케줄러는 지금을, 시연·채점은 지정 시각을 넘긴다("시계 돌리기").
전이 시각은 점검 시각이 아니라 마지막 발송 시각 + 168시간이다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from psycopg import Connection

from app.status.transitions import transition

NO_REPLY = timedelta(hours=168)

# (지금 상태, 기준 발송 종류, 사건, final_action)
RULES = [
    ("WAITING_CUSTOMER", "INFO_REQUEST", "NO_REPLY_168H", "CLOSED_NO_RESPONSE"),  # §6-4 점검 3, D22
    ("RESOLVED", "FINAL_REPLY", "NO_REPLY_168H_AFTER_RESOLVED", None),            # §6-4 점검 4, D20
]


def close_due(conn: Connection, as_of: datetime) -> list[tuple[str, str, datetime]]:
    """마지막 SENT 시각 + 168시간 ≤ as_of이고 그 뒤 고객 회신이 없는 문의를 닫는다.

    (sub_ticket_id, 사건, 전이 시각) 목록을 돌려준다.
    """
    closed = []
    for status, sent_type, event, final_action in RULES:
        rows = conn.execute(
            """SELECT s.sub_ticket_id, max(m.sent_at_utc) AS sent_at
                 FROM svc.sub_ticket s
                 JOIN svc.ticket_message m
                   ON m.sub_ticket_id = s.sub_ticket_id AND m.message_type = %s AND m.message_status = 'SENT'
                WHERE s.status = %s
                GROUP BY s.sub_ticket_id
               HAVING max(m.sent_at_utc) + %s <= %s
                  AND NOT EXISTS (SELECT 1 FROM svc.ticket_message r
                                   WHERE r.sub_ticket_id = s.sub_ticket_id AND r.message_type = 'CUSTOMER_REPLY'
                                     AND r.sent_at_utc > max(m.sent_at_utc))""",
            (sent_type, status, NO_REPLY, as_of),
        ).fetchall()
        for sub_ticket_id, sent_at in rows:
            at = sent_at + NO_REPLY
            transition(conn, sub_ticket_id, "CLOSED", event, at, "SYSTEM", final_action=final_action)
            closed.append((sub_ticket_id, event, at))
    return closed
