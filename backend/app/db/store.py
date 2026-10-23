"""접수와 처리 결과 저장 (기술 명세서 v1.4 §2-4, §6-2, §7, 테이블 정의서 v1.3).

- 원문은 그대로 저장하고 메시지에 가린 곳 수(mask_count)만 남긴다. 실행 기록(agent_step)에는 가린 글만 넣는다.
- 고객에게 가는 글은 DRAFT로만 저장한다(CLAUDE.md 규칙 3). SENT는 승인 API(send_draft)만 쓴다.
- 고객 회신 재처리(reply_id)는 새 제공 항목만 넣고, 이전 초안을 밀어내고, 조정값을 지킨다(FR-032, FR-011 예외 3행).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.checks.draft_check import check_draft
from app.config import get_settings
from app.llm.drafts import CHECK_PROVIDED_FIELDS, Draft, Gloss, Source
from app.masking import mask_fields, mask_text
from app.pipeline.graph import RunOutcome
from app.pipeline.reprocess import last_pipeline_step
from app.status.transitions import ConcurrentChange, TransitionRefused, current, transition

MAX_BODY = 2000  # svc.ticket.inquiry_body CHECK

# 확인 표시 → eval.self_check.check_type (테이블 정의서 v1.3 주석의 9값). 앞부분이 같으면 그 종류다.
# 맞는 값이 없는 표시는 self_check에 넣지 않고 실행 기록(agent_step)의 flags에만 남긴다.
FLAG_CHECK_TYPES: list[tuple[str, str]] = [
    ("확신 낮음", "LOW_CONFIDENCE"),
    ("분류 실패", "LOW_CONFIDENCE"),
    ("긴급도 판정 실패", "LOW_CONFIDENCE"),
    ("언어 판정 불확실", "LANG_UNCERTAIN"),
    ("추출 실패", "EXTRACT_FAILED"),
    ("형식 확인", "EXTRACT_FAILED"),
    ("값 충돌", "EXTRACT_FAILED"),
    ("제품 미확정", "PRODUCT_UNKNOWN"),
    ("제품 확인 필요", "PRODUCT_UNKNOWN"),
    ("펌웨어 없는 제품", "PRODUCT_UNKNOWN"),
    ("우선순위 미정", "RULE_FAILED"),
    ("배정 규칙 없음", "RULE_FAILED"),
    ("SLA 미정", "RULE_FAILED"),
    ("SLA 정책 없음", "RULE_FAILED"),
    ("분류 뒤 계산됨", "RULE_FAILED"),
    ("제품 확인 뒤 배정됨", "RULE_FAILED"),
    ("제품·유형 확인 뒤 계산됨", "RULE_FAILED"),
    ("반품 사유 확인 필요", "RETURN_REASON"),
    ("근거 없음", "NO_EVIDENCE"),
    ("제품 문서 미검색", "NO_EVIDENCE"),
    ("검색 실패", "NO_EVIDENCE"),
]
ERROR_KINDS = {"LLM_TIMEOUT", "LLM_INVALID_OUTPUT", "RULE_NOT_FOUND", "DB", "VALIDATION", "UNKNOWN"}


class IntakeError(ValueError):
    """접수 입력 거부 (API는 400)."""


def check_type_of(flag: str) -> str | None:
    return next((kind for prefix, kind in FLAG_CHECK_TYPES if flag.startswith(prefix)), None)


def body_sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _json(value: Any) -> Jsonb:
    return Jsonb(value, dumps=lambda v: json.dumps(v, ensure_ascii=False, default=str))


def _masked_json(value: Any) -> Jsonb:
    """실행 기록용: 모든 글을 가린 뒤 JSON으로 (§7 위치 (2))."""
    return _json(mask_fields(json.loads(json.dumps(value, ensure_ascii=False, default=str)))[0])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- 접수 ---


def create_ticket(conn: Connection, data: dict[str, Any]) -> str:
    """접수 입력을 검사하고 티켓·하위 문의·INQUIRY·접수 이력을 한 트랜잭션으로 넣는다. 새 ticket_id를 돌려준다."""
    body = data.get("inquiry_body") or ""
    if not body.strip():
        raise IntakeError("내용을 입력하세요")
    if len(body) > MAX_BODY:
        raise IntakeError(f"본문은 {MAX_BODY}자 이하여야 합니다")
    customer = conn.execute("SELECT tier FROM ref.customer WHERE customer_id = %s", (data.get("customer_id"),)).fetchone()
    if customer is None:  # 명세서 FR-010 D25: 미등록 고객 거부
        raise IntakeError("등록되지 않은 고객")
    product_code = data.get("product_code") or None
    if product_code and conn.execute("SELECT 1 FROM ref.product WHERE product_code = %s", (product_code,)).fetchone() is None:
        raise IntakeError("등록되지 않은 제품")
    source = data.get("source") or "SIMULATOR"
    received = data.get("received_at_utc") or _now()

    with conn.transaction():
        (no,) = conn.execute("SELECT nextval('svc.ticket_new_no')").fetchone()
        ticket_id = f"CSV1-{no:06d}"
        sub_ticket_id = f"{ticket_id}-1"
        conn.execute(
            """INSERT INTO svc.ticket (ticket_id, received_at_utc, channel, language, customer_id, customer_tier,
                   inquiry_subject, inquiry_body, source, source_ticket_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (ticket_id, received, data.get("channel"), data.get("language"), data["customer_id"], customer[0],
             data.get("inquiry_subject"), body, source, data.get("source_ticket_id")),
        )
        conn.execute("INSERT INTO svc.sub_ticket (sub_ticket_id, ticket_id, seq, product_code) VALUES (%s, %s, 1, %s)",
                     (sub_ticket_id, ticket_id, product_code))
        _, mask_count = mask_text(body)
        conn.execute(
            """INSERT INTO svc.ticket_message (ticket_id, sender, message_type, message_status, sent_at_utc, language,
                   body, sent_by_name, mask_count)
               VALUES (%s, 'CUSTOMER', 'INQUIRY', 'RECEIVED', %s, %s, %s, 'CUSTOMER', %s)""",
            (ticket_id, received, data.get("language"), body, mask_count),
        )
        conn.execute("SELECT svc.transition(%s, 'NEW', 'INTAKE', %s, 'SYSTEM')", (sub_ticket_id, received))
    return ticket_id


