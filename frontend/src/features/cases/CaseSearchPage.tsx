// SCR-09 접수 이력(해결사례 검색) (화면 명세 SCR-09, FR 초안 06, 변경 add-case-search). 읽기만, 상담원 참고용.
// 배치는 목업 v1.42 `viewSimilar`: 안내 띠 → 거르기 상자 → 표. 목업과 달리 검색해야 결과가 나온다(화면 명세 목업과 다른 곳).
// 원래 티켓은 운영진 문의 번호라 서비스 DB에 없을 수 있어 번호만 보인다(2026-10-29 검토 자료 ②).
// 검색 칸은 주소(?q=&error_code=&product_code=&category_code=)에 남긴다. 티켓 상세 [접수 이력에서 보기]가 이 주소로 연다.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type CaseRows } from "../../api";
import { CATEGORY, label } from "../../app/labels";
import { Banner, Button, Chip, DataTable, EmptyState, Modal, PageHeader, type Column } from "../../ui";
import "./cases.css";

const KEYS = ["q", "error_code", "product_code", "category_code"] as const;
type Form = Record<(typeof KEYS)[number], string>;
type Row = CaseRows["rows"][number];

function readForm(): Form {
  const p = new URLSearchParams(window.location.search);
  return Object.fromEntries(KEYS.map((k) => [k, p.get(k) ?? ""])) as Form;
}

