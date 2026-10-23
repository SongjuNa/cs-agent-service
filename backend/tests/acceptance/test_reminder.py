"""회신 요청 리마인드 완료 기준 (FR-023, AC-035-6, 변경 add-reminder).

문의는 정답지 입력으로 svc에 만들고(test_status_sla.seed) 정보 요청 발송을 사건 시각으로 남긴다. DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import ast
import re
from datetime import timedelta
from pathlib import Path

from app.db.replies import record_reply
from app.db.store import gloss_reminders
from app.scheduler import periodic_check
from app.status.reminder import NOTE_ENGLISH, REMIND_AFTER, reminder_of, send_reminders
from tests.acceptance.test_drafts import FakeTransport
from tests.acceptance.test_status_sla import db, seed, sent, utc  # noqa: F401  (db 픽스처를 함께 쓴다)
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처를 함께 쓴다)

AGENT = "TS_LV_AGENT_09"


def waiting(conn, gold_id="CSV1-000017", blocking=("serial_no",)):
    """정답지 1차 응답 시각에 정보 요청을 발송해 WAITING_CUSTOMER로 둔다."""
    sub_id = seed(conn, gold_id, targets=(4, 24))
    conn.execute("UPDATE svc.sub_ticket SET missing_blocking_info = %s, missing_info = %s WHERE sub_ticket_id = %s",
                 (list(blocking), list(blocking), sub_id))
    (fr,) = conn.execute("SELECT first_response_at_utc::timestamptz FROM gold.ticket_gold WHERE ticket_id = %s",
                         (gold_id,)).fetchone()
    sent(conn, sub_id, "INFO_REQUEST", fr)
    conn.execute("UPDATE svc.sub_ticket SET first_response_at_utc = %s WHERE sub_ticket_id = %s", (fr, sub_id))
    return sub_id, fr


def state(conn, sub_id):
    return conn.execute("SELECT status, first_response_at_utc, final_action FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                        (sub_id,)).fetchone()


def test_ac_023_5_english_reminder(db):
    """AC-023-5: 126시간 → 영어 리마인드 자동 발송(SYSTEM), 상태 WAITING_CUSTOMER, 1차 응답 시각 그대로."""
    sub_id, fr = waiting(db)
    assert periodic_check(db, fr + REMIND_AFTER - timedelta(minutes=1))["reminders"] == 0
    assert periodic_check(db, fr + REMIND_AFTER)["reminders"] == 1
    r = reminder_of(db, sub_id)
    assert (r["sender"], r["language"], r["sent_at_utc"]) == ("SYSTEM", "en", fr + timedelta(hours=126))
    assert "Serial number (nameplate)" in r["body"] and sub_id.rsplit("-", 1)[0] in r["body"]
    assert state(db, sub_id)[:2] == ("WAITING_CUSTOMER", fr)


def test_ac_023_6_closed_at_168h(db):
    """AC-023-6: 리마인드 뒤 42시간 더(168시간) → CLOSED_NO_RESPONSE."""
    sub_id, fr = waiting(db)
    periodic_check(db, fr + REMIND_AFTER)
    periodic_check(db, fr + REMIND_AFTER + timedelta(hours=42))
    assert state(db, sub_id)[0] == "CLOSED" and state(db, sub_id)[2] == "CLOSED_NO_RESPONSE"


def test_ac_023_7_reply_first(db):
    """AC-023-7: 120시간에 고객 회신 → 126시간에 리마인드 없음."""
    sub_id, fr = waiting(db)
    record_reply(db, sub_id.rsplit("-", 1)[0], "Serial is LVB-1.", None, fr + timedelta(hours=120), None, AGENT)
    assert send_reminders(db, fr + REMIND_AFTER) == [] and reminder_of(db, sub_id) is None


def test_ac_023_8_no_deadline(db):
    """AC-023-8: 본문에 SLA 목표 시간이나 완료 예정 시각이 없다."""
    sub_id, fr = waiting(db)
    (r,) = send_reminders(db, fr + REMIND_AFTER)
    body = r["body"]
    assert not re.search(r"\b\d+\s*(h|hours?|days?)\b", body, re.I)
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", body)
    assert not re.search(r"\b(deadline|within|by the end|expected|estimated)\b", body, re.I)


def test_only_once(db):
    """FR-023 처리 4·예외 3행: 두 번 점검해도 한 번."""
    sub_id, fr = waiting(db)
    assert len(send_reminders(db, fr + REMIND_AFTER)) == 1
    assert send_reminders(db, fr + REMIND_AFTER + timedelta(hours=1)) == []
    (n,) = db.execute("SELECT count(*) FROM svc.ticket_message WHERE sub_ticket_id = %s AND notice_transition = 'REMINDER'",
                      (sub_id,)).fetchone()
    assert n == 1


def test_no_template_sends_english(db):
    """FR-023 예외 1행: fr 템플릿이 없으면 영어로 보내고 "영어로 발송"."""
    sub_id, fr = waiting(db, "CSV1-000004", ("quantity",))
    assert db.execute("SELECT language FROM svc.ticket WHERE ticket_id = %s", (sub_id.rsplit("-", 1)[0],)).fetchone()[0] == "fr"
    (r,) = send_reminders(db, fr + REMIND_AFTER)
    assert r["language"] == "en" and r["notes"] == [NOTE_ENGLISH]


def test_gloss_attached(db):
    """§6-4 주기 점검 2: 리마인드에 한국어 대역을 붙인다. 대역 실패는 리마인드를 막지 않는다."""
    sub_id, fr = waiting(db)
    fake = FakeTransport(L7=[{"gloss": "고객님, 문의 건에 대해 명판의 제조번호를 보내 주세요. 감사합니다."}])
    result = periodic_check(db, fr + REMIND_AFTER, gloss_reminders(lambda: fake))
    assert result["reminders"] == 1 and result["glossed"] == 1
    (lang,) = db.execute("SELECT g.language FROM svc.message_gloss g JOIN svc.ticket_message m ON m.message_id = g.message_id "
                         "WHERE m.sub_ticket_id = %s", (sub_id,)).fetchone()
    assert lang == "ko"


def test_items_from_info_request_run(api):
    """FR-023 입력 "정보 요청에 쓴 빠진 항목"(C-77): 발송한 정보 요청 초안을 만든 실행의 Q7 항목을 쓴다."""
    from app.status.reminder import requested_fields
    from tests.acceptance.test_ticket_detail import info_request, only_draft, send
    draft = only_draft(info_request(api))
    assert send(api, draft).status_code == 200
    conn = api[2]
    (sub_id,) = conn.execute("SELECT sub_ticket_id FROM svc.ticket_message WHERE message_id = %s",
                             (draft["message_id"],)).fetchone()
    (missing,) = conn.execute("SELECT missing_info FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    assert requested_fields(conn, sub_id) == list(missing) and "serial_no" in missing


def test_gloss_failure_keeps_reminder(db):
    from app.llm.client import LlmTimeout
    sub_id, fr = waiting(db)
    result = periodic_check(db, fr + REMIND_AFTER, gloss_reminders(lambda: FakeTransport(L7=[LlmTimeout("t")])))
    assert result["reminders"] == 1 and result["glossed"] == 0 and reminder_of(db, sub_id) is not None


def test_ac_035_6_sender(db):
    """AC-035-6(앞부분): 리마인드 SENT 행은 보낸 쪽 SYSTEM, 그 밖의 SENT 행은 상담원(초안 행은 C-75)."""
    sub_id, fr = waiting(db)
    send_reminders(db, fr + REMIND_AFTER)
    rows = db.execute("""SELECT notice_transition, sender FROM svc.ticket_message
                          WHERE sub_ticket_id = %s AND message_status = 'SENT'""", (sub_id,)).fetchall()
    assert [s for n, s in rows if n == "REMINDER"] == ["SYSTEM"]
    assert all(s in ("AGENT", "DEPT") for n, s in rows if n != "REMINDER")  # 상담원(부서 상담원 포함, D34)


def test_reminder_code_does_not_import_llm():
    """리마인드 모듈은 언어 모델 호출 계층을 import하지 않는다(FR-023 수행 주체 "LLM을 쓰지 않음")."""
    src = Path(__file__).resolve().parents[2] / "app" / "status" / "reminder.py"
    mods = {n.module for n in ast.walk(ast.parse(src.read_text(encoding="utf-8"))) if isinstance(n, ast.ImportFrom)}
    assert not any(m and m.startswith("app.llm") for m in mods)
