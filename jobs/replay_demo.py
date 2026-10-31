"""접수함 시연용 미해결 데이터 (기술 명세서 v1.4 §9 W6, 테이블 정의서 v1.3 "시연 데이터(W6)").

운영진 데이터에서 스냅샷에 끝나지 않은 365건 중 팀 정답지 문의(D30)를 뺀 360건을 정답지 시각으로 svc에 재생한다.
접수 → 정보 요청 SENT → 대기 구간 → 현재 상태. 담당 상담원(assignee_masked)은 명단 이름으로 바꿔 넣는다(C-131).

정답 열을 읽는다. CLAUDE.md 규칙 6의 예외로, 조장 결정 2026-10-29(1안): 시연 데이터를 한 번 넣는 이 적재 작업만
gold.ticket_gold를 읽는다. 서비스 실행 코드(backend/app)는 계속 gold.v_inputs만 읽는다.

메시지는 FR-035 처리 6번대로 INQUIRY(RECEIVED), INFO_REQUEST(SENT, 시각 = 1차 응답, 정보 요청을 보낸 문의),
FINAL_REPLY(SENT, 시각 = 해결, 답이 있을 때)만 만든다. 지난 일을 옮겨 적는 것이라 승인 API를 거치지 않는다.

이미 svc에 있는 번호는 건너뛴다(메시지·이력은 지울 수 없어 다시 돌려도 겹치지 않게).

실행: 저장소 루트에서 python -m jobs.replay_demo   (뒤에 SLA 경고를 한 번 점검해 스냅샷 기준 경고를 단다)
"""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg import Connection

from app.config import get_settings
from app.db.assignees import name_of
from app.masking.mask import mask_text
from app.rules.sla import find_sla_target
from app.sla.alerts import raise_alerts
from jobs.replay_gold import SNAPSHOT, Gold, events_of

OPEN = ("NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED")
# 팀 정답지 v1 문의 중 미해결인 5건(기술 명세서 v1.4 W6). eval.gold_set이 적재돼 있으면 그 원본 번호도 뺀다(§6-1 D30)
TEAM_GOLD_5 = ("CSV1-003290", "CSV1-003742", "CSV1-003774", "CSV1-003820", "CSV1-003888")

# replay_gold.GOLD_SQL과 같은 순서의 앞 23열 + svc에 넣을 분류·배정·정보 열
DEMO_SQL = """
SELECT ticket_id, received_at_utc::timestamptz, channel, language, customer_id, customer_tier, inquiry_body,
       category_code, priority, status, escalated = 'Y', escalation_reason, info_request_sent = 'Y',
       first_response_at_utc::timestamptz, resolved_at_utc::timestamptz, customer_wait_hours::numeric,
       final_action, sla_first_response_target_h::int, sla_resolution_target_h::int,
       sla_first_response_status, sla_resolution_status, sla_elapsed_hours::numeric, assignee_masked,
       body_language, locale, contact_email_masked, inquiry_subject, product_code, urgency_flag,
       error_code_reported, fw_version_reported, priority_rule_id, priority_adjusted_by_agent = 'Y',
       routing_rule_id, assigned_dept, escalated_to, required_info, provided_info, missing_info,
       missing_blocking_info, info_request_message, final_reply
  FROM gold.ticket_gold
 WHERE status = ANY(%s) AND ticket_id <> ALL(%s)
 ORDER BY ticket_id"""


def _list(value: str | None) -> list[str]:
    """정답지의 ';' 목록 → 배열. 빈 값·NONE은 빈 배열."""
    if not value or value == "NONE":
        return []
    return [v for v in value.split(";") if v]


def _blank(value: str | None) -> str | None:
    return value or None


def excluded_ids(conn: Connection) -> list[str]:
    rows = conn.execute("SELECT source_ticket_id FROM eval.gold_set WHERE source_ticket_id IS NOT NULL").fetchall()
    return sorted(set(TEAM_GOLD_5) | {r[0] for r in rows})


def read_demo(conn: Connection, statuses: tuple[str, ...] = OPEN) -> list[tuple[Gold, dict]]:
    """정답지에서 이 상태인 문의를 읽는다. 처음에는 미해결(OPEN)만, 변경 add-dashboard-history는 해결·종료도 쓴다."""
    out = []
    for r in conn.execute(DEMO_SQL, (list(statuses), excluded_ids(conn))).fetchall():
        g = Gold(*r[:23])
        (body_language, locale, contact, subject, product, urgency, error_code, fw, rule, adjusted, routing, dept,
         escalated_to, required, provided, missing, blocking, info_message, final_reply) = r[23:]
        out.append((g, {
            "body_language": _blank(body_language), "locale": _blank(locale), "contact": _blank(contact),
            "subject": _blank(subject), "product": _blank(product), "urgency": urgency or "NONE",
            "error_code": _blank(error_code), "fw": _blank(fw), "rule": _blank(rule), "adjusted": bool(adjusted),
            "routing": _blank(routing), "dept": _blank(dept), "escalated_to": _blank(escalated_to),
            "required": _list(required), "provided": _list(provided), "missing": _list(missing),
            "blocking": _list(blocking), "info_message": _blank(info_message), "final_reply": _blank(final_reply),
        }))
    return out


