// SCR-08 기준정보 보기 (화면 명세 SCR-08, FR 초안 02·03·04, 변경 add-reference-views). 읽기만, 고치기·올리기 버튼 없음(AC-4).
// 배치는 목업 v1.42 `viewDocs`(색인 띠 → 종류 요약 → 거르기 → 표)와 `viewKnow`·`KTABS`(메뉴마다 탭 → 검색 → 표 10행씩).
// 메뉴 나누기는 화면 명세를 따른다: 처리 기한은 기타 관리 › 처리 기한, 부서 관리는 부서 목록만(2026-10-29 검토 자료 ②).
// 탭과 검색어, 쪽, 강조할 규칙은 주소(?tab=&q=&page=&rule=)에 남긴다. 거르기는 화면 안에서 한다(서버 호출 없음).
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { api, type DocumentRow, type Product, type RuleKind } from "../../api";
import { CATEGORY, URGENCY, label } from "../../app/labels";
import { Banner, Button, Chip, DataTable, EmptyState, Modal, PageHeader, Pager, PriorityBadge, Tabs, type Column } from "../../ui";
import { SourcePopup, type SourceTarget } from "../ticket/Popups";
import "./reference.css";

const FAIL = "불러오지 못함. 새로고침";
const PER = 10; // 목업 kTable 한 쪽 10행

// 문서 종류(기술 명세서 v1.4 §4-1 표)
export const DOC_TYPE: Record<string, string> = {
  DS: "데이터시트", IG: "설치·시운전 안내", TG: "트러블슈팅", RN: "릴리스노트", MG: "정비 안내", POL: "정책", FAQ: "제품군 FAQ",
};

/** 표 열. text는 검색과 CSV에, render는 화면에 쓴다(없으면 text) */
interface Col<R> { key: string; header: string; text: (r: R) => string | number | null | undefined; render?: (r: R) => ReactNode; align?: "right"; wrap?: boolean }

const toColumns = <R,>(cols: Col<R>[]): Column<R>[] =>
  cols.map((c) => ({ key: c.key, header: c.header, align: c.align, wrap: c.wrap, render: (r: R) => (c.render ? c.render(r) : c.text(r) ?? "—") }));

const matches = <R,>(cols: Col<R>[], q: string) => (r: R) =>
  !q || cols.some((c) => String(c.text(r) ?? "").toLowerCase().includes(q.toLowerCase()));

