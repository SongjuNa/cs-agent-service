"""티켓 상세 묶음과 검토 표시 5개 (FR-024, 기술 명세서 v1.4 §5-7, §8-1 GET /tickets/{id}, 화면 정의서 v2 SCR-03M).

저장된 값만 읽는다(FR-024 처리 5). 검토 표시는 저장하지 않고 읽을 때 계산한다(§5-7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection

from app.db.replies import customer_followups, messages
from app.db.store import body_sha, check_type_of, latest_gloss
from app.llm.verify import VerifyResult
from app.db.runs import agent_edits, latest_pipeline_run, pipeline_run, run_for_sub
from app.pipeline.reprocess import last_pipeline_step
from app.pipeline.state import VerifyFinding
from app.rules.escalation import load_team_rules
from app.sla.adjust import adjustments
from app.sla.alerts import alert_history
from app.sla.clock import clocks
from app.status.dept_reply import EXCEPTION_DEPTS
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


def ticket_detail(conn: Connection, ticket_id: str, agent_dept: str | None = None,
                  as_of: datetime | None = None) -> dict[str, Any] | None:
    ticket = _row(conn, """
        SELECT t.ticket_id, t.received_at_utc, t.channel, t.language, t.body_language, t.body_language_uncertain,
               t.customer_id, t.customer_tier, c.company_masked, c.country, t.source, t.source_ticket_id, t.multi_yn,
               t.inquiry_subject, t.inquiry_body, t.contact_name, t.contact_email, t.contact_phone,
               EXISTS (SELECT 1 FROM eval.gold_set g
                       WHERE t.source_ticket_id IN (g.source_ticket_id, g.gold_set_id)) AS gold_set
          FROM svc.ticket t JOIN ref.customer c ON c.customer_id = t.customer_id
         WHERE t.ticket_id = %s""", (ticket_id,))
    if ticket is None:
        return None
    # 접수·고객 회신 재처리(FR-032)·다시 처리(FR-036 처리 5)
    run = _row(conn, f"""SELECT r.run_id, r.trigger, r.status, r.last_step, r.started_at_utc, r.finished_at_utc
                            FROM svc.agent_run r
                           WHERE r.ticket_id = %s AND {pipeline_run()}
                           ORDER BY r.run_id DESC LIMIT 1""", (ticket_id,))
    processing = run is None or run["status"] is None
    retry = latest_pipeline_run(conn, ticket_id)  # [다시 시도]를 보일지: 서버의 다시 시도 조건과 같다(AC-001-4)
    can_retry = retry is not None and retry["status"] == "FAILED" and not retry["busy"]
    rows = _rows(conn, "SELECT * FROM svc.sub_ticket WHERE ticket_id = %s ORDER BY seq", (ticket_id,))
    # [다시 처리]: 처리 중이 아니고 끝나지 않은(CLOSED가 아닌) 하위 문의가 있으면(FR-030 처리 5, SCR-03 ⑥ 종료)
    can_reprocess = (retry is not None and not retry["busy"] and not processing
                     and any(r["status"] != "CLOSED" for r in rows))
    sla = clocks(conn, [r["sub_ticket_id"] for r in rows], as_of)
    # 하위 문의마다 자기 run(복합 문의는 하위 문의별 run, AC-036-4)
    subs = [_sub_detail(conn, s, run_for_sub(conn, s["sub_ticket_id"])) | _state(conn, s, sla.get(s["sub_ticket_id"]))
            | _dept(conn, s, agent_dept) for s in rows]
    # FR-006 출력: 티켓의 유형 = 하위 문의 유형을 순번 순으로 ';'로 이은 값(표에 열이 없어 계산, 기술 명세서 §6-2)
    ticket["category_code"] = ";".join(r["category_code"] for r in rows if r["category_code"]) or None
    summary = _row(conn, """SELECT status, rep_sub_ticket_id, rep_res_status, rep_remaining_h, open_count, inquiry_count
                              FROM svc.v_ticket_summary WHERE ticket_id = %s""", (ticket_id,))
    return {"ticket": ticket, "summary": summary, "run": run, "processing": processing, "can_retry": can_retry,
            "can_reprocess": can_reprocess, "sub_tickets": subs,
            "messages": messages(conn, ticket_id)}  # FR-035 처리 7


def _state(conn: Connection, sub: dict[str, Any], sla: dict[str, Any] | None) -> dict[str, Any]:
    """상태·SLA·이력 (FR-025 출력, FR-026 출력, 기술 명세서 §6-4)."""
    hist = history(conn, sub["sub_ticket_id"])
    return {
        "state": {k: sub[k] for k in ("status", "version", "resolved_at_utc", "final_action", "priority",
                                      "priority_rule_id", "priority_adjusted_by_agent")},
        "adjustments": adjustments(conn, sub["sub_ticket_id"]),  # FR-028 출력
        "sla": sla,
        "history": hist,
        "wait_intervals": wait_intervals(hist),
        "alerts": alert_history(conn, sub["sub_ticket_id"]),  # FR-027 출력
        "customer_followups": customer_followups(conn, sub["sub_ticket_id"]),  # FR-032 처리 6 (C-70)
    }


def _steps(conn: Connection, run_id: int | None) -> dict[str, Any]:
    if run_id is None:
        return {}
    return {r["step_name"]: r for r in _rows(
        conn, """SELECT step_id, step_name, result, input_json, output_json, error_kind, error FROM svc.agent_step
                  WHERE run_id = %s ORDER BY step_order""", (run_id,))}


def _sub_detail(conn: Connection, sub: dict[str, Any], run: dict[str, Any] | None) -> dict[str, Any]:
    run_id = run["run_id"] if run else None
    steps = _steps(conn, run_id)
    out = {name: (st["output_json"] or {}) for name, st in steps.items()}
    if "T2" not in out and run_id is not None:  # 복합 문의의 T2는 티켓 run에 하위 문의별 몫으로 있다
        out["T2"] = last_pipeline_step(conn, sub["sub_ticket_id"], "T2") or {}
    flags: list[str] = next((o["flags"] for o in reversed(list(out.values())) if "flags" in o), [])
    failed = _rows(conn, """SELECT check_type, detail FROM eval.self_check
                             WHERE run_id = %s AND sub_ticket_id = %s AND NOT passed_yn AND check_type <> ALL(%s)
                             ORDER BY check_id""", (run_id, sub["sub_ticket_id"], list(NOT_IN_MARK_3)))
    labels = dict(conn.execute("SELECT field, label FROM ref.info_field").fetchall())
    status = "처리 중" if run is None or run["status"] is None else ("자동 처리 실패" if run["status"] == "FAILED" else None)
    drafts = _drafts(conn, sub, labels, len(failed))
    edits = agent_edits(conn, sub["sub_ticket_id"])
    return {
        "sub_ticket": {k: sub[k] for k in (
            "sub_ticket_id", "seq", "category_code", "assignee_masked", "urgency_flag", "product_code", "priority", "priority_rule_id",
            "routing_rule_id", "assigned_dept", "return_kind", "sla_id", "required_info", "provided_info",
            "missing_info", "missing_blocking_info", "sla_first_response_target_h", "sla_resolution_target_h",
            "first_response_at_utc", "info_request_sent", "status", "pipeline_error", "evidence_json",
            "escalated", "escalated_to", "escalation_reason")},
        "escalated_at_utc": _escalated_at(conn, sub["sub_ticket_id"]) if sub["escalated_to"] else None,  # FR-033
        "checks": [{"check_type": r["check_type"], "flag": (r["detail"] or {}).get("flag")} for r in failed],
        "other_flags": [f for f in flags if check_type_of(f) is None and f not in DRAFT_FLAGS],
        "diagnosis": out.get("Q8a"),  # 고장 진단 후보(FR-018). 고장 계열이 아니면 None
        "similar_cases": out.get("Q8b"),  # 유사 해결사례(FR-019). 찾는 유형이 아니면 None. 초안에는 쓰지 않음
        "escalation": out.get("Q9a"),  # 이관 후보(FR-020). 버튼 없이 표시만
        "evidence_rows": _with_steps(_evidence_rows(conn, sub, out, flags, labels, status, edits), run_id, steps),
        "drafts": drafts,
        "fields": _fields(conn, sub["sub_ticket_id"], labels),
        "edits": edits,  # "상담원 수정" 표시(FR-030 처리 6)
        "product_name": (conn.execute("SELECT product_name FROM ref.product WHERE product_code = %s",
                                      (sub["product_code"],)).fetchone() or [None])[0],
        "version": sub["version"],
    }


def _fields(conn: Connection, sub_ticket_id: str, labels: dict[str, str]) -> list[dict[str, Any]]:
    """추출 값(FR-030 처리 1 "원문에서 뽑은 값 강조", 화면 정의서 v1 SCR-03 L-01). span이 없으면 화면이 원문에서 값을 찾는다(C-109)."""
    return [{**r, "label": labels.get(r["field"], r["field"])} for r in _rows(
        conn, """SELECT field, value_raw, value_norm, span_start, span_end, source FROM svc.inquiry_field
                  WHERE sub_ticket_id = %s ORDER BY field_id""", (sub_ticket_id,))]


# 근거 줄 → 그 줄을 만든 단계 (FR-036 처리 7 "왜?에서 해당 단계로", 기술 명세서 §2-2 단계 표)
ROW_STEPS = {"C-01": ("T2",), "C-02": ("T2",), "M-C-01": ("Q2",), "C-03": ("Q3",), "C-04": ("Q4",), "C-07": ("Q5",),
             "C-06": ("Q6",), "M-C-02": ("Q7", "Q9", "Q8"), "C-08": ("Q8a",),
             "C-09": ("Q9a",)}  # ⑧은 화면 정의서 v2 SCR-03M "agent_step(Q9)"


def _with_steps(rows: list[dict[str, Any]], run_id: int | None, steps: dict[str, Any]) -> list[dict[str, Any]]:
    """why에 단계(run_id, step_id, step_name)를 붙인다. 화면은 GET /runs/{run_id}/steps에서 그 단계를 연다."""
    for row in rows:
        name = next((n for n in ROW_STEPS.get(row["id"], ()) if n in steps), None)
        row["why"]["step"] = ({"run_id": run_id, "step_id": steps[name]["step_id"], "step_name": name}
                              if name else None)
    return rows


def _empty(status: str | None, reason: str) -> str:
    return f"없음({status or reason})"


def _edited(edits: dict[str, dict[str, Any]], name: str) -> tuple[list[str], dict[str, Any]]:
    """상담원이 고친 항목이면 근거 한 줄과 "왜?" 값(FR-030 처리 6: 고친 값이 근거가 된다, C-117)."""
    e = edits.get(name)
    if not e:
        return [], {}
    return [f"상담원 수정: {e['from'] or '없음'} → {e['to']}"], {"상담원 수정": f"{e.get('by')} {e.get('at')}"}


def _evidence_rows(conn, sub, out, flags, labels, status, edits=None) -> list[dict[str, Any]]:
    """근거 영역 줄 C-01~M-C-02 (화면 정의서 v2 SCR-03M ④ C, FR-024 처리 1·2, 예외 1행)."""
    edits = edits or {}
    cat_note, cat_why = _edited(edits, "category_code")
    urg_note, urg_why = _edited(edits, "urgency_flag")
    t2, q3, q4, q5, q6 = (out.get(k, {}) for k in ("T2", "Q3", "Q4", "Q5", "Q6"))
    rows = []
    category_failed = any(f.startswith("분류 실패") for f in flags)
    rows.append({"id": "C-01", "label": "① 유형",
                 "result": sub["category_code"] or _empty(status, "분류 실패" if category_failed else "미정"),
                 "evidence": cat_note + list(sub["evidence_sentences"] or []),
                 "why": {"confidence": t2.get("category_confidence"), **cat_why}})
    rows.append({"id": "C-02", "label": "② 긴급도", "result": sub["urgency_flag"] if t2 or urg_note else _empty(status, "미실행"),
                 "evidence": urg_note + ([t2["urgency_evidence"]] if t2.get("urgency_evidence") else []), "why": urg_why})
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
    if sub["status"] == "ESCALATED" and sub["escalated_to"]:  # 화면 정의서 v1 C-04 "→ {이관 부서} ({사유}, {시각})"
        at = _escalated_at(conn, sub["sub_ticket_id"])
        dept_evidence.append(f"→ {sub['escalated_to']} ({sub['escalation_reason']}, {at:%Y-%m-%d %H:%M} UTC)" if at
                             else f"→ {sub['escalated_to']} ({sub['escalation_reason']})")
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
    q8a = out.get("Q8a")
    if q8a is not None:  # 고장 계열만(FR-018 처리 1, FR-024 입력, AC-024-1)
        top = (q8a.get("fault_candidates") or [None])[0]
        notes = q8a.get("notes") or []
        method = {"EXACT": "정확 일치", "SYMPTOM": "증상 검색"}.get(q8a.get("method"), "")
        rows.append({"id": "C-08", "label": "⑨ 고장 진단",
                     "result": f"{top['fault_id']} ({method})" if top else f"없음({', '.join(notes) or '진단 없음'})",
                     "evidence": ([top["cause"]] if top and top.get("cause") else []) + notes,
                     "why": {"rule": _row(conn, "SELECT * FROM ref.fault WHERE fault_id = %s", (top["fault_id"],)) if top else None,
                             "method": q8a.get("method"), "score": top.get("score") if top else None}})
    q9a = out.get("Q9a")
    if q9a is not None:  # 이관 후보(FR-020 처리 3·4, AC-024-1). 부서별 한 줄(예외 3행)
        found = q9a.get("escalation_candidates") or []
        by_dept: dict[str, list[str]] = {}
        for c in found:
            by_dept.setdefault(c["dept"], []).append(f"{c['rule_id']} ({c['reason']})" + (" (팀 규칙)" if c.get("team") else ""))
        lines = [f"{dept} — {', '.join(rules)}" for dept, rules in by_dept.items()]
        condition = q9a.get("escalation_condition")
        rows.append({"id": "C-09", "label": "⑩ 이관 후보",
                     "result": " / ".join(lines) if found else "없음" + (f" — 이관 조건: {condition}" if condition else ""),
                     "evidence": q9a.get("notes") or [],
                     "why": {"rules": [_escalation_rule(conn, c) for c in found]}})
    return rows


def _dept(conn: Connection, sub: dict[str, Any], agent_dept: str | None) -> dict[str, Any]:
    """부서 회신 영역(FR-030 처리 2)과 예외 부서 메일, 고른 부서의 작성 영역(§8-2, C-164).

    writer: 이관받은 부서가 고른 부서와 같으면 예외 부서는 DEPT_MAIL, 그 밖의 부서는 DEPT_REPLY, 나머지는 CS.
    """
    to = sub["escalated_to"]
    writer = "CS" if not to or to != agent_dept else ("DEPT_MAIL" if to in EXCEPTION_DEPTS else "DEPT_REPLY")
    replies = _rows(conn, """SELECT message_id, body, sent_by_name, sent_at_utc FROM svc.ticket_message
                              WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE' AND message_status = 'RECEIVED'
                              ORDER BY sent_at_utc, message_no""", (sub["sub_ticket_id"],))
    mails = _rows(conn, """SELECT message_id, message_status, body, sent_by_name, sent_at_utc, superseded_at FROM svc.ticket_message
                            WHERE sub_ticket_id = %s AND sender = 'DEPT' AND message_type = 'FINAL_REPLY'
                              AND message_status IN ('DRAFT','SENT') ORDER BY message_no""", (sub["sub_ticket_id"],))
    for m in mails:  # 임시 저장 때 만든 대역(C-165)
        gloss = latest_gloss(conn, m["message_id"]) if m["message_status"] == "DRAFT" else None
        m["gloss"] = gloss.body if gloss else None
    return {"writer": writer, "dept_replies": replies, "dept_mails": mails}


def _escalated_at(conn: Connection, sub_ticket_id: str):
    """이관 시각 = 마지막 ESCALATE 이력(§5-6 저장, FR-033)."""
    row = conn.execute("""SELECT max(changed_at_utc) FROM svc.ticket_status_history
                           WHERE sub_ticket_id = %s AND event_kind = 'ESCALATE'""", (sub_ticket_id,)).fetchone()
    return row[0] if row else None


def _escalation_rule(conn: Connection, c: dict[str, Any]) -> dict[str, Any] | None:
    """맞은 규칙 행: 운영진 행은 ref.routing_rule, 팀 규칙은 설정 파일 행(design 결정 3)."""
    if not c.get("team"):
        return _row(conn, "SELECT * FROM ref.routing_rule WHERE rule_id = %s", (c["rule_id"],))
    try:
        return next((dict(r) for r in load_team_rules() if r["rule_id"] == c["rule_id"]), None)
    except Exception:  # noqa: BLE001 — 설정 파일을 못 읽으면 행만 비운다
        return None


def _drafts(conn: Connection, sub: dict[str, Any], labels: dict[str, str], failed_count: int) -> list[dict[str, Any]]:
    drafts = _rows(conn, """SELECT message_id, message_no, message_type, message_status, language, body, sent_at_utc AS made_at_utc,
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
        re_request = d["message_type"] == "INFO_REQUEST" and _re_request(conn, sub["sub_ticket_id"], d)
        out.append({**d, "re_request": re_request,
                    "gloss": None if gloss is None else {"language": gloss.language, "body": gloss.body,
                                                         "numbers_match": gloss.numbers_match, "made_at_utc": gloss.made_at},
                    "check": check, "verify": verify, "sent": sent,
                    "review_marks": review_marks(d, sub, labels, failed_count, check, verify)})
    return out


