"""이관 처리 완료 기준 (FR-033 처리 1~7, 변경 add-escalation).

AC-033-1·2·4와 예외는 접수 API로 처리한 문의를 이관 API로 이관한다(대역 언어 모델, 롤백).
AC-033-5는 정답의 이관 부서·사유를 읽는 재생 시험이다(CLAUDE.md 규칙 6 예외, 팀 정답지 대신 tickets.csv, C-156).
AC-033-3·6·7은 변경 add-dept-reply, AC-033-8은 test_agent_roster.py가 확인한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.sla.clock import clocks
from app.status.escalation import (
    MSG_ALREADY, MSG_NO_REASON, MSG_NOT_IN_PROGRESS, MSG_SAME_DEPT, REASONS, EscalateError, escalate,
)
from app.status.transitions import transition
from tests.acceptance.test_status_sla import seed
from tests.acceptance.test_ticket_detail import api, index, info_request, rows  # noqa: F401  (api·index 픽스처)

AGENT = "TS_LV_AGENT_09"


def post(api, sub_id, **data):
    return api[0].post(f"/sub-tickets/{sub_id}/escalate", json=data, headers={"X-Agent-Id": AGENT})


def sub_of(detail):
    return detail["sub_tickets"][0]["sub_ticket"]["sub_ticket_id"]


def test_ac_033_1_field_svc(api):
    """AC-033-1: CSV1-000017(이관 후보 FIELD_SVC)을 ONSITE_REQUIRED로 이관 → ESCALATED, FIELD_SVC 접수함에 이관됨, 안내 초안 없음."""
    detail = info_request(api)
    sub_id = sub_of(detail)
    drafts_before = api[2].execute("SELECT count(*) FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_status = 'DRAFT'",
                                   (sub_id,)).fetchone()[0]
    res = post(api, sub_id, dept="FIELD_SVC", reason_code="ONSITE_REQUIRED", memo="Site visit needed for ACB trip.")
    assert res.status_code == 200, res.text
    assigned = res.json()["assigned_dept"]
    status, escalated, to, reason, dept = api[2].execute(
        "SELECT status, escalated, escalated_to, escalation_reason, assigned_dept FROM svc.sub_ticket WHERE sub_ticket_id = %s",
        (sub_id,)).fetchone()
    assert (status, escalated, to, reason, dept) == ("ESCALATED", True, "FIELD_SVC", "ONSITE_REQUIRED", assigned)  # 원래 부서 그대로
    note = api[2].execute("""SELECT sender, message_status, body, sent_by_name FROM svc.ticket_message
                              WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE'""", (sub_id,)).fetchall()
    assert note == [("AGENT", "SENT", "Site visit needed for ACB trip.", AGENT)]
    last = api[2].execute("""SELECT event_kind, changed_by, reason FROM svc.ticket_status_history WHERE sub_ticket_id = %s
                              ORDER BY history_id DESC LIMIT 1""", (sub_id,)).fetchone()
    assert last == ("ESCALATE", AGENT, "ONSITE_REQUIRED")
    after = api[2].execute("SELECT count(*) FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_status = 'DRAFT'",
                           (sub_id,)).fetchone()[0]
    assert after == drafts_before  # 이관 안내 초안은 만들지 않는다(처리 5)
    inbox = api[0].get("/tickets", params={"dept": "FIELD_SVC"}).json()["rows"]
    (row,) = [r for r in inbox if r["sub_ticket_id"] == sub_id]
    assert row["escalated_in_from"] == assigned and row["status"] == "ESCALATED"
    assert sub_id in {r["sub_ticket_id"] for r in api[0].get("/tickets", params={"dept": assigned}).json()["rows"]}
    shown = api[0].get(f"/tickets/{detail['ticket']['ticket_id']}").json()
    c04 = rows(shown)["C-04"]["evidence"]
    assert any(e.startswith("→ FIELD_SVC (ONSITE_REQUIRED, ") for e in c04)
    assert shown["sub_tickets"][0]["sub_ticket"]["escalated_to"] == "FIELD_SVC" and shown["sub_tickets"][0]["escalated_at_utc"]