/** [CSV 내려받기]: 지금 거른 표 전체(모든 쪽)를 화면에서 CSV로 만든다(화면 명세 동작 표) */
function downloadCsv<R>(name: string, cols: Col<R>[], rows: R[]) {
  const cell = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const body = [cols.map((c) => cell(c.header)).join(","), ...rows.map((r) => cols.map((c) => cell(c.text(r))).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + body], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `${name}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

type UrlState = { tab: string; q: string; page: number; rule: string; type: string };

function useUrlState(base: string, firstTab: string): [UrlState, (next: Partial<UrlState>) => void] {
  const read = (): UrlState => {
    const p = new URLSearchParams(window.location.search);
    return { tab: p.get("tab") ?? firstTab, q: p.get("q") ?? "", page: Math.max(1, Number(p.get("page")) || 1), rule: p.get("rule") ?? "", type: p.get("type") ?? "" };
  };
  const [state, setState] = useState(read);
  const go = (next: Partial<UrlState>) => {
    const s = { ...state, page: 1, ...next };
    const p = new URLSearchParams();
    if (s.tab !== firstTab) p.set("tab", s.tab);
    if (s.type) p.set("type", s.type);
    if (s.q) p.set("q", s.q);
    if (s.page > 1) p.set("page", String(s.page));
    if (s.rule) p.set("rule", s.rule);
    window.history.replaceState(null, "", `${base}${p.toString() ? `?${p}` : ""}`);
    setState(s);
  };
  return [state, go];
}

function SearchBox({ value, onSearch, label: text, placeholder, children }: {
  value: string; onSearch: (q: string) => void; label: string; placeholder: string; children?: ReactNode;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <form className="rf-filter" onSubmit={(e) => { e.preventDefault(); onSearch(draft.trim()); }}>
      {children}
      <label htmlFor="rf-q">{text}</label>
      <input id="rf-q" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} />
      <Button type="submit" variant="primary">검색</Button>
    </form>
  );
}

/** 한 쪽 10행 표 + 쪽 넘기기 + 아래 행 수 */
function PagedTable<R>({ cols, rows, rowKey, page, onPage, onRowClick, marked, empty, caption }: {
  cols: Col<R>[]; rows: R[]; rowKey: (r: R) => string; page: number; onPage: (p: number) => void;
  onRowClick?: (r: R) => void; marked?: (r: R) => boolean; empty: string; caption: string;
}) {
  const pages = Math.max(1, Math.ceil(rows.length / PER));
  const cur = Math.min(page, pages);
  return (
    <>
      <DataTable columns={toColumns(cols)} rows={rows.slice((cur - 1) * PER, cur * PER)} rowKey={rowKey} onRowClick={onRowClick} marked={marked}
        caption={caption} empty={<EmptyState title={empty}>검색어를 바꿔 보세요</EmptyState>} />
      <div className="rf-pager">
        {rows.length > PER ? <Pager total={rows.length} page={cur} size={PER} unit="행" onPage={onPage} /> : rows.length > 0 && <span className="rf-sub">{rows.length}행</span>}
      </div>
    </>
  );
}

// ---------------- 문서 관리 (N-08-01, N-08-02) ----------------

export function DocsPage() {
  const [s, go] = useUrlState("/docs", "");
  const q = useQuery({ queryKey: ["ref-documents"], queryFn: api.documents });
  const [open, setOpen] = useState<DocumentRow | null>(null);
  const all = q.data ?? [];
  const cols: Col<DocumentRow>[] = [
    { key: "id", header: "문서 ID", text: (d) => d.doc_id, render: (d) => <b className="rf-mono">{d.doc_id}</b> },
    { key: "title", header: "제목", text: (d) => d.title, wrap: true },
    { key: "type", header: "종류", text: (d) => DOC_TYPE[d.doc_type] ?? d.doc_type },
    { key: "scope", header: "제품·제품군", text: (d) => d.product_code ?? d.family, render: (d) => <span className="rf-mono">{d.product_code ?? d.family ?? "—"}</span> },
    { key: "rev", header: "개정", text: (d) => d.revision },
    { key: "chars", header: "글자 수", align: "right", text: (d) => d.chars, render: (d) => d.chars?.toLocaleString("en-US") ?? "—" },
    { key: "sections", header: "절", align: "right", text: (d) => d.chunk_count },
    { key: "index", header: "색인", text: (d) => (d.chunk_count ? "색인됨" : "색인 없음"),
      render: (d) => (d.chunk_count ? <Chip tone="pos">색인됨</Chip> : <Chip tone="crit">색인 없음</Chip>) },
  ];
  const typed = s.type ? all.filter((d) => d.doc_type === s.type) : all;
  // 목업처럼 색인 없는 문서를 먼저, 그다음 문서 ID 순
  const rows = typed.filter(matches(cols.slice(0, 4), s.q)).sort((a, b) => Number(a.chunk_count > 0) - Number(b.chunk_count > 0) || a.doc_id.localeCompare(b.doc_id));
  const notIndexed = all.filter((d) => d.chunk_count === 0).length;
  const types = Object.keys(DOC_TYPE).filter((t) => all.some((d) => d.doc_type === t));

  return (
    <div className="rf">
      <PageHeader title="문서 관리" meta="답변 초안의 근거 문서 · 읽기 전용"
        actions={<Button onClick={() => downloadCsv("documents", cols, rows)} disabled={!q.data}>CSV 내려받기</Button>} />
      {notIndexed > 0 && <Banner tone="crit" title={`색인 안 됨 ${notIndexed}건`}>이 문서는 근거 검색에 나오지 않습니다.</Banner>}
      {q.isError && <Banner tone="neg" title={FAIL} />}
      <section className="ui-card">
        <div className="rf-summary" role="group" aria-label="종류로 거르기" data-testid="doc-types">
          {types.map((t) => (
            <button key={t} type="button" className={s.type === t ? "rf-sum is-on" : "rf-sum"} onClick={() => go({ type: s.type === t ? "" : t })}>
              {DOC_TYPE[t]} <b>{all.filter((d) => d.doc_type === t).length}</b></button>
          ))}
          {s.type && <button type="button" className="rf-sum" onClick={() => go({ type: "" })}>전체 보기</button>}
        </div>
        <SearchBox value={s.q} onSearch={(v) => go({ q: v })} label="문서 ID·범위" placeholder="TG-ACB-AS-2000, POL-RETURN">
          <label htmlFor="rf-type">종류</label>
          <select id="rf-type" value={s.type} onChange={(e) => go({ type: e.target.value })}>
            <option value="">전체</option>
            {types.map((t) => <option key={t} value={t}>{DOC_TYPE[t]}</option>)}
          </select>
        </SearchBox>
        {!q.data ? <div className="rf-skeleton" aria-busy="true" /> : (
          <PagedTable cols={cols} rows={rows} rowKey={(d) => d.doc_id} page={s.page} onPage={(p) => go({ page: p })} onRowClick={setOpen}
            empty="조건에 맞는 문서가 없습니다" caption="문서 목록" />
        )}
      </section>
      {open && <DocModal doc={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function DocModal({ doc, onClose }: { doc: DocumentRow; onClose: () => void }) {
  const q = useQuery({ queryKey: ["ref-document", doc.doc_id], queryFn: () => api.document(doc.doc_id), retry: false });
  const [chunk, setChunk] = useState<SourceTarget | null>(null);
  if (chunk) return <SourcePopup target={chunk} onClose={() => setChunk(null)} />;
  return (
    <Modal title={`${doc.doc_id} 절 목록`} onClose={onClose} wide footer={<Button onClick={onClose}>닫기</Button>}>
      <p className="rf-sub">{doc.title} · {DOC_TYPE[doc.doc_type] ?? doc.doc_type}{doc.revision ? ` · 개정 ${doc.revision}` : ""}</p>
      {q.isError && <Banner tone="neg">문서를 찾을 수 없음</Banner>}
      {!q.data && !q.isError && <p className="rf-sub">여는 중…</p>}
      {q.data && (q.data.sections.length === 0 ? <EmptyState title="색인된 절이 없습니다" /> : (
        <ol className="rf-sections" data-testid="doc-sections">
          {q.data.sections.map((c) => (
            <li key={c.chunk_id}>
              <button type="button" className="rf-link" onClick={() => setChunk({ kind: "cite", chunk_id: c.chunk_id, text: `${doc.doc_id} §${c.section_no ?? ""}` })}>
                <span className="rf-mono">§{c.section_no ?? "—"}</span> {c.section_title ?? ""}
              </button>
            </li>
          ))}
        </ol>
      ))}
    </Modal>
  );
}

// ---------------- 지식 관리 메뉴의 탭 화면 (N-08-03 ~ N-08-09) ----------------

type Menu = "rules" | "products" | "depts" | "etc";
interface TabDef { key: string; label: string; table: string; kind?: RuleKind | "products" | "departments" }

// 목업 KTABS. kind가 없는 탭은 API가 없어 "아직 보기 화면이 없습니다"(화면 명세 목업과 다른 곳)
const MENUS: Record<Menu, { title: string; meta: string; path: string; tabs: TabDef[] }> = {
  rules: { title: "규칙 관리", meta: "우선순위·부서 배정·필수 정보 규칙 · 읽기 전용", path: "/rules", tabs: [
    { key: "prio", label: "우선순위 규칙", table: "ref.priority_rule", kind: "priority" },
    { key: "urg", label: "긴급도", table: "ref.urgency" },
    { key: "route", label: "부서 배정 규칙", table: "ref.routing_rule", kind: "routing" },
    { key: "req", label: "필수 정보", table: "ref.required_info_rule", kind: "required-info" },
    { key: "info", label: "정보 항목", table: "ref.info_field" },
  ] },
  products: { title: "제품 관리", meta: "제품 기준정보 · 읽기 전용", path: "/products", tabs: [
    { key: "master", label: "제품 목록", table: "ref.product", kind: "products" },
    { key: "spec", label: "사양", table: "ref.product_spec" },
    { key: "fault", label: "고장 사전", table: "ref.fault" },
  ] },
  depts: { title: "부서 관리", meta: "담당 부서 · 읽기 전용", path: "/depts", tabs: [
    { key: "dept", label: "부서", table: "ref.department", kind: "departments" },
  ] },
  etc: { title: "기타 관리", meta: "그 밖의 코드와 기준표 · 읽기 전용", path: "/etc", tabs: [
    { key: "cat", label: "문의 유형", table: "ref.inquiry_category" },
    { key: "sla", label: "처리 기한", table: "ref.sla_policy", kind: "sla" },
    { key: "esc", label: "이관 사유", table: "—" },
    { key: "lang", label: "언어·채널", table: "—" },
  ] },
};

type R = Record<string, unknown>;
const str = (v: unknown) => (v === null || v === undefined || v === "" ? null : String(v));
const list = (v: unknown) => (Array.isArray(v) ? (v as unknown[]).map(String) : []);
const mono = (v: unknown) => <span className="rf-mono">{str(v) ?? "—"}</span>;

const COLS: Record<string, Col<R>[]> = {
  priority: [
    { key: "order", header: "순서", align: "right", text: (r) => str(r.rule_order) },
    { key: "id", header: "규칙 ID", text: (r) => str(r.rule_id), render: (r) => mono(r.rule_id) },
    { key: "cond", header: "조건", text: (r) => str(r.condition), wrap: true },
    { key: "prio", header: "우선순위", text: (r) => str(r.priority), render: (r) => <PriorityBadge priority={str(r.priority)} /> },
    { key: "urg", header: "긴급도", text: (r) => list(r.urgencies).join(", ") || null, wrap: true,
      render: (r) => list(r.urgencies).map((u) => label(URGENCY, u)).join(", ") || <span className="rf-sub">모든 긴급도</span> },
    { key: "cat", header: "문의 유형", text: (r) => list(r.categories).join(", ") || null, wrap: true,
      render: (r) => list(r.categories).join(", ") || <span className="rf-sub">모든 유형</span> },
  ],
  routing: [
    { key: "id", header: "규칙 ID", text: (r) => str(r.rule_id), render: (r) => mono(r.rule_id) },
    { key: "fam", header: "제품군", text: (r) => str(r.family) },
    { key: "cat", header: "문의 유형", text: (r) => str(r.category), render: (r) => label(CATEGORY, str(r.category)) },
    { key: "src", header: "출처", text: (r) => str(r.rule_source), render: (r) => <Chip tone="outline">{str(r.rule_source) ?? "—"}</Chip> },
    { key: "dept", header: "1차 부서", text: (r) => str(r.primary_dept), render: (r) => mono(r.primary_dept) },
    { key: "esc", header: "이관 부서", text: (r) => str(r.escalation_dept), render: (r) => mono(r.escalation_dept) },
    { key: "cond", header: "이관 조건", text: (r) => str(r.escalation_condition), wrap: true },
  ],
  "required-info": [
    { key: "fam", header: "제품군", text: (r) => str(r.family) },
    { key: "cat", header: "문의 유형", text: (r) => str(r.category), render: (r) => label(CATEGORY, str(r.category)) },
    { key: "fields", header: "항목(순서대로)", wrap: true,
      text: (r) => fields(r).map((f) => f.field).join(", "),
      render: (r) => <span className="rf-fields">{fields(r).map((f) => f.is_blocking ? <b key={f.field}>{f.field}</b> : <span key={f.field}>{f.field}</span>)}</span> },
    { key: "block", header: "막는 항목", text: (r) => fields(r).filter((f) => f.is_blocking).map((f) => f.field).join(", ") || "없음", wrap: true },
  ],
  sla: [
    { key: "id", header: "SLA ID", text: (r) => str(r.sla_id), render: (r) => mono(r.sla_id) },
    { key: "cat", header: "문의 유형", text: (r) => str(r.category), render: (r) => label(CATEGORY, str(r.category)) },
    { key: "tier", header: "고객 등급", text: (r) => str(r.customer_tier) },
    { key: "prio", header: "우선순위", text: (r) => str(r.priority), render: (r) => <PriorityBadge priority={str(r.priority)} /> },
    { key: "first", header: "1차 응답(시간)", align: "right", text: (r) => str(r.first_response_hours) },
    { key: "res", header: "해결(시간)", align: "right", text: (r) => str(r.resolution_hours) },
  ],
  products: [
    { key: "code", header: "제품 코드", text: (r) => str(r.product_code), render: (r) => <b className="rf-mono">{str(r.product_code)}</b> },
    { key: "name", header: "제품 이름", text: (r) => str(r.product_name), wrap: true },
    { key: "fam", header: "제품군", text: (r) => str(r.family) },
    { key: "price", header: "단가(USD)", align: "right", text: (r) => str(r.list_price_usd) },
    { key: "lead", header: "표준 납기(주)", align: "right", text: (r) => str(r.std_lead_time_weeks) },
    { key: "life", header: "수명 상태", text: (r) => str(r.lifecycle_status) },
    { key: "warranty", header: "보증(개월)", align: "right", text: (r) => str(r.warranty_months) },
  ],
  departments: [
    { key: "code", header: "부서 코드", text: (r) => str(r.dept_code), render: (r) => mono(r.dept_code) },
    { key: "ko", header: "부서 이름", text: (r) => str(r.dept_name_ko) },
    { key: "en", header: "영어 이름", text: (r) => str(r.dept_name_en) },
    { key: "level", header: "단계", text: (r) => str(r.level) },
    { key: "scope", header: "담당 범위", text: (r) => str(r.scope), wrap: true },
  ],
};

type FieldItem = { field: string; field_order: number; is_blocking: boolean };
const fields = (r: R) => (Array.isArray(r.fields) ? (r.fields as FieldItem[]) : []);
const rowId = (r: R) => String(r.rule_id ?? r.sla_id ?? r.product_code ?? r.dept_code ?? `${r.family}|${r.category}`);

async function load(kind: NonNullable<TabDef["kind"]>): Promise<R[]> {
  if (kind === "products") return (await api.products()) as unknown as R[];
  if (kind === "departments") return (await api.departments()) as unknown as R[];
  return (await api.rules(kind)).rows;
}

export function KnowledgePage({ menu }: { menu: Menu }) {
  const M = MENUS[menu];
  const [s, go] = useUrlState(M.path, M.tabs[0].key);
  const tab = M.tabs.find((t) => t.key === s.tab) ?? M.tabs[0];
  const kind = tab.kind;
  const q = useQuery({ queryKey: ["ref-table", kind], queryFn: () => load(kind!), enabled: !!kind });
  const [product, setProduct] = useState<Product | null>(null);
  const cols = kind ? COLS[kind] : [];
  const rows = (q.data ?? []).filter(matches(cols, s.q));

  // 「왜?」에서 연 규칙(?rule=)이 있는 쪽으로 간다
  useEffect(() => {
    if (!s.rule || !q.data) return;
    const i = rows.findIndex((r) => rowId(r) === s.rule);
    if (i >= 0 && Math.floor(i / PER) + 1 !== s.page) go({ page: Math.floor(i / PER) + 1, rule: s.rule });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.rule, q.data]);

  return (
    <div className="rf">
      <PageHeader title={M.title} meta={M.meta}
        actions={kind && <Button onClick={() => downloadCsv(tab.table.replace(/^ref\./, ""), cols, rows)} disabled={!q.data}>CSV 내려받기</Button>} />
      <section className="ui-card">
        <Tabs label={`${M.title} 표`} value={tab.key} onChange={(k) => go({ tab: k, q: "", rule: "" })}
          items={M.tabs.map((t) => ({ key: t.key, label: t.label }))} />
        {!kind ? (
          <EmptyState title="이 표는 아직 보기 화면이 없습니다">원본 테이블 {tab.table}</EmptyState>
        ) : (
          <>
            <SearchBox key={tab.key} value={s.q} onSearch={(v) => go({ q: v, rule: s.rule })} label="검색" placeholder="코드, 이름">
              <span className="rf-src">원본 테이블 <span className="rf-mono">{tab.table}</span></span>
            </SearchBox>
            {q.isError && <Banner tone="neg" title={FAIL} />}
            {!q.data ? <div className="rf-skeleton" aria-busy="true" /> : (
              <PagedTable cols={cols} rows={rows} rowKey={rowId} page={s.page} onPage={(p) => go({ page: p, rule: s.rule })}
                marked={s.rule ? (r) => rowId(r) === s.rule : undefined}
                onRowClick={kind === "products" ? (r) => setProduct(r as unknown as Product) : undefined}
                empty="조건에 맞는 행이 없습니다" caption={tab.label} />
            )}
            {kind === "priority" && <p className="rf-note">위에서부터 처음 맞는 행 하나를 씁니다.</p>}
          </>
        )}
      </section>
      {product && <ProductModal code={product.product_code} onClose={() => setProduct(null)} />}
    </div>
  );
}

function ProductModal({ code, onClose }: { code: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["ref-product", code], queryFn: () => api.product(code), retry: false });
  const d = q.data;
  return (
    <Modal title={`${code} 제품 상세`} onClose={onClose} wide footer={<Button onClick={onClose}>닫기</Button>}>
      {q.isError && <Banner tone="neg">제품을 찾을 수 없음</Banner>}
      {!d && !q.isError && <p className="rf-sub">여는 중…</p>}
      {d && (
        <div className="rf-product" data-testid="product-detail">
          <dl className="rf-kvs">
            <dt>제품 이름</dt><dd>{d.product_name}</dd>
            <dt>제품군</dt><dd>{d.family ?? "—"}</dd>
            <dt>단가</dt><dd>{d.list_price_usd ?? "—"} USD</dd>
            <dt>표준 납기</dt><dd>{d.std_lead_time_weeks ?? "—"}주</dd>
            <dt>수명 상태</dt><dd>{d.lifecycle_status ?? "—"}</dd>
            <dt>보증</dt><dd>{d.warranty_months ?? "—"}개월</dd>
            <dt>규격</dt><dd className="rf-chips">{d.standards.length ? d.standards.map((x) => <Chip key={x} tone="outline">{x}</Chip>) : "없음"}</dd>
            <dt>인증</dt><dd className="rf-chips">{d.certifications.length ? d.certifications.map((x) => <Chip key={x} tone="outline">{x}</Chip>) : "없음"}</dd>
          </dl>
          <h3 className="rf-h3">사양</h3>
          <DataTable caption="사양" rows={d.specs} rowKey={(x) => x.attribute} empty={<EmptyState title="사양 값이 없습니다" />}
            columns={[
              { key: "a", header: "사양 항목", render: (x) => <span className="rf-mono">{x.attribute}</span> },
              { key: "v", header: "값", render: (x) => x.value ?? "—", wrap: true },
              { key: "d", header: "근거 문서", render: (x) => <span className="rf-mono">{x.doc_id ?? "—"}{x.section ? ` §${x.section}` : ""}</span> },
            ]} />
          <h3 className="rf-h3">펌웨어 출시 이력</h3>
          <DataTable caption="펌웨어 출시 이력" rows={d.firmware} rowKey={(x) => x.fw_version} empty={<EmptyState title="펌웨어가 없는 제품입니다" />}
            columns={[
              { key: "v", header: "버전", render: (x) => <span className="rf-mono">{x.fw_version}</span> },
              { key: "d", header: "출시일", render: (x) => x.release_date ?? "—" },
              { key: "l", header: "최신", render: (x) => (x.is_latest ? <Chip tone="info">최신</Chip> : "") },
              { key: "c", header: "바뀐 것", render: (x) => x.changes ?? "—", wrap: true },
            ]} />
        </div>
      )}
    </Modal>
  );
}
