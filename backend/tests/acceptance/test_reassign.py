"""담당 변경 (변경 add-reassign). 여러 문의를 한 번에 바꾸고, 바꾼 기록이 이력에 남는다."""

from __future__ import annotations

from app.api.assign import (MAX_IDS, MSG_NO_AGENT, MSG_NO_IDS, MSG_TOO_MANY, MSG_UNKNOWN, SKIP_DEPT, SKIP_NOT_FOUND,
                            SKIP_SAME)
from app.db.assignees import agents
from tests.acceptance.test_compound_inquiry import compound
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)

H = {"X-Agent-Id": "leo"}


def _other(dept: str, current: str | None) -> str:
    return next(a["name"] for a in agents(dept) if a["name"] != current)


def _row(client, dept: str, tid: str) -> dict:
    return client.get("/tickets", params={"dept": dept, "q": tid}).json()["rows"][0]


def test_assign_moves_and_records_history(api):
    """TS_ENERGY 문의의 담당을 같은 부서 다른 사람으로 바꾸면 접수함 줄이 바뀌고, 이력에 ASSIGNEE 한 줄이 남는다. 같은 사람에게 다시 하면 건너뛴다."""
    tid = compound(api)["ticket"]["ticket_id"]
    client = api[0]
    sid = f"{tid}-1"  # 펌웨어 문의 → TS_ENERGY
    before = _row(client, "TS_ENERGY", tid)["assignee_masked"]
    to = _other("TS_ENERGY", before)
    res = client.post("/sub-tickets/assign", json={"sub_ticket_ids": [sid], "assignee": to}, headers=H)
    assert res.status_code == 200 and res.json() == {"moved": [sid], "skipped": []}
    assert _row(client, "TS_ENERGY", tid)["assignee_masked"] == to
    events = [e for e in client.get(f"/tickets/{tid}/timeline").json() if e["kind"] == "ASSIGNEE"]
    assert len(events) == 1 and events[0]["from_assignee"] == before and events[0]["to_assignee"] == to and events[0]["changed_by"] == "leo"
    again = client.post("/sub-tickets/assign", json={"sub_ticket_ids": [sid], "assignee": to}, headers=H).json()
    assert again == {"moved": [], "skipped": [{"sub_ticket_id": sid, "reason": SKIP_SAME}]}
    assert len([e for e in client.get(f"/tickets/{tid}/timeline").json() if e["kind"] == "ASSIGNEE"]) == 1  # 기록이 겹치지 않는다


def test_assign_skips_without_blocking_others(api):
    """다른 부서 사람·없는 문의는 사유와 함께 건너뛰고, 나머지는 바뀐다."""
    tid = compound(api)["ticket"]["ticket_id"]
    client = api[0]
    s1, s2 = f"{tid}-1", f"{tid}-2"  # TS_ENERGY, GCS_L1
    to = _other("GCS_L1", _row(client, "GCS_L1", tid)["assignee_masked"])  # 지금 담당과 다른 사람
    res = client.post("/sub-tickets/assign", json={"sub_ticket_ids": [s1, s2, "CSV1-999999-1"], "assignee": to}, headers=H).json()
    assert res["moved"] == [s2]
    assert {(x["sub_ticket_id"], x["reason"]) for x in res["skipped"]} == {(s1, SKIP_DEPT), ("CSV1-999999-1", SKIP_NOT_FOUND)}
    assert _row(client, "GCS_L1", tid)["assignee_masked"] == to


def test_assign_validation(api):
    """빈 선택·너무 많음·상담원 미선택·명단에 없는 이름은 400이고 아무것도 바꾸지 않는다."""
    tid = compound(api)["ticket"]["ticket_id"]
    client = api[0]
    sid = f"{tid}-1"
    name = agents("TS_ENERGY")[0]["name"]
    cases = [({"sub_ticket_ids": [], "assignee": name}, H, MSG_NO_IDS),
             ({"sub_ticket_ids": [f"X{i}" for i in range(MAX_IDS + 1)], "assignee": name}, H, MSG_TOO_MANY),
             ({"sub_ticket_ids": [sid], "assignee": name}, {}, MSG_NO_AGENT),
             ({"sub_ticket_ids": [sid], "assignee": "없는사람"}, H, MSG_UNKNOWN)]
    before = _row(client, "TS_ENERGY", tid)["assignee_masked"]
    for body, headers, msg in cases:
        res = client.post("/sub-tickets/assign", json=body, headers=headers)
        assert res.status_code == 400 and res.json()["detail"] == msg
    assert _row(client, "TS_ENERGY", tid)["assignee_masked"] == before