def ticket_input(conn: Connection, ticket_id: str) -> dict[str, Any]:
    """저장된 접수에서 처리 흐름 입력(접수 입력 열)을 읽는다. 제목은 넣지 않는다(§2-3)."""
    row = conn.execute(
        """SELECT t.ticket_id, t.channel, t.customer_id, s.product_code, t.language, t.inquiry_body, t.received_at_utc
             FROM svc.ticket t JOIN svc.sub_ticket s ON s.ticket_id = t.ticket_id AND s.seq = 1
            WHERE t.ticket_id = %s""",
        (ticket_id,),
    ).fetchone()
    keys = ("ticket_id", "channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")
    return dict(zip(keys, row))


# --- 실행 기록 ---


def start_run(conn: Connection, ticket_id: str, sub_ticket_id: str | None, trigger: str) -> int:
    with conn.transaction():
        (run_id,) = conn.execute(
            """INSERT INTO svc.agent_run (ticket_id, sub_ticket_id, trigger, started_at_utc, llm_model)
               VALUES (%s, %s, %s, %s, %s) RETURNING run_id""",
            (ticket_id, sub_ticket_id, trigger, _now(), get_settings().llm_model_small),
        ).fetchone()
    return run_id


def finish_run(conn: Connection, run_id: int, status: str, last_step: str | None) -> None:
    conn.execute("UPDATE svc.agent_run SET finished_at_utc = %s, status = %s, last_step = %s WHERE run_id = %s",
                 (_now(), status, last_step, run_id))


def add_step(conn: Connection, run_id: int, name: str, output: Any = None, input_: Any = None,
             result: str = "SUCCESS", error_kind: str | None = None, error: str | None = None) -> None:
    now = _now()
    conn.execute(
        """INSERT INTO svc.agent_step (run_id, step_name, step_order, started_at_utc, finished_at_utc, result,
               input_json, output_json, error_kind, error)
           VALUES (%s, %s, (SELECT coalesce(max(step_order), 0) + 1 FROM svc.agent_step WHERE run_id = %s),
                   %s, %s, %s, %s, %s, %s, %s)""",
        (run_id, name, run_id, now, now, result, None if input_ is None else _masked_json(input_),
         None if output is None else _masked_json(output), error_kind, None if error is None else mask_text(error)[0]),
    )


