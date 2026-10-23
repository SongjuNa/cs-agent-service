"""가상 상담원 명단과 담당 배정 (변경 add-agent-roster, 조장 결정 2026-10-23, 기술 명세서 v1.4 §8-3).

접수·수정은 API(대역 언어 모델, 롤백), 재생은 운영진 4,000건을 scoring에 재생(롤백)한다.
"""

from __future__ import annotations

from app.db.assignees import agents, name_of, roster
from app.db.workload import workload
from tests.acceptance.test_inbox import snapshot  # noqa: F401  (snapshot 픽스처)
from tests.acceptance.test_status_sla import SNAPSHOT, replayed  # noqa: F401
from tests.acceptance.test_ticket_detail import api, index, info_request  # noqa: F401  (api 픽스처)
from tests.acceptance.test_ticket_detail_full import first, patch, detail_of


def test_roster_shape(conn):
    """11개 부서 × 12명 + 시연용 2명, 이름이 모두 다르고, 운영진 데이터 상담원 ID가 모두 명단에 있다."""
    depts = [r[0] for r in conn.execute("SELECT dept_code FROM ref.department ORDER BY dept_code")]
    assert sorted({a["dept"] for a in roster()}) == depts
    demo = {"QA_CLAIM", "RND_FW"}  # 운영진 데이터에 상담원이 없는 부서: 시연용 1명(FR-033 처리 10)
    assert all(len(agents(d)) == (1 if d in demo else 12) for d in depts)
    assert [a["demo"] for d in sorted(demo) for a in agents(d)] == [True, True]
    assert {a["source_id"] for a in roster() if a["dept"] in demo} == {"QA_CLAIM_AGENT_01", "RND_FW_AGENT_01"}
    assert len({a["name"] for a in roster()}) == len(roster()) == 134
    ids = {r[0] for r in conn.execute("SELECT DISTINCT assignee_masked FROM gold.ticket_gold")}
    assert {name_of(i) for i in ids}.isdisjoint(ids)  # 모두 이름으로 바뀐다


def test_ref_agents(api):
    """GET /ref/agents?dept=TS_LV → TS_LV 12명, 명단 순서."""
    got = api[0].get("/ref/agents", params={"dept": "TS_LV"}).json()
    assert [a["name"] for a in got] == [a["name"] for a in agents("TS_LV")] and len(got) == 12
    assert len(api[0].get("/ref/agents").json()) == 134


def test_intake_assigns_in_turn(api):
    """접수 두 건(TS_LV) → 명단 첫째, 둘째 사람이 차례로 맡는다(가장 적게 맡은 사람, C-127)."""
    names = [a["name"] for a in agents("TS_LV")]

    def least_loaded():  # 시작 상태가 비어 있지 않아도 같은 규칙으로 기대값을 셈
        load = dict(api[2].execute("""SELECT assignee_masked, count(*) FROM svc.sub_ticket WHERE assignee_masked = ANY(%s)
                                        AND status IN ('NEW','IN_PROGRESS','WAITING_CUSTOMER','ESCALATED') GROUP BY 1""",
                                   (names,)).fetchall())
        return min(names, key=lambda n: (load.get(n, 0), names.index(n)))

    got = []
    for _ in range(2):
        expected = least_loaded()
        got.append((expected, first(info_request(api))["sub_ticket"]))
    assert [s["assigned_dept"] for _, s in got] == ["TS_LV", "TS_LV"]
    assert [s["assignee_masked"] for _, s in got] == [e for e, _ in got]
    assert got[0][1]["assignee_masked"] != got[1][1]["assignee_masked"]


def test_dept_change_reassigns(api):
    """상담원 수정으로 담당 부서가 바뀌면 새 부서 사람이 맡는다. 부서가 그대로면 담당도 그대로."""
    d = info_request(api)
    s = first(d)
    before = s["sub_ticket"]["assignee_masked"]
    assert patch(api, s["sub_ticket"]["sub_ticket_id"], urgency_flag="NONE",
                 expected_version=s["version"]).status_code == 202
    same = first(detail_of(api, d["ticket"]["ticket_id"]))
    if same["sub_ticket"]["assigned_dept"] == "TS_LV":
        assert same["sub_ticket"]["assignee_masked"] == before
    assert patch(api, s["sub_ticket"]["sub_ticket_id"], category_code="QUOTE",
                 expected_version=same["version"]).status_code == 202
    after = first(detail_of(api, d["ticket"]["ticket_id"]))["sub_ticket"]
    assert after["assigned_dept"] != "TS_LV"
    assert after["assignee_masked"] in [a["name"] for a in agents(after["assigned_dept"])]


def test_unknown_value_kept(api):
    """명단에 없는 값(손으로 넣은 ID)은 다음 저장에서도 그대로 둔다(C-128)."""
    d = info_request(api)
    s = first(d)
    api[2].execute("UPDATE svc.sub_ticket SET assignee_masked = 'TS_LV_AGENT_09' WHERE sub_ticket_id = %s",
                   (s["sub_ticket"]["sub_ticket_id"],))
    assert patch(api, s["sub_ticket"]["sub_ticket_id"], urgency_flag="NONE",
                 expected_version=s["version"]).status_code == 202
    assert first(detail_of(api, d["ticket"]["ticket_id"]))["sub_ticket"]["assignee_masked"] == "TS_LV_AGENT_09"


def test_replay_names_and_my_work(snapshot):
    """재생 → 정답지 상담원 ID 대신 명단 이름, 그 이름으로 [내 담당]을 본다(W6, FR-047)."""
    c = snapshot
    gold_id = c.execute("SELECT assignee_masked FROM gold.ticket_gold WHERE ticket_id = 'CSV1-000017'").fetchone()[0]
    name = name_of(gold_id)
    assert gold_id == "TS_LV_AGENT_09" and name != gold_id
    (stored,) = c.execute("SELECT assignee_masked FROM scoring.sub_ticket WHERE sub_ticket_id = 'CSV1-000017-1'").fetchone()
    assert stored == name
    mine = workload(c, None, agent=name, as_of=SNAPSHOT, schema="scoring")
    expected = {r[0] for r in c.execute(
        """SELECT s.sub_ticket_id FROM scoring.sub_ticket s
            WHERE s.assignee_masked = %s AND s.status IN ('NEW','IN_PROGRESS','WAITING_CUSTOMER','ESCALATED')
              AND s.sla_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM scoring.sla_alert a WHERE a.sub_ticket_id = s.sub_ticket_id
                            AND a.cleared_at_utc IS NULL)""", (name,)).fetchall()}
    assert mine["scope"] == "mine" and {r["sub_ticket_id"] for r in mine["risks"]} == expected
    assert sum(len(w) for w in (mine["risks"], mine["waiting_customer"], mine["waiting_escalation"])) > 0
