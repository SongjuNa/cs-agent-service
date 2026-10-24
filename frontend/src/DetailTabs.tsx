// 상세 전체판 탭 3개: 고객이 보낸 것(L), 시스템이 판단한 것(C, 하위 문의마다 구역), 이력(B)
// (화면 정의서 v1 SCR-03 L·C·B, 명세서 FR-030 처리 1·2·4·6, 변경 add-ticket-detail-full)
import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type Detail, type Diagnosis, type Escalation, type EscalationCandidate, type EvidenceRow, type FaultCandidate, type Field, type RunRow, type SubTicket, type TimelineItem } from "./api";
import { EvidencePanel } from "./EvidencePanel";
import type { SourceTarget } from "./Popups";

const CATEGORIES = ["COMPLIANCE", "DEFECT", "FW_UPDATE", "INSTALL", "MANUAL", "ORDER_LEAD", "QUOTE", "RETURN", "TECH_SPEC", "WARRANTY"];
const URGENCIES = ["NONE", "COMMISSION", "DEADLINE", "PROD_IMPACT", "SAFETY", "SITE_DOWN"];
const FOLD = 600; // 이보다 긴 원문은 접는다(FR-030 예외 5행). 길이는 구현 선택

const STATUS_MARK: Record<string, string> = {
  NEW: "○", IN_PROGRESS: "▶", WAITING_CUSTOMER: "⏸", ESCALATED: "↗", RESOLVED: "✓", CLOSED: "■",
};
const STATUS_CLASS: Record<string, string> = {
  NEW: "st-new", IN_PROGRESS: "st-progress", WAITING_CUSTOMER: "st-waiting", ESCALATED: "st-escalated",
  RESOLVED: "st-resolved", CLOSED: "st-closed",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${STATUS_CLASS[status] ?? ""}`}>{STATUS_MARK[status] ?? ""} {status}</span>;
}

const hours = (h: number | null | undefined) => (h === null || h === undefined ? "—" : `${Number(h).toFixed(1)}h`);

/** SLA 두 시계(FR-026 출력, SCR-03 C-06). 대기 중이면 해결 시계 "멈춤" */
export function Clocks({ sub }: { sub: SubTicket }) {
  const sla = sub.sla;
  if (!sla || sla.fr_target_h === null || sla.res_target_h === null) return <span className="gray">SLA 미정</span>;
  const cls = (s: string | null) => (s === "BREACHED" ? "bad" : s === "AT_RISK" ? "gold" : "ok");
  const waiting = sub.state.status === "WAITING_CUSTOMER";
  return (
    <span className="clocks">
      <span className={cls(sla.fr_status)}>1차 응답 {hours(sla.fr_elapsed_h)} / {sla.fr_target_h}h {sla.fr_status === "MET" ? "✓" : sla.fr_status ?? ""}</span>
      {" · "}
      <span className={waiting ? "gray" : cls(sla.res_status)}>
        해결 {hours(sla.res_elapsed_h)} / {sla.res_target_h}h {waiting ? "⏸ 멈춤" : sla.res_status ?? ""}
      </span>
    </span>
  );
}

/** 원문에서 추출 값 위치를 찾는다. span이 있으면 그것, 없으면 값 글자를 찾는다(C-109) */
function marks(body: string, fields: Field[]): { start: number; end: number; label: string }[] {
  const out: { start: number; end: number; label: string }[] = [];
  for (const f of fields) {
    let start = f.span_start ?? -1;
    let end = f.span_end ?? -1;
    if (start < 0 || end <= start) {
      const value = (f.value_raw ?? "").trim();
      if (value.length < 2) continue;
      start = body.toLowerCase().indexOf(value.toLowerCase());
      end = start + value.length;
    }
    if (start >= 0 && !out.some((m) => start < m.end && end > m.start)) out.push({ start, end, label: f.label });
  }
  return out.sort((a, b) => a.start - b.start);
}

function Highlighted({ body, fields }: { body: string; fields: Field[] }) {
  const parts: ReactNode[] = [];
  let at = 0;
  for (const m of marks(body, fields)) {
    parts.push(body.slice(at, m.start));
    parts.push(<mark key={m.start} className="extract" title={m.label}>{body.slice(m.start, m.end)}</mark>);
    at = m.end;
  }
  parts.push(body.slice(at));
  return <>{parts}</>;
}

export function CustomerTab({ detail }: { detail: Detail }) {
  const t = detail.ticket;
  const [open, setOpen] = useState(t.inquiry_body.length <= FOLD);
  const fields = detail.sub_tickets.flatMap((s) => s.fields.filter((f) => f.source === "INQUIRY"));
  const body = open ? t.inquiry_body : `${t.inquiry_body.slice(0, FOLD)}…`;
  const replies = detail.messages.filter((m) => m.message_type === "CUSTOMER_REPLY" || m.message_type === "ESCALATION_NOTE");
  return (
    <section className="customer">
      <table className="kv">
        <tbody>
          <tr><th>제목</th><td>{t.inquiry_subject ?? "—"} <span className="muted small">처리에는 쓰지 않음</span></td></tr>
          <tr><th>채널</th><td>{t.channel}{t.channel === "PHONE" && <span className="chip">영어 메모, 답장은 {t.language}</span>}</td></tr>
          <tr><th>언어</th><td>고객 언어 {t.language} / 본문 언어 {t.body_language ?? "—"}
            {t.body_language_uncertain && <span className="gray"> ? 본문 언어 판정 불확실</span>}</td></tr>
          <tr><th>고객</th><td>{t.company_masked ?? t.customer_id} · {t.customer_tier} · {t.country ?? ""}</td></tr>
          <tr><th>제품</th><td>{detail.sub_tickets.map((s) => s.sub_ticket.product_code ?? "제품 미확정").join(", ")}</td></tr>
          <tr><th>보낸 사람</th><td>{[t.contact_name, t.contact_email, t.contact_phone].filter(Boolean).join(" · ") || "—"}</td></tr>
        </tbody>
      </table>
      <h4>원문</h4>
      <pre className="draft-body"><Highlighted body={body} fields={open ? fields : []} /></pre>
      {t.inquiry_body.length > FOLD && (
        <button type="button" className="link" onClick={() => setOpen(!open)}>{open ? "접기" : "펼치기"}</button>
      )}
      {fields.length > 0 && <p className="small muted">밑줄 = 시스템이 원문에서 뽑은 값(마우스를 올리면 항목 이름)</p>}
      {replies.length > 0 && (
        <>
          <h4>고객 회신</h4>
          {replies.map((m) => (
            <div key={m.message_id} className="card">
              <div className="small muted">{m.sent_at_utc.replace("T", " ").slice(0, 16)} UTC · {m.language}{m.seq ? ` · 문의 ${m.seq}` : ""}</div>
              <pre className="draft-body">{m.body}</pre>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

function Edited({ sub, name }: { sub: SubTicket; name: string }) {
  const e = sub.edits[name];
  return e ? <span className="chip human" title={`${String(e.from ?? "—")} → ${String(e.to)} (${e.by ?? ""})`}>상담원 수정</span> : null;
}

function EditControls({ sub, locked, onSave }: {
  sub: SubTicket; locked: boolean; onSave: (data: Record<string, unknown>) => Promise<void>;
}) {
  const st = sub.sub_ticket;
  const [category, setCategory] = useState(st.category_code ?? "");
  const [urgency, setUrgency] = useState(st.urgency_flag);
  const [product, setProduct] = useState(st.product_code ?? "");
  const [returnKind, setReturnKind] = useState(st.return_kind ?? "");
  const [products, setProducts] = useState<{ product_code: string; product_name: string }[]>([]);
  useEffect(() => { api.products().then(setProducts).catch(() => setProducts([])); }, []);

  const changed: Record<string, unknown> = {};
  if (category && category !== st.category_code) changed.category_code = category;
  if (urgency !== st.urgency_flag) changed.urgency_flag = urgency;
  if (product && product !== st.product_code) changed.product_code = product;
  if (returnKind && returnKind !== st.return_kind) changed.return_kind = returnKind;

  return (
    <div className="edit-row">
      <label>유형 <Edited sub={sub} name="category_code" />
        <select value={category} disabled={locked} onChange={(e) => setCategory(e.target.value)}>
          {!st.category_code && <option value="">유형을 정하지 못함. 직접 선택</option>}
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>긴급도 <Edited sub={sub} name="urgency_flag" />
        <select value={urgency} disabled={locked} onChange={(e) => setUrgency(e.target.value)}>
          {URGENCIES.map((u) => <option key={u}>{u}</option>)}
        </select>
      </label>
      <label>제품 <Edited sub={sub} name="product_code" />
        <select value={product} disabled={locked} onChange={(e) => setProduct(e.target.value)} title={sub.product_name ?? undefined}>
          {!st.product_code && <option value="">제품 확인 필요. 선택</option>}
          {products.map((p) => <option key={p.product_code} value={p.product_code}>{p.product_code}</option>)}
        </select>
      </label>
      {(category || st.category_code) === "RETURN" && (
        <label>반품 구분 <Edited sub={sub} name="return_kind" />
          <select value={returnKind} disabled={locked} onChange={(e) => setReturnKind(e.target.value)}>
            <option value="">{st.return_kind === "UNKNOWN" ? "확인 필요" : "—"}</option>
            <option value="DEFECT">불량</option>
            <option value="NON_DEFECT">비불량</option>
          </select>
        </label>
      )}
      <button type="button" disabled={locked || !Object.keys(changed).length} onClick={() => void onSave(changed)}>
        저장하고 다시 계산
      </button>
    </div>
  );
}

function RequiredChecklist({ sub, locked, onReceived }: {
  sub: SubTicket; locked: boolean; onReceived: (field: string, value: string) => Promise<void>;
}) {
  const row = sub.evidence_rows.find((r) => r.id === "C-07");
  const [value, setValue] = useState<Record<string, string>>({});
  if (!row?.items?.length) return null;
  return (
    <ul className="checklist">
      {row.items.map((item) => (
        <li key={item.field} className={item.state === "blocking" ? "bad" : item.state === "missing" ? "gray" : "ok"}>
          {item.state === "provided" ? "✓" : item.state === "blocking" ? "!" : "–"} {item.label}
          {item.state === "provided" ? <span className="muted"> {item.value ?? ""}</span>
            : <span className="muted"> {item.state === "blocking" ? "막는 항목" : "빠짐"}</span>}
          {sub.fields.some((f) => f.field === item.field && f.source === "AGENT") && <span className="chip human">상담원 입력</span>}
          {item.state !== "provided" && !locked && (
            <span className="received">
              <input placeholder="받은 값(선택)" value={value[item.field] ?? ""}
                     onChange={(e) => setValue({ ...value, [item.field]: e.target.value })} />
              <button type="button" onClick={() => void onReceived(item.field, value[item.field] ?? "")}>받았음</button>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

const METHOD: Record<string, string> = { EXACT: "정확 일치", SYMPTOM: "증상 검색" };

function FaultLine({ c }: { c: FaultCandidate }) {
  return (
    <div className="fault">
      <b>{c.fault_id}</b> <span className="chip">{METHOD[c.method ?? ""] ?? "—"} {c.score !== null ? c.score.toFixed(2) : ""}</span>
      {c.onsite_required && <span className="chip bad">현장 출동 필요</span>}
      {c.replace_required && <span className="chip bad">교체 필요</span>}
      <dl className="fault-body">
        <dt>원인</dt><dd>{c.cause ?? "—"}</dd>
        <dt>점검</dt><dd>{c.check ?? "—"}</dd>
        <dt>조치</dt><dd>{c.action ?? "—"}</dd>
      </dl>
    </div>
  );
}

/** 고장 진단 후보(화면 정의서 v1 SCR-03 C-08): 1순위 크게, 2·3순위 접힘. 상담원 참고용(FR-018 처리 5). */
function DiagnosisPanel({ diagnosis }: { diagnosis: Diagnosis }) {
  const [first, ...rest] = diagnosis.fault_candidates;
  return (
    <div className="card diagnosis">
      <header><h5>고장 진단 후보</h5><span className="muted small">참고용, 초안에는 쓰지 않음</span>
        {diagnosis.notes.map((n) => <span key={n} className="chip gray">{n}</span>)}
      </header>
      {first ? <FaultLine c={first} /> : <p className="muted">진단 없음</p>}
      {rest.length > 0 && (
        <details>
          <summary>다른 후보 {rest.length}개</summary>
          {rest.map((c) => <FaultLine key={c.fault_id} c={c} />)}
        </details>
      )}
    </div>
  );
}

/** 이관 후보(화면 정의서 v1 SCR-03 C-09, FR-020 출력): 부서별 한 줄, 팀 규칙 표시, 버튼 없음. */
function EscalationPanel({ escalation }: { escalation: Escalation }) {
  const byDept = new Map<string, EscalationCandidate[]>();
  for (const c of escalation.escalation_candidates) byDept.set(c.dept, [...(byDept.get(c.dept) ?? []), c]);
  return (
    <div className="card escalation">
      <header><h5>이관 후보</h5><span className="muted small">확정은 상담원이 함</span>
        {escalation.notes.map((n) => <span key={n} className="chip gray">{n}</span>)}
      </header>
      {byDept.size === 0 ? (
        <p>없음{escalation.escalation_condition && <span className="muted"> — 이관 조건: {escalation.escalation_condition}</span>}</p>
      ) : (
        <ul className="escalation-lines">
          {[...byDept].map(([dept, rules]) => (
            <li key={dept}>
              <b>{dept}</b> —{" "}
              {rules.map((c, i) => (
                <span key={c.rule_id}>{i > 0 && ", "}{c.rule_id} ({c.reason}){c.team && <span className="chip human">팀 규칙</span>}</span>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** "부서 회신" 영역(FR-030 처리 2): C/S 상담원이 보는 내부 기록. 예외 부서가 보낸 고객 메일도 함께(C-164). */
function DeptReplyPanel({ sub }: { sub: SubTicket }) {
  const st = sub.sub_ticket;
  const at = (t: string | null) => (t ?? "").replace("T", " ").slice(0, 16);
  const sent = sub.dept_mails.filter((m) => m.message_status === "SENT");
  return (
    <div className="card dept-reply">
      <header><h5>부서 회신</h5><span className="muted small">내부 기록 — 고객에게 가지 않음</span></header>
      <p className="small">이관 부서 <b>{st.escalated_to}</b> · 사유 {st.escalation_reason} · 이관 {at(sub.escalated_at_utc)} UTC</p>
      {sub.dept_replies.length === 0 && sent.length === 0 ? <p className="gray">부서 회신 대기 중</p> : (
        <ul className="dept-lines">
          {sub.dept_replies.map((r) => (
            <li key={r.message_id}><span className="muted">{at(r.sent_at_utc)} · {r.sent_by_name}</span>
              <pre className="draft-body">{r.body}</pre></li>
          ))}
          {sent.map((m) => (
            <li key={m.message_id}><span className="muted">{at(m.sent_at_utc)} · {m.sent_by_name} · 고객에게 보낸 메일</span>
              <pre className="draft-body">{m.body}</pre></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RunList({ ticketId }: { ticketId: string }) {
  const [runs, setRuns] = useState<RunRow[] | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (open && runs === null) api.runs(ticketId).then((r) => setRuns(r.runs)).catch(() => setRuns([]));
  }, [open, runs, ticketId]);
  return (
    <details className="runs" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>실행 기록 보기</summary>
      {runs === null ? <p className="muted">읽는 중…</p> : (
        <table className="inbox-table">
          <thead><tr><th>run</th><th>문의</th><th>계기</th><th>결과</th><th>마지막 단계</th><th>시작</th><th>단계</th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <td>{r.run_id}</td><td>{r.sub_ticket_id ?? "티켓"}</td><td>{r.trigger}</td>
                <td className={r.status === "FAILED" ? "bad" : ""}>{r.status ?? "처리 중"}</td><td>{r.last_step ?? "—"}</td>
                <td>{r.started_at_utc.replace("T", " ").slice(0, 19)}</td>
                <td>{r.step_count}{r.failed_steps ? <span className="bad"> (실패 {r.failed_steps})</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

export function SystemTab({ detail, locked, focus, onWhy, onSource, onAdjust, onEdit }: {
  detail: Detail; locked: boolean; focus: string | null;
  onWhy: (row: EvidenceRow) => void; onSource: (t: SourceTarget) => void; onAdjust: (sub: SubTicket) => void;
  onEdit: (sub: SubTicket, data: Record<string, unknown>) => Promise<void>;
}) {
  const n = detail.sub_tickets.length;
  return (
    <section>
      {detail.sub_tickets.map((sub) => {
        const st = sub.sub_ticket;
        const closed = st.status === "CLOSED";
        const adj = sub.adjustments[sub.adjustments.length - 1];
        return (
          <div key={st.sub_ticket_id} className="card sub-section">
            <header>
              <h4>문의 {st.seq}/{n}: {st.category_code ?? "유형 미정"}</h4>
              <StatusBadge status={st.status} />
              <Clocks sub={sub} />
            </header>
            {st.pipeline_error && <p className="bad">! 자동 처리 실패: {st.pipeline_error}</p>}
            <div className="priority-row">
              우선순위 <b>{st.priority ?? "—"}</b> <span className="muted">(규칙 {st.priority_rule_id ?? "—"})</span>
              {adj && <span className="chip human" title={adj.reason}>상담원 조정: {adj.from_priority} → {adj.to_priority} ({adj.reason})</span>}
              <button type="button" disabled={locked || closed || !st.priority} onClick={() => onAdjust(sub)}>조정</button>
            </div>
            <EditControls key={`${st.sub_ticket_id}-${sub.version}`} sub={sub} locked={locked || closed}
                          onSave={(data) => onEdit(sub, data)} />
            <RequiredChecklist sub={sub} locked={locked || closed}
                               onReceived={(field, value) => onEdit(sub, { received_fields: [{ field, value: value || null }] })} />
            {sub.diagnosis && <DiagnosisPanel diagnosis={sub.diagnosis} />}
            {sub.escalation && <EscalationPanel escalation={sub.escalation} />}
            {st.escalated && <DeptReplyPanel sub={sub} />}
            <EvidencePanel sub={sub} focus={focus} onWhy={onWhy} onSource={onSource} />
          </div>
        );
      })}
      <RunList ticketId={detail.ticket.ticket_id} />
    </section>
  );
}

const ALERT_TEXT: Record<string, string> = {
  FR_AT_RISK: "1차 응답 위험", FR_BREACHED: "1차 응답 위반", RES_AT_RISK: "해결 위험", RES_BREACHED: "해결 위반",
};

function line(item: TimelineItem): { icon: string; text: string; cls?: string } {
  switch (item.kind) {
    case "STATUS":
      return { icon: "⇢", text: `상태 ${item.from_status ?? "—"} → ${item.to_status} (${item.event_kind}, ${item.changed_by})` };
    case "PRIORITY":
      return { icon: "⚖", text: `우선순위 조정 ${item.from_priority} → ${item.to_priority}, SLA ${item.from_fr_target_h}/${item.from_res_target_h}h → ${item.to_fr_target_h}/${item.to_res_target_h}h (${item.adjusted_by}: ${item.reason})` };
    case "ALERT_RAISED":
      return { icon: "⚠", text: `경고 발생: ${ALERT_TEXT[String(item.alert_type)] ?? item.alert_type}`, cls: String(item.alert_type).endsWith("BREACHED") ? "bad" : "gold" };
    case "ALERT_CLEARED":
      return { icon: "✓", text: `경고 해제: ${ALERT_TEXT[String(item.alert_type)] ?? item.alert_type}` };
    default:
      if (item.sender === "SYSTEM" && item.notice_transition === "REMINDER") return { icon: "↻", text: "리마인드 자동 발송" };
      return { icon: item.sender === "CUSTOMER" ? "✉" : "➤",
               text: `${item.message_type} · ${item.sender}${item.sent_by_name && item.sent_by_name !== item.sender ? ` ${item.sent_by_name}` : ""} · ${item.language}${item.edited_yn ? " · 수정됨" : ""}` };
  }
}

export function HistoryTab({ ticketId, reloadKey, locked, onReply }: {
  ticketId: string; reloadKey: number; locked: boolean; onReply: () => void;
}) {
  const [items, setItems] = useState<TimelineItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.timeline(ticketId).then((r) => { setItems(r); setError(null); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "이력을 읽지 못함"));
  }, [ticketId, reloadKey]);
  return (
    <section>
      <div className="intake-head">
        <button type="button" disabled={locked} onClick={onReply}>고객 회신 입력</button>
      </div>
      {error && <p className="bad">! {error}</p>}
      {items === null ? <p className="muted">읽는 중…</p> : (
        <ol className="timeline">
          {items.map((item) => {
            const l = line(item);
            const at = item.at.replace("T", " ").slice(0, 16);
            return (
              <li key={`${item.kind}-${item.id}`} className={l.cls ?? ""}>
                <span className="muted">{at}</span> <span aria-hidden="true">{l.icon}</span>
                {item.seq ? <span className="chip">문의 {item.seq}</span> : null} {l.text}
                {item.kind === "MESSAGE" && typeof item.body === "string" && (
                  <details><summary className="small">본문</summary><pre className="draft-body">{item.body}</pre></details>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
