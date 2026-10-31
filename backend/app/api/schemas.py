"""API 응답 모양 (변경 add-api-response-models, 기술 명세서 v1.4 §1·§8-1).

라우터의 response_model로 쓰여 /openapi.json에 응답 모양을 싣는다. 화면 타입(frontend/src/api.gen.ts)은 이 계약에서 만든다.
동작을 바꾸지 않는다(design 결정 2):
- 모든 모델은 extra="allow"라 여기 적지 않은 값도 응답에서 빠지지 않는다.
- 숫자는 Num(int | float | Decimal)으로 받아 들어온 종류 그대로 내보낸다. DB numeric(Decimal)은 지금처럼 문자열로 나간다.
- 칸이 매번 다른 값(실행 단계 출력, 규칙 행, 「왜?」)은 dict[str, Any]로 둔다(design 결정 3).
이름은 화면 타입(frontend/src/api.ts)과 같게 둔다(design 결정 1).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict

Num = Union[int, float, Decimal]
Json = dict[str, Any]


def _closed(schema: dict[str, Any]) -> None:
    """계약에는 적은 칸만 싣는다(additionalProperties를 빼서 화면 타입에 아무 이름 칸이 생기지 않게)."""
    schema.pop("additionalProperties", None)


class Out(BaseModel):
    # extra="allow": 적지 않은 값도 응답에서 빼지 않는다(동작 유지). 계약에는 적은 칸만 보인다
    model_config = ConfigDict(extra="allow", json_schema_extra=_closed)


# ---- 접수·처리 시작 (POST /tickets, /tickets/{id}/reprocess, /tickets/{id}/replies) ----

class Accepted(Out):
    ticket_id: str
    processing: bool
    run_id: int | None = None


class ReplyTransition(Out):
    sub_ticket_id: str
    # "from"은 파이썬 예약어라 모델 칸으로 두지 않는다(extra로 그대로 나간다)
    to: str


class ReplyAccepted(Out):
    message_id: int
    targets: list[str]
    transitions: list[ReplyTransition]
    reprocess: list[str]
    notes: list[str]
    processing: bool


# ---- 접수함 (GET /tickets, FR-029) ----

class Note(Out):
    """내부 메모(add-internal-notes). 고객에게 보내지 않는다."""

    note_id: int
    ticket_id: str
    body: str
    author: str
    created_at_utc: datetime


class AssignSkip(Out):
    sub_ticket_id: str
    reason: str


class AssignResult(Out):
    """담당 변경 결과(add-reassign). 바뀐 문의와, 건너뛴 문의(사유와 함께)."""

    moved: list[str]
    skipped: list[AssignSkip]


class InboxCounts(Out):
    total: int
    alert: int
    needs_info: int
    has_draft: int
    waiting: int
    new: int  # 신규(NEW) 상태
    escalated: int  # 이관(ESCALATED) 상태
    breach: int  # 기한 초과 경고가 있는 줄(1차 응답·해결 중 하나라도)
    risk: int  # 기한 임박 경고만 있는 줄(초과가 있으면 breach로만 센다)
    mine: int  # 요청의 me와 담당 상담원이 같은 줄
    turn_me: int  # 내 차례(turn=ME)인 줄
    deep: int  # 검토 모드 상세(review_depth=DEEP)인 줄


class InboxRow(Out):
    sub_ticket_id: str
    ticket_id: str
    seq: int
    inquiry_count: int
    received_at_utc: datetime
    channel: str
    language: str
    customer_id: str
    company_masked: str
    customer_tier: str
    country: str | None
    inquiry_subject: str | None
    product_code: str | None
    product_name: str | None
    category_code: str | None
    urgency_flag: str
    priority: str | None
    priority_adjusted: bool | None
    assigned_dept: str | None
    escalated_to: str | None
    assignee_masked: str | None
    escalated_in_from: str | None
    status: str
    fr_status: str | None
    res_status: str | None
    remaining_h: Num | None
    alerts: list[str]
    needs_info: bool
    has_unsent_draft: bool
    reminder_sent: bool
    turn: str  # ME·DEPT·CUSTOMER·DONE
    next_action: str  # DONE·WAIT_DEPT·WAIT_CUSTOMER·SEND_INFO_REQUEST·CHECK_DEPT_REPLY·APPROVE_DRAFT·WRITE_ANSWER
    review_depth: str  # DEEP·NORMAL·QUICK
    memo_count: int  # 이 티켓의 내부 메모 수(add-internal-notes)


class Inbox(Out):
    dept: str | None
    as_of: datetime
    page: int
    size: int
    counts: InboxCounts
    rows: list[InboxRow]
    message: str | None


# ---- 티켓 상세 (GET /tickets/{id}, FR-024·030) ----

class Ticket(Out):
    ticket_id: str
    received_at_utc: datetime
    channel: str
    language: str
    body_language: str | None
    body_language_uncertain: bool
    customer_id: str
    customer_tier: str
    company_masked: str
    country: str
    source: str
    source_ticket_id: str | None
    multi_yn: bool
    inquiry_subject: str | None
    inquiry_body: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    gold_set: bool
    category_code: str | None


class Run(Out):
    run_id: int
    trigger: str
    status: str | None
    last_step: str | None
    started_at_utc: datetime
    finished_at_utc: datetime | None


class Summary(Out):
    status: str
    rep_sub_ticket_id: str | None
    rep_res_status: str | None
    rep_remaining_h: Num | None
    open_count: int | None
    inquiry_count: int | None


class Message(Out):
    message_id: int
    message_no: int
    seq: int | None
    sender: str
    message_type: str
    message_status: str
    sent_at_utc: datetime
    language: str
    body: str
    sent_by_name: str
    source_draft_id: int | None
    edited_yn: bool | None
    mask_count: int | None
    notice_transition: str | None


class SubTicketRow(Out):
    """svc.sub_ticket 열 중 상세가 내보내는 것(detail._sub_detail)."""

    sub_ticket_id: str
    seq: int
    category_code: str | None
    assignee_masked: str | None
    urgency_flag: str
    product_code: str | None
    priority: str | None
    priority_rule_id: str | None
    routing_rule_id: str | None
    assigned_dept: str | None
    return_kind: str | None
    sla_id: str | None
    required_info: list[str]
    provided_info: list[str]
    missing_info: list[str]
    missing_blocking_info: list[str]
    sla_first_response_target_h: int | None
    sla_resolution_target_h: int | None
    first_response_at_utc: datetime | None
    info_request_sent: bool
    status: str
    pipeline_error: str | None
    evidence_json: Any
    escalated: bool
    escalated_to: str | None
    escalation_reason: str | None


class SubState(Out):
    status: str
    version: int
    resolved_at_utc: datetime | None
    final_action: str | None
    priority: str | None
    priority_rule_id: str | None
    priority_adjusted_by_agent: bool | None


class Sla(Out):
    fr_target_h: int | None
    res_target_h: int | None
    fr_elapsed_h: Num | None
    fr_status: str | None
    wait_h: Num | None
    res_elapsed_h: Num | None
    res_status: str | None
    remaining_h: Num | None
    as_of_utc: datetime | None
    notes: list[str]


class Adjustment(Out):
    adjust_id: int
    from_priority: str
    to_priority: str
    from_sla_id: str | None
    to_sla_id: str | None
    from_fr_target_h: int | None
    from_res_target_h: int | None
    to_fr_target_h: int | None
    to_res_target_h: int | None
    reason_kind: str
    reason: str
    adjusted_by: str
    adjusted_at_utc: datetime


class StatusHistory(Out):
    from_status: str | None
    to_status: str | None
    event_kind: str | None
    changed_at_utc: datetime | None
    changed_by: str | None
    reason: str | None


class WaitInterval(Out):
    entered_at_utc: datetime | None
    left_at_utc: datetime | None


class AlertRow(Out):
    alert_type: str
    raised_at_utc: datetime | None
    elapsed_h: Num | None
    target_h: int | None
    cleared_at_utc: datetime | None


class CheckFlag(Out):
    check_type: str
    flag: str | None


class RequiredItem(Out):
    field: str
    label: str
    state: Literal["provided", "missing", "blocking"]
    value: str | None


class EvidenceRow(Out):
    """근거 영역 한 줄(C-01~C-09). why·candidates·lookups는 줄마다 칸이 다르다(design 결정 3)."""

    id: str
    label: str
    result: str
    evidence: list[str]
    why: Json
    items: list[RequiredItem] | None = None
    candidates: Any = None
    lookups: Any = None


class Gloss(Out):
    language: str | None
    body: str | None
    numbers_match: bool | None
    made_at_utc: datetime | None


class SelfCheck(Out):
    passed_yn: bool | None
    detail: Json | None
    checked_at_utc: datetime | None


class SentCopy(Out):
    message_id: int
    sent_at_utc: datetime
    sent_by_name: str
    edited_yn: bool | None
    override_check: bool | None
    body: str


class Mark(Out):
    no: int
    passed: bool
    state: str | None = None
    text: str | None
    findings: list[Json] | None = None
    full_text: str | None = None
    detail: Json | None = None


class ReviewMarks(Out):
    marks: list[Mark]
    summary: str


class Draft(Out):
    message_id: int
    message_no: int
    message_type: Literal["INFO_REQUEST", "FINAL_REPLY"]
    message_status: str
    language: str
    body: str
    made_at_utc: datetime
    superseded_at: datetime | None
    re_request: bool
    gloss: Gloss | None
    check: SelfCheck | None
    verify: SelfCheck | None
    sent: SentCopy | None
    review_marks: ReviewMarks


class Field(Out):
    field: str
    label: str
    value_raw: str | None
    value_norm: str | None
    span_start: int | None
    span_end: int | None
    source: str | None


class DeptReply(Out):
    message_id: int
    body: str
    sent_by_name: str
    sent_at_utc: datetime


class DeptMail(DeptReply):
    message_status: str
    superseded_at: datetime | None
    gloss: str | None


class SimilarCase(Out):
    case_id: str
    cause: str | None
    action: str | None
    result: str | None
    error_code: str | None = None
    score: Num
    method: str


class SimilarCases(Out):
    cases: list[SimilarCase]
    notes: list[str]


class SubTicket(Out):
    sub_ticket: SubTicketRow
    escalated_at_utc: datetime | None
    checks: list[CheckFlag]
    other_flags: list[str]
    diagnosis: Json | None  # 고장 진단 후보(FR-018). 고장 계열이 아니면 null
    similar_cases: SimilarCases | None = None  # 유사 해결사례(FR-019, add-similar-cases 결정 4). 찾는 유형이 아니면 null
    escalation: Json | None  # 이관 후보(FR-020)
    evidence_rows: list[EvidenceRow]
    drafts: list[Draft]
    fields: list[Field]
    edits: Json
    product_name: str | None
    version: int
    state: SubState
    adjustments: list[Adjustment]
    sla: Sla | None
    history: list[StatusHistory]
    wait_intervals: list[WaitInterval]
    alerts: list[AlertRow]
    customer_followups: int
    writer: Literal["CS", "DEPT_REPLY", "DEPT_MAIL"]
    dept_replies: list[DeptReply]
    dept_mails: list[DeptMail]
    turn: str  # ME·DEPT·CUSTOMER·DONE (접수함 줄과 같은 규칙, add-inbox-turn-depth)
    next_action: str
    review_depth: str  # DEEP·NORMAL·QUICK


class Detail(Out):
    ticket: Ticket
    summary: Summary | None
    run: Run | None
    processing: bool
    can_retry: bool
    can_reprocess: bool
    sub_tickets: list[SubTicket]
    messages: list[Message]


class TimelineItem(Out):
    """한 줄 = 공통 칸 + 종류별 칸(extra)."""

    kind: str  # STATUS / MESSAGE / PRIORITY / ASSIGNEE / ALERT_RAISED / ALERT_CLEARED
    at: datetime
    seq: int | None
    id: int


# ---- 메시지 (PUT /messages/{id}, gloss, verify, send) ----

class Saved(Out):
    message_id: int
    gloss: bool


class Verified(Out):
    message_id: int
    state: str | None
    mark: str


class Sent(Out):
    sent_message_id: int
    override_check: bool
    notes: list[str]
    status_changed: bool


# ---- 근거 절 (GET /chunks/{id}) ----

class Chunk(Out):
    chunk_id: str
    doc_id: str
    doc_title: str | None
    section_no: str | None
    section_title: str | None
    text: str


# ---- 하위 문의 (우선순위·수정·이관·부서 회신) ----

class AdjustPreview(Out):
    from_priority: str | None
    to_priority: str
    from_sla_id: str | None
    to_sla_id: str | None
    from_fr_target_h: int | None
    from_res_target_h: int | None
    to_fr_target_h: int | None
    to_res_target_h: int | None
    becomes_breached: bool
    fr_elapsed_h: Num | None
    res_elapsed_h: Num | None
    version: int


class Adjusted(Out):
    adjust_id: int
    priority: str
    priority_adjusted_by_agent: bool
    from_priority: str | None
    from_sla_id: str | None
    to_sla_id: str | None
    from_fr_target_h: int | None
    from_res_target_h: int | None
    to_fr_target_h: int | None
    to_res_target_h: int | None
    sla: Sla | None
    alerts_raised: list[str]
    alerts_cleared: list[str]


class EditAccepted(Out):
    sub_ticket_id: str
    processing: bool
    run_id: int
    version: int | None
    changes: Json


class Escalated(Out):
    sub_ticket_id: str
    status: str
    escalated_to: str
    escalation_reason: str | None
    assigned_dept: str | None
    note_message_id: int | None
    version: int | None


class DeptReplyAccepted(Out):
    sub_ticket_id: str
    status: str
    reply_message_id: int
    run_id: int | None
    processing: bool


class DeptMailSaved(Out):
    sub_ticket_id: str
    message_id: int


# ---- 처리 기록 (GET /tickets/{id}/runs, /runs/{id}/steps, FR-036) ----

class RunRow(Out):
    run_id: int
    ticket_id: str | None
    sub_ticket_id: str | None
    trigger: str
    started_at_utc: datetime
    finished_at_utc: datetime | None
    duration_ms: int | None
    status: str | None
    last_step: str | None
    llm_model: str | None


class RunListRow(RunRow):
    pipeline: bool | None
    step_count: int
    failed_steps: int
    llm_calls: int | None
    input_tokens: int | None
    output_tokens: int | None
    current: bool


class Runs(Out):
    ticket_id: str
    runs: list[RunListRow]


class Step(Out):
    step_id: int
    step_name: str
    step_order: int | None
    started_at_utc: datetime | None
    finished_at_utc: datetime | None
    latency_ms: int | None
    result: str | None
    error_kind: str | None
    error: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    llm_calls: int | None
    input_json: Any
    output_json: Any


class Steps(Out):
    run: RunRow
    steps: list[Step]


# ---- 기준 목록 (GET /ref/*) ----

class Customer(Out):
    customer_id: str
    company_masked: str
    country: str
    tier: str


class Product(Out):
    product_code: str
    product_name: str
    family: str | None = None
    list_price_usd: Num | None = None
    std_lead_time_weeks: int | None = None
    lifecycle_status: str | None = None
    warranty_months: int | None = None


class Department(Out):
    dept_code: str
    dept_name_ko: str
    dept_name_en: str
    level: str | None = None
    scope: str | None = None


class Agent(Out):
    name: str
    dept: str
    demo: bool


# ---- 시연용 불러오기 (GET /gold/tickets/{id}) ----

class Loaded(Out):
    source_ticket_id: str
    channel: str
    customer_id: str
    product_code: str | None
    language: str
    inquiry_body: str
    received_at_utc: datetime | None
    gold_set: bool


# ---- 나의 업무 현황 (GET /me/workload, FR-047) ----

class WorkRow(Out):
    sub_ticket_id: str
    ticket_id: str
    seq: int
    inquiry_count: int
    company_masked: str
    customer_tier: str
    priority: str | None
    status: str


class RiskRow(WorkRow):
    alerts: list[str]
    remaining_h: Num | None


class DraftRow(WorkRow):
    message_id: int
    message_type: str
    created_at_utc: datetime
    has_check: bool


class WaitingCustomerRow(WorkRow):
    requested_at_utc: datetime | None
    reminder_sent: bool
    elapsed_h: float | None
    remind_at_h: float
    close_at_h: float


class WaitingEscalationRow(WorkRow):
    escalated_to: str
    escalated_at_utc: datetime | None
    elapsed_h: float | None


class Tiles(Out):
    drafts: int
    risks: int
    waiting_customer: int
    waiting_escalation: int


class Today(Out):
    sent: int
    escalated: int
    adjusted: int


class Workload(Out):
    dept: str | None
    agent: str | None
    scope: str | None
    as_of: datetime
    message: str | None
    tiles: Tiles
    risks: list[RiskRow]
    drafts: list[DraftRow]
    waiting_customer: list[WaitingCustomerRow]
    waiting_escalation: list[WaitingEscalationRow]
    today: Today
    sla_unset: int
    empty: dict[str, str]


# ---- 통화 받아쓰기 (POST /calls/transcribe, /calls/note-draft, FR-050) ----

class Usage(Out):
    call: str
    prompt_version: str | None
    attempts: int | None
    input_tokens: int | None
    output_tokens: int | None


class CallProvided(Out):
    field_code: str
    label: str
    value: str | None
    utterance_no: int | None
    found: bool
    message: str | None


class CallNote(Out):
    note_en: str | None
    note_error: str | None
    summary_en: str | None
    urgency: str | None
    provided: list[CallProvided]
    mask_count: int
    usage: list[Usage]


class Utterance(Out):
    no: int
    speaker: str
    start_sec: float
    end_sec: float
    text: str


class CallGap(Out):
    start_sec: float
    end_sec: float
    reason: str


class CallResult(CallNote):
    duration_sec: float
    utterances: list[Utterance]
    gaps: list[CallGap]


# ---- 고객 관리 (변경 add-customer-views, FR 초안 01) ----


class CustomerRow(Out):
    customer_id: str
    company_masked: str
    country: str
    tier: str
    segment: str
    ticket_count: int
    open_count: int
    last_received_at: datetime | None


class CustomerRows(Out):
    total: int
    page: int
    size: int
    tier_counts: dict[str, int]
    rows: list[CustomerRow]


class CustomerHistoryRow(Out):
    sub_ticket_id: str
    ticket_id: str
    seq: int
    inquiry_count: int
    source_ticket_id: str | None
    received_at_utc: datetime
    category_code: str | None
    product_code: str | None
    priority: str | None
    status: str
    alerts: list[str]


class CustomerDetail(Out):
    customer_id: str
    company_masked: str
    country: str
    tier: str
    segment: str
    account_since: date | None
    last_contact_email: str | None
    last_language: str | None
    ticket_count: int
    open_count: int
    alert_count: int
    as_of: datetime
    history: list[CustomerHistoryRow]


class CountryRow(Out):
    country: str
    customer_count: int
    ticket_count: int
    open_count: int


# ---- 기준정보 보기 (변경 add-reference-views) ----

class DocumentRow(Out):
    doc_id: str
    title: str
    doc_type: str
    product_code: str | None = None
    family: str | None = None
    revision: str | None = None
    chars: int | None = None
    chunk_count: int


class DocumentSection(Out):
    chunk_id: str
    section_no: str | None = None
    section_title: str | None = None


class DocumentDetail(Out):
    doc_id: str
    title: str
    doc_type: str
    product_code: str | None = None
    family: str | None = None
    revision: str | None = None
    chars: int | None = None
    sections: list[DocumentSection]


class ProductSpec(Out):
    attribute: str
    value: str | None = None
    doc_id: str | None = None
    section: str | None = None


class FirmwareRow(Out):
    fw_version: str
    release_date: date | None = None
    is_latest: bool | None = None
    changes: str | None = None
    doc_id: str | None = None


class ProductDetail(Product):
    specs: list[ProductSpec]
    standards: list[str]
    certifications: list[str]
    firmware: list[FirmwareRow]


class RuleRows(Out):
    kind: Literal["priority", "routing", "required-info", "sla"]
    rows: list[Json]  # 칸이 종류마다 다르다(design 결정 3 표, 변경 add-api-response-models 결정 3)


# ---- 해결사례 직접 검색 (변경 add-case-search) ----

class CaseRow(Out):
    case_id: str
    ticket_id: str
    category_code: str | None
    product_code: str | None
    product_family: str | None
    error_code: str | None
    symptom: str | None
    resolution_result: str | None
    case_summary: str | None
    score: Num | None
    same_error_code: bool


class CaseRows(Out):
    rows: list[CaseRow]
    total: int
    notes: list[str]


class CaseDetail(Out):
    case_id: str
    ticket_id: str
    category_code: str | None
    product_code: str | None
    product_family: str | None
    error_code: str | None
    symptom: str | None
    initial_hypothesis: str | None
    root_cause: str | None
    diagnosis_method: str | None
    action_taken: str | None
    replacement_part: str | None
    onsite_visit: str | None
    resolution_result: str | None
    time_to_resolve_hours: str | None
    recurrence_prevention: str | None
    case_summary: str | None


# ---- 상담원 도우미 (변경 add-agent-assistant) ----

class AssistSource(Out):
    no: int
    chunk_id: str
    doc_id: str
    section_no: str
    title: str


class AssistAnswer(Out):
    found: bool
    answer: str
    sources: list[AssistSource]
    followups: list[str]
    notes: list[str]
