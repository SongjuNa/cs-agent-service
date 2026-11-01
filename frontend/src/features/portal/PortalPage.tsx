// 고객 포털 미리보기 (SCR-13, 변경 add-portal-preview). 고객이 보는 화면: 문의 방법을 고르고, 챗봇 ELLO와 대화하거나 상담원 문의를 남긴다.
// 상담원 시스템과 분리된 화면이며 고객에게는 공개 문서만 보인다. 시연용이라 챗봇 답은 규칙으로 만든 예시이고, 접수 번호도 예시다(서버에 문의를 만들지 않는다).
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Clock, Headphones, Paperclip, Send, Star, ThumbsDown, ThumbsUp, TriangleAlert, UserRound, Zap } from "./lucide";
import { CAT, fieldLabel, fieldLabelEn } from "./portalData";
import { koSection, koTerms } from "./docKo";
import { maskPII } from "./mask";
import { CAT_EN, FIELD_DEFS, REQUIRED_BY_CAT, UNKNOWN, fieldsOf, isBlocking, missingFields, type Values } from "./intakeForm";
import { L, botReply, checkAnswer, greeting, type AnswerInput, type BotMsg, type BotState, type Lang, type Submitted } from "./botCustomer";
import ello from "../../assets/ello.png";
import logo from "../../assets/logo-ls.png";
import "./portal.css";

type View = 'choose' | 'form' | 'chat' | 'rate' | 'done'
type Sub = Submitted & { ticket: string }
const NEW_ST: BotState = { asked: 0, fails: 0 }
const ticketNo = () => `CSV1-${4000 + Math.floor(Math.random() * 900)}`

/**
 * 고객 포털 (고객이 보는 화면): 문의 방법을 고르고, 챗봇 ELLO와 대화하거나 상담원 문의를 남긴다.
 * 상담원 시스템과 분리된 화면이며, 고객에게는 공개 문서만 보인다. 목업은 AI 대신 규칙으로 답한다.
 */
export function PortalPage({ onExit }: { onExit: () => void }) {
  const [lang, setLang] = useState<Lang>('ko')
  const [view, setView] = useState<View>('choose')
  const t = (ko: string, en: string) => L(lang, ko, en)
  const [receipt, setReceipt] = useState<{ no: string; via: string; n?: number } | null>(null)

  return (
    <div className="pt">
      <header className="pt-top">
        <div className="pt-brand"><img src={logo} alt="LS" /><b>{t('고객지원 센터', 'Customer Support')}</b></div>
        <span className="grow" />
        <div className="pt-lang" role="group" aria-label="language">
          {(['ko', 'en'] as Lang[]).map((l) => <button key={l} className={lang === l ? 'on' : ''} onClick={() => setLang(l)}>{l === 'ko' ? '한국어' : 'English'}</button>)}
        </div>
        <a href="/inbox" className="pt-demo" title="시연용 미리보기에서 상담원 시스템으로 돌아갑니다" onClick={(e) => { e.preventDefault(); onExit(); }}><ArrowLeft size={14} />상담원 시스템 (시연용 미리보기)</a>
      </header>

      <main className="pt-main">
        {view === 'choose' && <Choose lang={lang} onPick={(v) => setView(v)} />}
        {view === 'form' && <WebForm lang={lang} onBack={() => setView('choose')} onDone={(no, n) => { setReceipt({ no, via: 'form', n }); setView('done') }} />}
        {view === 'chat' && <Chat lang={lang} onBack={() => setView('choose')} onEnd={(no) => { setReceipt(no ? { no, via: 'chat' } : null); setView('rate') }} />}
        {view === 'rate' && <Rate lang={lang} ticket={receipt?.no} onDone={() => setView('done')} />}
        {view === 'done' && (
          <section className="pt-card pt-center">
            <span className="pt-ok"><Check size={26} /></span>
            <h2>{receipt?.via === 'form' ? t('문의를 접수했어요', 'Your inquiry has been received') : t('이용해 주셔서 감사합니다', 'Thank you for contacting us')}</h2>
            {receipt?.no && <p className="muted">{t('문의 번호', 'Reference number')} <b className="mono">{receipt.no}</b><br />{receipt.via === 'form' ? t(`필수 정보 ${receipt.n ?? ''}개를 모두 받았어요. 추가 요청 없이 바로 처리를 시작해요. 첫 답변은 문의 내용과 고객 등급에 따라 최대 72시간 이내에 이메일로 보내 드려요.`, `We received all ${receipt.n ?? ''} required items, so we can start right away without asking again. Your first reply will be emailed within 72 hours at most, depending on the inquiry and your service level.`) : t('대화 내용은 이메일로도 보내 드려요.', 'A copy of this conversation will also be sent to you by email.')}</p>}
            <button className="pt-btn primary" onClick={() => { setReceipt(null); setView('choose') }}>{t('새로 문의하기', 'Start a new inquiry')}</button>
          </section>
        )}
      </main>
      <footer className="pt-foot">{t('이 화면은 시연용입니다. 챗봇 답변은 규칙으로 만든 예시이며 실제 AI 응답이 아닙니다.', 'Demo screen. Chatbot answers are rule-based examples, not real AI responses.')}</footer>
    </div>
  )
}

