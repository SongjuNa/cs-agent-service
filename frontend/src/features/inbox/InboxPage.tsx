// SCR-02 접수함 (FR-029). 목업 v1.42 viewInbox 배치: 화면 머리 → [요약 칸막이 탭 → 필터 판 → 표 → 쪽 넘김] 카드 하나.
// 필터·정렬·쪽은 주소 쿼리에 둬 상세에서 돌아와도 그대로다(SCR-02-AC-8).
import { useEffect, useRef, useState } from "react";
import type { Inbox, InboxRow } from "../../api";
import { useDepartments, useInboxCounts } from "../../app/queries";
import { CATEGORY, CHANNEL, STATUS, label } from "../../app/labels";
import { useSession } from "../../app/session";
import { Icon } from "../../app/icons";
import {
  AlertChip, Banner, Button, Chip, DataTable, EmptyState, formatRemaining, PageHeader, Pager, PriorityBadge, Tabs,
  type Column,
} from "../../ui";
import { ALL_ALERTS, hasFilters, rememberInboxUrl, SIZE, useInbox } from "./inboxQuery";
import "./inbox.css";

const FAIL = "목록을 불러오지 못함. 새로고침"; // FR-029 예외 4행
const DEBOUNCE_MS = 300; // SCR-02 "입력 멈춘 뒤 0.3초"
const MAX_Q = 100; // SCR-02 입력 검증(구현 선택)

const SELECTS = [
  { name: "status", label: "상태", options: Object.entries(STATUS) },
  { name: "priority", label: "우선순위", options: ["P1", "P2", "P3", "P4"].map((p) => [p, p]) },
  { name: "alert", label: "경고", options: [[ALL_ALERTS, "경고 있음"], ["FR_AT_RISK", "1차 응답 임박"], ["FR_BREACHED", "1차 응답 지남"],
    ["RES_AT_RISK", "해결 기한 임박"], ["RES_BREACHED", "해결 기한 지남"]] },
  { name: "channel", label: "채널", options: Object.entries(CHANNEL) },
] as const;
const CHECKS = [["needs_info", "정보 요청 필요"], ["has_draft", "미발송 초안"], ["composite", "복합 문의"]] as const;

// 요약 칸막이 탭 (SCR-02-S1). 누르면 그 필터 하나만 켠다
const SUMMARY = [
  { key: "all", label: "전체", count: "total" },
  { key: "alert", label: "경고", count: "alert" },
  { key: "needs_info", label: "정보 요청 필요", count: "needs_info" },
  { key: "has_draft", label: "미발송 초안", count: "has_draft" },
] as const;

const time = (iso: string | null) => (iso ? iso.replace("T", " ").slice(0, 16) : "—");
const closed = (r: InboxRow) => r.status === "RESOLVED" || r.status === "CLOSED";

function remainingCell(r: InboxRow) {
  if (r.status === "WAITING_CUSTOMER") return <span className="sub">멈춤</span>;
  if (r.res_status === "MET" || closed(r)) return <span className="sub">—</span>;
  if (r.remaining_h === null || r.remaining_h === undefined) return <span className="sub">SLA 미정</span>;
  return <span className={r.res_status === "BREACHED" ? "neg-t" : undefined}>{formatRemaining(Number(r.remaining_h))}</span>;
}

type Row = InboxRow & { __index: number }; // __index = 순번(이 쪽까지 센 번호)

