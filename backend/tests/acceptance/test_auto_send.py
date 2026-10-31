"""자동 발송 실행·사후 검수·설정 API (변경 add-auto-send 결정 3~5). 대역 언어 모델로 접수하고(롤백) 판정이 통과하면 SYSTEM이 AI_AUTO로 보낸다.
설정을 저장하지 않으면 시험에서는 꺼져 있다(tests/conftest.py)."""

from __future__ import annotations

from tests.acceptance.test_drafts import GLOSS_OK, L2_QUOTE, QUOTE_BODY, field, l1
from tests.acceptance.test_ticket_detail import api, index, intake  # noqa: F401  (api 픽스처)
from app.status.autosend import auto_message_id, evaluate, load_rules, save_rules

ANSWER = {"body": "The latest firmware release notes for your HMI-XGT-iXP90 are on our support site.", "citations": [], "numbers_used": []}
GLOSS = {"gloss": "HMI-XGT-iXP90의 최신 펌웨어 릴리스 노트는 지원 사이트에 있습니다."}
# 정답지 CSV1-000031(MANUAL, P4)이 요구하는 필수 정보(제품 모델·문서 종류)를 채워, 근거 문서가 찾아지고 막는 정보 누락이 없게 한다
L2_MANUAL = {"fields": [field("product_model", "HMI-XGT-iXP90"), field("document_type", "firmware release notes")]}
QUERY = "firmware release notes HMI-XGT-iXP90 XGT iXP90"


def turn_on(conn, **over):
    save_rules(conn, {"enabled": True, "cats": {"MANUAL": True, "TECH_SPEC": True, "FW_UPDATE": True, "COMPLIANCE": False},
                      "channels": {"EMAIL": True, "WEB_FORM": True, "PHONE": True, "CHAT": True, "PARTNER_PORTAL": True}, **over}, "tester")


def manual(api, **replies):
    """MANUAL(매뉴얼) 문의 한 건을 접수한다. 정답지 CSV1-000031은 MANUAL이다."""
    base = {"L1": [l1("MANUAL", "en", "NONE", QUERY)], "L2": [L2_MANUAL], "L4": [ANSWER], "L7": [GLOSS]}
    return intake(api, "CSV1-000031", **{**base, **replies})


def sub_of(detail):
    return detail["sub_tickets"][0]


def test_eligible_inquiry_is_sent_automatically(api):
    """판정이 통과하면 상담원 승인 없이 SYSTEM이 AI_AUTO 이름으로 보내고, 같은 전이(FINAL_REPLY_SENT)로 RESOLVED가 되며 이력에 남는다."""
    turn_on(api[2])
    detail = manual(api)
    sub = sub_of(detail)
    assert sub["sub_ticket"]["status"] == "RESOLVED", [d["message_status"] for d in sub["drafts"]]
    conn = api[2]
    sent = conn.execute("""SELECT sender, sent_by_name, message_type, message_status, edited_yn, override_check FROM svc.ticket_message
                            WHERE sub_ticket_id = %s AND message_status = 'SENT'""", (sub["sub_ticket"]["sub_ticket_id"],)).fetchall()
    assert sent == [("SYSTEM", "AI_AUTO", "FINAL_REPLY", "SENT", False, False)]
    last = conn.execute("""SELECT event_kind, changed_by FROM svc.ticket_status_history WHERE sub_ticket_id = %s ORDER BY history_id DESC LIMIT 1""",
                        (sub["sub_ticket"]["sub_ticket_id"],)).fetchone()
    assert last == ("FINAL_REPLY_SENT", "AI_AUTO")
    assert auto_message_id(conn, sub["sub_ticket"]["sub_ticket_id"]) is not None


def test_not_sent_when_switch_is_off(api):
    """꺼져 있으면 같은 문의도 초안만 남고 상담원이 확인한다."""
    save_rules(api[2], {"enabled": False}, "tester")
    sub = sub_of(manual(api))
    assert sub["sub_ticket"]["status"] == "IN_PROGRESS" and [d["message_status"] for d in sub["drafts"]] == ["DRAFT"]
    assert api[2].execute("SELECT count(*) FROM svc.ticket_message WHERE sub_ticket_id = %s AND sender = 'SYSTEM' AND message_status = 'SENT'",
                          (sub["sub_ticket"]["sub_ticket_id"],)).fetchone()[0] == 0


