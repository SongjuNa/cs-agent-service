"""고객 회신 저장과 상태 전이 (명세서 v1.5 FR-032 처리 1·2, 예외 1~3행, FR-035 처리 2·5).

상담원이 대신 입력한 회신을 CUSTOMER_REPLY RECEIVED 한 행으로 원문 저장하고, 대상 문의가 WAITING_CUSTOMER·RESOLVED면
IN_PROGRESS로 바꾼다. 그 문의만 API가 백그라운드로 Q1부터 다시 처리한다(그 밖의 상태는 저장만, C-72). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

from app.masking import mask_text
from app.status.transitions import transition

MAX_REPLY = 2000  # FR-032 입력 "2,000자 이하(제안 상한)"
LANGUAGES = ("ar", "de", "en", "es", "fr", "id", "it", "ja", "pl", "pt", "ru", "th", "tr", "vi", "zh")  # schema.sql ticket.language
REOPEN = ("WAITING_CUSTOMER", "RESOLVED")  # §6-4 전이표 CUSTOMER_REPLY 2행

MSG_EMPTY = "회신 내용을 입력하세요"                        # FR-032 예외 1행
MSG_BEFORE_SENT = "회신 시각은 요청 발송 이후여야 합니다"    # 예외 2행
MSG_CLOSED = "종료 후 회신으로 기록됨"                       # 예외 3행
MSG_TOO_LONG = "길이 초과"                                   # FR-035 예외 3행 문구, 상한은 FR-032 입력
MSG_FUTURE = "회신 시각은 지금보다 뒤일 수 없습니다"         # 구현 선택 (입력 "미래 거부")
MSG_LANGUAGE = "지원하지 않는 언어"                          # 구현 선택
MSG_TARGET = "이 티켓의 문의가 아님"                         # 구현 선택
MSG_BEFORE_HISTORY = "회신 시각은 마지막 상태 변경 이후여야 합니다"  # 구현 선택 (상태 이력 순서 보호)


class ReplyError(ValueError):
    """회신 거부 (API는 400)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_reply(conn: Connection, ticket_id: str, body: str | None, language: str | None,
                 received_at: datetime | None, target_ids: list[str] | None, agent_id: str) -> dict[str, Any]:
    """회신을 저장하고 전이한다. 돌려주는 값: message_id, 전이 목록, 다시 처리할 문의, 안내 문구.

    티켓이 없으면 LookupError, 입력이 틀리면 ReplyError. 메시지와 전이는 한 트랜잭션이다.
    """
    ticket = conn.execute("SELECT language FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    if ticket is None:
        raise LookupError(ticket_id)
    if not (body or "").strip():
        raise ReplyError(MSG_EMPTY)
    if len(body) > MAX_REPLY:
        raise ReplyError(MSG_TOO_LONG)
    language = language or ticket[0]  # 기본값 = 고객 언어
    if language not in LANGUAGES:
        raise ReplyError(MSG_LANGUAGE)
    now = _now()
    at = received_at or now
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if at > now:
        raise ReplyError(MSG_FUTURE)

    status = dict(conn.execute("SELECT sub_ticket_id, status FROM svc.sub_ticket WHERE ticket_id = %s ORDER BY seq",
                               (ticket_id,)).fetchall())
    if target_ids:
        if any(t not in status for t in target_ids):
            raise ReplyError(MSG_TARGET)
        targets = list(dict.fromkeys(target_ids))
    else:  # 기본값 = 대기 중인 모든 문의, 없으면 티켓의 모든 문의
        targets = [s for s, st in status.items() if st == "WAITING_CUSTOMER"] or list(status)

    (last_sent,) = conn.execute(
        """SELECT max(sent_at_utc) FROM svc.ticket_message
            WHERE sub_ticket_id = ANY(%s) AND message_status = 'SENT' AND message_type IN ('INFO_REQUEST','FINAL_REPLY')""",
        (targets,)).fetchone()
    if last_sent is not None and at < last_sent:
        raise ReplyError(MSG_BEFORE_SENT)
    reopen = [s for s in targets if status[s] in REOPEN]
    (last_change,) = conn.execute("SELECT max(changed_at_utc) FROM svc.ticket_status_history WHERE sub_ticket_id = ANY(%s)",
                                  (reopen,)).fetchone()
    if last_change is not None and at < last_change:
        raise ReplyError(MSG_BEFORE_HISTORY)

    _, mask_count = mask_text(body)
    transitions, notes = [], []
    with conn.transaction():
        (message_id,) = conn.execute(
            """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                   language, body, sent_by_name, mask_count)
               VALUES (%s, %s, 'CUSTOMER', 'CUSTOMER_REPLY', 'RECEIVED', %s, %s, %s, 'CUSTOMER', %s) RETURNING message_id""",
            (ticket_id, targets[0] if len(targets) == 1 else None, at, language, body, mask_count),
        ).fetchone()
        for sub_id in targets:
            if status[sub_id] in REOPEN:
                transition(conn, sub_id, "IN_PROGRESS", "CUSTOMER_REPLY", at, agent_id)
                transitions.append({"sub_ticket_id": sub_id, "from": status[sub_id], "to": "IN_PROGRESS"})
    # 다시 처리는 IN_PROGRESS로 돌아온 문의만. 그 밖의 상태는 저장만 한다(FR-032 처리 2, FR-025 예외 3행, C-72)
    reprocess = [t["sub_ticket_id"] for t in transitions]
    if any(status[s] == "CLOSED" for s in targets):
        notes.append(MSG_CLOSED)
    if mask_count:
        notes.append(f"개인정보 {mask_count}곳(LLM·로그에는 가림)")  # FR-035 예외 4행
    return {"message_id": message_id, "targets": targets, "transitions": transitions, "reprocess": reprocess,
            "notes": notes}


def messages(conn: Connection, ticket_id: str, seq: int | None = None) -> list[dict[str, Any]]:
    """발송·수신 행을 시각순으로 (FR-035 처리 4·7). DRAFT·APPROVED 초안은 상세의 drafts가 보인다."""
    cur = conn.execute(
        """SELECT m.message_id, m.message_no, s.seq, m.sender, m.message_type, m.message_status, m.sent_at_utc,
                  m.language, m.body, m.sent_by_name, m.source_draft_id, m.edited_yn, m.mask_count, m.notice_transition
             FROM svc.ticket_message m LEFT JOIN svc.sub_ticket s ON s.sub_ticket_id = m.sub_ticket_id
            WHERE m.ticket_id = %s AND m.message_status IN ('SENT','RECEIVED') AND (%s::int IS NULL OR s.seq = %s)
            ORDER BY m.sent_at_utc, m.message_no""", (ticket_id, seq, seq))
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def customer_followups(conn: Connection, sub_ticket_id: str) -> int:
    """재문의 횟수(FR-032 처리 6, 제안 규칙): 회신 직전 대기 중이 아니었거나 새 제공 항목이 없던 회신의 수.

    svc.sub_ticket에 열이 없어 저장하지 않고 계산한다(C-70). 다시 처리가 실패해 추출이 없던 회신은 "새 항목 없음"으로 세지 않는다.
    """
    (n,) = conn.execute(
        """SELECT count(*) FROM svc.ticket_message m
            WHERE m.message_type = 'CUSTOMER_REPLY'
              AND (m.sub_ticket_id = %(s)s OR (m.sub_ticket_id IS NULL AND m.ticket_id =
                   (SELECT ticket_id FROM svc.sub_ticket WHERE sub_ticket_id = %(s)s)))
              AND (NOT EXISTS (SELECT 1 FROM svc.ticket_status_history h
                                WHERE h.sub_ticket_id = %(s)s AND h.event_kind = 'CUSTOMER_REPLY'
                                  AND h.from_status = 'WAITING_CUSTOMER' AND h.changed_at_utc = m.sent_at_utc)
                   OR (NOT EXISTS (SELECT 1 FROM svc.inquiry_field f
                                    WHERE f.sub_ticket_id = %(s)s AND f.source_message_id = m.message_id)
                       AND EXISTS (SELECT 1 FROM svc.agent_step st JOIN svc.agent_run r ON r.run_id = st.run_id
                                    WHERE r.ticket_id = m.ticket_id AND r.trigger = 'CUSTOMER_REPLY' AND st.step_name = 'Q1'
                                      AND (st.output_json ->> 'reply_message_id')::bigint = m.message_id)))""",
        {"s": sub_ticket_id}).fetchone()
    return n
