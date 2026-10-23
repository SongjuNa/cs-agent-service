"""나의 업무 현황 (명세서 v1.5 FR-047, 기술 명세서 v1.4 §8-1 `GET /me/workload`, §8-3 값 출처, 화면 정의서 v1 SCR-04).

범위: 상담원(X-Agent-Id)이 있으면 "내 담당" = sub_ticket.assignee_masked = 상담원 ID(§8-3, D33). 부서만 있으면
그 부서(assigned_dept) 전체(§8-3, AC-047-1). 화면에서 "부서 전체"로 바꿀 수 있다(scope, C-118).
숫자는 FR-026·027이 낸 값(inquiry_sla, sla_alert)을 세기만 하고 새로 계산하지 않는다. 저장·상태 변경 없음.
schema는 svc(서비스) 또는 scoring(재생 채점). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import Connection

from app.db.inbox import ALERTS, OPEN
from app.status.closing import NO_REPLY
from app.status.reminder import REMIND_AFTER

MSG_NO_SCOPE = "상단에서 이름과 부서를 고르세요"  # FR-047 예외 3행
EMPTY = {  # FR-047 예외 1행 "영역별 문구"
    "drafts": "승인 대기 초안이 없습니다",
    "risks": "기한 위험·위반 문의가 없습니다",
    "waiting_customer": "고객 회신 대기 문의가 없습니다",
    "waiting_escalation": "이관 회신 대기 문의가 없습니다",
}
DRAFT_TYPES = ("INFO_REQUEST", "FINAL_REPLY", "PROGRESS_NOTICE")  # 접수함 "승인 대기"와 같은 정의(FR-029)


def _hours(delta: timedelta | None) -> float | None:
    return None if delta is None else round(delta.total_seconds() / 3600, 1)


def _rows(conn: Connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def workload(conn: Connection, dept: str | None, agent: str | None = None, scope: str | None = None,
             as_of: datetime | None = None, schema: str = "svc") -> dict[str, Any]:
    """영역 5개를 한 번에(§8-1). scope: mine(내 담당) / dept(부서 전체). 비우면 상담원이 있으면 mine."""
    assert schema in ("svc", "scoring")
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    agent = (agent or "").strip() or None
    scope = scope if scope in ("mine", "dept") else ("mine" if agent else "dept")
    if scope == "mine" and not agent:
        scope = "dept"
    out: dict[str, Any] = {"dept": dept, "agent": agent, "scope": scope, "as_of": as_of, "message": None,
                           "tiles": {"drafts": 0, "risks": 0, "waiting_customer": 0, "waiting_escalation": 0},
                           "drafts": [], "risks": [], "waiting_customer": [], "waiting_escalation": [],
                           "today": {"sent": 0, "escalated": 0, "adjusted": 0}, "sla_unset": 0, "empty": EMPTY}
    if not dept and scope == "dept":
        out["message"] = MSG_NO_SCOPE
        return out

    mine = "s.assignee_masked = %(agent)s" if scope == "mine" else "s.assigned_dept = %(dept)s"
    params: dict[str, Any] = {"dept": dept, "agent": agent, "as_of": as_of, "open": list(OPEN),
                              "alerts": list(ALERTS), "types": list(DRAFT_TYPES)}
    base = f"""{schema}.sub_ticket s JOIN {schema}.ticket t ON t.ticket_id = s.ticket_id
               JOIN ref.customer c ON c.customer_id = t.customer_id
              WHERE {mine} AND s.status = ANY(%(open)s)"""
    cols = """s.sub_ticket_id, s.ticket_id, s.seq,
              (SELECT count(*) FROM {schema}.sub_ticket k WHERE k.ticket_id = s.ticket_id) AS inquiry_count,
              c.company_masked, t.customer_tier, s.priority, s.status""".format(schema=schema)

    # ② 기한 위험·위반: 풀리지 않은 경고가 있는 미해결 문의, SLA 미정은 빼고 따로(FR-047 처리 2, 예외 2행)
    out["risks"] = _risks(conn, schema, cols, mine, params)
    (out["sla_unset"],) = conn.execute(f"SELECT count(*) FROM {base} AND s.sla_id IS NULL", params).fetchone()

    # ③ 승인 대기 초안: 보내지 않은 DRAFT·APPROVED(superseded 아님). 우선순위 → 만든 시각(FR-047 처리 3, §8-3)
    out["drafts"] = _rows(conn, f"""
        SELECT {cols}, m.message_id, m.message_type, m.sent_at_utc AS created_at_utc,
               {"false AND " if schema != "svc" else ""}EXISTS (SELECT 1 FROM eval.self_check sc  -- 검사 기록은 서비스 실행만
                        WHERE sc.sub_ticket_id = s.sub_ticket_id AND NOT sc.passed_yn AND sc.check_type <> 'VERIFY'
                          AND (sc.message_id = m.message_id
                               OR sc.run_id IN (SELECT st.run_id FROM {schema}.agent_step st WHERE st.step_name = 'Q13'
                                                   AND (st.output_json ->> 'message_id')::bigint = m.message_id))
                      ) AS has_check
          FROM {base.replace('WHERE', 'JOIN ' + schema + '.ticket_message m ON m.sub_ticket_id = s.sub_ticket_id WHERE', 1)}
           AND m.message_status IN ('DRAFT','APPROVED') AND m.message_type = ANY(%(types)s) AND m.superseded_at IS NULL
           AND NOT EXISTS (SELECT 1 FROM {schema}.ticket_message x
                            WHERE x.source_draft_id = m.message_id AND x.message_status = 'SENT')
         ORDER BY s.priority NULLS LAST, m.sent_at_utc, m.message_id""", params)

    # ④-1 고객 회신 대기: 마지막 정보 요청 발송 뒤 경과, 126h·168h, 리마인드(FR-047 처리 4 ①). 발송 행이 없으면
    # (재생 데이터) 상태 이력의 INFO_REQUEST_SENT 시각을 쓴다(같은 순간, C-119). 기준 시각 뒤의 기록은 보지 않는다
    waiting = _rows(conn, f"""
        SELECT {cols},
               coalesce((SELECT max(m.sent_at_utc) FROM {schema}.ticket_message m
                          WHERE m.sub_ticket_id = s.sub_ticket_id AND m.message_type = 'INFO_REQUEST'
                            AND m.message_status = 'SENT' AND m.sent_at_utc <= %(as_of)s),
                        (SELECT max(h.changed_at_utc) FROM {schema}.ticket_status_history h
                          WHERE h.sub_ticket_id = s.sub_ticket_id AND h.event_kind = 'INFO_REQUEST_SENT'
                            AND h.changed_at_utc <= %(as_of)s)) AS requested_at_utc,
               EXISTS (SELECT 1 FROM {schema}.ticket_message r WHERE r.sub_ticket_id = s.sub_ticket_id
                          AND r.notice_transition = 'REMINDER' AND r.message_status = 'SENT'
                          AND r.sent_at_utc <= %(as_of)s) AS reminder_sent
          FROM {base} AND s.status = 'WAITING_CUSTOMER'""", params)
    for w in waiting:
        w["elapsed_h"] = _hours(as_of - w["requested_at_utc"]) if w["requested_at_utc"] else None
        w["remind_at_h"], w["close_at_h"] = _hours(REMIND_AFTER), _hours(NO_REPLY)
    out["waiting_customer"] = sorted(waiting, key=lambda w: (-(w["elapsed_h"] or 0), w["sub_ticket_id"]))

    # ④-2 이관 회신 대기: ESCALATED이고 이관 부서가 있는 것. 이관 시각 = 마지막 ESCALATE 이력(FR-047 처리 4 ②)
    escalated = _rows(conn, f"""
        SELECT {cols}, s.escalated_to,
               (SELECT max(h.changed_at_utc) FROM {schema}.ticket_status_history h
                 WHERE h.sub_ticket_id = s.sub_ticket_id AND h.event_kind = 'ESCALATE'
                   AND h.changed_at_utc <= %(as_of)s) AS escalated_at_utc
          FROM {base} AND s.status = 'ESCALATED' AND s.escalated_to IS NOT NULL""", params)
    for e in escalated:
        e["elapsed_h"] = _hours(as_of - e["escalated_at_utc"]) if e["escalated_at_utc"] else None
    out["waiting_escalation"] = sorted(escalated, key=lambda e: (-(e["elapsed_h"] or 0), e["sub_ticket_id"]))

    out["tiles"] = {k: len(out[k]) for k in ("drafts", "risks", "waiting_customer", "waiting_escalation")}
    out["today"] = _today(conn, schema, scope, params)
    return out


def _risks(conn: Connection, schema: str, cols: str, mine: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _rows(conn, f"""
        WITH f AS MATERIALIZED (SELECT * FROM {schema}.inquiry_sla(%(as_of)s))
        SELECT {cols}, a.alerts, f.remaining_h
          FROM {schema}.sub_ticket s
          JOIN {schema}.ticket t ON t.ticket_id = s.ticket_id
          JOIN ref.customer c ON c.customer_id = t.customer_id
          JOIN LATERAL (SELECT array_agg(al.alert_type ORDER BY al.alert_type) AS alerts FROM {schema}.sla_alert al
                         WHERE al.sub_ticket_id = s.sub_ticket_id AND al.alert_type = ANY(%(alerts)s)
                           AND al.raised_at_utc <= %(as_of)s  -- 기준 시각에 살아 있던 경고
                           AND (al.cleared_at_utc IS NULL OR al.cleared_at_utc > %(as_of)s)) a ON a.alerts IS NOT NULL
          LEFT JOIN f ON f.sub_ticket_id = s.sub_ticket_id
         WHERE {mine} AND s.status = ANY(%(open)s) AND s.sla_id IS NOT NULL
         ORDER BY f.remaining_h ASC NULLS LAST, s.sub_ticket_id""", params)
    for r in rows:
        r["alerts"] = list(r["alerts"])
    return rows


def _today(conn: Connection, schema: str, scope: str, params: dict[str, Any]) -> dict[str, int]:
    """기준 시각의 날짜(UTC)에 한 발송·이관·조정 수(FR-047 처리 5). 내 담당이면 내가 한 것, 부서 전체면 그 부서 문의에
    한 것(C-120)."""
    day = params["as_of"].astimezone(timezone.utc).date()
    p = {**params, "day": day}
    who = {"mine": ("m.sent_by_name = %(agent)s", "h.changed_by = %(agent)s", "a.adjusted_by = %(agent)s"),
           "dept": ("s.assigned_dept = %(dept)s",) * 3}[scope]
    on_day = "(({col} AT TIME ZONE 'UTC')::date = %(day)s AND {col} <= %(as_of)s)"  # 기준 시각까지
    (sent,) = conn.execute(
        f"""SELECT count(*) FROM {schema}.ticket_message m JOIN {schema}.sub_ticket s ON s.sub_ticket_id = m.sub_ticket_id
             WHERE m.message_status = 'SENT' AND m.sender IN ('AGENT','DEPT') AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY')
               AND {who[0]} AND {on_day.format(col='m.sent_at_utc')}""", p).fetchone()
    (escalated,) = conn.execute(
        f"""SELECT count(*) FROM {schema}.ticket_status_history h JOIN {schema}.sub_ticket s ON s.sub_ticket_id = h.sub_ticket_id
             WHERE h.event_kind = 'ESCALATE' AND {who[1]} AND {on_day.format(col='h.changed_at_utc')}""", p).fetchone()
    (adjusted,) = conn.execute(
        f"""SELECT count(*) FROM {schema}.priority_adjustment a JOIN {schema}.sub_ticket s ON s.sub_ticket_id = a.sub_ticket_id
             WHERE {who[2]} AND {on_day.format(col='a.adjusted_at_utc')}""", p).fetchone()
    return {"sent": sent, "escalated": escalated, "adjusted": adjusted}
