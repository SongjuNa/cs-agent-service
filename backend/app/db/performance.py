"""내 실적 (변경 add-my-performance, 최신 목업 나의 업무 현황의 "내 실적"). 한 상담원이 최근 며칠 동안 한 일을 날짜별로 센다.

처리 = 내가 보낸 정보 요청·답변(발송) + 내가 한 이관 + 내가 한 우선순위 조정. 나의 업무 현황의 "오늘 처리한 건수"(db/workload.py _today)와
같은 정의를 날짜별로 묶은 것이라 두 카드의 오늘 숫자가 같다. 기한 충족은 **내가 담당이고 접수일이 이 기간 안인** 문의 기준이다
(목업은 미해결 기준이었으나 해결·종료 이력이 있어 기간 기준으로 한다). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg import Connection

DEFAULT_DAYS, MAX_DAYS = 7, 90
DAY = "(({col} AT TIME ZONE 'UTC')::date)"


def performance(conn: Connection, agent: str, as_of: datetime | None = None, days: int = DEFAULT_DAYS,
                schema: str = "svc") -> dict[str, Any]:
    assert schema in ("svc", "scoring")
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    days = max(1, min(days, MAX_DAYS))
    today = as_of.astimezone(timezone.utc).date()
    first = today - timedelta(days=days - 1)
    start = datetime(first.year, first.month, first.day, tzinfo=timezone.utc)  # 기간의 첫 날 0시(UTC)부터 기준 시각까지
    p = {"agent": agent, "start": start, "as_of": as_of}

    def by_day(sql: str) -> dict[date, int]:
        return {d: n for d, n in conn.execute(sql, p).fetchall()}

    sent = by_day(f"""SELECT {DAY.format(col='m.sent_at_utc')}, count(*) FROM {schema}.ticket_message m
                       WHERE m.message_status = 'SENT' AND m.sender IN ('AGENT','DEPT') AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY')
                         AND m.sent_by_name = %(agent)s AND m.sent_at_utc >= %(start)s AND m.sent_at_utc <= %(as_of)s GROUP BY 1""")
    esc = by_day(f"""SELECT {DAY.format(col='h.changed_at_utc')}, count(*) FROM {schema}.ticket_status_history h
                      WHERE h.event_kind = 'ESCALATE' AND h.changed_by = %(agent)s
                        AND h.changed_at_utc >= %(start)s AND h.changed_at_utc <= %(as_of)s GROUP BY 1""")
    adj = by_day(f"""SELECT {DAY.format(col='a.adjusted_at_utc')}, count(*) FROM {schema}.priority_adjustment a
                      WHERE a.adjusted_by = %(agent)s AND a.adjusted_at_utc >= %(start)s AND a.adjusted_at_utc <= %(as_of)s GROUP BY 1""")
    daily = []
    for i in range(days):
        d = first + timedelta(days=i)
        s, e, a = sent.get(d, 0), esc.get(d, 0), adj.get(d, 0)
        daily.append({"date": d.isoformat(), "n": s + e + a, "sent": s, "escalated": e, "adjusted": a})

    fr_met, fr_bad, res_ok, total = conn.execute(
        f"""WITH f AS MATERIALIZED (SELECT * FROM {schema}.inquiry_sla(%(as_of)s))
            SELECT count(*) FILTER (WHERE f.fr_status = 'MET'), count(*) FILTER (WHERE f.fr_status = 'BREACHED'),
                   count(*) FILTER (WHERE f.res_status <> 'BREACHED'), count(*)
              FROM {schema}.sub_ticket s JOIN f ON f.sub_ticket_id = s.sub_ticket_id
             WHERE s.assignee_masked = %(agent)s AND f.received_at_utc >= %(start)s AND f.received_at_utc <= %(as_of)s""", p).fetchone()
    auto = {"sent": 0, "pending": 0}
    if schema == "svc":  # 내가 담당인 문의 중 자동 발송된 것(기간 안)과 사후 검수 전(기간 무관)
        auto["sent"], auto["pending"] = conn.execute(
            """SELECT count(*) FILTER (WHERE m.sent_at_utc >= %(start)s AND m.sent_at_utc <= %(as_of)s),
                      count(*) FILTER (WHERE r.message_id IS NULL AND m.sent_at_utc <= %(as_of)s)
                 FROM svc.ticket_message m JOIN svc.sub_ticket s ON s.sub_ticket_id = m.sub_ticket_id
                 LEFT JOIN svc.auto_review r ON r.message_id = m.message_id
                WHERE m.sender = 'SYSTEM' AND m.sent_by_name = 'AI_AUTO' AND m.message_type = 'FINAL_REPLY'
                  AND m.message_status = 'SENT' AND s.assignee_masked = %(agent)s""", p).fetchone()
    return {
        "agent": agent, "as_of": as_of, "days": days, "auto": auto,
        "total": sum(x["n"] for x in daily),
        "daily": daily,
        "sla": {"window_total": total, "fr_met": fr_met, "fr_breached": fr_bad, "res_ok": res_ok},
    }
