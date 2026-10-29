// SCR-07 고객 관리 (화면 명세 SCR-07, FR 초안 01, 변경 add-customer-views). 읽기만.
// 배치는 목업 v1.42 `viewCustomers`·`viewCustomer`·`viewCustMap`: 탭 "고객 목록 / 나라별" → 등급 요약 → 거르기 → 표.
// 나라별은 지도 그림 대신 표(proposal 범위 밖). 상세 주소는 /customers/{id}(목업 #c-{id} 대신, 티켓 상세와 같은 방식)
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type CustomerDetail, type CustomerRows } from "../../api";
import { CATEGORY, label } from "../../app/labels";
import { useSession } from "../../app/session";
import { AlertChip, Banner, Button, Chip, DataTable, EmptyState, PageHeader, Pager, PriorityBadge, StatusBadge, Tabs, type Column } from "../../ui";
import { langName, utc } from "../ticket/CustomerTab";
import "./customers.css";

const SIZE = 50; // 화면 명세 SCR-07 size=50
const FAIL = "불러오지 못함. 새로고침";
const TIER_ORDER = ["PLATINUM", "GOLD", "SILVER", "STANDARD"];

type Row = CustomerRows["rows"][number];
type History = CustomerDetail["history"][number];

function readQuery() {
  const p = new URLSearchParams(window.location.search);
  return { tab: p.get("tab") === "countries" ? "countries" : "list", q: p.get("q") ?? "", tier: p.get("tier") ?? "",
           country: p.get("country") ?? "", page: Math.max(1, Number(p.get("page")) || 1) };
}

export function CustomersPage({ navigate }: { navigate: (path: string) => void }) {
  const [state, setState] = useState(readQuery);
  const [text, setText] = useState(state.q);
  const go = (next: Partial<ReturnType<typeof readQuery>>) => {
    const s = { ...state, page: 1, ...next };
    const p = new URLSearchParams();
    if (s.tab === "countries") p.set("tab", "countries");
    if (s.q) p.set("q", s.q);
    if (s.tier) p.set("tier", s.tier);
    if (s.country) p.set("country", s.country);
    if (s.page > 1) p.set("page", String(s.page));
    window.history.replaceState(null, "", `/customers${p.toString() ? `?${p}` : ""}`);
    setState(s);
  };

  return (
    <div className="cu">
      <PageHeader title="고객 관리" meta="읽기 전용 · 연락처는 원문 그대로" />
      <section className="ui-card">
        <Tabs label="고객 관리 보기" value={state.tab} onChange={(k) => go({ tab: k })}
          items={[{ key: "list", label: "고객 목록" }, { key: "countries", label: "나라별" }]} />
        {state.tab === "countries"
          ? <Countries onCountry={(c) => { setText(""); go({ tab: "list", country: c, q: "", tier: "" }); }} />
          : <List state={state} text={text} setText={setText} go={go} onOpen={(id) => navigate(`/customers/${encodeURIComponent(id)}`)} />}
      </section>
    </div>
  );
}

function List({ state, text, setText, go, onOpen }: {
  state: ReturnType<typeof readQuery>; text: string; setText: (v: string) => void;
  go: (next: Partial<ReturnType<typeof readQuery>>) => void; onOpen: (id: string) => void;
}) {
  const params = new URLSearchParams({ page: String(state.page), size: String(SIZE) });
  if (state.q) params.set("q", state.q);
  if (state.tier) params.set("tier", state.tier);
  if (state.country) params.set("country", state.country);
  const q = useQuery({ queryKey: ["customers", params.toString()], queryFn: () => api.customerList(params), placeholderData: keepPreviousData });
  const data = q.data;
  const tiers = data ? TIER_ORDER.filter((t) => t in data.tier_counts).concat(Object.keys(data.tier_counts).filter((t) => !TIER_ORDER.includes(t))) : [];
  const all = data ? Object.values(data.tier_counts).reduce((a, b) => a + b, 0) : 0;

  const columns: Column<Row>[] = [
    { key: "id", header: "고객 ID", render: (r) => <span className="cu-id">{r.customer_id}</span> },
    { key: "company", header: "고객사", render: (r) => r.company_masked },
    { key: "tier", header: "등급", render: (r) => <Chip tone="outline">{r.tier}</Chip> },
    { key: "country", header: "나라", render: (r) => r.country },
    { key: "open", header: "미해결", align: "right", render: (r) => (r.open_count ? <b>{r.open_count}</b> : <span className="cu-sub">0</span>) },
    { key: "all", header: "전체 문의", align: "right", render: (r) => r.ticket_count },
    { key: "last", header: "최근 문의", render: (r) => <span className="cu-sub">{utc(r.last_received_at)}</span> },
  ];
  return (
    <>
      <div className="cu-tiers" role="group" aria-label="등급으로 거르기" data-testid="tiers">
        <button type="button" className={state.tier ? "cu-tier" : "cu-tier is-on"} onClick={() => go({ tier: "" })}>
          등록 고객 <b>{all}</b></button>
        {tiers.map((t) => (
          <button key={t} type="button" className={state.tier === t ? "cu-tier is-on" : "cu-tier"} onClick={() => go({ tier: state.tier === t ? "" : t })}
            data-tier={t}>{t} <b>{data!.tier_counts[t]}</b></button>
        ))}
      </div>
      <form className="cu-filter" onSubmit={(e) => { e.preventDefault(); go({ q: text.trim() }); }}>
        <label htmlFor="cu-q">고객 ID·고객사</label>
        <input id="cu-q" value={text} onChange={(e) => setText(e.target.value)} placeholder="CUST-0350 또는 고객사" />
        {state.country && <Chip tone="info">나라 {state.country} <button type="button" className="cu-x" aria-label="나라 거르기 지우기" onClick={() => go({ country: "" })}>×</button></Chip>}
        <Button type="submit" variant="primary">검색</Button>
      </form>
      {q.isError && <Banner tone="neg" title={FAIL} />}
      {!data ? <div className="cu-skeleton" aria-busy="true" /> : (
        <>
          <DataTable columns={columns} rows={data.rows} rowKey={(r) => r.customer_id} onRowClick={(r) => onOpen(r.customer_id)} stale={q.isFetching && q.isPlaceholderData}
            caption="고객 목록" empty={<EmptyState title="조건에 맞는 고객이 없습니다">검색어나 등급 필터를 바꿔 보세요</EmptyState>} />
          <div className="cu-pager"><Pager total={data.total} page={data.page} size={data.size} unit="명" onPage={(p) => go({ page: p })} /></div>
        </>
      )}
    </>
  );
}

