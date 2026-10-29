// 서버 API (기술 명세서 v1.4 §8-1, 화면 정의서 v2 부록 A).
// 응답 타입은 서버 계약(openapi.json)에서 만든 api.gen.ts를 쓴다(변경 add-api-response-models, C-45 바꿈).
// 계약을 다시 만들려면: cd backend && python ../jobs/export_openapi.py, 그다음 frontend에서 npm run gen:api.
// 서버가 칸을 정하지 않은 값(근거 줄의 candidates·lookups, 고장 진단·이관 후보, 검사 detail)만 아래에서 손으로 좁힌다.
import type { components } from "./api.gen";

type S = components["schemas"];

export type Ticket = S["Ticket"];
export type Run = S["Run"];
export type RequiredItem = S["RequiredItem"] & { state: "provided" | "missing" | "blocking" };
export type EvidenceRow = Omit<S["EvidenceRow"], "items" | "candidates" | "lookups"> & {
  items?: RequiredItem[] | null;
  candidates?: Candidate[] | null;
  lookups?: Lookup[] | null;
};
export type Mark = Omit<S["Mark"], "findings" | "detail"> & { findings?: Finding[] | null; detail?: CheckDetail | null };
export type Draft = Omit<S["Draft"], "check" | "review_marks"> & {
  check: { passed_yn: boolean | null; detail: CheckDetail } | null;
  review_marks: { marks: Mark[]; summary: string };
};
export type Field = S["Field"];
export type Sla = S["Sla"];
export type Adjustment = S["Adjustment"];
export type DeptReply = S["DeptReply"];
export type DeptMail = S["DeptMail"];
export type SubTicket = Omit<S["SubTicket"], "sub_ticket" | "evidence_rows" | "drafts" | "diagnosis" | "escalation" | "edits"> & {
  sub_ticket: Omit<S["SubTicketRow"], "evidence_json"> & { evidence_json: Candidate[] }; // 열은 NOT NULL DEFAULT []
  evidence_rows: EvidenceRow[];
  drafts: Draft[];
  diagnosis?: Diagnosis | null; // 고장 진단(FR-018). 고장 계열이 아니면 null
  escalation?: Escalation | null; // 이관 후보(FR-020). 표시만 하고 상태는 그대로
  edits: Record<string, EditMark>;
};
export type Detail = Omit<S["Detail"], "sub_tickets"> & { sub_tickets: SubTicket[] };
export type TimelineItem = S["TimelineItem"] & Record<string, unknown>; // 종류별 칸은 계약에 없다(design 결정 3)
export type RunRow = S["RunListRow"];
export type AdjustPreview = S["AdjustPreview"];
export type Chunk = S["Chunk"];
export type Utterance = S["Utterance"];
export type CallGap = S["CallGap"];
export type CallProvided = S["CallProvided"];
export type CallNote = S["CallNote"];
export type CallResult = S["CallResult"];
export type Customer = S["Customer"];
export type Product = S["Product"];
export type Loaded = S["Loaded"];
export type Department = S["Department"];
export type Agent = S["Agent"];
export type InboxRow = S["InboxRow"];
type WorkBase = Omit<S["RiskRow"], "alerts" | "remaining_h">;
/** 나의 업무 현황 네 영역의 행. 공통 칸은 꼭 있고, 영역마다 다른 칸은 있을 수도 없을 수도 있다. */
export type WorkRow = WorkBase &
  Partial<Omit<S["RiskRow"] & S["DraftRow"] & S["WaitingCustomerRow"] & S["WaitingEscalationRow"], keyof WorkBase>>;
export type Workload = S["Workload"];
export type Inbox = S["Inbox"];



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



export interface Finding {
  kind: string;
  quote: string;
  reason: string;
}


export interface CheckDetail {
  passed: boolean;
  bad_citations: string[];
  bad_numbers: string[];
  missing_labels?: string[];
}


// 상세 전체판 (FR-030, 변경 add-ticket-detail-full)
export interface EditMark { from: unknown; to: unknown; by: string | null; at: string | null }




export interface EscalationCandidate {
  rule_id: string;
  dept: string;
  reason: string;
  reason_code: string;
  team: boolean;
}

