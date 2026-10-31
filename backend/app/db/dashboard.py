"""운영 대시보드 집계 (변경 add-ops-overview, 최신 목업 "운영 현황"). 관리자가 팀 전체를 한눈에 본다.

문의(하위 문의)마다 필요한 값만 SQL 한 번으로 읽고 파이썬에서 센다(약 4천 행). 기한 상태는 접수함과 같은 inquiry_sla(as_of)로,
경고는 접수함과 같은 정의(초과 = *_BREACHED가 하나라도, 임박 = *_AT_RISK만)로 센다. 숫자는 서버가 센 값을 화면이 그대로 보인다.
schema는 svc(서비스) 또는 scoring(재생 채점). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg import Connection

from app.db.inbox import AT_RISK, BREACHED, OPEN

DEFAULT_DAYS, MAX_DAYS = 30, 365
ESC_LATE_H = 168  # 이관 지연: 전문 부서로 넘긴 뒤 이 시간이 지난 건(목업 ESC_LONG_H)
STAGES = ("NEW", "REVIEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED")

SQL = """
WITH f AS MATERIALIZED (SELECT * FROM {schema}.inquiry_sla(%(as_of)s))
SELECT s.sub_ticket_id, s.assigned_dept, s.assignee_masked, s.status, s.urgency_flag, t.received_at_utc, c.country,
       f.fr_status, f.res_status,
       coalesce(a.alerts, '{{}}') AS alerts,
       CASE WHEN s.status = ANY(%(open)s) THEN EXISTS (
              SELECT 1 FROM {schema}.ticket_message m
               WHERE m.sub_ticket_id = s.sub_ticket_id AND m.message_status IN ('DRAFT','APPROVED')
                 AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE') AND m.superseded_at IS NULL
                 AND NOT EXISTS (SELECT 1 FROM {schema}.ticket_message x WHERE x.source_draft_id = m.message_id AND x.message_status = 'SENT'))
            ELSE false END AS has_draft,
       CASE WHEN s.status = 'ESCALATED' THEN (
              SELECT max(h.changed_at_utc) FROM {schema}.ticket_status_history h
               WHERE h.sub_ticket_id = s.sub_ticket_id AND h.event_kind = 'ESCALATE') END AS escalated_at
  FROM {schema}.sub_ticket s
  JOIN {schema}.ticket t ON t.ticket_id = s.ticket_id
  JOIN ref.customer c ON c.customer_id = t.customer_id
  JOIN f ON f.sub_ticket_id = s.sub_ticket_id
  LEFT JOIN LATERAL (
    SELECT array_agg(al.alert_type) AS alerts FROM {schema}.sla_alert al
     WHERE al.sub_ticket_id = s.sub_ticket_id AND al.cleared_at_utc IS NULL) a ON true
