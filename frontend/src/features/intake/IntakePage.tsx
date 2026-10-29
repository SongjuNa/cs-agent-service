// SCR-01 접수 시뮬레이터 (화면 정의서 v1 SCR-01·SCR-01-P1, 명세서 FR-001·FR-003). 시연·테스트 담당자용.
// 배치는 목업 v1.42 `viewSim`: 3단계 "문의 입력 → 자동 처리 → 완료". 처리는 흉내 내지 않고 실제 단계 기록을 읽는다.
import { useEffect, useState } from "react";
import { api, ApiError, fieldErrors, type Customer, type Detail, type Loaded, type Product, type TicketInput } from "../../api";
import { CATEGORY, CHANNEL, label } from "../../app/labels";
import { useDepartments } from "../../app/queries";
import { useSession } from "../../app/session";
import { Banner, Button, Chip, Field, PageHeader } from "../../ui";
import { lastInboxUrl } from "../inbox/inboxQuery";
import { langName } from "../ticket/CustomerTab";
import "./intake.css";

const CHANNELS = ["EMAIL", "CHAT", "PHONE", "WEB_FORM", "PARTNER_PORTAL"];
const LANGUAGES = ["ar", "de", "en", "es", "fr", "id", "it", "ja", "pl", "pt", "ru", "th", "tr", "vi", "zh"];
const MAX_BODY = 2000;
const ID_FORMAT = /^(CSV1-\d{6}|GS-\d{3})$/; // 운영진 번호, 팀 정답지 번호(화면 정의서 v2 부록 B-1)
// 시연용 고정 5건(목업 SIM_LOAD, 화면 명세 SCR-01-02)
const DEMO: [string, string][] = [
  ["CSV1-000017", "고장·불량"], ["CSV1-003578", "기술 사양"], ["CSV1-000008", "펌웨어 + 매뉴얼"],
  ["CSV1-000004", "견적"], ["CSV1-000031", "매뉴얼"],
];
// ② 단계 6줄과 그 줄에 들어가는 처리 단계(기술 명세서 §4 노드 표). 줄 묶음은 구현 선택
const STAGES: [string, string[]][] = [
  ["언어 식별", ["T1"]],
  ["문의 유형 분류와 요청 나누기", ["T2", "T3"]],
  ["긴급도 판단, 제공 정보 추출", ["Q1"]],
  ["규칙표 적용: 우선순위, 담당 부서, 필수 정보, 기한", ["Q2", "Q3", "Q4", "Q5", "Q6", "Q9a"]],
  ["문서 근거 검색, 숫자 조회", ["Q8a", "Q8b", "Q8", "Q9"]],
  ["초안 작성과 자체 대조", ["Q7", "Q10", "Q11", "T5", "Q13", "Q14", "T6"]],
];
const stageOf = (step: string) => {
  const i = STAGES.findIndex(([, steps]) => steps.includes(step));
  return i < 0 ? 0 : i;
};
const POLL_MS = 2000;

type Form = { channel: string; customer_id: string; product_code: string; language: string; inquiry_body: string; received_at: string };
const nowInput = () => new Date().toISOString().slice(0, 16);
const empty = (): Form => ({ channel: "EMAIL", customer_id: "", product_code: "", language: "en", inquiry_body: "", received_at: nowInput() });

type Run = { ticketId: string; runId: number | null };

export function IntakePage({ onOpen, navigate }: { onOpen: (ticketId: string) => void; navigate: (path: string) => void }) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [form, setForm] = useState<Form>(empty);
  const [origin, setOrigin] = useState<Loaded | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [result, setResult] = useState<Detail | null>(null);

  function reset() {
    setForm(empty()); setOrigin(null); setRun(null); setResult(null); setStep(1);
  }

  const steps = ["문의 입력", "자동 처리", "완료"];
  return (
    <div className="in-page">
      <PageHeader title="접수 시뮬레이터" meta="이메일·채팅·전화·포털 대신 문의를 넣습니다" />
      <ol className="in-steps" aria-label="접수 단계">
        {steps.map((l, i) => (
          <li key={l} className={step === i + 1 ? "is-on" : step > i + 1 ? "is-done" : undefined} aria-current={step === i + 1 ? "step" : undefined}>
            <span className="in-steps__n">{step > i + 1 ? "✓" : i + 1}</span>{l}
          </li>
        ))}
      </ol>
      {step === 1 && (
        <InputStep form={form} setForm={setForm} origin={origin} setOrigin={setOrigin} onClear={reset}
                   onAccepted={(r) => { setRun(r); setStep(2); }} />
      )}
      {step === 2 && run && <ProgressStep run={run} onOpen={onOpen} onDone={(d) => { setResult(d); setStep(3); }} />}
      {step === 3 && result && (
        <DoneStep detail={result} onOpen={onOpen} onInbox={() => navigate(lastInboxUrl())} onAgain={reset} />
      )}
    </div>
  );
}

