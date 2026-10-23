// 서버 API (기술 명세서 v1.4 §8-1, 화면 정의서 v2 부록 A).
// 타입은 backend/app/db/detail.py가 돌려주는 모양을 손으로 옮겼다(OpenAPI 생성은 하지 않음, 개발_결정_기록 C-45).

export interface Ticket {
  ticket_id: string;
  received_at_utc: string;
  channel: string;
  language: string;
  body_language: string | null;
  body_language_uncertain: boolean | null;
  customer_id: string;
  customer_tier: string;
  company_masked: string | null;
  country: string | null;
  source: string;
  source_ticket_id: string | null;
  gold_set: boolean;
  multi_yn: boolean;
  inquiry_subject: string | null; // 저장만, 처리에는 쓰지 않음
  inquiry_body: string;
  contact_name: string | null; // 보낸 사람 연락처 원문(FR-030 처리 1, 가-7)
  contact_email: string | null;
  contact_phone: string | null;
}

export interface Run {
  run_id: number;
  trigger: string;
  status: string | null; // null = 처리 중
  last_step: string | null;
}

export interface Candidate {
  doc_id: string;
  section: string;
  quote: string;
  score: number;
  chunk_id: string;
}

export interface Lookup {
  item: string;
  value: string | number;
  unit: string | null;
  source_table: string;
  source_key: string;
}

export interface RequiredItem {
  field: string;
  label: string;
  state: "provided" | "missing" | "blocking";
  value: string | null;
}

export interface EvidenceRow {
  id: string; // C-01, C-02, M-C-01, C-03, C-04, C-07, C-06, M-C-02
  label: string;
  result: string;
  evidence: string[];
  why: Record<string, unknown>;
  items?: RequiredItem[];
  candidates?: Candidate[];
  lookups?: Lookup[];
}

export interface Finding {
  kind: string;
  quote: string;
  reason: string;
}

export interface Mark {
  no: number;
  passed: boolean;
  state?: string | null; // ④ CHECK, ⑤ PASSED/FOUND/FAILED/STALE/null
  text: string | null;
  findings?: Finding[];
  full_text?: string;
  detail?: CheckDetail | null;
}

export interface CheckDetail {
  passed: boolean;
  bad_citations: string[];
  bad_numbers: string[];
  missing_labels?: string[];
}

export interface Draft {
  message_id: number;
  message_type: "INFO_REQUEST" | "FINAL_REPLY";
  message_status: "DRAFT" | "APPROVED";
  language: string;
  body: string;
  made_at_utc: string;
  superseded_at: string | null;
  gloss: { language: string; body: string; numbers_match: boolean | null; made_at_utc: string } | null;
  check: { passed_yn: boolean; detail: CheckDetail } | null;
  verify: { passed_yn: boolean; detail: Record<string, unknown> } | null;
  sent: { message_id: number; sent_at_utc: string; sent_by_name: string; edited_yn: boolean; override_check: boolean; body: string } | null;
  review_marks: { marks: Mark[]; summary: string };
}

// 상세 전체판 (FR-030, 변경 add-ticket-detail-full)
export interface Field {
  field: string;
  label: string;
  value_raw: string | null;
  value_norm: string | null;
  span_start: number | null;
  span_end: number | null;
  source: "INQUIRY" | "CUSTOMER_REPLY" | "AGENT";
}
export interface EditMark { from: unknown; to: unknown; by: string | null; at: string | null }
export interface Sla {
  fr_target_h: number | null;
  res_target_h: number | null;
  fr_elapsed_h: number | null;
  fr_status: string | null;
  wait_h: number | null;
  res_elapsed_h: number | null;
  res_status: string | null;
  remaining_h: number | null;
  notes: string[];
}
export interface Adjustment {
  from_priority: string;
  to_priority: string;
  from_fr_target_h: number | null;
  from_res_target_h: number | null;
  to_fr_target_h: number | null;
  to_res_target_h: number | null;
  reason_kind: string;
  reason: string;
  adjusted_by: string;
  adjusted_at_utc: string;
}

export interface SubTicket {
  fields: Field[];
  edits: Record<string, EditMark>;
  product_name: string | null;
  version: number;
  state: { status: string; final_action: string | null; priority: string | null; priority_adjusted_by_agent: boolean };
  sla: Sla | null;
  adjustments: Adjustment[];
  alerts: { alert_type: string; raised_at_utc: string; cleared_at_utc: string | null }[];
  sub_ticket: Record<string, unknown> & {
    sub_ticket_id: string;
    seq: number;
    category_code: string | null;
    urgency_flag: string;
    product_code: string | null;
    return_kind: string | null;
    assigned_dept: string | null;
    required_info: string[];
    status: string;
    priority: string | null;
    priority_rule_id: string | null;
    missing_blocking_info: string[];
    pipeline_error: string | null;
    evidence_json: Candidate[];
  };
  checks: { check_type: string; flag: string | null }[];
  other_flags: string[];
  evidence_rows: EvidenceRow[];
  drafts: Draft[];
}

