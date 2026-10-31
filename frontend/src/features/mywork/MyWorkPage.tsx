// SCR-04 나의 업무 현황 (화면 정의서 v1 SCR-04, 명세서 FR-047, 기술 명세서 §8-3). 숫자는 서버가 센 값을 그대로 보인다.
// 배치는 목업 v1.42 `viewHome`: 머리 → 인사말 → 숫자 칸 4개 → 탭 → 탭별 표. 탭은 주소(?tab=)에 남긴다.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { api, type InboxRow, type Performance, type WorkRow, type Workload } from "../../api";
import { ALERT, DEPTH, NEXT_ACTION, label } from "../../app/labels";
import { useDepartments } from "../../app/queries";
import { useSession } from "../../app/session";
import { AlertChip, Banner, Button, DataTable, EmptyState, PageHeader, Pager, PriorityBadge, StatusBadge, Tabs, formatRemaining, type Column } from "../../ui";
import { lastInboxUrl } from "../inbox/inboxQuery";
import "./mywork.css";

const REFRESH_MS = 5 * 60 * 1000; // FR-047 처리 6, §8-2 (FR-027 점검 주기와 같게)
const FAIL = "불러오지 못함. 새로고침"; // FR-047 예외 4행
const NO_SCOPE = "상단에서 이름과 부서를 고르세요"; // FR-047 예외 3행
const SCOPE_KEY = "cs-my-scope";
const PAGE = 10; // 목업 표 한 쪽 10줄

type Area = "risks" | "drafts" | "waiting_customer" | "waiting_escalation";
const TABS: { key: Area; label: string }[] = [
  { key: "risks", label: "기한 위험·위반" }, { key: "drafts", label: "승인 대기 초안" },
  { key: "waiting_customer", label: "고객 회신 대기" }, { key: "waiting_escalation", label: "이관 회신 대기" },
];

function savedScope(): "mine" | "dept" | null {
  try {
    const v = localStorage.getItem(SCOPE_KEY);
    return v === "mine" || v === "dept" ? v : null;
  } catch {
    return null;
  }
}

function tabFromUrl(): Area {
  const t = new URLSearchParams(window.location.search).get("tab");
  return TABS.some((x) => x.key === t) ? (t as Area) : "risks";
}

const hours = (h: string | number | null | undefined) => (h === null || h === undefined ? "—" : `${Number(h).toFixed(1)} h`);
const when = (at: string | null) => (at ? `${at.replace("T", " ").slice(0, 16)} UTC` : "—");

function greeting(): string {
  const hr = new Date().getHours();
  if (hr >= 5 && hr < 11) return "좋은 아침입니다";
  if (hr >= 11 && hr < 14) return "점심 시간 잘 보내셨나요";
  if (hr >= 14 && hr < 18) return "좋은 오후입니다";
  if (hr >= 18 && hr < 22) return "오늘도 수고 많으셨습니다";
  return "늦은 시간까지 수고 많으십니다";
}

