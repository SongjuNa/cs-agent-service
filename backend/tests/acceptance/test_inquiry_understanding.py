"""문의 이해 완료 기준 (FR-004·005·007·008, 변경 add-inquiry-understanding).

- 대역 Transport 시험: 언어 모델 없이 실패 처리, 제목 제외, 값 정리를 본다.
- 실제 Gemini 시험: GEMINI_API_KEY가 있을 때만 돈다. 없으면 "키 없음"으로 건너뛴다.
입력은 gold.v_inputs(서비스와 같은 입력 열)에서 읽는다. 기대값은 명세서 AC의 값이다.
"""

from __future__ import annotations

import json

import pytest

from app.config import get_settings
from app.llm.client import LlmTimeout, PROMPTS_DIR, default_transport
from app.llm.extract import clean_fields, normalize_fw
from app.pipeline.understand import understand_ticket

# --- 공통 ---


def ticket_input(conn, ticket_id: str) -> dict:
    cur = conn.execute("SELECT * FROM gold.v_inputs WHERE ticket_id = %s", (ticket_id,))
    names = [d.name for d in cur.description]
    return dict(zip(names, cur.fetchone()))


class FakeTransport:
    """정해진 응답 글을 차례로 낸다. L1·L2를 지시문 첫 줄로 구분한다. 받은 지시문을 모두 남긴다."""

    def __init__(self, l1: list, l2: list):
        self.queues = {"L1": list(l1), "L2": list(l2)}
        self.prompts: list[str] = []

    def send(self, prompt: str, schema: dict) -> str:
        self.prompts.append(prompt)
        call = "L2" if prompt.startswith("You extract") else "L1"
        reply = self.queues[call].pop(0) if len(self.queues[call]) > 1 else self.queues[call][0]
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)

    def count(self, call: str) -> int:
        first = "You extract" if call == "L2" else "You read one"
        return sum(p.startswith(first) for p in self.prompts)


def l1_reply(category="QUOTE", urgency="NONE", lang="fr", conf=0.9, lang_conf=0.95, extra=()):
    subs = [{
        "seq": 1, "category_code": category, "category_confidence": conf,
        "evidence_sentences": ["s1"], "urgency_flag": urgency, "urgency_evidence": None,
        "query_en": "q",
    }]
    subs += list(extra)
    return {"body_language": lang, "body_language_confidence": lang_conf, "sub_tickets": subs}


EMPTY_L2 = {"fields": []}


# --- FR-004 ---


