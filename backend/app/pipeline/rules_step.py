"""처리 흐름 Q2~Q6 (기술 명세서 v1.4 §2-2): 3번 변경의 규칙 함수를 불러 하위 문의 상태를 채운다."""

from __future__ import annotations

from psycopg import Connection

from app.pipeline.state import RuleCheck, SubTicketState, TicketState
from app.rules.lookup import lookup_customer
from app.rules.priority import decide_priority
from app.rules.required_info import RequiredInfoResult, check_required_info
from app.rules.routing import assign_dept, decide_return_kind
from app.rules.sla import find_sla_target


def apply_rules(conn: Connection, state: TicketState) -> dict[str, RequiredInfoResult]:
    """규칙 단계를 돌린다. 고객 기준정보가 없으면 CustomerNotFound를 그대로 올린다(§2-2 Q2, D25).

    돌려주는 값: 하위 문의별 필수정보 결과(라벨이 L3에 필요하다).
    """
    customer = lookup_customer(conn, state.customer_id)  # Q2
    required: dict[str, RequiredInfoResult] = {}
    for sub in state.sub_tickets:
        sub.customer_tier = customer.customer_tier
        _apply(conn, sub, required)
    return required


def _add_flags(sub: SubTicketState, flags: list[str]) -> None:
    sub.flags += [f for f in flags if f not in sub.flags]


def _apply(conn: Connection, sub: SubTicketState, required: dict[str, RequiredInfoResult]) -> None:
    priority = decide_priority(conn, sub.category_code, sub.urgency_flag)  # Q3
    sub.priority_rule = priority.priority
    sub.priority_rule_id = priority.priority_rule_id
    sub.priority_trace = [RuleCheck(rule_id=c.rule_id, matched=c.matched) for c in priority.priority_trace]
    sub.priority_final = priority.priority  # 조정(FR-028)이 없으므로 규칙값 그대로
    _add_flags(sub, priority.flags)

    if sub.category_code == "RETURN":  # Q4 반품 구분: L2가 영어로 정리한 사유(§5-3)
        sub.return_kind = decide_return_kind(sub.return_reason).return_kind
    routing = assign_dept(conn, sub.product_family, sub.category_code, sub.return_kind)
    sub.assigned_dept = routing.assigned_dept
    sub.routing_rule_id = routing.routing_rule_id
    sub.escalation_condition = routing.escalation_condition
    _add_flags(sub, routing.flags)

    info = check_required_info(conn, sub.product_family, sub.category_code,
                               [pf.field for pf in sub.provided_fields])  # Q5
    sub.missing_info = info.missing_info
    sub.missing_blocking_info = info.missing_blocking_info
    required[sub.sub_ticket_id] = info
    _add_flags(sub, info.flags)

    sla = find_sla_target(conn, sub.category_code, sub.customer_tier, sub.priority_final)  # Q6
    sub.sla_id = sla.sla_id
    sub.fr_target_h = sla.sla_first_response_target_h
    sub.res_target_h = sla.sla_resolution_target_h
    _add_flags(sub, sla.flags)