const COLUMNS: Column<Row>[] = [
  { key: "seq", header: "순번", align: "right", render: (r) => <span className="sub">{r.__index}</span> },
  { key: "ticket_id", header: "티켓 번호", sortKey: "ticket_id", render: (r) => (
    <a className="ui-tid" href={`/tickets/${encodeURIComponent(r.ticket_id)}`} onClick={(e) => e.preventDefault()}>
      {r.ticket_id}{r.inquiry_count > 1 ? ` #${r.seq}` : ""}
    </a>
  ) },
  { key: "received", header: "접수 시각", sortKey: "received_at", render: (r) => <span className="sub">{time(r.received_at_utc)}</span> },
  { key: "channel", header: "채널", render: (r) => label(CHANNEL, r.channel) },
  { key: "company", header: "고객사·등급", render: (r) => (
    <span className="inbox-co">
      <span className="inbox-co__name" title={r.company_masked ?? undefined}>{r.company_masked ?? "—"}</span>
      {r.customer_tier && <Chip tone="outline">{r.customer_tier}</Chip>}
    </span>
  ) },
  { key: "product", header: "제품", render: (r) => r.product_code
    ? <span title={r.product_name ?? undefined}>{r.product_code}</span>
    : <Chip tone="crit">미확인</Chip> },
  { key: "category", header: "유형", render: (r) => (
    <>{label(CATEGORY, r.category_code)}{r.inquiry_count > 1 && <span className="sub"> 복합 {r.inquiry_count}건 중 {r.seq}</span>}</>
  ) },
  { key: "priority", header: "우선순위", sortKey: "priority", render: (r) => r.priority
    ? <>{r.priority === "P1" && <span className="inbox-p1dot" title="우선순위 P1" />}<PriorityBadge priority={r.priority} adjusted={!!r.priority_adjusted} /></>
    : <span className="sub">—</span> },
  { key: "status", header: "처리 상태", sortKey: "status", render: (r) => (
    <>
      {label(STATUS, r.status)}
      {r.escalated_in_from ? <span className="sub"> {r.escalated_in_from}에서 이관됨</span>
        : r.status === "ESCALATED" && r.escalated_to ? <span className="sub"> → {r.escalated_to}</span> : null}
    </>
  ) },
  { key: "remaining", header: "남은 시간", sortKey: "remaining", align: "right", render: remainingCell },
  { key: "alerts", header: "경고", render: (r) => r.alerts.length ? <span className="inbox-chips">{r.alerts.map((a) => <AlertChip key={a} alert={a} />)}</span> : null },
  { key: "needs_info", header: "정보 요청", render: (r) => r.needs_info ? <Chip tone="neg">필요</Chip> : <span className="sub">—</span> },
  { key: "draft", header: "승인 대기", render: (r) => r.has_unsent_draft ? <Chip tone="crit">승인 대기</Chip> : <span className="sub">—</span> },
  { key: "reminder", header: "리마인드", render: (r) => r.status === "WAITING_CUSTOMER" && r.reminder_sent ? <Chip>발송됨</Chip> : <span className="sub">—</span> },
];