def add_self_check(conn: Connection, run_id: int, sub_ticket_id: str, check_type: str, passed: bool,
                   detail: dict | None, message_id: int | None = None) -> None:
    conn.execute(
        """INSERT INTO eval.self_check (run_id, sub_ticket_id, message_id, check_type, passed_yn, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (run_id, sub_ticket_id, message_id, check_type, passed, None if detail is None else _json(detail)),
    )


# --- 처리 결과 ---


def save_outcome(conn: Connection, run_id: int, ticket_id: str, outcome: RunOutcome, reply_id: int | None = None) -> None:
    """처리 결과 저장. reply_id가 있으면 고객 회신 재처리 결과다(FR-032 처리 3·4, 변경 add-customer-reply)."""
    """처리 결과를 저장하고 실행을 끝낸다(design 결정 2)."""
    with conn.transaction():
        if outcome.run_status != "SUCCESS" or outcome.state is None:
            _save_failure(conn, run_id, ticket_id, outcome)
            return
        state = outcome.state
        conn.execute("UPDATE svc.ticket SET body_language = %s, body_language_uncertain = %s WHERE ticket_id = %s",
                     (state.body_language, state.body_language_uncertain, ticket_id))
        (inquiry_id,) = conn.execute(
            "SELECT message_id FROM svc.ticket_message WHERE ticket_id = %s AND message_type = 'INQUIRY' ORDER BY message_no LIMIT 1",
            (ticket_id,),
        ).fetchone()
        last = "Q6"
        for sub in state.sub_tickets:
            last = _save_sub(conn, run_id, state, sub, outcome, inquiry_id, reply_id)
        finish_run(conn, run_id, _pipeline_done(conn, run_id, state.sub_tickets), last)


def _pipeline_done(conn: Connection, run_id: int, subs) -> str:
    """T6: 처리 흐름이 끝나면 NEW → IN_PROGRESS (기술 명세서 §2-2 T6, FR-001 처리 4).

    NEW가 아닌 문의(다시 처리 등)는 그대로 둔다. 전이가 실패하면 NEW로 두고 run PARTIAL(§2-2 T6 실패 칸).
    """
    now = _now()
    moved, failed = [], []
    for sub in subs:
        status, _ = current(conn, sub.sub_ticket_id)
        if status != "NEW":
            continue
        try:
            transition(conn, sub.sub_ticket_id, "IN_PROGRESS", "PIPELINE_DONE", now, "SYSTEM")
            moved.append(sub.sub_ticket_id)
        except (TransitionRefused, ConcurrentChange) as exc:
            failed.append(f"{sub.sub_ticket_id}: {exc}")
    if failed:
        add_step(conn, run_id, "T6", output={"moved": moved}, result="FAILED", error_kind="VALIDATION",
                 error="; ".join(failed))
        return "PARTIAL"
    if moved:
        add_step(conn, run_id, "T6", output={"moved": moved, "to_status": "IN_PROGRESS"})
    return "SUCCESS"


def _save_failure(conn: Connection, run_id: int, ticket_id: str, outcome: RunOutcome) -> None:
    kind = outcome.error_type if outcome.error_type in ERROR_KINDS else "UNKNOWN"
    step = "T2" if outcome.state is None else "Q2"
    add_step(conn, run_id, step, result="FAILED", error_kind=kind, error=outcome.message)
    conn.execute("UPDATE svc.sub_ticket SET pipeline_error = %s WHERE ticket_id = %s",
                 (f"{kind}: {outcome.message or ''}".strip(), ticket_id))
    finish_run(conn, run_id, "FAILED", step)


MSG_NO_NEW_FIELDS = "제공 항목 변화 없음"  # FR-032 예외 5행


def _save_sub(conn, run_id, state, sub, outcome: RunOutcome, inquiry_id: int, reply_id: int | None = None) -> str:
    req = outcome.required.get(sub.sub_ticket_id)
    known = {r[0] for r in conn.execute("SELECT field FROM svc.inquiry_field WHERE sub_ticket_id = %s",
                                        (sub.sub_ticket_id,)).fetchall()}
    provided = [pf.field for pf in sub.provided_fields]
    evidence = [{"doc_id": c.doc_id, "section": c.section_no, "quote": _chunk_quote(conn, c.chunk_id, c.title),
                 "score": c.score, "chunk_id": c.chunk_id} for c in sub.doc_candidates]
    top = sub.doc_candidates[0] if sub.doc_candidates else None
    blocking = bool(sub.missing_blocking_info)
    conn.execute(
        """UPDATE svc.sub_ticket SET category_code = %s, evidence_sentences = %s, urgency_flag = %s, product_code = %s,
               error_code_reported = %s, fw_version_reported = %s,
               priority = CASE WHEN priority_adjusted_by_agent THEN priority ELSE %s END, priority_rule_id = %s,
               routing_rule_id = %s, assigned_dept = %s, return_kind = %s,
               sla_id = CASE WHEN priority_adjusted_by_agent THEN sla_id ELSE %s END,
               required_info = %s, provided_info = %s, missing_info = %s, missing_blocking_info = %s,
               sla_first_response_target_h = CASE WHEN priority_adjusted_by_agent THEN sla_first_response_target_h ELSE %s END,
               sla_resolution_target_h = CASE WHEN priority_adjusted_by_agent THEN sla_resolution_target_h ELSE %s END,
               evidence_json = %s,
               reference_doc_id = %s, reference_section = %s, no_evidence_flag = %s, pipeline_error = NULL
           WHERE sub_ticket_id = %s""",
        (sub.category_code, sub.evidence_sentences, sub.urgency_flag, sub.product_code, sub.error_code, sub.current_fw,
         sub.priority_final, sub.priority_rule_id, sub.routing_rule_id, sub.assigned_dept, sub.return_kind, sub.sla_id,
         req.required_info if req else [], provided, sub.missing_info, sub.missing_blocking_info,
         sub.fr_target_h, sub.res_target_h, _json(evidence), top.doc_id if top else None,
         top.section_no if top else None, not blocking and not sub.doc_candidates, sub.sub_ticket_id),
    )
    # 조정한 문의는 규칙값(priority_rule_id)만 새로 쓰고 조정값을 덮어쓰지 않는다(FR-011 예외 3행, C-69)
    added = [pf for pf in sub.provided_fields if pf.field not in known]  # 회신 재처리는 새 항목만(합집합)
    for pf in added:
        conn.execute(
            """INSERT INTO svc.inquiry_field (sub_ticket_id, field, value_raw, value_norm, source, source_message_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (sub.sub_ticket_id, pf.field, pf.value_raw, pf.value_norm,
             "INQUIRY" if reply_id is None else "CUSTOMER_REPLY", inquiry_id if reply_id is None else reply_id),
        )
    for flag in sub.flags:
        kind = check_type_of(flag)
        if kind:
            add_self_check(conn, run_id, sub.sub_ticket_id, kind, False, {"flag": flag})

    # 실행 기록: 단계마다 결과 한 행("왜?"가 읽는다). 확인 표시 전체는 마지막 단계 결과의 flags에 둔다
    names = outcome.llm_field_names
    steps: list[dict[str, Any]] = [
        {"name": "T2", "input_": {"field_names": names.get("L1", [])}, "output": {
            "language": state.language, "body_language": state.body_language,
            "body_language_uncertain": state.body_language_uncertain, "category_code": sub.category_code,
            "category_confidence": sub.category_confidence, "urgency_flag": sub.urgency_flag,
            "urgency_evidence": sub.urgency_evidence, "evidence_sentences": sub.evidence_sentences}},
        {"name": "Q1", "input_": {"field_names": names.get("L2", [])}, "output": {
            "provided_fields": [pf.model_dump() for pf in sub.provided_fields], "product_code": sub.product_code,
            "error_code": sub.error_code, "current_fw": sub.current_fw, "return_reason": sub.return_reason,
            **({} if reply_id is None else {"reply_message_id": reply_id, "added_fields": [pf.field for pf in added],
                                            **({} if added else {"note": MSG_NO_NEW_FIELDS})})}},
        {"name": "Q2", "output": {"customer_id": state.customer_id, "customer_tier": sub.customer_tier,
                                  "product_code": sub.product_code, "product_family": sub.product_family}},
        {"name": "Q3", "output": {"priority": sub.priority_final, "priority_rule_id": sub.priority_rule_id,
                                  "priority_trace": [c.model_dump() for c in sub.priority_trace]}},
        {"name": "Q4", "output": {"assigned_dept": sub.assigned_dept, "routing_rule_id": sub.routing_rule_id,
                                  "escalation_condition": sub.escalation_condition,
                                  "return_kind": sub.return_kind, "return_reason": sub.return_reason}},
        {"name": "Q5", "output": {"required_info": req.required_info if req else [], "provided_info": provided,
                                  "missing_info": sub.missing_info, "missing_blocking_info": sub.missing_blocking_info,
                                  "labels": req.labels if req else {}}},
        {"name": "Q6", "output": {"sla_id": sub.sla_id, "fr_target_h": sub.fr_target_h, "res_target_h": sub.res_target_h}},
    ]
    if blocking:
        steps.append({"name": "Q7", "output": {"requested": sub.missing_info}})
    else:
        steps.append({"name": "Q8", "output": {"doc_candidates": [c.model_dump() for c in sub.doc_candidates]}})
        steps.append({"name": "Q9", "output": {"lookups": [lv.model_dump() for lv in sub.lookups]}})

    if reply_id is not None:  # 재처리로 밀린 초안 (§2-4 "재처리")
        conn.execute(
            """UPDATE svc.ticket_message SET superseded_at = %s
                WHERE sub_ticket_id = %s AND sender = 'SYSTEM' AND message_status = 'DRAFT' AND superseded_at IS NULL
                  AND message_type IN ('INFO_REQUEST','FINAL_REPLY')""", (_now(), sub.sub_ticket_id))
    for draft in (d for d in outcome.drafts if d.sub_ticket_id == sub.sub_ticket_id):
        message_id = insert_draft(conn, state.ticket_id, draft)
        if draft.message_type == "FINAL_REPLY":
            steps.append({"name": "Q10", "output": {"message_id": message_id, "lookups_used": draft.lookups_used}})
            add_self_check(conn, run_id, sub.sub_ticket_id, "DRAFT_CHECK", bool(draft.check and draft.check["passed"]),
                           {**(draft.check or {}), "body_sha256": body_sha(draft.body)}, message_id)
            steps.append({"name": "Q11", "output": draft.check})
        else:  # 정보 요청의 자체 대조 = 막는 항목 라벨 누락 검사(에이전트 설계서 6-1 3번)
            check = info_request_check(draft.body, sub.missing_blocking_info, req.labels if req else {})
            add_self_check(conn, run_id, sub.sub_ticket_id, "DRAFT_CHECK", check["passed"],
                           {**check, "body_sha256": body_sha(draft.body)}, message_id)
            steps.append({"name": "Q11", "output": check})
        if draft.gloss:
            insert_gloss(conn, message_id, draft.gloss)
        steps.append({"name": "Q13", "output": {"message_id": message_id, "gloss": draft.gloss is not None}})
        if draft.verify is not None:
            save_verify(conn, run_id, sub.sub_ticket_id, message_id, draft.body, draft.verify)
            error = draft.verify.error
            steps.append({"name": "Q14", "output": {"message_id": message_id, "state": draft.verify.state},
                          "result": "FAILED" if error else "SUCCESS",
                          "error_kind": error if error in ERROR_KINDS else ("UNKNOWN" if error else None)})

    steps[-1]["output"] = {**(steps[-1]["output"] or {}), "flags": sub.flags}
    last = steps[-1]["name"]
    for step in steps:
        add_step(conn, run_id, step.pop("name"), **step)
    return last


def _chunk_quote(conn: Connection, chunk_id: str | None, title: str) -> str:
    """evidence_json의 quote(인용문): 절 본문 첫 문장(200자까지). 본문을 못 읽으면 절 제목."""
    row = conn.execute("SELECT text FROM ref.doc_chunk WHERE chunk_id = %s", (chunk_id,)).fetchone()
    lines = [ln.strip() for ln in (row[0] if row else "").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return title
    first = lines[0].split(". ")[0]
    return first[:200]


def insert_draft(conn: Connection, ticket_id: str, draft: Draft) -> int:
    _, mask_count = mask_text(draft.body)
    (message_id,) = conn.execute(
        """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
               language, body, sent_by_name, mask_count)
           VALUES (%s, %s, 'SYSTEM', %s, 'DRAFT', %s, %s, %s, 'SYSTEM', %s) RETURNING message_id""",
        (ticket_id, draft.sub_ticket_id, draft.message_type, _now(), draft.language, draft.body, mask_count),
    ).fetchone()
    return message_id


def insert_gloss(conn: Connection, message_id: int, gloss: Gloss) -> None:
    conn.execute(
        "INSERT INTO svc.message_gloss (message_id, language, body, numbers_match, made_at_utc) VALUES (%s, %s, %s, %s, %s)",
        (message_id, gloss.language, gloss.body, gloss.numbers_match, gloss.made_at),
    )


def save_verify(conn: Connection, run_id: int, sub_ticket_id: str, message_id: int, body: str, result) -> None:
    add_self_check(conn, run_id, sub_ticket_id, "VERIFY", result.passed_yn,
                   {**result.detail(), "body_sha256": body_sha(body)}, message_id)


# --- 초안 다루기 (FR-031, FR-039, FR-049) ---


def load_draft(conn: Connection, message_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT m.message_id, m.ticket_id, m.sub_ticket_id, m.message_type, m.message_status, m.language, m.body,
                  m.superseded_at
             FROM svc.ticket_message m
            WHERE m.message_id = %s AND m.sender = 'SYSTEM' AND m.message_type IN ('INFO_REQUEST','FINAL_REPLY')""",
        (message_id,),
    ).fetchone()
    if row is None:
        return None
    keys = ("message_id", "ticket_id", "sub_ticket_id", "message_type", "message_status", "language", "body", "superseded_at")
    return dict(zip(keys, row))


def latest_gloss(conn: Connection, message_id: int) -> Gloss | None:
    row = conn.execute(
        """SELECT language, body, numbers_match, made_at_utc FROM svc.message_gloss
            WHERE message_id = %s AND language = 'ko' ORDER BY made_at_utc DESC, gloss_id DESC LIMIT 1""",
        (message_id,),
    ).fetchone()
    return Gloss(row[0], row[1], row[2], row[3]) if row else None


def intake_step(conn: Connection, sub_ticket_id: str, step_name: str) -> dict | None:
    """그 하위 문의의 마지막 처리 흐름 실행(접수 또는 고객 회신 재처리)에서 한 단계의 결과를 읽는다."""
    return last_pipeline_step(conn, sub_ticket_id, step_name)


def draft_sources(conn: Connection, sub_ticket_id: str) -> tuple[list[Source], list[tuple], list[tuple[str, str]], list[str]]:
    """초안 검사·검증에 쓰는 저장값: 근거 절, 조회값, 제공 항목, 근거 문장."""
    sub = conn.execute("SELECT evidence_json, evidence_sentences FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                       (sub_ticket_id,)).fetchone()
    sources = []
    for c in sub[0]:
        row = conn.execute("SELECT section_title, text FROM ref.doc_chunk WHERE chunk_id = %s", (c.get("chunk_id"),)).fetchone()
        if row:
            sources.append(Source(c["doc_id"], c["section"], row[0], row[1]))
    lookups = [(lv["item"], lv["value"], lv.get("unit"), f"{lv.get('source_table')}:{lv.get('source_key')}")
               for lv in (intake_step(conn, sub_ticket_id, "Q9") or {}).get("lookups", [])]
    provided = [tuple(r) for r in conn.execute(
        "SELECT field, coalesce(value_norm, value_raw) FROM svc.inquiry_field WHERE sub_ticket_id = %s ORDER BY field_id",
        (sub_ticket_id,)).fetchall()]
    return sources, lookups, provided, list(sub[1])


def recheck(conn: Connection, sub_ticket_id: str, body: str) -> dict[str, Any]:
    """최종 본문의 자체 대조(FR-031 처리 2 = FR-021 처리 5와 같은 검사)."""
    sources, lookups, provided, _ = draft_sources(conn, sub_ticket_id)
    allowed = ([s.text for s in sources] + [str(v) for _, v, _, _ in lookups]
               + [v for name, v in provided if name in CHECK_PROVIDED_FIELDS and v])
    return check_draft(body, {(s.doc_id, s.section_no) for s in sources}, allowed).as_dict()


def info_request_check(body: str, blocking: list[str], labels: dict[str, str]) -> dict[str, Any]:
    """정보 요청 초안의 자체 대조: 막는 항목 라벨이 본문에 다 있는가(L3 누락 검사와 같은 기준, FR-015 예외 2행)."""
    missing = [labels.get(f, f) for f in blocking if labels.get(f, f) not in body]
    return {"passed": not missing, "missing_labels": missing, "bad_citations": [], "bad_numbers": []}


def check_body(conn: Connection, message_type: str, sub_ticket_id: str, body: str) -> dict[str, Any]:
    """초안 종류에 맞는 자체 대조(FR-031 처리 2: 상담원이 고친 본문도 같은 검사)."""
    if message_type == "FINAL_REPLY":
        return recheck(conn, sub_ticket_id, body)
    (blocking,) = conn.execute("SELECT missing_blocking_info FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                               (sub_ticket_id,)).fetchone()
    return info_request_check(body, list(blocking), (intake_step(conn, sub_ticket_id, "Q5") or {}).get("labels", {}))


def draft_object(conn: Connection, draft: dict[str, Any]) -> Draft:
    return Draft(draft["sub_ticket_id"], draft["message_type"], draft["language"], draft["body"],
                 gloss=latest_gloss(conn, draft["message_id"]))


def update_draft_body(conn: Connection, message_id: int, body: str) -> None:
    conn.execute("UPDATE svc.ticket_message SET body = %s WHERE message_id = %s AND message_status = 'DRAFT'",
                 (body, message_id))


MSG_CLOSED_RECORDED = "종료된 문의입니다. 메시지만 기록됨"  # FR-031 예외 3행
SEND_TRANSITIONS = {  # 발송 뒤 전이 (FR-031 처리 4, FR-025 전이표)
    "INFO_REQUEST": ("WAITING_CUSTOMER", "INFO_REQUEST_SENT"),
    "FINAL_REPLY": ("RESOLVED", "FINAL_REPLY_SENT"),
}


def send_draft(conn: Connection, draft: dict[str, Any], final_body: str, agent_id: str, override: bool,
               expected_version: int | None = None) -> tuple[int, str | None]:
    """SENT 행을 새로 쓰고 초안을 APPROVED로, 처음이면 1차 응답 시각(FR-031 처리 3·5), 상태 전이(처리 4).

    (SENT 행 번호, 전이가 거부됐을 때의 안내)를 돌려준다.
    - 다른 사람이 먼저 바꿨으면(version 다름) ConcurrentChange, 아무것도 쓰지 않는다(FR-025 예외 2행).
    - 전이표에 없는 전이면 발송 기록은 남기고 상태는 그대로, 실행 로그를 남긴다(FR-031 예외 3행).
    """
    now = _now()
    _, mask_count = mask_text(final_body)
    refused: str | None = None
    with conn.transaction():
        to_status, event = SEND_TRANSITIONS[draft["message_type"]]
        try:
            transition(conn, draft["sub_ticket_id"], to_status, event, now, agent_id, expected_version=expected_version)
        except TransitionRefused as exc:
            refused = MSG_CLOSED_RECORDED if exc.status == "CLOSED" else f"{exc} — 메시지만 기록됨"
        (sent_id,) = conn.execute(
            """INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc,
                   language, body, source_draft_id, edited_yn, sent_by_name, override_check, mask_count)
               VALUES (%s, %s, 'AGENT', %s, 'SENT', %s, %s, %s, %s, %s, %s, %s, %s) RETURNING message_id""",
            (draft["ticket_id"], draft["sub_ticket_id"], draft["message_type"], now, draft["language"], final_body,
             draft["message_id"], final_body != draft["body"], agent_id, override, mask_count),
        ).fetchone()
        conn.execute("UPDATE svc.ticket_message SET message_status = 'APPROVED' WHERE message_id = %s", (draft["message_id"],))
        conn.execute(
            """UPDATE svc.sub_ticket SET first_response_at_utc = coalesce(first_response_at_utc, %s),
                   info_request_sent = info_request_sent OR %s
             WHERE sub_ticket_id = %s""",
            (now, draft["message_type"] == "INFO_REQUEST", draft["sub_ticket_id"]),
        )
    if refused:  # 실행 로그 (FR-031 예외 3행, FR-025 예외 1행)
        run_id = start_run(conn, draft["ticket_id"], draft["sub_ticket_id"], "AGENT_EDIT")
        with conn.transaction():
            add_step(conn, run_id, "T6", input_={"message_id": sent_id, "event_kind": event, "to_status": to_status},
                     result="FAILED", error_kind="VALIDATION", error=refused)
            finish_run(conn, run_id, "PARTIAL", "T6")
    return sent_id, refused
