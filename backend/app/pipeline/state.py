"""상태 객체 (기술 명세서 v1.4 §2-3, T32).

노드끼리 넘기는 값이다. 이름은 DB 표(§6)와 맞춘다. 이번 변경(문의 이해)이 쓰지 않는 필드도
이름과 형식은 그대로 두고, 뒤 변경이 채운다.

제목(inquiry_subject)은 넣지 않는다. 그래서 어떤 노드도 제목을 읽을 수 없다(§2-3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProvidedField(BaseModel):
    """L2가 뽑은 제공 항목 1개 (§3-2 L2 추출 출력)."""

    field: str
    value_raw: str
    value_norm: str | None = None
    span: tuple[int, int] | None = None  # 가린 본문(body_masked) 기준 글자 위치


class RuleCheck(BaseModel):
    rule_id: str
    matched: bool


class FaultCandidate(BaseModel):
    fault_id: str
    cause: str | None = None  # ref.fault.root_cause
    check: str | None = None  # ref.fault.diagnosis(점검)
    action: str | None = None
    onsite_required: bool | None = None
    replace_required: bool | None = None
    method: str | None = None
    score: float | None = None


class EscalationHint(BaseModel):
    rule_id: str
    dept: str
    reason: str | None = None
    reason_code: str | None = None  # escalation_reason 코드([이관] 기본값, C-146)
    team: bool = False  # 팀 보충 규칙(설정 파일)에서 나온 후보


class DocCandidate(BaseModel):
    chunk_id: int | str
    doc_id: str
    section_no: str | None = None
    title: str | None = None
    score: float | None = None


class LookupValue(BaseModel):
    item: str
    value: Any = None
    unit: str | None = None
    source_table: str | None = None
    source_key: str | None = None


class VerifyFinding(BaseModel):
    kind: str
    quote: str
    reason: str


class SubTicketState(BaseModel):
    """하위 문의 1개의 메모지 (DB: svc.sub_ticket)."""

    sub_ticket_id: str  # f"{ticket_id}-{seq}"
    ticket_id: str
    seq: int
    category_code: str | None = None  # 10종 또는 None(분류 실패)
    category_confidence: float | None = None
    evidence_sentences: list[str] = Field(default_factory=list)
    query_en: str | None = None
    urgency_flag: str = "NONE"  # 6값, 실패 시 NONE
    urgency_evidence: str | None = None
    provided_fields: list[ProvidedField] = Field(default_factory=list)
    product_code: str | None = None
    product_family: str | None = None
    customer_tier: str | None = None  # Q2(FR-010)가 채운다
    error_code: str | None = None  # DB: sub_ticket.error_code_reported
    current_fw: str | None = None  # DB: sub_ticket.fw_version_reported
    return_reason: str | None = None
    return_kind: Literal["DEFECT", "NON_DEFECT", "UNKNOWN"] | None = None
    priority_rule: str | None = None
    priority_rule_id: str | None = None
    priority_trace: list[RuleCheck] = Field(default_factory=list)
    assignee: str | None = None
    priority_final: str | None = None
    assigned_dept: str | None = None
    routing_rule_id: str | None = None
    escalation_condition: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    missing_blocking_info: list[str] = Field(default_factory=list)
    sla_id: str | None = None
    fr_target_h: int | None = None
    res_target_h: int | None = None
    fault_candidates: list[FaultCandidate] = Field(default_factory=list)
    diagnosis: dict[str, Any] | None = None  # Q8a 결과(후보·찾은 방법·표시 문구). 진단 대상이 아니면 None. DB 열 아님
    similar_cases: dict[str, Any] | None = None  # Q8b 결과(사례 3건까지·표시 문구, FR-019). 찾는 유형이 아니면 None. DB 열 아님
    escalation_candidates: list[EscalationHint] = Field(default_factory=list)
    escalation: dict[str, Any] | None = None  # Q9a 결과(후보·이관 조건 문구·표시·실패 여부). DB 열 아님
    doc_candidates: list[DocCandidate] = Field(default_factory=list)
    lookups: list[LookupValue] = Field(default_factory=list)
    draft_id: int | None = None
    draft_check: dict[str, Any] | None = None  # 모양은 초안 변경(FR-021)이 정한다
    verify_findings: list[VerifyFinding] | None = None
    dept_reply: str | None = None
    flags: list[str] = Field(default_factory=list)
    pipeline_error: str | None = None
    failed_step: str | None = None  # pipeline_error가 난 단계(Q7·Q8·Q10·T5). 실행 기록용, DB 열 아님


class TicketState(BaseModel):
    """티켓의 메모지 (DB: svc.ticket)."""

    ticket_id: str
    channel: str
    customer_id: str
    language: str
    body_language: str | None = None
    body_language_uncertain: bool = False
    body_masked: str
    received_at: datetime | None = None
    sub_tickets: list[SubTicketState] = Field(default_factory=list)
    multi_yn: bool = False
    run_id: int | None = None  # 실행 기록(svc.agent_run) 저장은 접수 API와 함께 만든다
    agent_edit: dict[str, Any] | None = None  # 상담원 수정 실행의 기록(FR-030 처리 6). Q2 단계 input_json에 남긴다. DB 열 아님
