"""masking 시나리오 시험 (openspec/changes/add-masking, FR-038).

AC-038-3은 정답지가 적재된 DB를 읽는다. 시험 코드가 정답지 열(final_reply)을 읽는 것은 CLAUDE.md 규칙 6의 시험 예외.
"""

import re

import psycopg
import pytest

from app.config import get_settings
from app.llm.inputs import prepare_llm_input
from app.masking import MASKED_PHONE, MaskingError, mask_text
from app.masking import mask as mask_module


def test_ac_038_1_email_and_international_phone_masked_two_places():
    original = "contact me at kim@example.com or +82-10-1234-5678"
    masked, count = mask_text(original)

    assert "kim@example.com" not in masked
    assert "1234-5678" not in masked
    assert count == 2
    assert original == "contact me at kim@example.com or +82-10-1234-5678"


def test_ac_038_2_date_po_and_serial_untouched():
    masked, count = mask_text("delivery by 2025-10-28, PO 4500123456, S/N LVB-2024-00117")

    assert "2025-10-28" in masked and "4500123456" in masked and "LVB-2024-00117" in masked
    assert count == 0


def test_ac_038_6_mobile_without_separator_masked_po_untouched():
    masked, count = mask_text("call 0501234567, PO 4500123456")

    assert "0501234567" not in masked and MASKED_PHONE in masked
    assert "4500123456" in masked
    assert count == 1


def test_ac_038_6_dotted_phone_is_not_a_firmware_version():
    masked, count = mask_text("fw 2.31 installed, call 010.1234.5678")

    assert "2.31" in masked and "010.1234.5678" not in masked
    assert count == 1


def test_ac_038_4_already_masked_values_untouched():
    text = "COMPANY_4975_0183 user57705@***.masked TS_TRF_AGENT_09"
    masked, count = mask_text(text)

    assert masked == text
    assert count == 0


def test_ac_038_3_training_data_has_nothing_to_mask():
    with psycopg.connect(get_settings().database_url) as conn:
        rows = conn.execute(
            "SELECT ticket_id, inquiry_body, info_request_message, final_reply FROM gold.ticket_gold"
        ).fetchall()
    assert len(rows) == 4000

    total = 0
    by_ticket = {}
    for ticket_id, *texts in rows:
        for text in texts:
            masked, count = mask_text(text or "")
            total += count
            by_ticket.setdefault(ticket_id, []).append(masked)

    assert total == 0
    assert any("IEC 62271-200" in t for t in by_ticket["CSV1-000341"])
    assert any("IEC 62271-100" in t for t in by_ticket["CSV1-002841"])


def test_ac_038_5_gate_output_has_no_raw_domain_or_phone():
    result = prepare_llm_input({"body": "reply to lee@customer.co.kr, tel 010-9876-5432", "language": "en"})

    for value in result.fields.values():
        for domain in re.findall(r"@([A-Za-z0-9.*-]+)", value):
            assert domain == "***.masked"
        assert "9876-5432" not in value
    assert result.mask_count == 2
    assert result.field_names == ["body", "language"]


def test_ac_038_5_contact_field_is_rejected():
    with pytest.raises(MaskingError) as excinfo:
        prepare_llm_input({"body": "hello", "contact_email": "lee@customer.co.kr"})

    assert excinfo.value.kind == "VALIDATION"


def test_masking_rule_failure_becomes_validation_error(monkeypatch):
    def broken(_text):
        raise RuntimeError("regex broke")

    monkeypatch.setattr(mask_module, "_mask", broken)
    with pytest.raises(MaskingError) as excinfo:
        prepare_llm_input({"body": "anything"})

    assert excinfo.value.kind == "VALIDATION"
