"""자동 발송 상태 (변경 add-auto-send-views). 접수함은 같은 계산을 SQL로 한다(db/inbox.py AUTO_SQL).

NONE = 자동 발송한 적 없음, PENDING = 자동 발송했고 사후 검수 전, REVIEWED = 사후 검수 끝.
자동 발송 메시지 = 보낸이 SYSTEM, 이름 AI_AUTO인 SENT 최종 답변(status/autosend.py AUTO_AGENT).
"""

from __future__ import annotations

from psycopg import Connection


def auto_state(conn: Connection, sub_ticket_id: str) -> str:
    row = conn.execute(
        """SELECT EXISTS (SELECT 1 FROM svc.auto_review r WHERE r.message_id = m.message_id)
             FROM svc.ticket_message m
            WHERE m.sub_ticket_id = %s AND m.sender = 'SYSTEM' AND m.sent_by_name = 'AI_AUTO'
              AND m.message_type = 'FINAL_REPLY' AND m.message_status = 'SENT'
            ORDER BY m.message_id DESC LIMIT 1""", (sub_ticket_id,)).fetchone()
    return "NONE" if row is None else ("REVIEWED" if row[0] else "PENDING")
