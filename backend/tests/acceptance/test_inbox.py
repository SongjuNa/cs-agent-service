"""접수함 완료 기준 (FR-029, 변경 add-inbox).

AC-029-1·2·5는 운영진 4,000건을 scoring에 재생하고(롤백), 시험 코드만 정답의 담당 부서·막는 항목을 넣는다
(CLAUDE.md 규칙 6 예외: 정답과 비교하는 시험). AC-029-3·4는 API로 접수한다.
"""

from __future__ import annotations

import pytest

from app.db.inbox import ALERTS, MSG_EMPTY, MSG_NO_DEPT, InboxQuery, inbox
from app.sla.alerts import raise_alerts
from tests.acceptance.test_compound_inquiry import compound
from tests.acceptance.test_sla_alert import TEAM_GOLD_5
from tests.acceptance.test_status_sla import SNAPSHOT, replayed  # noqa: F401  (replayed 픽스처)
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)


# API 시험을 먼저 둔다. replayed(모듈 단위)가 열어 둔 트랜잭션이 api 픽스처의 기준표 적재와 잠금으로 엉키지 않게.


def test_no_dept(api):
    """FR-029 예외 1행: 부서를 고르지 않으면 빈 목록과 "부서를 선택하세요"."""
    got = api[0].get("/tickets").json()
    assert got["rows"] == [] and got["message"] == MSG_NO_DEPT == "부서를 선택하세요"


def test_empty_dept(api):
    """FR-029 예외 2행: 줄이 없는 부서 → 빈 목록과 "처리할 티켓이 없습니다"."""
    got = api[0].get("/tickets", params={"dept": "RND_FW"}).json()
    assert got["rows"] == [] and got["message"] == MSG_EMPTY == "처리할 티켓이 없습니다"