function InputStep({ form, setForm, origin, setOrigin, onClear, onAccepted }: {
  form: Form; setForm: (f: Form | ((f: Form) => Form)) => void; origin: Loaded | null; setOrigin: (l: Loaded | null) => void;
  onClear: () => void; onAccepted: (r: Run) => void;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadId, setLoadId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => { api.products().then(setProducts).catch(() => setProducts([])); }, []);
  useEffect(() => {
    const timer = setTimeout(() => { api.customers(form.customer_id).then(setCustomers).catch(() => setCustomers([])); }, 200);
    return () => clearTimeout(timer);
  }, [form.customer_id]);

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [key]: e.target.value });
    setErrors((x) => ({ ...x, [key === "received_at" ? "received_at_utc" : key]: "" }));
  };

  async function load(id: string) {
    const value = id.trim().toUpperCase();
    setLoadError(null);
    if (!ID_FORMAT.test(value)) { setLoadError("형식: CSV1-000000 또는 GS-001"); return; }
    setLoading(true);
    try {
      const l = await api.load(value);
      // 입력 칸만 채운다(FR-003 처리 3, AC-003-1). 제목·정답 칸은 없다.
      // 접수 시각은 원본 대신 지금으로 채운다(2026-10-29 조장 결정, v1.5.2): 원본 시각(2025-10)이면 SLA가 수천 시간 지난 것으로 보인다
      setForm({ channel: l.channel, customer_id: l.customer_id, product_code: l.product_code ?? "", language: l.language,
                inquiry_body: l.inquiry_body, received_at: nowInput() });
      setOrigin(l);
      setErrors({}); setFailure(null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "불러오지 못함");
    } finally {
      setLoading(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const blank = (v: string) => (v.trim() ? v.trim() : null);
    const data: TicketInput = {
      channel: form.channel, customer_id: form.customer_id.trim(), product_code: blank(form.product_code),
      language: form.language, inquiry_subject: null, inquiry_body: form.inquiry_body,
      received_at_utc: form.received_at ? `${form.received_at.length === 16 ? `${form.received_at}:00` : form.received_at}Z` : null,
      source_ticket_id: origin?.source_ticket_id ?? null, contact_name: null, contact_email: null, contact_phone: null,
    };
    setBusy(true); setErrors({}); setFailure(null);
    try {
      const res = await api.intake(data);
      onAccepted({ ticketId: res.ticket_id, runId: res.run_id ?? null });
    } catch (err) {
      const list = fieldErrors(err);
      if (list.length) setErrors(Object.fromEntries(list.map((x) => [x.field, x.message])));
      else setFailure(`접수 실패: ${err instanceof ApiError ? err.message : "서버에 닿지 못함"}`);
    } finally {
      setBusy(false);
    }
  }

  const loaded = origin ? <Chip tone="info">불러옴</Chip> : null;
  const lab = (text: string) => <>{text} {loaded}</>;
  return (
    <section className="ui-card in-card">
      <div className="ui-card__head">
        <h2 className="ui-card__title">문의 입력</h2>
        {origin && <span className="in-origin">원본 {origin.source_ticket_id}{origin.gold_set && <Chip tone="neu">채점용 문의</Chip>}</span>}
        <div className="in-load">
          <label htmlFor="in-demo">시연용 문의 불러오기</label>
          <select id="in-demo" value="" disabled={loading} onChange={(e) => e.target.value && void load(e.target.value)}>
            <option value="">고르기</option>
            {DEMO.map(([id, kind]) => <option key={id} value={id}>{id} ({kind})</option>)}
          </select>
          <input aria-label="문의 번호" placeholder="CSV1-000017 또는 GS-001" value={loadId}
                 onChange={(e) => { setLoadId(e.target.value); setLoadError(null); }}
                 onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void load(loadId); } }} />
          <Button size="sm" busy={loading} onClick={() => void load(loadId)}>불러오기</Button>
        </div>
      </div>
      {loadError && <div className="in-pad"><Banner tone="neg">{loadError}</Banner></div>}
      <form className="in-form" onSubmit={submit} noValidate>
        <div className="in-grid">
          <Field label={lab("채널")} required error={errors.channel}>
            <select value={form.channel} onChange={set("channel")}>
              {CHANNELS.map((c) => <option key={c} value={c}>{label(CHANNEL, c)}</option>)}
            </select>
          </Field>
          <Field label={lab("접수 시각 (UTC)")} hint="비우면 지금" error={errors.received_at_utc}>
            <input type="datetime-local" step={1} value={form.received_at} onChange={set("received_at")} />
          </Field>
          <Field label={lab("고객 ID")} required error={errors.customer_id}>
            <input list="in-customers" value={form.customer_id} onChange={set("customer_id")} placeholder="CUST-0350" />
          </Field>
          <Field label={lab("제품 코드")} error={errors.product_code}>
            <input list="in-products" value={form.product_code} onChange={set("product_code")} placeholder="비워 두면 1차 상담으로 갑니다" />
          </Field>
          <Field label={lab("고객 언어")} required error={errors.language}>
            <select value={form.language} onChange={set("language")}>
              {LANGUAGES.map((l) => <option key={l} value={l}>{langName(l)}</option>)}
            </select>
          </Field>
          <div />
          <div className="is-full">
            <Field label={lab("본문")} required error={errors.inquiry_body}
                   hint={<span className={form.inquiry_body.length > MAX_BODY ? "tk-neg" : undefined}>{form.inquiry_body.length.toLocaleString()} / 2,000자</span>}>
              <textarea rows={8} value={form.inquiry_body} onChange={set("inquiry_body")} dir={form.language === "ar" ? "rtl" : undefined} />
            </Field>
          </div>
        </div>
        <datalist id="in-customers">
          {customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{`${c.company_masked} · ${c.country} · ${c.tier}`}</option>)}
        </datalist>
        <datalist id="in-products">
          {products.map((p) => <option key={p.product_code} value={p.product_code}>{p.product_name}</option>)}
        </datalist>
        {failure && <Banner tone="neg">{failure}</Banner>}
        <div className="in-actions">
          <span className="in-note">제목은 받지 않습니다. 유형이 드러나 분류를 흐리기 때문입니다.</span>
          <Button onClick={onClear} disabled={busy}>지우기</Button>
          <Button type="submit" variant="primary" busy={busy}>접수하고 처리 시작</Button>
        </div>
      </form>
    </section>
  );
}

