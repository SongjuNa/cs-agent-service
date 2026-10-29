// 탭 ② 시스템이 판단한 것 (SCR-03 C-01~C-10, FR-024, 문의마다 한 칸). 배치는 목업 v1.42 `judgSection`(이름 | 값 | 왜?).
// 유형·긴급도·제품 고치기(FR-030 처리 5), 받은 항목 표시(C-07), 우선순위 [조정](P3), 실행 기록(C-11)도 이 탭에 둔다.
import { Fragment, useEffect, useRef, useState } from "react";
import { api, type Detail, type EvidenceRow, type FaultCandidate, type RunRow, type SubTicket } from "../../api";
import { CATEGORY, URGENCY, label } from "../../app/labels";
import { Button, Chip, Field, PriorityBadge, SlaBadge, StatusBadge } from "../../ui";
import type { SourceTarget } from "./Popups";

const CATEGORIES = ["DEFECT", "FW_UPDATE", "MANUAL", "QUOTE", "TECH_SPEC", "COMPLIANCE", "RETURN", "WARRANTY", "INSTALL", "ORDER_LEAD"];
const CHECK_NAMES: Record<string, string> = {
  LOW_CONFIDENCE: "확신 낮음·판정 실패", LANG_UNCERTAIN: "언어 불확실", EXTRACT_FAILED: "추출 실패", PRODUCT_UNKNOWN: "제품 미확정",
  RULE_FAILED: "규칙 판정 실패", RETURN_REASON: "반품 사유 확인 필요", NO_EVIDENCE: "근거 없음", DRAFT_CHECK: "자체 대조 불일치",
};
const METHOD: Record<string, string> = { EXACT: "정확 일치", SYMPTOM: "증상 검색" };

function Edited({ sub, name }: { sub: SubTicket; name: string }) {
  const e = sub.edits[name];
  return e ? <Chip tone="brand" title={`${String(e.from ?? "—")} → ${String(e.to)} (${e.by ?? ""})`}>상담원 수정</Chip> : null;
}

/** 유형·긴급도·제품(·반품 구분) 고치기 → PATCH /sub-tickets/{id}, 저장하면 다시 계산(처리 중) */
function EditControls({ sub, locked, onSave }: { sub: SubTicket; locked: boolean; onSave: (data: Record<string, unknown>) => void }) {
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
    <div className="tk-edit" aria-label={`문의 ${st.seq} 값 고치기`}>
      <Field label="유형">
        <select value={category} disabled={locked} onChange={(e) => setCategory(e.target.value)}>
          {!st.category_code && <option value="">유형을 정하지 못함. 직접 선택</option>}
          {CATEGORIES.map((c) => <option key={c} value={c}>{label(CATEGORY, c)} ({c})</option>)}
        </select>
      </Field>
      <Field label="긴급도">
        <select value={urgency} disabled={locked} onChange={(e) => setUrgency(e.target.value)}>
          {Object.entries(URGENCY).map(([v, l]) => <option key={v} value={v}>{l} ({v})</option>)}
        </select>
      </Field>
      <Field label="제품">
        <select value={product} disabled={locked} onChange={(e) => setProduct(e.target.value)}>
          {!st.product_code && <option value="">제품 확인 필요. 선택</option>}
          {products.map((p) => <option key={p.product_code} value={p.product_code}>{p.product_code}</option>)}
        </select>
      </Field>
      {(category || st.category_code) === "RETURN" && (
        <Field label="반품 구분">
          <select value={returnKind} disabled={locked} onChange={(e) => setReturnKind(e.target.value)}>
            <option value="">{st.return_kind === "UNKNOWN" ? "확인 필요" : "—"}</option>
            <option value="DEFECT">불량</option>
            <option value="NON_DEFECT">비불량</option>
          </select>
        </Field>
      )}
      <Button disabled={locked || !Object.keys(changed).length} onClick={() => onSave(changed)}>저장하고 다시 계산</Button>
    </div>
  );
}