def test_ac_029_3_compound_rows(api):
    """AC-029-3: CSV1-000008(복합) → 펌웨어는 TS_ENERGY, 매뉴얼은 GCS_L1 접수함에 "n건 중 k" 한 줄씩."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    client = api[0]
    seen = {}
    for dept in ("TS_ENERGY", "GCS_L1"):
        rows = [r for r in client.get("/tickets", params={"dept": dept, "q": tid}).json()["rows"]]
        assert len(rows) == 1
        seen[dept] = (rows[0]["category_code"], rows[0]["seq"], rows[0]["inquiry_count"])
    assert seen == {"TS_ENERGY": ("FW_UPDATE", 1, 2), "GCS_L1": ("MANUAL", 2, 2)}
    rows = client.get("/tickets", params={"dept": "TS_ENERGY", "composite": "true", "q": tid}).json()["rows"]
    assert [r["sub_ticket_id"] for r in rows] == [f"{tid}-1"]
    assert rows[0]["has_unsent_draft"]  # 펌웨어 메일 초안이 승인 대기


def test_ac_029_4_row_opens_detail(api):
    """AC-029-4: 줄의 ticket_id로 상세가 열린다(화면 클릭은 브라우저로 확인)."""
    detail = compound(api)
    row = api[0].get("/tickets", params={"dept": "GCS_L1", "q": detail["ticket"]["ticket_id"]}).json()["rows"][0]
    res = api[0].get(f"/tickets/{row['ticket_id']}")
    assert res.status_code == 200 and res.json()["ticket"]["ticket_id"] == row["ticket_id"]


def test_same_rows_as_view(api):
    """C-102: 접수함 조회의 줄은 뷰 svc.v_inquiry_inbox와 같은 값이다(서비스 DB, 지금 기준)."""
    compound(api)
    conn = api[2]
    # remaining_h는 뷰가 now()라 계산 순간이 달라 빼고, 나머지 열은 모두 본다
    keys = ("sub_ticket_id", "ticket_id", "seq", "inquiry_count", "received_at_utc", "channel", "language",
            "customer_id", "company_masked", "customer_tier", "product_code", "category_code", "urgency_flag",
            "priority", "escalated_to", "assignee_masked", "status", "fr_status", "res_status", "alerts",
            "needs_info", "has_unsent_draft", "reminder_sent", "assigned_dept")
    view = conn.execute(f"SELECT {', '.join(keys)} FROM svc.v_inquiry_inbox").fetchall()
    mine = []
    for dept in {v[-1] for v in view if v[-1]}:
        rows = inbox(conn, InboxQuery(dept=dept, include_closed=True, size=200))["rows"]
        mine += [tuple(r[k] if k != "alerts" else list(r[k]) for k in keys) for r in rows if r["assigned_dept"] == dept]
    expected = [tuple(list(v[i]) if keys[i] == "alerts" else v[i] for i in range(len(keys))) for v in view if v[-1]]
    assert mine and sorted(mine) == sorted(expected)


@pytest.fixture
def snapshot(replayed):
    """미해결 360건(팀 정답지 5건 제외) + 정답 담당 부서·막는 항목 + 스냅샷 경고. 시험마다 롤백."""
    c = replayed[2]
    with c.transaction(force_rollback=True):
        c.execute("""UPDATE scoring.sub_ticket s
                        SET assigned_dept = g.assigned_dept,
                            missing_blocking_info = coalesce(string_to_array(nullif(g.missing_blocking_info, ''), ';'),
                                                             '{}')
                       FROM gold.ticket_gold g WHERE s.sub_ticket_id = g.ticket_id || '-1'""")
        c.execute("""UPDATE scoring.sub_ticket SET assigned_dept = NULL
                      WHERE sub_ticket_id = ANY(%s)""", ([t + "-1" for t in TEAM_GOLD_5],))
        # 롤백할 4,000건이라 통계가 비어 있다. 통계 없이 짜인 실행 계획은 inquiry_sla를 몇 분씩 돌린다.
        c.execute("ANALYZE scoring.ticket, scoring.sub_ticket, scoring.ticket_status_history, "
                  "scoring.ticket_message, scoring.sla_alert")
        raise_alerts(c, SNAPSHOT, schema="scoring")
        yield c


def ts_lv(c, **kw):
    return inbox(c, InboxQuery(dept="TS_LV", as_of=SNAPSHOT, size=200, **kw), schema="scoring")


def test_ac_029_1_ts_lv_snapshot(snapshot):
    """AC-029-1: 스냅샷 TS_LV → 67건. 기본 정렬은 내 차례 묶음이 먼저이고(add-inbox-turn-depth), 묶음 안에서
    맨 위는 경고가 있고 남은 시간이 가장 적다."""
    got = ts_lv(snapshot)
    rows = got["rows"]
    assert got["counts"]["total"] == len(rows) == 67
    assert got["counts"]["alert"] == sum(bool(r["alerts"]) for r in rows)
    mine = [r for r in rows if r["turn"] == "ME"]
    assert rows[:len(mine)] == mine  # 내 차례 묶음이 맨 위
    for turn in ("ME", "DEPT", "CUSTOMER", "DONE"):
        group = [r for r in rows if r["turn"] == turn]
        alerted = [r for r in group if r["alerts"]]
        if not alerted:
            continue
        # 묶음 안에서 경고 줄이 위, 그 안에서 남은 시간 오름차순(FR-027 처리 5)
        assert group[:len(alerted)] == alerted
        assert [r["remaining_h"] for r in alerted] == sorted(r["remaining_h"] for r in alerted)


def test_escalated_rows_join_inbox(snapshot):
    """FR-029 처리 1, C-101: 이관받은 문의(escalated_to = TS_LV)도 보이고 "{원 부서}에서 이관됨"."""
    snapshot.execute("""UPDATE scoring.sub_ticket s SET escalated_to = g.escalated_to, escalation_reason = g.escalation_reason
                          FROM gold.ticket_gold g WHERE s.sub_ticket_id = g.ticket_id || '-1' AND g.escalated_to = 'TS_LV'""")
    rows = ts_lv(snapshot)["rows"]
    moved = {r["ticket_id"]: r["escalated_in_from"] for r in rows if r["escalated_in_from"]}
    assert len(rows) == 69 and moved == {"CSV1-003280": "SALES_OPS", "CSV1-003449": "CERT"}


def test_ac_029_2_needs_info(snapshot):
    """AC-029-2: "정보 요청 필요" → missing_blocking_info가 비어 있지 않은 줄만."""
    got = ts_lv(snapshot, needs_info=True)
    ids = [r["sub_ticket_id"] for r in got["rows"]]
    blocking = dict(snapshot.execute("SELECT sub_ticket_id, missing_blocking_info FROM scoring.sub_ticket "
                                     "WHERE sub_ticket_id = ANY(%s)", (ids,)).fetchall())
    assert len(ids) == 23 == got["counts"]["needs_info"] and all(blocking[i] for i in ids)


def test_ac_029_5_closed_hidden(snapshot):
    """AC-029-5: 종료 포함이 꺼지면 RESOLVED·CLOSED 없음, 켜면 보인다."""
    assert not {r["status"] for r in ts_lv(snapshot)["rows"]} & {"RESOLVED", "CLOSED"}
    with_closed = ts_lv(snapshot, include_closed=True)
    assert {"RESOLVED", "CLOSED"} <= {r["status"] for r in with_closed["rows"]}
    assert with_closed["counts"]["total"] > 67


def test_filters_and_search(snapshot):
    """FR-029 처리 4: 필터를 함께 건다. 검색은 문의 번호·고객사."""
    rows = ts_lv(snapshot, status=["WAITING_CUSTOMER"], priority=["P1", "P2"])["rows"]
    assert rows and all(r["status"] == "WAITING_CUSTOMER" and r["priority"] in ("P1", "P2") for r in rows)
    breached = ts_lv(snapshot, alert=["RES_BREACHED"])["rows"]
    assert breached and all("RES_BREACHED" in r["alerts"] for r in breached)
    assert set(ALERTS) >= {a for r in ts_lv(snapshot)["rows"] for a in r["alerts"]}
    phone = ts_lv(snapshot, channel=["PHONE"])["rows"]
    assert phone and {r["channel"] for r in phone} == {"PHONE"}
    one = ts_lv(snapshot)["rows"][5]
    assert [r["sub_ticket_id"] for r in ts_lv(snapshot, q=one["ticket_id"].lower())["rows"]] == [one["sub_ticket_id"]]
    assert one["sub_ticket_id"] in [r["sub_ticket_id"] for r in ts_lv(snapshot, q=one["company_masked"])["rows"]]
    assert ts_lv(snapshot, composite=True)["rows"] == []  # 재생은 모두 단일 문의
    assert ts_lv(snapshot, has_draft=True)["counts"]["total"] == 0


def test_sort_page_and_no_target(snapshot):
    """FR-029 처리 3·7, 예외 3행: 열 정렬, 50건 쪽, SLA 미정은 맨 아래."""
    rows = ts_lv(snapshot, sort="-received_at")["rows"]
    assert [r["received_at_utc"] for r in rows] == sorted((r["received_at_utc"] for r in rows), reverse=True)
    first = inbox(snapshot, InboxQuery(dept="TS_LV", as_of=SNAPSHOT), schema="scoring")
    second = inbox(snapshot, InboxQuery(dept="TS_LV", as_of=SNAPSHOT, page=2), schema="scoring")
    assert (len(first["rows"]), len(second["rows"]), first["counts"]["total"]) == (50, 17, 67)
    target = next(r for r in ts_lv(snapshot)["rows"] if not r["alerts"])["sub_ticket_id"]  # 경고는 지울 수 없는 기록
    snapshot.execute("UPDATE scoring.sub_ticket SET sla_resolution_target_h = NULL, sla_first_response_target_h = NULL "
                     "WHERE sub_ticket_id = %s", (target,))
    rows = ts_lv(snapshot)["rows"]
    # 기본 정렬은 내 차례 묶음이 먼저라(add-inbox-turn-depth), SLA 미정 줄은 자기 묶음의 맨 아래다
    group = [r for r in rows if r["turn"] == next(x["turn"] for x in rows if x["sub_ticket_id"] == target)]
    assert group[-1]["sub_ticket_id"] == target and group[-1]["remaining_h"] is None



def test_counts_new_escalated_breach_risk(snapshot):
    """add-inbox-row-fields: counts에 신규·이관·기한 초과·기한 임박이 더해진다. 초과와 임박은 겹치지 않고, 줄에 국가·문의 제목이 있다."""
    got = ts_lv(snapshot)
    rows, c = got["rows"], got["counts"]
    breached = [r for r in rows if set(r["alerts"]) & {"FR_BREACHED", "RES_BREACHED"}]
    at_risk = [r for r in rows if r["alerts"] and r not in breached]
    assert c["breach"] == len(breached) > 0
    assert c["risk"] == len(at_risk)
    assert c["breach"] + c["risk"] == c["alert"]
    assert c["new"] == sum(r["status"] == "NEW" for r in rows)
    assert c["escalated"] == sum(r["status"] == "ESCALATED" for r in rows)
    assert all("country" in r and "inquiry_subject" in r for r in rows)
    assert any(r["country"] for r in rows)  # 문의 제목은 채점용 재생 데이터에 비어 있어 칸이 있는지만 본다


def test_inbox_turn_sql_matches_rules(snapshot):
    """add-inbox-turn-depth: SQL로 옮긴 규칙이 app/rules/turn.py의 순수 함수와 모든 줄에서 같다. 기본 정렬은 내 차례 묶음이 먼저다."""
    from app.rules.turn import TURN_RANK, depth_of, turn_of

    got = ts_lv(snapshot, include_closed=True)
    rows = got["rows"]
    assert rows
    for r in rows:
        assert (r["turn"], r["next_action"]) == turn_of(r["status"], r["needs_info"], r["has_unsent_draft"], r["dept_replied"]), r["sub_ticket_id"]
        assert r["review_depth"] == depth_of(r["priority"], r["urgency_flag"], r["needs_info"]), r["sub_ticket_id"]
    ranks = [TURN_RANK[r["turn"]] for r in rows]
    assert ranks == sorted(ranks)  # ME → DEPT·CUSTOMER → DONE
    assert got["counts"]["turn_me"] == sum(r["turn"] == "ME" for r in rows)


def test_inbox_assignee_turn_depth_filters(snapshot):
    """담당·차례·검토 모드 필터와 counts.mine."""
    allrows = ts_lv(snapshot)["rows"]
    name = next(r["assignee_masked"] for r in allrows if r["assignee_masked"])
    mine = ts_lv(snapshot, assignee=name, me=name)
    assert mine["rows"] and all(r["assignee_masked"] == name for r in mine["rows"])
    assert mine["counts"]["mine"] == mine["counts"]["total"] == len(mine["rows"])
    team = ts_lv(snapshot, me=name)
    assert team["counts"]["mine"] == len(mine["rows"]) and team["counts"]["total"] > team["counts"]["mine"]
    me_rows = ts_lv(snapshot, turn=["ME"])["rows"]
    assert me_rows and all(r["turn"] == "ME" for r in me_rows)
    deep = ts_lv(snapshot, depth=["DEEP"])
    assert deep["counts"]["deep"] == len(deep["rows"]) and all(r["review_depth"] == "DEEP" for r in deep["rows"])


def test_detail_turn_depth_same_as_inbox_row(api):
    """add-inbox-turn-depth: 상세의 하위 문의 turn·next_action·review_depth가 접수함 줄과 같다."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    client = api[0]
    got = client.get(f"/tickets/{tid}").json()
    by_id = {s["sub_ticket"]["sub_ticket_id"]: s for s in got["sub_tickets"]}
    checked = 0
    for dept in ("TS_ENERGY", "GCS_L1"):
        for row in client.get("/tickets", params={"dept": dept, "q": tid}).json()["rows"]:
            sub = by_id[row["sub_ticket_id"]]
            assert (sub["turn"], sub["next_action"], sub["review_depth"]) == (row["turn"], row["next_action"], row["review_depth"])
            checked += 1
    assert checked == 2