function Choose({ lang, onPick }: { lang: Lang; onPick: (v: View) => void }) {
  const t = (ko: string, en: string) => L(lang, ko, en)
  // 장단점을 따지게 하지 않고, 내 문의가 어느 쪽인지 바로 알아보게 한다: 고객의 말, 예시 문의 3개, 답변 시간 한 줄
  const ways = [
    { v: 'chat' as View, icon: <img src={ello} alt="" />, tone: 'chat', say: t('지금 바로 답을 받고 싶어요', 'I want an answer right now'), title: t('챗봇 ELLO', 'Chat with ELLO'),
      goodFor: [t('제품 사양, 문서 찾기', 'Specs and documents'), t('보증·반품 정책 확인', 'Warranty and return policy'), t('간단한 질문', 'Quick questions')],
      time: t('답변 즉시', 'Instant answer'), timeIcon: <Zap size={18} />, btn: t('챗봇으로 문의하기', 'Chat now') },
    { v: 'form' as View, icon: <UserRound size={24} />, tone: 'form', say: t('자세히 남기고 답을 기다릴게요', 'I will leave the details and wait'), title: t('상담원에게 문의 (웹 폼)', 'Contact a specialist (web form)'),
      goodFor: [t('제품 고장, 오류', 'Faults and errors'), t('견적, 주문, 반품·교환', 'Quotes, orders, returns'), t('사진·파일 여러 개 보내기', 'Sending many photos or files')],
      time: t('상담원이 확인 후 답변 · 최대 72시간', 'Specialist reply · up to 72 hours'), timeIcon: <Clock size={18} />, btn: t('웹 폼으로 문의하기', 'Use the web form') },
  ]
  return (
    <section>
      <h1 className="pt-h1">{t('무엇을 도와드릴까요?', 'How can we help you?')}</h1>
      <p className="pt-sub">{t('문의 방법을 골라 주세요.', 'Please choose how you would like to contact us.')}</p>
      <div className="pt-ways">
        {ways.map((w) => (
          <article key={w.v} className={`pt-card pt-way ${w.tone}`}>
            <p className="pt-say">“{w.say}”</p>
            <div className="pt-way-h"><span className="pt-ic">{w.icon}</span><b>{w.title}</b></div>
            <div className="pt-good"><small>{t('이런 문의에 좋아요', 'Best for')}</small><ul>{w.goodFor.map((x) => <li key={x}><Check size={16} />{x}</li>)}</ul></div>
            <div className="pt-time">{w.timeIcon}<b>{w.time}</b></div>
            <button className="pt-btn primary pt-go" onClick={() => onPick(w.v)}>{w.btn}</button>
          </article>
        ))}
      </div>
      <p className="pt-reassure"><Headphones size={15} />{t('챗봇으로 시작해도 언제든 상담원에게 문의를 남길 수 있어요.', 'Even if you start with the chatbot, you can leave an inquiry for a specialist at any time.')}</p>
    </section>
  )
}

