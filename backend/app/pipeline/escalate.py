"""처리 흐름 Q9a 이관 후보 (기술 명세서 v1.4 §2-1, §5-6). 하위 문의마다 이관 후보를 붙인다."""

from __future__ import annotations

from psycopg import Connection

from app.pipeline.state import EscalationHint, SubTicketState
from app.rules.escalation import escalation_candidates


def add_escalation_candidates(conn: Connection, sub: SubTicketState) -> None:
    """진단 1순위의 출동·교체 표시를 쓴다(FR-020 입력, C-148). 진단 후보가 없으면 SAFETY만 본다."""
    top = sub.fault_candidates[0] if sub.fault_candidates else None
    result = escalation_candidates(conn, sub.category_code, sub.urgency_flag,
                                   (top.onsite_required, top.replace_required) if top else None,
                                   sub.return_reason, sub.priority_final, sub.escalation_condition)
    sub.escalation_candidates = [EscalationHint(rule_id=c.rule_id, dept=c.dept, reason=c.reason,
                                                reason_code=c.reason_code, team=c.team) for c in result.candidates]
    sub.escalation = result.as_output()