/** C-07 필수정보: ✓ 제공(값) / ● 막는 항목 / ○ 빠짐 / "상담원 입력". 빠진 항목은 [받았음]으로 표시(FR-030 처리 5) */
function Required({ sub, row, locked, onReceived }: {
  sub: SubTicket; row: EvidenceRow; locked: boolean; onReceived: (field: string, value: string) => void;
}) {
  const [value, setValue] = useState<Record<string, string>>({});
  return (
    <ul className="tk-items" data-testid={`required-${sub.sub_ticket.seq}`}>
      {(row.items ?? []).map((it) => (
        <li key={it.field} className={`is-${it.state}`} data-field={it.field} data-state={it.state}>
          <span aria-hidden="true">{it.state === "provided" ? "✓" : it.state === "blocking" ? "●" : "○"}</span>
          {it.label}
          <span className="tk-items__sub">{it.state === "provided" ? `제공(${it.value ?? ""})` : it.state === "blocking" ? "막는 항목" : "빠짐"}</span>
          {sub.fields.some((f) => f.field === it.field && f.source === "AGENT") && <Chip tone="brand">상담원 입력</Chip>}
          {it.state !== "provided" && !locked && (
            <>
              <input placeholder="받은 값(선택)" aria-label={`${it.label} 받은 값`} value={value[it.field] ?? ""}
                     onChange={(e) => setValue({ ...value, [it.field]: e.target.value })} />
              <Button size="sm" onClick={() => onReceived(it.field, value[it.field] ?? "")}>받았음</Button>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

function Fault({ c }: { c: FaultCandidate }) {
  return (
    <div className="tk-fault">
      <div className="tk-row__line">
        <b>{c.fault_id}</b><Chip tone="outline">{METHOD[c.method ?? ""] ?? "—"}{c.score !== null ? ` ${c.score.toFixed(2)}` : ""}</Chip>
        {c.onsite_required && <Chip tone="neg">현장 출동 필요</Chip>}
        {c.replace_required && <Chip tone="neg">교체 필요</Chip>}
      </div>
      <dl><dt>원인</dt><dd>{c.cause ?? "—"}</dd><dt>점검</dt><dd>{c.check ?? "—"}</dd><dt>조치</dt><dd>{c.action ?? "—"}</dd></dl>
    </div>
  );
}

/** 비슷한 해결사례 (FR-019, 변경 add-similar-cases 결정 4). 고장 진단 줄 바로 아래, 상담원 참고용 */
function Similar({ sub, onCases }: { sub: SubTicket; onCases?: (sub: SubTicket) => void }) {
  const sc = sub.similar_cases;
  if (!sc) return null;
  return (
    <div className="tk-row" data-row="C-08b" data-testid="similar-cases">
      <span className="tk-row__k">비슷한 해결사례</span>
      <div className="tk-row__v">
        <span className="tk-row__line">
          {sc.cases.length ? `${sc.cases.length}건` : <span className="tk-muted">없음</span>}
          {onCases && <button type="button" className="tk-link tk-link--b" onClick={() => onCases(sub)}>접수 이력에서 보기</button>}
        </span>
        <span className="tk-row__ev">참고용, 초안에는 쓰지 않음{sc.notes.map((n) => ` · ${n}`).join("")}</span>
        {sc.cases.map((c) => (
          <div key={c.case_id} className="tk-fault" data-case={c.case_id}>
            <div className="tk-row__line">
              <b>{c.case_id}</b>
              <Chip tone="outline">{c.method === "ERROR_CODE" ? "같은 에러 코드" : "뜻 검색"} {Number(c.score).toFixed(2)}</Chip>
              {c.error_code && <span className="tk-mono">{c.error_code}</span>}
            </div>
            <dl><dt>원인</dt><dd>{c.cause ?? "—"}</dd><dt>조치</dt><dd>{c.action ?? "—"}</dd><dt>결과</dt><dd>{c.result ?? "—"}</dd></dl>
          </div>
        ))}
      </div>
      <span />
    </div>
  );
}

/** 줄 값 아래에 펼쳐 보이는 것(근거 문장, 절·조회값, 진단·이관 후보) */
function RowBody({ sub, row, onSource }: { sub: SubTicket; row: EvidenceRow; onSource: (t: SourceTarget) => void }) {
  if (row.id === "C-08" && sub.diagnosis) {
    const [first, ...rest] = sub.diagnosis.fault_candidates;
    return (
      <>
        <span className="tk-row__ev">참고용, 초안에는 쓰지 않음{sub.diagnosis.notes.map((n) => ` · ${n}`).join("")}</span>
        {first && <Fault c={first} />}
        {rest.length > 0 && <details className="tk-old"><summary>다른 후보 {rest.length}개</summary>{rest.map((c) => <Fault key={c.fault_id} c={c} />)}</details>}
      </>
    );
  }
  if (row.id === "C-09" && sub.escalation) {
    const list = sub.escalation.escalation_candidates;
    return (
      <span className="tk-row__ev">
        확정은 상담원이 합니다.{" "}
        {list.length === 0 && sub.escalation.escalation_condition && `이관 조건: ${sub.escalation.escalation_condition}`}
        {list.some((c) => c.team) && <Chip tone="brand">팀 규칙 포함</Chip>}
      </span>
    );
  }
  if (row.candidates?.length || row.lookups?.length) {
    return (
      <ul className="tk-items">
        {(row.candidates ?? []).map((c) => (
          <li key={c.chunk_id}>
            <button type="button" className="tk-link" onClick={() => onSource({ kind: "cite", chunk_id: c.chunk_id, text: `(${c.doc_id} §${c.section})`, score: c.score })}>
              {c.doc_id} §{c.section}
            </button>
            <span className="tk-items__sub">“{c.quote}”, 점수 {c.score.toFixed(3)}</span>
          </li>
        ))}
        {(row.lookups ?? []).map((lv, i) => (
          <li key={`l${i}`}>
            <button type="button" className="tk-link" onClick={() => onSource({ kind: "lookup", lookup: lv })}>{lv.item}</button>
            {String(lv.value)} {lv.unit ?? ""}<span className="tk-items__sub">({lv.source_table}: {lv.source_key})</span>
          </li>
        ))}
      </ul>
    );
  }
  return row.evidence.length > 0 ? <span className="tk-row__ev">{row.evidence.map((e) => `“${e}”`).join(" · ")}</span> : null;
}

function RunList({ ticketId }: { ticketId: string }) {
  const [runs, setRuns] = useState<RunRow[] | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (open && runs === null) api.runs(ticketId).then((r) => setRuns(r.runs)).catch(() => setRuns([]));
  }, [open, runs, ticketId]);
  return (
    <details className="tk-runs" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>실행 기록 보기</summary>
      {runs === null ? <p className="tk-muted">읽는 중…</p> : (
        <table className="ui-table">
          <thead><tr><th>실행</th><th>문의</th><th>계기</th><th>결과</th><th>마지막 단계</th><th>시작</th><th>단계</th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <td>{r.run_id}</td><td>{r.sub_ticket_id ?? "티켓"}</td><td>{r.trigger}</td>
                <td className={r.status === "FAILED" ? "tk-neg" : undefined}>{r.status ?? "처리 중"}</td><td>{r.last_step ?? "—"}</td>
                <td>{r.started_at_utc.replace("T", " ").slice(0, 19)}</td>
                <td>{r.step_count}{r.failed_steps ? <span className="tk-neg"> (실패 {r.failed_steps})</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

export function SystemTab({ detail, locked, focus, onWhy, onSource, onAdjust, onEdit, onCases }: {
  detail: Detail; locked: boolean; focus: string | null;
  onWhy: (row: EvidenceRow) => void; onSource: (t: SourceTarget) => void; onAdjust: (sub: SubTicket) => void;
  onEdit: (sub: SubTicket, data: Record<string, unknown>) => void;
  /** [접수 이력에서 보기]: 그 문의의 에러 코드·제품으로 해결사례 검색을 연다(SCR-09 동작 표) */
  onCases?: (sub: SubTicket) => void;
}) {
  const refs = useRef<Record<string, HTMLElement | null>>({});
  useEffect(() => { if (focus) refs.current[focus]?.scrollIntoView({ block: "center" }); }, [focus]);
  const n = detail.sub_tickets.length;

  return (
    <div className="tk-pane">
      {detail.sub_tickets.map((sub) => {
        const st = sub.sub_ticket;
        const closed = st.status === "CLOSED";
        const adj = sub.adjustments[sub.adjustments.length - 1];
        return (
          <section key={st.sub_ticket_id} className="tk-sub" aria-label={`문의 ${st.seq}`} data-testid={`judge-${st.seq}`}>
            {n > 1 && (
              <div className="tk-sub__head">
                문의 {st.seq}/{n}: {label(CATEGORY, st.category_code)} <StatusBadge status={st.status} />
                <SlaBadge status={sub.sla?.res_status} />
              </div>
            )}
            {st.pipeline_error && <div className="tk-strip tk-strip--neg"><b>자동 처리 실패</b><span>{st.pipeline_error}</span></div>}
            {(sub.checks.length > 0 || sub.other_flags.length > 0) && (
              <div className="tk-row" ref={(el) => (refs.current["C-10"] = el)} data-row="C-10">
                <span className="tk-row__k">확인 표시</span>
                <span className="tk-row__line">
                  {sub.checks.map((c, i) => <Chip key={i} tone="neg">{CHECK_NAMES[c.check_type] ?? c.check_type}{c.flag ? `: ${c.flag}` : ""}</Chip>)}
                  {sub.other_flags.map((f) => <Chip key={f} tone="neu" title="확인 표시 종류에 없는 표시">기타 표시: {f}</Chip>)}
                </span>
                <span />
              </div>
            )}
            {sub.evidence_rows.map((row) => (
              <Fragment key={row.id}>
              <div className={focus === row.id ? "tk-row is-focus" : "tk-row"} data-row={row.id}
                   ref={(el) => (refs.current[row.id] = el)}>
                <span className="tk-row__k">{row.label.replace(/^[①-⑩]\s*/, "")}</span>
                <div className="tk-row__v">
                  <span className="tk-row__line">
                    {row.id === "C-03" ? (
                      <>
                        <PriorityBadge priority={st.priority} adjusted={!!adj} />
                        <span className="tk-muted">규칙값 {sub.adjustments[0]?.from_priority ?? st.priority ?? "—"} ({st.priority_rule_id ?? "—"})</span>
                        {adj && <span>{adj.from_priority} → {adj.to_priority} (상담원 조정, 사유: {adj.reason})</span>}
                        <button type="button" className="tk-link tk-link--b" disabled={locked || closed || !st.priority} onClick={() => onAdjust(sub)}>조정</button>
                      </>
                    ) : row.id === "C-01" ? (
                      <>{row.result.startsWith("없음") ? <span className="tk-muted">{row.result}</span> : <>{label(CATEGORY, row.result)} <span className="tk-mono">{row.result}</span></>}<Edited sub={sub} name="category_code" /></>
                    ) : row.id === "C-02" ? (
                      <>{URGENCY[row.result] ?? row.result} <span className="tk-mono">{row.result}</span><Edited sub={sub} name="urgency_flag" /></>
                    ) : (
                      <span className={row.result.startsWith("없음") ? "tk-muted" : undefined}>{row.result}</span>
                    )}
                    {row.id === "M-C-01" && <Edited sub={sub} name="product_code" />}
                  </span>
                  {row.id === "C-07" && row.items?.length ? (
                    <Required sub={sub} row={row} locked={locked || closed}
                              onReceived={(field, value) => onEdit(sub, { received_fields: [{ field, value: value || null }] })} />
                  ) : <RowBody sub={sub} row={row} onSource={onSource} />}
                </div>
                {/* 목업의 "왜?" 글자 링크 대신 일반 버튼(2026-10-29 조장 요청) */}
                <Button size="sm" className="tk-why" onClick={() => onWhy(row)}>근거 보기</Button>
              </div>
              {row.id === "C-08" && <Similar sub={sub} onCases={onCases} />}
              </Fragment>
            ))}
            {!sub.evidence_rows.some((r) => r.id === "C-08") && <Similar sub={sub} onCases={onCases} />}
            <EditControls key={`${st.sub_ticket_id}-${sub.version}`} sub={sub} locked={locked || closed} onSave={(data) => onEdit(sub, data)} />
          </section>
        );
      })}
      <RunList ticketId={detail.ticket.ticket_id} />
    </div>
  );
}
