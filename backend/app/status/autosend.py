"""자동 발송 실행과 사후 검수 (변경 add-auto-send, CLAUDE.md 규칙 3·D32 변경).

접수 처리가 끝난 문의가 자동 판정(rules/autosend.py)을 통과하고 **상담원 [승인하고 발송]이 보는 확인(send_issues)이 비어 있을 때만**
같은 발송 함수(db/store.send_draft)를 auto=True로 불러 보낸다(보내는 쪽 SYSTEM, 이름 AI_AUTO). 새 우회로는 없다.
실제 메일 전송은 연동되어 있지 않다. "보냄"은 상담원 발송과 같이 발송 기록을 남기는 것이다.
이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg import Connection

from app.db.detail import NOT_IN_MARK_3, verify_state
from app.db.runs import run_for_sub
from app.db.sendcheck import send_issues
from app.db.store import load_draft, send_draft
from app.config import get_settings
from app.rules.autosend import DEFAULT_RULES, normalize, validate, verdict

log = logging.getLogger(__name__)
AUTO_AGENT = "AI_AUTO"
SETTING_KEY = "rules"
MSG_NOT_AUTO = "자동 발송된 문의가 아님"
MSG_REVIEWED = "이미 검수함"


class AutoError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def load_rules(conn: Connection) -> dict[str, Any]:
    row = conn.execute("SELECT value FROM svc.auto_setting WHERE key = %s", (SETTING_KEY,)).fetchone()
    if row is None:  # 아직 저장한 적 없으면 기본값. 켜짐 여부는 환경 변수(AUTO_SEND_DEFAULT)가 정한다
        return normalize({**DEFAULT_RULES, "enabled": get_settings().auto_send_default})
    return normalize(row[0])


def save_rules(conn: Connection, value: Any, agent_id: str) -> dict[str, Any]:
    errors = validate(value)
    if errors:
        raise AutoError(" · ".join(errors), 400)
    rules = normalize(value)
    import json
    conn.execute(
        """INSERT INTO svc.auto_setting (key, value, updated_by) VALUES (%s, %s::jsonb, %s)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at_utc = now()""",
        (SETTING_KEY, json.dumps(rules), agent_id))
    return rules


def _facts(conn: Connection, sub_ticket_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """판정에 쓸 값과, 보낼 후보 초안(아직 DRAFT인 최신 최종 답변)."""
    channel, cat, prio, urgency, status, blocking, evidence, count = conn.execute(
        """SELECT t.channel, s.category_code, s.priority, s.urgency_flag, s.status, s.missing_blocking_info, s.evidence_json,
                  (SELECT count(*) FROM svc.sub_ticket x WHERE x.ticket_id = s.ticket_id)
             FROM svc.sub_ticket s JOIN svc.ticket t USING (ticket_id) WHERE s.sub_ticket_id = %s""", (sub_ticket_id,)).fetchone()
    f: dict[str, Any] = {"channel": channel, "category_code": cat, "priority": prio, "urgency_flag": urgency, "status": status,
                         "has_blocking_missing": bool(blocking), "has_evidence": bool(evidence), "inquiry_count": count,
                         "has_draft": False}
    row = conn.execute(
        """SELECT message_id FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_type = 'FINAL_REPLY'
              AND message_status = 'DRAFT' AND sender = 'SYSTEM' AND superseded_at IS NULL ORDER BY message_id DESC LIMIT 1""",
        (sub_ticket_id,)).fetchone()
    if row is None:
        return f, None
    draft = load_draft(conn, row[0])
    f["has_draft"] = draft is not None
    if draft is None:
        return f, None
    issues, _ = send_issues(conn, draft, draft["body"])
    f["issues"] = [i["text"] for i in issues]
    run = run_for_sub(conn, sub_ticket_id)
    f["failed_checks"] = conn.execute(
        """SELECT count(*) FROM eval.self_check WHERE run_id = %s AND sub_ticket_id = %s AND NOT passed_yn AND check_type <> ALL(%s)""",
        (run["run_id"] if run else None, sub_ticket_id, list(NOT_IN_MARK_3))).fetchone()[0]
    verify = conn.execute("""SELECT passed_yn, detail FROM eval.self_check WHERE message_id = %s AND check_type = 'VERIFY'
                              ORDER BY checked_at_utc DESC, check_id DESC LIMIT 1""", (draft["message_id"],)).fetchone()
    state, _, _ = verify_state(None if verify is None else {"passed_yn": verify[0], "detail": verify[1]}, draft["body"])
    f["verify_passed"] = state == "PASSED"
    return f, draft


def evaluate(conn: Connection, sub_ticket_id: str, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """이 문의를 지금 자동으로 보내도 되는지(보내지는 않는다). {auto, passed, blocked}."""
    f, _ = _facts(conn, sub_ticket_id)
    auto, passed, blocked = verdict(f, rules or load_rules(conn))
    return {"auto": auto, "passed": passed, "blocked": blocked}


def maybe_auto_send(conn: Connection, sub_ticket_id: str) -> dict[str, Any]:
    """판정이 통과하면 자동 발송한다. 돌려주는 값: {sent, message_id?, blocked}. 실패해도 예외를 올리지 않는 쪽은 호출하는 곳이 맡는다."""
    rules = load_rules(conn)
    if not rules["enabled"]:
        return {"sent": False, "blocked": ["자동 처리가 꺼져 있음"]}
    f, draft = _facts(conn, sub_ticket_id)
    auto, _, blocked = verdict(f, rules)
    if not auto or draft is None:
        return {"sent": False, "blocked": blocked}
    sent_id, refused = send_draft(conn, draft, draft["body"], AUTO_AGENT, False, auto=True)
    return {"sent": refused is None, "message_id": sent_id, "blocked": [refused] if refused else []}


def auto_send_ticket(conn: Connection, ticket_id: str) -> list[dict[str, Any]]:
    """티켓의 모든 하위 문의를 검토한다. 하나가 실패해도 다른 문의와 처리 결과는 그대로 둔다(자동 발송만 건너뜀)."""
    out = []
    for (sub_id,) in conn.execute("SELECT sub_ticket_id FROM svc.sub_ticket WHERE ticket_id = %s ORDER BY seq", (ticket_id,)).fetchall():
        try:
            with conn.transaction():
                out.append({"sub_ticket_id": sub_id, **maybe_auto_send(conn, sub_id)})
        except Exception:  # noqa: BLE001 — 자동 발송 실패는 처리 실패가 아니다. 초안은 남아 상담원이 확인한다
            log.exception("자동 발송 실패: %s", sub_id)
            out.append({"sub_ticket_id": sub_id, "sent": False, "blocked": ["자동 발송 중 오류"]})
    return out


def auto_message_id(conn: Connection, sub_ticket_id: str) -> int | None:
    row = conn.execute(
        """SELECT message_id FROM svc.ticket_message WHERE sub_ticket_id = %s AND sender = 'SYSTEM' AND sent_by_name = %s
              AND message_type = 'FINAL_REPLY' AND message_status = 'SENT' ORDER BY message_id DESC LIMIT 1""",
        (sub_ticket_id, AUTO_AGENT)).fetchone()
    return row[0] if row else None


def review(conn: Connection, sub_ticket_id: str, agent_id: str) -> dict[str, Any]:
    """사후 검수 완료를 기록한다. 자동 발송된 문의에만, 한 번만."""
    with conn.transaction():
        message_id = auto_message_id(conn, sub_ticket_id)
        if message_id is None:
            raise AutoError(MSG_NOT_AUTO, 409)
        if conn.execute("SELECT 1 FROM svc.auto_review WHERE message_id = %s", (message_id,)).fetchone():
            raise AutoError(MSG_REVIEWED, 409)
        reviewed_at = conn.execute("INSERT INTO svc.auto_review (message_id, reviewed_by) VALUES (%s, %s) RETURNING reviewed_at_utc",
                                   (message_id, agent_id)).fetchone()[0]
    return {"sub_ticket_id": sub_ticket_id, "message_id": message_id, "reviewed_by": agent_id, "reviewed_at_utc": reviewed_at}
