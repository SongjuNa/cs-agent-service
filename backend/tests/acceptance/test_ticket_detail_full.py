"""티켓 상세 전체판 완료 기준 (FR-030, 변경 add-ticket-detail-full).

API를 TestClient로 부른다. 언어 모델은 대역 Transport, DB 쓰기는 바깥 트랜잭션을 롤백해 남기지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.status.transitions import transition
from tests.acceptance.test_compound_inquiry import compound, sub
from tests.acceptance.test_drafts import GLOSS_OK, QUOTE_BODY, FakeTransport
from tests.acceptance.test_ticket_detail import (  # noqa: F401  (api·index 픽스처)
    INFO_REPLY, api, index, info_request, quote, rows, send,
)
from app.rules.lookup import lookup_customer, lookup_product
from app.rules.priority import decide_priority
from app.rules.required_info import check_required_info
from app.rules.routing import assign_dept
from app.rules.sla import find_sla_target

AGENT = {"X-Agent-Id": "TS_LV_AGENT_09"}
ANSWER = {"L3": [INFO_REPLY], "L4": [{"body": "Please check the manual (MAN-ACB §1).", "citations": [], "numbers_used": []}],
          "L7": [{"gloss": "설명서를 확인해 주세요."}]}


def detail_of(api, tid):
    return api[0].get(f"/tickets/{tid}").json()


def first(detail):
    return detail["sub_tickets"][0]


def close(conn, sub_id):
    """IN_PROGRESS → RESOLVED → CLOSED(허용 전이표대로, 시험용 시각은 지금)."""
    now = datetime.now(timezone.utc)
    transition(conn, sub_id, "RESOLVED", "FINAL_REPLY_SENT", now, "TS_LV_AGENT_09")
    transition(conn, sub_id, "CLOSED", "NO_REPLY_168H_AFTER_RESOLVED", now, "SYSTEM", final_action="CLOSED_NO_RESPONSE")


def patch(api, sub_id, **body):
    api[1].fake = FakeTransport(**ANSWER)
    return api[0].patch(f"/sub-tickets/{sub_id}", headers=AGENT, json=body)


# --- 상세 묶음 ---


def test_ac_030_1_info_request_detail(api):
    """AC-030-1: CSV1-000017 → 원문·강조할 error_code, DEFECT·SITE_DOWN·P1(PR-02)·TS_LV·1h/24h·막는 항목 serial_no, 영어 정보 요청."""
    d = info_request(api)
    s = first(d)
    body = d["ticket"]["inquiry_body"]
    error = next(f for f in s["fields"] if f["field"] == "error_code")
    assert "Terminal overheating" in body and error["value_raw"].lower() in body.lower()  # 화면이 원문에서 찾아 강조(C-109)
    st = s["sub_ticket"]
    assert (st["category_code"], st["urgency_flag"], st["priority"], st["priority_rule_id"], st["assigned_dept"]) == \
        ("DEFECT", "SITE_DOWN", "P1", "PR-02", "TS_LV")
    assert (st["sla_first_response_target_h"], st["sla_resolution_target_h"]) == (1, 24)
    assert st["missing_blocking_info"] == ["serial_no"]
    (draft,) = [x for x in s["drafts"] if not x["superseded_at"]]
    assert (draft["message_type"], draft["language"]) == ("INFO_REQUEST", "en")


def test_ac_030_2_priority_why(api):
    """AC-030-2: 우선순위 "왜?" → PR-02 규칙 행(priority_rules.csv)과 긴급도 근거 문장."""
    r = rows(info_request(api))
    assert r["C-03"]["why"]["rule"]["rule_id"] == "PR-02" and "PR-02 ✓" in r["C-03"]["evidence"][0]
    assert r["C-02"]["result"] == "SITE_DOWN" and r["C-02"]["evidence"] == ["plant stopped"]


def test_ac_030_3_compound_sections(api):
    """AC-030-3: CSV1-000008 → 문의 1(FW_UPDATE)·문의 2(MANUAL) 구역, 각자 근거 문장, 하위 문의별 답변 초안."""
    d = compound(api)
    assert [s["sub_ticket"]["category_code"] for s in d["sub_tickets"]] == ["FW_UPDATE", "MANUAL"]
    for seq in (1, 2):
        part = sub(d, seq)
        evidence = next(r for r in part["evidence_rows"] if r["id"] == "C-01")["evidence"]
        assert evidence and evidence != next(r for r in sub(d, 3 - seq)["evidence_rows"] if r["id"] == "C-01")["evidence"]
        assert [x["message_type"] for x in part["drafts"] if not x["superseded_at"]] == ["FINAL_REPLY"]


def test_ac_030_4_quote_detail(api):
    """AC-030-4: CSV1-000004 → 막는 항목 없음(정보 요청 초안 없음), 프랑스어 답변, 조회값 520 USD·4주."""
    s = first(quote(api))
    assert s["sub_ticket"]["missing_blocking_info"] == []
    (draft,) = s["drafts"]
    assert (draft["message_type"], draft["language"]) == ("FINAL_REPLY", "fr")
    lookups = {lv["item"]: lv["value"] for lv in rows({"sub_tickets": [s]})["M-C-02"]["lookups"]}
    assert lookups["list_price_usd"] == 520 and lookups["std_lead_time_weeks"] == 4


def test_contacts_and_subject(api):
    """FR-030 처리 1(가-7): 보낸 사람 연락처·제목 원문이 상세에 있다."""
    client, clients, conn = api
    clients.fake = FakeTransport(**ANSWER)
    from tests.acceptance.test_ticket_detail import gold_input
    data = {**gold_input(conn, "CSV1-000004"), "inquiry_subject": "Quote", "contact_name": "Marie Dupont",
            "contact_email": "marie@example.fr", "contact_phone": "+33 1 23 45 67 89"}
    tid = client.post("/tickets", json=data).json()["ticket_id"]
    t = detail_of(api, tid)["ticket"]
    assert (t["inquiry_subject"], t["contact_name"], t["contact_email"], t["contact_phone"]) == \
        ("Quote", "Marie Dupont", "marie@example.fr", "+33 1 23 45 67 89")


def test_unknown_ticket(api):
    """FR-030 예외 1행: 없는 번호 → 404 "티켓을 찾을 수 없음"(상세·이력)."""
    for path in ("/tickets/CSV1-999999", "/tickets/CSV1-999999/timeline"):
        res = api[0].get(path)
        assert res.status_code == 404 and res.json()["detail"] == "티켓을 찾을 수 없음"


# --- 분류 직접 수정 (FR-030 처리 6) ---


def expected_rules(conn, customer_id, product_code, category, urgency):
    family = lookup_product(conn, product_code).product_family
    tier = lookup_customer(conn, customer_id).customer_tier
    priority = decide_priority(conn, category, urgency)
    sla = find_sla_target(conn, category, tier, priority.priority)
    return (priority.priority, assign_dept(conn, family, category).assigned_dept,
            check_required_info(conn, family, category, []).required_info,
            sla.sla_first_response_target_h, sla.sla_resolution_target_h)


def test_ac_030_5_category_edit(api):
    """AC-030-5: 유형을 바꿔 저장 → "상담원 수정", 우선순위·부서·필수 항목·SLA 목표가 새 유형으로."""
    d = info_request(api)
    s = first(d)
    sub_id = s["sub_ticket"]["sub_ticket_id"]
    res = patch(api, sub_id, category_code="TECH_SPEC", expected_version=s["version"])
    assert res.status_code == 202, res.text
    after = first(detail_of(api, d["ticket"]["ticket_id"]))
    st = after["sub_ticket"]
    assert after["edits"]["category_code"]["from"] == "DEFECT" and after["edits"]["category_code"]["to"] == "TECH_SPEC"
    assert after["edits"]["category_code"]["by"] == "TS_LV_AGENT_09"
    want = expected_rules(api[2], d["ticket"]["customer_id"], st["product_code"], "TECH_SPEC", "SITE_DOWN")
    assert (st["priority"], st["assigned_dept"], st["required_info"], st["sla_first_response_target_h"],
            st["sla_resolution_target_h"]) == want
    before = s["sub_ticket"]
    assert st["category_code"] == "TECH_SPEC"
    assert want != (before["priority"], before["assigned_dept"], before["required_info"],
                    before["sla_first_response_target_h"], before["sla_resolution_target_h"])  # 실제로 값이 바뀌었다
    run = api[0].get(f"/tickets/{d['ticket']['ticket_id']}/runs").json()["runs"]
    assert any(r["trigger"] == "AGENT_EDIT" and r["status"] == "SUCCESS" for r in run)
    assert api[1].fake.count("L1") == 0 and api[1].fake.count("L2") == 0  # 규칙 단계부터(언어 모델 분류·추출 안 부름)


def test_reprocess_keeps_agent_edit(api):
    """FR-030 처리 5·6, C-112: 상담원이 유형을 고친 뒤 [다시 처리]해도 고친 유형이 남고 근거 줄에 "상담원 수정"이 보인다."""
    d = info_request(api)
    tid = d["ticket"]["ticket_id"]
    s = first(d)
    assert patch(api, s["sub_ticket"]["sub_ticket_id"], category_code="TECH_SPEC",
                 expected_version=s["version"]).status_code == 202
    edited = first(detail_of(api, tid))["sub_ticket"]
    from tests.acceptance.test_ticket_detail import defect_l1
    from tests.acceptance.test_drafts import L2_DEFECT
    api[1].fake = FakeTransport(L1=[defect_l1()], L2=[L2_DEFECT], L3=[INFO_REPLY], L7=[GLOSS_OK])  # 언어 모델은 다시 DEFECT
    assert api[0].post(f"/tickets/{tid}/reprocess").status_code == 202
    after = detail_of(api, tid)
    assert after["run"]["trigger"] == "RETRY" and after["run"]["status"] == "SUCCESS", after["run"]
    st = first(after)["sub_ticket"]
    assert api[1].fake.count("L1") == 1  # 처음부터 다시 돌았다
    assert (st["category_code"], st["priority"], st["assigned_dept"], st["required_info"]) == (
        "TECH_SPEC", edited["priority"], edited["assigned_dept"], edited["required_info"])
    (c01,) = [r for r in first(after)["evidence_rows"] if r["id"] == "C-01"]
    assert c01["evidence"][0] == "상담원 수정: DEFECT → TECH_SPEC" and "상담원 수정" in c01["why"]


def test_ac_013_3_received_field(api):
    """AC-013-3: serial_no를 받았다고 저장 → 막는 항목에서 빠지고 정보 요청 필요가 꺼진다. 이전 정보 요청 초안은 대체됨."""
    d = info_request(api)
    s = first(d)
    sub_id = s["sub_ticket"]["sub_ticket_id"]
    res = patch(api, sub_id, received_fields=[{"field": "serial_no", "value": "SN-1234"}])
    assert res.status_code == 202, res.text
    after = first(detail_of(api, d["ticket"]["ticket_id"]))
    assert "serial_no" not in after["sub_ticket"]["missing_blocking_info"]
    assert after["edits"]["received_fields"]["to"] == ["serial_no"]
    assert any(f["field"] == "serial_no" and f["source"] == "AGENT" and f["value_raw"] == "SN-1234" for f in after["fields"])
    old = [x for x in after["drafts"] if x["message_type"] == "INFO_REQUEST"]
    assert old and all(x["superseded_at"] for x in old)


def test_ac_010_3_product_edit(api):
    """AC-010-3: 제품을 고르면 Q2(FR-010)부터 다시 돌아 부서·필수 항목이 채워진다."""
    d = quote(api)
    s = first(d)
    res = patch(api, s["sub_ticket"]["sub_ticket_id"], product_code="ACB-AS-2000")
    assert res.status_code == 202, res.text
    st = first(detail_of(api, d["ticket"]["ticket_id"]))["sub_ticket"]
    family = lookup_product(api[2], "ACB-AS-2000").product_family
    assert st["product_code"] == "ACB-AS-2000"
    assert st["assigned_dept"] == assign_dept(api[2], family, "QUOTE").assigned_dept
    assert st["required_info"] == check_required_info(api[2], family, "QUOTE", []).required_info


def test_edit_refused(api):
    """FR-030 예외 4행·SCR-03-P8: 이전 version 409, 틀린 값 400, 고칠 값 없음 400, 상담원 ID 없음 400, 종료 409."""
    d = info_request(api)
    s = first(d)
    sub_id = s["sub_ticket"]["sub_ticket_id"]
    client, _, conn = api
    res = patch(api, sub_id, category_code="TECH_SPEC", expected_version=s["version"] - 1)
    assert res.status_code == 409 and res.json()["detail"] == "다른 사용자가 변경함. 새로고침"
    res = patch(api, sub_id, category_code="NOPE")
    assert res.status_code == 400 and res.json()["detail"] == "category_code 값이 올바르지 않음"
    res = patch(api, sub_id, return_kind="DEFECT")  # 유형이 RETURN이 아님
    assert res.status_code == 400
    assert patch(api, sub_id, category_code="DEFECT").json()["detail"] == "고칠 값이 없음"
    assert client.patch(f"/sub-tickets/{sub_id}", json={"category_code": "TECH_SPEC"}).status_code == 400
    assert patch(api, "CSV1-999999-1", category_code="TECH_SPEC").status_code == 404
    close(conn, sub_id)
    res = patch(api, sub_id, category_code="TECH_SPEC")
    assert res.status_code == 409 and res.json()["detail"] == "종료된 문의는 바꿀 수 없음"


def test_edit_busy(api):
    """처리 흐름이 도는 중이면 409 "처리 중"."""
    d = info_request(api)
    tid = d["ticket"]["ticket_id"]
    api[2].execute("INSERT INTO svc.agent_run (ticket_id, trigger, started_at_utc, llm_model) VALUES (%s, 'RETRY', now(), 'm')",
                   (tid,))
    res = patch(api, first(d)["sub_ticket"]["sub_ticket_id"], category_code="TECH_SPEC")
    assert res.status_code == 409 and res.json()["detail"] == "처리 중"


# --- 다시 처리 (FR-030 처리 5) ---


def test_reprocess_supersedes_drafts(api):
    """FR-030 처리 5, §2-4: 성공한 티켓도 다시 처리 → 새 RETRY, 이전 초안 superseded, 발송한 메시지는 그대로."""
    d = info_request(api)
    tid = d["ticket"]["ticket_id"]
    assert d["can_reprocess"] and not d["can_retry"]
    (draft,) = first(d)["drafts"]
    assert send(api, draft).status_code == 200
    from tests.acceptance.test_ticket_detail import defect_l1
    from tests.acceptance.test_drafts import L2_DEFECT
    api[1].fake = FakeTransport(L1=[defect_l1()], L2=[L2_DEFECT], L3=[INFO_REPLY], L7=[GLOSS_OK])
    res = api[0].post(f"/tickets/{tid}/reprocess")
    assert res.status_code == 202, res.text
    after = detail_of(api, tid)
    assert after["run"]["trigger"] == "RETRY" and after["run"]["status"] == "SUCCESS"
    drafts = first(after)["drafts"]
    assert [x["message_id"] for x in drafts if not x["superseded_at"]] != [draft["message_id"]]
    sent = [m for m in after["messages"] if m["message_type"] == "INFO_REQUEST" and m["message_status"] == "SENT"]
    assert len(sent) == 1 and sent[0]["source_draft_id"] == draft["message_id"]


def test_reprocess_closed_refused(api):
    """화면 정의서 v1 SCR-03 ⑥ 종료: 모든 하위 문의가 CLOSED면 409 "종료된 문의입니다", 상세 can_reprocess 거짓."""
    d = quote(api)
    tid = d["ticket"]["ticket_id"]
    close(api[2], first(d)["sub_ticket"]["sub_ticket_id"])
    res = api[0].post(f"/tickets/{tid}/reprocess")
    assert res.status_code == 409 and res.json()["detail"] == "종료된 문의입니다"
    assert not detail_of(api, tid)["can_reprocess"]


# --- 이력 (FR-030 처리 4) ---


def test_timeline_order_and_kinds(api):
    """FR-030 처리 4, §8-1 timeline: 상태 변경·발송 메시지·조정이 시각순 한 줄 목록."""
    d = info_request(api)
    tid = d["ticket"]["ticket_id"]
    (draft,) = first(d)["drafts"]
    assert send(api, draft).status_code == 200
    sub_id = first(d)["sub_ticket"]["sub_ticket_id"]
    res = api[0].post(f"/sub-tickets/{sub_id}/priority", headers=AGENT,
                      json={"new_priority": "P2", "reason_kind": "CUSTOMER_REQUEST", "reason_text": "고객 요청"})
    assert res.status_code == 200, res.text
    items = api[0].get(f"/tickets/{tid}/timeline").json()
    kinds = [i["kind"] for i in items]
    assert kinds[0] == "STATUS" and items[0]["to_status"] == "NEW"
    assert "MESSAGE" in kinds and "PRIORITY" in kinds
    assert [i["at"] for i in items] == sorted(i["at"] for i in items)
    inquiry = next(i for i in items if i["kind"] == "MESSAGE" and i["message_type"] == "INQUIRY")
    sent = next(i for i in items if i["kind"] == "MESSAGE" and i["message_type"] == "INFO_REQUEST")
    assert inquiry["sender"] == "CUSTOMER" and sent["sender"] == "AGENT" and sent["body"]
    prio = next(i for i in items if i["kind"] == "PRIORITY")
    assert (prio["from_priority"], prio["to_priority"], prio["reason"]) == ("P1", "P2", "고객 요청")
    assert any(i["kind"] == "STATUS" and i["to_status"] == "WAITING_CUSTOMER" for i in items)


def test_quote_body_untouched_by_detail(api):
    """FR-030 출력: 상세는 화면 표시만, 읽어도 저장 값이 바뀌지 않는다."""
    d = quote(api)
    again = detail_of(api, d["ticket"]["ticket_id"])
    assert first(again)["drafts"][0]["body"] == QUOTE_BODY and first(again)["version"] == first(d)["version"]
