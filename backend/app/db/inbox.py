"""접수함 목록 (명세서 v1.5 FR-029, 기술 명세서 v1.4 §8-1 `GET /tickets`, 화면 정의서 v1 SCR-02).

줄 = 뷰 v_inquiry_inbox와 같은 열·같은 계산(하위 문의 한 줄)이고, SLA는 기준 시각(as_of)으로 계산한다
(화면 정의서 v1 SCR-00-04 "모든 조회의 as_of"). 뷰를 그대로 읽지 않는 까닭: 뷰는 now() 기준이고, 뷰 안의
inquiry_sla가 줄마다 다시 계산돼 4,000건에서 1분을 넘는다. 여기서는 inquiry_sla를 한 번만 계산한다(C-102).
뷰와 같은 결과인지는 시험(test_same_rows_as_view)이 본다.
schema는 svc(서비스) 또는 scoring(재생 채점). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

OPEN = ("NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED")  # FR-029 처리 1
ALERTS = ("FR_AT_RISK", "FR_BREACHED", "RES_AT_RISK", "RES_BREACHED")
BREACHED = ("FR_BREACHED", "RES_BREACHED")  # 기한 초과(counts.breach)
AT_RISK = ("FR_AT_RISK", "RES_AT_RISK")  # 기한 임박(counts.risk). 초과가 함께 있으면 초과로만 센다
PAGE_SIZE, MAX_SIZE = 50, 200  # FR-029 처리 7(50건), 최대는 구현 선택
MSG_NO_DEPT = "부서를 선택하세요"  # FR-029 예외 1행
MSG_EMPTY = "처리할 티켓이 없습니다"  # FR-029 예외 2행
# 기본 정렬: 경고 있음 → 해결 남은 시간(없으면 맨 아래) → 접수 시각 → 하위 문의 번호(FR-029 처리 3, FR-027 처리 5, C-99)
# 내 차례 묶음이 먼저(add-inbox-turn-depth 결정 3), 각 묶음 안은 기존 정렬
DEFAULT_ORDER = "turn_rank, (cardinality(alerts) > 0) DESC, remaining_h ASC NULLS LAST, received_at_utc, sub_ticket_id"
SORTS = {"received_at": "received_at_utc", "priority": "priority", "remaining": "remaining_h",
         "status": "status", "ticket_id": "ticket_id"}


@dataclass
class InboxQuery:
    dept: str | None
    status: list[str] = field(default_factory=list)
    priority: list[str] = field(default_factory=list)
    alert: list[str] = field(default_factory=list)
    channel: list[str] = field(default_factory=list)
    needs_info: bool = False
    has_draft: bool = False
    composite: bool = False
    q: str | None = None
    include_closed: bool = False
    page: int = 1
    size: int = PAGE_SIZE
    sort: str | None = None
    assignee: str | None = None  # 담당 상담원 이름이 같은 줄만
    turn: list[str] = field(default_factory=list)  # ME·DEPT·CUSTOMER·DONE
    depth: list[str] = field(default_factory=list)  # DEEP·NORMAL·QUICK
    me: str | None = None  # counts.mine을 셀 상담원 이름
    as_of: datetime | None = None


# app/rules/turn.py의 turn_of·depth_of와 같은 규칙을 SQL로 옮긴 것. 필터·정렬·쪽 나누기가 SQL에서 일어나서다.
# 두 쪽이 같은지는 시험(test_inbox_turn_sql_matches_rules)이 본다.
TURN_SQL = """CASE WHEN status IN ('RESOLVED','CLOSED') THEN 'DONE' WHEN status = 'ESCALATED' THEN 'DEPT'
                    WHEN status = 'WAITING_CUSTOMER' THEN 'CUSTOMER' ELSE 'ME' END"""
ACTION_SQL = """CASE WHEN status IN ('RESOLVED','CLOSED') THEN 'DONE' WHEN status = 'ESCALATED' THEN 'WAIT_DEPT'
                       WHEN status = 'WAITING_CUSTOMER' THEN 'WAIT_CUSTOMER' WHEN needs_info THEN 'SEND_INFO_REQUEST'
                       WHEN dept_replied THEN 'CHECK_DEPT_REPLY' WHEN has_unsent_draft THEN 'APPROVE_DRAFT'
                       ELSE 'WRITE_ANSWER' END"""
DEPTH_SQL = """CASE WHEN urgency_flag IN ('SAFETY','SITE_DOWN') OR priority = 'P1' THEN 'DEEP'
                      WHEN NOT needs_info AND priority IN ('P3','P4') THEN 'QUICK' ELSE 'NORMAL' END"""
RANK_SQL = """CASE WHEN status IN ('RESOLVED','CLOSED') THEN 2 WHEN status IN ('ESCALATED','WAITING_CUSTOMER') THEN 1 ELSE 0 END"""


def _order(sort: str | None) -> str:
    """열 머리 정렬(FR-029 처리 3). "-"가 앞이면 내림차순. 모르는 값이면 기본."""
    if not sort:
        return DEFAULT_ORDER
    desc = sort.startswith("-")
    col = SORTS.get(sort.lstrip("-"))
    if col is None:
        return DEFAULT_ORDER
    return f"{col} {'DESC' if desc else 'ASC'} NULLS LAST, sub_ticket_id"


def inbox(conn: Connection, query: InboxQuery, schema: str = "svc") -> dict[str, Any]:
    """접수함 한 쪽과 건수 요약. 부서가 없으면 빈 목록과 안내(FR-029 예외 1행)."""
    assert schema in ("svc", "scoring")
    as_of = query.as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    size = max(1, min(query.size, MAX_SIZE))
    page = max(1, query.page)
    out: dict[str, Any] = {"dept": query.dept, "as_of": as_of, "page": page, "size": size,
                           "counts": {"total": 0, "alert": 0, "needs_info": 0, "has_draft": 0, "waiting": 0,
                                      "new": 0, "escalated": 0, "breach": 0, "risk": 0, "mine": 0, "turn_me": 0, "deep": 0},
                           "rows": [], "message": None}
    if not query.dept:
        out["message"] = MSG_NO_DEPT
        return out

    where = ["(assigned_dept = %(dept)s OR escalated_to = %(dept)s)"]
    params: dict[str, Any] = {"dept": query.dept, "as_of": as_of}
    if not query.include_closed:
        where.append("status = ANY(%(open)s)")
        params["open"] = list(OPEN)
    for name in ("status", "priority", "channel"):
        values = getattr(query, name)
        if values:
            where.append(f"{name} = ANY(%({name})s)")
            params[name] = values
    if query.alert:
        where.append("alerts && %(alert)s::text[]")
        params["alert"] = query.alert
    if query.assignee:
        where.append("assignee_masked = %(assignee)s")
        params["assignee"] = query.assignee
    for name, col in (("turn", "turn"), ("depth", "review_depth")):
        values = getattr(query, name)
        if values:
            where.append(f"{col} = ANY(%({name})s)")
            params[name] = values
    if query.needs_info:
        where.append("needs_info")
    if query.has_draft:
        where.append("has_unsent_draft")
    if query.composite:
        where.append("inquiry_count > 1")
    if query.q and query.q.strip():
        where.append("(ticket_id ILIKE %(q)s OR company_masked ILIKE %(q)s)")
        params["q"] = f"%{query.q.strip()}%"

    base = f"""
        WITH f AS MATERIALIZED (SELECT * FROM {schema}.inquiry_sla(%(as_of)s)),
        rows AS (
          SELECT s.sub_ticket_id, s.ticket_id, s.seq, count(*) OVER (PARTITION BY s.ticket_id) AS inquiry_count,
                 t.received_at_utc, t.channel, t.language, t.customer_id, c.company_masked, t.customer_tier,
                 c.country, t.inquiry_subject,
                 s.product_code, p.product_name, s.category_code, s.urgency_flag, s.priority,
                 s.priority_adjusted_by_agent AS priority_adjusted, s.assigned_dept, s.escalated_to, s.assignee_masked,
                 s.status, f.fr_status, f.res_status, f.remaining_h,
                 coalesce(a.alerts, '{{}}') AS alerts,
                 cardinality(s.missing_blocking_info) > 0 AS needs_info,
                 coalesce(d.has_unsent_draft, false) AS has_unsent_draft,
                 coalesce(r.reminder_sent, false) AS reminder_sent,
                 coalesce(dr.dept_replied, false) AS dept_replied
            FROM {schema}.sub_ticket s
            JOIN {schema}.ticket t ON t.ticket_id = s.ticket_id
            JOIN ref.customer c ON c.customer_id = t.customer_id
            JOIN f ON f.sub_ticket_id = s.sub_ticket_id
            LEFT JOIN ref.product p ON p.product_code = s.product_code
            LEFT JOIN LATERAL (
              SELECT array_agg(al.alert_type ORDER BY al.alert_type) AS alerts
                FROM {schema}.sla_alert al
               WHERE al.sub_ticket_id = s.sub_ticket_id AND al.cleared_at_utc IS NULL
            ) a ON true
            LEFT JOIN LATERAL (
              SELECT true AS has_unsent_draft
                FROM {schema}.ticket_message m
               WHERE m.sub_ticket_id = s.sub_ticket_id
                 AND m.message_status IN ('DRAFT','APPROVED')
                 AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY','PROGRESS_NOTICE')
                 AND m.superseded_at IS NULL
                 AND NOT EXISTS (SELECT 1 FROM {schema}.ticket_message x
                                  WHERE x.source_draft_id = m.message_id AND x.message_status = 'SENT')
               LIMIT 1
            ) d ON true
            LEFT JOIN LATERAL (
              SELECT true AS reminder_sent
                FROM {schema}.ticket_message m
               WHERE m.sub_ticket_id = s.sub_ticket_id AND m.notice_transition = 'REMINDER' AND m.message_status = 'SENT'
               LIMIT 1
            ) r ON true
            LEFT JOIN LATERAL (
              SELECT true AS dept_replied
                FROM {schema}.ticket_message m
               WHERE m.sub_ticket_id = s.sub_ticket_id AND m.message_type = 'ESCALATION_NOTE' AND m.message_status = 'RECEIVED'
               LIMIT 1
            ) dr ON true
        ),
        ranked AS (
          SELECT rows.*, {TURN_SQL} AS turn, {ACTION_SQL} AS next_action, {DEPTH_SQL} AS review_depth,
                 {RANK_SQL} AS turn_rank
            FROM rows
        )
        SELECT * FROM ranked WHERE {' AND '.join(where)}"""
    counts = conn.execute(
        f"""SELECT count(*), count(*) FILTER (WHERE cardinality(alerts) > 0), count(*) FILTER (WHERE needs_info),
                   count(*) FILTER (WHERE has_unsent_draft), count(*) FILTER (WHERE status = 'WAITING_CUSTOMER'),
                   count(*) FILTER (WHERE status = 'NEW'), count(*) FILTER (WHERE status = 'ESCALATED'),
                   count(*) FILTER (WHERE alerts && %(breached)s::text[]),
                   count(*) FILTER (WHERE alerts && %(at_risk)s::text[] AND NOT alerts && %(breached)s::text[]),
                   count(*) FILTER (WHERE assignee_masked = %(me)s), count(*) FILTER (WHERE turn = 'ME'),
                   count(*) FILTER (WHERE review_depth = 'DEEP')
              FROM ({base}) x""", {**params, "breached": list(BREACHED), "at_risk": list(AT_RISK), "me": query.me}).fetchone()
    out["counts"] = dict(zip(("total", "alert", "needs_info", "has_draft", "waiting", "new", "escalated", "breach", "risk",
                                  "mine", "turn_me", "deep"), counts))
    params.update(limit=size, offset=(page - 1) * size)
    cur = conn.execute(f"{base} ORDER BY {_order(query.sort)} LIMIT %(limit)s OFFSET %(offset)s", params)
    names = [c.name for c in cur.description]
    for r in cur.fetchall():
        row = dict(zip(names, r))
        # 이관받은 줄: 이 부서가 escalated_to이고 담당이 아님 → "{원 부서}에서 이관됨"(FR-029 처리 1)
        row["escalated_in_from"] = row["assigned_dept"] if (row["escalated_to"] == query.dept
                                                            and row["assigned_dept"] != query.dept) else None
        row["alerts"] = list(row["alerts"] or [])
        out["rows"].append(row)
    if not out["rows"] and page == 1:
        out["message"] = MSG_EMPTY
    return out
