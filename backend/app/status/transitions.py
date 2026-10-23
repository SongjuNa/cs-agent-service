"""상태 전이 (명세서 v1.5 FR-025, 기술 명세서 v1.4 §6-4).

상태는 DB 함수 svc.transition() 하나로만 바꾼다. 허용 전이표(svc.status_transition)에 없으면 DB가 거부한다.
이력은 사건 시각으로 남긴다(T34). 이 모듈은 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).
"""

from __future__ import annotations

from datetime import datetime

from psycopg import Connection, errors

MSG_REFUSED = "현재 상태({status})에서는 할 수 없는 작업"
MSG_CONCURRENT = "다른 사용자가 먼저 변경함. 새로고침"


class TransitionRefused(Exception):
    """허용 전이표에 없는 전이 (FR-025 예외 1행)."""

    def __init__(self, status: str):
        super().__init__(MSG_REFUSED.format(status=status))
        self.status = status


class ConcurrentChange(Exception):
    """다른 사람이 먼저 바꿈 (FR-025 예외 2행)."""

    def __init__(self):
        super().__init__(MSG_CONCURRENT)


def current(conn: Connection, sub_ticket_id: str, lock: bool = False) -> tuple[str, int]:
    """(상태, version). lock이면 행을 잠근다(같은 트랜잭션 안에서만 뜻이 있다)."""
    row = conn.execute(
        "SELECT status, version FROM svc.sub_ticket WHERE sub_ticket_id = %s" + (" FOR UPDATE" if lock else ""),
        (sub_ticket_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"문의가 없다: {sub_ticket_id}")
    return row[0], row[1]


def transition(conn: Connection, sub_ticket_id: str, to_status: str, event_kind: str, at: datetime, actor: str,
               reason: str | None = None, final_action: str | None = None,
               expected_version: int | None = None) -> None:
    """svc.transition()을 부른다. 거부·동시 수정은 예외로 바꾼다. 호출하는 쪽의 트랜잭션 안에서 돈다."""
    status, version = current(conn, sub_ticket_id, lock=True)
    if expected_version is not None and expected_version != version:
        raise ConcurrentChange()
    try:
        with conn.transaction():  # 거부되면 이 안만 되돌린다
            conn.execute("SELECT svc.transition(%s, %s, %s, %s, %s, %s, %s)",
                         (sub_ticket_id, to_status, event_kind, at, actor, reason, final_action))
    except errors.RaiseException as exc:
        if "허용되지 않은 전이" in str(exc):
            raise TransitionRefused(status) from exc
        raise


def history(conn: Connection, sub_ticket_id: str) -> list[dict]:
    """상태 이력 시각순 (FR-025 출력)."""
    cur = conn.execute(
        """SELECT from_status, to_status, event_kind, changed_at_utc, changed_by, reason
             FROM svc.ticket_status_history WHERE sub_ticket_id = %s ORDER BY changed_at_utc, history_id""",
        (sub_ticket_id,),
    )
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def wait_intervals(rows: list[dict]) -> list[dict]:
    """WAITING_CUSTOMER 대기 구간: 들어간 시각과 나온 시각(아직이면 None) (FR-025 처리 3)."""
    out = []
    for i, row in enumerate(rows):
        if row["to_status"] == "WAITING_CUSTOMER":
            nxt = rows[i + 1]["changed_at_utc"] if i + 1 < len(rows) else None
            out.append({"entered_at_utc": row["changed_at_utc"], "left_at_utc": nxt})
    return out
