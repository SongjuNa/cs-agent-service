"""가상 상담원 명단과 담당 배정 (조장 결정 2026-10-23, 기술 명세서 v1.4 §8-3, 테이블 정의서 v1.3 assignee_masked).

명단은 `app/roster/agent_roster.json`(지어낸 이름. 11개 부서 × 12명 + QA_CLAIM·RND_FW 시연용 각 1명, FR-033 처리 10). 담당 값(assignee_masked)에는 이름을 쓴다(C-128).
새 문의는 그 부서에서 미해결 문의를 가장 적게 맡은 사람, 같으면 명단 순서로 배정한다(C-127).
이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from psycopg import Connection

ROSTER_FILE = Path(__file__).resolve().parents[1] / "roster" / "agent_roster.json"
OPEN = ("NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED")  # FR-029 처리 1


@lru_cache(maxsize=1)
def roster() -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(ROSTER_FILE.read_text(encoding="utf-8"))["agents"])


def agents(dept: str | None = None) -> list[dict[str, str]]:
    """[{name, dept, demo}] (명단 순서). dept가 있으면 그 부서만. demo = 시연용(FR-033 처리 10)."""
    return [{"name": a["name"], "dept": a["dept"], "demo": a.get("demo", False)}
            for a in roster() if dept is None or a["dept"] == dept]


def name_of(source_id: str | None) -> str | None:
    """운영진 데이터 상담원 ID(TS_LV_AGENT_09) → 명단 이름. 명단에 없으면 그대로."""
    return next((a["name"] for a in roster() if a["source_id"] == source_id), source_id)


def assign(conn: Connection, sub_ticket_id: str) -> str | None:
    """담당 부서가 있고 담당이 비었거나 다른 부서 명단 사람이면 배정한다. 명단에 없는 값(손으로 넣은 ID 등)은 그대로 둔다.
    돌려주는 값: 지금 담당."""
    dept, current = conn.execute("SELECT assigned_dept, assignee_masked FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                 (sub_ticket_id,)).fetchone()
    names = [a["name"] for a in agents(dept)] if dept else []
    other_dept = current is not None and any(a["name"] == current for a in roster()) and current not in names
    if not names or not (current is None or other_dept):
        return current
    load = dict(conn.execute(
        """SELECT assignee_masked, count(*) FROM svc.sub_ticket
            WHERE assignee_masked = ANY(%s) AND status = ANY(%s) AND sub_ticket_id <> %s GROUP BY 1""",
        (names, list(OPEN), sub_ticket_id)).fetchall())
    chosen = min(names, key=lambda n: (load.get(n, 0), names.index(n)))
    conn.execute("UPDATE svc.sub_ticket SET assignee_masked = %s WHERE sub_ticket_id = %s", (chosen, sub_ticket_id))
    return chosen