def test_high_risk_and_failed_checks_are_never_sent(api):
    """항상 사람 확인 유형(견적), 검증이 지적한 초안은 켜져 있어도 보내지 않고 막는 사유를 설명한다."""
    turn_on(api[2])
    quote = intake(api, "CSV1-000004", L1=[l1("QUOTE", "fr", "NONE", "price")], L2=[L2_QUOTE],
                   L4=[{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], L7=[GLOSS_OK])
    qs = sub_of(quote)["sub_ticket"]
    assert qs["status"] == "IN_PROGRESS" and any("고위험 유형" in b for b in evaluate(api[2], qs["sub_ticket_id"])["blocked"])
    flagged = manual(api, L8=[{"findings": [{"kind": "OFF_TOPIC", "quote": "latest firmware release notes", "reason": "질문과 다름"}]}])
    fs = sub_of(flagged)["sub_ticket"]
    assert fs["status"] == "IN_PROGRESS" and any("확인이 필요한 것" in b or "검증" in b for b in evaluate(api[2], fs["sub_ticket_id"])["blocked"])


def test_auto_send_failure_does_not_fail_processing(api, monkeypatch):
    """자동 발송 중 오류가 나도 처리는 성공하고 초안은 남는다(상담원이 확인)."""
    import app.api.tickets as tickets

    def boom(conn, ticket_id):
        raise RuntimeError("자동 발송 오류 시험")
    monkeypatch.setattr(tickets, "auto_send_ticket", boom)
    turn_on(api[2])
    detail = manual(api)
    assert detail["run"]["status"] == "SUCCESS" and [d["message_status"] for d in sub_of(detail)["drafts"]] == ["DRAFT"]


def test_post_review_once_and_only_for_auto_sent(api):
    """사후 검수는 자동 발송된 문의에 한 번만. 상담원 미선택 400, 없는 문의 404, 자동 발송이 아니면 409, 두 번째는 409."""
    turn_on(api[2])
    sid = sub_of(manual(api))["sub_ticket"]["sub_ticket_id"]
    client = api[0]
    assert client.post(f"/sub-tickets/{sid}/auto-review").status_code == 400
    assert client.post("/sub-tickets/CSV1-999999-1/auto-review", headers={"X-Agent-Id": "leo"}).status_code == 404
    ok = client.post(f"/sub-tickets/{sid}/auto-review", headers={"X-Agent-Id": "leo"})
    assert ok.status_code == 200 and ok.json()["reviewed_by"] == "leo" and ok.json()["sub_ticket_id"] == sid
    again = client.post(f"/sub-tickets/{sid}/auto-review", headers={"X-Agent-Id": "leo"})
    assert again.status_code == 409 and "이미 검수" in again.json()["detail"]
    save_rules(api[2], {"enabled": False}, "tester")
    other = sub_of(manual(api))["sub_ticket"]["sub_ticket_id"]  # 자동 발송이 아닌 문의
    assert client.post(f"/sub-tickets/{other}/auto-review", headers={"X-Agent-Id": "leo"}).status_code == 409


def test_rules_api_defaults_validation_and_stats(api):
    """설정은 저장한 값을 돌려주고, 항상 사람 확인 유형을 켜려 하면 400이며, 통계가 자동 발송 건수를 센다."""
    client = api[0]
    first = client.get("/auto-rules").json()
    assert first["enabled"] is False and first["cats"]["MANUAL"] is True and "DEFECT" in first["always_human"]  # 시험에서는 기본이 꺼짐
    assert client.put("/auto-rules", json={"enabled": True, "cats": {"DEFECT": True}}, headers={"X-Agent-Id": "leo"}).status_code == 400
    assert client.put("/auto-rules", json={"enabled": True}).status_code == 400  # 상담원 미선택
    saved = client.put("/auto-rules", json={"enabled": True, "cats": {"MANUAL": False}, "channels": {"PHONE": True}}, headers={"X-Agent-Id": "leo"}).json()
    assert saved["enabled"] is True and saved["cats"]["MANUAL"] is False and saved["channels"]["PHONE"] is True
    assert client.get("/auto-rules").json()["cats"]["MANUAL"] is False
    assert load_rules(api[2])["cats"]["MANUAL"] is False
    turn_on(api[2])
    manual(api)
    stats = client.get("/auto-rules").json()["stats"]
    assert stats["auto_total"] >= 1 and stats["auto_pending"] >= 1 and stats["total"] >= stats["auto_total"]
