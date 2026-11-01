"""가린 값(**MASKED**)을 "고객이 준 항목"으로 센다 (2026-11-01 결정, FR-008 제공 항목·AC-008-5 채점).

운영진 데이터는 일련번호·주문서 번호 값을 **MASKED**로 가려 두었고, 정답(provided_info)은 이를 "줬다"로 센다.
L2(언어 모델)는 값이 안 보여 빼기 쉬우므로, 코드가 "항목 이름: **MASKED**"를 찾아 제공 항목에 더한다(llm/extract.py).
항목 이름이 없는 가린 값(채팅의 "CONT-MC-32a, **MASKED**")은 어느 항목인지 정할 수 없어 L2 판단에 맡긴다.
"""

from __future__ import annotations

from app.llm.extract import MASKED, add_masked, load_masked_labels, masked_fields
from app.pipeline.state import ProvidedField
from app.pipeline.understand import understand_ticket
from app.rules.required_info import check_required_info
from tests.acceptance.test_inquiry_understanding import FakeTransport, l1_reply, ticket_input

INFO = [("product_model", "Product model / ordering code"), ("serial_no", "Serial number (nameplate)"),
        ("purchase_doc", "PO or invoice number"), ("po_number", "PO number"), ("error_code", "Error code or symptom displayed")]


def fields(body: str) -> list[str]:
    return [pf.field for pf in masked_fields(body, INFO)]


def test_labeled_masked_values_are_provided():
    """메일 양식의 "항목 이름: **MASKED**" → 그 항목을 받음. 위치는 **MASKED** 자리."""
    body = "Details:\n- Serial number (nameplate): **MASKED**\n- PO or invoice number: **MASKED**\n- Quantity: 2"
    found = masked_fields(body, INFO)
    assert [pf.field for pf in found] == ["serial_no", "purchase_doc"]
    for pf in found:
        assert pf.value_raw == pf.value_norm == MASKED and body[pf.span[0]:pf.span[1]] == MASKED


def test_call_note_and_other_languages():
    """통화 메모의 "이름=**MASKED**", 다국어 이름(config/masked_field_labels.yaml), 전각 콜론도 센다."""
    assert fields("[Call note] … Provided: Serial number (nameplate)=**MASKED**; PO number=**MASKED**.") == [
        "serial_no", "po_number"]
    assert fields("- Número de serie (placa de características): **MASKED**") == ["serial_no"]
    assert fields("- 序列号（铭牌）：**MASKED**") == ["serial_no"]
    assert fields("- Sipariş (PO) numarası: **MASKED**") == ["po_number"]


def test_longer_label_is_not_confused_with_shorter_one():
    """"Numéro de commande ou de facture"(주문서·송장)는 "Numéro de commande"(주문 번호)로 세지 않는다."""
    assert fields("- Numéro de commande ou de facture: **MASKED**") == ["purchase_doc"]
    assert fields("- Numéro de commande: **MASKED**") == ["po_number"]


def test_unlabeled_masked_is_not_guessed():
    """항목 이름이 없는 가린 값과 가린 값이 없는 본문은 더하지 않는다."""
    assert fields("installing Magnetic Contactor 32A now\n\nCONT-MC-32a, **MASKED**") == []
    assert fields("- Serial number (nameplate): SN-1234") == []


def test_l2_value_is_kept():
    """L2가 이미 뽑은 항목은 그대로 두고, 빠뜨린 가린 항목만 더한다."""
    l2 = [ProvidedField(field="serial_no", value_raw="SN-1", value_norm="SN-1")]
    masked = masked_fields("- Serial number (nameplate): **MASKED**\n- PO number: **MASKED**", INFO)
    merged = add_masked(l2, masked)
    assert [(pf.field, pf.value_raw) for pf in merged] == [("serial_no", "SN-1"), ("po_number", MASKED)]


def test_label_file_covers_operator_languages():
    """설정 파일에 세 항목의 다국어 이름이 있다(운영진 데이터·팀 정답지에 나온 이름)."""
    table = load_masked_labels()
    assert set(table) == {"serial_no", "purchase_doc", "po_number"}
    assert "Serial number (nameplate)" in table["serial_no"] and len(table["serial_no"]) >= 15


def test_masked_serial_is_not_blocking(conn):
    """CSV1-000007(PLC 고장, 본문 "Serial number (nameplate): **MASKED**"): L2가 일련번호를 빠뜨려도
    제공 항목에 serial_no가 들어가고, 막는 항목에서 빠진다(운영진 값: 막는 항목 없음)."""
    l2 = {"fields": [{"field": "product_model", "value_raw": "PLC-XGB-XBM-DR16S", "value_norm": "PLC-XGB-XBM-DR16S",
                      "span": None}]}
    out = understand_ticket(conn, FakeTransport([l1_reply("DEFECT", lang="en")], [l2]), ticket_input(conn, "CSV1-000007"))
    sub = out.state.sub_tickets[0]
    names = {pf.field for pf in sub.provided_fields}
    assert {"product_model", "serial_no"} <= names
    required = check_required_info(conn, sub.product_family, "DEFECT", names)
    assert "serial_no" not in required.missing_blocking_info


def test_masked_kept_when_l2_fails(conn):
    """L2가 두 번 실패해도(FR-008 예외 4행) 가린 항목은 받은 것으로 둔다."""
    fake = FakeTransport([l1_reply("DEFECT", lang="en")], ["not json", "not json"])
    sub = understand_ticket(conn, fake, ticket_input(conn, "CSV1-000007")).state.sub_tickets[0]
    assert [pf.field for pf in sub.provided_fields] == ["serial_no"] and "추출 실패" in sub.flags
