"""운영 대시보드 집계 (변경 add-ops-overview, 최신 목업 "운영 현황"). 운영진 4,000건을 scoring에 재생한 스냅샷에서
서버가 센 값을 SQL 직접 집계와 접수함 값에 맞대 본다(시험마다 롤백)."""

from __future__ import annotations

from datetime import timedelta

from app.db.dashboard import ESC_LATE_H, STAGES, dashboard
from app.db.inbox import AT_RISK, BREACHED, OPEN, InboxQuery, inbox
from tests.acceptance.test_inbox import snapshot  # noqa: F401  (미해결 360건 + 담당 + 스냅샷 경고 픽스처)
from tests.acceptance.test_status_sla import SNAPSHOT, replayed  # noqa: F401

DAYS = 30


def dash(c, days=DAYS):
    return dashboard(c, SNAPSHOT, days, schema="scoring")


def test_open_and_alert_counts_match_sql(snapshot):
    """미해결·기한 초과·임박 건수가 DB를 직접 센 값과 같고, 초과와 임박은 겹치지 않는다."""
    d = dash(snapshot)
    total = snapshot.execute("SELECT count(*) FROM scoring.sub_ticket WHERE status = ANY(%s)", (list(OPEN),)).fetchone()[0]
    breach, risk = snapshot.execute(
        """SELECT count(*) FILTER (WHERE alerts && %s::text[]),
                  count(*) FILTER (WHERE alerts && %s::text[] AND NOT alerts && %s::text[])
             FROM (SELECT s.sub_ticket_id,
                          coalesce((SELECT array_agg(a.alert_type) FROM scoring.sla_alert a
                                     WHERE a.sub_ticket_id = s.sub_ticket_id AND a.cleared_at_utc IS NULL), '{}') AS alerts
                     FROM scoring.sub_ticket s WHERE s.status = ANY(%s)) x""",
        (list(BREACHED), list(AT_RISK), list(BREACHED), list(OPEN))).fetchone()
    assert d["open"]["total"] == total > 300
    assert (d["open"]["breach"], d["open"]["risk"]) == (breach, risk) and breach > 0
    assert sum(s["open"] for s in d["stages"]) == total and [s["stage"] for s in d["stages"]] == list(STAGES)


def test_daily_series_is_complete_and_matches_window(snapshot):
    """일별 접수는 기간의 모든 날을 오래된 날부터 0으로 채워 주고, 합이 그 기간에 접수한 문의 수와 같다."""
    d = dash(snapshot)
    days = [x["date"] for x in d["daily"]]
    assert len(days) == DAYS and days == sorted(days) and days[-1] == SNAPSHOT.date().isoformat()
    since = SNAPSHOT - timedelta(days=DAYS)
    in_window = snapshot.execute(
        """SELECT count(*) FROM scoring.sub_ticket s JOIN scoring.ticket t USING (ticket_id)
            WHERE t.received_at_utc > %s AND t.received_at_utc <= %s""", (since, SNAPSHOT)).fetchone()[0]
    assert sum(x["n"] for x in d["daily"]) == in_window == d["sla"]["window_total"] > 0


def test_sla_counts_match_inquiry_sla(snapshot):
    """기간 안 접수 문의의 1차 응답 충족·위반, 해결 기한 위반 아님이 inquiry_sla를 직접 센 값과 같다."""
    d = dash(snapshot)
    since = SNAPSHOT - timedelta(days=DAYS)
    met, bad, ok = snapshot.execute(
        """SELECT count(*) FILTER (WHERE f.fr_status = 'MET'), count(*) FILTER (WHERE f.fr_status = 'BREACHED'),
                  count(*) FILTER (WHERE f.res_status <> 'BREACHED')
             FROM scoring.inquiry_sla(%s) f WHERE f.received_at_utc > %s AND f.received_at_utc <= %s""",
        (SNAPSHOT, since, SNAPSHOT)).fetchone()
    assert (d["sla"]["fr_met"], d["sla"]["fr_breached"], d["sla"]["res_ok"]) == (met, bad, ok)


def test_dept_agent_country_buckets_match_inbox(snapshot):
    """부서별 쌓임이 접수함(그 부서가 담당인 줄)과 같고, 상담원·나라별 합이 미해결 합을 넘지 않는다."""
    d = dash(snapshot)
    rows = [r for r in inbox(snapshot, InboxQuery(dept="TS_LV", as_of=SNAPSHOT, size=200), schema="scoring")["rows"]
            if r["assigned_dept"] == "TS_LV"]
    mine = next(x for x in d["by_dept"] if x["dept"] == "TS_LV")
    assert mine["open"] == len(rows)
    assert mine["breach"] == sum(1 for r in rows if set(r["alerts"]) & set(BREACHED))
    assert sum(x["open"] for x in d["by_dept"]) <= d["open"]["total"]
    assert 0 < sum(x["open"] for x in d["by_agent"]) <= d["open"]["total"]
    assert 0 < sum(x["open"] for x in d["by_country"]) <= d["open"]["total"]
    assert all(x["esc_late"] <= x["open"] for x in d["by_dept"]) and ESC_LATE_H == 168
    assert d["by_country"][0]["safety"] == max(x["safety"] for x in d["by_country"])  # 안전 문의가 많은 나라가 먼저
