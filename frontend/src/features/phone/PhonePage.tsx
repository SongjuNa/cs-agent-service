// SCR-05 전화 상담 (명세서 FR-050, 기술 명세서 §12 통화 받아쓰기 1단계, 화면 명세 SCR-05). 저장은 [접수] 한 번뿐(D36).
// 배치는 목업 v1.42 `viewPhone`: 위 막대 → 왼쪽 대화 / 오른쪽 판단·필수 정보 → 아래 통화 메모. 위 막대는 "녹음 올리기"(정할 것 Q7).
import { useEffect, useState } from "react";
import { api, ApiError, fieldErrors, type CallGap, type CallResult, type Customer, type Utterance } from "../../api";
import { URGENCY, label } from "../../app/labels";
import { Banner, Button, Chip, Field, PageHeader } from "../../ui";
import { langName } from "../ticket/CustomerTab";
import "./phone.css";

const LANGUAGES = ["ar", "de", "en", "es", "fr", "id", "it", "ja", "pl", "pt", "ru", "th", "tr", "vi", "zh"];
const MAX_NOTE = 2000;
const EMPTY_HINT = "통화가 끝난 뒤 녹음을 올리면 AI가 받아쓰고 영어 메모 초안을 만듭니다";
const GAP_REASON: Record<string, string> = { NO_SPEECH: "말소리 없음", INAUDIBLE: "알아들을 수 없음" };

export const mmss = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

/** 지금에서 녹음 길이를 뺀 UTC 시각(통화 시작 추정, 구현 선택 C-181) → 입력 칸 값 */
function callStart(durationSec: number): string {
  return new Date(Date.now() - durationSec * 1000).toISOString().slice(0, 19);
}

type Form = { customer_id: string; language: string; product_code: string; received_at: string };
type Saved = { ticketId: string };

