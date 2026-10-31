// SCR-03 머리 카드 H-01~H-05와 경고 띠 H-03. 배치는 목업 v1.42 `viewTicket`의 .obj-head(제목 줄 + 숫자 6칸)와 .strip.
import type { ReactNode } from "react";
import type { Detail, SubTicket } from "../../api";
import { CATEGORY, CHANNEL, DEPTH, DEPTH_HINT, label, NEXT_HINT, STATUS } from "../../app/labels";
import { useDepartments } from "../../app/queries";
import { Button, Chip, PriorityBadge } from "../../ui";

const num = (v: number | string | null | undefined): number | null => (v === null || v === undefined ? null : Number(v));
const h = (v: number) => `${v.toFixed(1)} h`;

/** 대표 문의: 서버 요약(가장 급한 문의)이 고른 것, 없으면 첫 문의 */
export function repOf(detail: Detail): SubTicket | undefined {
  return detail.sub_tickets.find((s) => s.sub_ticket.sub_ticket_id === detail.summary?.rep_sub_ticket_id) ?? detail.sub_tickets[0];
}

function Stat({ k, children, sub, small }: { k: string; children: ReactNode; sub?: ReactNode; small?: boolean }) {
  return (
    <div className={small ? "tk-stat tk-stat--small" : "tk-stat"}>
      <span className="tk-stat__k">{k}</span>
      <span className="tk-stat__v">{children}</span>
      {sub && <span className="tk-stat__s">{sub}</span>}
    </div>
  );
}

/** H-02 1차 응답: 보냈으면 "보냄", 아니면 남은 시간과 목표 */
function FirstResponse({ sub }: { sub: SubTicket }) {
  const sla = sub.sla;
  if (sub.sub_ticket.first_response_at_utc || sla?.fr_status === "MET") return <Chip tone="pos">보냄</Chip>;
  if (!sla || sla.fr_target_h === null) return <span className="tk-muted">SLA 미정</span>;
  const left = sla.fr_target_h - (num(sla.fr_elapsed_h) ?? 0);
  return <span className={left < 0 ? "tk-neg" : undefined}>{left < 0 ? "−" : ""}{h(Math.abs(left))}</span>;
}

function resolutionText(sub: SubTicket): { value: ReactNode; sub: string } {
  const sla = sub.sla;
  const status = sub.sub_ticket.status;
  if (status === "RESOLVED" || status === "CLOSED") return { value: "끝남", sub: "" };
  if (!sla || sla.res_target_h === null) return { value: <span className="tk-muted">SLA 미정</span>, sub: "" };
  if (status === "WAITING_CUSTOMER") return { value: "멈춤", sub: `고객 회신 대기, 목표 ${sla.res_target_h} h` };
  const left = num(sla.remaining_h) ?? sla.res_target_h - (num(sla.res_elapsed_h) ?? 0);
  return {
    value: <span className={left < 0 ? "tk-neg" : undefined}>{left < 0 ? "−" : ""}{h(Math.abs(left))}</span>,
    sub: `${left < 0 ? "지남" : "남음"}, 목표 ${sla.res_target_h} h`,
  };
}

export interface InboxNav { ids: string[]; index: number; go: (ticketId: string) => void }