export interface Detail {
  ticket: Ticket;
  run: Run | null;
  processing: boolean;
  can_retry: boolean; // [다시 시도]: 마지막 처리가 실패했고 도는 중이 아님(AC-001-4)
  can_reprocess: boolean; // [다시 처리]: 도는 중이 아니고 종료만 남은 티켓이 아님(FR-030 처리 5)
  summary: { status: string; rep_sub_ticket_id: string; rep_res_status: string | null; rep_remaining_h: number | null;
             open_count: number; inquiry_count: number } | null;
  messages: { message_id: number; seq: number | null; sender: string; message_type: string; sent_at_utc: string;
              language: string; body: string }[];
  sub_tickets: SubTicket[];
}

export interface TimelineItem {
  kind: "STATUS" | "MESSAGE" | "PRIORITY" | "ALERT_RAISED" | "ALERT_CLEARED";
  at: string;
  seq: number | null;
  id: number;
  [key: string]: unknown;
}
export interface RunRow {
  run_id: number;
  sub_ticket_id: string | null;
  trigger: string;
  status: string | null;
  last_step: string | null;
  started_at_utc: string;
  step_count: number;
  failed_steps: number;
}
export interface EditInput {
  category_code?: string;
  urgency_flag?: string;
  product_code?: string;
  return_kind?: string;
  received_fields?: { field: string; value: string | null }[];
  expected_version?: number;
}
export interface AdjustPreview {
  to_sla_id: string | null;
  from_fr_target_h: number | null;
  from_res_target_h: number | null;
  to_fr_target_h: number | null;
  to_res_target_h: number | null;
  becomes_breached: boolean;
  version: number;
}

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  doc_title: string;
  section_no: string;
  section_title: string;
  text: string;
}

export interface SendIssue {
  kind: string;
  text: string;
  items: string[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public body: unknown) {
    super(message);
  }
}

const AGENT_KEY = "cs-agent-id";

export function agentId(): string {
  try {
    return localStorage.getItem(AGENT_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveAgentId(id: string): void {
  try {
    localStorage.setItem(AGENT_KEY, id);
  } catch {
    // 브라우저 저장을 못 쓰면 이번 화면에서만 쓴다
  }
}

// 머리 막대 부서·기준 시각(화면 정의서 v1 SCR-00-03·04). 브라우저에 기억한다.
const DEPT_KEY = "cs-agent-dept";
const AS_OF_KEY = "cs-as-of";
export const SNAPSHOT = "2026-09-30T23:59:00Z"; // README 스냅샷 시각
export type AsOfMode = "now" | "snapshot";

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // 브라우저 저장을 못 쓰면 이번 화면에서만 쓴다
  }
}

export const agentDept = () => read(DEPT_KEY);
export const saveAgentDept = (dept: string) => write(DEPT_KEY, dept);
export const asOfMode = (): AsOfMode => (read(AS_OF_KEY) === "snapshot" ? "snapshot" : "now");
export const saveAsOfMode = (mode: AsOfMode) => write(AS_OF_KEY, mode);

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-Agent-Id": agentId(), "X-Agent-Dept": agentDept() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail
      : data?.detail?.message ?? `요청 실패(${res.status})`;
    throw new ApiError(res.status, detail, data);
  }
  return data as T;
}

// 접수 시뮬레이터 (화면 정의서 v1 SCR-01, 기술 명세서 §8-1)
export interface Customer { customer_id: string; company_masked: string; country: string; tier: string }
export interface Product { product_code: string; product_name: string }
export interface Loaded {
  source_ticket_id: string;
  channel: string;
  customer_id: string;
  product_code: string | null;
  language: string;
  inquiry_body: string;
  received_at_utc: string | null;
  gold_set: boolean;
}
export interface TicketInput {
  channel: string;
  customer_id: string;
  product_code: string | null;
  language: string;
  inquiry_subject: string | null;
  inquiry_body: string;
  received_at_utc: string | null;
  source_ticket_id: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
}
export interface FieldError { field: string; message: string }

/** 접수 400의 항목별 오류(detail.errors). 없으면 빈 목록 */
export function fieldErrors(e: unknown): FieldError[] {
  const body = e instanceof ApiError ? (e.body as { detail?: { errors?: FieldError[] } } | null) : null;
  return body?.detail?.errors ?? [];
}