function ProgressStep({ run, onOpen, onDone }: { run: Run; onOpen: (id: string) => void; onDone: (d: Detail) => void }) {
  const [seen, setSeen] = useState<string[]>([]);
  const [failed, setFailed] = useState<{ stage: number; step: string; reason: string } | null>(null);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    let alive = true;
    let misses = 0;
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      try {
        const [d, s] = await Promise.all([
          api.ticket(run.ticketId),
          run.runId ? api.steps(run.runId) : Promise.resolve({ steps: [] }),
        ]);
        if (!alive) return;
        misses = 0;
        setSeen(s.steps.map((x) => x.step_name));
        if (!d.processing) {
          if (d.run?.status === "FAILED") {
            const bad = s.steps.find((x) => x.error) ?? null;
            const step = bad?.step_name ?? d.run.last_step ?? "";
            const reason = d.sub_tickets.find((x) => x.sub_ticket.pipeline_error)?.sub_ticket.pipeline_error ?? bad?.error ?? "";
            setFailed({ stage: stageOf(step), step, reason });
          } else onDone(d);
          return;
        }
      } catch {
        if (++misses >= 3) { if (alive) setLost(true); return; } // 읽기 실패 3번 연속(화면 명세 동작 표)
      }
      timer = setTimeout(tick, POLL_MS);
    }
    void tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [run, onDone]);

  const reached = seen.length ? Math.max(...seen.map(stageOf)) : 0;
  const state = (i: number) => failed ? (i < failed.stage ? "done" : i === failed.stage ? "fail" : "wait")
    : i < reached ? "done" : i === reached ? "run" : "wait";
  return (
    <section className="ui-card in-card in-card--narrow">
      <div className="ui-card__head"><h2 className="ui-card__title">{failed ? "자동 처리 실패" : "자동 처리 중"}</h2>
        <span className="in-origin">{run.ticketId}</span></div>
      <div className="in-pad">
        <ul className="in-progress" data-testid="progress">
          {STAGES.map(([l], i) => (
            <li key={l} data-state={state(i)}><span className="in-progress__st" aria-hidden="true">{state(i) === "done" ? "✓" : state(i) === "fail" ? "✕" : ""}</span>{l}</li>
          ))}
        </ul>
        {failed && (
          <Banner tone="neg" title={`자동 처리 실패: ${failed.step}`}
                  action={<Button size="sm" onClick={() => onOpen(run.ticketId)}>티켓 상세에서 다시 처리</Button>}>
            {failed.reason || "티켓은 신규 상태로 남았습니다."}
          </Banner>
        )}
        {lost && (
          <Banner tone="neg" action={<Button size="sm" onClick={() => onOpen(run.ticketId)}>티켓 상세 보기</Button>}>진행 상황을 불러오지 못함</Banner>
        )}
      </div>
    </section>
  );
}