def _requested(conn: Connection, message_id: int | None) -> set[str] | None:
    """정보 요청 초안을 만든 실행의 Q7 요청 항목(실행 기록에서 읽는다. 저장 열이 없다)."""
    row = conn.execute(
        """SELECT q7.output_json -> 'requested' FROM svc.agent_step q13
             JOIN svc.agent_step q7 ON q7.run_id = q13.run_id AND q7.step_name = 'Q7'
            WHERE q13.step_name = 'Q13' AND (q13.output_json ->> 'message_id')::bigint = %s
            ORDER BY q7.step_order DESC LIMIT 1""", (message_id,)).fetchone()
    return set(row[0]) if row and row[0] is not None else None


def _re_request(conn: Connection, sub_ticket_id: str, draft: dict[str, Any]) -> bool:
    """FR-032 처리 4 "이전 요청과 같은 항목이면 재요청": 이 초안의 요청 항목이 모두 앞서 발송한 정보 요청에 있었으면 참(C-73)."""
    prev = conn.execute(
        """SELECT source_draft_id FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_type = 'INFO_REQUEST'
              AND message_status = 'SENT' AND message_no < %s ORDER BY message_no DESC LIMIT 1""",
        (sub_ticket_id, draft["message_no"])).fetchone()
    if prev is None:
        return False
    before, now = _requested(conn, prev[0]), _requested(conn, draft["message_id"])
    return bool(before and now and now <= before)


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
