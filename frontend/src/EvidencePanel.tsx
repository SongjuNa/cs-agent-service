// 탭 "시스템이 판단한 것" = 근거 영역 C (FR-024, 화면 정의서 v2 SCR-03M ④ C).
import { useEffect, useRef, useState } from "react";
import type { EvidenceRow, SubTicket } from "./api";
import type { SourceTarget } from "./Popups";

const CHECK_NAMES: Record<string, string> = {
  LOW_CONFIDENCE: "확신 낮음·판정 실패",
  LANG_UNCERTAIN: "언어 불확실",
  EXTRACT_FAILED: "추출 실패",
  PRODUCT_UNKNOWN: "제품 미확정",
  RULE_FAILED: "규칙 판정 실패",
  RETURN_REASON: "반품 사유 확인 필요",
  NO_EVIDENCE: "근거 없음",
  DRAFT_CHECK: "자체 대조 불일치",
};

export function EvidencePanel({ sub, focus, onWhy, onSource }: {
  sub: SubTicket;
  focus: string | null;
  onWhy: (row: EvidenceRow) => void;
  onSource: (t: SourceTarget) => void;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const refs = useRef<Record<string, HTMLElement | null>>({});
  useEffect(() => {
    if (!focus) return;
    setOpen((s) => new Set(s).add(focus));
    refs.current[focus]?.scrollIntoView({ block: "center" });
  }, [focus]);
  const toggle = (id: string) => setOpen((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <div className="evidence">
      <section id="C-10" ref={(el) => (refs.current["C-10"] = el)} className={`row ${focus === "C-10" ? "focus" : ""}`}>
        <div className="row-head"><span className="row-label">확인 표시</span>
          {sub.checks.length === 0 && sub.other_flags.length === 0 && <span className="ok">✓ 없음</span>}
        </div>
        <ul className="chips">
          {sub.checks.map((c, i) => (
            <li key={i} className="chip bad">! {CHECK_NAMES[c.check_type] ?? c.check_type}{c.flag ? ` — ${c.flag}` : ""}</li>
          ))}
          {sub.other_flags.map((f) => <li key={f} className="chip gray" title="확인 표시 종류에 없는 표시">? 기타 표시 — {f}</li>)}
        </ul>
      </section>
      {sub.evidence_rows.map((row) => (
        <section key={row.id} id={row.id} ref={(el) => (refs.current[row.id] = el)}
                 className={`row ${focus === row.id ? "focus" : ""}`}>
          <div className="row-head">
            <button type="button" className="row-toggle" onClick={() => toggle(row.id)} aria-expanded={open.has(row.id)}>
              {open.has(row.id) ? "▾" : "▸"} <span className="row-label">{row.label}</span>
            </button>
            <span className={row.result.startsWith("없음") ? "gray" : ""}>{row.result}</span>
            {row.evidence.length > 0 && <span className="muted"> — {row.evidence.join(" · ")}</span>}
            <button type="button" className="why" onClick={() => onWhy(row)}>왜?</button>
          </div>
          {open.has(row.id) && <RowDetail row={row} onSource={onSource} />}
        </section>
      ))}
    </div>
  );
}

function RowDetail({ row, onSource }: { row: EvidenceRow; onSource: (t: SourceTarget) => void }) {
  if (row.items) {
    return (
      <ul className="items">
        {row.items.map((it) => (
          <li key={it.field} className={it.state === "blocking" ? "bad" : it.state === "missing" ? "gray" : "ok"}>
            {it.state === "provided" ? `✓ ${it.label} 제공(${it.value ?? ""})` : it.state === "blocking" ? `! ${it.label} — 막는 항목` : `? ${it.label} — 빠짐`}
          </li>
        ))}
      </ul>
    );
  }
  if (row.candidates || row.lookups) {
    return (
      <div className="detail">
        {(row.candidates ?? []).length > 0 && (
          <ul>
            {row.candidates!.map((c) => (
              <li key={c.chunk_id}>
                <button type="button" className="link" onClick={() => onSource({ kind: "cite", chunk_id: c.chunk_id, text: `(${c.doc_id} §${c.section})`, score: c.score })}>
                  {c.doc_id} §{c.section}
                </button>{" "}
                <span className="muted">“{c.quote}” · 점수 {c.score.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        )}
        {(row.lookups ?? []).length > 0 && (
          <ul>
            {row.lookups!.map((lv, i) => (
              <li key={i}>
                <button type="button" className="link" onClick={() => onSource({ kind: "lookup", lookup: lv })}>{lv.item}</button>{" "}
                {String(lv.value)} {lv.unit ?? ""} <span className="muted">({lv.source_table}: {lv.source_key})</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  return (
    <div className="detail">
      {row.evidence.length > 0 ? <ul>{row.evidence.map((e, i) => <li key={i}>“{e}”</li>)}</ul> : <p className="muted">근거 문장 없음</p>}
    </div>
  );
}
