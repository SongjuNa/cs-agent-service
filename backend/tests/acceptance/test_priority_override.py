"""우선순위 조정과 SLA 재계산 완료 기준 (FR-028, AC-027-5, 변경 add-priority-override).

문의는 정답지 입력으로 svc에 만들고(test_status_sla.seed) 규칙 결과 P4(PR-07)로 둔다. DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_conn
from app.main import app
from app.rules.sla import find_sla_target
from app.sla.adjust import MSG_BAD_KIND, MSG_BREACH, MSG_CLOSED, MSG_NO_REASON, MSG_SAME, AdjustError, adjust, adjustments
from app.sla.alerts import alert_history, raise_alerts
from app.status.transitions import ConcurrentChange
from tests.acceptance.test_status_sla import db, seed, sent  # noqa: F401  (db 픽스처를 함께 쓴다)

AGENT = "TS_LV_AGENT_09"
REASON = ("CUSTOMER_REQUEST", "고객이 납기 확인을 서둘러 요청")


def manual_p4(conn):
    """CSV1-000031: MANUAL × STANDARD, 규칙 PR-07 → P4, 목표 72/168h."""
    sub_id = seed(conn, "CSV1-000031", targets=(72, 168))
    conn.execute("""UPDATE svc.sub_ticket SET category_code = 'MANUAL', priority = 'P4', priority_rule_id = 'PR-07',
                        sla_id = 'SLA-MANUAL-STANDARD-P4' WHERE sub_ticket_id = %s""", (sub_id,))
    received = conn.execute("SELECT received_at_utc FROM svc.ticket WHERE ticket_id = %s",
                            (sub_id.rsplit("-", 1)[0],)).fetchone()[0]
    return sub_id, received


def row(conn, sub_id):
    return conn.execute("""SELECT priority, priority_rule_id, priority_adjusted_by_agent, sla_id,
                                  sla_first_response_target_h, sla_resolution_target_h
                             FROM svc.sub_ticket WHERE sub_ticket_id = %s""", (sub_id,)).fetchone()


def test_ac_028_1_p4_to_p3(db):
    """AC-028-1: P3로 바꾸면 24/120h(SLA-MANUAL-STANDARD-P3), PR-07 그대로, 이력에 이전·새 값과 사유."""
    sub_id, received = manual_p4(db)
    at = received + timedelta(hours=1)
    out = adjust(db, sub_id, "P3", *REASON, AGENT, at)
    assert row(db, sub_id) == ("P3", "PR-07", True, "SLA-MANUAL-STANDARD-P3", 24, 120)
    assert out["to_fr_target_h"] == 24 and out["to_res_target_h"] == 120 and out["sla"]["res_target_h"] == 120
    (h,) = adjustments(db, sub_id)
    assert (h["from_priority"], h["to_priority"], h["from_sla_id"], h["to_sla_id"]) == \
        ("P4", "P3", "SLA-MANUAL-STANDARD-P4", "SLA-MANUAL-STANDARD-P3")
    assert (h["from_fr_target_h"], h["from_res_target_h"], h["to_fr_target_h"], h["to_res_target_h"]) == (72, 168, 24, 120)
    assert (h["reason_kind"], h["reason"], h["adjusted_by"], h["adjusted_at_utc"]) == (*REASON, AGENT, at)


def test_ac_028_2_no_reason(db):
    """AC-028-2: 사유가 비면 거부되고 값이 그대로."""
    sub_id, received = manual_p4(db)
    before = row(db, sub_id)
    for kind, text, msg in ((REASON[0], "  ", MSG_NO_REASON), (None, "사유", MSG_NO_REASON), ("WRONG", "사유", MSG_BAD_KIND)):
        with pytest.raises(AdjustError) as exc:
            adjust(db, sub_id, "P3", kind, text, AGENT, received)
        assert str(exc.value) == msg and exc.value.status == 400
    assert row(db, sub_id) == before and adjustments(db, sub_id) == []


def test_ac_028_3_adjusted_120_targets(db):
    """AC-028-3(운영진 조정 120건, 팀 정답지 미적재 C-67): 정답 priority로 다시 조회한 목표가 100% 같다."""
    rows = db.execute("""SELECT ticket_id, category_code, customer_tier, priority,
                                sla_first_response_target_h::int, sla_resolution_target_h::int
                           FROM gold.ticket_gold WHERE priority_adjusted_by_agent = 'Y'""").fetchall()
    assert len(rows) == 120
    for _, cat, tier, pr, fr_t, res_t in rows:
        t = find_sla_target(db, cat, tier, pr)
        assert (t.sla_first_response_target_h, t.sla_resolution_target_h) == (fr_t, res_t)


def test_ac_027_5_raise_to_breach(db):
    """AC-027-5: P4(168h) 경과 130h에 RES_AT_RISK → P3(120h)로 올리면 RES_BREACHED가 새로 생긴다."""
    sub_id, received = manual_p4(db)
    db.execute("UPDATE svc.sub_ticket SET first_response_at_utc = %s WHERE sub_ticket_id = %s",
               (received + timedelta(hours=1), sub_id))
    at = received + timedelta(hours=130)
    raise_alerts(db, at, sub_ticket_ids=[sub_id])
    assert [a["alert_type"] for a in alert_history(db, sub_id)] == ["RES_AT_RISK"]
    with pytest.raises(AdjustError) as exc:               # 예외 3행: 반영 전에 확인
        adjust(db, sub_id, "P3", *REASON, AGENT, at)
    assert str(exc.value) == MSG_BREACH and exc.value.preview["becomes_breached"]
    assert row(db, sub_id)[0] == "P4"
    out = adjust(db, sub_id, "P3", *REASON, AGENT, at, confirm_breach=True)
    assert out["alerts_raised"] == ["RES_BREACHED"] and out["sla"]["res_status"] == "BREACHED"
    assert {a["alert_type"] for a in alert_history(db, sub_id)} == {"RES_AT_RISK", "RES_BREACHED"}


def test_same_priority_and_closed_refused(db):
    """FR-028 처리 1, 예외 2행: 같은 우선순위, 종료 문의는 거부."""
    sub_id, received = manual_p4(db)
    with pytest.raises(AdjustError) as exc:
        adjust(db, sub_id, "P4", *REASON, AGENT, received)
    assert str(exc.value) == MSG_SAME
    sent(db, sub_id, "FINAL_REPLY", received + timedelta(hours=2))
    with pytest.raises(AdjustError) as exc:
        adjust(db, sub_id, "P3", *REASON, AGENT, received + timedelta(hours=3))
    assert str(exc.value) == MSG_CLOSED


def test_lower_priority_clears_alert(db):
    """FR-027 처리 6: P3(120h) 경과 100h의 RES_AT_RISK는 P4(168h)로 낮추면 해제된다."""
    sub_id, received = manual_p4(db)
    db.execute("""UPDATE svc.sub_ticket SET priority = 'P3', sla_id = 'SLA-MANUAL-STANDARD-P3',
                      sla_first_response_target_h = 24, sla_resolution_target_h = 120,
                      first_response_at_utc = %s WHERE sub_ticket_id = %s""", (received + timedelta(hours=1), sub_id))
    at = received + timedelta(hours=100)
    raise_alerts(db, at, sub_ticket_ids=[sub_id])
    out = adjust(db, sub_id, "P4", "IMPACT_REASSESSED", "영향 범위가 한 대뿐", AGENT, at)
    assert out["alerts_cleared"] == ["RES_AT_RISK"] and alert_history(db, sub_id)[0]["cleared_at_utc"] == at


def test_concurrent_adjust_refused(db):
    """FR-025 예외 2행: 읽은 version이 다르면 거부."""
    sub_id, received = manual_p4(db)
    (version,) = db.execute("SELECT version FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    adjust(db, sub_id, "P3", *REASON, AGENT, received, expected_version=version)
    with pytest.raises(ConcurrentChange):
        adjust(db, sub_id, "P2", *REASON, "TS_LV_AGENT_10", received, expected_version=version)


@pytest.fixture
def client(db):
    def shared():
        yield db
    app.dependency_overrides[get_conn] = shared
    yield TestClient(app), db
    app.dependency_overrides.clear()


def test_api_preview_and_adjust(client):
    """§8-1 POST /sub-tickets/{id}/priority와 미리 보기 GET, 상세 API의 조정 이력."""
    http, conn = client
    sub_id, _ = manual_p4(conn)
    view = http.get(f"/sub-tickets/{sub_id}/priority", params={"new_priority": "P3"}).json()
    assert (view["from_fr_target_h"], view["from_res_target_h"], view["to_fr_target_h"], view["to_res_target_h"],
            view["to_sla_id"]) == (72, 168, 24, 120, "SLA-MANUAL-STANDARD-P3")
    assert row(conn, sub_id)[0] == "P4"
    body = {"new_priority": "P3", "reason_kind": REASON[0], "reason_text": REASON[1], "confirm_breach": True}
    assert http.post(f"/sub-tickets/{sub_id}/priority", json=body).status_code == 400  # 상담원 ID 없음
    res = http.post(f"/sub-tickets/{sub_id}/priority", json=body, headers={"X-Agent-Id": AGENT})
    assert res.status_code == 200, res.text
    blank = http.post(f"/sub-tickets/{sub_id}/priority", headers={"X-Agent-Id": AGENT},
                      json={**body, "new_priority": "P2", "reason_text": ""})
    assert blank.status_code == 400 and blank.json()["detail"] == MSG_NO_REASON
    detail = http.get(f"/tickets/{sub_id.rsplit('-', 1)[0]}").json()
    sub = detail["sub_tickets"][0]
    assert sub["state"]["priority"] == "P3" and sub["state"]["priority_adjusted_by_agent"]
    assert sub["state"]["priority_rule_id"] == "PR-07" and sub["adjustments"][0]["to_priority"] == "P3"
    assert http.get("/sub-tickets/NOPE-1/priority", params={"new_priority": "P3"}).status_code == 404


def test_adjust_code_does_not_import_llm():
    """명세서 그룹 4: 조정 코드는 언어 모델 호출 계층을 import하지 않는다."""
    path = Path(__file__).resolve().parents[2] / "app" / "sla" / "adjust.py"
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        assert not any(n.startswith("app.llm") for n in names)