function Countries({ onCountry }: { onCountry: (country: string) => void }) {
  const q = useQuery({ queryKey: ["countries"], queryFn: api.countries });
  type C = NonNullable<typeof q.data>[number];
  const columns: Column<C>[] = [
    { key: "country", header: "나라", render: (r) => <b>{r.country}</b> },
    { key: "customers", header: "고객 수", align: "right", render: (r) => r.customer_count },
    { key: "tickets", header: "전체 문의", align: "right", render: (r) => r.ticket_count },
    { key: "open", header: "미해결", align: "right", render: (r) => r.open_count },
  ];
  if (q.isError) return <Banner tone="neg" title={FAIL} />;
  if (!q.data) return <div className="cu-skeleton" aria-busy="true" />;
  return <DataTable columns={columns} rows={q.data} rowKey={(r) => r.country} onRowClick={(r) => onCountry(r.country)} caption="나라별 고객"
    empty={<EmptyState title="고객이 없습니다" />} />;
}

export function CustomerPage({ customerId, onOpen, navigate }: { customerId: string; onOpen: (ticketId: string) => void; navigate: (path: string) => void }) {
  const { asOf } = useSession();
  const q = useQuery({ queryKey: ["customer", customerId, asOf], queryFn: () => api.customer(customerId, asOf), retry: false });
  const back = <Button variant="ghost" onClick={() => navigate("/customers")}>고객 관리로</Button>;
  if (q.error instanceof ApiError && q.error.status === 404) {
    return <EmptyState title={`고객을 찾을 수 없습니다 ${customerId}`}>{back}</EmptyState>;
  }
  if (q.isError) return <Banner tone="neg" title={FAIL} action={back} />;
  const d = q.data;
  if (!d) return <div className="cu-skeleton" aria-busy="true" />;
  const columns: Column<History>[] = [
    { key: "ticket", header: "티켓", render: (h) => <span className="cu-id">{h.ticket_id}{h.inquiry_count > 1 && <span className="cu-sub"> #{h.seq}</span>}</span> },
    { key: "source", header: "원본 번호", render: (h) => <span className="cu-mono">{h.source_ticket_id ?? "—"}</span> },
    { key: "at", header: "접수 시각", render: (h) => <span className="cu-sub">{utc(h.received_at_utc)}</span> },
    { key: "cat", header: "유형", render: (h) => label(CATEGORY, h.category_code) },
    { key: "product", header: "제품", render: (h) => h.product_code ?? <span className="cu-sub">미확인</span> },
    { key: "prio", header: "우선순위", render: (h) => <PriorityBadge priority={h.priority} /> },
    { key: "status", header: "상태", render: (h) => <StatusBadge status={h.status} /> },
    { key: "alerts", header: "경고", render: (h) => <span className="cu-chips">{h.alerts.map((a) => <AlertChip key={a} alert={a} />)}</span> },
  ];
  return (
    <div className="cu" data-testid="customer-page">
      <section className="ui-card cu-head">
        <div className="cu-head__top">
          <h1 className="cu-head__id">{d.customer_id}</h1>
          <span className="cu-head__name">{d.company_masked}</span>
          <Chip tone="outline">{d.tier}</Chip>
          <span className="cu-head__back">{back}</span>
        </div>
        <dl className="cu-stats">
          <div><dt>미해결 문의</dt><dd data-testid="open-count">{d.open_count}</dd></div>
          <div><dt>기한 위험·위반</dt><dd className={d.alert_count ? "is-bad" : undefined}>{d.alert_count}</dd></div>
          <div><dt>나라</dt><dd>{d.country}</dd></div>
          <div><dt>최근 답장 언어</dt><dd>{langName(d.last_language)}</dd></div>
          <div><dt>최근 연락처 이메일</dt><dd>{d.last_contact_email ?? "—"}</dd></div>
        </dl>
      </section>
      <section className="ui-card">
        <div className="ui-card__head"><h2 className="ui-card__title">문의 이력</h2><span className="cu-sub">최근 순 · {d.history.length}건</span></div>
        <DataTable columns={columns} rows={d.history} rowKey={(h) => h.sub_ticket_id} onRowClick={(h) => onOpen(h.ticket_id)} caption="문의 이력"
          empty={<EmptyState title="문의 이력이 없습니다" />} />
      </section>
    </div>
  );
}