def _message(conn: Connection, g: Gold, sub_id: str | None, sender: str, kind: str, status: str,
             at: datetime, body: str, by: str) -> None:
    _, masked = mask_text(body)
    conn.execute(
        """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
               language, body, sent_by_name, mask_count)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (g.ticket_id, sub_id, sender, kind, status, at, g.language, body[:5000], by, masked),
    )


def replay_one(conn: Connection, g: Gold, x: dict) -> None:
    sub_id = f"{g.ticket_id}-1"
    target = find_sla_target(conn, g.category, g.tier, g.priority)  # 정답 우선순위로 목표 조회(§10-1 3과 같다)
    assignee = name_of(g.assignee)
    conn.execute(
        """INSERT INTO svc.ticket (ticket_id, received_at_utc, channel, language, body_language, locale, customer_id,
               customer_tier, contact_email_masked, inquiry_subject, inquiry_body, source, source_ticket_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'REPLAY', %s)""",
        (g.ticket_id, g.received, g.channel, g.language, x["body_language"], x["locale"], g.customer_id, g.tier,
         x["contact"], x["subject"], g.body[:2000], g.ticket_id),
    )
    conn.execute(
        """INSERT INTO svc.sub_ticket (sub_ticket_id, ticket_id, seq, category_code, urgency_flag, product_code,
               error_code_reported, fw_version_reported, priority, priority_rule_id, priority_adjusted_by_agent,
               routing_rule_id, assigned_dept, sla_id, sla_first_response_target_h, sla_resolution_target_h,
               assignee_masked, escalated, escalated_to, escalation_reason, required_info, provided_info,
               missing_info, missing_blocking_info, info_request_sent)
           VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (sub_id, g.ticket_id, g.category, x["urgency"], x["product"], x["error_code"], x["fw"], g.priority,
         x["rule"], x["adjusted"], x["routing"], x["dept"], target.sla_id, target.sla_first_response_target_h,
         target.sla_resolution_target_h, assignee, g.escalated, x["escalated_to"],
         g.escalation_reason if g.escalated or x["escalated_to"] else None, x["required"], x["provided"],
         x["missing"], x["blocking"], g.info_sent),
    )
    _message(conn, g, None, "CUSTOMER", "INQUIRY", "RECEIVED", g.received, g.body, "CUSTOMER")
    for to_status, event, at in events_of(g):
        conn.execute("SELECT svc.transition(%s, %s, %s, %s, 'SYSTEM', %s, %s)",
                     (sub_id, to_status, event, at,
                      (g.escalation_reason or "이관(재생)") if event == "ESCALATE" else None,
                      "CLOSED_NO_RESPONSE" if event == "NO_REPLY_168H" else None))
        if event == "INFO_REQUEST_SENT" and x["info_message"]:
            _message(conn, g, sub_id, "AGENT", "INFO_REQUEST", "SENT", at, x["info_message"], assignee or "AGENT")
        if event == "FINAL_REPLY_SENT" and x["final_reply"]:
            _message(conn, g, sub_id, "AGENT", "FINAL_REPLY", "SENT", at, x["final_reply"], assignee or "AGENT")
    conn.execute("UPDATE svc.sub_ticket SET first_response_at_utc = %s WHERE sub_ticket_id = %s",
                 (g.first_response, sub_id))


def replay(conn: Connection, statuses: tuple[str, ...] = OPEN, limit: int | None = None) -> dict[str, int]:
    """svc에 없는 문의만 넣는다(기본은 미해결). 호출하는 쪽 트랜잭션 안에서 돈다.

    limit이 있으면 그 건수까지만 넣는다(많은 건을 나눠 넣을 때). 돌려주는 값: target = 정답지에서 읽은 건수,
    skipped = 이미 svc에 있어 건너뛴 건수, added = 이번에 넣은 건수.
    """
    have = {r[0] for r in conn.execute("SELECT ticket_id FROM svc.ticket").fetchall()}
    rows = read_demo(conn, statuses)
    pending = [(g, x) for g, x in rows if g.ticket_id not in have]
    for g, x in pending[:limit]:
        replay_one(conn, g, x)
    added = len(pending) if limit is None else min(limit, len(pending))
    return {"target": len(rows), "added": added, "skipped": len(rows) - len(pending)}


def main() -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        with conn.transaction():
            result = replay(conn)
        conn.execute("ANALYZE svc.ticket, svc.sub_ticket, svc.ticket_status_history, svc.ticket_message")
        with conn.transaction():
            alerts = raise_alerts(conn, SNAPSHOT)  # 스냅샷 기준 경고(FR-027). 실제 시각 점검은 스케줄러가 한다
    print(f"미해결 {result['target']}건 중 {result['added']}건 넣음, {result['skipped']}건 이미 있음. 스냅샷 경고 {len(alerts)}건")


if __name__ == "__main__":
    main()
