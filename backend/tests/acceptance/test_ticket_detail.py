"""티켓 상세 최소판 완료 기준 (FR-024, FR-031, FR-039, FR-049, 변경 add-ticket-detail-minimal).

API를 TestClient로 부른다. 언어 모델은 대역 Transport, DB 쓰기는 바깥 트랜잭션을 롤백해 남기지 않는다.
"""

from __future__ import annotations

from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clients, get_conn, get_connect
from app.llm.client import LlmTimeout
from app.main import app
from jobs import run_tickets
from tests.acceptance.test_drafts import (  # noqa: F401  (index 픽스처를 함께 쓴다)
    GLOSS_OK, L2_DEFECT, L2_QUOTE, QUOTE_BODY, FakeTransport, WordCountEmbedder, field, index, l1,
)

INFO_BODY = "Please send the Serial number (nameplate) of the breaker."
INFO_REPLY = {"body": INFO_BODY, "requested_fields": ["serial_no"]}


class FakeClients:
    def __init__(self):
        self.fake: FakeTransport | None = None

    def transport(self):
        return self.fake

    def embedder(self):
        return WordCountEmbedder()


@pytest.fixture
def api(conn, index):
    clients = FakeClients()

    def shared_conn():
        yield conn

    app.dependency_overrides[get_conn] = shared_conn
    app.dependency_overrides[get_connect] = lambda: (lambda: nullcontext(conn))
    app.dependency_overrides[get_clients] = lambda: clients
    with conn.transaction(force_rollback=True):
        yield TestClient(app), clients, conn
    app.dependency_overrides.clear()


def gold_input(conn, ticket_id):
    """jobs/run_tickets.py와 같은 입력(gold.v_inputs만 읽음)."""
    return run_tickets.payload(run_tickets.read_inputs(conn, [ticket_id])[0])


def intake(api, source_id, body_extra="", **replies):
    client, clients, conn = api
    clients.fake = FakeTransport(**replies)
    data = gold_input(conn, source_id)
    data["inquiry_body"] += body_extra
    res = client.post("/tickets", json=data)
    assert res.status_code == 201, res.text
    detail = client.get(f"/tickets/{res.json()['ticket_id']}").json()
    assert not detail["processing"]
    return detail


def defect_l1(urgency="SITE_DOWN"):
    reply = l1("DEFECT", "en", urgency, "breaker trips")
    reply["sub_tickets"][0]["urgency_evidence"] = "plant stopped"
    return reply


def info_request(api):
    return intake(api, "CSV1-000017", L1=[defect_l1()], L2=[L2_DEFECT], L3=[INFO_REPLY], L7=[{"gloss": "명판의 제조번호를 보내 주세요."}])


