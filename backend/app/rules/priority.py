"""우선순위 계산 (FR-011, 기술 명세서 §5-2).

조건은 코드에 적지 않고 priority_rule_urgency, priority_rule_category 표에서 읽는다.
조건 표에 행이 없으면 그 조건은 "모두 맞음"이다.
"""

from dataclasses import dataclass, field

from psycopg import Connection


@dataclass(frozen=True)
class RuleCheck:
    rule_id: str
    matched: bool


@dataclass(frozen=True)
class PriorityResult:
    priority: str | None = None
    priority_rule_id: str | None = None
    condition: str | None = None          # 화면 표시용 원문(§5-2)
    priority_trace: list[RuleCheck] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def decide_priority(conn: Connection, category_code: str | None, urgency_flag: str | None) -> PriorityResult:
    if not category_code or not urgency_flag:
        return PriorityResult(flags=["분류 뒤 계산됨"])
    rules = conn.execute(
        """SELECT r.rule_id, r.condition, r.priority,
                  array_remove(array_agg(DISTINCT u.urgency), NULL),
                  array_remove(array_agg(DISTINCT c.category), NULL)
             FROM ref.priority_rule r
             LEFT JOIN ref.priority_rule_urgency u USING (rule_id)
             LEFT JOIN ref.priority_rule_category c USING (rule_id)
            GROUP BY r.rule_id, r.condition, r.priority, r.rule_order
            ORDER BY r.rule_order"""
    ).fetchall()
    trace = []
    for rule_id, condition, priority, urgencies, categories in rules:
        urg_ok = not urgencies or urgency_flag in urgencies
        cat_ok = not categories or category_code in categories
        trace.append(RuleCheck(rule_id, urg_ok and cat_ok))
        if urg_ok and cat_ok:
            return PriorityResult(priority, rule_id, condition, trace)
    return PriorityResult(priority_trace=trace, flags=["우선순위 미정"])
