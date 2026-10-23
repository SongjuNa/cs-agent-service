"""티켓 이력: 메시지·상태 변경·경고·우선순위 조정을 시각순 한 줄 목록으로 (명세서 v1.5 FR-030 처리 4,
기술 명세서 v1.4 §8-1 GET /tickets/{id}/timeline, 화면 정의서 v1 SCR-03 B-01).

이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

# 같은 시각이면 상태 변경 → 메시지 → 조정 → 경고 순(구현 선택)
ORDER = {"STATUS": 0, "MESSAGE": 1, "PRIORITY": 2, "ALERT_RAISED": 3, "ALERT_CLEARED": 4}

SQL = """
SELECT 'STATUS' AS kind, h.changed_at_utc AS at, s.seq, h.history_id AS id,
       jsonb_build_object('from_status', h.from_status, 'to_status', h.to_status, 'event_kind', h.event_kind,
                          'changed_by', h.changed_by, 'reason', h.reason) AS data
  FROM svc.ticket_status_history h JOIN svc.sub_ticket s ON s.sub_ticket_id = h.sub_ticket_id
 WHERE s.ticket_id = %(t)s
UNION ALL
SELECT 'MESSAGE', m.sent_at_utc, s.seq, m.message_id,
       jsonb_build_object('message_id', m.message_id, 'sender', m.sender, 'message_type', m.message_type,
                          'message_status', m.message_status, 'language', m.language, 'body', m.body,
                          'sent_by_name', m.sent_by_name, 'edited_yn', m.edited_yn,
                          'notice_transition', m.notice_transition, 'override_check', m.override_check)
  FROM svc.ticket_message m LEFT JOIN svc.sub_ticket s ON s.sub_ticket_id = m.sub_ticket_id
 WHERE m.ticket_id = %(t)s AND m.message_status IN ('SENT','RECEIVED')
UNION ALL
SELECT 'PRIORITY', p.adjusted_at_utc, s.seq, p.adjust_id,
       jsonb_build_object('from_priority', p.from_priority, 'to_priority', p.to_priority,
                          'from_fr_target_h', p.from_fr_target_h, 'from_res_target_h', p.from_res_target_h,
                          'to_fr_target_h', p.to_fr_target_h, 'to_res_target_h', p.to_res_target_h,
                          'reason_kind', p.reason_kind, 'reason', p.reason, 'adjusted_by', p.adjusted_by)
  FROM svc.priority_adjustment p JOIN svc.sub_ticket s ON s.sub_ticket_id = p.sub_ticket_id
 WHERE s.ticket_id = %(t)s
UNION ALL
SELECT 'ALERT_RAISED', a.raised_at_utc, s.seq, a.alert_id,
       jsonb_build_object('alert_type', a.alert_type, 'elapsed_h', a.elapsed_h, 'target_h', a.target_h)
  FROM svc.sla_alert a JOIN svc.sub_ticket s ON s.sub_ticket_id = a.sub_ticket_id
 WHERE s.ticket_id = %(t)s
UNION ALL
SELECT 'ALERT_CLEARED', a.cleared_at_utc, s.seq, a.alert_id, jsonb_build_object('alert_type', a.alert_type)
  FROM svc.sla_alert a JOIN svc.sub_ticket s ON s.sub_ticket_id = a.sub_ticket_id
 WHERE s.ticket_id = %(t)s AND a.cleared_at_utc IS NOT NULL
"""


def timeline(conn: Connection, ticket_id: str) -> list[dict[str, Any]] | None:
    """한 줄 = {kind, at, seq, id, ...종류별 값}. 없는 티켓이면 None. 리마인드는 sender SYSTEM, notice_transition REMINDER."""
    if conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone() is None:
        return None
    rows = conn.execute(SQL, {"t": ticket_id}).fetchall()
    out = [{"kind": kind, "at": at, "seq": seq, "id": id_, **data} for kind, at, seq, id_, data in rows]
    return sorted(out, key=lambda r: (r["at"], ORDER[r["kind"]], r["id"]))