def test_ac_004_3_language_fallback_when_l1_invalid_twice(conn):
    """AC-004-3: L1이 두 번 모두 스키마 밖 응답 → body_language = language, 불확실 표시, L2 실행."""
    bad = l1_reply(lang="xx")  # 15개 언어 밖
    fake = FakeTransport([bad, bad], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000008"))
    assert out.run_status == "SUCCESS"
    assert out.state.body_language == "ar" == out.state.language
    assert out.state.body_language_uncertain
    assert "언어 판정 불확실" in out.state.sub_tickets[0].flags
    assert fake.count("L1") == 2 and fake.count("L2") == 1


def test_low_language_confidence_falls_back(conn):
    """FR-004 처리 3: 확신도 0.6 미만 → language로 두고 불확실 표시."""
    fake = FakeTransport([l1_reply(lang="en", lang_conf=0.4)], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    assert out.state.body_language == "fr" and out.state.body_language_uncertain


# --- FR-005 ---


def test_ac_005_2_subject_never_sent(conn):
    """AC-005-2: 입력에 제목을 일부러 넣어도 언어 모델에 보낸 글과 입력 항목 이름에 없다."""
    subject = conn.execute(
        "SELECT inquiry_subject FROM gold.ticket_gold WHERE ticket_id = 'CSV1-000004'"
    ).fetchone()[0]
    assert subject.startswith("Demande de tarif")
    data = ticket_input(conn, "CSV1-000004") | {"inquiry_subject": subject}
    fake = FakeTransport([l1_reply()], [EMPTY_L2])
    out = understand_ticket(conn, fake, data)
    assert out.run_status == "SUCCESS"
    assert all(subject not in p for p in fake.prompts)
    for names in out.llm_field_names.values():
        assert "inquiry_subject" not in names
    assert "inquiry_subject" not in out.state.model_dump_json()


def test_ac_005_3_out_of_enum_twice_is_classification_failure(conn):
    """AC-005-3: 10종 밖 유형 두 번 → category_code 비움 + "분류 실패", 흐름 계속."""
    bad = l1_reply(category="PRICING")
    fake = FakeTransport([bad, bad], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    sub = out.state.sub_tickets[0]
    assert out.run_status == "SUCCESS"
    assert sub.category_code is None and "분류 실패" in sub.flags
    assert sub.urgency_flag == "NONE" and "긴급도 판정 실패" in sub.flags


def test_l1_timeout_twice_fails_run(conn):
    """FR-005 예외 2행, 기술 명세서 §2-2 T2: 시간 초과 두 번 → 실행 FAILED, "다시 시도"."""
    fake = FakeTransport([LlmTimeout("t"), LlmTimeout("t")], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    assert out.run_status == "FAILED" and out.error_type == "LLM_TIMEOUT"
    assert out.message == "자동 처리 실패. 다시 시도"
    assert fake.count("L1") == 2 and fake.count("L2") == 0


def test_masking_error_fails_without_llm(conn):
    """기술 명세서 §2-2 T1: 가리기 검사 오류면 언어 모델을 부르지 않고 FAILED(VALIDATION)."""
    fake = FakeTransport([l1_reply()], [EMPTY_L2])
    data = ticket_input(conn, "CSV1-000004") | {"inquiry_body": None}
    out = understand_ticket(conn, fake, data)
    assert out.run_status == "FAILED" and out.error_type == "VALIDATION"
    assert fake.prompts == []


def test_low_category_confidence_flag(conn):
    """FR-005 처리 4: 유형 확신도 0.6 미만 → "확신 낮음"."""
    fake = FakeTransport([l1_reply(conf=0.5)], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    assert "확신 낮음" in out.state.sub_tickets[0].flags


def test_prompt_uses_customer_message_and_definitions(conn):
    """CLAUDE.md 규칙 5, 기술 명세서 §3-3: 본문은 <customer_message> 안에만, 유형 정의·긴급도 기준을 넣는다."""
    fake = FakeTransport([l1_reply()], [EMPTY_L2])
    data = ticket_input(conn, "CSV1-000004")
    understand_ticket(conn, fake, data)
    l1 = fake.prompts[0]
    body_start = data["inquiry_body"][:40]
    assert l1.index("<customer_message>") < l1.index(body_start) < l1.index("</customer_message>")
    assert l1.count(body_start) == 1
    assert "릴리스 노트는 제외" in l1 and "단자 과열·변색도 SAFETY" in l1
    assert "{" + "body_masked}" not in l1


# --- FR-007 ---


def test_requests_split_keep_own_urgency(conn):
    """FR-006 처리 4(2순위, add-compound-inquiry): 요청이 둘이면 하위 문의 둘로 나누고 각자의 긴급도를 쓴다.

    1순위는 하위 문의 하나에 가장 높은 긴급도를 모았다. 이제 SAFETY는 그 요청의 하위 문의에 남는다.
    """
    second = {"seq": 2, "category_code": "DEFECT", "category_confidence": 0.9, "evidence_sentences": ["smoke"],
              "urgency_flag": "SAFETY", "urgency_evidence": "smoke", "query_en": "q2"}
    fake = FakeTransport([l1_reply(urgency="DEADLINE", extra=[second])], [EMPTY_L2])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    first, other = out.state.sub_tickets
    assert out.state.multi_yn and (first.seq, other.seq) == (1, 2)
    assert (first.category_code, first.urgency_flag) == ("QUOTE", "DEADLINE")
    assert (other.category_code, other.urgency_flag, other.sub_ticket_id) == ("DEFECT", "SAFETY", "CSV1-000004-2")


def test_same_category_merged(conn):
    """§3-2: 같은 유형 두 번 → 하나로 합치고 근거 문장을 이어 붙인다."""
    dup = {"seq": 2, "category_code": "QUOTE", "category_confidence": 0.8, "evidence_sentences": ["s2"],
           "urgency_flag": "NONE", "urgency_evidence": None, "query_en": "q"}
    fake = FakeTransport([l1_reply(extra=[dup])], [EMPTY_L2])
    sub = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004")).state.sub_tickets[0]
    assert sub.evidence_sentences == ["s1", "s2"]
    assert len(understand_ticket(conn, FakeTransport([l1_reply(extra=[dup])], [EMPTY_L2]),
                                 ticket_input(conn, "CSV1-000004")).state.sub_tickets) == 1


# --- FR-008 (값 정리, 대역) ---


def test_l2_cleaning_rules():
    """FR-008 처리 2·3, 예외 2·3행: 코드북 밖 버림, 펌웨어·날짜·수량·제품 코드 정리, 위치 확인, 값 충돌."""
    body = "Model hmi-xgt-exp60, fw v3.40, qty 2, date 2025-10-28"
    raw = [
        {"field": "product_model", "value_raw": "hmi-xgt-exp60", "value_norm": "hmi-xgt-exp60", "span": [6, 19]},
        {"field": "current_fw", "value_raw": "v3.40", "value_norm": "v3.40", "span": [24, 29]},
        {"field": "quantity", "value_raw": "2", "value_norm": "2", "span": [0, 3]},  # 위치 틀림
        {"field": "required_date", "value_raw": "2025-10-28", "value_norm": "2025-13-40", "span": None},
        {"field": "wish", "value_raw": "x", "value_norm": "x", "span": None},
        {"field": "current_fw", "value_raw": "v3.4a", "value_norm": "v3.4a", "span": None},
    ]
    fields, flags = clean_fields(raw, body, {"product_model", "current_fw", "quantity", "required_date"},
                                 ["HMI-XGT-eXP60"])
    by = {(f.field, f.value_raw): f for f in fields}
    assert ("wish", "x") not in by
    assert by[("product_model", "hmi-xgt-exp60")].value_norm == "HMI-XGT-eXP60"
    assert by[("product_model", "hmi-xgt-exp60")].span == (6, 19)
    assert by[("current_fw", "v3.40")].value_norm == "3.40"
    assert by[("current_fw", "v3.4a")].value_norm is None
    assert by[("quantity", "2")].value_norm == "2" and by[("quantity", "2")].span is None
    assert by[("required_date", "2025-10-28")].value_norm is None
    assert "형식 확인(current_fw)" in flags and "형식 확인(required_date)" in flags
    assert "값 충돌(current_fw)" in flags


def test_normalize_fw_keeps_trailing_zero():
    assert normalize_fw("3.10") == "3.10" and normalize_fw("Ver. 2.31") == "2.31"


def test_l2_fills_product_code_and_copies(conn):
    """FR-008 처리 4·5 (대역): 빈 product_code를 본문 제품 코드로 채우고 error_code·current_fw를 복사한다."""
    data = ticket_input(conn, "CSV1-000004") | {"product_code": None}
    l2 = {"fields": [
        {"field": "product_model", "value_raw": "HMI-XGT-eXP60", "value_norm": "HMI-XGT-eXP60", "span": [0, 0]},
        {"field": "error_code", "value_raw": "E.OC", "value_norm": "E.OC", "span": [0, 0]},
        {"field": "current_fw", "value_raw": "v1.20", "value_norm": "1.20", "span": [0, 0]},
    ]}
    fake = FakeTransport([l1_reply()], [l2])
    sub = understand_ticket(conn, fake, data).state.sub_tickets[0]
    assert sub.product_code == "HMI-XGT-eXP60" and sub.product_family is not None
    assert sub.error_code == "E.OC" and sub.current_fw == "1.20"


def test_l2_unknown_product_is_unconfirmed(conn):
    """FR-008 처리 4: 대조 실패 → "제품 미확정"."""
    data = ticket_input(conn, "CSV1-000004") | {"product_code": None}
    l2 = {"fields": [{"field": "product_model", "value_raw": "ZZ-999", "value_norm": "ZZ-999", "span": None}]}
    sub = understand_ticket(conn, FakeTransport([l1_reply()], [l2]), data).state.sub_tickets[0]
    assert sub.product_code is None and "제품 미확정" in sub.flags


def test_l2_failure_continues(conn):
    """FR-008 예외 4행: 두 번 실패 → 빈 목록 + "추출 실패", 흐름 계속."""
    fake = FakeTransport([l1_reply()], ["not json", "not json"])
    out = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000004"))
    sub = out.state.sub_tickets[0]
    assert out.run_status == "SUCCESS" and sub.provided_fields == [] and "추출 실패" in sub.flags


def test_prompt_files_exist():
    for name in ("l1_understand_v2.md", "l1_category_definitions_v1.md", "l1_urgency_criteria_v1.md",
                 "l2_extract_v1.md"):
        assert (PROMPTS_DIR / name).is_file()


# --- 실제 Gemini 시험 (키가 있을 때만) ---

needs_key = pytest.mark.skipif(not get_settings().gemini_api_key, reason="키 없음: GEMINI_API_KEY가 없어 언어 모델 시험을 건너뜀")


@pytest.fixture(scope="module")
def live(conn):
    transport = default_transport()
    cache: dict[str, object] = {}

    def run(ticket_id: str, **override):
        key = ticket_id + json.dumps(override, sort_keys=True)
        if key not in cache:
            cache[key] = understand_ticket(conn, transport, ticket_input(conn, ticket_id) | override)
        return cache[key]

    return run


@needs_key
@pytest.mark.parametrize("ticket_id, language, body_language", [
    ("CSV1-003578", "it", "en"),  # AC-004-1
    ("CSV1-000008", "ar", "ar"),  # AC-004-2
])
def test_ac_004_1_2_body_language(live, ticket_id, language, body_language):
    out = live(ticket_id)
    assert out.state.language == language and out.state.body_language == body_language


@needs_key
@pytest.mark.parametrize("ticket_id, category", [
    ("CSV1-000017", "DEFECT"), ("CSV1-000007", "DEFECT"), ("CSV1-000004", "QUOTE"),
    ("CSV1-000097", "RETURN"), ("CSV1-000039", "RETURN"), ("CSV1-000008", "FW_UPDATE"),
    ("CSV1-000031", "MANUAL"),  # 기준서 1-1장(릴리스 노트 → FW_UPDATE)과 다름. 결정 기록 C 항목
    ("CSV1-003578", "TECH_SPEC"), ("CSV1-000085", "FW_UPDATE"),
])
def test_ac_005_1_categories(live, ticket_id, category):
    assert live(ticket_id).state.sub_tickets[0].category_code == category


@needs_key
def test_ac_007_1_terminal_overheating_is_safety(live):
    sub = live("CSV1-000017").state.sub_tickets[0]
    assert sub.urgency_flag == "SAFETY" and sub.urgency_evidence


@needs_key
@pytest.mark.parametrize("ticket_id, urgency", [("CSV1-000004", "DEADLINE"), ("CSV1-000031", "NONE")])
def test_ac_007_2_3_urgency(live, ticket_id, urgency):
    assert live(ticket_id).state.sub_tickets[0].urgency_flag == urgency


def _values(sub, field):
    return {pf.value_norm for pf in sub.provided_fields if pf.field == field}


@needs_key
def test_ac_008_1_quote_fields(live):
    sub = live("CSV1-000004").state.sub_tickets[0]
    assert "HMI-XGT-eXP60" in _values(sub, "product_model")
    assert "1" in _values(sub, "quantity")
    assert any("CIF" in (v or "") and "Le Havre" in (v or "") for v in _values(sub, "incoterms"))
    assert "2025-10-28" in _values(sub, "required_date")


@needs_key
def test_ac_008_2_fw_copied(live):
    sub = live("CSV1-000008").state.sub_tickets[0]
    assert sub.current_fw == "3.40"  # DB 저장 때 sub_ticket.fw_version_reported
    assert {"product_model", "tool_version", "logs"} <= {pf.field for pf in sub.provided_fields}


@needs_key
def test_ac_008_3_error_code_copied(live):
    assert live("CSV1-001112").state.sub_tickets[0].error_code == "E.OC"  # sub_ticket.error_code_reported


@needs_key
def test_ac_008_4_fill_empty_product_code(live):
    assert live("CSV1-000004", product_code=None).state.sub_tickets[0].product_code == "HMI-XGT-eXP60"