// 접수함 (화면 정의서 v1 SCR-02, 기술 명세서 §8-1 GET /tickets)
export interface Department { dept_code: string; dept_name_ko: string; dept_name_en: string }
export interface InboxRow {
  sub_ticket_id: string;
  ticket_id: string;
  seq: number;
  inquiry_count: number;
  received_at_utc: string;
  channel: string;
  language: string;
  customer_id: string;
  company_masked: string;
  customer_tier: string | null;
  product_code: string | null;
  product_name: string | null;
  category_code: string | null;
  urgency_flag: string | null;
  priority: string | null;
  priority_adjusted: boolean | null;
  assigned_dept: string | null;
  escalated_to: string | null;
  escalated_in_from: string | null;
  status: string;
  fr_status: string | null;
  res_status: string | null;
  remaining_h: string | number | null;
  alerts: string[];
  needs_info: boolean;
  has_unsent_draft: boolean;
  reminder_sent: boolean;
}
// 나의 업무 현황 (FR-047, §8-1 GET /me/workload, §8-3)
export interface WorkRow {
  sub_ticket_id: string;
  ticket_id: string;
  seq: number;
  inquiry_count: number;
  company_masked: string | null;
  customer_tier: string | null;
  priority: string | null;
  status: string;
}
export interface Workload {
  dept: string | null;
  agent: string | null;
  scope: "mine" | "dept";
  as_of: string;
  message: string | null;
  tiles: { drafts: number; risks: number; waiting_customer: number; waiting_escalation: number };
  risks: (WorkRow & { alerts: string[]; remaining_h: string | number | null })[];
  drafts: (WorkRow & { message_id: number; message_type: string; created_at_utc: string; has_check: boolean })[];
  waiting_customer: (WorkRow & { requested_at_utc: string | null; elapsed_h: number | null; reminder_sent: boolean;
    remind_at_h: number; close_at_h: number })[];
  waiting_escalation: (WorkRow & { escalated_to: string; escalated_at_utc: string | null; elapsed_h: number | null })[];
  today: { sent: number; escalated: number; adjusted: number };
  sla_unset: number;
  empty: Record<"drafts" | "risks" | "waiting_customer" | "waiting_escalation", string>;
}

export interface Inbox {
  dept: string | null;
  as_of: string;
  page: number;
  size: number;
  counts: { total: number; alert: number; needs_info: number; has_draft: number; waiting: number };
  rows: InboxRow[];
  message: string | null;
}

export const api = {
  timeline: (id: string) => call<TimelineItem[]>("GET", `/tickets/${encodeURIComponent(id)}/timeline`),
  runs: (id: string) => call<{ runs: RunRow[] }>("GET", `/tickets/${encodeURIComponent(id)}/runs`),
  steps: (runId: number) => call<{ steps: { step_name: string; result: string | null; error: string | null }[] }>(
    "GET", `/runs/${runId}/steps`),
  edit: (subId: string, data: EditInput) => call<{ processing: boolean }>("PATCH", `/sub-tickets/${encodeURIComponent(subId)}`, data),
  adjustPreview: (subId: string, p: string) =>
    call<AdjustPreview>("GET", `/sub-tickets/${encodeURIComponent(subId)}/priority?new_priority=${p}`),
  adjust: (subId: string, data: { new_priority: string; reason_kind: string; reason_text: string; confirm_breach: boolean;
                                  expected_version: number }) =>
    call<unknown>("POST", `/sub-tickets/${encodeURIComponent(subId)}/priority`, data),
  reply: (id: string, data: { body: string; language: string; received_at: string | null; target_sub_ticket_ids: string[] | null }) =>
    call<{ processing: boolean }>("POST", `/tickets/${encodeURIComponent(id)}/replies`, data),
  departments: () => call<Department[]>("GET", "/ref/departments"),
  inbox: (query: URLSearchParams) => call<Inbox>("GET", `/tickets?${query.toString()}`),
  workload: (query: URLSearchParams) => call<Workload>("GET", `/me/workload?${query.toString()}`),
  customers: (q: string) => call<Customer[]>("GET", `/ref/customers?q=${encodeURIComponent(q)}`),
  products: () => call<Product[]>("GET", "/ref/products"),
  load: (id: string) => call<Loaded>("GET", `/gold/tickets/${encodeURIComponent(id)}`),
  intake: (data: TicketInput) => call<{ ticket_id: string; processing: boolean }>("POST", "/tickets", data),
  reprocess: (id: string) => call<{ ticket_id: string; processing: boolean }>("POST", `/tickets/${encodeURIComponent(id)}/reprocess`),
  ticket: (id: string) => call<Detail>("GET", `/tickets/${encodeURIComponent(id)}`),
  chunk: (chunkId: string) => call<Chunk>("GET", `/chunks/${encodeURIComponent(chunkId)}`),
  save: (draftId: number, body: string) => call<{ gloss: boolean }>("PUT", `/messages/${draftId}`, { body }),
  gloss: (draftId: number) => call<{ gloss: boolean }>("POST", `/messages/${draftId}/gloss`),
  verify: (draftId: number) => call<{ state: string; mark: string }>("POST", `/messages/${draftId}/verify`),
  send: (draftId: number, finalBody: string, override: boolean) =>
    call<{ sent_message_id: number; override_check: boolean; notes: string[] }>(
      "POST", `/messages/${draftId}/send`, { final_body: finalBody, override_check: override }),
};
