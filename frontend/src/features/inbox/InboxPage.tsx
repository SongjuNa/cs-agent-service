// SCR-02 접수함 (FR-029). 목업 v1.42 viewInbox 배치: 화면 머리 → [요약 칸막이 탭 → 필터 판 → 표 → 쪽 넘김] 카드 하나.
// 필터·정렬·쪽은 주소 쿼리에 둬 상세에서 돌아와도 그대로다(SCR-02-AC-8).
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Inbox, type InboxRow } from "../../api";
import { useAgents, useDepartments, useInboxCounts } from "../../app/queries";
import { ALERT, CATEGORY, CHANNEL, DEPTH, NEXT_ACTION, STATUS, TURN_GROUP, label } from "../../app/labels";
import { useSession } from "../../app/session";
import { Icon } from "../../app/icons";
import {
  AlertChip, Banner, Button, Chip, DataTable, EmptyState, formatRemaining, PageHeader, Pager, PriorityBadge, Tabs,
  type Column,
} from "../../ui";
import { ALL_ALERTS, hasFilters, rememberInboxOrder, rememberInboxUrl, SIZE, useInbox } from "./inboxQuery";
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
  { key: "waiting", label: "회신 대기", count: "waiting" },
  { key: "escalated", label: "이관", count: "escalated" },
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

const columnsFor = (sel: Set<string>, toggle: (id: string) => void, pageAll: boolean, togglePage: () => void, showAssignee: boolean): Column<Row>[] => [
  { key: "pick", header: <input type="checkbox" aria-label="이 쪽 전체 선택" checked={pageAll} onChange={togglePage} onClick={(e) => e.stopPropagation()} />,
    render: (r) => <input type="checkbox" aria-label={`${r.ticket_id} #${r.seq} 선택`} checked={sel.has(r.sub_ticket_id)} onChange={() => toggle(r.sub_ticket_id)} onClick={(e) => e.stopPropagation()} /> },
  { key: "seq", header: "순번", align: "right", render: (r) => <span className="sub">{r.__index}</span> },
  { key: "ticket_id", header: "티켓 번호", sortKey: "ticket_id", render: (r) => (
    <a className="ui-tid" href={`/tickets/${encodeURIComponent(r.ticket_id)}`} onClick={(e) => e.preventDefault()}>
      {r.ticket_id}{r.inquiry_count > 1 ? ` #${r.seq}` : ""}
    </a>
  ) },
  { key: "channel", header: "채널", render: (r) => (
    <span className="inbox-chan">{label(CHANNEL, r.channel)}{r.status === "NEW" && <span className="inbox-new" title="새로 접수되어 아직 처리를 시작하지 않은 문의입니다">NEW</span>}</span>
  ) },
  { key: "subject", header: "문의", render: (r) => (
    <>
      {(r.summary_ko ?? r.inquiry_subject)
        ? <span className="inbox-subject" title={r.summary_ko ? `AI 요약: ${r.summary_ko}` : (r.inquiry_subject ?? undefined)} data-summary={r.summary_ko ? "ai" : "subject"}>{r.summary_ko ?? r.inquiry_subject}</span>
        : <span className="sub">—</span>}
      {r.memo_count > 0 && <span className="inbox-memo" title={`내부 메모 ${r.memo_count}건`}>메모 {r.memo_count}</span>}
    </>
  ) },
  { key: "received", header: "접수 시각", sortKey: "received_at", render: (r) => <span className="sub">{time(r.received_at_utc)}</span> },
  { key: "company", header: "고객사·등급", render: (r) => (
    <span className="inbox-co">
      <span className="inbox-co__name" title={r.company_masked ?? undefined}>{r.company_masked ?? "—"}</span>
      {r.customer_tier && <Chip tone="outline">{r.customer_tier}</Chip>}
      {r.country && <span className="sub">{r.country}</span>}
    </span>
  ) },
  { key: "product", header: "제품", render: (r) => r.product_code
    ? <span title={r.product_name ?? undefined}>{r.product_code}</span>
    : <Chip tone="crit">미확인</Chip> },
  { key: "category", header: "유형", render: (r) => (
    <>{label(CATEGORY, r.category_code)}{r.inquiry_count > 1 && <span className="sub"> 복합 {r.inquiry_count}건 중 {r.seq}</span>}</>
  ) },
  { key: "priority", header: "우선순위", sortKey: "priority", render: (r) => r.priority
    ? <>{r.priority === "P1" && <span className="inbox-p1dot" title="우선순위 P1" />}<PriorityBadge priority={r.priority} adjusted={!!r.priority_adjusted} />
        {r.turn !== "DONE" && <span className={`inbox-depth inbox-depth--${r.review_depth.toLowerCase()}`} title="검토 모드: 얼마나 깊게 봐야 하는지">{DEPTH[r.review_depth]}</span>}</>
    : <span className="sub">—</span> },
  { key: "status", header: "처리 상태 · 다음 행동", sortKey: "status", render: (r) => (
    // 이관받은 줄은 상태 칸에 "{원 부서}에서 이관됨"만 보인다(FR-029 처리 1)
    <>
      {r.escalated_in_from ? <>{r.escalated_in_from}에서 이관됨</> : (
        <>
          {label(STATUS, r.status)}
          {r.status === "ESCALATED" && r.escalated_to ? <span className="sub"> → {r.escalated_to}</span> : null}
        </>
      )}
      <span className={`inbox-action inbox-action--${r.turn.toLowerCase()}`} title="누구 차례인지는 상세의 '지금 할 일'과 같은 기준입니다">
        {r.turn === "ME" && "→ "}{label(NEXT_ACTION, r.next_action)}{showAssignee && r.assignee_masked ? <span className="sub"> · {r.assignee_masked}</span> : null}
      </span>
    </>
  ) },
  { key: "remaining", header: "남은 시간", sortKey: "remaining", align: "right", render: remainingCell },
  { key: "alerts", header: "경고", render: (r) => r.alerts.length ? <span className="inbox-chips">{r.alerts.map((a) => <AlertChip key={a} alert={a} />)}</span> : null },
  { key: "needs_info", header: "정보 요청", render: (r) => r.needs_info ? <Chip tone="neg">필요</Chip> : <span className="sub">—</span> },
  { key: "draft", header: "승인 대기", render: (r) => r.has_unsent_draft ? <Chip tone="crit">승인 대기</Chip> : <span className="sub">—</span> },
  { key: "reminder", header: "리마인드", render: (r) => r.status === "WAITING_CUSTOMER" && r.reminder_sent ? <Chip>발송됨</Chip> : <span className="sub">—</span> },
];