"""


def _kind(alerts: list[str]) -> str | None:
    """breach(초과) / risk(임박, 초과가 없을 때) / None."""
    if set(alerts) & set(BREACHED):
        return "breach"
    return "risk" if set(alerts) & set(AT_RISK) else None


def dashboard(conn: Connection, as_of: datetime | None = None, days: int = DEFAULT_DAYS, schema: str = "svc") -> dict[str, Any]:
    assert schema in ("svc", "scoring")
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    days = max(1, min(days, MAX_DAYS))
    since = as_of - timedelta(days=days)
    today = as_of.date()
    cur = conn.execute(SQL.format(schema=schema), {"as_of": as_of, "open": list(OPEN)})
    names = [c.name for c in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]

    openr = [r for r in rows if r["status"] in OPEN]
    window = [r for r in rows if since < r["received_at_utc"] <= as_of]
    kinds = {r["sub_ticket_id"]: _kind(list(r["alerts"] or [])) for r in openr}
    breach = sum(1 for k in kinds.values() if k == "breach")
    risk = sum(1 for k in kinds.values() if k == "risk")

    # 일별 접수(UTC 날짜): 기간의 모든 날을 0으로 채워 돌려준다
    per_day: dict[date, int] = defaultdict(int)
    for r in window:
        per_day[r["received_at_utc"].date()] += 1
    daily = [{"date": (today - timedelta(days=i)).isoformat(), "n": per_day.get(today - timedelta(days=i), 0)}
             for i in range(days - 1, -1, -1)]

    def bucket(key: str, extra=None) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in openr:
            k = r[key]
            if not k:
                continue
            b = out.setdefault(k, {"key": k, "open": 0, "breach": 0, "risk": 0, "esc_late": 0, "safety": 0})
            b["open"] += 1
            kd = kinds[r["sub_ticket_id"]]
            b["breach"] += kd == "breach"
            b["risk"] += kd == "risk"
            b["safety"] += r["urgency_flag"] == "SAFETY"
            if r["status"] == "ESCALATED" and r["escalated_at"] and (as_of - r["escalated_at"]).total_seconds() / 3600 >= ESC_LATE_H:
                b["esc_late"] += 1
        return sorted(out.values(), key=lambda b: (-b["open"], b["key"]))

    stages = {k: {"open": 0, "breach": 0} for k in STAGES}
    for r in openr:
        s = r["status"]
        parked = s in ("WAITING_CUSTOMER", "ESCALATED")
        stage = s if parked else ("REVIEW" if r["has_draft"] else ("NEW" if s == "NEW" else "IN_PROGRESS"))
        stages[stage]["open"] += 1
        stages[stage]["breach"] += kinds[r["sub_ticket_id"]] == "breach"

    by_agent = bucket("assignee_masked")
    agent_dept = {r["assignee_masked"]: r["assigned_dept"] for r in openr if r["assignee_masked"]}
    for b in by_agent:
        b["dept"] = agent_dept.get(b["key"])
    by_country = sorted(bucket("country"), key=lambda b: (-b["safety"], -b["breach"], -b["esc_late"], -b["risk"], -b["open"], b["key"]))

    return {
        "as_of": as_of, "days": days,
        "open": {"total": len(openr), "breach": breach, "risk": risk, "new_today": sum(1 for r in rows if r["received_at_utc"].date() == today)},
        # 접수일이 이 기간 안인 문의의 기한 충족: 1차 응답 MET·BREACHED(아직 정해지지 않은 건은 뺀다), 해결 기한 위반이 아닌 건
        "sla": {"window_total": len(window),
                "fr_met": sum(1 for r in window if r["fr_status"] == "MET"),
                "fr_breached": sum(1 for r in window if r["fr_status"] == "BREACHED"),
                "res_ok": sum(1 for r in window if r["res_status"] != "BREACHED")},
        "daily": daily,
        "by_dept": [{"dept": b["key"], "open": b["open"], "breach": b["breach"], "esc_late": b["esc_late"]} for b in bucket("assigned_dept")],
        "by_agent": [{"agent": b["key"], "dept": b["dept"], "open": b["open"], "breach": b["breach"], "risk": b["risk"]} for b in by_agent],
        "by_country": [{"country": b["key"], "open": b["open"], "breach": b["breach"], "risk": b["risk"], "safety": b["safety"], "esc_late": b["esc_late"]} for b in by_country],
        "stages": [{"stage": k, **stages[k]} for k in STAGES],
        "edited": _edited(conn, since, as_of, schema),
        "auto": _auto(conn, since, as_of, schema),
    }


def _auto(conn: Connection, since: datetime, as_of: datetime, schema: str) -> dict[str, int]:
    """AI와 사람의 처리 비중(변경 add-auto-send-views): 기간 안에 보낸 최종 답변 중 자동 발송(sent)과 그 사후 검수 완료(reviewed), 사람이 보낸 것(human).
    사후 검수 표는 svc에만 있어 채점용 재생에는 자동 발송이 없다(0)."""
    if schema != "svc":
        return {"sent": 0, "reviewed": 0, "human": 0, "total": 0}
    sent, reviewed, human = conn.execute(
        """SELECT count(*) FILTER (WHERE m.sender = 'SYSTEM'),
                  count(*) FILTER (WHERE m.sender = 'SYSTEM' AND r.message_id IS NOT NULL),
                  count(*) FILTER (WHERE m.sender IN ('AGENT','DEPT'))
             FROM svc.ticket_message m LEFT JOIN svc.auto_review r ON r.message_id = m.message_id
            WHERE m.message_status = 'SENT' AND m.message_type = 'FINAL_REPLY'
              AND ((m.sender = 'SYSTEM' AND m.sent_by_name = 'AI_AUTO') OR m.sender IN ('AGENT','DEPT'))
              AND m.sent_at_utc > %s AND m.sent_at_utc <= %s""", (since, as_of)).fetchone()
    return {"sent": sent, "reviewed": reviewed, "human": human, "total": sent + human}


def _edited(conn: Connection, since: datetime, as_of: datetime, schema: str) -> dict[str, int]:
    """상담원이 보낸 답변 중 AI 초안을 고쳐 보낸 비율의 재료. edited_yn이 기록된 것만 센다(재생 이력에는 없다)."""
    sent, edited = conn.execute(
        f"""SELECT count(*), count(*) FILTER (WHERE edited_yn) FROM {schema}.ticket_message
             WHERE message_status = 'SENT' AND sender = 'AGENT' AND message_type IN ('INFO_REQUEST','FINAL_REPLY')
               AND edited_yn IS NOT NULL AND sent_at_utc > %s AND sent_at_utc <= %s""", (since, as_of)).fetchone()
    return {"sent": sent, "edited": edited}