function DoneStep({ detail, onOpen, onInbox, onAgain }: { detail: Detail; onOpen: (id: string) => void; onInbox: () => void; onAgain: () => void }) {
  const { dept } = useSession();
  const depts = useDepartments();
  const name = (code: string | null) => depts.data?.find((d) => d.dept_code === code)?.dept_name_ko ?? code ?? "—";
  const subs = detail.sub_tickets;
  const assigned = [...new Set(subs.map((s) => s.sub_ticket.assigned_dept))];
  const drafts = subs.map((s) => {
    const live = s.drafts.filter((d) => !d.superseded_at);
    return live.some((d) => d.message_type === "INFO_REQUEST") ? "정보 요청" : live.some((d) => d.message_type === "FINAL_REPLY") ? "답변" : "없음";
  });
  const partial = detail.run?.status === "PARTIAL";
  return (
    <section className="ui-card in-card in-card--narrow" data-testid="done">
      <div className="ui-card__head"><h2 className="ui-card__title">접수했습니다</h2>
        {partial ? <Chip tone="crit">일부 문의 처리 실패</Chip> : <Chip tone="pos">자동 처리 완료</Chip>}</div>
      <div className="in-pad in-done">
        <dl className="tk-kvs">
          <dt>티켓 번호</dt><dd><b className="tk-mono-b" data-testid="done-id">{detail.ticket.ticket_id}</b></dd>
          <dt>문의</dt>
          <dd data-testid="done-subs">{subs.map((s) => `${label(CATEGORY, s.sub_ticket.category_code)} ${s.sub_ticket.priority ?? "—"}`).join(", ")}</dd>
          <dt>담당 부서</dt><dd data-testid="done-dept">{assigned.map(name).join(", ")}</dd>
          <dt>준비된 초안</dt><dd>{drafts.join(", ")}</dd>
        </dl>
        {dept && !assigned.includes(dept) && (
          <Banner tone="info">이 티켓은 {assigned.map(name).join(", ")} 접수함에 들어갔습니다. 상세 화면은 부서와 상관없이 열 수 있습니다.</Banner>
        )}
        <div className="in-actions in-actions--left">
          <Button variant="primary" onClick={() => onOpen(detail.ticket.ticket_id)}>티켓 상세 보기</Button>
          <Button onClick={onInbox}>접수함으로</Button>
          <Button variant="ghost" onClick={onAgain}>다른 문의 접수</Button>
        </div>
      </div>
    </section>
  );
}
