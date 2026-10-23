// SCR-03 티켓 상세 전체판 (화면 정의서 v1 SCR-03, v2 0-7절 A안 탭 4개, 명세서 FR-030).
// 머리 + 탭 4개(고객이 보낸 것 / 시스템이 판단한 것 / 보낼 것 기본 / 이력). 처리 중이면 2초마다 다시 읽는다.
import { useCallback, useEffect, useState } from "react";
import { AdjustPopup, ReplyPopup } from "./ActionPopups";
import { api, ApiError, type Detail, type Draft, type EvidenceRow, type SubTicket } from "./api";
import { Clocks, CustomerTab, HistoryTab, StatusBadge, SystemTab } from "./DetailTabs";
import { DraftCard } from "./DraftCard";
import { FailPopup, SourcePopup, WhyPopup, type SourceTarget } from "./Popups";

type Tab = "customer" | "system" | "send" | "history";
const POLL_MS = 2000;
const MSG_NO_TICKET = "티켓을 찾을 수 없음"; // FR-030 예외 1행

export function TicketDetailPage({ ticketId, agent, onBack }: { ticketId: string; agent: string; onBack: (message?: string) => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("send");
  const [sendTab, setSendTab] = useState<Draft["message_type"] | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [why, setWhy] = useState<EvidenceRow | null>(null);
  const [source, setSource] = useState<SourceTarget | null>(null);
  const [fail, setFail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adjusting, setAdjusting] = useState<SubTicket | null>(null);
  const [replying, setReplying] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);

  const load = useCallback(async () => {
    try {
      const d = await api.ticket(ticketId);
      setDetail(d);
      setError(null);
      setHistoryKey((k) => k + 1);
      return d;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) onBack(MSG_NO_TICKET); // 접수함으로 되돌림
      else setError(e instanceof ApiError ? e.message : "문의를 읽지 못함");
      return null;
    }
  }, [ticketId, onBack]);

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

  const { ticket, run, summary } = detail;
  const subs = detail.sub_tickets;
  const closed = subs.length > 0 && subs.every((s) => s.sub_ticket.status === "CLOSED");
  const noResponse = closed && subs.every((s) => s.state.final_action === "CLOSED_NO_RESPONSE");
  const locked = detail.processing || closed;
  const failedStep = run?.last_step ?? "";
  const failReason = subs.find((s) => s.sub_ticket.pipeline_error)?.sub_ticket.pipeline_error ?? "";
  const runText = detail.processing ? "처리 중"
    : run?.status === "FAILED" ? `자동 처리 실패: ${failedStep} — ${failReason}`
    : run?.status === "PARTIAL" ? "일부 문의 처리 실패" : "완료";
  const types = ["INFO_REQUEST", "FINAL_REPLY"] as const;
  const live = (s: SubTicket) => s.drafts.filter((d) => !d.superseded_at);
  const activeType = sendTab ?? types.find((t) => subs.some((s) => live(s).some((d) => d.message_type === t))) ?? "FINAL_REPLY";
  const rep = subs.find((s) => s.sub_ticket.sub_ticket_id === summary?.rep_sub_ticket_id) ?? subs[0];

  async function action(fn: () => Promise<unknown>, fallback: string) {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setFail(e instanceof ApiError ? e.message : fallback);
    } finally {
      setBusy(false);
      void load();
    }
  }

  const reprocess = () => action(() => api.reprocess(ticketId), "다시 처리 실패");
  const edit = (sub: SubTicket, data: Record<string, unknown>) =>
    action(() => api.edit(sub.sub_ticket.sub_ticket_id, { ...data, expected_version: sub.version }), "저장 실패");

  const reloadDraft = (messageId: number) => async () => {
    const d = await load();
    return d?.sub_tickets.flatMap((s) => s.drafts).find((x) => x.message_id === messageId);
  };

  function noDraftText(sub: SubTicket, type: Draft["message_type"]): string {
    if (detail!.processing) return "처리 중";
    if (sub.sub_ticket.pipeline_error) return "초안 생성 실패 — 다시 처리";
    if (type === "INFO_REQUEST") return sub.sub_ticket.missing_blocking_info.length ? "정보 요청 초안 없음" : "막는 항목 없음";
    if (sub.sub_ticket.missing_blocking_info.length) return "막는 정보 요청 중";
    return "근거 없음 — 상담원 작성 필요";
  }

  const jump = (rowId: string) => { setTab("system"); setFocus(null); setTimeout(() => setFocus(rowId)); };

  return (
    <div className="detail-page">
      <header className="summary">
        <div className="h01">
          <button type="button" onClick={() => onBack()}>← 목록으로</button>
          <h2>{ticket.ticket_id}</h2>
          {ticket.source_ticket_id && <span className="muted">원본 {ticket.source_ticket_id}에서 불러옴</span>}
          {ticket.gold_set && <span className="chip gray">채점용 문의</span>}
          {summary && <StatusBadge status={summary.status} />}
          {rep && <Clocks sub={rep} />}
          {subs.length > 1 && <span className="chip">복합 {subs.length}건</span>}
        </div>
        <div className="h03">
          {ticket.company_masked ?? ticket.customer_id} · {ticket.customer_tier} · {ticket.country ?? ""} · {ticket.channel} ·
          고객 언어 {ticket.language}
        </div>
        <div className={`h04 ${run?.status === "FAILED" ? "bad" : detail.processing ? "gray" : ""}`}>
          {detail.processing ? "⏳ " : run?.status === "FAILED" ? "! " : "✓ "}{runText}
          {(detail.can_reprocess || detail.can_retry) && (
            <button type="button" className="retry" onClick={() => void reprocess()} disabled={busy}>
              {detail.can_retry ? "다시 시도" : "다시 처리"}
            </button>
          )}
          {closed && <span className="chip gray">{noResponse ? "무응답 종료" : "종료된 문의입니다"}</span>}
        </div>
      </header>

      <nav className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "customer"} onClick={() => setTab("customer")}>고객이 보낸 것</button>
        <button role="tab" aria-selected={tab === "system"} onClick={() => setTab("system")}>시스템이 판단한 것</button>
        <button role="tab" aria-selected={tab === "send"} onClick={() => setTab("send")}>보낼 것</button>
        <button role="tab" aria-selected={tab === "history"} onClick={() => setTab("history")}>이력</button>
      </nav>

      {tab === "customer" ? <CustomerTab detail={detail} />
        : detail.processing && tab !== "history" ? <p className="card gray">⏳ 처리 중 — 끝나면 자동으로 채워집니다</p>
        : tab === "system" ? (
          <SystemTab detail={detail} locked={locked || busy} focus={focus} onWhy={setWhy} onSource={setSource}
                     onAdjust={setAdjusting} onEdit={edit} />
        ) : tab === "history" ? (
          <HistoryTab ticketId={ticketId} reloadKey={historyKey} locked={closed || detail.processing} onReply={() => setReplying(true)} />
        ) : (
          <div className="send">
            <nav className="subtabs">
              {types.map((t) => (
                <button key={t} aria-selected={activeType === t} onClick={() => setSendTab(t)}>
                  {t === "INFO_REQUEST" ? "정보 요청" : "답변"}
                </button>
              ))}
              <button disabled title="여유 시 기능(FR-048)">진행 안내 <small>여유 시</small></button>
              <button disabled title="3순위 기능(FR-033)" className="escalate">이관 <small>3순위</small></button>
            </nav>
            {subs.map((sub) => {
              const drafts = live(sub).filter((d) => d.message_type === activeType);
              const old = sub.drafts.filter((d) => d.superseded_at && d.message_type === activeType);
              const lookups = sub.evidence_rows.find((r) => r.id === "M-C-02")?.lookups ?? [];
              return (
                <div key={sub.sub_ticket.sub_ticket_id}>
                  {subs.length > 1 && <h4>문의 {sub.sub_ticket.seq}/{subs.length}: {sub.sub_ticket.category_code ?? "유형 미정"}</h4>}
                  {drafts.map((d) => (
                    <DraftCard key={d.message_id} agent={agent} draft={d} lookups={lookups} candidates={sub.sub_ticket.evidence_json}
                               ticketLanguage={ticket.language} onSource={setSource} onFail={setFail}
                               reload={reloadDraft(d.message_id)} onJump={jump} />
                  ))}
                  {!drafts.length && <p className="card gray">{noDraftText(sub, activeType)}</p>}
                  {old.length > 0 && (
                    <details><summary>이전 초안 {old.length}개</summary>
                      {old.map((d) => <pre key={d.message_id} className="draft-body">{d.body}</pre>)}
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}

      {why && <WhyPopup label={why.label} why={{ 결과: why.result, 근거: why.evidence, ...why.why }} onClose={() => setWhy(null)} />}
      {source && <SourcePopup target={source} onClose={() => setSource(null)} />}
      {fail && <FailPopup message={fail} onClose={() => setFail(null)} />}
      {adjusting && (
        <AdjustPopup sub={adjusting} onClose={() => setAdjusting(null)} onDone={() => { setAdjusting(null); void load(); }} />
      )}
      {replying && (
        <ReplyPopup ticketId={ticketId} language={ticket.language} subs={subs} onClose={() => setReplying(false)}
                    onDone={() => { setReplying(false); void load(); }} />
      )}
    </div>
  );
}