def test_ac_033_2_no_reason(api):
    """AC-033-2: 사유가 빈 이관 → 거부("이관 사유를 고르세요"), 상태 그대로."""
    sub_id = sub_of(info_request(api))
    res = post(api, sub_id, dept="FIELD_SVC", reason_code="")
    assert (res.status_code, res.json()["detail"]) == (400, MSG_NO_REASON)
    assert api[2].execute("SELECT status, escalated_to FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                          (sub_id,)).fetchone() == ("IN_PROGRESS", None)


def test_ac_033_4_sla_keeps_running(api):
    """AC-033-4: ESCALATED 동안 해결 경과가 계속 늘어난다(대기 구간은 WAITING_CUSTOMER만, 처리 7)."""
    sub_id = sub_of(info_request(api))
    assert post(api, sub_id, dept="FIELD_SVC", reason_code="ONSITE_REQUIRED").status_code == 200
    now = datetime.now(timezone.utc)
    a = clocks(api[2], [sub_id], as_of=now + timedelta(hours=1))[sub_id]
    b = clocks(api[2], [sub_id], as_of=now + timedelta(hours=5))[sub_id]
    assert float(b["res_elapsed_h"]) - float(a["res_elapsed_h"]) == pytest.approx(4, abs=0.01)
    assert float(b["wait_h"]) == float(a["wait_h"]) == 0


def test_ac_033_5_replay_gold(conn):
    """AC-033-5: 정답에서 이관된 행마다 정답 이관 부서·사유로 이관을 재생 → 상태 전이와 기록이 오류 없이 끝난다."""
    gold = conn.execute("""SELECT ticket_id, assigned_dept, escalated_to, escalation_reason, received_at_utc::timestamptz
                             FROM gold.ticket_gold WHERE escalated = 'Y' ORDER BY ticket_id""").fetchall()
    failed = []
    with conn.transaction(force_rollback=True):
        for gid, assigned, to, reason, received in gold:
            sub_id = seed(conn, gid)
            conn.execute("UPDATE svc.sub_ticket SET assigned_dept = %s WHERE sub_ticket_id = %s", (assigned, sub_id))
            try:
                escalate(conn, sub_id, to, reason, None, AGENT, received + timedelta(hours=1))
            except EscalateError as exc:
                failed.append((gid, assigned, to, str(exc)))
        done = conn.execute("""SELECT count(*) FROM svc.sub_ticket s JOIN svc.ticket t USING (ticket_id)
                                WHERE t.source = 'REPLAY' AND s.status = 'ESCALATED'""").fetchone()[0]
    print(f"\nAC-033-5 이관 재생 {len(gold) - len(failed)}/{len(gold)}, 거부 {failed[:5]}")
    # 정답에는 1차 담당이 이미 이관 부서인 행이 있다(schema.sql "1차 담당이 이미 FIELD_SVC인 ONSITE_REQUIRED")
    assert all(f[3] == MSG_SAME_DEPT and f[1] == f[2] for f in failed)
    assert done == len(gold) - len(failed) > 0


def test_exceptions(api):
    """FR-033 예외: 이미 ESCALATED / 같은 부서 / 처리 중 아님 / 목록 밖 값 / 상담원 없음."""
    sub_id = sub_of(info_request(api))
    assigned = api[2].execute("SELECT assigned_dept FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()[0]
    same = post(api, sub_id, dept=assigned, reason_code="CAUSE_ANALYSIS")
    assert (same.status_code, same.json()["detail"]) == (400, MSG_SAME_DEPT)
    assert post(api, sub_id, dept="NOPE", reason_code="CAUSE_ANALYSIS").status_code == 400
    assert post(api, sub_id, dept="QA_CLAIM", reason_code="NOPE").status_code == 400
    assert api[0].post(f"/sub-tickets/{sub_id}/escalate", json={"dept": "QA_CLAIM", "reason_code": "RMA_REQUIRED"}).status_code == 400
    assert post(api, "NOPE-1", dept="QA_CLAIM", reason_code="RMA_REQUIRED").status_code == 404
    assert post(api, sub_id, dept="QA_CLAIM", reason_code="RMA_REQUIRED").status_code == 200
    again = post(api, sub_id, dept="RND_FW", reason_code="FW_UPDATE_FAILURE")
    assert (again.status_code, again.json()["detail"]) == (409, MSG_ALREADY.format(dept="QA_CLAIM"))
    body = api[2].execute("SELECT body FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE'",
                          (sub_id,)).fetchone()[0]
    assert body == "이관: QA_CLAIM (RMA_REQUIRED)"  # 메모가 없을 때(C-154)


def test_not_in_progress(conn):
    """처리 1, FR-025 예외 1행: IN_PROGRESS가 아니면(WAITING_CUSTOMER) 거부·실행 로그 기록, 상태 그대로. 버전이 다르면 동시 수정."""
    from app.status.transitions import ConcurrentChange
    with conn.transaction(force_rollback=True):
        sub_id = seed(conn, "CSV1-000017")
        with pytest.raises(ConcurrentChange):
            escalate(conn, sub_id, "FIELD_SVC", "ONSITE_REQUIRED", None, AGENT, datetime.now(timezone.utc), expected_version=-1)
        conn.execute("""INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                            language, body, sent_by_name) VALUES ('T-CSV1-000017', %s, 'AGENT', 'INFO_REQUEST', 'SENT', now(), 'en', 'x', %s)""",
                     (sub_id, AGENT))
        transition(conn, sub_id, "WAITING_CUSTOMER", "INFO_REQUEST_SENT", datetime.now(timezone.utc), AGENT)
        with pytest.raises(EscalateError) as exc:
            escalate(conn, sub_id, "FIELD_SVC", "ONSITE_REQUIRED", None, AGENT, datetime.now(timezone.utc))
        assert str(exc.value) == MSG_NOT_IN_PROGRESS
        assert conn.execute("SELECT status FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()[0] == "WAITING_CUSTOMER"
        step = conn.execute("""SELECT st.step_name, st.result, st.error_kind, st.error FROM svc.agent_step st
                                 JOIN svc.agent_run r USING (run_id) WHERE r.sub_ticket_id = %s ORDER BY st.step_id DESC LIMIT 1""",
                            (sub_id,)).fetchone()
        assert step == ("T6", "FAILED", "VALIDATION", MSG_NOT_IN_PROGRESS)  # 실행 로그에 거부 기록(FR-025 예외 1행)
    assert len(REASONS) == 11