export function HeadCard({ detail, onBack, onReprocess, busy, nav }: {
  detail: Detail; onBack: () => void; onReprocess: () => void; busy: boolean; nav?: InboxNav;
}) {
  const depts = useDepartments();
  const { ticket, run, summary } = detail;
  const subs = detail.sub_tickets;
  const rep = repOf(detail);
  const kinds = [...new Set(subs.map((s) => s.sub_ticket.category_code).filter(Boolean))].map((c) => label(CATEGORY, c));
  const products = [...new Set(subs.map((s) => s.sub_ticket.product_code).filter(Boolean))];
  const deptName = (code: string | null) => depts.data?.find((d) => d.dept_code === code)?.dept_name_ko ?? code ?? "—";
  const deptsShown = [...new Set(subs.map((s) => s.sub_ticket.assigned_dept))];
  const res = rep ? resolutionText(rep) : null;
  const closed = subs.length > 0 && subs.every((s) => s.sub_ticket.status === "CLOSED");

  // H-04: 처리 중 / 자동 처리 실패({단계} — {사유}) / 완료
  const failReason = subs.find((s) => s.sub_ticket.pipeline_error)?.sub_ticket.pipeline_error ?? "";
  const runLine = detail.processing ? <Chip tone="info">처리 중</Chip>
    : run?.status === "FAILED" ? <Chip tone="neg">자동 처리 실패: {run.last_step ?? ""}{failReason ? ` — ${failReason}` : ""}</Chip>
    : run?.status === "PARTIAL" ? <Chip tone="crit">일부 문의 처리 실패</Chip>
    : null;

  return (
    <section className="tk-head" aria-label="티켓 요약">
      <div className="tk-head__top">
        <h1 className="tk-head__id">{ticket.ticket_id}</h1>
        <span className="tk-head__ttl">{[kinds.join(" + ") || "유형 미정", products.join(", ") || "제품 미확인"].join(", ")}</span>
        <span className="tk-head__chips">
          {subs.length > 1 && <Chip tone="brand">복합 문의 {subs.length}건</Chip>}
          {ticket.source_ticket_id && <Chip tone="outline">원본 {ticket.source_ticket_id}</Chip>}
          {ticket.gold_set && <Chip tone="neu">채점용 문의</Chip>}
          {closed && <Chip tone="neu">종료된 문의입니다</Chip>}
          {runLine}
        </span>
        <span className="tk-head__actions">
          {nav && nav.ids.length > 0 && nav.index >= 0 && (
            <span className="tk-nav" role="group" aria-label="이전·다음 문의">
              <button type="button" disabled={nav.index === 0} aria-label="이전 문의 (k)" title="이전 문의 · k" onClick={() => nav.go(nav.ids[nav.index - 1])}>‹</button>
              <span>{nav.index + 1} / {nav.ids.length}</span>
              <button type="button" disabled={nav.index >= nav.ids.length - 1} aria-label="다음 문의 (j)" title="다음 문의 · j" onClick={() => nav.go(nav.ids[nav.index + 1])}>›</button>
            </span>
          )}
          {(detail.can_reprocess || detail.can_retry) && (
            <Button onClick={onReprocess} busy={busy}>{detail.can_retry ? "다시 시도" : "다시 처리"}</Button>
          )}
          <Button className="tk-back" onClick={onBack}>접수함으로</Button>
        </span>
      </div>
      <p className="tk-recv">
        접수 <b>{ticket.received_at_utc.replace("T", " ").slice(0, 16)}</b> · {label(CHANNEL, ticket.channel)} · {ticket.country ?? "국가 미상"} · 답장 {ticket.language}
      </p>
      {subs.some((x) => x.sub_ticket.summary_ko) && (
        <div className="tk-sum" data-testid="ai-summary">
          <span className="tk-sum__k">AI 요약</span>
          <ul>
            {subs.filter((x) => x.sub_ticket.summary_ko).map((x) => (
              <li key={x.sub_ticket.sub_ticket_id}>{subs.length > 1 ? <b>문의 {x.sub_ticket.seq} · </b> : null}{x.sub_ticket.summary_ko}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="tk-stats">
        <Stat k="상태" sub={subs.length > 1 ? "가장 급한 문의 기준" : undefined}>{label(STATUS, summary?.status ?? rep?.sub_ticket.status)}</Stat>
        <Stat k="채널">{label(CHANNEL, ticket.channel)}</Stat>
        <Stat k="우선순위">
          {subs.map((s) => <PriorityBadge key={s.sub_ticket.sub_ticket_id} priority={s.sub_ticket.priority}
                                          adjusted={s.adjustments.length > 0} />)}
        </Stat>
        <Stat k="1차 응답" sub={rep?.sla?.fr_target_h && !rep.sub_ticket.first_response_at_utc
          ? `${rep.sla.fr_target_h - (num(rep.sla.fr_elapsed_h) ?? 0) < 0 ? "지남" : "남음"}, 목표 ${rep.sla.fr_target_h} h` : undefined}>
          {rep ? <FirstResponse sub={rep} /> : "—"}
        </Stat>
        <Stat k="해결 기한" sub={res?.sub}>{res?.value ?? "—"}</Stat>
        <Stat k="담당" small>{deptsShown.map(deptName).join(", ")}</Stat>
      </div>
    </section>
  );
}

/** 지금 할 일 한 줄과 검토 모드. 접수함 줄과 같은 서버 규칙(turn·next_action·review_depth, 변경 add-inbox-turn-depth) */
export function NowStrip({ detail, deptName }: { detail: Detail; deptName: (code: string | null) => string }) {
  const rep = repOf(detail);
  if (!rep || detail.processing) return null;
  const done = rep.turn === "DONE";
  const waiting = rep.turn === "DEPT" || rep.turn === "CUSTOMER";
  const text = rep.next_action === "WAIT_DEPT"
    ? `${deptName(rep.sub_ticket.escalated_to)} 회신 대기 — ${NEXT_HINT.WAIT_DEPT}` : label(NEXT_HINT, rep.next_action);
  return (
    <section className={`tk-now tk-now--${done ? "done" : waiting ? "wait" : "me"}`} aria-label="지금 할 일" data-testid="now-strip">
      <span className="tk-now__k">{done ? "완료" : waiting ? "대기" : "내 차례"}</span>
      <span className="tk-now__t">{text}</span>
      {!done && (
        <span className={`tk-now__depth tk-now__depth--${rep.review_depth.toLowerCase()}`} title={DEPTH_HINT[rep.review_depth]}>
          검토 모드 · {DEPTH[rep.review_depth]}
        </span>
      )}
    </section>
  );
}

/** H-03 경고 띠. 1차 응답 경고가 먼저(FR-027), 회신 대기면 안내만 */
export function AlertBand({ detail, onShowSend }: { detail: Detail; onShowSend: () => void }) {
  const rep = repOf(detail);
  if (!rep?.sla) return null;
  const sla = rep.sla;
  const open = rep.alerts.filter((a) => !a.cleared_at_utc).map((a) => a.alert_type);
  const pct = (e: number, t: number) => Math.round((e / t) * 100);
  if (rep.sub_ticket.status === "WAITING_CUSTOMER") {
    return <div className="tk-strip tk-strip--neu" role="status"><b>고객 회신 대기</b><span>해결 시계가 멈춰 있습니다.</span></div>;
  }
  const fr = open.find((a) => a.startsWith("FR_"));
  if (fr && sla.fr_target_h !== null && !rep.sub_ticket.first_response_at_utc) {
    const e = num(sla.fr_elapsed_h) ?? 0;
    const over = fr.endsWith("BREACHED") || e > sla.fr_target_h; // 경고가 아직 AT_RISK여도 시계가 넘었으면 "지남"
    return (
      <div className={`tk-strip ${over ? "tk-strip--neg" : "tk-strip--crit"}`} role="alert">
        <b>{over ? "1차 응답 기한 지남" : "1차 응답 기한 임박"}</b>
        <span>1차 응답 기한 {sla.fr_target_h} h 중 {e.toFixed(1)} h가 지났습니다({pct(e, sla.fr_target_h)} %). 정보 요청을 먼저 보내면 1차 응답으로 인정됩니다.</span>
        <Button size="sm" onClick={onShowSend}>보낼 것 보기</Button>
      </div>
    );
  }
  const r = open.find((a) => a.startsWith("RES_"));
  if (r && sla.res_target_h !== null) {
    const e = num(sla.res_elapsed_h) ?? 0;
    const over = r.endsWith("BREACHED") || e > sla.res_target_h;
    return (
      <div className={`tk-strip ${over ? "tk-strip--neg" : "tk-strip--crit"}`} role="alert">
        <b>{over ? "해결 기한 지남" : "해결 기한 임박"}</b>
        <span>해결 기한 {sla.res_target_h} h 중 {e.toFixed(1)} h가 지났습니다.</span>
      </div>
    );
  }
  return null;
}
