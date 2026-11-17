"""부서 회신 메일을 문의에 연결한다.

한 통마다: C/S 메일함으로 온 메일인가 → 제목에 [ESC:하위 문의 번호]가 있는가 → 보낸 사람이 그 문의를 이관받은 부서
메일함인가 → 인용문을 떼고 남은 본문이 있는가. 모두 통과하면 기존 [회신 등록](`register_reply`, via_mail=True)으로 넘긴다.
그래서 상태 전이·실행 로그·다시 처리(DEPT_REPLY)는 화면에서 회신을 등록할 때와 같다.
처리했든 건너뛰었든 "본 메일" 표시(태그)를 해서 같은 메일을 두 번 보지 않는다. 건너뛴 까닭은 결과에 남긴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from psycopg import Connection

from app.mail.inbox import Inbox, InboundMail
from app.mail.outbound import dept_address
from app.status.dept_reply import DeptError, register_reply
from app.status.transitions import ConcurrentChange

TAG_RE = re.compile(r"\[ESC:([A-Za-z0-9_-]+)\]")
# 답장에 붙는 원문 인용의 시작(영어·한국어 메일 프로그램)
_QUOTE_START = re.compile(r"^(On .+ wrote:|-{2,}\s*Original Message\s*-{2,}|-{5,}|_{5,}|From: .+|보낸 사람: .+|.+님이 작성:)\s*$",
                          re.IGNORECASE)


def parse_tag(subject: str) -> str | None:
    match = TAG_RE.search(subject or "")
    return match.group(1) if match else None


def strip_quoted(text: str) -> str:
    """답장 본문에서 인용한 원문(> 줄, "On ... wrote:" 아래)을 뗀다."""
    kept: list[str] = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if _QUOTE_START.match(line.strip()):
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


@dataclass
class Collected:
    accepted: list[dict] = field(default_factory=list)   # {sub_ticket_id, run_id, reply_message_id, mail_id}
    skipped: list[dict] = field(default_factory=list)    # {mail_id, subject, reason}


def _escalated_to(conn: Connection, sub_ticket_id: str) -> str | None:
    row = conn.execute("SELECT escalated_to FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_ticket_id,)).fetchone()
    return row[0] if row else None


def _one(conn: Connection, mail: InboundMail, cs_address: str, dept_domain: str, at: datetime) -> tuple[dict | None, str | None]:
    if cs_address.lower() not in mail.to:
        return None, "C/S 메일함으로 온 메일이 아님"
    sub_ticket_id = parse_tag(mail.subject)
    if not sub_ticket_id:
        return None, "제목에 이관 표시([ESC:…])가 없음"
    escalated_to = _escalated_to(conn, sub_ticket_id)
    if escalated_to is None:
        return None, f"이관된 문의를 찾을 수 없음({sub_ticket_id})"
    if mail.sender != dept_address(escalated_to, dept_domain):
        return None, f"이관받은 부서({escalated_to}) 메일함에서 온 메일이 아님"
    body = strip_quoted(mail.text)
    if not body:
        return None, "인용문을 빼면 본문이 없음"
    try:
        out = register_reply(conn, sub_ticket_id, body, f"MAIL:{mail.sender}", None, at, via_mail=True)
    except (DeptError, ConcurrentChange) as exc:
        return None, str(exc)
    return {"sub_ticket_id": sub_ticket_id, "run_id": out["run_id"], "reply_message_id": out["reply_message_id"],
            "mail_id": mail.id}, None


def collect_replies(conn: Connection, inbox: Inbox, *, cs_address: str, dept_domain: str, at: datetime) -> Collected:
    """아직 보지 않은 C/S 메일을 모두 보고, 연결한 회신과 건너뛴 메일을 돌려준다. 다시 처리는 부른 쪽이 한다."""
    result = Collected()
    seen: list[str] = []
    for mail in inbox.pending():
        accepted, reason = _one(conn, mail, cs_address, dept_domain, at)
        if accepted:
            result.accepted.append(accepted)
        else:
            result.skipped.append({"mail_id": mail.id, "subject": mail.subject, "reason": reason})
        seen.append(mail.id)
    inbox.mark_done(seen)
    return result
