"""내부 메모 (변경 add-internal-notes). 상담원끼리 남기는 메모이며 고객 메시지·상세의 고객 쪽 값에 섞이지 않는다."""

from __future__ import annotations

import json

from app.api.notes import MAX_LEN, MSG_EMPTY, MSG_NO_AGENT, MSG_NO_TICKET, MSG_TOO_LONG
from tests.acceptance.test_compound_inquiry import compound
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)

H = {"X-Agent-Id": "leo"}


def test_add_and_list_notes(api):
    """메모를 남기면 201과 남긴 사람·시각이 오고, 목록은 시각순이다."""
    tid = compound(api)["ticket"]["ticket_id"]
    client = api[0]
    first = client.post(f"/tickets/{tid}/notes", json={"body": "  통화로 확인함  "}, headers=H)
    assert first.status_code == 201
    got = first.json()
    assert got["body"] == "통화로 확인함" and got["author"] == "leo" and got["ticket_id"] == tid and got["created_at_utc"]
    client.post(f"/tickets/{tid}/notes", json={"body": "다음 담당자에게: 회신 오면 바로 확인"}, headers={"X-Agent-Id": "mia"})
    notes = client.get(f"/tickets/{tid}/notes").json()
    assert [n["author"] for n in notes] == ["leo", "mia"]
    assert [n["body"] for n in notes][0] == "통화로 확인함"


def test_note_validation(api):
    """빈 메모·2000자 초과·상담원 미선택은 400, 없는 티켓은 404. 막힌 요청은 아무것도 저장하지 않는다."""
    tid = compound(api)["ticket"]["ticket_id"]
    client = api[0]
    for body, msg in (("", MSG_EMPTY), ("   ", MSG_EMPTY), ("가" * (MAX_LEN + 1), MSG_TOO_LONG)):
        res = client.post(f"/tickets/{tid}/notes", json={"body": body}, headers=H)
        assert res.status_code == 400 and res.json()["detail"] == msg
    assert client.post(f"/tickets/{tid}/notes", json={"body": "내용"}).json()["detail"] == MSG_NO_AGENT
    assert client.post("/tickets/CSV1-999999/notes", json={"body": "내용"}, headers=H).json()["detail"] == MSG_NO_TICKET
    assert client.get("/tickets/CSV1-999999/notes").status_code == 404
    assert client.get(f"/tickets/{tid}/notes").json() == []
    ok = client.post(f"/tickets/{tid}/notes", json={"body": "가" * MAX_LEN}, headers=H)
    assert ok.status_code == 201  # 경계값 2000자는 된다


def test_note_counts_in_inbox_and_never_in_customer_side(api):
    """접수함 줄의 memo_count가 메모 수와 같고, 메모는 상세의 메시지·초안(고객에게 가는 글)에 섞이지 않는다."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    client = api[0]
    secret = "내부용-절대고객에게보이면안됨"
    client.post(f"/tickets/{tid}/notes", json={"body": secret}, headers=H)
    client.post(f"/tickets/{tid}/notes", json={"body": "두 번째 메모"}, headers=H)
    rows = [r for dept in ("TS_ENERGY", "GCS_L1") for r in client.get("/tickets", params={"dept": dept, "q": tid}).json()["rows"]]
    assert rows and all(r["memo_count"] == 2 for r in rows)
    after = client.get(f"/tickets/{tid}").json()
    assert secret not in json.dumps({"messages": after["messages"], "subs": [s["drafts"] for s in after["sub_tickets"]]}, ensure_ascii=False)
