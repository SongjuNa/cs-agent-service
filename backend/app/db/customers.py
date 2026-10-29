"""고객 관리 읽기 (변경 add-customer-views, FR 초안 01). 고객 목록·상세·나라별 집계.

ref.customer와 svc의 티켓을 읽기만 한다. 고치는 함수는 없다(proposal "읽기만").
미해결 = 하위 문의 상태가 NEW·IN_PROGRESS·WAITING_CUSTOMER·ESCALATED(FR-034 처리 2와 같은 정의, design 결정 1).
경고 = 기준 시각에 살아 있는 sla_alert(나의 업무 현황과 같은 조건).
이 모듈은 규칙 코드·언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1·2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

from app.db.inbox import ALERTS, OPEN

PAGE_SIZE = 50  # 쪽 크기 기본(design 결정 1)
MAX_SIZE = 200
MSG_NOT_FOUND = "고객을 찾을 수 없음"  # design 결정 2


def _rows(conn: Connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _as_of(as_of: datetime | None) -> datetime:
    as_of = as_of or datetime.now(timezone.utc)
    return as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)


# 고객별 문의 수·미해결 수·최근 문의 시각. 미해결은 티켓 단위(하위 문의 하나라도 미해결이면 미해결 티켓)
_COUNTS = """
    SELECT t.customer_id, count(*) AS ticket_count,
           count(*) FILTER (WHERE EXISTS (SELECT 1 FROM svc.sub_ticket s WHERE s.ticket_id = t.ticket_id
                                              AND s.status = ANY(%(open)s))) AS open_count,
           max(t.received_at_utc) AS last_received_at
      FROM svc.ticket t GROUP BY t.customer_id"""


def customer_list(conn: Connection, q: str | None = None, tier: str | None = None, country: str | None = None,
                  page: int = 1, size: int = PAGE_SIZE) -> dict[str, Any]:
    """목록 한 쪽(최근 문의 시각 내림차순, 문의 없는 고객은 뒤). tier_counts는 등급 거르기 전의 등급별 수(화면 등급 요약)."""
    size = max(1, min(size, MAX_SIZE))
    page = max(1, page)
    q = (q or "").strip()
    params: dict[str, Any] = {"open": list(OPEN), "like": f"%{q}%", "q": q, "tier": tier or None,
                              "country": country or None, "limit": size, "offset": (page - 1) * size}
    where = """(%(q)s = '' OR c.customer_id ILIKE %(like)s OR c.company_masked ILIKE %(like)s)
               AND (%(country)s::text IS NULL OR c.country = %(country)s)"""
    tiers = dict(conn.execute(f"SELECT c.tier, count(*) FROM ref.customer c WHERE {where} GROUP BY 1", params).fetchall())
    where_tier = f"{where} AND (%(tier)s::text IS NULL OR c.tier = %(tier)s)"
    (total,) = conn.execute(f"SELECT count(*) FROM ref.customer c WHERE {where_tier}", params).fetchone()
    rows = _rows(conn, f"""
        SELECT c.customer_id, c.company_masked, c.country, c.tier, c.segment,
               coalesce(n.ticket_count, 0) AS ticket_count, coalesce(n.open_count, 0) AS open_count, n.last_received_at
          FROM ref.customer c LEFT JOIN ({_COUNTS}) n ON n.customer_id = c.customer_id
         WHERE {where_tier}
         ORDER BY n.last_received_at DESC NULLS LAST, c.customer_id
         LIMIT %(limit)s OFFSET %(offset)s""", params)
    return {"total": total, "page": page, "size": size, "tier_counts": tiers, "rows": rows}


def customer_detail(conn: Connection, customer_id: str, as_of: datetime | None = None) -> dict[str, Any] | None:
    """고객 정보 + 최근 연락처·언어 + 문의 이력(하위 문의 1줄씩, 접수 시각 내림차순). 없는 고객이면 None."""
    params: dict[str, Any] = {"id": customer_id, "as_of": _as_of(as_of), "open": list(OPEN), "alerts": list(ALERTS)}
    found = _rows(conn, """SELECT customer_id, company_masked, country, tier, segment, account_since
                             FROM ref.customer WHERE customer_id = %(id)s""", params)
    if not found:
        return None
    out = found[0]
    latest = _rows(conn, """SELECT contact_email, language FROM svc.ticket WHERE customer_id = %(id)s
                             ORDER BY received_at_utc DESC, ticket_id DESC LIMIT 1""", params)
    out["last_contact_email"] = latest[0]["contact_email"] if latest else None  # FR-030 처리 1(원문 표시)
    out["last_language"] = latest[0]["language"] if latest else None
    history = _rows(conn, """
        SELECT s.sub_ticket_id, s.ticket_id, s.seq,
               (SELECT count(*) FROM svc.sub_ticket k WHERE k.ticket_id = s.ticket_id) AS inquiry_count,
               t.source_ticket_id, t.received_at_utc, s.category_code, s.product_code, s.priority, s.status,
               coalesce((SELECT array_agg(a.alert_type ORDER BY a.alert_type) FROM svc.sla_alert a
                          WHERE a.sub_ticket_id = s.sub_ticket_id AND a.alert_type = ANY(%(alerts)s)
                            AND a.raised_at_utc <= %(as_of)s
                            AND (a.cleared_at_utc IS NULL OR a.cleared_at_utc > %(as_of)s)
                            AND s.status = ANY(%(open)s)), '{}') AS alerts
          FROM svc.sub_ticket s JOIN svc.ticket t ON t.ticket_id = s.ticket_id
         WHERE t.customer_id = %(id)s
         ORDER BY t.received_at_utc DESC, s.ticket_id DESC, s.seq""", params)
    for h in history:
        h["alerts"] = list(h["alerts"])
    out["history"] = history
    out["ticket_count"] = len({h["ticket_id"] for h in history})
    out["open_count"] = len({h["ticket_id"] for h in history if h["status"] in OPEN})
    out["alert_count"] = sum(1 for h in history if h["alerts"])
    out["as_of"] = params["as_of"]
    return out


def countries(conn: Connection) -> list[dict[str, Any]]:
    """나라별 고객 수, 문의 수, 미해결 문의 수(design 결정 3). 고객 수 내림차순."""
    return _rows(conn, f"""
        SELECT c.country, count(*) AS customer_count, coalesce(sum(n.ticket_count), 0)::int AS ticket_count,
               coalesce(sum(n.open_count), 0)::int AS open_count
          FROM ref.customer c LEFT JOIN ({_COUNTS}) n ON n.customer_id = c.customer_id
         GROUP BY c.country ORDER BY customer_count DESC, c.country""", {"open": list(OPEN)})