function Ticket({ row }: { row: WorkRow }) {
  return <span className="mw-tid">{row.ticket_id}{row.inquiry_count > 1 && <span className="mw-seq"> #{row.seq}</span>}</span>;
}

/** 126h(리마인드)·168h(무응답 종료) 눈금 막대(SCR-04-L3) */
function WaitBar({ elapsed, remind, close }: { elapsed: number | null; remind: number; close: number }) {
  const pct = (h: number) => `${Math.min(100, Math.max(0, (h / close) * 100))}%`;
  const e = elapsed ?? 0;
  return (
    <span className="mw-bar" title={`리마인드 ${remind}h · 무응답 종료 ${close}h`} role="img"
          aria-label={`경과 ${e.toFixed(1)}h, 리마인드 ${remind}h, 종료 ${close}h`}>
      <span className={e >= remind ? "mw-bar__fill is-late" : "mw-bar__fill"} style={{ width: pct(e) }} />
      <span className="mw-bar__tick" style={{ left: pct(remind) }} />
    </span>
  );
}

export function MyWorkPage({ onOpen, navigate }: { onOpen: (id: string) => void; navigate: (path: string) => void }) {
  const { agent, dept, asOf } = useSession();
  const depts = useDepartments();
  const [scope, setScope] = useState<"mine" | "dept">(savedScope() ?? (agent ? "mine" : "dept"));
  const [tab, setTabState] = useState<Area>(tabFromUrl);
  const [page, setPage] = useState(1);
  const effective = scope === "mine" && !agent ? "dept" : scope;
  const ready = effective === "mine" ? Boolean(agent) : Boolean(dept);

  const q = useQuery({
    queryKey: ["workload", { dept, agent, scope: effective, asOf }],
    queryFn: () => {
      const p = new URLSearchParams({ scope: effective });
      if (dept) p.set("dept", dept);
      if (asOf) p.set("as_of", asOf);
      return api.workload(p);
    },
    enabled: ready,
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  });

  // 최신 목업: "새 문의" 타일과 "지금 처리할 건"은 접수함 API(내 담당 + 내 차례)에서 온다(변경 add-inbox-turn-depth의 값)
  const nowQ = useQuery({
    queryKey: ["mywork-now", { dept, agent, scope: effective, asOf }],
    queryFn: () => {
      const base = new URLSearchParams({ dept, size: "8", turn: "ME" });
      if (asOf) base.set("as_of", asOf);
      if (effective === "mine") { base.set("assignee", agent); base.set("me", agent); }
      const counts = new URLSearchParams({ dept, size: "1" });
      if (asOf) counts.set("as_of", asOf);
      if (effective === "mine") { counts.set("assignee", agent); counts.set("me", agent); }
      return Promise.all([api.inbox(base), api.inbox(counts)]).then(([list, all]) => ({ rows: list.rows, turnMe: list.counts.total, counts: all.counts }));
    },
    enabled: ready,
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  });

  function setTab(t: Area) {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", t);
    window.history.replaceState(null, "", url);
    setTabState(t);
    setPage(1);
  }
  function choose(next: "mine" | "dept") {
    setScope(next);
    setPage(1);
    try { localStorage.setItem(SCOPE_KEY, next); } catch { /* 기억 못 해도 된다 */ }
  }

  if (!ready) {
    return (
      <>
        <PageHeader title="나의 업무 현황" />
        <EmptyState title={NO_SCOPE} />
      </>
    );
  }

  const data = q.data;
  const deptName = depts.data?.find((d) => d.dept_code === dept)?.dept_name_ko ?? dept;
  const meta = effective === "mine"
    ? `${agent}, ${deptName} (${dept}) · 기준 ${data ? when(data.as_of) : "…"}`
    : `부서 전체 기준 · ${deptName} (${dept}) · 기준 ${data ? when(data.as_of) : "…"}`;

  return (
    <div className="mw">
      <PageHeader title="나의 업무 현황" meta={meta} actions={
        <>
          <div className="ui-tabs ui-tabs--seg mw-scope" role="group" aria-label="보는 범위">
            <button type="button" className="ui-tab" aria-pressed={effective === "mine"} aria-selected={effective === "mine"}
                    disabled={!agent} onClick={() => choose("mine")}>내 담당</button>
            <button type="button" className="ui-tab" aria-pressed={effective === "dept"} aria-selected={effective === "dept"}
                    disabled={!dept} onClick={() => choose("dept")}>부서 전체</button>
          </div>
          <Button onClick={() => navigate(lastInboxUrl())}>접수함 열기</Button>
        </>
      } />
      {q.isError && <Banner tone="neg" action={<Button size="sm" onClick={() => void q.refetch()}>새로고침</Button>}>{FAIL}</Banner>}
      {!data ? <div className="mw-skeleton" aria-busy="true" /> : (
        <Body data={data} agent={agent ?? ""} stale={q.isError} tab={tab} setTab={setTab} now={nowQ.data} mine={effective === "mine"}
              page={page} setPage={setPage} onOpen={onOpen} navigate={navigate} />
      )}
    </div>
  );
}

const SPANS = [7, 14, 30] as const;
const ratio = (n: number, d: number) => (d ? Math.round((n / d) * 100) : null);

/** 최신 목업 "내 실적". 최근 며칠 동안 내가 한 발송·이관·조정을 날짜별 막대로, 내 담당 문의의 기한 충족을 숫자로 보인다(서버가 센 값, 변경 add-my-performance) */
/** AI 자동 처리: 내 담당 문의 중 AI가 사람 승인 없이 보낸 것과 사후 검수 대기(변경 add-auto-send-views). 숫자는 내 실적 API가 센다 */
function AutoCard({ agent, navigate }: { agent: string; navigate: (path: string) => void }) {
  const { asOf } = useSession();
  const q = useQuery({
    queryKey: ["my-performance", { agent, asOf, span: 7 }],
    queryFn: () => { const p = new URLSearchParams({ days: "7" }); if (asOf) p.set("as_of", asOf); return api.performance(p); },
    placeholderData: keepPreviousData, refetchInterval: REFRESH_MS,
  });
  const a = q.data?.auto;
  if (!a || (a.sent === 0 && a.pending === 0)) return null;
  return (
    <section className="ui-card mw-auto" aria-label="AI 자동 처리" data-testid="my-auto">
      <b>AI 자동 처리</b>
      <span>최근 7일 내 담당 {a.sent}건을 AI가 사람 승인 없이 보냈고, 사후 검수 대기는 <b>{a.pending}건</b>입니다.</span>
      <Button size="sm" onClick={() => navigate("/inbox?auto=true")}>확인하기</Button>
    </section>
  );
}

function PerformanceCard({ agent }: { agent: string }) {
  const { asOf } = useSession();
  const [span, setSpan] = useState<number>(7);
  const q = useQuery({
    queryKey: ["my-performance", { agent, asOf, span }],
    queryFn: () => { const p = new URLSearchParams({ days: String(span) }); if (asOf) p.set("as_of", asOf); return api.performance(p); },
    placeholderData: keepPreviousData, refetchInterval: REFRESH_MS,
  });
  const d: Performance | undefined = q.data;
  const today = d?.daily[d.daily.length - 1];
  const max = Math.max(1, ...(d?.daily.map((x) => x.n) ?? [1]));
  const fr = d ? ratio(d.sla.fr_met, d.sla.fr_met + d.sla.fr_breached) : null;
  const res = d ? ratio(d.sla.res_ok, d.sla.window_total) : null;
  return (
    <section className="ui-card mw-perf" aria-label="내 실적" data-testid="my-performance">
      <header className="mw-perf__h">
        <b>내 실적</b>
        <span className="mw-perf__span" role="group" aria-label="기간">
          {SPANS.map((n) => <button key={n} type="button" aria-pressed={span === n} className={span === n ? "is-on" : ""} onClick={() => setSpan(n)}>{n}일</button>)}
        </span>
      </header>
      {q.isError && !d && <p className="mw-perf__err" role="alert">내 실적을 불러오지 못함</p>}
      {d && today && (
        <div className="mw-perf__body">
          <div className="mw-perf__nums">
            <div data-stat="today"><b>{today.n}</b><span>오늘 처리 (발송 {today.sent} · 이관 {today.escalated} · 조정 {today.adjusted})</span></div>
            <div data-stat="total"><b>{d.total}</b><span>최근 {d.days}일 처리 · 하루 평균 {(d.total / d.days).toFixed(1)}</span></div>
            <div data-stat="fr"><b>{fr ?? "—"}{fr !== null && "%"}</b><span>1차 응답 충족 (최근 {d.days}일 접수·내 담당 {d.sla.window_total}건)</span></div>
            <div data-stat="res"><b>{res ?? "—"}{res !== null && "%"}</b><span>해결 기한 내 (같은 기준)</span></div>
          </div>
          <div className="mw-perf__bars" role="img" aria-label={`최근 ${d.days}일 날짜별 처리 건수`}>
            {d.daily.map((x, i) => (
              <div key={x.date} className={i === d.daily.length - 1 ? "mw-perf__bar is-today" : "mw-perf__bar"} title={`${x.date} · ${x.n}건 (발송 ${x.sent} · 이관 ${x.escalated} · 조정 ${x.adjusted})`}>
                <i style={{ height: `${(x.n / max) * 100}%` }} />
                {(d.daily.length <= 14 || i % 5 === 0 || i === d.daily.length - 1) && <small>{Number(x.date.slice(8, 10))}</small>}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

type Now = { rows: InboxRow[]; turnMe: number; counts: { new: number } };

/** 최신 목업 "지금 처리할 건"과 "가장 급한 내 문의". 접수함의 내 차례 묶음 앞부분이다 */
function NowList({ now, mine, onOpen, navigate }: { now: Now; mine: boolean; onOpen: (id: string) => void; navigate: (path: string) => void }) {
  const scope = mine ? "" : "?m=0";
  const top = now.rows[0];
  return (
    <div className="mw-now">
      <section className="ui-card mw-now__list" aria-label="지금 처리할 건" data-testid="now-list">
        <header className="mw-now__h">
          <b>지금 처리할 건</b><span className="mw-sub">{now.turnMe}건</span>
          <button type="button" className="tk-link" onClick={() => navigate(`/inbox${scope}`)}>접수함에서 모두 보기</button>
        </header>
        {now.rows.length === 0 ? <p className="mw-now__empty">지금 처리할 일이 없습니다</p> : (
          <ul>
            {now.rows.map((r) => (
              <li key={r.sub_ticket_id}>
                <button type="button" onClick={() => onOpen(r.ticket_id)}>
                  <span className="mw-now__id">{r.ticket_id}{r.inquiry_count > 1 ? ` #${r.seq}` : ""}</span>
                  <span className="mw-now__t" title={r.summary_ko ?? r.inquiry_subject ?? undefined}>{r.summary_ko ?? r.inquiry_subject ?? r.product_code ?? "—"}</span>
                  {r.priority && <PriorityBadge priority={r.priority} adjusted={!!r.priority_adjusted} />}
                  <span className="mw-now__a">→ {label(NEXT_ACTION, r.next_action)}</span>
                  <span className="mw-sub">{DEPTH[r.review_depth]}</span>
                  {r.alerts.map((a) => <AlertChip key={a} alert={a} />)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {top && top.alerts.length > 0 && (
        <section className="ui-card mw-now__top" aria-label="가장 급한 내 문의" data-testid="most-urgent">
          <b>가장 급한 내 문의</b>
          <button type="button" onClick={() => onOpen(top.ticket_id)}>
            <span className="mw-now__id">{top.ticket_id}</span>
            <span>{top.summary_ko ?? top.inquiry_subject ?? top.product_code ?? ""}</span>
            <span className="mw-sub">{top.alerts.map((a) => label(ALERT, a)).join(" · ")}</span>
          </button>
        </section>
      )}
    </div>
  );
}

function Body({ data, agent, stale, tab, setTab, page, setPage, onOpen, navigate, now, mine }: {
  now?: Now; mine: boolean;
  data: Workload; agent: string; stale: boolean; tab: Area; setTab: (t: Area) => void;
  page: number; setPage: (p: number) => void; onOpen: (id: string) => void; navigate: (path: string) => void;
}) {
  // 인사말: 지금 처리할 건(회신·이관 대기 빼고) = 위험 표 중 대기 상태가 아닌 것은 셀 수 없어 위험·초안 합으로 대신하지 않는다.
  // 화면 명세 N-04-01: "기한이 지난 건 m건" = 위험·위반 표의 해결 BREACHED 수
  const breached = data.risks.filter((r) => r.alerts.includes("RES_BREACHED")).length;
  const checked = data.drafts.filter((d) => d.has_check).length;
  const reminded = data.waiting_customer.filter((w) => w.reminder_sent).length;
  const tile = (area: Area, k: string, sub: ReactNode, onClick: () => void, bad = false) => (
    <button type="button" className={tab === area ? "mw-k is-on" : "mw-k"} onClick={onClick} data-tile={area}>
      <span>{k}</span><b className={bad ? "is-bad" : undefined}>{data.tiles[area]}</b><em>{sub}</em>
    </button>
  );
  const rows: WorkRow[] = data[tab];
  const shown = rows.slice((page - 1) * PAGE, page * PAGE);
  const open = (r: WorkRow) => onOpen(r.ticket_id);

  return (
    <div className={stale ? "mw-body is-stale" : "mw-body"}>
      <p className="mw-greet" data-testid="greet">
        <b>{greeting()}{agent ? `, 상담원 ${agent}님.` : "."}</b>{" "}
        {data.tiles.risks || data.tiles.drafts
          ? <>기한 위험·위반 <b>{data.tiles.risks}건</b>{breached ? <>, 그중 해결 기한이 지난 건이 <b className="is-bad">{breached}건</b></> : null}, 승인 대기 초안 <b>{data.tiles.drafts}건</b>입니다.</>
          : "지금 급한 건이 없습니다."}
      </p>
      <div className="mw-tiles">
        {tile("drafts", "승인 대기 초안", `${checked}건에 확인 표시`, () => setTab("drafts"))}
        {tile("risks", "기한 위험·위반", breached ? `해결 기한 지남 ${breached}` : "기한 안", () => setTab("risks"), breached > 0)}
        {tile("waiting_customer", "고객 회신 대기", `리마인드 발송 ${reminded}`, () => navigate("/inbox?status=WAITING_CUSTOMER"))}
        {tile("waiting_escalation", "이관 회신 대기", "전문 부서 회신 전", () => setTab("waiting_escalation"))}
        {now && (
          <button type="button" className="mw-k" data-tile="new" onClick={() => navigate(`/inbox?status=NEW${mine ? "" : "&m=0"}`)}>
            <span>새 문의</span><b>{now.counts.new}</b><em>아직 처리를 시작하지 않음</em>
          </button>
        )}
      </div>
      {now && <NowList now={now} mine={mine} onOpen={onOpen} navigate={navigate} />}

      <section className="ui-card mw-card">
        <Tabs label="나의 업무 현황" value={tab} onChange={(k) => setTab(k as Area)}
              items={TABS.map((t) => ({ key: t.key, label: t.label, count: data.tiles[t.key] }))} />
        <Table area={tab} rows={shown} onRow={open} empty={data.empty[tab]} stale={stale} />
        <div className="mw-pager"><Pager total={rows.length} page={page} size={PAGE} onPage={setPage} /></div>
      </section>

      <section className="ui-card mw-today" aria-label="오늘 처리한 건수">
        <h3>오늘 처리한 건수 <span className="mw-sub">{data.as_of.slice(0, 10)} UTC</span></h3>
        <div className="mw-today__n" data-testid="today">
          <span>발송<b>{data.today.sent}</b></span><span>이관<b>{data.today.escalated}</b></span><span>우선순위 조정<b>{data.today.adjusted}</b></span>
          {data.sla_unset > 0 && (
            <button type="button" className="tk-link" onClick={() => navigate(lastInboxUrl())}>SLA 미정 {data.sla_unset}건</button>
          )}
        </div>
      </section>
      {mine && agent && <AutoCard agent={agent} navigate={navigate} />}
      {mine && agent && <PerformanceCard agent={agent} />}
    </div>
  );
}

function Table({ area, rows, onRow, empty, stale }: { area: Area; rows: WorkRow[]; onRow: (r: WorkRow) => void; empty: string; stale: boolean }) {
  const ticket: Column<WorkRow> = { key: "ticket", header: "티켓", render: (r) => <Ticket row={r} /> };
  const company: Column<WorkRow> = { key: "company", header: "고객사·등급", render: (r) => <>{r.company_masked} <span className="mw-sub">{r.customer_tier}</span></> };
  const prio: Column<WorkRow> = { key: "priority", header: "우선순위", render: (r) => <PriorityBadge priority={r.priority} /> };
  const columns: Record<Area, Column<WorkRow>[]> = {
    risks: [ticket, company, prio,
      { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status} /> },
      { key: "alerts", header: "경고", render: (r) => <span className="mw-chips">{(r.alerts ?? []).map((a) => <AlertChip key={a} alert={a} />)}</span> },
      { key: "left", header: "해결 남은 시간", align: "right",
        render: (r) => <span className={Number(r.remaining_h) < 0 ? "tk-neg" : undefined}>{formatRemaining(r.remaining_h === null || r.remaining_h === undefined ? null : Number(r.remaining_h))}</span> }],
    drafts: [ticket,
      { key: "type", header: "종류", render: (r) => (r.message_type === "INFO_REQUEST" ? "정보 요청" : r.message_type === "FINAL_REPLY" ? "답변" : "진행 안내") },
      prio,
      { key: "made", header: "만든 시각", render: (r) => <span className="mw-sub">{when(r.created_at_utc ?? null)}</span> },
      { key: "check", header: "확인 표시", render: (r) => (r.has_check ? <span className="mw-check" title="실패한 자동 검사가 있음. 상세에서 확인">● 확인 필요</span> : null) }],
    waiting_customer: [ticket, company,
      { key: "req", header: "정보 요청 발송", render: (r) => <span className="mw-sub">{when(r.requested_at_utc ?? null)}</span> },
      { key: "bar", header: "126h 리마인드 · 168h 종료", render: (r) => <WaitBar elapsed={r.elapsed_h ?? null} remind={r.remind_at_h ?? 126} close={r.close_at_h ?? 168} /> },
      { key: "elapsed", header: "경과", align: "right", render: (r) => hours(r.elapsed_h) },
      { key: "remind", header: "리마인드", render: (r) => (r.reminder_sent ? <span className="mw-sent">리마인드 발송됨</span> : null) }],
    waiting_escalation: [ticket, company,
      { key: "to", header: "이관 부서", render: (r) => r.escalated_to },
      { key: "at", header: "이관 시각", render: (r) => <span className="mw-sub">{when(r.escalated_at_utc ?? null)}</span> },
      { key: "elapsed", header: "경과", align: "right", render: (r) => hours(r.elapsed_h) }],
  };
  return (
    <DataTable columns={columns[area]} rows={rows} onRowClick={onRow} stale={stale} caption={TABS.find((t) => t.key === area)?.label}
               rowKey={(r) => `${r.sub_ticket_id}-${r.message_id ?? ""}`} empty={<EmptyState title={empty} />} />
  );
}
