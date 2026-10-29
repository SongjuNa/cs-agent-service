"""고객 회신 재처리의 첫 노드: Q1부터 (기술 명세서 v1.4 §2-4 "고객 회신 재처리", 명세서 v1.5 FR-032 처리 3).

T2(문의 이해)는 다시 부르지 않고 마지막 처리 실행의 T2 결과와 sub_ticket 값을 쓴다. L2 입력 본문은 접수 원문과
모든 고객 회신을 시각순으로 이어 붙여 가린 글이다. 제공 항목은 이전 값을 유지하고 새 항목만 더한다(합집합).
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.db.runs import agent_edits, for_sub, pipeline_run, ticket_of
from app.llm.client import Transport
from app.llm.extract import extract
from app.llm.inputs import prepare_llm_input
from app.masking import MaskingError
from app.pipeline.runlog import track
from app.pipeline.state import ProvidedField, SubTicketState, TicketState
from app.pipeline.understand import UnderstandOutcome, _ref_rows, understand_ticket
from app.rules.lookup import lookup_product
from app.rules.required_info import check_required_info

T2_FLAGS = ("확신 낮음", "분류 실패", "긴급도 판정 실패", "언어 판정 불확실")  # T2가 다는 표시는 이어 받는다


def last_pipeline_step(conn: Connection, sub_ticket_id: str, step_name: str) -> dict | None:
    """그 하위 문의의 마지막 처리 흐름 실행(접수·회신 재처리·다시 처리)에서 한 단계의 결과.

    복합 문의의 T2는 티켓 run에 하위 문의별 몫 목록(sub_tickets)으로 있으므로 그 문의의 seq 몫을 돌려준다.
    """
    row = conn.execute(
        f"""SELECT st.output_json FROM svc.agent_step st JOIN svc.agent_run r ON r.run_id = st.run_id
             WHERE {for_sub()} AND {pipeline_run()} AND st.step_name = %s
             ORDER BY r.run_id DESC, st.step_order DESC LIMIT 1""",
        (sub_ticket_id, ticket_of(sub_ticket_id), step_name),
    ).fetchone()
    out = row[0] if row else None
    if out and "sub_tickets" in out:
        seq = int(sub_ticket_id.rsplit("-", 1)[1])
        part = next((p for p in out["sub_tickets"] if p.get("seq") == seq), {})
        out = {**{k: v for k, v in out.items() if k != "sub_tickets"}, **part}
    return out


def reply_text(conn: Connection, ticket_id: str) -> str:
    """접수 원문 + 모든 고객 회신(시각순)을 빈 줄로 이어 붙인 원문."""
    (body,) = conn.execute("SELECT inquiry_body FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    replies = [r[0] for r in conn.execute(
        """SELECT body FROM svc.ticket_message WHERE ticket_id = %s AND message_type = 'CUSTOMER_REPLY'
            ORDER BY sent_at_utc, message_no""", (ticket_id,)).fetchall()]
    return "\n\n".join([body, *replies])


def dept_reply_text(conn: Connection, sub_ticket_id: str) -> str:
    """그 하위 문의의 이관 부서 회신(ESCALATION_NOTE RECEIVED) 원문을 시각순으로 빈 줄로 이은 글(C-162). 없으면 빈 글."""
    return "\n\n".join(r[0] for r in conn.execute(
        """SELECT body FROM svc.ticket_message WHERE sub_ticket_id = %s AND message_type = 'ESCALATION_NOTE'
              AND message_status = 'RECEIVED' ORDER BY sent_at_utc, message_no""", (sub_ticket_id,)).fetchall())


def reextract(conn: Connection, transport: Transport, ticket_input: dict[str, Any]) -> UnderstandOutcome:
    """처리 흐름 첫 노드 자리에 들어간다. ticket_input은 {"ticket_id", "target_ids"}."""
    ticket_id = ticket_input["ticket_id"]
    t = conn.execute("SELECT channel, customer_id, language, body_language, body_language_uncertain, received_at_utc, "
                     "multi_yn FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    try:  # T1과 같이 가린다. 검사 오류면 언어 모델을 부르지 않는다(§7)
        body_masked = prepare_llm_input({"inquiry_body": reply_text(conn, ticket_id)}).fields["inquiry_body"]
    except MaskingError as exc:
        return UnderstandOutcome(None, "FAILED", MaskingError.kind, str(exc))

    info_fields = _ref_rows(conn, "SELECT field, label FROM ref.info_field ORDER BY field")
    product_codes = [r[0] for r in _ref_rows(conn, "SELECT product_code FROM ref.product")]
    subs, names = [], []
    for sub_id in ticket_input["target_ids"]:
        row = conn.execute(
            """SELECT seq, category_code, evidence_sentences, urgency_flag, product_code, error_code_reported,
                      fw_version_reported, return_kind FROM svc.sub_ticket WHERE sub_ticket_id = %s""", (sub_id,)).fetchone()
        seq, category, evidence, urgency, product_code, error_code, fw, return_kind = row
        t2 = last_pipeline_step(conn, sub_id, "T2") or {}
        q1 = last_pipeline_step(conn, sub_id, "Q1") or {}
        flags = last_pipeline_step(conn, sub_id, _last_step_name(conn, sub_id)) or {}
        family = lookup_product(conn, product_code).product_family
        required = check_required_info(conn, family, category, []).required_info
        with track(transport, sub_id):
            l2 = extract(transport, body_masked, list(evidence), info_fields, required, family, category,
                         product_code, product_codes)
        before = [ProvidedField(field=f, value_raw=raw or "", value_norm=norm) for f, raw, norm in conn.execute(
            """SELECT field, value_raw, value_norm FROM svc.inquiry_field WHERE sub_ticket_id = %s ORDER BY field_id""",
            (sub_id,)).fetchall()]
        known = {pf.field for pf in before}
        merged = before + [pf for pf in l2.provided_fields if pf.field not in known]  # FR-032 처리 3: 늘기만 한다
        new_code = product_code or l2.product_code
        if new_code and new_code != product_code:
            family = lookup_product(conn, new_code).product_family
        subs.append(SubTicketState(
            sub_ticket_id=sub_id, ticket_id=ticket_id, seq=seq, category_code=category,
            category_confidence=t2.get("category_confidence"), evidence_sentences=list(evidence),
            query_en=t2.get("query_en"), urgency_flag=urgency, urgency_evidence=t2.get("urgency_evidence"),
            provided_fields=merged, product_code=new_code, product_family=family,
            error_code=error_code or l2.error_code, current_fw=fw or l2.current_fw,
            return_reason=l2.return_reason or q1.get("return_reason"),
            return_kind=return_kind if _agent_chose_return(conn, sub_id) else None,  # 상담원이 고른 반품 구분(FR-030 처리 6)
            flags=[f for f in flags.get("flags", []) if f.startswith(T2_FLAGS)] + l2.flags,
        ))
        names = l2.field_names
    state = TicketState(ticket_id=ticket_id, channel=t[0], customer_id=t[1], language=t[2], body_language=t[3],
                        body_language_uncertain=t[4], body_masked=body_masked, received_at=t[5], sub_tickets=subs,
                        multi_yn=t[6])
    return UnderstandOutcome(state, "SUCCESS", llm_field_names={"L2": names})


def _last_step_name(conn: Connection, sub_ticket_id: str) -> str:
    row = conn.execute(
        f"""SELECT r.last_step FROM svc.agent_run r WHERE {for_sub()} AND {pipeline_run()}
                AND r.last_step IS NOT NULL ORDER BY r.run_id DESC LIMIT 1""",
        (sub_ticket_id, ticket_of(sub_ticket_id))).fetchone()
    return row[0] if row else "Q6"


def reuse(conn: Connection, transport: Transport, ticket_input: dict[str, Any]) -> UnderstandOutcome:
    """상담원 수정(AGENT_EDIT)의 첫 노드: 언어 모델을 부르지 않고 규칙 단계(Q2)부터(FR-030 처리 6, §2-4 부분 재실행).

    ticket_input = {"ticket_id", "target_ids", "agent_edit"}. 고친 값은 이미 sub_ticket 열과 inquiry_field(source AGENT)에
    있으므로 지금 값을 그대로 읽는다. T2 표시 중 상담원이 고친 항목의 표시는 뗀다.
    """
    ticket_id = ticket_input["ticket_id"]
    record = ticket_input.get("agent_edit") or {}
    changed = set(record.get("agent_edit", {}))
    t = conn.execute("SELECT channel, customer_id, language, body_language, body_language_uncertain, received_at_utc, "
                     "multi_yn, inquiry_body FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    subs = []
    for sub_id in ticket_input["target_ids"]:
        seq, category, evidence, urgency, product_code, error_code, fw, return_kind = conn.execute(
            """SELECT seq, category_code, evidence_sentences, urgency_flag, product_code, error_code_reported,
                      fw_version_reported, return_kind FROM svc.sub_ticket WHERE sub_ticket_id = %s""",
            (sub_id,)).fetchone()
        t2 = last_pipeline_step(conn, sub_id, "T2") or {}
        q1 = last_pipeline_step(conn, sub_id, "Q1") or {}
        flags = (last_pipeline_step(conn, sub_id, _last_step_name(conn, sub_id)) or {}).get("flags", [])
        dropped = ((("확신 낮음", "분류 실패") if "category_code" in changed else ())
                   + (("긴급도 판정 실패",) if "urgency_flag" in changed else ()))
        provided = [ProvidedField(field=f, value_raw=raw or "", value_norm=norm) for f, raw, norm in conn.execute(
            "SELECT field, value_raw, value_norm FROM svc.inquiry_field WHERE sub_ticket_id = %s ORDER BY field_id",
            (sub_id,)).fetchall()]
        subs.append(SubTicketState(
            sub_ticket_id=sub_id, ticket_id=ticket_id, seq=seq, category_code=category,
            category_confidence=t2.get("category_confidence"), evidence_sentences=list(evidence),
            query_en=t2.get("query_en"), urgency_flag=urgency, urgency_evidence=t2.get("urgency_evidence"),
            provided_fields=provided, product_code=product_code,
            product_family=lookup_product(conn, product_code).product_family, error_code=error_code, current_fw=fw,
            return_reason=q1.get("return_reason"),
            return_kind=return_kind if "return_kind" in changed or _agent_chose_return(conn, sub_id) else None,
            flags=[f for f in flags if f.startswith(T2_FLAGS) and not (dropped and f.startswith(dropped))],
        ))
    try:  # 처리 흐름의 뒤 노드(Q8 검색 등)가 쓰는 가린 본문. 원문 + 고객 회신(§7)
        body_masked = prepare_llm_input({"inquiry_body": reply_text(conn, ticket_id)}).fields["inquiry_body"]
    except MaskingError as exc:
        return UnderstandOutcome(None, "FAILED", MaskingError.kind, str(exc))
    state = TicketState(ticket_id=ticket_id, channel=t[0], customer_id=t[1], language=t[2], body_language=t[3],
                        body_language_uncertain=t[4], body_masked=body_masked, received_at=t[5], sub_tickets=subs,
                        multi_yn=t[6], agent_edit=record or None)
    return UnderstandOutcome(state, "SUCCESS", llm_field_names={})


def with_dept_reply(conn: Connection, transport: Transport, ticket_input: dict[str, Any]) -> UnderstandOutcome:
    """이관 부서 회신(DEPT_REPLY)의 첫 노드: 언어 모델 없이 저장값을 읽는다. 언어 모델은 Q8부터(§2-4, C-160).

    규칙 단계(Q2~Q6)는 다시 계산해도 같은 값이고, 고장 진단(Q8a)·유사 해결사례(Q8b)·이관 후보(Q9a)는 직전 결과를 옮겨 적는다(그래프가 건너뜀).
    부서 회신 글을 dept_reply에 넣어 답변 경로(Q8~Q14)가 L4·Q11·L8에 쓰게 한다(§2-3 dept_reply).
    """
    outcome = reuse(conn, transport, {"ticket_id": ticket_input["ticket_id"], "target_ids": ticket_input["target_ids"]})
    if outcome.state is not None:
        for sub in outcome.state.sub_tickets:
            sub.dept_reply = dept_reply_text(conn, sub.sub_ticket_id) or None
            sub.diagnosis = last_pipeline_step(conn, sub.sub_ticket_id, "Q8a")
            sub.similar_cases = last_pipeline_step(conn, sub.sub_ticket_id, "Q8b")
            sub.escalation = last_pipeline_step(conn, sub.sub_ticket_id, "Q9a")
    return outcome


def _agent_chose_return(conn: Connection, sub_ticket_id: str) -> bool:
    """이전 상담원 수정에서 반품 구분을 골랐는지(고른 값은 규칙이 다시 판정하지 않는다, design 결정 3)."""
    return conn.execute(
        """SELECT 1 FROM svc.agent_step st JOIN svc.agent_run r ON r.run_id = st.run_id
            WHERE r.sub_ticket_id = %s AND r.trigger = 'AGENT_EDIT' AND st.step_name = 'Q2'
              AND st.input_json -> 'agent_edit' ? 'return_kind' LIMIT 1""", (sub_ticket_id,)).fetchone() is not None


def keep_agent_edits(conn: Connection, transport: Transport, ticket_input: dict[str, Any]) -> UnderstandOutcome:
    """다시 처리(RETRY)의 첫 노드: 처음부터 다시 이해한 뒤 상담원이 고친 값을 덮어 둔다(FR-030 처리 5·6, C-112).

    고친 유형·긴급도·제품·반품 구분은 언어 모델의 새 판정보다 앞서고, 상담원이 "받았음"으로 둔 항목(inquiry_field
    source AGENT)은 제공 항목에 넣는다. 그 하위 문의가 없어졌으면(나눔이 달라짐) 덮을 것이 없다.
    """
    outcome = understand_ticket(conn, transport, ticket_input)
    if outcome.state is None:
        return outcome
    for sub in outcome.state.sub_tickets:
        edits = agent_edits(conn, sub.sub_ticket_id)
        if not edits:
            continue
        to = {name: e["to"] for name, e in edits.items()}
        dropped: tuple[str, ...] = ()
        if "category_code" in to:
            sub.category_code = to["category_code"]
            dropped += ("확신 낮음", "분류 실패")
        if "urgency_flag" in to:
            sub.urgency_flag = to["urgency_flag"]
            dropped += ("긴급도 판정 실패",)
        if "product_code" in to:
            sub.product_code = to["product_code"]
            sub.product_family = lookup_product(conn, sub.product_code).product_family
        if "return_kind" in to and sub.category_code == "RETURN":
            sub.return_kind = to["return_kind"]
        if dropped:
            sub.flags = [f for f in sub.flags if not f.startswith(dropped)]
        known = {pf.field for pf in sub.provided_fields}
        sub.provided_fields += [ProvidedField(field=f, value_raw=raw or "", value_norm=norm) for f, raw, norm in conn.execute(
            """SELECT field, value_raw, value_norm FROM svc.inquiry_field WHERE sub_ticket_id = %s AND source = 'AGENT'
                ORDER BY field_id""", (sub.sub_ticket_id,)).fetchall() if f not in known]
    return outcome