export function CaseSearchPage() {
  const [form, setForm] = useState<Form>(readForm);
  // 주소에 검색 칸이 있으면(티켓 상세에서 왔으면) 바로 찾는다
  const [asked, setAsked] = useState<Form | null>(() => (KEYS.some((k) => readForm()[k]) ? readForm() : null));
  const [open, setOpen] = useState<string | null>(null);
  const products = useQuery({ queryKey: ["products"], queryFn: api.products });

  const params = asked && new URLSearchParams(KEYS.filter((k) => asked[k]).map((k) => [k, asked[k]]));
  const q = useQuery({ queryKey: ["cases", params?.toString()], queryFn: () => api.cases(params!), enabled: !!asked, retry: false });

  const submit = () => {
    const next = Object.fromEntries(KEYS.map((k) => [k, form[k].trim()])) as Form;
    const p = new URLSearchParams(KEYS.filter((k) => next[k]).map((k) => [k, next[k]]));
    window.history.replaceState(null, "", `/history${p.toString() ? `?${p}` : ""}`);
    setAsked(next);
  };
  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const columns: Column<Row>[] = [
    { key: "id", header: "사례 번호", render: (r) => <b className="cs-mono">{r.case_id}</b> },
    { key: "ticket", header: "원래 티켓", render: (r) => <span className="cs-mono cs-sub" title="운영진 문의 번호(서비스에 없을 수 있음)">{r.ticket_id}</span> },
    { key: "cat", header: "유형", render: (r) => label(CATEGORY, r.category_code) },
    { key: "product", header: "제품", render: (r) => <span className="cs-mono">{r.product_code ?? "—"}</span> },
    { key: "code", header: "에러 코드", render: (r) => (r.error_code
      ? <span className="cs-code"><span className="cs-mono">{r.error_code}</span>{r.same_error_code && <Chip tone="info">같은 코드</Chip>}</span>
      : <span className="cs-sub">없음</span>) },
    { key: "summary", header: "해결 요약", wrap: true, render: (r) => r.case_summary ?? "—" },
  ];
  const badInput = q.error instanceof ApiError && q.error.status === 400;

  return (
    <div className="cs">
      <PageHeader title="접수 이력" meta="상담원 참고용 해결사례 · 읽기 전용" />
      <Banner tone="info">사례는 상담원 화면에만 참고로 보이고, 고객에게 가는 글의 근거로는 쓰지 않습니다.</Banner>
      <section className="ui-card">
        <form className="cs-filter" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <div className="cs-field cs-field--grow">
            <label htmlFor="cs-q">증상 검색어</label>
            <input id="cs-q" type="search" maxLength={200} value={form.q} onChange={set("q")} placeholder="breaker trips after reset" />
          </div>
          <div className="cs-field">
            <label htmlFor="cs-code">에러 코드</label>
            <input id="cs-code" value={form.error_code} onChange={set("error_code")} placeholder="E.OC" />
          </div>
          <div className="cs-field">
            <label htmlFor="cs-product">제품 코드</label>
            <select id="cs-product" value={form.product_code} onChange={set("product_code")}>
              <option value="">전체</option>
              {(products.data ?? []).map((p) => <option key={p.product_code} value={p.product_code}>{p.product_code}</option>)}
            </select>
          </div>
          <div className="cs-field">
            <label htmlFor="cs-cat">문의 유형</label>
            <select id="cs-cat" value={form.category_code} onChange={set("category_code")}>
              <option value="">전체</option>
              {Object.entries(CATEGORY).map(([c, l]) => <option key={c} value={c}>{l}</option>)}
            </select>
          </div>
          <Button type="submit" variant="primary" disabled={q.isFetching}>{q.isFetching ? "찾는 중…" : "찾기"}</Button>
        </form>
        {!asked ? (
          <EmptyState title="증상, 에러 코드, 제품 중 하나 이상을 넣어 찾으세요" />
        ) : badInput ? (
          <div className="cs-pad"><Banner tone="neg" title={q.error?.message} /></div>
        ) : q.isError ? (
          <div className="cs-pad"><Banner tone="neg" title="검색하지 못함. 다시 시도" /></div>
        ) : !q.data ? (
          <div className="cs-skeleton" aria-busy="true" />
        ) : (
          <>
            {q.data.notes.map((n) => <div key={n} className="cs-pad"><Banner tone="crit" title={n} /></div>)}
            <p className="cs-count" data-testid="case-count">{q.data.total}건 중 {q.data.rows.length}건, 같은 에러 코드 먼저</p>
            <DataTable columns={columns} rows={q.data.rows} rowKey={(r) => r.case_id} onRowClick={(r) => setOpen(r.case_id)} caption="해결사례 검색 결과"
              empty={<EmptyState title="조건에 맞는 사례가 없습니다">검색어나 거르기를 바꿔 보세요</EmptyState>} />
          </>
        )}
      </section>
      {open && <CaseModal caseId={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

const DETAIL: [string, string][] = [
  ["symptom", "증상"], ["initial_hypothesis", "처음 가설"], ["root_cause", "원인"], ["diagnosis_method", "진단 방법"],
  ["action_taken", "조치"], ["replacement_part", "교체 부품"], ["onsite_visit", "현장 방문"], ["resolution_result", "결과"],
  ["time_to_resolve_hours", "해결 시간(시간)"], ["recurrence_prevention", "재발 방지"], ["case_summary", "요약"],
];

function CaseModal({ caseId, onClose }: { caseId: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["case", caseId], queryFn: () => api.caseDetail(caseId), retry: false });
  const d = q.data as Record<string, unknown> | undefined;
  return (
    <Modal title={`${caseId} 사례 상세`} onClose={onClose} wide footer={<Button onClick={onClose}>닫기</Button>}>
      {q.isError && <Banner tone="neg">사례를 찾을 수 없음</Banner>}
      {!d && !q.isError && <p className="cs-sub">여는 중…</p>}
      {d && (
        <div data-testid="case-detail">
          <p className="cs-sub">
            원래 티켓 <span className="cs-mono">{String(d.ticket_id)}</span> · {label(CATEGORY, d.category_code as string)} ·{" "}
            <span className="cs-mono">{String(d.product_code ?? "—")}</span>{d.error_code ? <> · <span className="cs-mono">{String(d.error_code)}</span></> : null}
            {" "}· 참고용, 초안에는 쓰지 않음
          </p>
          <dl className="cs-kvs">
            {DETAIL.map(([k, l]) => <div key={k} data-field={k}><dt>{l}</dt><dd>{d[k] ? String(d[k]) : "—"}</dd></div>)}
          </dl>
        </div>
      )}
    </Modal>
  );
}
