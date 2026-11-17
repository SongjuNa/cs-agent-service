"""이관 메일 실제 발송·수신 (변경 add-escalation-mail-live).

SMTP와 받은 메일함은 가짜로 바꿔 끼운다. 가짜 메일함은 보낸 메일을 그대로 받아 두는 Mailpit처럼 동작해,
"보낸 요청 메일 → 부서 답장 → 받은 메일함 확인 → 문의에 연결 → 다시 처리"를 한 시험 안에서 끝까지 돌린다.
"""

from __future__ import annotations

import itertools
import smtplib
from email.message import EmailMessage

import httpx
import pytest

from app.api.deps import get_mail
from app.config import Settings
from app.main import app
from app.mail import InboundMail, MailpitInbox, dept_address, parse_tag, strip_quoted
from tests.acceptance.test_dept_reply import (CS_AGENT, GLOSS, RMA_DRAFT, FakeTransport, defect_plc, detail,  # noqa: F401
                                              sub_of)
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)

CS = "cs-center@cs.example.com"
DOMAIN = "dept.example.com"


class FakeMailpit:
    """SMTP 발송 + 받은 메일함. 보낸 메일은 모두 메일함에 들어간다(Mailpit과 같음)."""

    def __init__(self, fail_send: bool = False):
        self.fail_send = fail_send
        self.mails: dict[str, tuple[EmailMessage, bool]] = {}
        self._ids = itertools.count(1)

    # Sender
    def send(self, message: EmailMessage) -> None:
        if self.fail_send:
            raise smtplib.SMTPServerDisconnected("메일 서버 꺼짐")
        self.mails[str(next(self._ids))] = (message, False)

    # Inbox: C/S 주소로 온 메일 중 아직 "본 메일" 표시가 없는 것(Mailpit 검색 to:… -tag:…와 같음)
    def pending(self) -> list[InboundMail]:
        return [InboundMail(id=i, sender=m["From"].lower(), to=[m["To"].lower()], subject=m["Subject"],
                            text=m.get_content()) for i, (m, done) in self.mails.items() if not done and m["To"] == CS]

    def mark_done(self, ids: list[str]) -> None:
        for i in ids:
            self.mails[i] = (self.mails[i][0], True)

    def to(self, address: str) -> list[EmailMessage]:
        return [m for m, _ in self.mails.values() if m["To"] == address]

    def deliver(self, sender: str, subject: str, text: str, to: str = CS) -> None:
        """다른 메일 프로그램에서 온 메일처럼 넣는다."""
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = sender, to, subject
        message.set_content(text)
        self.mails[str(next(self._ids))] = (message, False)


class FakeMail:
    def __init__(self, box: FakeMailpit, enabled: bool = True):
        self.settings = Settings(database_url="unused", mail_enabled=enabled, mail_cs_address=CS, mail_dept_domain=DOMAIN,
                                 app_base_url="http://cs.local")
        self.sender = self.inbox = box

    @property
    def enabled(self) -> bool:
        return self.settings.mail_enabled


@pytest.fixture
def box(api):
    box = FakeMailpit()
    app.dependency_overrides[get_mail] = lambda: FakeMail(box)
    return box


def escalate(api, sub_id, send_mail=True, memo="교체 판정 부탁드립니다"):
    res = api[0].post(f"/sub-tickets/{sub_id}/escalate",
                      json={"dept": "QA_CLAIM", "reason_code": "RMA_REQUIRED", "memo": memo, "send_mail": send_mail},
                      headers={"X-Agent-Id": CS_AGENT})
    assert res.status_code == 200, res.text
    return res.json()


def notes(api, ticket_id):
    return [e for e in api[0].get(f"/tickets/{ticket_id}/timeline").json()
            if e["kind"] == "MESSAGE" and e["message_type"] == "ESCALATION_NOTE"]


# ---- 순수 함수 ----

def test_parse_tag_and_dept_address():
    assert parse_tag("Re: [ESC:CS-000123-1] CS-000123 이관 요청") == "CS-000123-1"
    assert parse_tag("RE: 견적 문의") is None
    assert dept_address("QA_CLAIM", DOMAIN) == "qa_claim@dept.example.com"


