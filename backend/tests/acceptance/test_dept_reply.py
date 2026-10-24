"""부서 회신과 예외 부서 메일 완료 기준 (FR-033 처리 8·9, FR-031 처리 9, 변경 add-dept-reply).

접수 API로 처리한 문의를 이관 API로 이관한 뒤 부서 상담원의 API로 회신·메일을 쓴다(대역 언어 모델, 롤백).
화면 모양(AC-033-7의 버튼)은 상세 응답의 writer로 보고, 화면은 Playwright로 확인한다(C-164).
"""

from __future__ import annotations

from app.status.dept_reply import MSG_EMPTY, MSG_NOT_ESCALATED, MSG_NOT_EXCEPTION, MSG_WRONG_DEPT
from tests.acceptance.test_drafts import FakeTransport
from tests.acceptance.test_fault_diagnosis import PLC_REPLY, defect_plc
from tests.acceptance.test_ticket_detail import api, index, info_request, rows  # noqa: F401  (api·index 픽스처)

CS_AGENT = "TS_LV_AGENT_09"
RMA_REPLY = "RMA-2026-0042 issued. Replacement ships in 3 weeks."
RMA_DRAFT = {"body": "Please check the base power supply. Your RMA number is RMA-2026-0042 and the "
                     "replacement ships in 3 weeks.", "citations": [], "numbers_used": []}
GLOSS = {"gloss": "교체 번호 RMA-2026-0042, 3주 뒤 출하."}


def heads(agent, dept):
    return {"X-Agent-Id": agent, "X-Agent-Dept": dept}


def sub_of(detail):
    return detail["sub_tickets"][0]["sub_ticket"]["sub_ticket_id"]


def escalate(api, sub_id, dept, reason):
    res = api[0].post(f"/sub-tickets/{sub_id}/escalate", json={"dept": dept, "reason_code": reason},
                      headers={"X-Agent-Id": CS_AGENT})
    assert res.status_code == 200, res.text


def detail(api, ticket_id, dept):
    return api[0].get(f"/tickets/{ticket_id}", headers={"X-Agent-Dept": dept}).json()


def test_ac_033_3_qa_claim_reply(api):
    """AC-033-3: QA_CLAIM으로 이관된 CSV1-000007 → QA_CLAIM_AGENT_01이 접수함에서 열어 [회신 등록] → IN_PROGRESS,
    ESCALATION_NOTE RECEIVED(DEPT, QA_CLAIM_AGENT_01), "부서 회신" 영역. 다시 처리(DEPT_REPLY)의 L4·Q11·L8에 회신."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    escalate(api, sub_id, "QA_CLAIM", "RMA_REQUIRED")
    inbox = api[0].get("/tickets", params={"dept": "QA_CLAIM"}).json()["rows"]
    assert sub_id in {r["sub_ticket_id"] for r in inbox}
    assert detail(api, ticket_id, "QA_CLAIM")["sub_tickets"][0]["writer"] == "DEPT_REPLY"
    waiting = detail(api, ticket_id, "TS_AUTO")["sub_tickets"][0]
    assert waiting["writer"] == "CS" and waiting["dept_replies"] == []  # 화면은 "부서 회신 대기 중"

    api[1].fake = fake = FakeTransport(L4=[RMA_DRAFT], L7=[GLOSS])
    res = api[0].post(f"/sub-tickets/{sub_id}/dept-reply", json={"body": RMA_REPLY}, headers=heads("QA_CLAIM_AGENT_01", "QA_CLAIM"))
    assert res.status_code == 202, res.text
    conn = api[2]
    assert conn.execute("SELECT status FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()[0] == "IN_PROGRESS"
    note = conn.execute("""SELECT sender, message_status, sent_by_name, body, language FROM svc.ticket_message
                            WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE' AND message_status = 'RECEIVED'""",
                        (sub_id,)).fetchall()
    assert note == [("DEPT", "RECEIVED", "QA_CLAIM_AGENT_01", RMA_REPLY, "ko")]
    last = conn.execute("""SELECT event_kind, changed_by FROM svc.ticket_status_history WHERE sub_ticket_id = %s
                            ORDER BY history_id DESC LIMIT 1""", (sub_id,)).fetchone()
    assert last == ("DEPT_REPLY", "QA_CLAIM_AGENT_01")

    shown = detail(api, ticket_id, "TS_AUTO")
    sub = shown["sub_tickets"][0]
    (reply,) = sub["dept_replies"]
    assert (reply["body"], reply["sent_by_name"]) == (RMA_REPLY, "QA_CLAIM_AGENT_01") and reply["sent_at_utc"]
    assert shown["run"]["trigger"] == "DEPT_REPLY" and shown["run"]["status"] == "SUCCESS"
    # 언어 모델은 Q8부터: L1·L2를 부르지 않는다(C-160). L4는 부서 회신 칸이 있는 v3
    assert fake.count("L1") == fake.count("L2") == 0
    (l4,) = [p for c, p in fake.prompts if c == "L4"]
    assert "<dept_reply>\nRMA-2026-0042 issued." in l4
    assert any(c == "L8" and "<dept_reply>RMA-2026-0042" in p for c, p in fake.prompts)
    (draft,) = [d for d in sub["drafts"] if not d["superseded_at"]]
    assert draft["message_status"] == "DRAFT" and "RMA-2026-0042" in draft["body"]
    assert draft["check"]["passed_yn"], draft["check"]  # 회신 속 번호는 근거 밖 숫자가 아니다(§3-4 2번)
    assert sub["diagnosis"] and rows(shown)["C-09"]["result"].startswith("QA_CLAIM")  # Q8a·Q9a는 옮겨 적음
    # 상담원이 고친 본문의 다시 대조(임시 저장)도 회신 숫자를 허용한다
    api[1].fake = FakeTransport(L7=[GLOSS])
    assert api[0].put(f"/messages/{draft['message_id']}", json={"body": draft["body"] + " RMA-2026-0042"}).status_code == 200
    check = conn.execute("""SELECT passed_yn FROM eval.self_check WHERE message_id = %s AND check_type = 'DRAFT_CHECK'
                             ORDER BY check_id DESC LIMIT 1""", (draft["message_id"],)).fetchone()[0]
    assert check