/** 선택한 행을 엑셀에서 열 수 있는 CSV로 저장한다(한글이 깨지지 않게 BOM을 붙인다). 화면에 보이는 값 그대로다 */
function exportCsv(list: InboxRow[]) {
  const head = ["티켓 번호", "접수 시각(UTC)", "채널", "고객사", "등급", "제품", "유형", "우선순위", "상태", "남은 시간", "경고"];
  const cell = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const body = list.map((r) => [
    r.inquiry_count > 1 ? `${r.ticket_id} #${r.seq}` : r.ticket_id, time(r.received_at_utc), label(CHANNEL, r.channel),
    r.company_masked ?? "", r.customer_tier ?? "", r.product_code ?? "미확인", label(CATEGORY, r.category_code), r.priority ?? "",
    label(STATUS, r.status), r.status === "WAITING_CUSTOMER" ? "멈춤" : closed(r) || r.remaining_h == null ? "" : formatRemaining(Number(r.remaining_h)),
    r.alerts.map((a) => ALERT[a] ?? a).join(" · "),
  ]);
  const csv = "\uFEFF" + [head, ...body].map((row) => row.map(cell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = `접수함_${list.length}건.csv`;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

export function InboxPage({ onOpen, flash, navigate }: {
  onOpen: (ticketId: string, seq: number) => void;
  flash?: string | null;
  navigate: (path: string) => void;
}) {
  const { dept, asOf, agent } = useSession();
  const depts = useDepartments();
  const [search, setSearch] = useState(() => new URLSearchParams(window.location.search));
  const [text, setText] = useState(search.get("q") ?? "");
  const onlyMine = !!agent && search.get("m") !== "0"; // 처음 열면 내 담당만, 팀 전체는 m=0
  const inbox = useInbox(search, dept, asOf, agent);
  const counts = useInboxCounts(dept, asOf, search.get("include_closed") === "true", agent);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const qc = useQueryClient();
  const agentList = useAgents();
  const [to, setTo] = useState("");
  const [notice, setNotice] = useState<{ tone: "info" | "neg"; text: string } | null>(null);
  const last = useRef<Inbox | undefined>(undefined);
  if (inbox.data) last.current = inbox.data;
  const data = inbox.data ?? last.current;

  useEffect(() => { rememberInboxUrl(`/inbox${window.location.search}`); }, [search]);
  useEffect(() => { if (data) rememberInboxOrder(data.rows.map((r) => r.ticket_id)); }, [data]);
  useEffect(() => {
    const onPop = () => setSearch(new URLSearchParams(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  /** 선택한 문의의 담당을 바꾼다(변경 add-reassign). 건너뛴 문의는 사유와 함께 알린다 */
  async function reassign(subIds: string[], name: string) {
    try {
      const res = await api.assign(subIds, name);
      const skipped = res.skipped.length ? ` · ${res.skipped.length}건은 바꾸지 못함(${[...new Set(res.skipped.map((s) => s.reason))].join(", ")})` : "";
      setNotice({ tone: res.moved.length ? "info" : "neg", text: res.moved.length ? `${res.moved.length}건을 ${name === agent ? "내가 맡았습니다" : `${name}에게 넘겼습니다`}${skipped}` : `바뀐 문의가 없습니다${skipped}` });
      setPicked(new Set()); setTo("");
      void qc.invalidateQueries({ queryKey: ["inbox"] }); void qc.invalidateQueries({ queryKey: ["inbox-counts"] });
      void qc.invalidateQueries({ queryKey: ["mywork-now"] }); void qc.invalidateQueries({ queryKey: ["workload"] });
    } catch (e) {
      setNotice({ tone: "neg", text: e instanceof ApiError ? e.message : "담당을 바꾸지 못했습니다. 다시 시도하세요" });
    }
  }

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
  const firstMine = data?.rows.find((r) => r.turn === "ME");
  const scope = onlyMine ? "내 담당" : "팀 전체";
  const c = data?.counts;
  const head = (
    <PageHeader title="접수함"
      meta={dept ? `${deptName ?? dept} (${dept}) · ${scope} ${c?.total ?? "…"}건 중 ${c ? (c.turn_me > 0 ? `지금 처리할 문의 ${c.turn_me}건${c.breach ? ` · 기한 초과 ${c.breach}` : ""}${c.risk ? ` · 기한 임박 ${c.risk}` : ""}` : "지금 처리할 문의 없음") : "…"}` : undefined}
      actions={<>
        {firstMine && <Button variant="primary" onClick={() => onOpen(firstMine.ticket_id, firstMine.seq)} title="내가 처리할 문의를 위에서부터 차례로 엽니다">다음 문의 처리 시작 <b className="ui-tid">{firstMine.ticket_id}</b></Button>}
        {agent && (
          <div className="inbox-scope" role="group" aria-label="보기 범위" title="누구에게 배정된 문의를 볼지 고릅니다">
            <button type="button" className={onlyMine ? "is-on" : ""} aria-pressed={onlyMine} onClick={() => update((q) => q.delete("m"))}>내 담당{counts.data ? <b>{counts.data.mine}</b> : null}</button>
            <button type="button" className={!onlyMine ? "is-on" : ""} aria-pressed={!onlyMine} onClick={() => update((q) => q.set("m", "0"))}>팀 전체{counts.data ? <b>{counts.data.total}</b> : null}</button>
          </div>
        )}
        <a className="ui-btn inbox-link-btn" href="/intake" onClick={(e) => { e.preventDefault(); navigate("/intake"); }}>문의 접수</a>
      </>} />
  );

  if (!dept) {
    return <>{head}{flash && <Banner tone="neg">{flash}</Banner>}<EmptyState title="부서를 선택하세요">왼쪽 위 프로필을 눌러 부서와 상담원을 고릅니다.</EmptyState></>;
  }

  const page = Number(search.get("page") ?? "1") || 1;
  const sort = search.get("sort") ?? undefined;
  const flags = ["alert", "needs_info", "has_draft"].filter((k) => search.has(k));
  const onlyStatus = (v: string) => flags.length === 0 && search.get("status") === v;
  const summaryOn = search.get("alert") === ALL_ALERTS && flags.length === 1 && !search.has("status") ? "alert"
    : search.get("needs_info") === "true" && flags.length === 1 && !search.has("status") ? "needs_info"
    : search.get("has_draft") === "true" && flags.length === 1 && !search.has("status") ? "has_draft"
    : onlyStatus("WAITING_CUSTOMER") ? "waiting"
    : onlyStatus("ESCALATED") ? "escalated"
    : flags.length === 0 && !search.has("status") ? "all" : "";

  function pickSummary(key: string) {
    update((q) => {
      q.delete("alert"); q.delete("needs_info"); q.delete("has_draft"); q.delete("status");
      if (key === "waiting") q.set("status", "WAITING_CUSTOMER");
      if (key === "escalated") q.set("status", "ESCALATED");
      if (key === "alert") q.set("alert", ALL_ALERTS);
      if (key === "needs_info" || key === "has_draft") q.set(key, "true");
    });
  }

  const rows = (data?.rows ?? []).map((r, i) => ({ ...r, __index: (page - 1) * SIZE + i + 1 }));
  const filtered = hasFilters(search);
  // 선택은 지금 쪽에 보이는 행만 센다. 쪽이나 필터를 바꿔 사라진 행은 선택에서 뺀다
  const shown = new Set(rows.map((r) => r.sub_ticket_id));
  const chosen = rows.filter((r) => picked.has(r.sub_ticket_id));
  const pageAll = rows.length > 0 && chosen.length === rows.length;
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const togglePage = () => setPicked((p) => { const n = new Set([...p].filter((id) => shown.has(id))); if (!pageAll) rows.forEach((r) => n.add(r.sub_ticket_id)); else rows.forEach((r) => n.delete(r.sub_ticket_id)); return n; });

  return (
    <>
      {head}
      {flash && <Banner tone="neg">{flash}</Banner>}
      {inbox.isError && (
        <Banner tone="neg" action={<Button size="sm" onClick={() => void inbox.refetch()}>새로고침</Button>}>{FAIL}</Banner>
      )}
      {notice && <Banner tone={notice.tone} action={<Button size="sm" variant="ghost" onClick={() => setNotice(null)}>닫기</Button>}>{notice.text}</Banner>}
      {chosen.length > 0 && (
        <div className="inbox-bulk" role="region" aria-label="선택한 문의 일괄 처리">
          <b>{chosen.length}건 선택</b>
          {agent && chosen.some((r) => r.assignee_masked !== agent) && (
            <Button size="sm" onClick={() => void reassign(chosen.map((r) => r.sub_ticket_id), agent)}>내가 맡기</Button>
          )}
          <select className="inbox-bulk__select" aria-label="넘길 상담원" value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">담당자 변경…</option>
            {(agentList.data ?? []).filter((a) => a.dept === dept).map((a) => <option key={a.name} value={a.name}>{a.name}{a.name === agent ? " (나)" : ""}</option>)}
          </select>
          <Button size="sm" disabled={!to} onClick={() => void reassign(chosen.map((r) => r.sub_ticket_id), to)}>변경</Button>
          <Button size="sm" onClick={() => exportCsv(chosen)}>내보내기 (CSV)</Button>
          <span className="inbox-bulk__grow" />
          <Button variant="ghost" size="sm" onClick={() => setPicked(new Set())}>선택 해제</Button>
        </div>
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
            <button type="button" className={`inbox-newchip${search.get("status") === "NEW" ? " is-on" : ""}`} aria-pressed={search.get("status") === "NEW"}
                    title="새로 접수되어 아직 처리를 시작하지 않은 문의만 봅니다"
                    onClick={() => update((q) => { if (q.get("status") === "NEW") q.delete("status"); else q.set("status", "NEW"); })}>
              새 문의{counts.data ? <b>{counts.data.new}</b> : null}
            </button>
            <button type="button" className={`inbox-newchip${search.get("depth") === "DEEP" ? " is-on" : ""}`} aria-pressed={search.get("depth") === "DEEP"}
                    title="긴급(안전·설비 정지)이거나 우선순위 P1이라 깊게 봐야 하는 문의만 봅니다"
                    onClick={() => update((q) => { if (q.get("depth") === "DEEP") q.delete("depth"); else q.set("depth", "DEEP"); })}>
              상세 검토{counts.data ? <b>{counts.data.deep}</b> : null}
            </button>
          </form>
        </div>

        <DataTable<Row>
          caption="접수함 목록"
          columns={columnsFor(picked, toggle, pageAll, togglePage, !onlyMine)}
          groupHeader={sort ? undefined : (r, prev) => (!prev || TURN_GROUP[prev.turn] !== TURN_GROUP[r.turn]
            ? <><b>{TURN_GROUP[r.turn]}</b>{r.turn === "ME" && c ? <span className="sub">{c.turn_me}건</span> : null}</> : null)}
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
