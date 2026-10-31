"""한국어 한 줄 요약 (변경 add-summary-ko). L1 호출이 하위 문의마다 summary_ko를 주면 접수 때 한 번 저장하고,
접수함·상세가 그대로 보인다. 모델은 항상 같은 글을 주지 않으므로 값을 DB에 저장해 화면을 열 때마다 바뀌지 않게 한다."""

from __future__ import annotations

from app.llm.understand import SUMMARY_MAX, clean_summary
from tests.acceptance.test_drafts import L2_DEFECT, GLOSS_OK
from tests.acceptance.test_ticket_detail import api, defect_l1, index, intake, INFO_REPLY  # noqa: F401  (api 픽스처)


def test_clean_summary():
    """한 줄로 다듬는다: 공백 정리, 너무 길면 자르고 …, 문자열이 아니거나 비면 None."""
    assert clean_summary("  ACB-AS-2000  단자\n과열 접수 ") == "ACB-AS-2000 단자 과열 접수"
    assert clean_summary("가" * 300).endswith("…") and len(clean_summary("가" * 300)) == SUMMARY_MAX
    assert clean_summary("") is None and clean_summary("   ") is None and clean_summary(None) is None and clean_summary(12) is None


def _with_summary(text):
    reply = defect_l1()
    if text is not None:
        reply["sub_tickets"][0]["summary_ko"] = text
    return reply


def test_summary_saved_and_shown(api):
    """모델이 준 요약이 DB에 저장되어 접수함 줄과 상세에 같은 값으로 나온다."""
    detail = intake(api, "CSV1-000017", L1=[_with_summary("ACB-AS-2000 단자 과열·변색 고장 접수")], L2=[L2_DEFECT],
                    L3=[INFO_REPLY], L7=[{"gloss": "명판의 제조번호를 보내 주세요."}])
    sub = detail["sub_tickets"][0]
    assert sub["sub_ticket"]["summary_ko"] == "ACB-AS-2000 단자 과열·변색 고장 접수"
    row = api[0].get("/tickets", params={"dept": sub["sub_ticket"]["assigned_dept"], "q": detail["ticket"]["ticket_id"]}).json()["rows"][0]
    assert row["summary_ko"] == sub["sub_ticket"]["summary_ko"]


def test_missing_summary_does_not_fail_processing(api):
    """모델이 요약을 빼먹어도 처리는 성공하고 요약은 비어 있다(화면은 문의 제목으로 대신한다)."""
    detail = intake(api, "CSV1-000017", L1=[_with_summary(None)], L2=[L2_DEFECT], L3=[INFO_REPLY],
                    L7=[{"gloss": "명판의 제조번호를 보내 주세요."}])
    assert detail["run"]["status"] == "SUCCESS" and detail["sub_tickets"][0]["sub_ticket"]["summary_ko"] is None