function WebForm({ lang, onBack, onDone }: { lang: Lang; onBack: () => void; onDone: (no: string, n: number) => void }) {
  const t = (ko: string, en: string) => L(lang, ko, en)
  const [cat, setCat] = useState('')
  const [vals, setVals] = useState<Values>({})
  const [f, setF] = useState({ company: '', email: '', body: '' })
  const [tried, setTried] = useState(false)
  const [agreed, setAgreed] = useState(false) // 개인정보 동의: 시연용 표시일 뿐 어디에도 저장하지 않는다(팀 화면 검토 2026-11-01)
  const keys = cat ? fieldsOf(cat) : []
  const missing = cat ? missingFields(cat, vals) : []
  const bad = { cat: !cat, email: !/.+@.+\..+/.test(f.email), body: f.body.trim().length < 10, agree: !agreed }
  const masked = maskPII(f.body).count
  const set = (k: string, v: string | string[]) => setVals((x) => ({ ...x, [k]: v }))
  const done = keys.length - missing.length
  const errCount = (bad.cat ? 1 : 0) + missing.length + (bad.body ? 1 : 0) + (bad.email ? 1 : 0) + (bad.agree ? 1 : 0)
  const submit = () => {
    setTried(true)
    if (errCount) { setTimeout(() => document.querySelector('.pt-field.err, .pt-types.err')?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 0); return }
    onDone(ticketNo(), keys.length)
  }
  const label = (k: string) => (lang === 'ko' ? fieldLabel(k) : fieldLabelEn(k))

  return (
    <section className="pt-card pt-form">
      <button className="pt-link" onClick={onBack}><ArrowLeft size={14} />{t('문의 방법 다시 고르기', 'Choose another way')}</button>
      <h2>{t('상담원에게 문의', 'Contact a specialist')}</h2>

      <div className={`pt-step ${tried && bad.cat ? 'err' : ''}`}><span>1</span><b>{t('어떤 문의인가요?', 'What is your inquiry about?')}</b></div>
      <div className={`pt-types ${tried && bad.cat ? 'err' : ''}`} role="radiogroup">
        {Object.keys(REQUIRED_BY_CAT).map((c) => (
          <button key={c} type="button" role="radio" aria-checked={cat === c} className={cat === c ? 'on' : ''} onClick={() => { setCat(c); setVals({}) }}>{lang === 'ko' ? CAT[c] : CAT_EN[c]}</button>
        ))}
      </div>
      {tried && bad.cat && <span className="err">{t('문의 유형을 골라 주세요', 'Please choose a type')}</span>}

      {cat && (
        <>
          <div className="pt-step"><span>2</span><b>{t('처리에 꼭 필요한 정보', 'Information we need to process this')}</b></div>
          <div className="pt-need">
            
            <div className="pt-prog" role="progressbar" aria-valuenow={done} aria-valuemax={keys.length}><i style={{ width: `${(done / Math.max(1, keys.length)) * 100}%` }} /></div>
            <small>{t(`필수 정보 ${done} / ${keys.length} 입력`, `${done} of ${keys.length} required items completed`)}</small>
          </div>
          <div className="pt-grid">
            {keys.map((k) => {
              const d = FIELD_DEFS[k]
              const blk = isBlocking(cat, k)
              const err = tried && missing.includes(k)
              const v = vals[k]
              const unk = v === UNKNOWN
              return (
                <div key={k} className={`pt-field ${err ? 'err' : ''}`} style={d.type === 'textarea' || d.type === 'file' ? { gridColumn: '1 / -1' } : undefined}>
                  <label htmlFor={`f-${k}`}>{label(k)} <em>{t('필수', 'Required')}</em></label>
                  {d.type === 'select' && <select id={`f-${k}`} className="select" disabled={unk} value={unk ? '' : (v as string) ?? ''} onChange={(e) => set(k, e.target.value)}><option value="">{t('선택해 주세요', 'Select')}</option>{d.options?.map(([val, ko, en]) => <option key={val} value={val}>{lang === 'ko' ? ko : en}</option>)}</select>}
                  {d.type === 'text' && <input id={`f-${k}`} className="input" disabled={unk} value={unk ? '' : (v as string) ?? ''} placeholder={d.ph?.[lang === 'ko' ? 0 : 1]} onChange={(e) => set(k, e.target.value)} />}
                  {d.type === 'textarea' && <textarea id={`f-${k}`} className="textarea" style={{ minHeight: 70 }} disabled={unk} value={unk ? '' : (v as string) ?? ''} placeholder={d.ph?.[lang === 'ko' ? 0 : 1]} onChange={(e) => set(k, e.target.value)} />}
                  {d.type === 'date' && <input id={`f-${k}`} className="input" type="date" disabled={unk} value={unk ? '' : (v as string) ?? ''} onChange={(e) => set(k, e.target.value)} />}
                  {d.type === 'number' && <input id={`f-${k}`} className="input" type="number" min={1} disabled={unk} value={unk ? '' : (v as string) ?? ''} onChange={(e) => set(k, e.target.value)} />}
                  {d.type === 'file' && !unk && (
                    <div className="pt-files">
                      <label className="pt-pick"><Paperclip size={14} />{t('파일 올리기', 'Upload files')}<input id={`f-${k}`} type="file" multiple hidden onChange={(e) => set(k, [...((Array.isArray(v) ? v : []) as string[]), ...Array.from(e.target.files ?? []).map((x) => x.name)])} /></label>
                      {(Array.isArray(v) ? v : []).map((n, i) => <span key={n + i} className="pt-chip-file">{n}<button type="button" aria-label="remove" onClick={() => set(k, (v as string[]).filter((_, j) => j !== i))}>×</button></span>)}
                    </div>
                  )}
                  {!blk && (
                    <label className="pt-unk"><input type="checkbox" checked={unk} onChange={(e) => set(k, e.target.checked ? UNKNOWN : d.type === 'file' ? [] : '')} />{t('모르겠어요', "I don't know")}</label>
                  )}
                  {unk && <span className="pt-unk-note">{k === 'serial_no' && cat === 'RETURN' ? t('괜찮아요. PO·송장 번호와 명판 사진으로 제품을 확인할게요.', 'No problem. We will identify the unit from your PO/invoice number and nameplate photo.') : t('괜찮아요. 이 정보 없이도 처리를 시작할 수 있어요.', 'No problem. We can start without this information.')}</span>}
                  {d.help && <small>{d.help[lang === 'ko' ? 0 : 1]}</small>}
                  {err && <span className="err">{t('이 항목은 꼭 입력해 주세요', 'Please fill in this item')}</span>}
                </div>
              )
            })}
          </div>
        </>
      )}

      <div className="pt-step"><span>{cat ? 3 : 2}</span><b>{t('자세한 내용과 연락처', 'Details and contact')}</b></div>
      <div className="pt-grid">
        <div className={`pt-field ${tried && bad.body ? 'err' : ''}`} style={{ gridColumn: '1 / -1' }}>
          <label htmlFor="f-body">{t('문의 내용', 'Message')} <em>{t('필수', 'Required')}</em></label>
          <textarea id="f-body" className="textarea" style={{ minHeight: 110 }} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
          {tried && bad.body && <span className="err">{t('10자 이상 적어 주세요', 'Please write at least 10 characters')}</span>}
        </div>
        <div className={`pt-field ${tried && bad.email ? 'err' : ''}`}>
          <label htmlFor="f-email">{t('이메일', 'Email')} <em>{t('필수', 'Required')}</em></label>
          <input id="f-email" className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
          {tried && bad.email && <span className="err">{t('이메일을 확인해 주세요', 'Please check your email')}</span>}
        </div>
        <div className="pt-field"><label htmlFor="f-co">{t('회사명', 'Company')}</label><input id="f-co" className="input" value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} /></div>
      </div>
      <p className="faint" style={{ fontSize: 12 }}>{t('이메일과 전화번호 같은 개인정보는 저장하기 전에 자동으로 가려요.', 'Personal data such as emails and phone numbers is masked automatically before storage.')}{masked > 0 && ` (${masked})`}</p>

      {tried && errCount > 0 && <div className="pt-summary" role="alert"><TriangleAlert size={16} />{t(`입력하지 않은 필수 항목이 ${errCount}개 있어요. 빨간 표시를 확인해 주세요.`, `${errCount} required item(s) are missing. Please check the highlighted fields.`)}</div>}
      <div className={`pt-consent ${tried && bad.agree ? 'err' : ''}`}>
        <label><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <b>{t('개인정보 수집·이용에 동의합니다', 'I agree to the collection and use of my personal data')}</b> <em>{t('필수', 'Required')}</em></label>
        <small>{t('문의 처리와 답변 발송을 위해 이메일·회사명을 수집하며, 문의 처리가 끝난 뒤 정해진 기간이 지나면 삭제해요.', 'We collect your email and company name only to handle your inquiry and send our reply, and delete them after the retention period.')}</small>
        {tried && bad.agree && <span className="err">{t('개인정보 수집·이용에 동의해 주세요', 'Please agree to the personal data policy')}</span>}
      </div>
      <button className="pt-btn primary" onClick={submit}>{t('문의 보내기', 'Send')}</button>
    </section>
  )
}

