"""이관 메일 표시 (변경 add-escalation-mail). 부서에 보낸 이관 요청과 부서 회신이 메일로 오갔는지 기록하고 이력에 나타낸다.
실제 메일 발송·수신 연동은 없다(표시만)."""

from __future__ import annotations

from tests.acceptance.test_dept_reply import (CS_AGENT, GLOSS, RMA_DRAFT, RMA_REPLY, FakeTransport, defect_plc, detail,
                                              heads, sub_of)  # noqa: F401
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)


def _notes(api, ticket_id):
    return [e for e in api[0].get(f"/tickets/{ticket_id}/timeline").json()
            if e["kind"] == "MESSAGE" and e["message_type"] == "ESCALATION_NOTE"]


def test_escalation_marks_mail_only_when_asked(api):
    """이관 때 send_mail이면 부서에 보낸 메모가 via_mail로 남고, 아니면 false다."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    res = api[0].post(f"/sub-tickets/{sub_id}/escalate", json={"dept": "QA_CLAIM", "reason_code": "RMA_REQUIRED", "memo": "교체 판정 부탁", "send_mail": True},
                      headers={"X-Agent-Id": CS_AGENT})
    assert res.status_code == 200, res.text
    notes = _notes(api, ticket_id)
    assert len(notes) == 1 and notes[0]["message_status"] == "SENT" and notes[0]["via_mail"] is True


def test_escalation_without_mail_flag_is_not_mail(api):
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    assert api[0].post(f"/sub-tickets/{sub_id}/escalate", json={"dept": "QA_CLAIM", "reason_code": "RMA_REQUIRED"},
                       headers={"X-Agent-Id": CS_AGENT}).status_code == 200
    assert [n["via_mail"] for n in _notes(api, ticket_id)] == [False]


def test_mail_reply_is_accepted_from_any_session_dept_and_marked(api):
    """메일 회신은 화면에서 고른 부서와 달라도 받아들이고 via_mail로 남는다. 메일이 아니면 예전처럼 다른 부서는 403."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    assert api[0].post(f"/sub-tickets/{sub_id}/escalate", json={"dept": "QA_CLAIM", "reason_code": "RMA_REQUIRED", "send_mail": True},
                       headers={"X-Agent-Id": CS_AGENT}).status_code == 200
    cs = heads(CS_AGENT, "TS_AUTO")  # C/S 쪽 세션(이관받은 부서가 아님)
    assert api[0].post(f"/sub-tickets/{sub_id}/dept-reply", json={"body": RMA_REPLY}, headers=cs).status_code == 403
    api[1].fake = FakeTransport(L4=[RMA_DRAFT], L7=[GLOSS])
    res = api[0].post(f"/sub-tickets/{sub_id}/dept-reply", json={"body": RMA_REPLY, "via_mail": True}, headers=cs)
    assert res.status_code == 202, res.text
    received = [n for n in _notes(api, ticket_id) if n["message_status"] == "RECEIVED"]
    assert len(received) == 1 and received[0]["via_mail"] is True and received[0]["sender"] == "DEPT"
    assert detail(api, ticket_id, "TS_AUTO")["sub_tickets"][0]["sub_ticket"]["status"] == "IN_PROGRESS"
