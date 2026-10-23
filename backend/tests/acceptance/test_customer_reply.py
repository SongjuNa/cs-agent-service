"""고객 회신 입력과 메시지 이력 완료 기준 (FR-032, FR-035, 변경 add-customer-reply).

API를 TestClient로 부른다. 언어 모델은 대역 Transport, DB 쓰기는 바깥 트랜잭션을 롤백해 남기지 않는다.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import psycopg
import pytest

from app.db.replies import MSG_BEFORE_SENT, MSG_CLOSED, MSG_EMPTY, MSG_FUTURE, record_reply
from app.db.store import MSG_NO_NEW_FIELDS
from app.sla.adjust import adjust
from app.sla.clock import clocks
from app.status.transitions import transition
from tests.acceptance.test_drafts import FakeTransport, field
from tests.acceptance.test_status_sla import SNAPSHOT, seed, sent, utc
from tests.acceptance.test_ticket_detail import (  # noqa: F401  (api·index 픽스처를 함께 쓴다)
    INFO_REPLY, api, defect_l1, index, info_request, only_draft, send,
)

AGENT = "TS_LV_AGENT_09"
SERIAL = "Serial number is LVB-2024-00117."
L2_SERIAL = {"fields": [field("product_model", "ACB-AS-2000"), field("error_code", "overheating"),
                        field("serial_no", "LVB-2024-00117")]}
REPLY_BODY = ("The breaker trips because of overheating (TG-ACB-AS-2000 §3). "
              "Please check the ventilation and the load current.")


def waiting(api):
    """CSV1-000017: 접수 → serial_no 정보 요청 → 발송 → WAITING_CUSTOMER."""
    detail = info_request(api)
    res = send(api, only_draft(detail))
    assert res.status_code == 200, res.text
    return detail["ticket"]["ticket_id"]


def reply(api, ticket_id, body, l2, l3=None, l4=None, **extra):
    client, clients, _ = api
    clients.fake = FakeTransport(L2=[l2], L3=[l3 or INFO_REPLY], L4=[l4 or {"body": REPLY_BODY, "citations": [], "numbers_used": []}],
                                 L7=[{"gloss": "대역"}])
    res = client.post(f"/tickets/{ticket_id}/replies", headers={"X-Agent-Id": AGENT}, json={"body": body, **extra})
    return res, client.get(f"/tickets/{ticket_id}").json()


def live_drafts(detail):
    return [d for d in detail["sub_tickets"][0]["drafts"] if d["superseded_at"] is None and d["sent"] is None]


def test_ac_032_1_serial_reply(api):
    """AC-032-1: IN_PROGRESS, 대기 구간 닫힘, serial_no 추가, 막는 항목 없음, TG-ACB-AS-2000 인용 답변 초안."""
    ticket_id = waiting(api)
    res, detail = reply(api, ticket_id, SERIAL, L2_SERIAL)
    assert res.status_code == 201, res.text
    assert res.json()["transitions"] == [{"sub_ticket_id": f"{ticket_id}-1", "from": "WAITING_CUSTOMER", "to": "IN_PROGRESS"}]
    sub = detail["sub_tickets"][0]
    assert sub["state"]["status"] == "IN_PROGRESS" and detail["run"]["trigger"] == "CUSTOMER_REPLY"
    (interval,) = sub["wait_intervals"]
    assert interval["left_at_utc"] is not None
    assert "serial_no" in sub["sub_ticket"]["provided_info"] and sub["sub_ticket"]["missing_blocking_info"] == []
    (draft,) = live_drafts(detail)
    assert draft["message_type"] == "FINAL_REPLY" and "TG-ACB-AS-2000" in draft["body"]
    conn = api[2]
    src = conn.execute("SELECT source, source_message_id FROM svc.inquiry_field WHERE sub_ticket_id = %s AND field = 'serial_no'",
                       (f"{ticket_id}-1",)).fetchone()
    assert src == ("CUSTOMER_REPLY", res.json()["message_id"])


def test_ac_032_2_no_serial_re_request(api):
    """AC-032-2: IN_PROGRESS, serial_no 남음, "재요청" 표시 정보 요청 초안, "제공 항목 변화 없음"."""
    ticket_id = waiting(api)
    res, detail = reply(api, ticket_id, "We will check and let you know.", {"fields": []})
    assert res.status_code == 201, res.text
    sub = detail["sub_tickets"][0]
    assert sub["state"]["status"] == "IN_PROGRESS"
    assert sub["sub_ticket"]["missing_blocking_info"] == ["serial_no"]
    (draft,) = live_drafts(detail)
    assert draft["message_type"] == "INFO_REQUEST" and draft["re_request"] is True
    q1 = api[2].execute("""SELECT st.output_json FROM svc.agent_step st JOIN svc.agent_run r ON r.run_id = st.run_id
                            WHERE r.ticket_id = %s AND r.trigger = 'CUSTOMER_REPLY' AND st.step_name = 'Q1'""",
                        (ticket_id,)).fetchone()[0]
    assert q1["note"] == MSG_NO_NEW_FIELDS and q1["added_fields"] == []
    assert sub["customer_followups"] == 1  # 새 항목 없는 회신 = 재문의(FR-032 처리 6)
    # 처음 정보 요청 초안은 발송됨, 그 뒤 초안은 재요청
    assert [d["re_request"] for d in sub["drafts"] if d["message_type"] == "INFO_REQUEST"] == [False, True]


@pytest.fixture
def db(conn):
    with conn.transaction(force_rollback=True):
        yield conn


def test_ac_032_3_wait_closed(db):
    """AC-032-3: CSV1-003578 product_model 요청 뒤 WAITING, 스냅샷에 회신 → 대기 구간이 닫히고 대기 합 100.9h."""
    sub_id = seed(db, "CSV1-003578", targets=(24, 120))
    (fr,) = db.execute("SELECT first_response_at_utc::timestamptz FROM gold.ticket_gold WHERE ticket_id = 'CSV1-003578'").fetchone()
    assert fr == utc("2026-09-26T19:07:45Z")
    sent(db, sub_id, "INFO_REQUEST", fr)
    out = record_reply(db, sub_id.rsplit("-", 1)[0], "The model is PV-INV-SOLAR-25.", None, SNAPSHOT, None, AGENT)
    assert out["reprocess"] == [sub_id]
    later = SNAPSHOT + timedelta(hours=50)  # 회신 뒤에는 대기 시간이 더 늘지 않는다
    wait = clocks(db, [sub_id], as_of=later)[sub_id]["wait_h"]
    assert wait.quantize(Decimal("0.1"), ROUND_HALF_UP) == Decimal("100.9")  # 정답지 customer_wait_hours 100.9


def test_ac_032_5_before_request_refused(api):
    """AC-032-5: 회신 시각이 정보 요청 발송보다 앞이면 거부, 아무것도 저장하지 않는다."""
    ticket_id = waiting(api)
    conn = api[2]
    (sent_at,) = conn.execute("""SELECT sent_at_utc FROM svc.ticket_message WHERE ticket_id = %s
                                   AND message_status = 'SENT'""", (ticket_id,)).fetchone()
    res, detail = reply(api, ticket_id, SERIAL, L2_SERIAL, received_at=(sent_at - timedelta(minutes=1)).isoformat())
    assert res.status_code == 400 and res.json()["detail"] == MSG_BEFORE_SENT
    assert detail["sub_tickets"][0]["state"]["status"] == "WAITING_CUSTOMER"
    assert not [m for m in detail["messages"] if m["message_type"] == "CUSTOMER_REPLY"]


def test_empty_and_future_refused(api):
    """FR-032 예외 1행·입력 "미래 거부", 상담원 ID 없음."""
    ticket_id = waiting(api)
    client = api[0]
    res, _ = reply(api, ticket_id, "  ", L2_SERIAL)
    assert res.status_code == 400 and res.json()["detail"] == MSG_EMPTY
    res, _ = reply(api, ticket_id, SERIAL, L2_SERIAL, received_at="2999-01-01T00:00:00Z")
    assert res.status_code == 400 and res.json()["detail"] == MSG_FUTURE
    assert client.post(f"/tickets/{ticket_id}/replies", json={"body": SERIAL}).status_code == 400
    assert client.post("/tickets/NOPE/replies", headers={"X-Agent-Id": AGENT}, json={"body": SERIAL}).status_code == 404


def test_ac_032_4_and_035_3_message_order(api):
    """AC-035-3·AC-032-4(앞부분): 접수 → 정보 요청 발송 → 회신 → 답변 발송까지, 행 순서와 1차 응답 시각."""
    ticket_id = waiting(api)
    _, detail = reply(api, ticket_id, SERIAL, L2_SERIAL)
    (draft,) = live_drafts(detail)
    res = send(api, draft, override=True)
    assert res.status_code == 200, res.text
    detail = api[0].get(f"/tickets/{ticket_id}").json()
    got = [(m["message_type"], m["message_status"]) for m in detail["messages"]]
    assert got == [("INQUIRY", "RECEIVED"), ("INFO_REQUEST", "SENT"), ("CUSTOMER_REPLY", "RECEIVED"),
                   ("FINAL_REPLY", "SENT")]
    statuses = {(d["message_type"], d["message_status"]) for d in detail["sub_tickets"][0]["drafts"]
                if d["superseded_at"] is None}
    assert statuses == {("INFO_REQUEST", "APPROVED"), ("FINAL_REPLY", "APPROVED")}
    info_sent = next(m for m in detail["messages"] if m["message_type"] == "INFO_REQUEST")
    assert detail["sub_tickets"][0]["sub_ticket"]["first_response_at_utc"] == info_sent["sent_at_utc"]
    assert detail["sub_tickets"][0]["state"]["status"] == "RESOLVED"


def test_ac_035_4_sent_row_cannot_change(api):
    """AC-035-4: SENT 행 본문 수정은 거부된다."""
    ticket_id = waiting(api)
    conn = api[2]
    (mid,) = conn.execute("SELECT message_id FROM svc.ticket_message WHERE ticket_id = %s AND message_status = 'SENT'",
                          (ticket_id,)).fetchone()
    with pytest.raises(psycopg.errors.RaiseException):
        with conn.transaction():
            conn.execute("UPDATE svc.ticket_message SET body = 'x' WHERE message_id = %s", (mid,))


def test_closed_reply_recorded_only(db):
    """FR-032 예외 3행: CLOSED 문의는 메시지만 저장, 다시 처리 없음."""
    sub_id = seed(db, "CSV1-003578", targets=(24, 120))
    at = utc("2026-09-26T19:07:45Z")
    sent(db, sub_id, "INFO_REQUEST", at)
    transition(db, sub_id, "CLOSED", "NO_REPLY_168H", at + timedelta(hours=168), "SYSTEM", final_action="CLOSED_NO_RESPONSE")
    out = record_reply(db, sub_id.rsplit("-", 1)[0], "Sorry for the delay.", None, at + timedelta(hours=200), None, AGENT)
    assert out["reprocess"] == [] and out["transitions"] == [] and MSG_CLOSED in out["notes"]
    assert db.execute("SELECT status FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()[0] == "CLOSED"


def test_resolved_reply_reopens_and_stops_close(db):
    """FR-032 처리 2: RESOLVED에 168시간 안 회신 → IN_PROGRESS, 해결 뒤 자동 종료 없음."""
    from app.status.closing import close_due
    sub_id = seed(db, "CSV1-003578", targets=(24, 120))
    at = utc("2026-09-26T19:07:45Z")
    sent(db, sub_id, "FINAL_REPLY", at)
    out = record_reply(db, sub_id.rsplit("-", 1)[0], "It still trips.", None, at + timedelta(hours=10), None, AGENT)
    assert out["transitions"][0]["from"] == "RESOLVED"
    close_due(db, at + timedelta(hours=400))
    assert db.execute("SELECT status FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()[0] == "IN_PROGRESS"


def test_adjusted_priority_kept(api):
    """FR-011 예외 3행(C-69): 조정한 우선순위·목표는 회신 재처리 뒤에도 그대로, 규칙값은 다시 계산."""
    ticket_id = waiting(api)
    conn = api[2]
    sub_id = f"{ticket_id}-1"
    rule_priority, rule_id = conn.execute("SELECT priority, priority_rule_id FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                          (sub_id,)).fetchone()
    new = "P4" if rule_priority != "P4" else "P3"
    adjust(conn, sub_id, new, "OTHER", "시험용 조정", AGENT, conn.execute("SELECT now()").fetchone()[0], confirm_breach=True)
    before = conn.execute("""SELECT priority, sla_id, sla_first_response_target_h, sla_resolution_target_h
                               FROM svc.sub_ticket WHERE sub_ticket_id = %s""", (sub_id,)).fetchone()
    reply(api, ticket_id, SERIAL, L2_SERIAL)
    after = conn.execute("""SELECT priority, sla_id, sla_first_response_target_h, sla_resolution_target_h, priority_rule_id
                              FROM svc.sub_ticket WHERE sub_ticket_id = %s""", (sub_id,)).fetchone()
    assert after[:4] == before and after[0] == new and after[4] == rule_id


def test_reprocess_failure_keeps_reply(api):
    """FR-032 예외 4행: 재처리 중 언어 모델 실패 → 회신·전이 유지, 실패 표시."""
    from app.llm.client import LlmTimeout
    ticket_id = waiting(api)
    res, detail = reply(api, ticket_id, SERIAL, L2_SERIAL, l4=LlmTimeout("t"))
    assert res.status_code == 201
    assert detail["sub_tickets"][0]["state"]["status"] == "IN_PROGRESS"
    assert [m for m in detail["messages"] if m["message_type"] == "CUSTOMER_REPLY"]


def test_in_progress_reply_saved_only(api):
    """FR-032 처리 2·FR-025 예외 3행(C-72): WAITING·RESOLVED가 아니면 상태 그대로, 저장만, 다시 처리 없음."""
    detail = info_request(api)
    ticket_id = detail["ticket"]["ticket_id"]
    res, after = reply(api, ticket_id, SERIAL, L2_SERIAL)  # 발송 전(IN_PROGRESS) 회신
    assert res.status_code == 201 and res.json()["transitions"] == [] and res.json()["processing"] is False
    assert after["sub_tickets"][0]["state"]["status"] == "IN_PROGRESS" and after["run"]["trigger"] == "INTAKE"
    assert [m["message_type"] for m in after["messages"]] == ["INQUIRY", "CUSTOMER_REPLY"]


def test_previous_draft_superseded(api):
    """§2-4 재처리: 아직 DRAFT인 이전 초안은 superseded_at으로 밀린다."""
    ticket_id = waiting(api)
    conn = api[2]
    (old,) = conn.execute(
        """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
               language, body, sent_by_name) VALUES (%s, %s, 'SYSTEM', 'FINAL_REPLY', 'DRAFT', now(), 'en', 'old', 'SYSTEM')
           RETURNING message_id""", (ticket_id, f"{ticket_id}-1")).fetchone()
    _, detail = reply(api, ticket_id, SERIAL, L2_SERIAL)
    drafts = {d["message_id"]: d for d in detail["sub_tickets"][0]["drafts"]}
    assert drafts[old]["superseded_at"] is not None
    assert [d for d in live_drafts(detail) if d["message_type"] == "FINAL_REPLY"]


def test_ac_025_2_reply_closes_wait(api):
    """AC-025-2: WAITING_CUSTOMER 문의에 회신 → IN_PROGRESS, 대기 구간(들어간 시각, 나온 시각) 1개."""
    ticket_id = waiting(api)
    res, detail = reply(api, ticket_id, SERIAL, L2_SERIAL)
    sub = detail["sub_tickets"][0]
    assert sub["state"]["status"] == "IN_PROGRESS"
    (interval,) = sub["wait_intervals"]
    reply_at = next(m["sent_at_utc"] for m in detail["messages"] if m["message_type"] == "CUSTOMER_REPLY")
    assert interval["entered_at_utc"] is not None and interval["left_at_utc"] == reply_at


def test_messages_seq_filter(api):
    """FR-035 처리 7: 시각순 조회, 문의 순번 필터(INQUIRY는 티켓 전체라 순번 없음)."""
    from app.db.replies import messages
    ticket_id = waiting(api)
    reply(api, ticket_id, SERIAL, L2_SERIAL)
    conn = api[2]
    assert [m["message_type"] for m in messages(conn, ticket_id)] == ["INQUIRY", "INFO_REQUEST", "CUSTOMER_REPLY"]
    assert [m["message_type"] for m in messages(conn, ticket_id, seq=1)] == ["INFO_REQUEST", "CUSTOMER_REPLY"]


def test_reply_code_does_not_import_llm():
    """회신 저장 모듈은 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 2)."""
    src = Path(__file__).resolve().parents[2] / "app" / "db" / "replies.py"
    mods = {n.module for n in ast.walk(ast.parse(src.read_text(encoding="utf-8"))) if isinstance(n, ast.ImportFrom)}
    assert not any(m and m.startswith("app.llm") for m in mods)