def test_strip_quoted_keeps_only_new_text():
    text = "RMA 발급했습니다.\n3주 뒤 출하.\n\nOn Mon, cs-center wrote:\n> 교체 판정 부탁\n> 원문"
    assert strip_quoted(text) == "RMA 발급했습니다.\n3주 뒤 출하."
    assert strip_quoted("> 인용만\n> 있음") == ""
    assert strip_quoted("확인했습니다\n\n-----Original Message-----\nFrom: cs") == "확인했습니다"


def test_mailpit_inbox_ignores_read_state():
    """사람이 메일함 화면에서 답장을 열어 "읽음"이 되어도 놓치지 않는다. 읽음 대신 C/S 주소와 "본 메일" 태그로 고른다."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, dict(request.url.params), request.content))
        if request.url.path == "/api/v1/search":
            return httpx.Response(200, json={"messages": [{"ID": "m1", "Read": True}]})
        if request.url.path == "/api/v1/message/m1":
            return httpx.Response(200, json={"From": {"Address": "QA_CLAIM@dept.example.com"},
                                             "To": [{"Address": CS}], "Subject": "Re: [ESC:A-1] x", "Text": "ok"})
        return httpx.Response(200, text="ok")

    inbox = MailpitInbox("http://mailpit", CS, transport=httpx.MockTransport(handler))
    [mail] = inbox.pending()
    assert mail.sender == "qa_claim@dept.example.com" and mail.to == [CS] and mail.text == "ok"
    assert calls[0][2]["query"] == f"to:{CS} -tag:cs-linked"  # is:unread를 쓰지 않는다
    inbox.mark_done(["m1"])
    assert calls[-1][:2] == ("PUT", "/api/v1/tags") and b"cs-linked" in calls[-1][3]


# ---- 보내기 ----

def test_escalation_sends_request_mail_to_dept_mailbox(api, box):
    """send_mail이면 이관 확정 뒤 부서 메일함으로 요청 메일이 한 통 나가고, 제목에 [ESC:하위 문의]가 붙는다."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    out = escalate(api, sub_id)
    assert out["status"] == "ESCALATED"
    assert out["mail"] == {"to": "qa_claim@dept.example.com", "subject": out["mail"]["subject"], "sent": True, "error": None}
    [mail] = box.to("qa_claim@dept.example.com")
    assert mail["From"] == CS and parse_tag(mail["Subject"]) == sub_id
    body = mail.get_content()
    assert "교체 판정 부탁드립니다" in body and f"http://cs.local/tickets/{ticket_id}" in body
    assert [n["via_mail"] for n in notes(api, ticket_id)] == [True]


def test_no_mail_when_not_asked_or_disabled(api, box):
    first = defect_plc(api)
    out = escalate(api, sub_of(first), send_mail=False)
    assert "mail" not in out and box.mails == {}


def test_disabled_keeps_old_display_only_behaviour(api):
    """연동이 꺼져 있으면 예전처럼 via_mail 표시만 남기고 아무것도 보내지 않는다."""
    off = FakeMailpit()
    app.dependency_overrides[get_mail] = lambda: FakeMail(off, enabled=False)
    first = defect_plc(api)
    out = escalate(api, sub_of(first))
    assert "mail" not in out and off.mails == {}
    assert [n["via_mail"] for n in notes(api, first["ticket"]["ticket_id"])] == [True]


def test_send_failure_keeps_escalation_and_clears_mail_flag(api):
    """SMTP가 실패해도 이관은 확정되고, 응답에 실패를 알리며, 이력이 "메일 발송"이라고 하지 않는다."""
    broken = FakeMailpit(fail_send=True)
    app.dependency_overrides[get_mail] = lambda: FakeMail(broken)
    first = defect_plc(api)
    out = escalate(api, sub_of(first))
    assert out["status"] == "ESCALATED" and out["mail"]["sent"] is False and "메일 서버 꺼짐" in out["mail"]["error"]
    assert [n["via_mail"] for n in notes(api, first["ticket"]["ticket_id"])] == [False]