/** 질문 바로 아래에서 답을 적고 보내는 칸. 양식에 맞지 않으면 이 칸 아래에 안내를 띄운다 */
function AnswerBox({ lang, input, onSend, onFile }: { lang: Lang; input: AnswerInput; onSend: (v: string) => void; onFile: (f: File) => void }) {
  const t = (ko: string, en: string) => L(lang, ko, en)
  const [v, setV] = useState('')
  const [err, setErr] = useState('')
  const pick = useRef<HTMLInputElement>(null)
  if (input.type === 'file') {
    return (
      <div className="pt-ans">
        <input ref={pick} type="file" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
        <button type="button" className="pt-btn primary" onClick={() => pick.current?.click()}><Paperclip size={14} />{t('파일 선택', 'Choose a file')}</button>
      </div>
    )
  }
  const go = () => { const e = checkAnswer(input.type, v, lang); setErr(e); if (!e) onSend(v.trim()) }
  const common = { id: 'pt-ans', value: v, 'aria-label': input.label, 'aria-invalid': !!err, onChange: (e: { target: { value: string } }) => { setV(e.target.value); setErr('') } }
  return (
    <form className="pt-ans" onSubmit={(e) => { e.preventDefault(); go() }} noValidate>
      <div className="pt-ans-r">
        {input.type === 'textarea'
          ? <textarea {...common} className={`textarea ${err ? 'err' : ''}`} rows={2} placeholder={input.ph} />
          : <input {...common} className={`input ${err ? 'err' : ''}`} type={input.type === 'number' ? 'text' : input.type} inputMode={input.type === 'number' ? 'decimal' : undefined} placeholder={input.ph} autoFocus />}
        <button type="submit" className="pt-btn primary">{t('보내기', 'Send')}</button>
      </div>
      {err && <small className="pt-ans-err" role="alert">{err}</small>}
    </form>
  )
}

