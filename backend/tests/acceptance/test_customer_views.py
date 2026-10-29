"""고객 관리 완료 기준 (FR 초안 01, 변경 add-customer-views design 결정 4).

AC 초안 문장의 "CSV1-000017"은 원본 번호다. 접수하면 새 번호로 들어가고 원본 번호는 source_ticket_id에 남는다
(2026-10-29 조장 결정, 검토 자료 ①).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.status.transitions import transition
from tests.acceptance.test_ticket_detail import api, index, info_request  # noqa: F401  (api 픽스처)


def detail(api, customer_id="CUST-0350"):
    res = api[0].get(f"/customers/{customer_id}")
    assert res.status_code == 200, res.text
    return res.json()


def test_detail_history(api):
    """AC 초안: CSV1-000017(고객 CUST-0350)을 접수하면 상세 이력에 있고, 이력은 접수 시각 내림차순이다."""
    d = info_request(api)
    got = detail(api)
    rows = [h for h in got["history"] if h["ticket_id"] == d["ticket"]["ticket_id"]]
    assert rows and rows[0]["source_ticket_id"] == "CSV1-000017"
    times = [h["received_at_utc"] for h in got["history"]]
    assert times == sorted(times, reverse=True)
    assert got["tier"] == "PLATINUM" and got["country"] == "TH" and got["last_language"] == "en"


def test_country_th_33(api):
    """AC 초안: 나라별 집계에서 TH 고객 수 = 33(ref.customer의 TH 행 수). 나라는 20개."""
    res = api[0].get("/customers/countries")
    assert res.status_code == 200, res.text
    by = {r["country"]: r for r in res.json()}
    assert by["TH"]["customer_count"] == 33 and len(by) == 20
    listed = api[0].get("/customers", params={"country": "TH", "size": 200}).json()
    assert listed["total"] == 33 and {r["country"] for r in listed["rows"]} == {"TH"}


def test_unknown_customer(api):
    """design 결정 2: 없는 고객 → 404 "고객을 찾을 수 없음"."""
    res = api[0].get("/customers/CUST-9999")
    assert res.status_code == 404 and res.json()["detail"] == "고객을 찾을 수 없음"


def test_open_count_drops_when_resolved(api):
    """design 결정 1: 하위 문의를 RESOLVED로 바꾸면 그 고객의 open_count가 1 줄어든다."""
    d = info_request(api)

    def row():
        got = api[0].get("/customers", params={"q": "CUST-0350"}).json()["rows"]
        return next(r for r in got if r["customer_id"] == "CUST-0350")

    before = row()
    transition(api[2], d["sub_tickets"][0]["sub_ticket"]["sub_ticket_id"], "RESOLVED", "FINAL_REPLY_SENT",
               datetime.now(timezone.utc), "TS_LV_AGENT_09")
    after = row()
    assert after["open_count"] == before["open_count"] - 1 and after["ticket_count"] == before["ticket_count"]


def test_list_filters_and_tier_counts(api):
    """design 결정 1: 등급 거르기, 쪽 크기, 등급별 수(등급 거르기 전)."""
    got = api[0].get("/customers", params={"tier": "GOLD", "size": 10}).json()
    assert got["size"] == 10 and len(got["rows"]) == 10 and {r["tier"] for r in got["rows"]} == {"GOLD"}
    assert got["total"] == got["tier_counts"]["GOLD"] and sum(got["tier_counts"].values()) == 600


def test_read_only_and_no_gold():
    """proposal "읽기만", CLAUDE.md 규칙 6: 고치는 주소가 없고, 정답지(gold)를 읽지 않는다."""
    from app.main import app

    methods = {m for r in app.routes if getattr(r, "path", "").startswith("/customers") for m in r.methods}
    assert methods <= {"GET", "HEAD"}
    src = (Path(__file__).resolve().parents[2] / "app" / "db" / "customers.py").read_text(encoding="utf-8")
    assert "gold." not in src
