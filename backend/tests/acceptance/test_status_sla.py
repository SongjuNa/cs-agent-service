"""상태 관리와 SLA 두 시계 완료 기준 (FR-025, FR-026, 변경 add-status-and-sla).

발송은 API(TestClient)로, 자동 종료·SLA는 정답지 시각으로 만든 문의로 확인한다. DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from app.config import get_settings
from app.sla.clock import NOTE_NEGATIVE, NOTE_NO_TARGET, clocks
from app.status.closing import NO_REPLY, close_due
from app.status.transitions import MSG_CONCURRENT, TransitionRefused, current, history, transition
from jobs import replay_gold
from tests.acceptance.test_ticket_detail import (  # noqa: F401  (api·index 픽스처를 함께 쓴다)
    api, draft_ticket, index, info_request, only_draft, quote, send,
)

SNAPSHOT = replay_gold.SNAPSHOT
AGENT = "TS_LV_AGENT_09"


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def seed(conn, gold_id: str, *, targets=(16, 168), pipeline_done: bool = True) -> str:
    """정답지 문의의 입력으로 svc에 문의 하나를 만들고 접수·처리 끝 이력을 남긴다(롤백 안에서만 쓴다)."""
    received, channel, language, customer_id, tier, body = conn.execute(
        """SELECT received_at_utc::timestamptz, channel, language, customer_id, customer_tier, inquiry_body
             FROM gold.ticket_gold WHERE ticket_id = %s""", (gold_id,)).fetchone()
    ticket_id = f"T-{gold_id}"
    conn.execute(
        """INSERT INTO svc.ticket (ticket_id, received_at_utc, channel, language, customer_id, customer_tier,
               inquiry_body, source, source_ticket_id) VALUES (%s, %s, %s, %s, %s, %s, %s, 'REPLAY', %s)""",
        (ticket_id, received, channel, language, customer_id, tier, body[:2000], gold_id))
    sub_id = f"{ticket_id}-1"
    conn.execute("""INSERT INTO svc.sub_ticket (sub_ticket_id, ticket_id, seq, sla_first_response_target_h,
                        sla_resolution_target_h) VALUES (%s, %s, 1, %s, %s)""", (sub_id, ticket_id, *targets))
    transition(conn, sub_id, "NEW", "INTAKE", received, "SYSTEM")
    if pipeline_done:
        transition(conn, sub_id, "IN_PROGRESS", "PIPELINE_DONE", received, "SYSTEM")
    return sub_id


def sent(conn, sub_id: str, message_type: str, at: datetime) -> None:
    """발송 한 건(SENT 행 + 전이)을 사건 시각으로 남긴다."""
    to_status, event = {"INFO_REQUEST": ("WAITING_CUSTOMER", "INFO_REQUEST_SENT"),
                        "FINAL_REPLY": ("RESOLVED", "FINAL_REPLY_SENT")}[message_type]
    ticket_id = sub_id.rsplit("-", 1)[0]
    conn.execute("""INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status,
                        sent_at_utc, language, body, sent_by_name) VALUES (%s, %s, 'AGENT', %s, 'SENT', %s, 'en', 'x', %s)""",
                 (ticket_id, sub_id, message_type, at, AGENT))
    transition(conn, sub_id, to_status, event, at, AGENT)


@pytest.fixture
def db(conn):
    with conn.transaction(force_rollback=True):
        yield conn


@pytest.fixture(scope="module")
def replayed():
    """운영진 4,000건을 scoring에 재생(롤백해 남기지 않는다)."""
    with psycopg.connect(get_settings().database_url, autocommit=True) as c:
        with c.transaction(force_rollback=True):
            result = replay_gold.replay(c)
            sla = {r[0]: dict(zip(("fr_elapsed_h", "fr_status", "wait_h", "res_elapsed_h", "res_status"), r[1:]))
                   for r in c.execute("""SELECT sub_ticket_id, fr_elapsed_h, fr_status, wait_h, res_elapsed_h, res_status
                                           FROM scoring.inquiry_sla(%s)""", (SNAPSHOT,)).fetchall()}
            yield result, sla, c


# --- FR-025 상태 ---


def test_ac_025_1_info_request_sent(api):
    """AC-025-1: 정보 요청 발송 → WAITING_CUSTOMER, 이력에 시각·상담원·INFO_REQUEST_SENT (C-51: 처리 끝 T6 뒤라 IN_PROGRESS에서)."""
    draft = only_draft(info_request(api))
    res = send(api, draft)
    assert res.status_code == 200 and res.json()["status_changed"], res.text
    detail = api[0].get(f"/tickets/{draft_ticket(api[2], draft)}").json()
    sub = detail["sub_tickets"][0]
    assert sub["state"]["status"] == "WAITING_CUSTOMER" and detail["summary"]["status"] == "WAITING_CUSTOMER"
    last = sub["history"][-1]
    sent_at = api[2].execute("SELECT sent_at_utc FROM svc.ticket_message WHERE message_id = %s",
                             (res.json()["sent_message_id"],)).fetchone()[0]
    assert (last["from_status"], last["to_status"], last["event_kind"], last["changed_by"]) == \
        ("IN_PROGRESS", "WAITING_CUSTOMER", "INFO_REQUEST_SENT", AGENT)
    assert datetime.fromisoformat(last["changed_at_utc"]) == sent_at
    assert sub["wait_intervals"] == [{"entered_at_utc": last["changed_at_utc"], "left_at_utc": None}]


def test_ac_025_3_no_reply_closes_at_168h(db):
    """AC-025-3: CSV1-000085 정보 요청 2025-10-09 18:55:19, 시계를 2025-10-16 18:55:19로 → CLOSED, CLOSED_NO_RESPONSE."""
    sub_id = seed(db, "CSV1-000085")
    fr, resolved = db.execute("""SELECT first_response_at_utc::timestamptz, resolved_at_utc::timestamptz
                                   FROM gold.ticket_gold WHERE ticket_id = 'CSV1-000085'""").fetchone()
    assert fr == utc("2025-10-09T18:55:19")
    sent(db, sub_id, "INFO_REQUEST", fr)
    assert close_due(db, utc("2025-10-16T18:55:18")) == []
    assert close_due(db, utc("2025-10-16T18:55:19")) == [(sub_id, "NO_REPLY_168H", resolved)]
    status, final_action = db.execute("SELECT status, final_action FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                      (sub_id,)).fetchone()
    assert (status, final_action) == ("CLOSED", "CLOSED_NO_RESPONSE")
    assert history(db, sub_id)[-1]["changed_at_utc"] == resolved  # 정답지 resolved_at_utc와 같은 시각


def test_ac_025_4_new_to_resolved_refused(db):
    """AC-025-4: NEW 문의를 RESOLVED로 바로 바꾸면 거부되고 NEW 그대로."""
    received = db.execute("SELECT received_at_utc::timestamptz FROM gold.ticket_gold WHERE ticket_id = 'CSV1-003950'").fetchone()[0]
    new_id = seed(db, "CSV1-003950", pipeline_done=False)
    with pytest.raises(TransitionRefused) as exc:
        transition(db, new_id, "RESOLVED", "FINAL_REPLY_SENT", received, AGENT)
    assert str(exc.value) == "현재 상태(NEW)에서는 할 수 없는 작업"
    assert current(db, new_id)[0] == "NEW"


def test_resolved_then_168h_closes(db):
    """FR-025 처리 4-1, D20: 최종 답변 뒤 168시간 회신이 없으면 CLOSED. 그 전에는 그대로."""
    sub_id = seed(db, "CSV1-000004", targets=(4, 72))
    at = utc("2025-10-03T00:00:00")
    sent(db, sub_id, "FINAL_REPLY", at)
    assert close_due(db, at + NO_REPLY - timedelta(seconds=1)) == []
    assert close_due(db, at + NO_REPLY + timedelta(days=3)) == [(sub_id, "NO_REPLY_168H_AFTER_RESOLVED", at + NO_REPLY)]
    status, resolved = db.execute("SELECT status, resolved_at_utc FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                                  (sub_id,)).fetchone()
    assert status == "CLOSED" and resolved == at


def test_concurrent_change_refused(api):
    """FR-025 예외 2행: 같은 version을 읽은 두 사람 중 뒤 요청은 거부되고 아무것도 남지 않는다."""
    detail = info_request(api)
    draft = only_draft(detail)
    version = detail["sub_tickets"][0]["state"]["version"]
    client = api[0]
    first = client.post(f"/messages/{draft['message_id']}/send", headers={"X-Agent-Id": AGENT},
                        json={"final_body": draft["body"], "expected_version": version})
    assert first.status_code == 200, first.text
    # 다른 상담원이 예전 version으로 같은 문의를 바꾸려 한다(새 초안을 직접 만들어 보낸다)
    conn = api[2]
    ticket_id = draft_ticket(conn, draft)
    (other,) = conn.execute(
        """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
               language, body, sent_by_name) VALUES (%s, %s, 'SYSTEM', 'FINAL_REPLY', 'DRAFT', now(), 'en', 'Hello', 'SYSTEM')
           RETURNING message_id""", (ticket_id, f"{ticket_id}-1")).fetchone()
    before = conn.execute("SELECT count(*) FROM svc.ticket_message WHERE ticket_id = %s", (ticket_id,)).fetchone()[0]
    second = client.post(f"/messages/{other}/send", headers={"X-Agent-Id": "TS_LV_AGENT_10"},
                         json={"final_body": "Hello", "override_check": True, "expected_version": version})
    assert second.status_code == 409 and second.json()["detail"] == MSG_CONCURRENT
    assert conn.execute("SELECT count(*) FROM svc.ticket_message WHERE ticket_id = %s", (ticket_id,)).fetchone()[0] == before


def test_send_refused_transition_records_message(api):
    """FR-031 예외 3행: 허용되지 않은 전이면 발송 기록은 남기고 상태는 그대로, 실행 로그를 남긴다."""
    draft = only_draft(info_request(api))
    assert send(api, draft).status_code == 200  # → WAITING_CUSTOMER
    conn = api[2]
    ticket_id = draft_ticket(conn, draft)
    (reply,) = conn.execute(
        """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
               language, body, sent_by_name) VALUES (%s, %s, 'SYSTEM', 'FINAL_REPLY', 'DRAFT', now(), 'en', 'Hello', 'SYSTEM')
           RETURNING message_id""", (ticket_id, f"{ticket_id}-1")).fetchone()
    res = api[0].post(f"/messages/{reply}/send", headers={"X-Agent-Id": AGENT},
                      json={"final_body": "Hello", "override_check": True})
    assert res.status_code == 200, res.text
    assert not res.json()["status_changed"]
    assert "현재 상태(WAITING_CUSTOMER)에서는 할 수 없는 작업 — 메시지만 기록됨" in res.json()["notes"]
    assert current(conn, f"{ticket_id}-1")[0] == "WAITING_CUSTOMER"
    step = conn.execute("""SELECT s.result, s.error FROM svc.agent_step s JOIN svc.agent_run r USING (run_id)
                            WHERE r.ticket_id = %s AND s.step_name = 'T6' ORDER BY s.step_id DESC LIMIT 1""",
                        (ticket_id,)).fetchone()
    assert step[0] == "FAILED" and "WAITING_CUSTOMER" in step[1]


def test_status_code_does_not_import_llm():
    """CLAUDE.md 규칙 1, 명세서 그룹 4: 상태·SLA 코드는 언어 모델 호출 계층을 import하지 않는다."""
    root = Path(__file__).resolve().parents[2] / "app"
    for folder in ("status", "sla"):
        for path in (root / folder).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                assert not any(n.startswith("app.llm") for n in names), path


# --- FR-026 SLA ---


def test_ac_026_1_csv1_000017(replayed):
    """AC-026-1: 1차 응답 BREACHED, 해결 경과 약 8.76h(정답 8.7h, 0.1h 이내), 해결 MET."""
    sla = replayed[1]["CSV1-000017-1"]
    assert sla["fr_status"] == "BREACHED" and sla["res_status"] == "MET"
    assert sla["wait_h"] == Decimal("30.80") and abs(sla["res_elapsed_h"] - Decimal("8.7")) <= Decimal("0.1")


def test_ac_026_2_waiting(replayed):
    """AC-026-2: CSV1-003578 대기 100.9h, 경과 105.5h, ON_TRACK, 1차 응답 BREACHED."""
    sla = replayed[1]["CSV1-003578-1"]
    assert sla["fr_status"] == "BREACHED" and sla["res_status"] == "ON_TRACK"
    assert abs(sla["res_elapsed_h"] - Decimal("105.5")) <= Decimal("0.1")


def test_ac_026_3_at_risk(replayed):
    """AC-026-3: CSV1-003401 경과 323.0h(계산 322.94h, 0.1h 이내) → AT_RISK."""
    sla = replayed[1]["CSV1-003401-1"]
    assert sla["res_status"] == "AT_RISK" and abs(sla["res_elapsed_h"] - Decimal("323.0")) <= Decimal("0.1")


def test_ac_026_4_no_first_response(replayed):
    """AC-026-4: CSV1-003950 1차 응답 경과 20.0h → BREACHED."""
    sla = replayed[1]["CSV1-003950-1"]
    assert sla["fr_status"] == "BREACHED" and abs(sla["fr_elapsed_h"] - Decimal("20.0")) <= Decimal("0.1")


def test_ac_026_5_no_response_na(replayed):
    """AC-026-5: CSV1-000085(CLOSED_NO_RESPONSE) 해결 상태 N/A."""
    assert replayed[1]["CSV1-000085-1"]["res_status"] == "N/A"


def test_ac_026_6_replay_4000(replayed):
    """AC-026-6 (§10-1 3, 운영진 4,000건): 목표 100%, 해결 상태 100%, 1차 응답 상태·경과는 열린 항목만 빼고 일치.

    - 1차 응답 상태 2건(CSV1-003890, 003951)은 정답이 스냅샷 뒤의 1차 응답 시각으로 계산된 D19 행이다(C-53).
    - 무응답 종료 159건은 정답 대기 0h(경과 = 종료 − 접수)라 FR-026 처리 3(대기 구간 뺌)과 다르다(C-54).
    """
    result = replayed[0]
    summary = result.summary()
    for item in ("sla_first_response_target_h", "sla_resolution_target_h", "sla_resolution_status"):
        assert summary[item]["matched"] == 4000, item
    misses = {c["source_ticket_id"] for c in result.cases
              if c["item"] == "sla_first_response_status" and c["match_yn"] is False}
    assert misses == {"CSV1-003890", "CSV1-003951"}
    assert summary["sla_elapsed_hours"]["excluded_n"] == 10  # D19
    no_response = {r[0] for r in replayed[2].execute(
        "SELECT ticket_id FROM gold.ticket_gold WHERE final_action = 'CLOSED_NO_RESPONSE'").fetchall()}
    elapsed_miss = {c["source_ticket_id"] for c in result.cases
                    if c["item"] == "sla_elapsed_hours" and c["match_yn"] is False}
    assert elapsed_miss == no_response and len(no_response) == 159


def test_ac_025_5_status_replay_recorded(replayed):
    """AC-025-5(참고 지표, §10-3 "생성·존재 기록"): 4,000건 모두 상태 이력이 생기고 스냅샷 상태를 기록한다."""
    result, _, c = replayed
    assert result.rows == 4000 and result.events >= 8000
    (n,) = c.execute("SELECT count(DISTINCT sub_ticket_id) FROM scoring.ticket_status_history").fetchone()
    assert n == 4000


def test_fr_026_exceptions_notes(db):
    """FR-026 예외 1행(목표 없음 → "SLA 미정")과 3행(음수 경과 → 0, "시간 기록 확인 필요")."""
    sub_id = seed(db, "CSV1-003950", targets=(None, None))
    received = db.execute("SELECT received_at_utc::timestamptz FROM gold.ticket_gold WHERE ticket_id = 'CSV1-003950'").fetchone()[0]
    sla = clocks(db, [sub_id], as_of=received - timedelta(hours=2))[sub_id]
    assert sla["fr_status"] is None and sla["res_status"] is None
    assert sla["fr_elapsed_h"] == 0 and sla["res_elapsed_h"] == 0
    assert sla["notes"] == [NOTE_NO_TARGET, NOTE_NEGATIVE]


def test_detail_shows_status_and_sla(api):
    """FR-025·026 출력: 상세 API가 상태·version·두 시계·이력·대기 구간·해결 시각과 티켓 대표 상태를 준다."""
    draft = only_draft(quote(api))
    assert send(api, draft).status_code == 200
    detail = api[0].get(f"/tickets/{draft_ticket(api[2], draft)}").json()
    sub = detail["sub_tickets"][0]
    assert sub["state"]["status"] == "RESOLVED" and sub["state"]["resolved_at_utc"] is not None
    assert sub["sla"]["fr_status"] in ("MET", "BREACHED") and sub["sla"]["res_status"] in ("MET", "BREACHED")
    assert sub["sla"]["remaining_h"] is None and sub["sla"]["notes"] == []
    assert [h["event_kind"] for h in sub["history"]] == ["INTAKE", "PIPELINE_DONE", "FINAL_REPLY_SENT"]
    assert sub["wait_intervals"] == [] and sub["alerts"] == []
    assert detail["summary"]["status"] == "RESOLVED" and detail["summary"]["open_count"] == 0
