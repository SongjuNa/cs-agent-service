"""SLA 위험 경고와 주기 점검 완료 기준 (FR-027, 기술 명세서 §6-4, 변경 add-sla-alert).

문의는 정답지 시각으로 만들고(test_status_sla.seed), DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.scheduler import INTERVAL_MINUTES, JOB_ID, periodic_check
from app.sla.alerts import alert_history, clear_alerts, raise_alerts
from tests.acceptance.test_status_sla import (  # noqa: F401  (db·replayed 픽스처를 함께 쓴다)
    SNAPSHOT, db, replayed, seed, sent, utc,
)


def gold_times(conn, gold_id):
    return conn.execute("""SELECT received_at_utc::timestamptz, first_response_at_utc::timestamptz,
                                  sla_first_response_target_h::int, sla_resolution_target_h::int
                             FROM gold.ticket_gold WHERE ticket_id = %s""", (gold_id,)).fetchone()


def make(conn, gold_id):
    """정답지 문의를 svc에 만들고 1차 응답 시각을 정답대로 넣는다."""
    received, fr, fr_t, res_t = gold_times(conn, gold_id)
    sub_id = seed(conn, gold_id, targets=(fr_t, res_t))
    conn.execute("UPDATE svc.sub_ticket SET first_response_at_utc = %s WHERE sub_ticket_id = %s", (fr, sub_id))
    return sub_id, received


def test_ac_027_1_at_risk_once(db):
    """AC-027-1: CSV1-003401(목표 360h)을 스냅샷에 점검 → RES_AT_RISK 한 줄, 발생 = 접수 + 270h, 접수함 뷰에 보임."""
    sub_id, received = make(db, "CSV1-003401")
    added = raise_alerts(db, SNAPSHOT)
    assert added == [(sub_id, "RES_AT_RISK", received + timedelta(hours=270))]  # 예외 1행: 점검 시각이 아님
    (alerts,) = db.execute("SELECT alerts FROM svc.v_inquiry_inbox WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    assert alerts == ["RES_AT_RISK"]


def test_ac_027_2_no_duplicate(db):
    """AC-027-2: 다음 주기에 다시 점검해도 새 경고가 없다."""
    sub_id, _ = make(db, "CSV1-003401")
    raise_alerts(db, SNAPSHOT)
    assert raise_alerts(db, SNAPSHOT + timedelta(minutes=INTERVAL_MINUTES)) == []
    assert len(alert_history(db, sub_id)) == 1


def test_ac_027_3_waiting_no_resolution_alert(db):
    """AC-027-3: CSV1-003578(WAITING_CUSTOMER) → 해결 경고 없음."""
    sub_id, received = make(db, "CSV1-003578")
    fr = gold_times(db, "CSV1-003578")[1]
    sent(db, sub_id, "INFO_REQUEST", fr)
    raise_alerts(db, SNAPSHOT)
    assert [a for a in alert_history(db, sub_id) if a["alert_type"].startswith("RES")] == []


TEAM_GOLD_5 = ["CSV1-003290", "CSV1-003742", "CSV1-003774", "CSV1-003820", "CSV1-003888"]  # 명세서 그룹 5 데이터 사실(D30)


def test_ac_027_4_recall_on_4000(replayed):
    """AC-027-4: 미해결 360건(팀 정답지 문의 5건 제외) 스냅샷 점검 → AT_RISK 34건·BREACHED 140건 모두 같은 경고."""
    c = replayed[2]
    with c.transaction(force_rollback=True):
        raise_alerts(c, SNAPSHOT, schema="scoring")
        rows = c.execute(
            """SELECT g.sla_resolution_status, count(*),
                      count(*) FILTER (WHERE EXISTS (SELECT 1 FROM scoring.sla_alert a
                                                      WHERE a.sub_ticket_id = g.ticket_id || '-1'
                                                        AND a.alert_type = 'RES_' || g.sla_resolution_status))
                 FROM gold.ticket_gold g
                WHERE g.status IN ('NEW', 'IN_PROGRESS', 'WAITING_CUSTOMER', 'ESCALATED')
                  AND g.sla_resolution_status IN ('AT_RISK', 'BREACHED')
                  AND g.ticket_id <> ALL(%s)
                GROUP BY 1""", (TEAM_GOLD_5,)).fetchall()
    assert sorted(rows) == [("AT_RISK", 34, 34), ("BREACHED", 140, 140)]


def test_waiting_over_threshold_no_resolution_alert(db):
    """FR-027 처리 4: 75%를 넘은 뒤 WAITING_CUSTOMER가 된 문의도 대기 중에는 해결 경고를 새로 달지 않는다."""
    sub_id, received = make(db, "CSV1-003401")
    sent(db, sub_id, "INFO_REQUEST", received + timedelta(hours=300))  # 300h > 270h 뒤 대기
    raise_alerts(db, SNAPSHOT)
    assert [a for a in alert_history(db, sub_id) if a["alert_type"].startswith("RES")] == []


def test_first_response_alerts(db):
    """FR-027 처리 3: CSV1-003950(NEW, 1차 응답 없음, 목표 16h) → FR_AT_RISK 접수 + 12h, FR_BREACHED 접수 + 16h."""
    sub_id, received = make(db, "CSV1-003950")
    got = {k: at for s, k, at in raise_alerts(db, SNAPSHOT) if s == sub_id}
    assert got["FR_AT_RISK"] == received + timedelta(hours=12)
    assert got["FR_BREACHED"] == received + timedelta(hours=16)


def test_no_target_no_alert(db):
    """FR-027 예외 2행: SLA 미정 문의는 점검하지 않는다."""
    sub_id = seed(db, "CSV1-003401", targets=(None, None))
    raise_alerts(db, SNAPSHOT)
    assert alert_history(db, sub_id) == []


def test_cleared_when_target_grows(db):
    """FR-027 처리 6: 목표가 늘어 조건이 풀리면 해제 시각을 남긴다."""
    sub_id, _ = make(db, "CSV1-003401")
    raise_alerts(db, SNAPSHOT)
    db.execute("UPDATE svc.sub_ticket SET sla_resolution_target_h = 720 WHERE sub_ticket_id = %s", (sub_id,))
    later = SNAPSHOT + timedelta(minutes=5)
    assert clear_alerts(db, later) == [(sub_id, "RES_AT_RISK")]
    assert alert_history(db, sub_id)[0]["cleared_at_utc"] == later
    (alerts,) = db.execute("SELECT alerts FROM svc.v_inquiry_inbox WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    assert alerts == []


def test_periodic_check_one_cycle(db):
    """§6-4 주기 점검: 한 번 부르면 경고가 생기고 168시간 무응답 문의가 닫힌다."""
    risky, _ = make(db, "CSV1-003401")
    quiet = seed(db, "CSV1-000085")
    sent(db, quiet, "INFO_REQUEST", utc("2025-10-09T18:55:19"))
    result = periodic_check(db, SNAPSHOT)
    assert result["alerts"] >= 1 and result["closed"] >= 1
    assert db.execute("SELECT status FROM svc.sub_ticket WHERE sub_ticket_id = %s", (quiet,)).fetchone()[0] == "CLOSED"
    assert alert_history(db, risky)[0]["alert_type"] == "RES_AT_RISK"


def test_scheduler_starts_with_app(monkeypatch):
    """§6-4: 서버를 켜면 5분 간격 작업 하나가 등록되고, 끄면 멈춘다."""
    monkeypatch.setattr(main, "get_settings", lambda: Settings(scheduler_enabled=True))
    with TestClient(main.app):
        scheduler = main.app.state.scheduler
        (job,) = scheduler.get_jobs()
        assert job.id == JOB_ID and job.trigger.interval == timedelta(minutes=INTERVAL_MINUTES)
    assert not scheduler.running


def test_detail_has_alert_history(db):
    """FR-027 출력: 상세 API 재료에 경고 이력(종류, 발생, 경과, 목표, 해제)."""
    sub_id, _ = make(db, "CSV1-003401")
    raise_alerts(db, SNAPSHOT)
    (a,) = alert_history(db, sub_id)
    assert set(a) == {"alert_type", "raised_at_utc", "elapsed_h", "target_h", "cleared_at_utc"}
    assert a["target_h"] == 360 and a["elapsed_h"] == 270  # 발생 당시 값(§6-2)


def test_alert_code_does_not_import_llm():
    """명세서 그룹 4: 경고·주기 점검 코드는 언어 모델 호출 계층을 import하지 않는다."""
    root = Path(__file__).resolve().parents[2] / "app"
    for path in (root / "sla" / "alerts.py", root / "scheduler.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith("app.llm") for n in names), path
