"""rule-engine 완료 기준 시험 (openspec/changes/add-rule-engine).

예시 문의의 입력 값(category_code, urgency_flag, provided_info)은 원래 언어 모델(5번 변경)이 만든다.
그래서 정답과 비교하는 시험 코드만 gold.ticket_gold에서 읽는다(CLAUDE.md 규칙 6).
"""

import ast
from pathlib import Path

import pytest

from app.rules.lookup import lookup_customer, lookup_product
from app.rules.priority import decide_priority
from app.rules.required_info import check_required_info
from app.rules.routing import assign_dept, decide_return_kind
from app.rules.sla import find_sla_target

RULES_DIR = Path(__file__).resolve().parents[2] / "app" / "rules"


def ticket(conn, ticket_id):
    row = conn.execute(
        """SELECT customer_id, product_code, product_family, category_code, urgency_flag, provided_info
             FROM gold.ticket_gold WHERE ticket_id = %s""",
        (ticket_id,),
    ).fetchone()
    customer_id, product_code, family, category, urgency, provided = row
    return {
        "customer_id": customer_id, "product_code": product_code, "family": family,
        "category": category, "urgency": urgency,
        "provided": [f for f in (provided or "").split(";") if f],
    }


def test_rules_do_not_import_llm():
    """CLAUDE.md 규칙 1: 규칙 코드는 언어 모델 호출 계층을 import하지 않는다."""
    for path in RULES_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n == "app.llm" or n.startswith("app.llm.") for n in names), path.name


def test_ac_010_1(conn):
    t = ticket(conn, "CSV1-000017")
    customer = lookup_customer(conn, t["customer_id"])
    product = lookup_product(conn, t["product_code"])
    assert (customer.customer_tier, customer.country) == ("PLATINUM", "TH")
    assert (product.product_family, product.tech_support_dept) == ("LV_BREAKER", "TS_LV")


def test_ac_010_2(conn):
    t = ticket(conn, "CSV1-000017")
    product = lookup_product(conn, None)
    assert product.product_family is None and "제품 미확정" in product.flags
    routing = assign_dept(conn, product.product_family, t["category"])
    required = check_required_info(conn, product.product_family, t["category"], t["provided"])
    assert routing.assigned_dept is None and routing.flags == ["제품 확인 뒤 배정됨"]
    assert required.missing_info == [] and required.flags == ["제품·유형 확인 뒤 계산됨"]


def test_ac_011_1(conn):
    t = ticket(conn, "CSV1-000017")
    result = decide_priority(conn, t["category"], t["urgency"])
    assert (result.priority, result.priority_rule_id) == ("P1", "PR-02")
    assert [(c.rule_id, c.matched) for c in result.priority_trace] == [("PR-01", False), ("PR-02", True)]


def test_ac_011_2(conn):
    t = ticket(conn, "CSV1-000004")
    result = decide_priority(conn, t["category"], t["urgency"])
    assert (result.priority, result.priority_rule_id) == ("P3", "PR-06")


def test_ac_011_3(conn):
    t = ticket(conn, "CSV1-000031")
    result = decide_priority(conn, t["category"], t["urgency"])
    assert (result.priority, result.priority_rule_id) == ("P4", "PR-07")


def test_ac_012_1(conn):
    t = ticket(conn, "CSV1-000017")
    result = assign_dept(conn, t["family"], t["category"])
    assert (result.assigned_dept, result.routing_rule_id) == ("TS_LV", "RT-LV_BREAKER-DEFECT")
    # 명세서 AC-012-1은 FIELD_SVC라고 적었지만 routing_rules.csv 그 행 값은 QA_CLAIM (조장 확인 사항)
    assert result.escalation_dept == "QA_CLAIM"
    assert result.escalation_condition


def test_ac_012_2(conn):
    t97 = ticket(conn, "CSV1-000097")
    kind97 = decide_return_kind("The units have a recurring quality problem")
    r97 = assign_dept(conn, t97["family"], t97["category"], kind97.return_kind)
    assert (r97.assigned_dept, r97.routing_rule_id) == ("WARRANTY_DESK", "RT-HMI-RETURN")

    # CSV1-000039 본문 사유는 프랑스어. L2가 영어로 바꿨다고 가정한 같은 뜻 문장(반품_사유_단어목록_v1 2장)
    t39 = ticket(conn, "CSV1-000039")
    kind39 = decide_return_kind("We received a different model from what we ordered")
    r39 = assign_dept(conn, t39["family"], t39["category"], kind39.return_kind)
    assert kind39.return_kind == "NON_DEFECT"
    assert (r39.assigned_dept, r39.routing_rule_id) == ("SCM", "RT-ALL-RETURN-NON_DEFECT")


def test_ac_012_3(conn):
    t = ticket(conn, "CSV1-000039")
    kind = decide_return_kind(None)
    first = assign_dept(conn, t["family"], t["category"], kind.return_kind)
    assert kind.return_kind == "UNKNOWN"
    assert first.routing_rule_id == "RT-MV_EQUIP-RETURN" and "반품 사유 확인 필요" in first.flags
    again = assign_dept(conn, t["family"], t["category"], "NON_DEFECT")
    assert (again.assigned_dept, again.routing_rule_id) == ("SCM", "RT-ALL-RETURN-NON_DEFECT")
    assert "반품 사유 확인 필요" not in again.flags


def test_ac_012_4(conn):
    result = assign_dept(conn, "CONTROL", "FW_UPDATE")
    assert result.assigned_dept is None
    assert "배정 규칙 없음 — 분류 재검토" in result.flags


def test_ac_013_1(conn):
    t = ticket(conn, "CSV1-000017")
    assert t["provided"] == ["product_model", "error_code", "load_profile"]
    result = check_required_info(conn, t["family"], t["category"], t["provided"])
    assert result.missing_info == ["serial_no", "operating_condition", "photos"]
    assert result.missing_blocking_info == ["serial_no"]


def test_ac_013_2(conn):
    t = ticket(conn, "CSV1-000004")
    result = check_required_info(conn, t["family"], t["category"], t["provided"])
    assert result.missing_info == [] and result.missing_blocking_info == []
    assert result.info_request_needed is False


def test_ac_013_3(conn):
    t = ticket(conn, "CSV1-000017")
    result = check_required_info(conn, t["family"], t["category"], t["provided"] + ["serial_no"])
    assert "serial_no" not in result.missing_blocking_info
    assert result.info_request_needed is False


def test_ac_014_1(conn):
    t = ticket(conn, "CSV1-000017")
    tier = lookup_customer(conn, t["customer_id"]).customer_tier
    priority = decide_priority(conn, t["category"], t["urgency"]).priority
    result = find_sla_target(conn, t["category"], tier, priority)
    assert (result.sla_first_response_target_h, result.sla_resolution_target_h) == (1, 24)
    assert result.sla_id == "SLA-DEFECT-PLATINUM-P1"


def test_ac_014_2(conn):
    t = ticket(conn, "CSV1-000031")
    tier = lookup_customer(conn, t["customer_id"]).customer_tier
    priority = decide_priority(conn, t["category"], t["urgency"]).priority
    assert (tier, priority) == ("STANDARD", "P4")
    result = find_sla_target(conn, t["category"], tier, priority)
    assert (result.sla_first_response_target_h, result.sla_resolution_target_h) == (72, 168)