export function InboxPage({ onOpen, flash, navigate }: {
  onOpen: (ticketId: string, seq: number) => void;
  flash?: string | null;
  navigate: (path: string) => void;
}) {
  const { dept, asOf } = useSession();
  const depts = useDepartments();
  const [search, setSearch] = useState(() => new URLSearchParams(window.location.search));
  const [text, setText] = useState(search.get("q") ?? "");
  const inbox = useInbox(search, dept, asOf);
  const counts = useInboxCounts(dept, asOf, search.get("include_closed") === "true");
  const last = useRef<Inbox | undefined>(undefined);
  if (inbox.data) last.current = inbox.data;
  const data = inbox.data ?? last.current;

  useEffect(() => { rememberInboxUrl(`/inbox${window.location.search}`); }, [search]);
  useEffect(() => {
    const onPop = () => setSearch(new URLSearchParams(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function update(change: (q: URLSearchParams) => void, keepPage = false) {
    const q = new URLSearchParams(search);
    change(q);
    if (!keepPage) q.delete("page");
    const qs = q.toString();
    window.history.replaceState(null, "", `/inbox${qs ? `?${qs}` : ""}`);
    setSearch(q);
  }

  // 검색어: 입력이 멈추고 0.3초 뒤 1쪽부터 (빈 값이면 q를 보내지 않는다)
  useEffect(() => {
    const value = text.trim().slice(0, MAX_Q);
    if (value === (search.get("q") ?? "")) return;
    const timer = setTimeout(() => update((q) => { if (value) q.set("q", value); else q.delete("q"); }), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }); // 매 입력마다 다시 건다

  const deptName = depts.data?.find((d) => d.dept_code === dept)?.dept_name_ko;
  const head = (
    <PageHeader title="접수함"
      meta={dept ? `${deptName ?? dept} (${dept}), 경고 있는 문의를 위에, 그 안에서 남은 시간이 적은 순` : undefined}
      actions={<a className="ui-btn inbox-link-btn" href="/intake" onClick={(e) => { e.preventDefault(); navigate("/intake"); }}>문의 접수</a>} />
  );

  if (!dept) {
    return <>{head}{flash && <Banner tone="neg">{flash}</Banner>}<EmptyState title="부서를 선택하세요">왼쪽 위 프로필을 눌러 부서와 상담원을 고릅니다.</EmptyState></>;
  }

  const page = Number(search.get("page") ?? "1") || 1;
  const sort = search.get("sort") ?? undefined;
  const summaryOn = search.get("alert") === ALL_ALERTS && !search.has("needs_info") && !search.has("has_draft") ? "alert"
    : search.get("needs_info") === "true" && !search.has("alert") && !search.has("has_draft") ? "needs_info"
    : search.get("has_draft") === "true" && !search.has("alert") && !search.has("needs_info") ? "has_draft"
    : !search.has("alert") && !search.has("needs_info") && !search.has("has_draft") ? "all" : "";

  function pickSummary(key: string) {
    update((q) => {
      q.delete("alert"); q.delete("needs_info"); q.delete("has_draft");
      if (key === "alert") q.set("alert", ALL_ALERTS);
      if (key === "needs_info" || key === "has_draft") q.set(key, "true");
    });
  }

  const rows = (data?.rows ?? []).map((r, i) => ({ ...r, __index: (page - 1) * SIZE + i + 1 }));
  const filtered = hasFilters(search);

  return (
    <>
      {head}
      {flash && <Banner tone="neg">{flash}</Banner>}
      {inbox.isError && (
        <Banner tone="neg" action={<Button size="sm" onClick={() => void inbox.refetch()}>새로고침</Button>}>{FAIL}</Banner>
      )}
      <section className="ui-card inbox-card">
        <Tabs variant="seg" label="건수 요약" value={summaryOn} onChange={pickSummary}
          items={SUMMARY.map((s) => ({ key: s.key, label: s.label, count: counts.data ? counts.data[s.count] : undefined }))} />

        <div className="inbox-filters">
          <div className="inbox-filters__row inbox-filters__top">
            {SELECTS.map((f) => (
              <label key={f.name} className="inbox-field">
                <span>{f.label}</span>
                <select value={search.get(f.name) ?? ""} onChange={(e) => update((q) => { if (e.target.value) q.set(f.name, e.target.value); else q.delete(f.name); })}>
                  <option value="">전체</option>
                  {f.options.map(([v, l]) => (
                    <option key={v} value={v} disabled={f.name === "status" && (v === "RESOLVED" || v === "CLOSED") && search.get("include_closed") !== "true"}>{l}</option>
                  ))}
                </select>
              </label>
            ))}
            {CHECKS.map(([name, text]) => (
              <label key={name} className="inbox-check">
                <input type="checkbox" checked={search.get(name) === "true"} onChange={(e) => update((q) => { if (e.target.checked) q.set(name, "true"); else q.delete(name); })} />
                {text}
              </label>
            ))}
            <label className="inbox-switch">
              <input type="checkbox" role="switch" checked={search.get("include_closed") === "true"} onChange={(e) => update((q) => {
                if (e.target.checked) { q.set("include_closed", "true"); return; }
                q.delete("include_closed");
                if (q.get("status") === "RESOLVED" || q.get("status") === "CLOSED") q.delete("status"); // 종료 상태 필터는 종료 포함이 켜져야 쓴다(C-105)
              })} />
              종료 포함
            </label>
          </div>
          <form className="inbox-filters__row inbox-search" role="search" onSubmit={(e) => {
            e.preventDefault();
            const value = text.trim().slice(0, MAX_Q);
            update((q) => { if (value) q.set("q", value); else q.delete("q"); });
          }}>
            <label className="inbox-field inbox-field--grow">
              <span>검색</span>
              <input type="search" value={text} maxLength={MAX_Q} onChange={(e) => setText(e.target.value)}
                     placeholder="티켓 번호 또는 고객사를 입력하고 검색을 누르세요" aria-label="검색어" />
            </label>
            <button type="submit" className="ui-btn ui-btn--primary inbox-go"><Icon name="search" />검색</button>
          </form>
        </div>

        <DataTable<Row>
          caption="접수함 목록"
          columns={COLUMNS}
          rows={data ? rows : undefined}
          loading={inbox.isPending}
          stale={inbox.isError}
          rowKey={(r) => r.sub_ticket_id}
          onRowClick={(r) => onOpen(r.ticket_id, r.seq)}
          faded={closed}
          sort={sort}
          onSortChange={(next) => update((q) => { if (next) q.set("sort", next); else q.delete("sort"); }, false)}
          empty={
            <EmptyState title={data?.message ?? "처리할 티켓이 없습니다"}>
              {filtered && <Button variant="ghost" size="sm" onClick={() => { setText(""); update((q) => { for (const k of [...q.keys()]) if (k !== "sort") q.delete(k); }); }}>필터 지우기</Button>}
            </EmptyState>
          }
        />
        {data && <Pager total={data.counts.total} page={page} size={SIZE} onPage={(p) => update((q) => q.set("page", String(p)), true)} />}
      </section>
    </>
  );
}
