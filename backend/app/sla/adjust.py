"""우선순위 조정과 SLA 재계산 (명세서 v1.5 FR-028, FR-014 처리 5, 기술 명세서 v1.4 §5-4).

규칙 결과(priority_rule_id)는 그대로 두고 최종 우선순위만 바꾼다. 목표는 새 우선순위로 다시 찾아 덮어쓰고,
이전 값은 priority_adjustment에 남긴다. 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection

from app.rules.sla import find_sla_target
from app.sla.alerts import clear_alerts, raise_alerts
from app.sla.clock import clocks
from app.status.transitions import ConcurrentChange

PRIORITIES = ("P1", "P2", "P3", "P4")
REASON_KINDS = ("CUSTOMER_REQUEST", "IMPACT_REASSESSED", "OTHER")  # FR-028 처리 6, 가-8
CLOSED = ("RESOLVED", "CLOSED")

MSG_NO_REASON = "조정 사유를 입력하세요"                    # FR-028 예외 1행
MSG_CLOSED = "종료된 문의는 바꿀 수 없음"                   # 예외 2행
MSG_SAME = "현재와 같은 우선순위"                           # 처리 1, 화면 정의서 v1 P3
MSG_NO_PRIORITY = "우선순위가 없는 문의"                    # C-68
MSG_BAD_KIND = "사유 분류는 CUSTOMER_REQUEST·IMPACT_REASSESSED·OTHER"  # 구현 선택
MSG_BREACH = "이 조정으로 SLA 위반 상태가 됩니다. 계속할까요?"  # 예외 3행


class AdjustError(Exception):
    """조정 거부. status는 API 응답 코드."""

    def __init__(self, message: str, status: int, preview: dict | None = None):
        super().__init__(message)
        self.status = status
        self.preview = preview


@dataclass
class _Sub:
    sub_ticket_id: str
    status: str
    version: int
    priority: str | None
    category_code: str | None
    customer_tier: str
    sla_id: str | None
    fr_target_h: int | None
    res_target_h: int | None


def _load(conn: Connection, sub_ticket_id: str, lock: bool = False) -> _Sub:
    row = conn.execute(
        """SELECT s.sub_ticket_id, s.status, s.version, s.priority, s.category_code, t.customer_tier, s.sla_id,
                  s.sla_first_response_target_h, s.sla_resolution_target_h
             FROM svc.sub_ticket s JOIN svc.ticket t ON t.ticket_id = s.ticket_id
            WHERE s.sub_ticket_id = %s""" + (" FOR UPDATE OF s" if lock else ""),
        (sub_ticket_id,),
    ).fetchone()
    if row is None:
        raise LookupError(sub_ticket_id)
    return _Sub(*row)


def _breaches(sla: dict[str, Any], fr_t: int | None, res_t: int | None, responded: bool) -> bool:
    res = res_t is not None and sla["res_elapsed_h"] > res_t
    fr = fr_t is not None and not responded and sla["fr_elapsed_h"] > fr_t
    return res or fr


def preview(conn: Connection, sub_ticket_id: str, new_priority: str, at: datetime) -> dict[str, Any]:
    """저장하지 않고 이전·새 목표와 즉시 위반 여부를 돌려준다(화면 정의서 v1 SCR-03-P3 미리 보기)."""
    sub = _load(conn, sub_ticket_id)
    _check(sub, new_priority)
    target = find_sla_target(conn, sub.category_code, sub.customer_tier, new_priority)
    sla = clocks(conn, [sub_ticket_id], as_of=at)[sub_ticket_id]
    (responded,) = conn.execute(
        "SELECT first_response_at_utc IS NOT NULL AND first_response_at_utc <= %s FROM svc.sub_ticket WHERE sub_ticket_id = %s",
        (at, sub_ticket_id)).fetchone()
    now_breached = _breaches(sla, sub.fr_target_h, sub.res_target_h, responded)
    new_breached = _breaches(sla, target.sla_first_response_target_h, target.sla_resolution_target_h, responded)
    return {
        "from_priority": sub.priority, "to_priority": new_priority,
        "from_sla_id": sub.sla_id, "to_sla_id": target.sla_id,
        "from_fr_target_h": sub.fr_target_h, "from_res_target_h": sub.res_target_h,
        "to_fr_target_h": target.sla_first_response_target_h, "to_res_target_h": target.sla_resolution_target_h,
        "becomes_breached": new_breached and not now_breached,
        "fr_elapsed_h": sla["fr_elapsed_h"], "res_elapsed_h": sla["res_elapsed_h"],
        "version": sub.version,
    }


def _check(sub: _Sub, new_priority: str) -> None:
    if new_priority not in PRIORITIES:
        raise AdjustError("우선순위는 P1~P4", 400)
    if sub.status in CLOSED:
        raise AdjustError(MSG_CLOSED, 409)
    if sub.priority is None:
        raise AdjustError(MSG_NO_PRIORITY, 409)
    if sub.priority == new_priority:
        raise AdjustError(MSG_SAME, 409)


def adjust(conn: Connection, sub_ticket_id: str, new_priority: str, reason_kind: str | None, reason: str | None,
           agent_id: str, at: datetime, confirm_breach: bool = False,
           expected_version: int | None = None) -> dict[str, Any]:
    """조정을 저장하고 경고를 다시 점검한다(FR-028 처리 1~5)."""
    if not reason_kind or not (reason or "").strip():
        raise AdjustError(MSG_NO_REASON, 400)
    if reason_kind not in REASON_KINDS:
        raise AdjustError(MSG_BAD_KIND, 400)
    view = preview(conn, sub_ticket_id, new_priority, at)
    if view["becomes_breached"] and not confirm_breach:
        raise AdjustError(MSG_BREACH, 409, preview=view)
    with conn.transaction():
        sub = _load(conn, sub_ticket_id, lock=True)
        if expected_version is not None and expected_version != sub.version:
            raise ConcurrentChange()
        _check(sub, new_priority)
        conn.execute(
            """UPDATE svc.sub_ticket SET priority = %s, priority_adjusted_by_agent = true, sla_id = %s,
                   sla_first_response_target_h = %s, sla_resolution_target_h = %s, version = version + 1
             WHERE sub_ticket_id = %s""",
            (new_priority, view["to_sla_id"], view["to_fr_target_h"], view["to_res_target_h"], sub_ticket_id),
        )
        (adjust_id,) = conn.execute(
            """INSERT INTO svc.priority_adjustment (sub_ticket_id, from_priority, to_priority, from_sla_id, to_sla_id,
                   from_fr_target_h, from_res_target_h, to_fr_target_h, to_res_target_h, reason_kind, reason,
                   adjusted_by, adjusted_at_utc)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING adjust_id""",
            (sub_ticket_id, sub.priority, new_priority, sub.sla_id, view["to_sla_id"], sub.fr_target_h,
             sub.res_target_h, view["to_fr_target_h"], view["to_res_target_h"], reason_kind, reason.strip(),
             agent_id, at),
        ).fetchone()
    raised = raise_alerts(conn, at, sub_ticket_ids=[sub_ticket_id])        # 처리 4
    cleared = clear_alerts(conn, at, sub_ticket_ids=[sub_ticket_id])       # FR-027 처리 6
    return {
        "adjust_id": adjust_id, "priority": new_priority, "priority_adjusted_by_agent": True,
        **{k: view[k] for k in ("from_priority", "from_sla_id", "to_sla_id", "from_fr_target_h", "from_res_target_h",
                                "to_fr_target_h", "to_res_target_h")},
        "sla": clocks(conn, [sub_ticket_id], as_of=at)[sub_ticket_id],
        "alerts_raised": [k for _, k, _ in raised], "alerts_cleared": [k for _, k in cleared],
    }


def adjustments(conn: Connection, sub_ticket_id: str) -> list[dict]:
    """조정 이력 시각순 (FR-028 출력)."""
    cur = conn.execute(
        """SELECT adjust_id, from_priority, to_priority, from_sla_id, to_sla_id, from_fr_target_h, from_res_target_h,
                  to_fr_target_h, to_res_target_h, reason_kind, reason, adjusted_by, adjusted_at_utc
             FROM svc.priority_adjustment WHERE sub_ticket_id = %s ORDER BY adjusted_at_utc, adjust_id""",
        (sub_ticket_id,))
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]
