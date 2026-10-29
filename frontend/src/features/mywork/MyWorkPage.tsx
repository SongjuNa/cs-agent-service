// SCR-04 나의 업무 현황 (화면 정의서 v1 SCR-04, 명세서 FR-047, 기술 명세서 §8-3). 숫자는 서버가 센 값을 그대로 보인다.
// 배치는 목업 v1.42 `viewHome`: 머리 → 인사말 → 숫자 칸 4개 → 탭 → 탭별 표. 탭은 주소(?tab=)에 남긴다.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { api, type WorkRow, type Workload } from "../../api";
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
        <Body data={data} agent={agent ?? ""} stale={q.isError} tab={tab} setTab={setTab}
              page={page} setPage={setPage} onOpen={onOpen} navigate={navigate} />
      )}
    </div>
  );
}

function Body({ data, agent, stale, tab, setTab, page, setPage, onOpen, navigate }: {
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
      </div>

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
