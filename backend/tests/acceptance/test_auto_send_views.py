"""자동 발송의 화면 연동 서버 값 (변경 add-auto-send-views): 접수함 auto 필터·auto_state·REVIEW_AUTO 차례, 상세, 대시보드·내 실적의 자동 처리 숫자."""

from __future__ import annotations

from tests.acceptance.test_auto_send import manual, sub_of, turn_on
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)
from app.rules.turn import turn_of


def inbox_row(client, detail, **params):
    sub = sub_of(detail)["sub_ticket"]
    got = client.get("/tickets", params={"dept": sub["assigned_dept"], "q": detail["ticket"]["ticket_id"], **params}).json()
    return got, next((r for r in got["rows"] if r["sub_ticket_id"] == sub["sub_ticket_id"]), None)


def test_turn_of_review_auto_is_my_turn_even_when_resolved():
    assert turn_of("RESOLVED", False, False, False, "PENDING") == ("ME", "REVIEW_AUTO")
    assert turn_of("RESOLVED", False, False, False, "REVIEWED") == ("DONE", "DONE")
    assert turn_of("RESOLVED", False, False, False) == ("DONE", "DONE")


def test_inbox_shows_auto_sent_until_reviewed(api):
    """자동 발송 직후: 닫힌 문의여도 기본 목록에 내 차례(REVIEW_AUTO)로 보이고 auto 건수에 든다. 검수하면 DONE이 되어 기본 목록에서 빠진다."""
    client, conn = api[0], api[2]
    turn_on(conn)
    detail = manual(api)
    sid = sub_of(detail)["sub_ticket"]["sub_ticket_id"]
    assert sub_of(detail)["auto_state"] == "PENDING" and sub_of(detail)["next_action"] == "REVIEW_AUTO"
    got, row = inbox_row(client, detail)
    assert row and row["auto_state"] == "PENDING" and row["turn"] == "ME" and row["next_action"] == "REVIEW_AUTO"
    assert got["counts"]["auto"] >= 1 and got["counts"]["auto_pending"] >= 1
    got, row = inbox_row(client, detail, auto=True)
    assert row and all(r["auto_state"] != "NONE" for r in got["rows"])
    assert client.post(f"/sub-tickets/{sid}/auto-review", headers={"X-Agent-Id": "leo"}).status_code == 200
    got, row = inbox_row(client, detail)
    assert row is None  # 검수까지 끝난 닫힌 문의는 기본 목록에 없다
    got, row = inbox_row(client, detail, auto=True)
    assert row and row["auto_state"] == "REVIEWED" and row["turn"] == "DONE"
    assert client.get(f"/tickets/{detail['ticket']['ticket_id']}").json()["sub_tickets"][0]["auto_state"] == "REVIEWED"


def test_non_auto_rows_have_state_none(api):
    client, conn = api[0], api[2]
    turn_on(conn, enabled=False)
    detail = manual(api)
    got, row = inbox_row(client, detail)
    assert row and row["auto_state"] == "NONE"
    got, row = inbox_row(client, detail, auto=True)
    assert row is None


def test_dashboard_and_performance_count_auto(api):
    client, conn = api[0], api[2]
    turn_on(conn)
    before = client.get("/dashboard/summary").json()["auto"]
    detail = manual(api)
    sub = sub_of(detail)["sub_ticket"]
    after = client.get("/dashboard/summary").json()["auto"]
    assert after["sent"] == before["sent"] + 1 and after["total"] == after["sent"] + after["human"]
    client.post(f"/sub-tickets/{sub['sub_ticket_id']}/auto-review", headers={"X-Agent-Id": "leo"})
    assert client.get("/dashboard/summary").json()["auto"]["reviewed"] == after["reviewed"] + 1
    perf = client.get("/me/performance", headers={"X-Agent-Id": "leo"}).json()
    assert set(perf["auto"]) == {"sent", "pending"} and perf["auto"]["pending"] >= 0
