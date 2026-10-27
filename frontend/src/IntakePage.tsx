// SCR-01 접수 시뮬레이터 (화면 정의서 v1 SCR-01·SCR-01-P1, 명세서 FR-001·FR-003). 시연·테스트 담당자용.
import { useEffect, useState } from "react";
import { api, ApiError, fieldErrors, type CallNote, type CallResult, type Customer, type Loaded, type Product, type TicketInput } from "./api";

const CHANNELS = ["EMAIL", "CHAT", "PHONE", "WEB_FORM", "PARTNER_PORTAL"];
const LANGUAGES = ["ar", "de", "en", "es", "fr", "id", "it", "ja", "pl", "pt", "ru", "th", "tr", "vi", "zh"];
const MAX_BODY = 2000;
const ID_FORMAT = /^(CSV1-\d{6}|GS-\d{3})$/; // 운영진 번호, 팀 정답지 번호(화면 정의서 v2 부록 B-1)

type Form = {
  channel: string; customer_id: string; product_code: string; language: string; inquiry_subject: string;
  inquiry_body: string; received_at: string; contact_name: string; contact_email: string; contact_phone: string;
};
const EMPTY: Form = {
  channel: "EMAIL", customer_id: "", product_code: "", language: "en", inquiry_subject: "", inquiry_body: "",
  received_at: "", contact_name: "", contact_email: "", contact_phone: "",
};

/** "2025-10-02T09:45:43+00:00" → 입력 칸 값 "2025-10-02T09:45:43" (UTC 그대로) */
function toInput(utc: string | null): string {
  return utc ? utc.replace(/(\.\d+)?(Z|[+-]\d\d:\d\d)$/, "").slice(0, 19) : "";
}

