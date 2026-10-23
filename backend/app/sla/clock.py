"""SLA 두 시계 (명세서 v1.5 FR-026, 기술 명세서 v1.4 §6-4).

값은 저장하지 않고 DB 함수 svc.inquiry_sla(as_of)로 기준 시각마다 계산한다.
1차 응답 시계는 멈추지 않고, 해결 시계는 WAITING_CUSTOMER 구간을 뺀다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

NOTE_NO_TARGET = "SLA 미정"                 # FR-026 예외 1행
NOTE_NEGATIVE = "시간 기록 확인 필요"       # FR-026 예외 3행


def clocks(conn: Connection, sub_ticket_ids: list[str], as_of: datetime | None = None) -> dict[str, dict[str, Any]]:
    as_of = as_of or datetime.now(timezone.utc)
    cur = conn.execute(
        """SELECT sub_ticket_id, fr_target_h, res_target_h, fr_elapsed_h, fr_status, wait_h,
                  res_elapsed_h, res_status, remaining_h
             FROM svc.inquiry_sla(%s) WHERE sub_ticket_id = ANY(%s)""",
        (as_of, sub_ticket_ids),
    )
    names = [d.name for d in cur.description]
    out = {}
    for row in cur.fetchall():
        sla = dict(zip(names, row))
        sla["as_of_utc"] = as_of
        notes = []
        if sla["fr_target_h"] is None or sla["res_target_h"] is None:
            notes.append(NOTE_NO_TARGET)
        for key in ("fr_elapsed_h", "res_elapsed_h", "wait_h"):
            if sla[key] is not None and sla[key] < 0:
                sla[key] = 0
                if NOTE_NEGATIVE not in notes:
                    notes.append(NOTE_NEGATIVE)
        sla["notes"] = notes
        out[sla.pop("sub_ticket_id")] = sla
    return out
