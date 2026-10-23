// SCR-04 나의 업무 현황 (화면 정의서 v1, 명세서 FR-047, 기술 명세서 §8-3). 숫자는 서버가 센 값을 그대로 보인다.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type WorkRow, type Workload } from "./api";
import { ALERT_LABEL, STATUS_BADGE } from "./InboxPage";

const REFRESH_MS = 5 * 60 * 1000; // FR-047 처리 6, §8-2 (FR-027 점검 주기와 같게)
const FAIL = "불러오지 못함. 새로고침"; // FR-047 예외 4행
const NO_SCOPE = "상단에서 이름과 부서를 고르세요"; // FR-047 예외 3행
const SCOPE_KEY = "cs-my-scope";
type Area = "risks" | "drafts" | "waiting_customer" | "waiting_escalation";
const TILES: [Area, string][] = [
  ["drafts", "승인 대기 초안"], ["risks", "기한 위험·위반"], ["waiting_customer", "고객 회신 대기"], ["waiting_escalation", "이관 회신 대기"],
];

function savedScope(): "mine" | "dept" | null {
  try {
    const v = localStorage.getItem(SCOPE_KEY);
    return v === "mine" || v === "dept" ? v : null;
  } catch {
    return null;
  }
}

function hours(h: string | number | null | undefined): string {
  if (h === null || h === undefined) return "—";
  const n = Number(h);
  return `${n < 0 ? "−" : ""}${Math.abs(n).toFixed(1)}h`;
}

function when(at: string | null): string {
  return at ? at.replace("T", " ").slice(0, 16) + " UTC" : "—";
}

function Ticket({ row }: { row: WorkRow }) {
  return <>{row.ticket_id}{row.inquiry_count > 1 && <span className="small"> ({row.seq}/{row.inquiry_count})</span>}</>;
}

function Status({ status }: { status: string }) {
  const b = STATUS_BADGE[status] ?? { cls: "", mark: "" };
  return <span className={`badge ${b.cls}`}>{b.mark} {status}</span>;
}

/** 126h(리마인드)·168h(무응답 종료) 눈금 막대(SCR-04-L3) */
function WaitBar({ elapsed, remind, close }: { elapsed: number | null; remind: number; close: number }) {
  const pct = (h: number) => `${Math.min(100, (h / close) * 100)}%`;
  return (
    <span className="waitbar" title={`리마인드 ${remind}h · 무응답 종료 ${close}h`}>
      <span className="fill" style={{ width: pct(elapsed ?? 0) }} />
      <span className="tick" style={{ left: pct(remind) }} />
    </span>
  );
}

