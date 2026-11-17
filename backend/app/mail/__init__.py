"""이관 메일 실제 발송·수신 (변경 add-escalation-mail-live).

이관할 때 부서 메일함으로 SMTP 메일을 보내고, 부서가 그 메일에 답장하면 받은 메일함(Mailpit API)에서 찾아
기존 부서 회신 처리(`register_reply`, via_mail)로 넘긴다. 이 패키지는 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).
"""

from app.mail.inbox import InboundMail, MailpitInbox
from app.mail.outbound import MailResult, SmtpSender, build_dept_reply, build_request, dept_address, send_request
from app.mail.replies import collect_replies, parse_tag, strip_quoted

__all__ = ["InboundMail", "MailResult", "MailpitInbox", "SmtpSender", "build_dept_reply", "build_request", "collect_replies", "dept_address",
           "parse_tag", "send_request", "strip_quoted"]
