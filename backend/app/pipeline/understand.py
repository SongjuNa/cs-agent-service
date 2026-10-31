"""처리 흐름 앞부분: T1 입력 고정 → T2 문의 이해(L1) → Q1 추출(L2) (기술 명세서 v1.4 §2-2).

접수 입력 한 건을 받아 하위 문의 n개가 든 TicketState를 만든다. L1이 나눈 요청마다 하위 문의 하나이고,
추출(L2)은 하위 문의마다 자기 유형·근거 문장으로 부른다(FR-006 처리 4, 변경 add-compound-inquiry).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection

from app.llm.client import LlmError, Transport
from app.llm.extract import extract
from app.llm.understand import FLAG_LANG_UNCERTAIN, understand
from app.llm.inputs import prepare_llm_input
from app.masking import MaskingError
from app.pipeline.runlog import track
from app.pipeline.state import SubTicketState, TicketState
from app.rules.lookup import lookup_product
from app.rules.required_info import check_required_info

# 접수 입력에서 읽는 열 (gold.v_inputs와 같은 입력 열). 제목(inquiry_subject)은 읽지 않는다(§2-3)
INPUT_COLUMNS = ("ticket_id", "channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")

MESSAGE_RETRY = "자동 처리 실패. 다시 시도"  # FR-005 예외 2행


@dataclass
class UnderstandOutcome:
    state: TicketState | None
    run_status: str  # schema.sql agent_run.status: SUCCESS / FAILED
    error_type: str | None = None  # 기술 명세서 §6-5 오류 종류
    message: str | None = None
    llm_field_names: dict[str, list[str]] | None = None  # 호출별 넣은 항목 이름 (§3-3)


def _ref_rows(conn: Connection, sql: str) -> list[tuple]:
    return [tuple(r) for r in conn.execute(sql).fetchall()]


def understand_ticket(conn: Connection, transport: Transport, ticket_input: dict[str, Any]) -> UnderstandOutcome:
    data = {k: ticket_input.get(k) for k in INPUT_COLUMNS}
    ticket_id = data["ticket_id"]
    language = data["language"]

    # T1 입력 고정: 본문을 가린다. 검사 오류면 언어 모델을 부르지 않는다(§2-2 T1, §7)
    try:
        if not isinstance(data["inquiry_body"], str) or not data["inquiry_body"].strip():
            raise MaskingError("본문이 없다")
        body_masked = prepare_llm_input({"inquiry_body": data["inquiry_body"]}).fields["inquiry_body"]
    except MaskingError as exc:
        return UnderstandOutcome(None, "FAILED", MaskingError.kind, str(exc))

    input_product = data["product_code"] or None
    product = lookup_product(conn, input_product)

    # T2 문의 이해 (L1)
    urgency_rows = _ref_rows(conn, "SELECT urgency, description FROM ref.urgency")
    try:
        l1 = understand(transport, body_masked, data["channel"], language, product.product_family, urgency_rows)
    except LlmError as exc:
        return UnderstandOutcome(None, "FAILED", exc.error_type, MESSAGE_RETRY)

    received = data["received_at_utc"]
    if isinstance(received, str) and received:
        received = datetime.fromisoformat(received)

    # Q1 추출 (L2). 하위 문의마다 그 제품군×유형의 required_info (§3-1 L2 입력, FR-006 처리 4)
    info_fields = _ref_rows(conn, "SELECT field, label FROM ref.info_field ORDER BY field")
    product_codes = [r[0] for r in _ref_rows(conn, "SELECT product_code FROM ref.product")]
    ticket_flags = [f for f in l1.flags if f == FLAG_LANG_UNCERTAIN]  # 언어 판정은 티켓 하나에 한 번
    subs, l2_names = [], []
    for req in l1.requests:
        required = check_required_info(conn, product.product_family, req.category_code, []).required_info
        with track(transport, f"{ticket_id}-{req.seq}"):
            l2 = extract(
                transport, body_masked, req.evidence_sentences, info_fields, required,
                product.product_family, req.category_code, input_product, product_codes,
            )
        l2_names = l2.field_names
        product_code = input_product or l2.product_code
        family = product.product_family
        if product_code and product_code != input_product:
            family = lookup_product(conn, product_code).product_family  # 보완한 코드로 제품군을 다시 구한다
        subs.append(SubTicketState(
            sub_ticket_id=f"{ticket_id}-{req.seq}",
            ticket_id=ticket_id,
            seq=req.seq,
            category_code=req.category_code,
            category_confidence=req.category_confidence,
            evidence_sentences=req.evidence_sentences,
            query_en=req.query_en,
            urgency_flag=req.urgency_flag,
            urgency_evidence=req.urgency_evidence,
            summary_ko=req.summary_ko,
            provided_fields=l2.provided_fields,
            product_code=product_code,
            product_family=family,
            error_code=l2.error_code,
            current_fw=l2.current_fw,
            return_reason=l2.return_reason,
            flags=ticket_flags + req.flags + l2.flags,
        ))
    state = TicketState(
        ticket_id=ticket_id,
        channel=data["channel"],
        customer_id=data["customer_id"],
        language=language,
        body_language=l1.body_language,
        body_language_uncertain=l1.body_language_uncertain,
        body_masked=body_masked,
        received_at=received or None,
        sub_tickets=subs,
        multi_yn=len(subs) > 1,
    )
    return UnderstandOutcome(state, "SUCCESS", llm_field_names={"L1": l1.field_names, "L2": l2_names})
