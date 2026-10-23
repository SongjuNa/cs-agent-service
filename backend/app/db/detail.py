"""티켓 상세 묶음과 검토 표시 5개 (FR-024, 기술 명세서 v1.4 §5-7, §8-1 GET /tickets/{id}, 화면 정의서 v2 SCR-03M).

저장된 값만 읽는다(FR-024 처리 5). 검토 표시는 저장하지 않고 읽을 때 계산한다(§5-7).
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.db.store import body_sha, check_type_of, latest_gloss
from app.llm.verify import VerifyResult
from app.pipeline.state import VerifyFinding
from app.sla.alerts import alert_history
from app.sla.clock import clocks
from app.status.transitions import history, wait_intervals

SAFETY_URGENCY = {"SAFETY", "SITE_DOWN"}
# ③에서 빼는 자체 검사: ⑤ 검증(§5-7 ③, 화면 정의서 v2 0-6)
NOT_IN_MARK_3 = ("VERIFY",)
DRAFT_FLAGS = {"자동 번역 실패", "초안 생성 실패. 다시 시도", "초안 길이 초과", "인용·숫자 불일치",
               "대역 없음(번역 실패)", "인용·숫자 확인"}


def _rows(conn: Connection, sql: str, params: tuple) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _row(conn: Connection, sql: str, params: tuple) -> dict[str, Any] | None:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def ticket_detail(conn: Connection, ticket_id: str) -> dict[str, Any] | None:
    ticket = _row(conn, """
        SELECT t.ticket_id, t.received_at_utc, t.channel, t.language, t.body_language, t.body_language_uncertain,
               t.customer_id, t.customer_tier, c.company_masked, c.country, t.source, t.source_ticket_id,
               EXISTS (SELECT 1 FROM eval.gold_set g WHERE g.source_ticket_id = t.source_ticket_id) AS gold_set
          FROM svc.ticket t JOIN ref.customer c ON c.customer_id = t.customer_id
         WHERE t.ticket_id = %s""", (ticket_id,))
    if ticket is None:
        return None
    run = _row(conn, """SELECT run_id, status, last_step, started_at_utc, finished_at_utc FROM svc.agent_run
                         WHERE ticket_id = %s AND trigger = 'INTAKE' ORDER BY run_id DESC LIMIT 1""", (ticket_id,))
    processing = run is None or run["status"] is None
    rows = _rows(conn, "SELECT * FROM svc.sub_ticket WHERE ticket_id = %s ORDER BY seq", (ticket_id,))
    sla = clocks(conn, [r["sub_ticket_id"] for r in rows])
    subs = [_sub_detail(conn, s, run) | _state(conn, s, sla.get(s["sub_ticket_id"])) for s in rows]
    summary = _row(conn, """SELECT status, rep_sub_ticket_id, rep_res_status, rep_remaining_h, open_count, inquiry_count
                              FROM svc.v_ticket_summary WHERE ticket_id = %s""", (ticket_id,))
    return {"ticket": ticket, "summary": summary, "run": run, "processing": processing, "sub_tickets": subs}


def _state(conn: Connection, sub: dict[str, Any], sla: dict[str, Any] | None) -> dict[str, Any]:
    """상태·SLA·이력 (FR-025 출력, FR-026 출력, 기술 명세서 §6-4)."""
    hist = history(conn, sub["sub_ticket_id"])
    return {
        "state": {k: sub[k] for k in ("status", "version", "resolved_at_utc", "final_action")},
        "sla": sla,
        "history": hist,
        "wait_intervals": wait_intervals(hist),
        "alerts": alert_history(conn, sub["sub_ticket_id"]),  # FR-027 출력
    }


def _steps(conn: Connection, run_id: int | None) -> dict[str, Any]:
    if run_id is None:
        return {}
    return {r["step_name"]: r for r in _rows(
        conn, """SELECT step_name, result, input_json, output_json, error_kind, error FROM svc.agent_step
                  WHERE run_id = %s ORDER BY step_order""", (run_id,))}


def _sub_detail(conn: Connection, sub: dict[str, Any], run: dict[str, Any] | None) -> dict[str, Any]:
    run_id = run["run_id"] if run else None
    steps = _steps(conn, run_id)
    out = {name: (st["output_json"] or {}) for name, st in steps.items()}
    flags: list[str] = next((o["flags"] for o in reversed(list(out.values())) if "flags" in o), [])
    failed = _rows(conn, """SELECT check_type, detail FROM eval.self_check
                             WHERE run_id = %s AND sub_ticket_id = %s AND NOT passed_yn AND check_type <> ALL(%s)
                             ORDER BY check_id""", (run_id, sub["sub_ticket_id"], list(NOT_IN_MARK_3)))
    labels = dict(conn.execute("SELECT field, label FROM ref.info_field").fetchall())
    status = "처리 중" if run is None or run["status"] is None else ("자동 처리 실패" if run["status"] == "FAILED" else None)
    drafts = _drafts(conn, sub, labels, len(failed))
    return {
        "sub_ticket": {k: sub[k] for k in (
            "sub_ticket_id", "seq", "category_code", "urgency_flag", "product_code", "priority", "priority_rule_id",
            "routing_rule_id", "assigned_dept", "return_kind", "sla_id", "required_info", "provided_info",
            "missing_info", "missing_blocking_info", "sla_first_response_target_h", "sla_resolution_target_h",
            "first_response_at_utc", "info_request_sent", "status", "pipeline_error", "evidence_json")},
        "checks": [{"check_type": r["check_type"], "flag": (r["detail"] or {}).get("flag")} for r in failed],
        "other_flags": [f for f in flags if check_type_of(f) is None and f not in DRAFT_FLAGS],
        "evidence_rows": _evidence_rows(conn, sub, out, flags, labels, status),
        "drafts": drafts,
    }


def _empty(status: str | None, reason: str) -> str:
    return f"없음({status or reason})"


def _evidence_rows(conn, sub, out, flags, labels, status) -> list[dict[str, Any]]:
    """근거 영역 줄 C-01~M-C-02 (화면 정의서 v2 SCR-03M ④ C, FR-024 처리 1·2, 예외 1행)."""
    t2, q3, q4, q5, q6 = (out.get(k, {}) for k in ("T2", "Q3", "Q4", "Q5", "Q6"))
    rows = []
    category_failed = any(f.startswith("분류 실패") for f in flags)
    rows.append({"id": "C-01", "label": "① 유형",
                 "result": sub["category_code"] or _empty(status, "분류 실패" if category_failed else "미정"),
                 "evidence": sub["evidence_sentences"], "why": {"confidence": t2.get("category_confidence")}})
    rows.append({"id": "C-02", "label": "② 긴급도", "result": sub["urgency_flag"] if t2 else _empty(status, "미실행"),
                 "evidence": [t2["urgency_evidence"]] if t2.get("urgency_evidence") else [], "why": {}})
    q2 = out.get("Q2", {})
    rows.append({"id": "M-C-01", "label": "③ 고객·제품",
                 "result": f"{q2.get('customer_id', '')} {q2.get('customer_tier') or ''} / {sub['product_code'] or '제품 미확정'}".strip(),
                 "evidence": [], "why": {"product_family": q2.get("product_family")}})
    trace = ", ".join(f"{c['rule_id']} {'✓' if c['matched'] else '✗'}" for c in q3.get("priority_trace", []))
    rows.append({"id": "C-03", "label": "④ 우선순위",
                 "result": f"{sub['priority']} ({sub['priority_rule_id']})" if sub["priority"] else _empty(status, "우선순위 미정"),
                 "evidence": [trace] if trace else [],
                 "why": {"rule": _row(conn, "SELECT * FROM ref.priority_rule WHERE rule_id = %s", (sub["priority_rule_id"],))}})
    dept_evidence = [sub["routing_rule_id"]] if sub["routing_rule_id"] else []
    if q4.get("escalation_condition"):
        dept_evidence.append(f"이관 조건: {q4['escalation_condition']}")
    if sub["return_kind"]:
        dept_evidence.append(f"반품 구분: {sub['return_kind']}")
    rows.append({"id": "C-04", "label": "⑤ 부서", "result": sub["assigned_dept"] or _empty(status, "배정 규칙 없음"),
                 "evidence": dept_evidence,
                 "why": {"rule": _row(conn, "SELECT * FROM ref.routing_rule WHERE rule_id = %s", (sub["routing_rule_id"],))}})
    provided = {r[0]: r[1] for r in conn.execute(
        "SELECT field, coalesce(value_norm, value_raw) FROM svc.inquiry_field WHERE sub_ticket_id = %s",
        (sub["sub_ticket_id"],)).fetchall()}
    items = [{"field": f, "label": labels.get(f, f),
              "state": "blocking" if f in sub["missing_blocking_info"] else "missing" if f in sub["missing_info"] else "provided",
              "value": provided.get(f)} for f in sub["required_info"]]
    rows.append({"id": "C-07", "label": "⑥ 필수정보",
                 "result": "막는 항목 있음" if sub["missing_blocking_info"] else ("빠진 항목 있음" if sub["missing_info"] else "모두 제공")
                 if sub["required_info"] else _empty(status, "제품·유형 미정"),
                 "evidence": [], "items": items, "why": {"labels": q5.get("labels", {})}})
    rows.append({"id": "C-06", "label": "⑦ SLA 목표",
                 "result": (f"1차 응답 {sub['sla_first_response_target_h']}h / 해결 {sub['sla_resolution_target_h']}h"
                            if sub["sla_id"] else _empty(status, "SLA 미정")),
                 "evidence": [sub["sla_id"]] if sub["sla_id"] else [],
                 "why": {"rule": _row(conn, "SELECT * FROM ref.sla_policy WHERE sla_id = %s", (sub["sla_id"],)),
                         "targets": q6}})
    if "Q7" in out:
        result, candidates, lookups = "없음(정보 요청 중)", [], []
    else:
        candidates = sub["evidence_json"]
        lookups = out.get("Q9", {}).get("lookups", [])
        result = f"후보 {len(candidates)}개" if candidates else _empty(status, "근거 없음")
    rows.append({"id": "M-C-02", "label": "⑧ 근거 절·조회값", "result": result, "evidence": [],
                 "candidates": candidates, "lookups": lookups, "why": {}})
    return rows


def _drafts(conn: Connection, sub: dict[str, Any], labels: dict[str, str], failed_count: int) -> list[dict[str, Any]]:
    drafts = _rows(conn, """SELECT message_id, message_type, message_status, language, body, sent_at_utc AS made_at_utc,
                                   superseded_at
                              FROM svc.ticket_message
                             WHERE sub_ticket_id = %s AND sender = 'SYSTEM' AND message_type IN ('INFO_REQUEST','FINAL_REPLY')
                             ORDER BY message_no""", (sub["sub_ticket_id"],))
    out = []
    for d in drafts:
        check = _latest_check(conn, d["message_id"], "DRAFT_CHECK")
        verify = _latest_check(conn, d["message_id"], "VERIFY")
        gloss = latest_gloss(conn, d["message_id"])
        sent = _row(conn, """SELECT message_id, sent_at_utc, sent_by_name, edited_yn, override_check, body
                               FROM svc.ticket_message WHERE source_draft_id = %s AND message_status = 'SENT'""",
                    (d["message_id"],))
        out.append({**d,
                    "gloss": None if gloss is None else {"language": gloss.language, "body": gloss.body,
                                                         "numbers_match": gloss.numbers_match, "made_at_utc": gloss.made_at},
                    "check": check, "verify": verify, "sent": sent,
                    "review_marks": review_marks(d, sub, labels, failed_count, check, verify)})
    return out


def _latest_check(conn: Connection, message_id: int, check_type: str) -> dict[str, Any] | None:
    return _row(conn, """SELECT passed_yn, detail, checked_at_utc FROM eval.self_check
                          WHERE message_id = %s AND check_type = %s ORDER BY checked_at_utc DESC, check_id DESC LIMIT 1""",
                (message_id, check_type))


def verify_state(verify: dict[str, Any] | None, body: str) -> tuple[str | None, str, list[dict]]:
    """⑤ 상태·문구·지적 (§5-7, 에이전트 설계서 6-3). 검증 행이 없으면 (None, "⑤ 검증 전", [])."""
    if verify is None:
        return None, "⑤ 검증 전", []
    detail = verify["detail"] or {}
    result = VerifyResult([VerifyFinding(**f) for f in detail.get("findings", [])],
                          detail.get("gloss_checked", True), detail.get("error"))
    if detail.get("body_sha256") and detail["body_sha256"] != body_sha(body):
        return "STALE", "⑤ 고친 뒤 검증 안 함", []
    return result.state, result.mark(), detail.get("findings", [])


def review_marks(draft: dict[str, Any], sub: dict[str, Any], labels: dict[str, str], failed_count: int,
                 check: dict[str, Any] | None, verify: dict[str, Any] | None) -> dict[str, Any]:
    reply = draft["message_type"] == "FINAL_REPLY"
    marks = []
    ok1 = bool(check and check["passed_yn"])
    marks.append({"no": 1, "passed": ok1, "text": None if ok1 else ("① 인용·숫자 확인 필요" if reply else "① 요청 항목 빠짐"),
                  "detail": (check or {}).get("detail")})
    blocking = sub["missing_blocking_info"] if reply else []
    marks.append({"no": 2, "passed": not blocking,
                  "text": None if not blocking else "② 막는 항목 남음: " + ", ".join(labels.get(f, f) for f in blocking)})
    marks.append({"no": 3, "passed": failed_count == 0, "text": None if failed_count == 0 else f"③ 확인 표시 {failed_count}개"})
    safety = sub["urgency_flag"] in SAFETY_URGENCY
    marks.append({"no": 4, "passed": not safety, "state": "CHECK" if safety else None,
                  "text": "④ 확인 필요: 안전 문의" if safety else None})
    state, text, findings = verify_state(verify, draft["body"])
    marks.append({"no": 5, "passed": state == "PASSED", "state": state, "text": None if state == "PASSED" else text,
                  "findings": findings, "full_text": text})
    all_ok = all(m["passed"] for m in marks)
    return {"marks": marks, "summary": "검사 5개 통과" if all_ok else " · ".join(m["text"] for m in marks if not m["passed"])}