def mail_case(api):
    """CSV1-000017을 FIELD_SVC로 이관하고 FIELD_SVC 상담원이 메일 초안을 쓴다."""
    first = info_request(api)
    sub_id = sub_of(first)
    escalate(api, sub_id, "FIELD_SVC", "ONSITE_REQUIRED")
    res = api[0].post(f"/sub-tickets/{sub_id}/dept-mail", json={"body": "We will visit your site on 2026-11-02 at 09:00."},
                      headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert res.status_code == 201, res.text
    return first, sub_id, res.json()["message_id"]


def test_ac_033_6_field_svc_mail(api):
    """AC-033-6: FIELD_SVC로 이관된 CSV1-000017 → FIELD_SVC 상담원이 메일을 쓰고 승인 → 숫자 검사·검증 없이
    FINAL_REPLY SENT(DEPT), 상태 IN_PROGRESS(DEPT_MAIL_SENT)."""
    first, sub_id, mid = mail_case(api)
    assert detail(api, first["ticket"]["ticket_id"], "FIELD_SVC")["sub_tickets"][0]["writer"] == "DEPT_MAIL"
    api[1].fake = fake = FakeTransport(L7=[{"gloss": "11월 2일 9시에 방문합니다."}])
    body = "We will visit your site on 2026-11-02 at 09:00. Technician: Kim."
    saved = api[0].put(f"/messages/{mid}", json={"body": body}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert saved.status_code == 200 and saved.json()["gloss"]  # 임시 저장은 대역만(C-165)
    res = api[0].post(f"/messages/{mid}/send", json={"final_body": body}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert res.status_code == 200, res.text
    assert fake.count("L8") == fake.count("L4") == 0
    conn = api[2]
    sent = conn.execute("""SELECT sender, message_type, sent_by_name, source_draft_id FROM svc.ticket_message
                            WHERE sub_ticket_id = %s AND message_status = 'SENT' AND message_type = 'FINAL_REPLY'""",
                        (sub_id,)).fetchall()
    assert sent == [("DEPT", "FINAL_REPLY", "FIELD_SVC_AGENT_01", mid)]
    status, first_response = conn.execute("SELECT status, first_response_at_utc FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                          (sub_id,)).fetchone()
    assert status == "IN_PROGRESS" and first_response is not None
    last = conn.execute("""SELECT event_kind FROM svc.ticket_status_history WHERE sub_ticket_id = %s
                            ORDER BY history_id DESC LIMIT 1""", (sub_id,)).fetchone()[0]
    assert last == "DEPT_MAIL_SENT"
    mails = detail(api, first["ticket"]["ticket_id"], "TS_LV")["sub_tickets"][0]["dept_mails"]
    assert [m["message_status"] for m in mails] == ["SENT"]  # 승인된 초안은 APPROVED라 목록에서 빠진다


def test_ac_031_6_no_checks(api):
    """AC-031-6: FIELD_SVC 상담원이 쓴 고객 메일을 승인 → 숫자·인용 대조와 검증 에이전트 없이 발송 행(DEPT)."""
    _, sub_id, mid = mail_case(api)
    # 근거 밖 숫자(날짜·시각)가 있어도 "확인 필요"(409) 없이 보낸다
    res = api[0].post(f"/messages/{mid}/send", json={"final_body": "We will visit your site on 2026-11-02 at 09:00."},
                      headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert res.status_code == 200 and res.json()["override_check"] is False
    checks = api[2].execute("SELECT count(*) FROM eval.self_check WHERE message_id = %s", (mid,)).fetchone()[0]
    assert checks == 0
    sent = api[2].execute("""SELECT count(*) FROM svc.ticket_message WHERE sub_ticket_id = %s AND sender = 'DEPT'
                              AND message_type = 'FINAL_REPLY' AND message_status = 'SENT'""", (sub_id,)).fetchone()[0]
    assert sent == 1
    again = api[0].post(f"/messages/{mid}/send", json={"final_body": "x"}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert again.status_code == 409  # 두 번 발송 거부(FR-031 예외 4행)


def test_ac_033_7_rnd_fw_view(api):
    """AC-033-7: RND_FW로 이관된 문의를 RND_FW_AGENT_01이 열면 회신 작성란과 [회신 등록]만(writer DEPT_REPLY)."""
    first = info_request(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    escalate(api, sub_id, "RND_FW", "FW_UPDATE_FAILURE")
    assert detail(api, ticket_id, "RND_FW")["sub_tickets"][0]["writer"] == "DEPT_REPLY"
    assert detail(api, ticket_id, "TS_LV")["sub_tickets"][0]["writer"] == "CS"
    assert detail(api, ticket_id, "FIELD_SVC")["sub_tickets"][0]["writer"] == "CS"  # 이관받지 않은 부서
    mail = api[0].post(f"/sub-tickets/{sub_id}/dept-mail", json={"body": "x"}, headers=heads("RND_FW_AGENT_01", "RND_FW"))
    assert (mail.status_code, mail.json()["detail"]) == (403, MSG_NOT_EXCEPTION)


def test_exceptions(api):
    """FR-033 예외 4행(빈 본문)과 구현 선택 C-166: 다른 부서, ESCALATED 아님(실행 로그), 부서 메일 검증 거부."""
    first = info_request(api)
    sub_id = sub_of(first)
    url = f"/sub-tickets/{sub_id}/dept-reply"
    before = api[0].post(url, json={"body": "ok"}, headers=heads("QA_CLAIM_AGENT_01", "QA_CLAIM"))
    assert (before.status_code, before.json()["detail"]) == (403, MSG_WRONG_DEPT)  # 이관 전
    escalate(api, sub_id, "FIELD_SVC", "ONSITE_REQUIRED")
    empty = api[0].post(url, json={"body": "  "}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert (empty.status_code, empty.json()["detail"]) == (400, MSG_EMPTY)
    mail_empty = api[0].post(f"/sub-tickets/{sub_id}/dept-mail", json={"body": ""}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert (mail_empty.status_code, mail_empty.json()["detail"]) == (400, MSG_EMPTY)
    other = api[0].post(url, json={"body": "ok"}, headers=heads("QA_CLAIM_AGENT_01", "QA_CLAIM"))
    assert (other.status_code, other.json()["detail"]) == (403, MSG_WRONG_DEPT)
    assert api[0].post(url, json={"body": "ok"}, headers={"X-Agent-Dept": "FIELD_SVC"}).status_code == 400  # 상담원 없음
    assert api[0].post("/sub-tickets/NOPE-1/dept-reply", json={"body": "ok"},
                       headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC")).status_code == 404
    mid = api[0].post(f"/sub-tickets/{sub_id}/dept-mail", json={"body": "Visit soon."},
                      headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC")).json()["message_id"]
    assert api[0].post(f"/messages/{mid}/verify").status_code == 400
    wrong = api[0].post(f"/messages/{mid}/send", json={"final_body": "Visit soon."}, headers=heads(CS_AGENT, "TS_LV"))
    assert (wrong.status_code, wrong.json()["detail"]) == (403, MSG_NOT_EXCEPTION)

    api[1].fake = FakeTransport(L4=[PLC_REPLY], L7=[GLOSS])
    assert api[0].post(url, json={"body": "Visit booked."}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC")).status_code == 202
    again = api[0].post(url, json={"body": "second"}, headers=heads("FIELD_SVC_AGENT_01", "FIELD_SVC"))
    assert (again.status_code, again.json()["detail"]) == (409, MSG_NOT_ESCALATED)
    step = api[2].execute("""SELECT st.step_name, st.result, st.error FROM svc.agent_step st JOIN svc.agent_run r USING (run_id)
                              WHERE r.sub_ticket_id = %s ORDER BY st.step_id DESC LIMIT 1""", (sub_id,)).fetchone()
    assert step == ("T6", "FAILED", MSG_NOT_ESCALATED)  # FR-025 예외 1행


def test_save_keeps_pipeline_steps(api):
    """C-169: 초안 임시 저장(AGENT_EDIT run, Q11·Q13)은 처리 흐름 실행이 아니므로 진단·이관 후보와 "왜?"가 남는다."""
    first = defect_plc(api)
    draft = first["sub_tickets"][0]["drafts"][0]
    api[1].fake = FakeTransport(L7=[GLOSS])
    assert api[0].put(f"/messages/{draft['message_id']}", json={"body": draft["body"] + " x"}).status_code == 200
    shown = api[0].get(f"/tickets/{first['ticket']['ticket_id']}").json()
    assert shown["sub_tickets"][0]["diagnosis"] and "C-09" in rows(shown)
    assert shown["run"]["trigger"] == "INTAKE"
