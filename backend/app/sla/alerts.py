"""SLA 위험 경고 (명세서 v1.5 FR-027, 기술 명세서 v1.4 §6-4 주기 점검 1).

기준 시각(as_of)에 끝나지 않은 문의의 두 시계를 읽어, 조건을 처음 넘은 경고만 넣는다(문의당 종류마다 한 번).
발생 시각은 점검 시각이 아니라 조건을 넘은 실제 시각이다. 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from psycopg import Connection

SCHEMAS = ("svc", "scoring")  # scoring은 재생 채점용
OPEN = ("NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED")      # FR-027 입력
RES_OPEN = ("NEW", "IN_PROGRESS", "ESCALATED")                      # WAITING_CUSTOMER는 해결 경고 없음(처리 4)
DEFAULT_THRESHOLD = Decimal("0.75")


def at_risk_threshold(conn: Connection) -> Decimal:
    """ref.sla_setting at_risk_threshold("75%" 같은 글)를 비율로 (§6-4)."""
    row = conn.execute("""SELECT substring(value FROM '([0-9]+(\\.[0-9]+)?)\\s*%')::numeric / 100
                            FROM ref.sla_setting WHERE key = 'at_risk_threshold'""").fetchone()
    return row[0] if row and row[0] is not None else DEFAULT_THRESHOLD


def _hours(h: Decimal | float) -> timedelta:
    return timedelta(hours=float(h))


def due_alerts(conn: Connection, as_of: datetime, schema: str = "svc", sub_ticket_ids: list[str] | None = None) -> list[dict]:
    """as_of에 조건을 넘은 경고 후보 (이미 있는지는 보지 않는다).

    1차 응답 여부는 inquiry_sla가 주지 않으므로 sub_ticket.first_response_at_utc ≤ as_of로 본다.
    """
    if schema not in SCHEMAS:
        raise ValueError(schema)
    thr = at_risk_threshold(conn)
    rows = conn.execute(
        f"""SELECT f.sub_ticket_id, f.status, f.received_at_utc, f.fr_target_h, f.res_target_h,
                   f.fr_elapsed_h, f.wait_h, f.res_elapsed_h,
                   s.first_response_at_utc IS NOT NULL AND s.first_response_at_utc <= %s AS responded
              FROM {schema}.inquiry_sla(%s) f
              JOIN {schema}.sub_ticket s ON s.sub_ticket_id = f.sub_ticket_id
             WHERE f.status = ANY(%s) AND (%s::text[] IS NULL OR f.sub_ticket_id = ANY(%s))""",
        (as_of, as_of, list(OPEN), sub_ticket_ids, sub_ticket_ids),
    ).fetchall()
    out = []
    for sub_id, status, received, fr_t, res_t, fr_el, wait_h, res_el, responded in rows:
        if fr_t is not None and not responded:                           # 처리 3
            if fr_el >= fr_t * thr:
                out.append(_alert(sub_id, "FR_AT_RISK", received + _hours(fr_t * thr), fr_t * thr, fr_t))
            if fr_el > fr_t:
                out.append(_alert(sub_id, "FR_BREACHED", received + _hours(fr_t), fr_t, fr_t))
        if res_t is not None and status in RES_OPEN:                     # 처리 2·4
            if res_el >= res_t * thr:
                out.append(_alert(sub_id, "RES_AT_RISK", received + _hours(wait_h + res_t * thr), res_t * thr, res_t))
            if res_el > res_t:
                out.append(_alert(sub_id, "RES_BREACHED", received + _hours(wait_h + res_t), res_t, res_t))
    return out


def _alert(sub_id: str, kind: str, raised: datetime, elapsed: Decimal, target: int) -> dict:
    """elapsed는 발생 당시 경과(= 넘은 기준값), target은 그때 목표 (기술 명세서 §6-2 "발생 당시 값")."""
    return {"sub_ticket_id": sub_id, "alert_type": kind, "raised_at_utc": raised, "elapsed_h": elapsed, "target_h": target}


def raise_alerts(conn: Connection, as_of: datetime, schema: str = "svc",
                 sub_ticket_ids: list[str] | None = None) -> list[tuple[str, str, datetime]]:
    """새로 넣은 경고 (sub_ticket_id, 종류, 발생 시각) 목록. 같은 종류는 문의당 한 번(UNIQUE)."""
    added = []
    with conn.transaction():
        for a in due_alerts(conn, as_of, schema, sub_ticket_ids):
            row = conn.execute(
                f"""INSERT INTO {schema}.sla_alert (sub_ticket_id, alert_type, raised_at_utc, elapsed_h, target_h)
                    VALUES (%s, %s, %s, %s, %s) ON CONFLICT (sub_ticket_id, alert_type) DO NOTHING
                    RETURNING alert_id""",
                (a["sub_ticket_id"], a["alert_type"], a["raised_at_utc"], a["elapsed_h"], a["target_h"]),
            ).fetchone()
            if row:
                added.append((a["sub_ticket_id"], a["alert_type"], a["raised_at_utc"]))
    return added


def clear_alerts(conn: Connection, as_of: datetime, schema: str = "svc",
                 sub_ticket_ids: list[str] | None = None) -> list[tuple[str, str]]:
    """목표가 바뀌어 조건이 풀린 경고에 해제 시각을 쓴다 (FR-027 처리 6)."""
    if schema not in SCHEMAS:
        raise ValueError(schema)
    due = {(a["sub_ticket_id"], a["alert_type"]) for a in due_alerts(conn, as_of, schema, sub_ticket_ids)}
    rows = conn.execute(
        f"""SELECT a.alert_id, a.sub_ticket_id, a.alert_type
              FROM {schema}.sla_alert a JOIN {schema}.sub_ticket s ON s.sub_ticket_id = a.sub_ticket_id
             WHERE a.cleared_at_utc IS NULL AND (%s::text[] IS NULL OR a.sub_ticket_id = ANY(%s))
               AND a.target_h IS DISTINCT FROM CASE WHEN a.alert_type LIKE 'FR%%' THEN s.sla_first_response_target_h
                                                    ELSE s.sla_resolution_target_h END""",
        (sub_ticket_ids, sub_ticket_ids),
    ).fetchall()
    cleared = []
    with conn.transaction():
        for alert_id, sub_id, kind in rows:
            if (sub_id, kind) not in due:
                conn.execute(f"UPDATE {schema}.sla_alert SET cleared_at_utc = %s WHERE alert_id = %s", (as_of, alert_id))
                cleared.append((sub_id, kind))
    return cleared


def alert_history(conn: Connection, sub_ticket_id: str) -> list[dict]:
    """경고 이력 발생 시각순 (FR-027 출력)."""
    cur = conn.execute(
        """SELECT alert_type, raised_at_utc, elapsed_h, target_h, cleared_at_utc FROM svc.sla_alert
            WHERE sub_ticket_id = %s ORDER BY raised_at_utc, alert_id""", (sub_ticket_id,))
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]