export function IntakePage({ onCreated }: { onCreated: (ticketId: string) => void }) {
  const [form, setForm] = useState<Form>(EMPTY);
  const [origin, setOrigin] = useState<Loaded | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => { api.products().then(setProducts).catch(() => setProducts([])); }, []);
  useEffect(() => {
    const timer = setTimeout(() => { api.customers(form.customer_id).then(setCustomers).catch(() => setCustomers([])); }, 200);
    return () => clearTimeout(timer);
  }, [form.customer_id]);

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value });

  function fill(loaded: Loaded) {
    // 입력 6칸만 채우고 제목·연락처는 비운다(FR-003 처리 3, AC-003-1)
    setForm({ ...EMPTY, channel: loaded.channel, customer_id: loaded.customer_id, product_code: loaded.product_code ?? "",
              language: loaded.language, inquiry_body: loaded.inquiry_body, received_at: toInput(loaded.received_at_utc) });
    setOrigin(loaded);
    setErrors({});
    setFailure(null);
    setLoading(false);
  }

  function clear() {
    setForm(EMPTY);
    setOrigin(null);
    setErrors({});
    setFailure(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const blank = (v: string) => (v.trim() ? v.trim() : null);
    const data: TicketInput = {
      channel: form.channel, customer_id: form.customer_id.trim(), product_code: blank(form.product_code),
      language: form.language, inquiry_subject: blank(form.inquiry_subject), inquiry_body: form.inquiry_body,
      received_at_utc: form.received_at ? `${form.received_at}Z` : null, source_ticket_id: origin?.source_ticket_id ?? null,
      contact_name: blank(form.contact_name), contact_email: blank(form.contact_email), contact_phone: blank(form.contact_phone),
    };
    setBusy(true);
    setErrors({});
    setFailure(null);
    try {
      const res = await api.intake(data);
      onCreated(res.ticket_id);
    } catch (err) {
      const list = fieldErrors(err);
      setErrors(Object.fromEntries(list.map((x) => [x.field, x.message])));
      setFailure(`접수 실패: ${err instanceof ApiError ? err.message : "서버에 닿지 못함"}`);
    } finally {
      setBusy(false);
    }
  }

  const err = (field: string) => errors[field] && <div className="bad small">! {errors[field]}</div>;

  return (
    <div className="intake-page">
      <p className="banner">시연·테스트 담당자용 · 채널 연동 대체</p>
      <div className="intake-head">
        <h2>접수 시뮬레이터</h2>
        <button type="button" onClick={() => setLoading(true)}>문의 번호로 불러오기</button>
        {origin && <span className="muted">원본 {origin.source_ticket_id}에서 불러옴</span>}
        {origin?.gold_set && <span className="chip gray">채점용 문의</span>}
      </div>

      <form className="intake-form" onSubmit={submit}>
        <label><span>채널 <span className="req">*</span></span>
          <select value={form.channel} onChange={set("channel")}>
            {CHANNELS.map((c) => <option key={c}>{c}</option>)}
          </select>{err("channel")}
        </label>
        <label><span>고객 <span className="req">*</span></span>
          <input list="customer-list" value={form.customer_id} onChange={set("customer_id")} placeholder="ID 또는 회사명으로 찾기" />
          <datalist id="customer-list">
            {customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{`${c.company_masked} · ${c.country} · ${c.tier}`}</option>)}
          </datalist>{err("customer_id")}
        </label>
        <label>제품 코드
          <input list="product-list" value={form.product_code} onChange={set("product_code")} placeholder="모르면 비우세요(본문에서 찾음)" />
          <datalist id="product-list">
            {products.map((p) => <option key={p.product_code} value={p.product_code}>{p.product_name}</option>)}
          </datalist>{err("product_code")}
        </label>
        <label><span>고객 언어 <span className="req">*</span></span>
          <select value={form.language} onChange={set("language")}>
            {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
          </select>{err("language")}
        </label>
        <label className="wide"><span>제목 <small className="muted">처리에는 쓰지 않음</small></span>
          <input value={form.inquiry_subject} onChange={set("inquiry_subject")} />
        </label>
        {form.channel === "PHONE" && (
          <CallPanel customerId={form.customer_id.trim()} language={form.language} productCode={form.product_code.trim()}
            onNote={(note, startedAt) => setForm((f) => ({ ...f, inquiry_body: note, received_at: f.received_at || startedAt }))} />
        )}
        <label className="wide"><span>본문 <span className="req">*</span></span>
          <textarea rows={8} value={form.inquiry_body} onChange={set("inquiry_body")} />
          <div className={`small ${form.inquiry_body.length > MAX_BODY ? "bad" : "muted"}`}>{form.inquiry_body.length} / {MAX_BODY}자</div>
          {err("inquiry_body")}
        </label>
        <label>접수 시각 (UTC)
          <input type="datetime-local" step={1} value={form.received_at} onChange={set("received_at")} />
          <div className="small muted">비우면 지금</div>{err("received_at_utc")}
        </label>
        <fieldset className="wide contact">
          <legend>보낸 사람 연락처 <small className="muted">선택</small></legend>
          <input aria-label="이름" placeholder="이름" value={form.contact_name} onChange={set("contact_name")} />
          <input aria-label="이메일" placeholder="이메일" value={form.contact_email} onChange={set("contact_email")} />
          <input aria-label="전화번호" placeholder="전화번호" value={form.contact_phone} onChange={set("contact_phone")} />
        </fieldset>
        <div className="wide intake-buttons">
          {failure && <span className="bad">! {failure}</span>}
          <button type="button" onClick={clear} disabled={busy}>비우기</button>
          <button type="submit" className="primary" disabled={busy}>{busy ? "접수 중…" : "접수"}</button>
        </div>
      </form>

      {loading && <LoadPopup onLoaded={fill} onClose={() => setLoading(false)} />}
    </div>
  );
}

const mmss = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

/** 지금에서 녹음 길이를 뺀 UTC 시각(통화 시작 추정, 구현 선택 C-181) → 입력 칸 값 */
function callStart(durationSec: number): string {
  return new Date(Date.now() - durationSec * 1000).toISOString().slice(0, 19);
}

