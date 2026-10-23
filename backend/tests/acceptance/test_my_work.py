"""나의 업무 현황 완료 기준 (FR-047, 변경 add-my-work).

AC-047-1·3은 운영진 4,000건을 scoring에 재생하고(롤백) 시험 코드만 정답의 담당 부서를 넣는다(CLAUDE.md 규칙 6 예외:
정답과 비교하는 시험). AC-047-2·4·5·6은 API로 접수하고, AC-047-7은 우선순위 조정 시험과 같은 문의를 쓴다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.workload import EMPTY, MSG_NO_SCOPE, workload
from app.sla.adjust import adjust
from app.sla.alerts import raise_alerts
from app.status.transitions import transition
from tests.acceptance.test_inbox import snapshot  # noqa: F401  (snapshot 픽스처)
from tests.acceptance.test_priority_override import REASON, manual_p4
from tests.acceptance.test_status_sla import SNAPSHOT, db, replayed  # noqa: F401  (픽스처)
from tests.acceptance.test_ticket_detail import api, index, info_request, quote, send  # noqa: F401  (api 픽스처)

AGENT = "TS_LV_AGENT_09"


def mine(api, **params):
    res = api[0].get("/me/workload", params=params, headers={"X-Agent-Id": AGENT})
    assert res.status_code == 200, res.text
    return res.json()


def dept(api, name="TS_LV", **params):
    res = api[0].get("/me/workload", params={"dept": name, "scope": "dept", **params})
    assert res.status_code == 200, res.text
    return res.json()


def test_no_scope(api):
    """FR-047 예외 3행: 이름·부서를 고르지 않으면 그리지 않고 "상단에서 이름과 부서를 고르세요"."""
    got = api[0].get("/me/workload").json()
    assert got["message"] == MSG_NO_SCOPE == "상단에서 이름과 부서를 고르세요" and got["risks"] == []


def test_empty_areas(api):
    """FR-047 예외 1행: 대상이 없으면 타일 0과 영역별 빈 문구."""
    got = dept(api, "RND_FW")
    assert got["tiles"] == {"drafts": 0, "risks": 0, "waiting_customer": 0, "waiting_escalation": 0}
    assert got["empty"]["drafts"] == EMPTY["drafts"] == "승인 대기 초안이 없습니다"


def test_ac_047_2_pending_drafts(api):
    """AC-047-2: 정보 요청 초안이 DRAFT인 하위 문의 2건 → 승인 대기 타일 2, 목록 두 줄."""
    ids = {info_request(api)["ticket"]["ticket_id"] for _ in range(2)}
    got = dept(api)
    assert got["tiles"]["drafts"] == 2 and {r["ticket_id"] for r in got["drafts"]} == ids
    assert {r["message_type"] for r in got["drafts"]} == {"INFO_REQUEST"}
    assert all("has_check" in r and r["created_at_utc"] for r in got["drafts"])


def test_mine_uses_assignee(api):
    """§8-3, D33: 상담원을 고르면 내 담당 = assignee_masked. 부서 전체로 바꾸면 부서(assigned_dept) 전체."""
    d = info_request(api)
    assert mine(api)["scope"] == "mine" and mine(api)["tiles"]["drafts"] == 0  # 아직 아무도 맡지 않음
    api[2].execute("UPDATE svc.sub_ticket SET assignee_masked = %s WHERE ticket_id = %s", (AGENT, d["ticket"]["ticket_id"]))
    assert mine(api)["tiles"]["drafts"] == 1
    assert mine(api, scope="dept", dept="TS_LV")["tiles"]["drafts"] == 1


def escalate(api, ticket_id, at):
    """FR-033(3순위)이 할 이관을 시험 준비로만 한다: 이관 부서를 두고 ESCALATE 전이."""
    sub_id = f"{ticket_id}-1"
    api[2].execute("UPDATE svc.sub_ticket SET escalated = true, escalated_to = 'FIELD_SVC', escalation_reason = 'ONSITE_REQUIRED' "
                   "WHERE sub_ticket_id = %s", (sub_id,))
    transition(api[2], sub_id, "ESCALATED", "ESCALATE", at, AGENT, reason="현장 방문 필요")
    return sub_id


def test_ac_047_4_escalation_waiting(api):
    """AC-047-4: CSV1-000017을 FIELD_SVC로 이관, 부서 TS_LV → 이관 회신 대기에 이관 부서·이관 시각과 함께."""
    d = info_request(api)  # CSV1-000017 입력
    at = datetime.now(timezone.utc) - timedelta(hours=5)
    escalate(api, d["ticket"]["ticket_id"], at)
    got = dept(api)
    (row,) = got["waiting_escalation"]
    assert d["ticket"]["source_ticket_id"] == "CSV1-000017"
    assert (row["ticket_id"], row["escalated_to"]) == (d["ticket"]["ticket_id"], "FIELD_SVC")
    assert datetime.fromisoformat(row["escalated_at_utc"]) == at and 4.9 <= row["elapsed_h"] <= 5.1
    assert got["tiles"]["waiting_escalation"] == 1


def test_ac_047_5_today_counts(api):
    """AC-047-5: 오늘 이 상담원이 답변 1건 발송·이관 1건 → 발송 1, 이관 1."""
    q = quote(api)
    (draft,) = q["sub_tickets"][0]["drafts"]
    assert draft["message_type"] == "FINAL_REPLY" and send(api, draft).status_code == 200
    escalate(api, info_request(api)["ticket"]["ticket_id"], datetime.now(timezone.utc))
    assert mine(api)["today"] == {"sent": 1, "escalated": 1, "adjusted": 0}
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert mine(api, as_of=yesterday)["today"] == {"sent": 0, "escalated": 0, "adjusted": 0}  # 기준 시각의 날짜


def test_ac_047_6_rows_open_detail(api):
    """AC-047-6: 목록 행의 ticket_id로 상세가 열린다(화면 클릭은 브라우저로 확인)."""
    info_request(api)
    row = dept(api)["drafts"][0]
    res = api[0].get(f"/tickets/{row['ticket_id']}")
    assert res.status_code == 200 and res.json()["ticket"]["ticket_id"] == row["ticket_id"]


def test_ac_047_7_alert_after_adjust(db):
    """AC-047-7: 경고가 없던 P4(168h) 문의를 경과 100h에 P3(120h)로 올리면 경고가 생기고 위험 목록에 나타난다."""
    sub_id, received = manual_p4(db)
    db.execute("UPDATE svc.sub_ticket SET assigned_dept = 'GCS_L1', first_response_at_utc = %s WHERE sub_ticket_id = %s",
               (received + timedelta(hours=1), sub_id))
    at = received + timedelta(hours=100)
    raise_alerts(db, at, sub_ticket_ids=[sub_id])
    assert sub_id not in [r["sub_ticket_id"] for r in workload(db, "GCS_L1", as_of=at)["risks"]]
    adjust(db, sub_id, "P3", *REASON, AGENT, at)
    risks = workload(db, "GCS_L1", as_of=at)["risks"]
    (row,) = [r for r in risks if r["sub_ticket_id"] == sub_id]
    assert row["alerts"] == ["RES_AT_RISK"] and row["priority"] == "P3"


# --- 재생(스냅샷) ---


def test_ac_047_1_ts_lv_risks(snapshot):
    """AC-047-1: 미해결 360건 + 스냅샷 + 부서 TS_LV → 해결 AT_RISK 8 + BREACHED 26이 모두 있고 타일 35, 남은 시간 오름차순."""
    got = workload(snapshot, "TS_LV", as_of=SNAPSHOT, schema="scoring")
    risks = got["risks"]
    breached = [r for r in risks if "RES_BREACHED" in r["alerts"]]  # 위반 행에는 앞서 난 위험 경고도 남아 있다
    at_risk = [r for r in risks if "RES_AT_RISK" in r["alerts"] and r not in breached]
    assert (len(at_risk), len(breached)) == (8, 26)
    # 처리 2대로 1차 응답 경고도 넣어 CSV1-003951(FR_AT_RISK)이 더해져 35(AC-047-1, 2026-10-23 조장 결정 C-121)
    assert [r["sub_ticket_id"] for r in risks if r not in breached + at_risk] == ["CSV1-003951-1"]
    assert got["tiles"]["risks"] == len(risks) == 35
    assert [r["remaining_h"] for r in risks] == sorted(r["remaining_h"] for r in risks)
    assert got["sla_unset"] == 0


def test_ac_047_3_reminder_shown(snapshot):
    """AC-047-3: CSV1-003578 WAITING_CUSTOMER, 정보 요청 뒤 130h(리마인드 발송됨) → 경과 시간과 "리마인드 발송됨"."""
    c = snapshot
    sub_id = "CSV1-003578-1"
    c.execute("""UPDATE scoring.sub_ticket s SET assigned_dept = 'TS_ENERGY' WHERE sub_ticket_id = %s""", (sub_id,))
    sent_at = c.execute("""SELECT changed_at_utc FROM scoring.ticket_status_history
                            WHERE sub_ticket_id = %s AND event_kind = 'INFO_REQUEST_SENT'""", (sub_id,)).fetchone()[0]
    # 재생은 메시지를 만들지 않는다. 시험 준비로 정보 요청 발송과 126h 리마인드 행을 둔다(롤백)
    c.execute("""INSERT INTO scoring.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status,
                     sent_at_utc, language, body, sent_by_name)
                 VALUES ('CSV1-003578', %s, 'AGENT', 'INFO_REQUEST', 'SENT', %s, 'en', 'Please send the serial.', 'TS_ENERGY_AGENT_04')""",
              (sub_id, sent_at))
    c.execute("""INSERT INTO scoring.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status,
                     sent_at_utc, language, body, sent_by_name, notice_transition)
                 VALUES ('CSV1-003578', %s, 'SYSTEM', 'PROGRESS_NOTICE', 'SENT', %s, 'en', 'Reminder', 'SYSTEM', 'REMINDER')""",
              (sub_id, sent_at + timedelta(hours=126)))
    got = workload(c, "TS_ENERGY", as_of=sent_at + timedelta(hours=130), schema="scoring")
    (row,) = [r for r in got["waiting_customer"] if r["sub_ticket_id"] == sub_id]
    assert row["reminder_sent"] and row["elapsed_h"] == 130.0
    assert (row["remind_at_h"], row["close_at_h"]) == (126.0, 168.0)


def test_sla_unset_counted_apart(snapshot):
    """FR-047 예외 2행: SLA 미정 문의는 위험 목록에서 빼고 "SLA 미정 n건"으로 따로."""
    target = workload(snapshot, "TS_LV", as_of=SNAPSHOT, schema="scoring")["risks"][0]["sub_ticket_id"]
    snapshot.execute("UPDATE scoring.sub_ticket SET sla_id = NULL WHERE sub_ticket_id = %s", (target,))
    got = workload(snapshot, "TS_LV", as_of=SNAPSHOT, schema="scoring")
    assert target not in [r["sub_ticket_id"] for r in got["risks"]] and got["sla_unset"] == 1
    assert got["tiles"]["risks"] == 34


@pytest.mark.parametrize("scope", ["mine", "dept"])
def test_scope_param(api, scope):
    """C-118: scope를 주지 않으면 상담원이 있을 때 내 담당, 부서만 있으면 부서 전체."""
    got = api[0].get("/me/workload", params={"dept": "TS_LV", "scope": scope}, headers={"X-Agent-Id": AGENT}).json()
    assert got["scope"] == scope
    assert api[0].get("/me/workload", params={"dept": "TS_LV"}).json()["scope"] == "dept"