export function MyWorkPage({ dept, agent, asOf, onOpen }: {
  dept: string; agent: string; asOf: string | null; onOpen: (id: string) => void;
}) {
  const [scope, setScope] = useState<"mine" | "dept">(savedScope() ?? (agent ? "mine" : "dept"));
  const [data, setData] = useState<Workload | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const effective = scope === "mine" && !agent ? "dept" : scope;
  const ready = effective === "mine" ? Boolean(agent) : Boolean(dept);

  const load = useCallback(async () => {
    if (!ready) return;
    const q = new URLSearchParams({ scope: effective });
    if (dept) q.set("dept", dept);
    if (asOf) q.set("as_of", asOf);
    try {
      setData(await api.workload(q));
      setFailed(null);
    } catch (e) {
      setFailed(e instanceof ApiError && e.status !== 500 ? `${FAIL} (${e.message})` : FAIL); // 이전 값은 그대로 둔다
    }
  }, [ready, effective, dept, asOf]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  function choose(next: "mine" | "dept") {
    setScope(next);
    try { localStorage.setItem(SCOPE_KEY, next); } catch { /* 기억 못 해도 된다 */ }
  }

  if (!ready) return <p className="muted page-msg">{NO_SCOPE}</p>;
  const jump = (area: Area) => document.getElementById(`my-${area}`)?.scrollIntoView({ behavior: "smooth" });
  const open = (row: WorkRow) => ({
    onClick: () => onOpen(row.ticket_id),
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter") onOpen(row.ticket_id); },
    tabIndex: 0,
  });
  const empty = (area: Area) => data && !data[area].length && <p className="muted">{data.empty[area]}</p>;

  return (
    <div className="my-work">
      <div className="scope-bar">
        <span>
          {effective === "mine" ? `${agent} 담당` : "부서 전체 기준"} · {dept || "부서 없음"} · 기준 {data ? when(data.as_of) : "…"}
        </span>
        <span className="scope-switch">
          <button type="button" aria-pressed={effective === "mine"} disabled={!agent} onClick={() => choose("mine")}>내 담당</button>
          <button type="button" aria-pressed={effective === "dept"} disabled={!dept} onClick={() => choose("dept")}>부서 전체</button>
        </span>
      </div>
      {failed && <p className="bad">! {failed}</p>}
      {!data ? <p className="muted page-msg">읽는 중…</p> : (
        <div className={failed ? "stale" : ""}>
          <div className="tiles">
            {TILES.map(([area, label]) => (
              <button type="button" key={area} className="tile" onClick={() => jump(area)}>
                <strong>{data.tiles[area]}</strong><span>{label}</span>
              </button>
            ))}
          </div>
          <p className="today">
            오늘 처리한 건수: 발송 {data.today.sent} · 이관 {data.today.escalated} · 조정 {data.today.adjusted}
            {data.sla_unset > 0 && <span className="chip gray">SLA 미정 {data.sla_unset}건</span>}
          </p>

          <section id="my-risks">
            <h3>기한 위험·위반</h3>
            {empty("risks") || (
              <table className="inbox-table">
                <thead><tr><th>문의 번호</th><th>고객사·등급</th><th>우선순위</th><th>상태</th><th>경고</th><th>해결 남은 시간</th></tr></thead>
                <tbody>{data.risks.map((r) => (
                  <tr key={r.sub_ticket_id} {...open(r)}>
                    <td><Ticket row={r} /></td><td>{r.company_masked} · {r.customer_tier}</td><td>{r.priority}</td>
                    <td><Status status={r.status} /></td>
                    <td>{r.alerts.map((a) => <span key={a} className={`chip ${ALERT_LABEL[a]?.cls ?? ""}`}>{ALERT_LABEL[a]?.text ?? a}</span>)}</td>
                    <td className={Number(r.remaining_h) < 0 ? "bad" : ""}>{hours(r.remaining_h)}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </section>

          <section id="my-drafts">
            <h3>승인 대기 초안</h3>
            {empty("drafts") || (
              <table className="inbox-table">
                <thead><tr><th>종류</th><th>문의 번호</th><th>우선순위</th><th>만든 시각</th><th>확인 표시</th></tr></thead>
                <tbody>{data.drafts.map((r) => (
                  <tr key={r.message_id} {...open(r)}>
                    <td>{r.message_type === "INFO_REQUEST" ? "정보 요청" : r.message_type === "FINAL_REPLY" ? "답변" : "진행 안내"}</td>
                    <td><Ticket row={r} /></td><td>{r.priority}</td><td>{when(r.created_at_utc)}</td>
                    <td>{r.has_check ? <span className="gold" title="실패한 자동 검사(self_check)가 있음. 상세에서 확인">● 확인 필요</span> : ""}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </section>

          <section id="my-waiting_customer">
            <h3>고객 회신 대기</h3>
            {empty("waiting_customer") || (
              <table className="inbox-table">
                <thead><tr><th>문의 번호</th><th>고객사·등급</th><th>정보 요청 발송</th><th>경과</th><th>126h · 168h</th><th>리마인드</th></tr></thead>
                <tbody>{data.waiting_customer.map((r) => (
                  <tr key={r.sub_ticket_id} {...open(r)}>
                    <td><Ticket row={r} /></td><td>{r.company_masked} · {r.customer_tier}</td><td>{when(r.requested_at_utc)}</td>
                    <td>{hours(r.elapsed_h)}</td><td><WaitBar elapsed={r.elapsed_h} remind={r.remind_at_h} close={r.close_at_h} /></td>
                    <td>{r.reminder_sent ? <span className="chip">리마인드 발송됨</span> : ""}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </section>

          <section id="my-waiting_escalation">
            <h3>이관 회신 대기</h3>
            {empty("waiting_escalation") || (
              <table className="inbox-table">
                <thead><tr><th>문의 번호</th><th>고객사·등급</th><th>이관 부서</th><th>이관 시각</th><th>경과</th></tr></thead>
                <tbody>{data.waiting_escalation.map((r) => (
                  <tr key={r.sub_ticket_id} {...open(r)}>
                    <td><Ticket row={r} /></td><td>{r.company_masked} · {r.customer_tier}</td><td>{r.escalated_to}</td>
                    <td>{when(r.escalated_at_utc)}</td><td>{hours(r.elapsed_h)}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
