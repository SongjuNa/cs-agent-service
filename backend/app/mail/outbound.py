"""이관 요청 메일 만들기와 보내기.

- 받는 곳: 부서 코드로 만든 부서 메일함 주소(`qa_claim@<MAIL_DEPT_DOMAIN>`). 표를 바꾸지 않고 설정 하나로 정한다.
- 제목에 `[ESC:<하위 문의 번호>]`를 넣는다. 부서가 답장하면 제목이 그대로 돌아오므로 이 표시로 문의를 찾는다.
- 고객 문의 원문은 부서 메일함 밖으로 나가는 글이라 개인정보를 가려서 넣는다(FR-038과 같은 가리기).
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from psycopg import Connection

from app.masking import mask_text

TAG = "[ESC:{sub_ticket_id}]"


def dept_address(dept_code: str, domain: str) -> str:
    """부서 메일함 주소. 예: QA_CLAIM → qa_claim@dept.example.com"""
    return f"{dept_code.strip().lower()}@{domain.strip()}"


@dataclass
class MailResult:
    """이관 응답에 붙이는 메일 결과. 발송에 실패해도 이관은 이미 확정되어 있다."""

    to: str
    subject: str
    sent: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {"to": self.to, "subject": self.subject, "sent": self.sent, "error": self.error}


class Sender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpSender:
    """SMTP로 보낸다. 로컬에서는 Mailpit(1025)이 받는다. 인증·TLS는 쓰지 않는다(시연 범위)."""

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host, self.port, self.timeout = host, port, timeout

    def send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            smtp.send_message(message)


def _context(conn: Connection, sub_ticket_id: str) -> dict:
    row = conn.execute(
        """SELECT s.ticket_id, s.seq, s.category_code, s.product_code, s.escalated_to, s.escalation_reason,
                  t.inquiry_subject, t.inquiry_body, t.language, c.company_masked, c.country,
                  d.dept_name_ko
             FROM svc.sub_ticket s
             JOIN svc.ticket t ON t.ticket_id = s.ticket_id
             LEFT JOIN ref.customer c ON c.customer_id = t.customer_id
             LEFT JOIN ref.department d ON d.dept_code = s.escalated_to
            WHERE s.sub_ticket_id = %s""", (sub_ticket_id,)).fetchone()
    if row is None:
        raise LookupError(sub_ticket_id)
    keys = ("ticket_id", "seq", "category_code", "product_code", "escalated_to", "escalation_reason", "inquiry_subject",
            "inquiry_body", "language", "company", "country", "dept_name")
    return dict(zip(keys, row))


def build_request(conn: Connection, sub_ticket_id: str, memo: str | None, *, sender: str, dept_domain: str,
                  app_base_url: str) -> EmailMessage:
    """이관 요청 메일 한 통. 이관이 확정된 뒤(escalated_to가 있는 상태)에 부른다."""
    ctx = _context(conn, sub_ticket_id)
    to = dept_address(ctx["escalated_to"], dept_domain)
    subject = f"{TAG.format(sub_ticket_id=sub_ticket_id)} {ctx['ticket_id']} 이관 요청 · {ctx['escalation_reason']}"
    original = mask_text(ctx["inquiry_body"] or "")[0]
    lines = [
        f"{ctx['dept_name'] or ctx['escalated_to']} 담당자님,",
        "",
        "글로벌 C/S 센터에서 아래 문의를 이관합니다. 확인 후 이 메일에 답장해 주세요.",
        "",
        f"- 문의 번호: {ctx['ticket_id']} (하위 문의 {ctx['seq']})",
        f"- 고객사: {ctx['company'] or '—'} ({ctx['country'] or '—'})",
        f"- 유형 / 제품: {ctx['category_code'] or '—'} / {ctx['product_code'] or '—'}",
        f"- 이관 사유: {ctx['escalation_reason']}",
        f"- C/S 메모: {(memo or '').strip() or '—'}",
        f"- 문의 화면: {app_base_url.rstrip('/')}/tickets/{ctx['ticket_id']}",
        "",
        f"[고객 문의 원문 · 언어 {ctx['language']} · 개인정보 가림]",
        f"제목: {ctx['inquiry_subject'] or '—'}",
        original,
        "",
        "─" * 40,
        "이 메일에 답장하면 회신이 문의에 자동으로 연결되고, AI가 회신 내용을 근거로 고객 답변 초안을 다시 씁니다.",
        f"제목의 {TAG.format(sub_ticket_id=sub_ticket_id)} 표시는 지우지 마세요.",
    ]
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    message.set_content("\n".join(lines))
    return message


def build_dept_reply(conn: Connection, sub_ticket_id: str, body: str, *, cs_address: str, dept_domain: str) -> EmailMessage:
    """시연용: 부서 메일함에서 C/S로 보내는 답장. 실제 메일 프로그램이 만드는 모양(Re: 제목, 인용문)을 그대로 따른다.
    받는 쪽(`collect_replies`)은 이 답장과 실제 메일 프로그램의 답장을 구분하지 않는다."""
    ctx = _context(conn, sub_ticket_id)
    if not ctx["escalated_to"]:
        raise LookupError(sub_ticket_id)
    note = conn.execute("""SELECT body FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE'
                              AND message_status = 'SENT' ORDER BY message_id DESC LIMIT 1""", (sub_ticket_id,)).fetchone()
    original = f"{TAG.format(sub_ticket_id=sub_ticket_id)} {ctx['ticket_id']} 이관 요청 · {ctx['escalation_reason']}"
    quoted = "\n".join(f"> {line}" for line in (note[0] if note else "").split("\n"))
    sender = dept_address(ctx["escalated_to"], dept_domain)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = cs_address
    message["Subject"] = f"Re: {original}"
    message["Message-ID"] = make_msgid(domain=dept_domain)
    message.set_content(f"{body.strip()}\n\nOn {ctx['ticket_id']}, {cs_address} wrote:\n{quoted}\n")
    return message


def send_request(conn: Connection, sender_client: Sender, sub_ticket_id: str, memo: str | None, *, sender: str,
                 dept_domain: str, app_base_url: str) -> MailResult:
    """만들고 보낸다. SMTP 오류는 결과에 담아 돌려주고 이관을 되돌리지 않는다."""
    message = build_request(conn, sub_ticket_id, memo, sender=sender, dept_domain=dept_domain, app_base_url=app_base_url)
    try:
        sender_client.send(message)
    except (OSError, smtplib.SMTPException) as exc:
        return MailResult(message["To"], message["Subject"], False, f"메일을 보내지 못함: {exc}")
    return MailResult(message["To"], message["Subject"], True)