export interface Escalation {
  escalation_candidates: EscalationCandidate[];
  escalation_condition: string | null;
  notes: string[];
}

export interface FaultCandidate {
  fault_id: string;
  cause: string | null;
  check: string | null;
  action: string | null;
  onsite_required: boolean | null;
  replace_required: boolean | null;
  method: "EXACT" | "SYMPTOM" | null;
  score: number | null;
}

export interface Diagnosis {
  fault_candidates: FaultCandidate[];
  method: "EXACT" | "SYMPTOM" | null;
  notes: string[];
}


export interface EditInput {
  category_code?: string;
  urgency_flag?: string;
  product_code?: string;
  return_kind?: string;
  received_fields?: { field: string; value: string | null }[];
  expected_version?: number;
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

/** multipart 요청(통화 녹음 올리기). Content-Type은 브라우저가 경계값과 함께 붙인다. */
async function callForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", headers: { "X-Agent-Id": agentId(), "X-Agent-Dept": agentDept() }, body: form });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.detail?.message ?? `요청 실패(${res.status})`, data);
  return data as T;
}

// 통화 받아쓰기 (명세서 FR-050, 기술 명세서 v1.4.1 §12-5). 저장하지 않는다(D36)

// 접수 시뮬레이터 (화면 정의서 v1 SCR-01, 기술 명세서 §8-1)
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
// 나의 업무 현황 (FR-047, §8-1 GET /me/workload, §8-3)


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
  escalate: (subId: string, data: { dept: string; reason_code: string; memo: string; expected_version: number }) =>
    call<unknown>("POST", `/sub-tickets/${encodeURIComponent(subId)}/escalate`, data),
  deptReply: (subId: string, body: string) =>
    call<{ processing: boolean }>("POST", `/sub-tickets/${encodeURIComponent(subId)}/dept-reply`, { body }),
  deptMail: (subId: string, body: string) =>
    call<{ message_id: number }>("POST", `/sub-tickets/${encodeURIComponent(subId)}/dept-mail`, { body }),
  departments: () => call<Department[]>("GET", "/ref/departments"),
  agents: () => call<Agent[]>("GET", "/ref/agents"),
  inbox: (query: URLSearchParams) => call<Inbox>("GET", `/tickets?${query.toString()}`),
  workload: (query: URLSearchParams) => call<Workload>("GET", `/me/workload?${query.toString()}`),
  customers: (q: string) => call<Customer[]>("GET", `/ref/customers?q=${encodeURIComponent(q)}`),
  products: () => call<Product[]>("GET", "/ref/products"),
  load: (id: string) => call<Loaded>("GET", `/gold/tickets/${encodeURIComponent(id)}`),
  transcribe: (file: File, customerId: string, language: string, productCode: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("customer_id", customerId);
    form.append("language", language);
    form.append("product_code", productCode);
    return callForm<CallResult>("/calls/transcribe", form);
  },
  noteDraft: (utterances: Utterance[], language: string, productCode: string | null) =>
    call<CallNote>("POST", "/calls/note-draft", { utterances, language, product_code: productCode }),
  intake: (data: TicketInput) => call<S["Accepted"]>("POST", "/tickets", data),
  reprocess: (id: string) => call<{ ticket_id: string; processing: boolean }>("POST", `/tickets/${encodeURIComponent(id)}/reprocess`),
  ticket: (id: string, asOf: string | null = null) =>
    call<Detail>("GET", `/tickets/${encodeURIComponent(id)}${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""}`),
  chunk: (chunkId: string) => call<Chunk>("GET", `/chunks/${encodeURIComponent(chunkId)}`),
  save: (draftId: number, body: string) => call<{ gloss: boolean }>("PUT", `/messages/${draftId}`, { body }),
  gloss: (draftId: number) => call<{ gloss: boolean }>("POST", `/messages/${draftId}/gloss`),
  verify: (draftId: number) => call<{ state: string; mark: string }>("POST", `/messages/${draftId}/verify`),
  send: (draftId: number, finalBody: string, override: boolean) =>
    call<{ sent_message_id: number; override_check: boolean; notes: string[] }>(
      "POST", `/messages/${draftId}/send`, { final_body: finalBody, override_check: override }),
};