/** 통화 녹음 칸 (명세서 FR-050 처리 6·7, 기술 명세서 v1.4.1 §12-5). 채널 PHONE일 때만 보인다 */
function CallPanel({ customerId, language, productCode, onNote }: {
  customerId: string; language: string; productCode: string; onNote: (note: string, startedAt: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<CallResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "transcribe" | "note">("");

  function show(note: CallNote, startedAt: string) {
    if (note.note_en) onNote(note.note_en, startedAt); // 메모 초안은 본문 칸에 바로 채운다. 상담원이 고친 뒤 [접수]
  }

  async function transcribe() {
    if (!file) return;
    setBusy("transcribe");
    setError(null);
    try {
      const res = await api.transcribe(file, customerId, language, productCode);
      setResult(res);
      show(res, callStart(res.duration_sec));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "서버에 닿지 못함");
    } finally {
      setBusy("");
    }
  }

  async function redraft() {
    if (!result) return;
    setBusy("note");
    setError(null);
    try {
      const note = await api.noteDraft(result.utterances, language, productCode || null);
      setResult({ ...result, ...note });
      show(note, callStart(result.duration_sec));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "서버에 닿지 못함");
    } finally {
      setBusy("");
    }
  }

  const gapAt = (sec: number) => result?.gaps.find((g) => g.reason === "NO_SPEECH" && Math.abs(g.end_sec - sec) < 0.05);

  return (
    <fieldset className="wide call-panel">
      <legend>통화 녹음 <small className="muted">AI가 녹음 전체를 받아쓰고 메모 초안을 만듭니다. 저장하지 않습니다</small></legend>
      <div className="call-upload">
        <input type="file" accept=".wav,.mp3,.flac,.ogg" aria-label="통화 녹음 파일"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(null); }} />
        <button type="button" onClick={transcribe} disabled={!file || busy !== ""}>
          {busy === "transcribe" ? "받아쓰기 중…" : error && !result ? "다시 받아쓰기" : "받아쓰기"}
        </button>
        <span className="small muted">wav·mp3·flac·ogg, 20MB·15분 이하</span>
      </div>
      {error && <p className="bad">! {error}</p>}
      {result && (
        <div className="call-result">
          <div className="call-transcript">
            <h4>받아쓴 글 <small className="muted">{mmss(result.duration_sec)}</small></h4>
            {result.gaps.length > 0 && <p className="bad small">받아쓰지 못한 구간 {result.gaps.length}곳: 녹음과 대조하세요</p>}
            <ol>
              {result.utterances.map((u) => {
                const gap = gapAt(u.start_sec);
                const inaudible = u.text.toLowerCase().includes("[inaudible]");
                return (
                  <li key={u.no}>
                    {gap && <div className="call-gap">받아쓰지 못한 구간 {mmss(gap.start_sec)}~{mmss(gap.end_sec)}</div>}
                    <span className="muted">[{u.no}] {u.speaker === "AGENT" ? "상담원" : "고객"} {mmss(u.start_sec)}</span>{" "}
                    {inaudible ? <span className="call-gap">알아들을 수 없음 {mmss(u.start_sec)}~{mmss(u.end_sec)}</span> : u.text}
                  </li>
                );
              })}
            </ol>
            {result.gaps.filter((g) => g.reason === "NO_SPEECH" && !result.utterances.some((u) => Math.abs(u.start_sec - g.end_sec) < 0.05))
              .map((g) => <div key={g.start_sec} className="call-gap">받아쓰지 못한 구간 {mmss(g.start_sec)}~{mmss(g.end_sec)}</div>)}
          </div>
          <div className="call-note">
            <h4>메모 초안 <small className="muted">본문 칸에 채움 · 가린 곳 {result.mask_count}</small></h4>
            {result.note_error ? <p className="bad">! {result.note_error}</p> : <p>{result.note_en}</p>}
            {result.provided.length > 0 && (
              <ul className="call-provided">
                {result.provided.map((p) => (
                  <li key={`${p.field_code}-${p.value}`} className={p.found ? "" : "bad"}>
                    {p.label}={p.value} {p.found ? <span className="muted small">[{p.utterance_no}]</span> : <strong>({p.message})</strong>}
                  </li>
                ))}
              </ul>
            )}
            <button type="button" onClick={redraft} disabled={busy !== "" || result.utterances.length === 0}>
              {busy === "note" ? "만드는 중…" : "메모 다시 만들기"}
            </button>
          </div>
        </div>
      )}
    </fieldset>
  );
}

/** SCR-01-P1 시연용 문의 불러오기 */
function LoadPopup({ onLoaded, onClose }: { onLoaded: (l: Loaded) => void; onClose: () => void }) {
  const [id, setId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(e: React.FormEvent) {
    e.preventDefault();
    const value = id.trim().toUpperCase();
    if (!ID_FORMAT.test(value)) { setError("형식: CSV1-000000 또는 GS-001"); return; }
    setBusy(true);
    try {
      onLoaded(await api.load(value));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "불러오지 못함");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-label="시연용 문의 불러오기">
      <form className="modal" onSubmit={load}>
        <h3>시연용 문의 불러오기</h3>
        <label>문의 번호 <input autoFocus value={id} onChange={(e) => { setId(e.target.value); setError(null); }} placeholder="CSV1-000017 또는 GS-001" /></label>
        {error && <p className="bad">! {error}</p>}
        <p className="small muted">입력 6칸(채널·고객·제품·언어·본문·접수 시각)만 채웁니다. 제목과 정답은 채우지 않습니다.</p>
        <div className="modal-buttons">
          <button type="button" onClick={onClose}>닫기</button>
          <button type="submit" className="primary" disabled={busy}>불러오기</button>
        </div>
      </form>
    </div>
  );
}