def quote(api, l4=None, l7=None, l8=None, extra=""):
    replies = {"L1": [l1("QUOTE", "fr", "NONE", "price quotation")], "L2": [L2_QUOTE],
               "L4": l4 or [{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], "L7": l7 or [GLOSS_OK]}
    if l8:
        replies["L8"] = l8
    return intake(api, "CSV1-000004", extra, **replies)


def rows(detail):
    return {r["id"]: r for r in detail["sub_tickets"][0]["evidence_rows"]}


def only_draft(detail):
    (draft,) = detail["sub_tickets"][0]["drafts"]
    return draft


def send(api, draft, body=None, override=False, agent="TS_LV_AGENT_09"):
    client = api[0]
    return client.post(f"/messages/{draft['message_id']}/send", headers={"X-Agent-Id": agent} if agent else {},
                       json={"final_body": draft["body"] if body is None else body, "override_check": override})


# --- 접수와 저장 ---


def test_ac_015_4_draft_only_status_unchanged(api):
    """AC-015-4: 초안은 DRAFT 행으로만 있고, 초안을 만든다고 상태가 바뀌지 않는다.

    처리 흐름이 끝나면 T6이 NEW → IN_PROGRESS로 바꾸므로 발송 전 상태는 IN_PROGRESS다(add-status-and-sla, C-51).
    """
    detail = info_request(api)
    draft = only_draft(detail)
    assert draft["message_type"] == "INFO_REQUEST" and draft["message_status"] == "DRAFT" and draft["sent"] is None
    assert detail["sub_tickets"][0]["sub_ticket"]["status"] == "IN_PROGRESS"
    assert [h["event_kind"] for h in detail["sub_tickets"][0]["history"]] == ["INTAKE", "PIPELINE_DONE"]
    assert detail["ticket"]["source_ticket_id"] == "CSV1-000017" and detail["ticket"]["ticket_id"] != "CSV1-000017"


def test_ac_038_1_raw_stored_log_masked(api):
    """AC-038-1: INQUIRY는 원문·mask_count 2, 실행 기록에는 이메일·전화번호가 없다."""
    extra = "\ncontact me at kim@example.com or +82-10-1234-5678"
    l1_reply = l1("QUOTE", "fr", "NONE", "price")
    l1_reply["sub_tickets"][0]["evidence_sentences"] = ["contact me at kim@example.com or +82-10-1234-5678"]
    detail = intake(api, "CSV1-000004", extra, L1=[l1_reply], L2=[L2_QUOTE],
                    L4=[{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], L7=[GLOSS_OK])
    conn = api[2]
    tid = detail["ticket"]["ticket_id"]
    body, mask_count = conn.execute("""SELECT body, mask_count FROM svc.ticket_message
                                       WHERE ticket_id = %s AND message_type = 'INQUIRY'""", (tid,)).fetchone()
    assert body.endswith(extra) and mask_count == 2
    logs = conn.execute("""SELECT string_agg(coalesce(st.input_json::text, '') || coalesce(st.output_json::text, ''), ' ')
                             FROM svc.agent_step st JOIN svc.agent_run r USING (run_id) WHERE r.ticket_id = %s""",
                        (tid,)).fetchone()[0]
    assert "kim@example.com" not in logs and "1234-5678" not in logs and "evidence_sentences" in logs


def test_unknown_customer_rejected(api):
    """FR-010 D25: 미등록 고객은 접수 거부(400)."""
    client, _, conn = api
    data = gold_input(conn, "CSV1-000004") | {"customer_id": "NO-SUCH"}
    res = client.post("/tickets", json=data)
    assert res.status_code == 400 and res.json()["detail"] == "등록되지 않은 고객"
    assert client.get("/tickets/NO-SUCH").status_code == 404


# --- FR-024 근거 영역과 검토 표시 ---


def test_ac_024_1_evidence_rows(api):
    """AC-024-1: 긴급도 근거, PR-02 판정 과정, RT-LV_BREAKER-DEFECT와 이관 조건, serial_no 막는 항목, SLA, 근거 절 줄."""
    r = rows(info_request(api))
    assert r["C-02"]["result"] == "SITE_DOWN" and r["C-02"]["evidence"] == ["plant stopped"]
    assert r["C-03"]["result"] == "P1 (PR-02)" and "PR-01 ✗" in r["C-03"]["evidence"][0] and "PR-02 ✓" in r["C-03"]["evidence"][0]
    assert r["C-03"]["why"]["rule"]["rule_id"] == "PR-02"
    assert r["C-04"]["evidence"][0] == "RT-LV_BREAKER-DEFECT" and any(e.startswith("이관 조건") for e in r["C-04"]["evidence"])
    serial = next(i for i in r["C-07"]["items"] if i["field"] == "serial_no")
    assert serial["state"] == "blocking" and serial["label"] == "Serial number (nameplate)"
    assert r["C-06"]["evidence"] == ["SLA-DEFECT-PLATINUM-P1"]
    assert r["M-C-02"]["result"] == "없음(정보 요청 중)"


def test_ac_024_2_citation_opens_section(api):
    """AC-024-2: (DS-CONT-MC-32a §2.1) 인용 → 그 절 본문."""
    res = api[0].get("/chunks/DS-CONT-MC-32a§2.1")
    assert res.status_code == 200 and res.json()["section_no"] == "2.1" and res.json()["text"].strip()
    assert api[0].get("/chunks/DS-NONE§9").json()["detail"] == "본문 열기 실패"


def test_ac_024_3_classification_failed(api):
    """AC-024-3: 분류 실패 → 유형 줄 "없음(분류 실패)", 나머지 줄은 정상."""
    detail = intake(api, "CSV1-000004", L1=["not json"], L2=[{"fields": []}], L7=[GLOSS_OK])
    r = rows(detail)
    assert r["C-01"]["result"] == "없음(분류 실패)"
    assert r["C-02"]["result"] == "NONE" and r["M-C-01"]["result"]
    assert {c["check_type"] for c in detail["sub_tickets"][0]["checks"]} >= {"LOW_CONFIDENCE"}


def test_ac_024_4_safety_mark(api):
    """AC-024-4: 긴급도 SAFETY(CSV1-000202) → ④ "확인 필요: 안전 문의", 표시 5개."""
    reply = l1("DEFECT", "ar", "SAFETY", "battery smoke")
    detail = intake(api, "CSV1-000202", L1=[reply], L2=[{"fields": [field("product_model", "ESS-BMS-V3")]}],
                    L3=[{"body": "يرجى إرسال Serial number (nameplate).", "requested_fields": ["serial_no"]}],
                    L7=[{"gloss": "Serial number (nameplate)를 보내 주세요."}])
    marks = only_draft(detail)["review_marks"]["marks"]
    assert len(marks) == 5 and marks[3]["state"] == "CHECK" and marks[3]["text"] == "④ 확인 필요: 안전 문의"


# --- FR-031 승인·발송 ---


def test_ac_031_1_send_info_request(api):
    """AC-031-1: 정보 요청 발송 → INFO_REQUEST SENT 행, 상태 WAITING_CUSTOMER, 1차 응답 시각 = 발송 시각."""
    draft = only_draft(info_request(api))
    res = send(api, draft)
    assert res.status_code == 200, res.text
    conn = api[2]
    sent = conn.execute("""SELECT message_type, sender, sent_by_name, sent_at_utc FROM svc.ticket_message
                            WHERE message_id = %s""", (res.json()["sent_message_id"],)).fetchone()
    assert sent[:3] == ("INFO_REQUEST", "AGENT", "TS_LV_AGENT_09")
    first, sent_flag, status = conn.execute(
        "SELECT first_response_at_utc, info_request_sent, status FROM svc.sub_ticket WHERE sub_ticket_id = %s",
        (f"{draft_ticket(conn, draft)}-1",)).fetchone()
    assert first == sent[3] and sent_flag and status == "WAITING_CUSTOMER"


def test_info_request_label_removed_needs_confirmation(api):
    """FR-031 처리 2·에이전트 설계서 6-1: 정보 요청에서 막는 항목 라벨을 지우면 ①이 걸리고 발송 때 확인을 받는다."""
    draft = only_draft(info_request(api))
    marks = draft["review_marks"]["marks"]
    assert marks[0]["passed"], marks[0]
    label = draft["check"]["detail"]["missing_labels"] == [] and api[2].execute(
        "SELECT label FROM ref.info_field WHERE field = 'serial_no'").fetchone()[0]
    body = draft["body"].replace(label, "")
    assert api[0].put(f"/messages/{draft['message_id']}", json={"body": body}).status_code == 200
    detail = api[0].get(f"/tickets/{draft_ticket(api[2], draft)}").json()
    assert only_draft(detail)["review_marks"]["marks"][0]["text"] == "① 요청 항목 빠짐"
    res = send(api, only_draft(detail), body=body)
    assert res.status_code == 409 and label in res.json()["issues"][0]["items"]


def draft_ticket(conn, draft):
    return conn.execute("SELECT ticket_id FROM svc.ticket_message WHERE message_id = %s", (draft["message_id"],)).fetchone()[0]


def test_ac_031_2_and_039_2_edited_reply(api):
    """AC-031-2: 한 문장을 고쳐 발송 → edited_yn Y, 원본 초안은 글자 그대로 APPROVED. AC-039-2: 발송 본문에 대역 없음."""
    draft = only_draft(quote(api))
    edited = draft["body"].replace("Un commercial vous enverra un devis précis.", "Notre équipe commerciale vous enverra un devis précis.")
    assert edited != draft["body"]
    res = send(api, draft, edited)
    assert res.status_code == 200, res.text
    conn = api[2]
    body, edited_yn = conn.execute("SELECT body, edited_yn FROM svc.ticket_message WHERE message_id = %s",
                                   (res.json()["sent_message_id"],)).fetchone()
    original, status = conn.execute("SELECT body, message_status FROM svc.ticket_message WHERE message_id = %s",
                                    (draft["message_id"],)).fetchone()
    assert edited_yn is True and original == draft["body"] and status == "APPROVED"
    sub_status, resolved = conn.execute("SELECT status, resolved_at_utc FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                        (f"{draft_ticket(conn, draft)}-1",)).fetchone()
    assert sub_status == "RESOLVED" and resolved is not None  # AC-031-2 "상태 RESOLVED"
    assert body == edited and "단가" not in body and "유효기간" not in body


def test_ac_031_3_number_outside_lookups(api):
    """AC-031-3: 조회값에 없는 숫자 → 409 "근거 밖", 그래도 발송하면 발송되고 override_check 기록."""
    draft = only_draft(quote(api))
    body = draft["body"] + " Remise de 15 %."
    res = send(api, draft, body)
    assert res.status_code == 409 and res.json()["issues"][0]["kind"] == "DRAFT_CHECK"
    assert res.json()["issues"][0]["items"] == ["15"]
    res = send(api, draft, body, override=True)
    assert res.status_code == 200 and res.json()["override_check"] is True
    (override,) = api[2].execute("SELECT override_check FROM svc.ticket_message WHERE message_id = %s",
                                 (res.json()["sent_message_id"],)).fetchone()
    assert override is True


def test_ac_031_5_send_twice(api):
    """AC-031-5: 같은 초안 두 번 승인 → 두 번째 거부, SENT 1건."""
    draft = only_draft(info_request(api))
    assert send(api, draft).status_code == 200
    second = send(api, draft)
    assert second.status_code == 409 and second.json()["detail"] == "이미 발송된 초안"
    (n,) = api[2].execute("SELECT count(*) FROM svc.ticket_message WHERE source_draft_id = %s AND message_status = 'SENT'",
                          (draft["message_id"],)).fetchone()
    assert n == 1


def test_send_needs_agent_and_body(api):
    """FR-031 처리 1, 화면 정의서 P7: 상담원 ID·본문이 없으면 거부."""
    draft = only_draft(info_request(api))
    assert send(api, draft, agent=None).json()["detail"] == "상담원 ID를 입력하세요"
    assert send(api, draft, "  ").json()["detail"] == "내용을 입력하세요"


# --- FR-039 임시 저장과 대역, FR-049 ⑤ ---


def test_ac_039_4_save_makes_new_gloss_and_stale(api):
    """AC-039-4: 임시 저장 → 고친 문장이 반영된 새 대역. ⑤는 STALE, [다시 검증]하면 PASSED."""
    new_gloss = {"gloss": GLOSS_OK["gloss"].replace("영업 담당이", "우리 영업팀이")}
    detail = quote(api, l7=[GLOSS_OK, new_gloss])
    draft = only_draft(detail)
    client, clients, _ = api
    edited = draft["body"].replace("Un commercial", "Notre équipe commerciale")
    res = client.put(f"/messages/{draft['message_id']}", json={"body": edited})
    assert res.status_code == 200 and res.json()["gloss"] is True
    assert clients.fake.count("L8") == 1  # 임시 저장은 검증을 부르지 않는다
    after = only_draft(client.get(f"/tickets/{detail['ticket']['ticket_id']}").json())
    assert after["body"] == edited and "우리 영업팀이" in after["gloss"]["body"]
    assert after["review_marks"]["marks"][4]["state"] == "STALE"
    res = client.post(f"/messages/{draft['message_id']}/verify")
    assert res.status_code == 200 and res.json()["state"] == "PASSED"
    final = only_draft(client.get(f"/tickets/{detail['ticket']['ticket_id']}").json())
    assert final["review_marks"]["marks"][4]["state"] == "PASSED"


def test_ac_049_2_all_five_pass(api):
    """AC-049-2: 코드 검사와 검증을 모두 통과(나머지 표시도 통과) → "검사 5개 통과"."""
    detail = quote(api)
    assert detail["sub_tickets"][0]["checks"] == []
    assert only_draft(detail)["review_marks"]["summary"] == "검사 5개 통과"


def test_ac_049_3_found_needs_confirmation(api):
    """AC-049-3: ⑤가 걸린 초안 → 확인 요구, 그래도 발송하면 발송되고 기록."""
    discount = "Nous vous accordons une remise de 30 % sur cette commande."
    body = QUOTE_BODY + " " + discount
    finding = {"findings": [{"kind": "PROMISE", "quote": discount, "reason": "근거에 없는 할인"}]}
    draft = only_draft(quote(api, l4=[{"body": body, "citations": [], "numbers_used": []}], l8=[finding]))
    assert draft["review_marks"]["marks"][4]["state"] == "FOUND"
    res = send(api, draft)
    assert res.status_code == 409 and [i["kind"] for i in res.json()["issues"]] == ["VERIFY"]
    res = send(api, draft, override=True)
    assert res.status_code == 200 and res.json()["override_check"] is True


def test_ac_049_4_verify_failed(api):
    """AC-049-4: 검증 두 번 시간 초과 → ⑤ 검증 못 함(실패), ①~④는 보이고 확인 없이 승인, 실행 기록에 LLM_TIMEOUT."""
    detail = quote(api, l8=[LlmTimeout("t")])
    draft = only_draft(detail)
    marks = draft["review_marks"]["marks"]
    assert marks[4]["state"] == "FAILED" and marks[4]["text"] == "⑤ 검증 못 함(실패)"
    assert all(m["passed"] for m in marks[:4])
    (kind,) = api[2].execute("""SELECT st.error_kind FROM svc.agent_step st JOIN svc.agent_run r USING (run_id)
                                 WHERE r.ticket_id = %s AND st.step_name = 'Q14'""",
                             (detail["ticket"]["ticket_id"],)).fetchone()
    assert kind == "LLM_TIMEOUT"
    res = send(api, draft)
    assert res.status_code == 200 and res.json()["notes"] == ["⑤ 검증 못 함 — 검증 없이 보냅니다"]
