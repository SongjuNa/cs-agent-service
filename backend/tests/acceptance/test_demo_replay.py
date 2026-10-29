"""시연 데이터 재생 (기술 명세서 v1.4 §9 W6 확인 기준, 기능 요구사항 명세서 v1.5 그룹 5 데이터 사실).

jobs/replay_demo.py를 svc에 돌린다(시험마다 롤백). 이미 적재된 DB면 건너뛰고 같은 값을 본다.
정답과 비교하는 시험이라 정답 열을 읽는다(CLAUDE.md 규칙 6 예외).
"""

from __future__ import annotations

import pytest

from app.sla.alerts import raise_alerts
from jobs.replay_demo import TEAM_GOLD_5, replay
from jobs.replay_gold import SNAPSHOT

REPLAYED = "FROM svc.sub_ticket s JOIN svc.ticket t USING (ticket_id) WHERE t.source = 'REPLAY'"


@pytest.fixture
def demo(conn):
    with conn.transaction(force_rollback=True):
        first = replay(conn)
        conn.execute("ANALYZE svc.ticket, svc.sub_ticket, svc.ticket_status_history, svc.ticket_message")
        yield conn, first


def test_w6_360_rows_without_team_gold(demo):
    """W6: 미해결 365건 중 팀 정답지 문의 5건을 뺀 360건이 원본 번호 그대로, 출처 REPLAY로 들어간다."""
    c, first = demo
    assert first["target"] == 360
    ids = {r[0] for r in c.execute(f"SELECT t.ticket_id {REPLAYED}").fetchall()}
    assert len(ids) == 360 and not ids & set(TEAM_GOLD_5)
    assert c.execute(f"SELECT count(*) {REPLAYED} AND t.source_ticket_id <> t.ticket_id").fetchone()[0] == 0


def test_w6_status_and_dept_counts(demo):
    """그룹 5 데이터 사실: 상태 IN_PROGRESS 237, ESCALATED 71, WAITING_CUSTOMER 33, NEW 19. 담당 부서 TS_LV 67."""
    c, _ = demo
    status = dict(c.execute(f"SELECT s.status, count(*) {REPLAYED} GROUP BY 1").fetchall())
    assert status == {"IN_PROGRESS": 237, "ESCALATED": 71, "WAITING_CUSTOMER": 33, "NEW": 19}
    dept = dict(c.execute(f"SELECT s.assigned_dept, count(*) {REPLAYED} GROUP BY 1").fetchall())
    assert (dept["TS_LV"], dept["WARRANTY_DESK"], dept["TS_AUTO"], dept["SCM"]) == (67, 60, 52, 52)


def test_w6_snapshot_sla_matches_gold(demo):
    """W6 확인 기준: 스냅샷 해결 SLA ON_TRACK 186, AT_RISK 34, BREACHED 140, 문의마다 정답과 같다."""
    c, _ = demo
    rows = c.execute(
        """SELECT f.res_status, g.sla_resolution_status FROM svc.inquiry_sla(%s) f
             JOIN svc.sub_ticket s USING (sub_ticket_id) JOIN svc.ticket t USING (ticket_id)
             JOIN gold.ticket_gold g ON g.ticket_id = t.source_ticket_id
            WHERE t.source = 'REPLAY'""", (SNAPSHOT,)).fetchall()
    assert len(rows) == 360 and all(a == b for a, b in rows)
    counts = {k: sum(1 for a, _ in rows if a == k) for k in ("ON_TRACK", "AT_RISK", "BREACHED")}
    assert counts == {"ON_TRACK": 186, "AT_RISK": 34, "BREACHED": 140}


def test_w6_snapshot_alerts(demo):
    """FR-027: 스냅샷 점검 뒤 AT_RISK 34건·BREACHED 140건 모두 같은 해결 경고가 달린다."""
    c, _ = demo
    raise_alerts(c, SNAPSHOT)
    rows = c.execute(
        f"""SELECT f.res_status, count(*), count(*) FILTER (WHERE EXISTS (
                SELECT 1 FROM svc.sla_alert a WHERE a.sub_ticket_id = s.sub_ticket_id AND a.alert_type = 'RES_' || f.res_status))
              FROM svc.inquiry_sla(%s) f JOIN svc.sub_ticket s USING (sub_ticket_id) JOIN svc.ticket t USING (ticket_id)
             WHERE t.source = 'REPLAY' AND f.res_status IN ('AT_RISK', 'BREACHED') GROUP BY 1""", (SNAPSHOT,)).fetchall()
    assert sorted(rows) == [("AT_RISK", 34, 34), ("BREACHED", 140, 140)]


def test_w6_messages_and_assignee(demo):
    """FR-035 처리 6: 문의마다 INQUIRY 하나, 정보 요청을 보낸 문의는 INFO_REQUEST SENT(시각 = 1차 응답). 담당은 명단 이름."""
    c, _ = demo
    inquiries = c.execute(f"""SELECT count(*) FROM svc.ticket_message m JOIN svc.ticket t USING (ticket_id)
                                WHERE t.source = 'REPLAY' AND m.message_type = 'INQUIRY'""").fetchone()[0]
    assert inquiries == 360
    bad = c.execute(f"""SELECT count(*) {REPLAYED} AND s.info_request_sent AND NOT EXISTS (
                          SELECT 1 FROM svc.ticket_message m WHERE m.sub_ticket_id = s.sub_ticket_id
                             AND m.message_type = 'INFO_REQUEST' AND m.message_status = 'SENT'
                             AND m.sent_at_utc = s.first_response_at_utc)""").fetchone()[0]
    assert bad == 0
    raw = c.execute(f"SELECT count(*) {REPLAYED} AND s.assignee_masked LIKE '%%_AGENT_%%'").fetchone()[0]
    assert raw == 0


def test_w6_rerun_adds_nothing(demo):
    """다시 돌려도 겹치지 않는다(메시지·이력은 지울 수 없다)."""
    c, _ = demo
    assert replay(c)["added"] == 0
