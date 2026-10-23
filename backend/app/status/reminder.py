"""126시간 회신 요청 리마인드 (명세서 v1.5 FR-023, D29, 기술 명세서 v1.4 §6-4 주기 점검 2).

WAITING_CUSTOMER이고 마지막 정보 요청 발송 + 126시간이 지나도록 고객 회신이 없으면, 고정 문안 + 막는 항목 라벨로
PROGRESS_NOTICE(REMINDER)를 바로 SENT(보낸 쪽 SYSTEM)로 쓴다. 상태와 1차 응답 시각은 그대로, 문의당 한 번.
고객에게 가는 글 중 상담원 승인 없이 나가는 유일한 예외다(D32). 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from psycopg import Connection

from app.masking import mask_text
from app.status.closing import NO_REPLY

REMIND_AFTER = NO_REPLY * 0.75  # 126시간 = 무응답 종료 168시간의 75% (FR-023 기능 설명)
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "reminder"  # T40: 언어별 고정 문안 파일
FALLBACK_LANGUAGE = "en"
NOTE_ENGLISH = "영어로 발송"  # FR-023 예외 1행
SIGNATURE = ""  # 서명 문구는 팀이 정하지 않음(에이전트 설계서 부록 A-1, C-74)


def template(language: str) -> tuple[str, str]:
    """(쓴 언어, 문안). 그 언어 파일이 없으면 영어."""
    path = TEMPLATE_DIR / f"{language}.txt"
    if not path.exists():
        language, path = FALLBACK_LANGUAGE, TEMPLATE_DIR / f"{FALLBACK_LANGUAGE}.txt"
    return language, path.read_text(encoding="utf-8")


def render(language: str, ticket_id: str, labels: list[str]) -> tuple[str, str]:
    """(쓴 언어, 본문). 기한·완료 예정 시각·SLA 목표는 넣지 않는다(FR-023 처리 2, AC-023-8)."""
    used, text = template(language)
    body = text.format(ticket_id=ticket_id, missing_labels="\n".join(f"- {label}" for label in labels),
                       support_signature=SIGNATURE)
    return used, body.rstrip() + "\n"


def due_reminders(conn: Connection, as_of: datetime) -> list[tuple[str, str, datetime]]:
    """(sub_ticket_id, ticket_id, 마지막 정보 요청 발송 시각) — 대상 문의 (FR-023 처리 1, 예외 2행)."""
    return [tuple(r) for r in conn.execute(
        """SELECT s.sub_ticket_id, s.ticket_id, max(m.sent_at_utc) AS sent_at
             FROM svc.sub_ticket s
             JOIN svc.ticket_message m
               ON m.sub_ticket_id = s.sub_ticket_id AND m.message_type = 'INFO_REQUEST' AND m.message_status = 'SENT'
            WHERE s.status = 'WAITING_CUSTOMER'
              AND NOT EXISTS (SELECT 1 FROM svc.ticket_message x
                               WHERE x.sub_ticket_id = s.sub_ticket_id AND x.notice_transition = 'REMINDER')
            GROUP BY s.sub_ticket_id, s.ticket_id
           HAVING max(m.sent_at_utc) + %s <= %s
              AND NOT EXISTS (SELECT 1 FROM svc.ticket_message r
                               WHERE r.sub_ticket_id = s.sub_ticket_id AND r.message_type = 'CUSTOMER_REPLY'
                                 AND r.sent_at_utc > max(m.sent_at_utc))""",
        (REMIND_AFTER, as_of)).fetchall()]


def requested_fields(conn: Connection, sub_ticket_id: str) -> list[str]:
    """마지막으로 발송한 정보 요청의 요청 항목: 그 초안을 만든 실행의 Q7 결과(열이 없어 실행 기록에서 읽는다, C-73과 같음)."""
    row = conn.execute(
        """SELECT q7.output_json -> 'requested'
             FROM svc.ticket_message m
             JOIN svc.agent_step q13 ON q13.step_name = 'Q13' AND (q13.output_json ->> 'message_id')::bigint = m.source_draft_id
             JOIN svc.agent_step q7 ON q7.run_id = q13.run_id AND q7.step_name = 'Q7'
            WHERE m.sub_ticket_id = %s AND m.message_type = 'INFO_REQUEST' AND m.message_status = 'SENT'
            ORDER BY m.sent_at_utc DESC, q7.step_order DESC LIMIT 1""", (sub_ticket_id,)).fetchone()
    return list(row[0]) if row and row[0] else []


def send_reminders(conn: Connection, as_of: datetime) -> list[dict]:
    """대상마다 리마인드 SENT 한 행. 발송 시각 = 마지막 정보 요청 발송 + 126시간(점검 시각이 아님)."""
    out = []
    for sub_id, ticket_id, sent_at in due_reminders(conn, as_of):
        language, missing = conn.execute(
            """SELECT t.language, s.missing_info
                 FROM svc.sub_ticket s JOIN svc.ticket t ON t.ticket_id = s.ticket_id WHERE s.sub_ticket_id = %s""",
            (sub_id,)).fetchone()
        fields = requested_fields(conn, sub_id) or list(missing)  # FR-023 입력 "정보 요청에 쓴 빠진 항목"(C-77)
        labels = dict(conn.execute("SELECT field, label FROM ref.info_field WHERE field = ANY(%s)", (fields,)).fetchall())
        used, body = render(language, ticket_id, [labels.get(f, f) for f in fields])
        at = sent_at + REMIND_AFTER
        row = conn.execute(
            """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                   language, body, sent_by_name, notice_transition, mask_count)
               VALUES (%s, %s, 'SYSTEM', 'PROGRESS_NOTICE', 'SENT', %s, %s, %s, 'SYSTEM', 'REMINDER', %s)
               ON CONFLICT DO NOTHING RETURNING message_id""",
            (ticket_id, sub_id, at, used, body, mask_text(body)[1]),
        ).fetchone()
        if row:  # 부분 유일 색인이 두 번째 발송을 막는다(FR-023 예외 3행)
            out.append({"message_id": row[0], "sub_ticket_id": sub_id, "sent_at_utc": at, "language": used,
                        "body": body, "notes": [NOTE_ENGLISH] if used != language else []})
    return out


def reminder_of(conn: Connection, sub_ticket_id: str) -> dict | None:
    cur = conn.execute("""SELECT message_id, sent_at_utc, language, body, sender FROM svc.ticket_message
                           WHERE sub_ticket_id = %s AND notice_transition = 'REMINDER'""", (sub_ticket_id,))
    row = cur.fetchone()
    return dict(zip([d.name for d in cur.description], row)) if row else None


