"""처리 실행 로그 완료 기준 (FR-036, 변경 add-run-log).

API를 TestClient로 부르고(test_ticket_detail.api), 언어 모델은 대역 Transport를 쓴다. DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import ast
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.api.tickets import process_ticket
from app.db import store
from app.db.runs import MSG_INTERRUPTED, close_stale_runs, purge_runs
from app.llm.client import LlmTimeout
from app.pipeline.runlog import RunLog
from tests.acceptance.test_drafts import FakeTransport
from tests.acceptance.test_status_sla import db, seed  # noqa: F401  (db 픽스처를 함께 쓴다)
from tests.acceptance.test_ticket_detail import api, gold_input, index, quote  # noqa: F401  (api 픽스처)

PIPELINE_STEPS = ["T2", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q8", "Q9", "Q10", "Q11", "Q13", "Q14", "T6"]
LLM_STEPS = {"T2": "l1_understand_v1", "Q1": "l2_extract_v2", "Q10": "l4_draft_v2", "Q13": "l7_gloss_v1",
             "Q14": "l8_verify_v1"}


class UsageTransport(FakeTransport):
    """응답마다 토큰 수(입력 100, 출력 20)를 남기는 대역 Transport(GeminiTransport.last_usage와 같은 모양)."""

    def send(self, prompt, schema):
        self.last_usage = None
        reply = super().send(prompt, schema)
        self.last_usage = (100, 20)
        return reply


def runs_of(api, ticket_id):
    res = api[0].get(f"/tickets/{ticket_id}/runs")
    assert res.status_code == 200, res.text
    return res.json()["runs"]


def steps_of(api, run_id):
    res = api[0].get(f"/runs/{run_id}/steps")
    assert res.status_code == 200, res.text
    return res.json()["steps"]


def by_name(steps):
    return {s["step_name"]: s for s in steps}


def test_ac_036_1_intake_steps(api):
    """AC-036-1: CSV1-000004 접수 → run 1개, T2부터 초안·검증까지 순서대로 모두 SUCCESS, Q9에 520과 4주."""
    detail = quote(api)
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    assert (run["trigger"], run["status"], run["current"]) == ("INTAKE", "SUCCESS", True)
    steps = steps_of(api, run["run_id"])
    assert [s["step_name"] for s in steps] == PIPELINE_STEPS
    assert all(s["result"] == "SUCCESS" for s in steps)
    lookups = {lv["item"]: lv for lv in by_name(steps)["Q9"]["output_json"]["lookups"]}
    assert Decimal(str(lookups["list_price_usd"]["value"])) == 520
    assert (lookups["std_lead_time_weeks"]["value"], lookups["std_lead_time_weeks"]["unit"]) == (4, "weeks")


def test_ac_036_2_no_subject_in_classification(api):
    """AC-036-2: 분류 단계(T2) 입력의 항목 이름 목록에 inquiry_subject가 없다."""
    detail = quote(api)
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    names = by_name(steps_of(api, run["run_id"]))["T2"]["input_json"]["field_names"]
    assert "body_masked" in names and not any("subject" in n for n in names)


def test_ac_036_3_timeout_then_retry(api):
    """AC-036-3: L1 시간 초과 → run FAILED, 마지막 단계 T2, LLM_TIMEOUT. 다시 처리하면 새 run, 이전 run은 남는다."""
    client, clients, conn = api
    clients.fake = FakeTransport(L1=[LlmTimeout("t")])
    data = gold_input(conn, "CSV1-000004")
    data["inquiry_subject"] = "Quote request"
    ticket_id = client.post("/tickets", json=data).json()["ticket_id"]
    (first,) = runs_of(api, ticket_id)
    assert (first["status"], first["last_step"]) == ("FAILED", "T2")
    (t2,) = steps_of(api, first["run_id"])
    assert (t2["step_name"], t2["result"], t2["error_kind"], t2["llm_calls"]) == ("T2", "FAILED", "LLM_TIMEOUT", 2)

    from tests.acceptance.test_drafts import GLOSS_OK, L2_QUOTE, QUOTE_BODY, l1
    clients.fake = FakeTransport(L1=[l1("QUOTE", "fr", "NONE", "price quotation")], L2=[L2_QUOTE],
                                 L4=[{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], L7=[GLOSS_OK])
    from contextlib import nullcontext
    process_ticket(lambda: nullcontext(conn), clients, ticket_id, trigger="RETRY")
    old, new = runs_of(api, ticket_id)
    assert old["run_id"] == first["run_id"] and old["status"] == "FAILED" and not old["current"]
    assert (new["trigger"], new["status"], new["current"]) == ("RETRY", "SUCCESS", True)
    detail = client.get(f"/tickets/{ticket_id}").json()  # 상세는 새 run의 결과를 읽는다
    assert detail["run"]["run_id"] == new["run_id"] and detail["sub_tickets"][0]["sub_ticket"]["category_code"] == "QUOTE"


def test_ac_036_5_priority_why_opens_step(api):
    """AC-036-5: 우선순위 줄의 "왜?" → 우선순위 단계(Q3) 출력(priority_rule_id, 적용 조건)."""
    detail = quote(api)
    row = next(r for r in detail["sub_tickets"][0]["evidence_rows"] if r["id"] == "C-03")
    ref = row["why"]["step"]
    assert ref["step_name"] == "Q3" and ref["run_id"] == detail["run"]["run_id"]
    step = next(s for s in steps_of(api, ref["run_id"]) if s["step_id"] == ref["step_id"])
    out = step["output_json"]
    assert out["priority_rule_id"] == detail["sub_tickets"][0]["sub_ticket"]["priority_rule_id"]
    assert out["priority_trace"] and {"rule_id", "matched"} <= set(out["priority_trace"][0])


def test_why_rows_point_to_steps(api):
    """FR-036 처리 7: 근거 줄마다 그 줄을 만든 단계를 가리킨다."""
    detail = quote(api)
    refs = {r["id"]: (r["why"]["step"] or {}).get("step_name") for r in detail["sub_tickets"][0]["evidence_rows"]}
    assert refs == {"C-01": "T2", "C-02": "T2", "M-C-01": "Q2", "C-03": "Q3", "C-04": "Q4", "C-07": "Q5",
                    "C-06": "Q6", "M-C-02": "Q9"}


def test_timing_and_usage(api):
    """FR-036 처리 2, §3-5: 모든 단계에 시간·소요, 언어 모델 단계에 호출 수·토큰·지시문 버전."""
    from tests.acceptance.test_drafts import GLOSS_OK, L2_QUOTE, QUOTE_BODY, l1
    client, clients, conn = api
    clients.fake = UsageTransport(L1=[l1("QUOTE", "fr", "NONE", "price quotation")], L2=[L2_QUOTE],
                                  L4=[{"body": QUOTE_BODY, "citations": [], "numbers_used": []}], L7=[GLOSS_OK])
    ticket_id = client.post("/tickets", json=gold_input(conn, "CSV1-000004")).json()["ticket_id"]
    (run,) = runs_of(api, ticket_id)
    steps = by_name(steps_of(api, run["run_id"]))
    for s in steps.values():
        assert s["started_at_utc"] <= s["finished_at_utc"] and s["latency_ms"] is not None or s["step_name"] == "T6"
    for name, version in LLM_STEPS.items():
        s = steps[name]
        assert (s["llm_calls"], s["input_tokens"], s["output_tokens"], s["prompt_version"]) == (1, 100, 20, version), name
    assert steps["Q3"]["llm_calls"] is None  # 규칙 단계는 언어 모델을 부르지 않는다
    assert (run["llm_calls"], run["input_tokens"], run["output_tokens"], run["failed_steps"]) == (5, 500, 100, 0)
    assert run["duration_ms"] is not None and run["duration_ms"] >= 0


def test_full_io_off_and_on(api, monkeypatch):
    """FR-036 처리 4: 전문은 기본으로 남기지 않고, LOG_FULL_LLM_IO=true면 가린 전문을 남긴다."""
    detail = quote(api)
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    assert all("full_io" not in (s["output_json"] or {}) for s in steps_of(api, run["run_id"]))

    monkeypatch.setenv("LOG_FULL_LLM_IO", "true")
    detail = quote(api, extra=" Contact: buyer.kim@example.com")
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    t2 = by_name(steps_of(api, run["run_id"]))["T2"]["output_json"]
    (io,) = t2["full_io"]
    assert io["call"] == "L1" and "<customer_message>" in io["prompt"] and io["response"]
    assert "buyer.kim@example.com" not in str(t2) and "***.masked" in io["prompt"]


def test_step_save_failure_keeps_result(api, monkeypatch, caplog):
    """FR-036 예외 1행: 단계 한 행 저장이 실패해도 처리 결과는 저장되고, 실패는 서버 로그에 남는다."""
    real = store._masked_json

    def broken(value):
        if isinstance(value, dict) and "priority_trace" in value:
            raise RuntimeError("로그 저장 실패 시험")
        return real(value)

    monkeypatch.setattr(store, "_masked_json", broken)
    with caplog.at_level(logging.ERROR, logger="app.db.store"):
        detail = quote(api)
    sub = detail["sub_tickets"][0]["sub_ticket"]
    assert sub["priority"] and sub["status"] == "IN_PROGRESS" and detail["run"]["status"] == "SUCCESS"
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    assert "Q3" not in [s["step_name"] for s in steps_of(api, run["run_id"])]
    assert any("실행 기록 저장 실패" in r.message for r in caplog.records)


def test_close_stale_runs(db):
    """FR-036 예외 2행: 끝나지 않은 실행은 서버가 켜질 때 FAILED로 닫고 문의에 UNKNOWN을 남긴다."""
    sub_id = seed(db, "CSV1-000017")
    ticket_id = sub_id.rsplit("-", 1)[0]
    run_id = store.start_run(db, ticket_id, sub_id, "INTAKE")
    now = datetime.now(timezone.utc)
    assert run_id in close_stale_runs(db, now)
    status, finished = db.execute("SELECT status, finished_at_utc FROM svc.agent_run WHERE run_id = %s",
                                  (run_id,)).fetchone()
    assert (status, finished) == ("FAILED", now)
    (error,) = db.execute("SELECT pipeline_error FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    assert error == MSG_INTERRUPTED and error.startswith("UNKNOWN")
    assert run_id not in close_stale_runs(db, now)  # 두 번 닫지 않는다


def test_purge_runs(db):
    """FR-036 예외 3행: 90일 지난 실행과 단계는 지우고, 메시지 이력과 자체 검사가 가리키는 실행은 남긴다(C-83)."""
    sub_id = seed(db, "CSV1-000017")
    ticket_id = sub_id.rsplit("-", 1)[0]
    old = datetime.now(timezone.utc) - timedelta(days=91)

    def finished_run():
        run_id = store.start_run(db, ticket_id, sub_id, "INTAKE")
        store.add_step(db, run_id, "Q3", output={"priority": "P3"})
        db.execute("UPDATE svc.agent_run SET finished_at_utc = %s, status = 'SUCCESS' WHERE run_id = %s", (old, run_id))
        return run_id

    gone, kept = finished_run(), finished_run()
    store.add_self_check(db, kept, sub_id, "LOW_CONFIDENCE", False, {"flag": "확신 낮음"})
    recent = store.start_run(db, ticket_id, sub_id, "INTAKE")
    store.finish_run(db, recent, "SUCCESS", "Q3")
    (messages_before,) = db.execute("SELECT count(*) FROM svc.ticket_message WHERE ticket_id = %s", (ticket_id,)).fetchone()

    removed = purge_runs(db, datetime.now(timezone.utc))
    assert gone in removed and kept not in removed and recent not in removed
    assert db.execute("SELECT count(*) FROM svc.agent_step WHERE run_id = %s", (gone,)).fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM svc.ticket_message WHERE ticket_id = %s", (ticket_id,)).fetchone()[0] == messages_before


def test_lookup_404(api):
    """FR-036 처리 7: 없는 티켓·실행은 404."""
    assert api[0].get("/tickets/NO-SUCH/runs").status_code == 404
    assert api[0].get("/runs/999999999/steps").status_code == 404


def test_reply_reprocess_failure_is_q1(db):
    """고객 회신 재처리(Q1부터)가 실패하면 실패 단계는 Q1이다(§2-4)."""
    from app.pipeline.graph import RunOutcome
    sub_id = seed(db, "CSV1-000017")
    ticket_id = sub_id.rsplit("-", 1)[0]
    run_id = store.start_run(db, ticket_id, sub_id, "CUSTOMER_REPLY")
    store.save_outcome(db, run_id, ticket_id, RunOutcome(None, "FAILED", error_type="LLM_TIMEOUT", message="t"), reply_id=1)
    assert db.execute("SELECT last_step FROM svc.agent_run WHERE run_id = %s", (run_id,)).fetchone()[0] == "Q1"


def test_runlog_without_node():
    """노드가 없는 단계(T6)는 시간 열을 비워 두고 저장 때 지금 시각을 쓴다."""
    assert RunLog().step_fields("T6") == {}


def test_run_modules_do_not_import_llm():
    """실행 기록 모듈은 언어 모델 호출 계층을 import하지 않는다(주기 점검이 부르고, Transport는 감싸기만 한다)."""
    root = Path(__file__).resolve().parents[2] / "app"
    for path in (root / "db" / "runs.py", root / "pipeline" / "runlog.py"):
        mods = {n.module for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.ImportFrom)}
        assert not any(m and m.startswith("app.llm") for m in mods), path