export function PhonePage({ onOpen }: { onOpen: (ticketId: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState<Form>({ customer_id: "", language: "en", product_code: "", received_at: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CallResult | null>(null);
  const [utterances, setUtterances] = useState<Utterance[]>([]);
  const [edited, setEdited] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"" | "transcribe" | "note" | "intake">("");
  const [failure, setFailure] = useState<{ kind: "transcribe" | "note"; message: string } | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const customer = useCustomer(form.customer_id.trim());

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function transcribe() {
    const miss: Record<string, string> = {};
    if (!file) miss.file = "받을 수 없는 녹음 파일";
    if (!form.customer_id.trim()) miss.customer_id = "고객 ID를 찾을 수 없음";
    setErrors(miss);
    if (!file || Object.keys(miss).length) return;
    setBusy("transcribe"); setFailure(null); setSaved(null);
    try {
      const res = await api.transcribe(file, form.customer_id.trim(), form.language, form.product_code.trim());
      setResult(res);
      setUtterances(res.utterances);
      setEdited(false);
      setNote(res.note_en ?? "");
      if (res.note_error && res.utterances.length) setFailure({ kind: "note", message: res.note_error });
      setForm((f) => ({ ...f, received_at: f.received_at || callStart(res.duration_sec) }));
    } catch (err) {
      const list = fieldErrors(err);
      if (list.length) setErrors(Object.fromEntries(list.map((x) => [x.field, x.message])));
      else setFailure({ kind: "transcribe", message: err instanceof ApiError ? err.message : "서버에 닿지 못함" });
    } finally {
      setBusy("");
    }
  }

  async function redraft() {
    if (!result) return;
    setBusy("note"); setFailure(null);
    try {
      const res = await api.noteDraft(utterances, form.language, form.product_code.trim() || null);
      setResult({ ...result, ...res });
      if (res.note_error) setFailure({ kind: "note", message: res.note_error });
      else { setNote(res.note_en ?? ""); setEdited(false); }
    } catch (err) {
      setFailure({ kind: "note", message: err instanceof ApiError ? err.message : "서버에 닿지 못함" });
    } finally {
      setBusy("");
    }
  }

  async function intake() {
    setBusy("intake"); setErrors({});
    const r = form.received_at;
    try {
      const res = await api.intake({
        channel: "PHONE", customer_id: form.customer_id.trim(), product_code: form.product_code.trim() || null, language: form.language,
        inquiry_subject: null, inquiry_body: note, received_at_utc: r ? `${r.length === 16 ? `${r}:00` : r}Z` : null,
        source_ticket_id: null, contact_name: null, contact_email: null, contact_phone: null,
      });
      setSaved({ ticketId: res.ticket_id });
    } catch (err) {
      const list = fieldErrors(err);
      if (list.length) setErrors(Object.fromEntries(list.map((x) => [x.field, x.message])));
      else setErrors({ inquiry_body: `접수 실패: ${err instanceof ApiError ? err.message : "서버에 닿지 못함"}` });
    } finally {
      setBusy("");
    }
  }

  const done = result !== null || failure?.kind === "transcribe"; // 받아쓰기를 한 번 해 봤으면 메모 칸을 연다
  return (
    <div className="ph">
      <PageHeader title="전화 상담" meta="통화 녹음을 받아 적어 판단과 필수 정보 확인을 돕습니다" />

      <section className="ui-card ph-bar" aria-label="녹음 올리기">
        <div className="ph-bar__in">
          <Field label="녹음 파일" required error={errors.file} hint="wav·mp3·flac·ogg, 20MB·15분 이하">
            <input type="file" accept=".wav,.mp3,.flac,.ogg"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setErrors((x) => ({ ...x, file: "" })); }} />
          </Field>
          <Field label="고객 ID" required error={errors.customer_id}>
            <input value={form.customer_id} onChange={set("customer_id")} placeholder="CUST-0350" />
          </Field>
          <Field label="고객 언어" required error={errors.language}>
            <select value={form.language} onChange={set("language")}>
              {LANGUAGES.map((l) => <option key={l} value={l}>{langName(l)}</option>)}
            </select>
          </Field>
          <Field label="제품 코드" error={errors.product_code}>
            <input value={form.product_code} onChange={set("product_code")} placeholder="모르면 비우세요" />
          </Field>
          <Field label="접수 시각 (UTC)" hint="비우면 통화 시작 시각" error={errors.received_at_utc}>
            <input type="datetime-local" step={1} value={form.received_at} onChange={set("received_at")} />
          </Field>
          <Button variant="primary" onClick={transcribe} busy={busy === "transcribe"} disabled={busy !== ""} data-testid="transcribe">
            {failure?.kind === "transcribe" ? "다시 받아쓰기" : "받아쓰기"}
          </Button>
        </div>
        <div className="ph-bar__info" data-testid="call-info">
          <b className="ph-dur">{result ? mmss(result.duration_sec) : "—:—"}</b>
          <span>{customer ? <>{customer.company_masked} · {customer.country} · {customer.tier}</> : "고객 정보 없음"}</span>
        </div>
      </section>

      {failure?.kind === "transcribe" && (
        <Banner tone="neg" title={failure.message}
          action={<Button size="sm" onClick={transcribe} disabled={busy !== ""}>다시 받아쓰기</Button>}>
          녹음을 다시 받아쓰거나, 아래 메모 칸에 직접 써서 접수할 수 있습니다.
        </Banner>
      )}

      <div className="ph-grid">
        <section className="ui-card ph-talk" aria-label="받아쓴 대화">
          <div className="ui-card__head"><h2 className="ui-card__title">받아쓴 대화</h2>
            <span className="ph-sub">발화마다 고칠 수 있습니다</span></div>
          <div className="ph-talk__body">
            {busy === "transcribe" ? <p className="ph-wait" role="status"><span className="ph-dots" aria-hidden />받아쓰기 중</p>
              : !result ? <p className="ph-empty">{EMPTY_HINT}</p>
              : utterances.length === 0 ? <p className="ph-empty">받아쓴 내용 없음</p>
              : <Transcript utterances={utterances} gaps={result.gaps}
                  onEdit={(no, text) => { setUtterances((us) => us.map((u) => (u.no === no ? { ...u, text } : u))); setEdited(true); }} />}
          </div>
        </section>

        <div className="ph-side">
          <section className="ui-card" aria-label="시스템이 판단한 것">
            <div className="ui-card__head"><h2 className="ui-card__title">시스템이 판단한 것</h2>
              <span className="ph-sub">확정은 상담원이 합니다</span></div>
            <dl className="ph-kv">
              <dt>긴급도</dt>
              <dd data-testid="urgency">{result?.urgency ? <>{label(URGENCY, result.urgency)} <span className="ph-mono">{result.urgency}</span></> : "—"}</dd>
            </dl>
            <p className="ph-note">유형·우선순위·부서는 접수 뒤 티켓 상세에서 정해집니다</p>
          </section>
          <section className="ui-card" aria-label="필수 정보">
            <div className="ui-card__head"><h2 className="ui-card__title">필수 정보</h2>
              <span className="ph-sub">메모에 든 값을 받아쓴 글과 대조</span></div>
            <Provided result={result} />
          </section>
        </div>
      </div>

      <section className="ui-card ph-memo" aria-label="통화 메모 초안">
        <div className="ui-card__head"><h2 className="ui-card__title">통화 메모 초안</h2>
          <span className="ph-sub">[접수] 전에는 아무것도 저장되지 않습니다</span>
          {result && <Chip tone="neu">가린 곳 {result.mask_count}</Chip>}
          {edited && <Chip tone="crit">대화를 고침: 메모 다시 만들기</Chip>}
        </div>
        <div className="ph-memo__body">
          {failure?.kind === "note" && (
            <Banner tone="neg" title={failure.message}
              action={<Button size="sm" onClick={redraft} disabled={busy !== ""}>다시 만들기</Button>}>받아쓴 대화는 그대로 있습니다.</Banner>
          )}
          <Field label="메모 (영어)" required error={errors.inquiry_body}
            hint={<span className={note.length > MAX_NOTE ? "tk-neg" : undefined}>{note.length.toLocaleString()} / 2,000자</span>}>
            <textarea rows={6} value={note} onChange={(e) => setNote(e.target.value)} disabled={!done || saved !== null}
              placeholder={done ? "메모를 직접 쓸 수 있습니다" : EMPTY_HINT} data-testid="memo" />
          </Field>
          {saved ? (
            <Banner tone="info" title={`${saved.ticketId} 티켓으로 저장됨`}
              action={<Button size="sm" variant="primary" onClick={() => onOpen(saved.ticketId)}>티켓 상세 보기</Button>}>
              채널 전화, 본문은 확인한 메모입니다.
            </Banner>
          ) : (
            <div className="ph-actions">
              <Button onClick={redraft} busy={busy === "note"} disabled={busy !== "" || !result || utterances.length === 0}>메모 다시 만들기</Button>
              <Button variant="primary" onClick={intake} busy={busy === "intake"} disabled={busy !== "" || !done}>접수</Button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function useCustomer(id: string): Customer | null {
  const [c, setC] = useState<Customer | null>(null);
  useEffect(() => {
    if (!/^CUST-\d{4}$/.test(id)) { setC(null); return; }
    let live = true;
    api.customers(id).then((list) => live && setC(list.find((x) => x.customer_id === id) ?? null)).catch(() => live && setC(null));
    return () => { live = false; };
  }, [id]);
  return c;
}

/** 발화와 받아쓰지 못한 구간을 시각순으로. 빈 시간(NO_SPEECH)은 그 뒤 첫 발화 앞에, 알아들을 수 없음은 그 발화 자리에 */
function Transcript({ utterances, gaps, onEdit }: { utterances: Utterance[]; gaps: CallGap[]; onEdit: (no: number, text: string) => void }) {
  const silent = gaps.filter((g) => g.reason === "NO_SPEECH");
  const before = (u: Utterance) => silent.filter((g) => g.end_sec <= u.start_sec + 0.05 && g.end_sec > (prevEnd.get(u.no) ?? -1) - 0.05);
  const prevEnd = new Map<number, number>();
  utterances.reduce((end, u) => { prevEnd.set(u.no, end); return Math.max(end, u.end_sec); }, -1);
  const last = utterances.length ? Math.max(...utterances.map((u) => u.end_sec)) : 0;
  const tail = silent.filter((g) => g.start_sec >= last - 0.05);
  return (
    <ol className="ph-lines">
      {utterances.map((u) => {
        const inaudible = gaps.find((g) => g.reason === "INAUDIBLE" && Math.abs(g.start_sec - u.start_sec) < 0.1);
        return [
          ...before(u).map((g) => <GapLine key={`g${g.start_sec}`} gap={g} />),
          inaudible ? <GapLine key={u.no} gap={inaudible} /> : (
            <li key={u.no} className={u.speaker === "AGENT" ? "ph-line is-agent" : "ph-line"} data-testid="utterance" data-speaker={u.speaker}>
              <span className="ph-who">{u.speaker === "AGENT" ? "상담원" : "고객"} <time>{mmss(u.start_sec)}</time></span>
              <textarea className="ph-say" rows={Math.max(1, Math.ceil(u.text.length / 70))} value={u.text}
                aria-label={`${u.no}번 발화`} onChange={(e) => onEdit(u.no, e.target.value)} />
            </li>
          ),
        ];
      })}
      {tail.map((g) => <GapLine key={`t${g.start_sec}`} gap={g} />)}
    </ol>
  );
}

function GapLine({ gap }: { gap: CallGap }) {
  return (
    <li className="ph-gap" data-testid="gap" role="note">
      받아쓰지 못한 구간 {mmss(gap.start_sec)}–{mmss(gap.end_sec)} ({GAP_REASON[gap.reason] ?? gap.reason})
    </li>
  );
}

function Provided({ result }: { result: CallResult | null }) {
  if (!result || result.provided.length === 0) return <p className="ph-empty">{result ? "메모에 든 값이 없습니다" : "받아쓰기 뒤에 보입니다"}</p>;
  const found = result.provided.filter((p) => p.found).length;
  return (
    <>
      <ul className="ph-req">
        {result.provided.map((p) => (
          <li key={`${p.field_code}-${p.value}`} className={p.found ? "is-found" : "is-missing"} data-testid="provided" data-field={p.field_code}>
            <span className="ph-req__mark" aria-hidden>{p.found ? "✓" : "!"}</span>
            <span className="ph-req__label">{p.label}</span>
            <span className="ph-req__val">
              <b>{p.value}</b>
              {p.found ? <small>{p.utterance_no ? `${p.utterance_no}번 발화` : "찾음"}</small> : <em>{p.message}</em>}
            </span>
          </li>
        ))}
      </ul>
      <p className="ph-count" data-testid="provided-count">필수 정보 {found}/{result.provided.length}</p>
    </>
  );
}