function Chat({ lang, onBack, onEnd }: { lang: Lang; onBack: () => void; onEnd: (ticket?: string) => void }) {
  const t = (ko: string, en: string) => L(lang, ko, en)
  const [msgs, setMsgs] = useState<BotMsg[]>(() => [greeting(lang)])
  const [st, setSt] = useState<BotState>(NEW_ST)
  const [text, setText] = useState('')
  const [typing, setTyping] = useState(false)
  const [sub, setSub] = useState<Sub | null>(null)
  const [open, setOpen] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const file = useRef<HTMLInputElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [msgs, typing, sub])

  const send = (raw: string, attach?: string) => {
    const v = raw.trim()
    if (!v && !attach) return
    const shown = maskPII(v)
    setMsgs((m) => [...m, { who: 'me', text: shown.text, attach }])
    setText('')
    if (shown.count) setMsgs((m) => [...m, { who: 'sys', text: t(`개인정보 ${shown.count}곳을 가려서 저장했어요.`, `${shown.count} piece(s) of personal data were masked.`) }])
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      if (sub) { setMsgs((m) => [...m, { who: 'bot', text: t('이미 접수된 문의예요. 새 문의는 아래 “새로 문의하기”를 눌러 주세요.', 'This inquiry is already filed. Use “New inquiry” below to start another.') }]); return }
      // 접수 중에 파일을 올리면 그 파일 이름이 지금 묻는 항목의 답이 된다
      if (attach && !v && !st.intake) { setMsgs((m) => [...m, { who: 'bot', text: t('사진을 받았어요. 상담원이 확인할 수 있게 함께 전달할게요. 어떤 제품의 사진인지 알려 주시겠어요?', 'Got your photo and I will pass it on. Which product is it?') }]); return }
      const r = botReply(v || attach || '', lang, st)
      setSt(r.st)
      setMsgs((m) => [...m, ...r.msgs])
      if (r.submitted) setTimeout(() => setSub({ ...r.submitted!, ticket: ticketNo() }), 400)
    }, 650)
  }
  const inlineAsk = !sub && msgs[msgs.length - 1]?.input
  const onFile = (f?: File) => { if (f) send('', f.name) }

  return (
    <section className="pt-chat">
      <header className="pt-chat-h">
        <button className="pt-link" onClick={onBack} aria-label={t('뒤로', 'Back')}><ArrowLeft size={16} /></button>
        <span className="pt-av"><img src={ello} alt="" /></span>
        <div className="grow"><b>ELLO</b><small><i className="sdot ok" /> {t('LS 고객지원 챗봇 · 온라인', 'LS support chatbot · online')}</small></div>
        {!sub && <button className="pt-btn" onClick={() => send(t('상담원에게 문의', 'Contact a specialist'))}><Headphones size={15} />{t('상담원에게 문의', 'Contact a specialist')}</button>}
        <button className="pt-btn" onClick={() => onEnd(sub?.ticket)}>{t('상담 종료', 'End chat')}</button>
      </header>

      <div className="pt-msgs">
        {msgs.map((m, i) => (
          <div key={i} className={`pt-row ${m.who}`}>
            {(m.who === 'bot') && <span className="pt-av sm"><img src={ello} alt="" /></span>}
                        <div className="pt-col">
              {m.who !== 'sys' && m.who !== 'me' && <small className="pt-who">ELLO</small>}
              <div className={`pt-bubble ${m.emergency ? 'danger' : ''}`}>
                {m.emergency && <b className="pt-alert"><TriangleAlert size={15} />{t('안전 안내', 'Safety notice')}</b>}
                {m.attach && <div className="pt-attach"><Paperclip size={13} />{m.attach}</div>}
                {m.text}
              </div>
              {m.cites && m.cites.length > 0 && (
                <div className="pt-cites">
                  {m.cites.map((c, j) => {
                    const k = `${i}-${j}`
                    return (
                      <div key={k}>
                        <button className="pt-cite" onClick={() => setOpen(open === k ? '' : k)} aria-expanded={open === k}>{t('근거', 'Source')}: {c.label}</button>
                        {open === k && <div className="pt-excerpt"><b>{lang === 'ko' ? koSection(c.title) : c.title}</b><p>{lang === 'ko' ? koTerms(c.excerpt) : c.excerpt}</p></div>}
                      </div>
                    )
                  })}
                </div>
              )}
              {m.input && i === msgs.length - 1 && !sub && !typing && <AnswerBox key={i} lang={lang} input={m.input} onSend={(v) => send(v)} onFile={(f) => onFile(f)} />}
              {m.chips && i === msgs.length - 1 && !sub && <div className="pt-chips">{m.chips.map((c) => <button key={c} onClick={() => send(c)}>{c}</button>)}</div>}
            </div>
          </div>
        ))}
        {typing && <div className="pt-row bot"><span className="pt-av sm"><img src={ello} alt="" /></span><div className="pt-bubble pt-dots" aria-label="typing"><i /><i /><i /></div></div>}
        {sub && (
          <div className="pt-hand done">
            <div>
              <b><Check size={15} /> {t('문의로 접수했어요', 'Inquiry filed')}</b>
              <dl>{[[t('문의 번호', 'Reference'), sub.ticket], ...sub.rows].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
              <small>{sub.urgent
                ? t('긴급 문의는 가장 먼저 확인해요. 첫 답변은 최대 4시간 이내에 이메일로 보내 드려요. 대화 내용이 함께 전달됐어요.', 'Urgent inquiries are reviewed first. Your first reply will be emailed within 4 hours at most. Your conversation was passed on.')
                : t('첫 답변은 문의 내용과 고객 등급에 따라 최대 72시간 이내에 이메일로 보내 드려요. 대화 내용이 함께 전달됐어요.', 'Your first reply will be emailed within 72 hours at most, depending on the inquiry and your service level. Your conversation was passed on.')}</small>
              <button className="pt-btn" onClick={() => { setSub(null); setSt(NEW_ST); setMsgs([greeting(lang)]) }}>{t('새로 문의하기', 'New inquiry')}</button>
            </div>
          </div>
        )}
        <div ref={end} />
      </div>

      <form className="pt-input" onSubmit={(e) => { e.preventDefault(); send(text) }}>
        <input ref={file} type="file" accept="image/*" hidden onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }} />
        <button type="button" className="pt-icon" disabled={!!inlineAsk} onClick={() => file.current?.click()} aria-label={t('사진 첨부', 'Attach a photo')} title={t('사진 첨부', 'Attach a photo')}><Paperclip size={18} /></button>
        <input className="input" value={text} onChange={(e) => setText(e.target.value)} disabled={!!sub || !!inlineAsk} placeholder={sub ? t('접수가 완료되었어요', 'Your inquiry is filed') : inlineAsk ? t('위 질문 아래 칸에 적어 주세요', 'Answer in the box under the question') : t('궁금한 내용을 적어 주세요', 'Type your question')} aria-label={t('메시지', 'Message')} />
        <button className="pt-icon send" type="submit" disabled={!text.trim() || !!inlineAsk} aria-label={t('보내기', 'Send')}><Send size={17} /></button>
      </form>
      <p className="pt-note">{t('이메일·전화번호 같은 개인정보는 자동으로 가려서 저장해요. 안전 문제는 긴급 문의로 가장 먼저 확인해요.', 'Personal data such as emails and phone numbers is masked automatically. Safety issues are reviewed first as urgent inquiries.')}</p>
    </section>
  )
}

