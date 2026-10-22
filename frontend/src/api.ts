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
}

export interface Run {
  run_id: number;
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

export interface SubTicket {
  sub_ticket: Record<string, unknown> & {
    sub_ticket_id: string;
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
  sub_tickets: SubTicket[];
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

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-Agent-Id": agentId() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : `요청 실패(${res.status})`;
    throw new ApiError(res.status, detail, data);
  }
  return data as T;
}

export const api = {
  ticket: (id: string) => call<Detail>("GET", `/tickets/${encodeURIComponent(id)}`),
  chunk: (chunkId: string) => call<Chunk>("GET", `/chunks/${encodeURIComponent(chunkId)}`),
  save: (draftId: number, body: string) => call<{ gloss: boolean }>("PUT", `/messages/${draftId}`, { body }),
  gloss: (draftId: number) => call<{ gloss: boolean }>("POST", `/messages/${draftId}/gloss`),
  verify: (draftId: number) => call<{ state: string; mark: string }>("POST", `/messages/${draftId}/verify`),
  send: (draftId: number, finalBody: string, override: boolean) =>
    call<{ sent_message_id: number; override_check: boolean; notes: string[] }>(
      "POST", `/messages/${draftId}/send`, { final_body: finalBody, override_check: override }),
};
