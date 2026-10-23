"""고객 회신 재처리의 첫 노드: Q1부터 (기술 명세서 v1.4 §2-4 "고객 회신 재처리", 명세서 v1.5 FR-032 처리 3).

T2(문의 이해)는 다시 부르지 않고 마지막 처리 실행의 T2 결과와 sub_ticket 값을 쓴다. L2 입력 본문은 접수 원문과
모든 고객 회신을 시각순으로 이어 붙여 가린 글이다. 제공 항목은 이전 값을 유지하고 새 항목만 더한다(합집합).
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.db.runs import for_sub, pipeline_run, ticket_of
from app.llm.client import Transport
from app.llm.extract import extract
from app.llm.inputs import prepare_llm_input
from app.masking import MaskingError
from app.pipeline.runlog import track
from app.pipeline.state import ProvidedField, SubTicketState, TicketState
from app.pipeline.understand import UnderstandOutcome, _ref_rows
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
                      fw_version_reported FROM svc.sub_ticket WHERE sub_ticket_id = %s""", (sub_id,)).fetchone()
        seq, category, evidence, urgency, product_code, error_code, fw = row
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