function Rate({ lang, ticket, onDone }: { lang: Lang; ticket?: string; onDone: () => void }) {
  const t = (ko: string, en: string) => L(lang, ko, en)
  const [solved, setSolved] = useState<boolean | null>(null)
  const [stars, setStars] = useState(0)
  const [note, setNote] = useState('')
  return (
    <section className="pt-card pt-center" style={{ maxWidth: 520, margin: '0 auto' }}>
      <h2>{t('상담은 어떠셨나요?', 'How was your experience?')}</h2>
      <p className="muted">{t('문제가 해결되었나요?', 'Was your issue resolved?')}</p>
      <div className="row" style={{ justifyContent: 'center' }}>
        <button className={`pt-btn ${solved === true ? 'primary' : ''}`} onClick={() => setSolved(true)}><ThumbsUp size={15} />{t('해결됐어요', 'Yes')}</button>
        <button className={`pt-btn ${solved === false ? 'primary' : ''}`} onClick={() => setSolved(false)}><ThumbsDown size={15} />{t('아니요', 'No')}</button>
      </div>
      <div className="pt-stars" role="radiogroup" aria-label={t('별점', 'Rating')}>
        {[1, 2, 3, 4, 5].map((n) => <button key={n} className={n <= stars ? 'on' : ''} onClick={() => setStars(n)} aria-label={`${n}`} role="radio" aria-checked={stars === n}><Star size={28} /></button>)}
      </div>
      <textarea className="textarea" placeholder={t('의견이 있다면 남겨 주세요 (선택)', 'Leave a comment (optional)')} value={note} onChange={(e) => setNote(e.target.value)} />
      {solved === false && <p className="faint" style={{ fontSize: 12.5 }}>{ticket ? t(`문의 번호 ${ticket}로 담당 상담원이 계속 도와드려요.`, `A specialist will continue with reference ${ticket}.`) : t('상담원 연결을 원하시면 처음 화면에서 “상담원에게 문의”를 선택해 주세요.', 'To reach a specialist, choose “Contact a specialist” on the first screen.')}</p>}
      <button className="pt-btn primary" disabled={solved === null} onClick={onDone}>{t('보내기', 'Submit')}</button>
    </section>
  )
}
