"""접수 시뮬레이터와 시연용 불러오기 완료 기준 (FR-001, FR-003, 변경 add-intake-simulator).

API로 접수한다. 언어 모델은 대역 Transport, DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.llm.client import LlmTimeout
from tests.acceptance.test_drafts import GLOSS_OK, L2_QUOTE, QUOTE_BODY, FakeTransport, l1
from tests.acceptance.test_run_log import runs_of, steps_of
from tests.acceptance.test_ticket_detail import api, gold_input, index  # noqa: F401  (api 픽스처)

QUOTE_REPLIES = dict(L1=[l1("QUOTE", "fr", "NONE", "price quotation")], L2=[L2_QUOTE],
                     L4=[{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], L7=[GLOSS_OK])


def post(api, data, **replies):
    client, clients, _ = api
    clients.fake = FakeTransport(**(replies or QUOTE_REPLIES))
    return client.post("/tickets", json=data)


def errors(res):
    assert res.status_code == 400, res.text
    return {e["field"]: e["message"] for e in res.json()["detail"]["errors"]}


def count(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


# --- FR-001 ---


def test_ac_001_1_intake(api):
    """AC-001-1: NEW 티켓, INQUIRY 1건, NEW 이력 1건, 처리 흐름 시작(run)."""
    client, clients, conn = api
    clients.fake = FakeTransport(**QUOTE_REPLIES)
    data = gold_input(conn, "CSV1-000004")
    data.pop("source"), data.pop("source_ticket_id")
    clients.fake = FakeTransport(L1=[LlmTimeout("t")])  # 처리 흐름이 끝난 상태를 보지 않고 접수 직후 기록만 본다
    res = client.post("/tickets", json=data)
    assert res.status_code == 201 and res.json()["processing"] is True
    tid = res.json()["ticket_id"]
    sub = f"{tid}-1"
    assert count(conn, "SELECT count(*) FROM svc.ticket_message WHERE ticket_id = %s AND message_type = 'INQUIRY'", tid) == 1
    assert conn.execute("""SELECT to_status, event_kind FROM svc.ticket_status_history WHERE sub_ticket_id = %s
                            ORDER BY history_id""", (sub,)).fetchall()[0] == ("NEW", "INTAKE")
    assert count(conn, "SELECT count(*) FROM svc.ticket_status_history WHERE sub_ticket_id = %s AND to_status = 'NEW'", sub) == 1
    assert conn.execute("SELECT source FROM svc.ticket WHERE ticket_id = %s", (tid,)).fetchone()[0] == "SIMULATOR"
    assert [r["trigger"] for r in runs_of(api, tid)] == ["INTAKE"]


def test_ac_001_2_unknown_customer(api):
    """AC-001-2: 없는 customer_id → 400, 그 항목에 오류, 티켓 없음."""
    _, _, conn = api
    before = count(conn, "SELECT count(*) FROM svc.ticket")
    res = post(api, gold_input(conn, "CSV1-000004") | {"customer_id": "CUST-9999"})
    assert errors(res) == {"customer_id": "고객 ID를 찾을 수 없음"}
    assert count(conn, "SELECT count(*) FROM svc.ticket") == before


def test_ac_001_3_subject_not_in_classification(api, monkeypatch):
    """AC-001-3: 제목은 분류(L1) 입력에 없다(전문 기록으로 확인)."""
    monkeypatch.setenv("LOG_FULL_LLM_IO", "true")
    _, _, conn = api
    subject = "URGENT subject line 7731"
    res = post(api, gold_input(conn, "CSV1-000004") | {"inquiry_subject": subject})
    tid = res.json()["ticket_id"]
    (run,) = runs_of(api, tid)
    t2 = next(s for s in steps_of(api, run["run_id"]) if s["step_name"] == "T2")
    (io,) = t2["output_json"]["full_io"]
    assert io["call"] == "L1" and subject not in io["prompt"] and "7731" not in str(t2)
    assert conn.execute("SELECT inquiry_subject FROM svc.ticket WHERE ticket_id = %s", (tid,)).fetchone()[0] == subject


def test_ac_001_4_retry_same_ticket(api):
    """AC-001-4: L1 실패 → NEW로 남고 run FAILED. 다시 시도하면 같은 티켓으로 새 RETRY run이 돈다."""
    client, clients, conn = api
    res = post(api, gold_input(conn, "CSV1-000004"), L1=[LlmTimeout("t")])
    tid = res.json()["ticket_id"]
    detail = client.get(f"/tickets/{tid}").json()
    assert detail["run"]["status"] == "FAILED" and detail["sub_tickets"][0]["state"]["status"] == "NEW"
    assert detail["can_retry"]  # [다시 시도] 버튼
    assert detail["sub_tickets"][0]["sub_ticket"]["pipeline_error"].endswith("다시 시도")

    clients.fake = FakeTransport(**QUOTE_REPLIES)
    res = client.post(f"/tickets/{tid}/reprocess")
    assert res.status_code == 202 and res.json()["ticket_id"] == tid
    first, again = runs_of(api, tid)
    assert (first["status"], again["trigger"], again["status"]) == ("FAILED", "RETRY", "SUCCESS")
    detail = client.get(f"/tickets/{tid}").json()
    assert detail["run"]["run_id"] == again["run_id"] and not detail["processing"]
    assert detail["sub_tickets"][0]["sub_ticket"]["category_code"] == "QUOTE"
    assert detail["sub_tickets"][0]["state"]["status"] == "IN_PROGRESS" and not detail["can_retry"]


def test_retry_refused(api):
    """없는 티켓 404, 도는 중이면 409(design 결정 4). 실패가 아닌 티켓의 다시 처리는 19번에서 열림(C-98)."""
    client, _, conn = api
    tid = post(api, gold_input(conn, "CSV1-000004")).json()["ticket_id"]
    assert client.post("/tickets/CSV1-999999/reprocess").status_code == 404
    with conn.transaction():
        conn.execute("""INSERT INTO svc.agent_run (ticket_id, trigger, started_at_utc, llm_model)
                        VALUES (%s, 'RETRY', now(), 'm')""", (tid,))
    assert client.get(f"/tickets/{tid}").json()["processing"]  # 단계를 쓰기 전에도 처리 중(C-87 해소)
    res = client.post(f"/tickets/{tid}/reprocess")
    assert res.status_code == 409 and res.json()["detail"] == "처리 중"


def test_field_errors_all_at_once(api):
    """FR-001 처리 1·예외 표: 항목별 오류를 한 번에, 티켓은 만들지 않는다."""
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    res = post(api, {"channel": "FAX", "customer_id": "CUST-0350", "product_code": "NOPE", "language": "ko",
                     "inquiry_body": "   ", "received_at_utc": future})
    assert errors(res) == {"channel": "채널을 고르세요", "product_code": "제품 코드를 찾을 수 없음(모르면 비우세요)",
                           "language": "고객 언어를 고르세요", "inquiry_body": "내용을 입력하세요",
                           "received_at_utc": "접수 시각은 미래일 수 없음"}
    assert errors(post(api, {}))["customer_id"] == "고객 ID를 찾을 수 없음"
    _, _, conn0 = api
    bad_source = gold_input(conn0, "CSV1-000004") | {"source": "LOAD", "source_ticket_id": None}
    assert set(errors(post(api, bad_source))) == {"source"}
    _, _, conn = api
    too_long = gold_input(conn, "CSV1-000004") | {"inquiry_body": "a" * 2001}
    assert errors(post(api, too_long)) == {"inquiry_body": "본문은 2000자 이하여야 합니다"}


def test_contact_saved_not_in_pipeline(api, monkeypatch):
    """FR-001 입력 표 v1.5 가-7: 연락처 원문은 ticket에 저장, 처리 흐름 입력·실행 로그에는 없다. 제품 코드는 비워도 된다."""
    monkeypatch.setenv("LOG_FULL_LLM_IO", "true")
    _, _, conn = api
    contact = {"contact_name": "Kim Minsu", "contact_email": "minsu.kim@example.com", "contact_phone": "+82-10-5555-0101"}
    tid = post(api, gold_input(conn, "CSV1-000004") | contact | {"product_code": None}).json()["ticket_id"]
    row = conn.execute("SELECT contact_name, contact_email, contact_phone FROM svc.ticket WHERE ticket_id = %s",
                       (tid,)).fetchone()
    assert row == tuple(contact.values())
    logs = str(conn.execute("""SELECT json_agg(json_build_array(st.input_json, st.output_json)) FROM svc.agent_step st
                                JOIN svc.agent_run r USING (run_id) WHERE r.ticket_id = %s""", (tid,)).fetchone()[0])
    assert "Kim Minsu" not in logs and "minsu.kim" not in logs and "5555-0101" not in logs  # 티켓 번호(CSV1-005555 등)와 겹치지 않게


# --- FR-003 ---


def test_ac_003_1_load_000017(api):
    """AC-003-1: CSV1-000017 → 입력 6칸, 제목·정답 열은 없다."""
    client = api[0]
    res = client.get("/gold/tickets/CSV1-000017")
    assert res.status_code == 200
    got = res.json()
    assert (got["channel"], got["customer_id"], got["product_code"], got["language"]) == ("PHONE", "CUST-0350", "ACB-AS-2000", "en")
    assert got["received_at_utc"].startswith("2025-10-02T09:45:43") and got["inquiry_body"]
    assert set(got) == {"source_ticket_id", "channel", "customer_id", "product_code", "language", "inquiry_body",
                        "received_at_utc", "gold_set"}


def test_ac_003_2_test_split_loads(api):
    """AC-003-2: 평가용(test)이던 CSV1-001112도 똑같이 채워진다."""
    got = api[0].get("/gold/tickets/CSV1-001112").json()
    assert got["source_ticket_id"] == "CSV1-001112" and got["channel"] and got["inquiry_body"] and got["gold_set"] is False


def test_load_errors(api):
    """FR-003 예외 표: 형식 오류 400, 없는 번호 404."""
    client = api[0]
    assert client.get("/gold/tickets/17").json() == {"detail": "형식: CSV1-000000 또는 GS-001"}
    assert client.get("/gold/tickets/CSV1-000017-1").status_code == 400
    res = client.get("/gold/tickets/CSV1-999999")
    assert res.status_code == 404 and res.json()["detail"] == "문의를 찾을 수 없음"


def test_loaded_intake_is_load(api):
    """FR-003 처리 4: 불러온 값으로 접수하면 원본 번호가 남고 출처는 LOAD."""
    client, clients, conn = api
    loaded = client.get("/gold/tickets/CSV1-000004").json()
    data = {k: loaded[k] for k in ("channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")}
    tid = post(api, data | {"source_ticket_id": loaded["source_ticket_id"]}).json()["ticket_id"]
    assert conn.execute("SELECT source, source_ticket_id FROM svc.ticket WHERE ticket_id = %s",
                        (tid,)).fetchone() == ("LOAD", "CSV1-000004")
    assert client.get(f"/tickets/{tid}").json()["ticket"]["source_ticket_id"] == "CSV1-000004"


def test_gold_set_flag(api):
    """FR-003 처리 1·2, 화면 정의서 v2 부록 B-1: 팀 정답지 문의는 원본 번호로도 GS- 번호로도 불러오고 gold_set: true.
    GS- 번호로 접수한 티켓의 상세에도 "채점용 문의"."""
    client, _, conn = api
    with conn.transaction():
        conn.execute("""INSERT INTO eval.gold_set (gold_set_id, set_version, source_ticket_id, language, inquiry_body, created_by)
                        VALUES ('GS-901', 'test', 'CSV1-000017', 'en', 'x', 'test')""")
        conn.execute("""INSERT INTO eval.gold_set (gold_set_id, set_version, channel, customer_id, product_code, language,
                            inquiry_body, received_at_utc, category_code, created_by)
                        VALUES ('GS-902', 'test', 'EMAIL', 'CUST-0350', NULL, 'de', 'Bitte Angebot fuer 2 Stueck.',
                                '2025-10-05T08:00:00Z', 'QUOTE', 'test')""")
    assert client.get("/gold/tickets/CSV1-000017").json()["gold_set"] is True
    got = client.get("/gold/tickets/gs-902").json()
    assert got == {"source_ticket_id": "GS-902", "channel": "EMAIL", "customer_id": "CUST-0350", "product_code": None,
                   "language": "de", "inquiry_body": "Bitte Angebot fuer 2 Stueck.",
                   "received_at_utc": "2025-10-05T08:00:00Z", "gold_set": True}
    assert client.get("/gold/tickets/GS-999").status_code == 404
    data = {k: got[k] for k in ("channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")}
    tid = post(api, data | {"source_ticket_id": "GS-902"}).json()["ticket_id"]
    assert client.get(f"/tickets/{tid}").json()["ticket"]["gold_set"] is True


def test_ref_lists(api):
    """§8-1 GET /ref/*: 고객 검색(ID·회사명), 제품 23종, 부서 13개."""
    client = api[0]
    found = client.get("/ref/customers", params={"q": "cust-0350"}).json()
    assert [c["customer_id"] for c in found] == ["CUST-0350"] and set(found[0]) == {"customer_id", "company_masked", "country", "tier"}
    assert len(client.get("/ref/customers").json()) == 20
    company = found[0]["company_masked"]
    assert [c["customer_id"] for c in client.get("/ref/customers", params={"q": company.lower()}).json()] == ["CUST-0350"]
    assert len(client.get("/ref/products").json()) == 23
    assert len(client.get("/ref/departments").json()) == 13
