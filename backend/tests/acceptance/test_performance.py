"""내 실적 (변경 add-my-performance). 해결·종료 이력과 미해결을 재생한 DB에서 한 상담원의 날짜별 처리와 기한 충족을
SQL 직접 집계에 맞대 보고, 이관·조정을 더하면 오늘 칸에 늘어나는지 본다(시험마다 롤백)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.performance import performance
from app.db.workload import workload
from app.sla.adjust import adjust
from app.status.escalation import escalate
from jobs.replay_demo import replay
from jobs.replay_gold import SNAPSHOT
from jobs.replay_history import CLOSED

DAYS = 30
AS_OF = SNAPSHOT  # 2026-09-30 23:59 UTC


@pytest.fixture
def replayed_all(conn):
    with conn.transaction(force_rollback=True):
        replay(conn)
        replay(conn, CLOSED)
        # 방금 넣은 큰 데이터는 통계가 비어 inquiry_sla 실행 계획이 나빠진다(test_demo_replay와 같은 조치)
        conn.execute("ANALYZE svc.ticket, svc.sub_ticket, svc.ticket_status_history, svc.ticket_message, svc.priority_adjustment, svc.sla_alert")
        yield conn


def busiest(c) -> str:
    """기간 안에 발송을 가장 많이 한 상담원(재생 이력의 발송은 담당 상담원 이름으로 남는다)."""
    return c.execute(
        """SELECT sent_by_name FROM svc.ticket_message WHERE message_status = 'SENT' AND sender IN ('AGENT','DEPT')
              AND message_type IN ('INFO_REQUEST','FINAL_REPLY') AND sent_at_utc > %s AND sent_at_utc <= %s
            GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1""", (AS_OF - timedelta(days=DAYS), AS_OF)).fetchone()[0]


def test_daily_sent_matches_sql_and_is_zero_filled(replayed_all):
    """날짜별 발송이 DB를 직접 센 값과 같고, 기간의 모든 날이 오래된 날부터 채워진다."""
    c = replayed_all
    agent = busiest(c)
    d = performance(c, agent, AS_OF, DAYS)
    assert [x["date"] for x in d["daily"]] == sorted(x["date"] for x in d["daily"]) and len(d["daily"]) == DAYS
    assert d["daily"][-1]["date"] == AS_OF.date().isoformat()
    first = AS_OF.date() - timedelta(days=DAYS - 1)
    start = datetime(first.year, first.month, first.day, tzinfo=timezone.utc)
    direct = c.execute(
        """SELECT count(*) FROM svc.ticket_message WHERE message_status = 'SENT' AND sender IN ('AGENT','DEPT')
              AND message_type IN ('INFO_REQUEST','FINAL_REPLY') AND sent_by_name = %s AND sent_at_utc >= %s AND sent_at_utc <= %s""",
        (agent, start, AS_OF)).fetchone()[0]
    assert direct > 0 and sum(x["sent"] for x in d["daily"]) == direct
    assert d["total"] == sum(x["n"] for x in d["daily"]) and all(x["n"] == x["sent"] + x["escalated"] + x["adjusted"] for x in d["daily"])


def test_sla_counts_match_inquiry_sla(replayed_all):
    """기한 충족이 내가 담당이고 접수일이 기간 안인 문의의 inquiry_sla를 직접 센 값과 같다."""
    c = replayed_all
    agent = busiest(c)
    d = performance(c, agent, AS_OF, DAYS)
    first = AS_OF.date() - timedelta(days=DAYS - 1)
    start = datetime(first.year, first.month, first.day, tzinfo=timezone.utc)
    met, bad, ok, total = c.execute(
        """SELECT count(*) FILTER (WHERE f.fr_status = 'MET'), count(*) FILTER (WHERE f.fr_status = 'BREACHED'),
                  count(*) FILTER (WHERE f.res_status <> 'BREACHED'), count(*)
             FROM svc.sub_ticket s JOIN svc.inquiry_sla(%s) f USING (sub_ticket_id)
            WHERE s.assignee_masked = %s AND f.received_at_utc >= %s AND f.received_at_utc <= %s""", (AS_OF, agent, start, AS_OF)).fetchone()
    assert (d["sla"]["fr_met"], d["sla"]["fr_breached"], d["sla"]["res_ok"], d["sla"]["window_total"]) == (met, bad, ok, total) and total > 0


def test_escalation_and_adjustment_count_today_and_match_workload(replayed_all):
    """내가 이관·조정하면 오늘 칸에 늘고, 나의 업무 현황의 '오늘 처리한 건수'와 같다. 다른 상담원의 실적에는 섞이지 않는다."""
    c = replayed_all
    agent, other = "leo", "mia"
    sub = c.execute("""SELECT s.sub_ticket_id, s.assigned_dept, s.priority FROM svc.sub_ticket s
                        WHERE s.status = 'IN_PROGRESS' AND s.assigned_dept = 'TS_LV' ORDER BY 1 LIMIT 1""").fetchone()
    sub_id, dept, priority = sub
    before = performance(c, agent, AS_OF, 7)["daily"][-1]
    escalate(c, sub_id, "FIELD_SVC", "ONSITE_REQUIRED", "현장 점검 요청", agent, AS_OF)
    other_sub = c.execute("""SELECT sub_ticket_id, priority FROM svc.sub_ticket WHERE status = 'IN_PROGRESS' AND assigned_dept = 'TS_LV'
                              AND sub_ticket_id <> %s ORDER BY 1 LIMIT 1""", (sub_id,)).fetchone()
    new_priority = "P3" if other_sub[1] != "P3" else "P4"
    adjust(c, other_sub[0], new_priority, "OTHER", "실적 시험", agent, AS_OF, confirm_breach=True)
    today = performance(c, agent, AS_OF, 7)["daily"][-1]
    assert (today["escalated"], today["adjusted"]) == (before["escalated"] + 1, before["adjusted"] + 1)
    assert today["n"] == before["n"] + 2
    wl = workload(c, "TS_LV", agent, "mine", AS_OF)["today"]
    assert (wl["sent"], wl["escalated"], wl["adjusted"]) == (today["sent"], today["escalated"], today["adjusted"])
    assert performance(c, other, AS_OF, 7)["daily"][-1]["escalated"] == 0  # 다른 사람 몫이 아니다
