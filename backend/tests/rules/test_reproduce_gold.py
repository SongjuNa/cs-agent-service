"""tickets.csv 4,000건 재현 시험 (W1 완료 기준)과 영어 반품 211건 단어 판정 (W10).

정답과 비교하는 시험이므로 gold.ticket_gold의 정답 열을 읽는다(CLAUDE.md 규칙 6).
"""

import pytest

from app.rules.lookup import lookup_customer
from app.rules.priority import decide_priority
from app.rules.required_info import check_required_info
from app.rules.routing import decide_return_kind
from app.rules.sla import find_sla_target

# 반품_사유_단어목록_v1_20261022.md 2장: 영어 반품 211건이 담고 있는 여섯 문장
RETURN_SENTENCES = [
    "The goods arrived with damaged packaging and a cracked housing",
    "The unit was dead on arrival and does not power up",
    "The units have a recurring quality problem",
    "We received a different model from what we ordered",
    "We ordered the wrong rating by mistake",
    "The project was cancelled and the units are unused",
]


def split(value):
    return [f for f in (value or "").split(";") if f]


@pytest.fixture(scope="module")
def gold(conn):
    return conn.execute(
        """SELECT ticket_id, customer_id, product_family, category_code, urgency_flag, provided_info,
                  priority, priority_rule_id, priority_adjusted_by_agent,
                  sla_first_response_target_h, sla_resolution_target_h,
                  required_info, missing_info, missing_blocking_info
             FROM gold.ticket_gold ORDER BY ticket_id"""
    ).fetchall()


def test_w1_5_priority(conn, gold):
    assert len(gold) == 4000
    wrong_rule, wrong_priority = [], []
    for row in gold:
        tid, _, _, category, urgency, _, priority, rule_id, adjusted = row[:9]
        result = decide_priority(conn, category, urgency)
        if result.priority_rule_id != rule_id:
            wrong_rule.append(tid)
        if adjusted == "N" and result.priority != priority:
            wrong_priority.append(tid)
    assert wrong_rule == [] and wrong_priority == []


def test_w1_6_sla_target(conn, gold):
    wrong = []
    for row in gold:
        tid, customer_id, _, category, _, _, priority = row[:7]
        fr_h, res_h = row[9:11]
        tier = lookup_customer(conn, customer_id).customer_tier
        result = find_sla_target(conn, category, tier, priority)
        if (str(result.sla_first_response_target_h), str(result.sla_resolution_target_h)) != (fr_h, res_h):
            wrong.append(tid)
    assert wrong == []


def test_w1_7_required_info(conn, gold):
    wrong = []
    for row in gold:
        tid, _, family, category, _, provided = row[:6]
        required, missing, blocking = row[11:14]
        result = check_required_info(conn, family, category, split(provided))
        if (result.required_info, result.missing_info, result.missing_blocking_info) != (
            split(required), split(missing), split(blocking)
        ):
            wrong.append(tid)
    assert wrong == []


def test_w10_1_english_returns(conn):
    rows = conn.execute(
        """SELECT ticket_id, inquiry_body, routing_rule_id FROM gold.ticket_gold
            WHERE category_code = 'RETURN' AND body_language = 'en'"""
    ).fetchall()
    assert len(rows) == 211
    wrong = []
    for tid, body, routing_rule_id in rows:
        found = [s for s in RETURN_SENTENCES if s in body]
        assert len(found) == 1, tid
        expected = "NON_DEFECT" if routing_rule_id == "RT-ALL-RETURN-NON_DEFECT" else "DEFECT"
        if decide_return_kind(found[0]).return_kind != expected:
            wrong.append(tid)
    assert wrong == []
