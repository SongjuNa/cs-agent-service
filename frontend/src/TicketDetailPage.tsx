// SCR-03M 티켓 상세 최소판 (화면 정의서 v2). 요약 머리 + 탭 4개(보낼 것 기본), 처리 중이면 2초마다 다시 읽는다.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Detail, type Draft, type EvidenceRow } from "./api";
import { DraftCard } from "./DraftCard";
import { EvidencePanel } from "./EvidencePanel";
import { FailPopup, SourcePopup, WhyPopup, type SourceTarget } from "./Popups";

type Tab = "customer" | "system" | "send" | "history";
const POLL_MS = 2000;

export function TicketDetailPage({ ticketId, agent }: { ticketId: string; agent: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("send");
  const [sendTab, setSendTab] = useState<Draft["message_type"] | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [why, setWhy] = useState<EvidenceRow | null>(null);
  const [source, setSource] = useState<SourceTarget | null>(null);
  const [fail, setFail] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api.ticket(ticketId);
      setDetail(d);
      setError(null);
      return d;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "문의를 읽지 못함");
      return null;
    }
  }, [ticketId]);

  useEffect(() => {
    setDetail(null);
    void load();
  }, [load]);
  useEffect(() => {
    if (!detail?.processing) return;
    const timer = setTimeout(() => void load(), POLL_MS);
    return () => clearTimeout(timer);
  }, [detail, load]);

  if (error) return <p className="bad page-msg">! {error}</p>;
  if (!detail) return <p className="muted page-msg">읽는 중…</p>;

  const { ticket, run } = detail;
  const sub = detail.sub_tickets[0];
  const runText = detail.processing ? "처리 중"
    : run?.status === "FAILED" ? `자동 처리 실패: ${run.last_step ?? ""} — ${sub?.sub_ticket.pipeline_error ?? ""}` : "완료";
  const drafts = (sub?.drafts ?? []).filter((d) => !d.superseded_at);
  const types = (["INFO_REQUEST", "FINAL_REPLY"] as const);
  const activeType = sendTab ?? types.find((t) => drafts.some((d) => d.message_type === t)) ?? "FINAL_REPLY";
  const evidenceRow = (id: string) => sub?.evidence_rows.find((r) => r.id === id);
  const lookups = evidenceRow("M-C-02")?.lookups ?? [];

  const reloadDraft = (messageId: number) => async () => {
    const d = await load();
    return d?.sub_tickets[0]?.drafts.find((x) => x.message_id === messageId);
  };

  function noDraftText(type: Draft["message_type"]): string {
    if (detail!.processing) return "처리 중";
    if (run?.status === "FAILED") return "초안 생성 실패";
    if (type === "FINAL_REPLY" && sub?.sub_ticket.missing_blocking_info.length) return "막는 정보 요청 중";
    if (type === "FINAL_REPLY") return "근거 없음 — 상담원 작성 필요";
    return "정보 요청 초안 없음(막는 항목 없음)";
  }

  return (
    <div className="detail-page">
      <header className="summary">
        <div className="h01">
          <h2>{ticket.ticket_id}</h2>
          {ticket.source_ticket_id && <span className="muted">원본 {ticket.source_ticket_id}</span>}
          {ticket.gold_set && <span className="chip gray">채점용 문의</span>}
          {sub?.sub_ticket.priority && <span className="chip">우선순위 {sub.sub_ticket.priority}</span>}
        </div>
        <div className="h03">
          {ticket.company_masked ?? ticket.customer_id} · {ticket.customer_tier} · {ticket.country ?? ""} · {ticket.channel} ·
          고객 언어 {ticket.language} / 본문 언어 {ticket.body_language ?? "—"}
          {ticket.body_language_uncertain && <span className="gray"> ? 본문 언어 판정 불확실</span>}
        </div>
        <div className={`h04 ${run?.status === "FAILED" ? "bad" : detail.processing ? "gray" : ""}`}>
          {detail.processing ? "⏳ " : run?.status === "FAILED" ? "! " : "✓ "}{runText}
        </div>
      </header>

      <nav className="tabs" role="tablist">
        <button role="tab" disabled title="2순위">고객이 보낸 것 <small>2순위</small></button>
        <button role="tab" aria-selected={tab === "system"} onClick={() => setTab("system")}>시스템이 판단한 것</button>
        <button role="tab" aria-selected={tab === "send"} onClick={() => setTab("send")}>보낼 것</button>
        <button role="tab" disabled title="2순위">이력 <small>2순위</small></button>
      </nav>

      {!sub ? <p className="muted">하위 문의 없음</p> : tab === "system" ? (
        <EvidencePanel sub={sub} focus={focus} onWhy={setWhy} onSource={setSource} />
      ) : (
        <div className="send">
          <nav className="subtabs">
            {types.map((t) => (
              <button key={t} aria-selected={activeType === t} onClick={() => setSendTab(t)}>
                {t === "INFO_REQUEST" ? "정보 요청" : "답변"}
              </button>
            ))}
          </nav>
          {drafts.filter((d) => d.message_type === activeType).map((d) => (
            <DraftCard key={d.message_id} agent={agent} draft={d} lookups={lookups} candidates={sub.sub_ticket.evidence_json}
                       ticketLanguage={ticket.language} onSource={setSource} onFail={setFail} reload={reloadDraft(d.message_id)}
                       onJump={(rowId) => { setTab("system"); setFocus(null); setTimeout(() => setFocus(rowId)); }} />
          ))}
          {!drafts.some((d) => d.message_type === activeType) && <p className="card gray">{noDraftText(activeType)}</p>}
          {(sub.drafts.length > drafts.length) && (
            <details><summary>이전 초안 {sub.drafts.length - drafts.length}개</summary>
              {sub.drafts.filter((d) => d.superseded_at).map((d) => <pre key={d.message_id} className="draft-body">{d.body}</pre>)}
            </details>
          )}
        </div>
      )}

      {why && <WhyPopup label={why.label} why={{ 결과: why.result, 근거: why.evidence, ...why.why }} onClose={() => setWhy(null)} />}
      {source && <SourcePopup target={source} onClose={() => setSource(null)} />}
      {fail && <FailPopup message={fail} onClose={() => setFail(null)} />}
    </div>
  );
}
