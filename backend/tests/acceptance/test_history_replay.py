"""해결·종료 이력 재생 (변경 add-dashboard-history). 운영 대시보드·내 실적이 12개월 실제 값으로 집계되도록
jobs/replay_history.py가 정답지의 해결·종료 문의를 svc에 넣는다(시험마다 롤백).
정답 열을 읽는다(CLAUDE.md 규칙 6 예외를 넓힌 작업, 사용자 허락 2026-10-31)."""

from __future__ import annotations

import pytest

from jobs.replay_demo import excluded_ids, replay
from jobs.replay_history import CLOSED

REPLAYED = "FROM svc.sub_ticket s JOIN svc.ticket t USING (ticket_id) WHERE t.source = 'REPLAY'"


@pytest.fixture
def history(conn):
    with conn.transaction(force_rollback=True):
        yield conn, replay(conn, CLOSED)


def test_only_closed_rows_with_gold_status_and_times(history):
    """넣은 문의는 모두 해결·종료이고, 상태·접수 시각·1차 응답 시각이 정답지와 같다. 팀 정답지 문의는 빠진다."""
    c, first = history
    gold_total = c.execute("SELECT count(*) FROM gold.ticket_gold WHERE status = ANY(%s) AND ticket_id <> ALL(%s)",
                           (list(CLOSED), excluded_ids(c))).fetchone()[0]
    assert first["target"] == gold_total > 0
    rows = c.execute(
        """SELECT s.status, g.status, t.received_at_utc = g.received_at_utc::timestamptz,
                  s.first_response_at_utc IS NOT DISTINCT FROM g.first_response_at_utc::timestamptz
             FROM svc.sub_ticket s JOIN svc.ticket t USING (ticket_id)
             JOIN gold.ticket_gold g ON g.ticket_id = t.ticket_id
            WHERE t.source = 'REPLAY' AND s.status = ANY(%s)""", (list(CLOSED),)).fetchall()
    assert len(rows) >= gold_total
    assert all(a == b and r and f for a, b, r, f in rows)
    assert c.execute(f"SELECT count(*) {REPLAYED} AND t.ticket_id = ANY(%s)", (excluded_ids(c),)).fetchone()[0] == 0


def test_spread_over_twelve_months(history):
    """접수일이 12개월 이상에 퍼져 있다(대시보드 일별·월별 추이가 점 몇 개로 보이지 않게 하려는 목적)."""
    c, _ = history
    months = c.execute(f"SELECT count(DISTINCT date_trunc('month', t.received_at_utc)) {REPLAYED}").fetchone()[0]
    assert months >= 12


def test_rerun_and_limit(history):
    """다시 돌리면 아무것도 더하지 않는다(limit이 있어도 마찬가지)."""
    c, first = history
    again = replay(c, CLOSED)
    assert again["added"] == 0 and again["skipped"] == first["target"]
    assert replay(c, CLOSED, limit=5)["added"] == 0  # 더 넣을 것이 없으면 limit이 있어도 0


def test_open_and_closed_together_are_not_duplicated(conn):
    """미해결 재생과 해결·종료 재생을 모두 돌려도 번호가 겹치지 않고, limit은 건수까지만 넣는다."""
    with conn.transaction(force_rollback=True):
        opened = replay(conn)
        part = replay(conn, CLOSED, limit=10)
        assert part["added"] == 10
        rest = replay(conn, CLOSED)
        assert rest["added"] == part["target"] - 10 - part["skipped"]
        ids = [r[0] for r in conn.execute("SELECT ticket_id FROM svc.ticket WHERE source = 'REPLAY'").fetchall()]
        assert len(ids) == len(set(ids)) >= opened["target"] + part["target"]