# ---- 받기 ----

def test_dept_reply_mail_is_linked_and_reprocessed(api, box):
    """부서가 요청 메일에 답장하면 poll이 문의에 연결하고(via_mail RECEIVED), 회신을 근거로 다시 처리한다."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    escalate(api, sub_id)
    sent = api[0].post("/mail/dept-reply-demo", json={"sub_ticket_id": sub_id,
                                                      "body": "RMA-2026-0042 issued. Replacement ships in 3 weeks."})
    assert sent.status_code == 202 and sent.json()["sender"] == "qa_claim@dept.example.com"

    api[1].fake = FakeTransport(L4=[RMA_DRAFT], L7=[GLOSS])
    res = api[0].post("/mail/poll")
    assert res.status_code == 200, res.text
    [linked] = res.json()["accepted"]
    assert linked["sub_ticket_id"] == sub_id
    received = [n for n in notes(api, ticket_id) if n["message_status"] == "RECEIVED"]
    assert len(received) == 1 and received[0]["via_mail"] is True and received[0]["sender"] == "DEPT"
    reply_body = api[2].execute("SELECT body FROM svc.ticket_message WHERE message_id = %s",
                                (linked["reply_message_id"],)).fetchone()[0]
    assert reply_body == "RMA-2026-0042 issued. Replacement ships in 3 weeks."  # 인용문은 떼고 저장
    sub = detail(api, ticket_id, "TS_AUTO")["sub_tickets"][0]
    assert sub["sub_ticket"]["status"] == "IN_PROGRESS"
    assert api[0].post("/mail/poll").json()["accepted"] == []  # 같은 메일은 두 번 연결하지 않는다


def test_reply_from_other_mailbox_is_ignored(api, box):
    """제목 표시가 맞아도 이관받은 부서 메일함이 아닌 곳에서 온 답장은 연결하지 않는다(사칭 방지)."""
    first = defect_plc(api)
    sub_id, ticket_id = sub_of(first), first["ticket"]["ticket_id"]
    escalate(api, sub_id)
    box.deliver("someone@evil.example.com", f"Re: [ESC:{sub_id}] 이관 요청", "승인합니다")
    box.deliver(dept_address("QA_CLAIM", DOMAIN), "Re: 제목 표시 없음", "확인")
    box.deliver(dept_address("QA_CLAIM", DOMAIN), f"Re: [ESC:{sub_id}] 다른 메일함으로", "확인", to="other@cs.example.com")
    out = api[0].post("/mail/poll").json()
    assert out["accepted"] == []
    reasons = {s["reason"] for s in out["skipped"]}
    assert any("이관받은 부서" in r for r in reasons) and any("[ESC:" in r for r in reasons)
    assert all(n["message_status"] == "SENT" for n in notes(api, ticket_id))


def test_reply_after_dept_already_answered_is_skipped(api, box):
    """화면에서 이미 회신을 등록해 ESCALATED가 아니면 늦게 온 메일은 건너뛰고 까닭을 남긴다."""
    first = defect_plc(api)
    sub_id = sub_of(first)
    escalate(api, sub_id)
    api[1].fake = FakeTransport(L4=[RMA_DRAFT, RMA_DRAFT], L7=[GLOSS, GLOSS])
    api[0].post("/mail/dept-reply-demo", json={"sub_ticket_id": sub_id, "body": "첫 답장"})
    api[0].post("/mail/dept-reply-demo", json={"sub_ticket_id": sub_id, "body": "두 번째 답장"})
    out = api[0].post("/mail/poll").json()
    assert len(out["accepted"]) == 1 and "이관된 문의만" in out["skipped"][-1]["reason"]


def test_mail_api_refuses_when_disabled(api):
    app.dependency_overrides[get_mail] = lambda: FakeMail(FakeMailpit(), enabled=False)
    assert api[0].get("/mail/config").json()["enabled"] is False
    assert api[0].post("/mail/poll").status_code == 409
