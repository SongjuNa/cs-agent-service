import { CAT, LIBRARY, PRODUCTS, fieldLabel, fieldLabelEn } from './portalData'
import { CAT_EN, FIELD_DEFS, UNKNOWN, fieldsOf, isBlocking } from './intakeForm'
import { POLICY_KO, koSection, koTerms, koTitle } from './docKo'
import { clip, findError, findProduct, flatten } from './portalText'

/**
 * 고객용 챗봇의 대답. 고객에게는 공개 문서(데이터시트, 설치 가이드, 릴리스 노트, 정책)만 보여 주고,
 * 내부 진단표와 다른 고객의 문의는 쓰지 않는다. 고장·반품·견적·주문처럼 사람이 확인해야 하는 문의는 상담원에게 연결한다
 * (자동 처리 규칙의 “항상 사람이 확인” 유형과 같은 기준). 목업은 AI가 아니라 키워드와 규칙으로 답한다.
 */
export type Lang = 'ko' | 'en'
export interface Cite { label: string; title: string; excerpt: string }
/** 질문 바로 아래에 띄우는 입력칸. 접수 중 묻는 항목마다 하나씩 붙는다 */
export interface AnswerInput { type: 'text' | 'textarea' | 'number' | 'date' | 'email' | 'file'; label: string; ph?: string }
/** 입력칸의 값이 양식에 맞는지 확인하고, 맞지 않으면 안내 문구를 돌려준다 */
export function checkAnswer(type: AnswerInput['type'], v: string, lang: Lang): string {
  const x = v.trim()
  if (!x) return L(lang, '내용을 입력해 주세요.', 'Please enter a value.')
  if (type === 'number' && !/^\d+(\.\d+)?$/.test(x)) return L(lang, '숫자만 입력해 주세요. (예: 10)', 'Digits only, e.g. 10.')
  if (type === 'number' && !(Number(x) > 0)) return L(lang, '1 이상의 숫자를 입력해 주세요.', 'Enter a number of 1 or more.')
  if (type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(x)) return L(lang, '이메일 형식으로 입력해 주세요. (예: name@company.com)', 'Use an email format, e.g. name@company.com.')
  return ''
}

export interface BotMsg { who: 'bot' | 'me' | 'sys' | 'agent'; text: string; cites?: Cite[]; chips?: string[]; emergency?: boolean; attach?: string; input?: AnswerInput }
/** 상담원에게 문의로 접수하는 중의 상태. 실시간 상담은 없어서 챗봇이 필요한 정보를 대화로 받아 문의로 접수한다 */
export interface Intake { cat?: string; urgent: boolean; stage: 'cat' | 'fields' | 'email' | 'done'; idx: number; vals: Record<string, string>; reason: string }
export interface BotState { product?: string; topic?: 'spec' | 'docs' | 'fw' | 'fault'; error?: string; asked: number; fails: number; intake?: Intake }
export interface Submitted { urgent: boolean; rows: [string, string][]; ticket?: string }
export interface BotResult { msgs: BotMsg[]; st: BotState; submitted?: Submitted }

/** 접수 중인 항목 이름 순서가 바뀌지 않게 유형을 고르는 버튼 */
const CAT_ORDER = ['DEFECT', 'QUOTE', 'ORDER_LEAD', 'RETURN', 'WARRANTY', 'INSTALL', 'TECH_SPEC', 'MANUAL', 'FW_UPDATE', 'COMPLIANCE']
const SAFETY = /화재|불이|연기|불꽃|스파크|감전|폭발|타는 ?냄새|탄 ?냄새|아크|fire|smoke|spark|shock|explo|burning|burnt|arc ?flash/i
const HUMAN = /상담원|사람|담당자|직원|연결해|human|agent|representative|operator|specialist/i
const ACTION = /견적|가격|단가|주문|발주|구매|반품하|교환하|반품 ?(요청|신청)|교환 ?(요청|신청)|quote|quotation|price|purchase|place an order|want to return|return my|exchange my/i
const FAULT = /오류|에러|고장|트립|불량|작동 ?(이|가)? ?(안|않)|멈|꺼짐|경보|알람|error|fault|trip|fail|broken|not working|alarm|stopped/i
const SPEC = /사양|스펙|정격|용량|규격|제원|spec|rating|capacity|datasheet/i
const DOCS = /문서|가이드|매뉴얼|자료|설치|시운전|배선|document|guide|manual|install|commission|wiring/i
const FW = /펌웨어|업데이트|릴리스|firmware|update|release/i
const POLICY: [RegExp, string][] = [[/보증|워런티|warranty|rma/i, 'POL-WARRANTY'], [/반품|교환|return|exchange/i, 'POL-RETURN'], [/납기|리드타임|배송|lead ?time|shipping|delivery/i, 'POL-ORDER']]
const GREET = /^(안녕|하이|hello|hi\b|hey)/i

/** 제품을 고르는 버튼: 제품군마다 하나씩 */
export const PRODUCT_CHIPS = ['MCCB 400AF', 'ACB 2000A', 'LSLV H100 22kW VFD', 'XGB PLC CPU 16 I/O', 'XGT iXP90 (10")', 'ESS PCS 100kW']

export const L = (lang: Lang, ko: string, en: string) => (lang === 'ko' ? ko : en)

export const greeting = (lang: Lang): BotMsg => ({
  who: 'bot',
  text: L(lang, '안녕하세요, ELLO예요. 제품 사양, 문서, 정책은 바로 안내해 드리고, 고장이나 주문처럼 확인이 필요한 문의는 담당 상담원께 문의로 접수해 드려요. 무엇을 도와드릴까요?',
    "Hello, I'm ELLO. I can answer questions about specifications, documents and policies right away, and file an inquiry for a support specialist when a case needs a person, such as faults and orders. How can I help?"),
  chips: topicChips(lang),
})
export const topicChips = (lang: Lang) => [
  L(lang, '제품 사양이 궁금해요', 'I need product specifications'),
  L(lang, '설치 가이드를 보고 싶어요', 'I need an installation guide'),
  L(lang, '제품에 오류가 났어요', 'My product shows an error'),
  L(lang, '보증 정책이 궁금해요', 'What is your warranty policy?'),
  L(lang, '반품·교환 정책이 궁금해요', 'What is your return policy?'),
]

const cite = (docId: string, sec?: string): Cite | null => {
  const d = LIBRARY.find((x) => x.doc_id === docId)
  const s = d && (sec ? d.sections.find((x) => x.section === sec) : d.sections.find((x) => x.body.length > 20))
  return d && s ? { label: `${d.doc_id} §${s.section}`, title: s.title, excerpt: flatten(s.body) } : null
}
const sectionBy = (docId: string, title: string) => LIBRARY.find((x) => x.doc_id === docId)?.sections.find((x) => x.title === title)

const productDoc = (product: string, type: string) => LIBRARY.find((d) => d.product_code === product && d.doc_type === type)

const catName = (lang: Lang, c: string) => (lang === 'ko' ? CAT[c] : CAT_EN[c])
const fLabel = (lang: Lang, k: string) => (lang === 'ko' ? fieldLabel(k) : fieldLabelEn(k))

/** 접수 시작: 문의 유형을 알면 바로 필요한 정보를 묻고, 모르면 유형부터 묻는다 */
function startIntake(lang: Lang, st: BotState, reason: string, cat?: string, urgent = false): { msgs: BotMsg[]; st: BotState } {
  const intake: Intake = { cat, urgent, stage: urgent ? 'email' : cat ? 'fields' : 'cat', idx: 0, vals: {}, reason }
  const lead: BotMsg = { who: 'bot', text: urgent
    ? L(lang, '안전이 가장 중요해요. 긴급 문의로 바로 접수할게요. 담당 상담원이 가장 먼저 확인해요.', 'Safety comes first. I will file this as an urgent inquiry that a specialist reviews first.')
    : L(lang, '이 문의는 담당 상담원이 직접 답변드려야 해요. 문의로 접수해 드릴게요. 지금까지의 대화는 함께 전달되고, 필요한 정보만 몇 가지 여쭤볼게요.', 'This needs a specialist to reply personally. I will file it as an inquiry and pass on our conversation, but first I need a few details.') }
  const next = nextQuestion(lang, { ...st, intake })
  return { msgs: [lead, ...next.msgs], st: next.st }
}

/** 다음에 물어볼 것: 유형 → 필요한 정보(막는 정보 먼저) → 이메일 → 접수 완료 */
function nextQuestion(lang: Lang, st: BotState): { msgs: BotMsg[]; st: BotState; submitted?: Submitted } {
  const it = st.intake!
  if (it.stage === 'cat') {
    return { msgs: [{ who: 'bot', text: L(lang, '어떤 문의인가요? 가장 가까운 것을 골라 주세요.', 'What is your inquiry about? Please pick the closest one.'), chips: CAT_ORDER.map((c) => catName(lang, c)) }], st }
  }
  if (it.stage === 'fields' && it.cat) {
    const keys = fieldsOf(it.cat)
    // 이미 대화에서 알게 된 값은 건너뛴다
    const vals = { ...it.vals }
    if (st.product && !vals.product_model) vals.product_model = PRODUCTS[st.product]?.product_name ?? st.product
    if (st.error && !vals.error_code) vals.error_code = st.error
    let i = it.idx
    while (i < keys.length && vals[keys[i]]) i++
    if (i < keys.length) {
      const k = keys[i], d = FIELD_DEFS[k], blk = isBlocking(it.cat, k)
      const help = d?.help?.[lang === 'ko' ? 0 : 1] ?? ''
      const chips = d?.type === 'select' ? (k === 'product_model' ? PRODUCT_CHIPS : d.options?.map(([, ko, en]) => (lang === 'ko' ? ko : en))) : undefined
      const ask = d?.type === 'file'
        ? L(lang, `‘${fLabel(lang, k)}’ 파일을 보내 주세요. 아래 클립 버튼으로 올릴 수 있어요. ${help}`, `Please send the “${fLabel(lang, k)}” using the paperclip below. ${help}`)
        : L(lang, `‘${fLabel(lang, k)}’ 정보를 알려 주세요. ${help}`, `Please tell me the “${fLabel(lang, k)}”. ${help}`)
      const type = d?.type === 'select' ? (k === 'product_model' ? 'text' : undefined) : (d?.type as AnswerInput['type'] | undefined)
      const input: AnswerInput | undefined = type ? { type, label: fLabel(lang, k), ph: d?.ph?.[lang === 'ko' ? 0 : 1] } : undefined
      return { msgs: [{ who: 'bot', text: ask, input, chips: [...(chips ?? []), ...(blk ? [] : [L(lang, '모르겠어요', "I don't know")])] }], st: { ...st, intake: { ...it, vals, idx: i } } }
    }
    return nextQuestion(lang, { ...st, intake: { ...it, vals, idx: i, stage: 'email' } })
  }
  if (it.stage === 'email') {
    return { msgs: [{ who: 'bot', text: L(lang, '마지막이에요. 답변을 받으실 이메일 주소를 알려 주세요.', 'Last step. Please tell me the email address for the reply.'), input: { type: 'email', label: L(lang, '이메일', 'Email'), ph: 'name@company.com' } }], st }
  }
  return { msgs: [], st }
}

/** 접수 완료: 문의 번호와 접수한 내용을 정리해서 알려 준다 */
function finish(lang: Lang, st: BotState): BotResult {
  const it = st.intake!
  const keys = it.cat ? fieldsOf(it.cat) : []
  const rows: [string, string][] = [
    [L(lang, '문의 유형', 'Type'), it.cat ? catName(lang, it.cat) : '-'],
    ...keys.filter((k) => it.vals[k]).map((k) => [fLabel(lang, k), it.vals[k] === UNKNOWN ? L(lang, '모르겠어요', "I don't know") : it.vals[k]] as [string, string]),
    [L(lang, '우선순위', 'Priority'), it.urgent ? L(lang, '긴급(P1)', 'Urgent (P1)') : L(lang, '일반', 'Normal')],
  ]
  return {
    msgs: [{ who: 'bot', text: L(lang, '문의로 접수했어요. 담당 상담원이 확인하고 이메일로 답변드릴게요.', 'Your inquiry has been filed. A specialist will review it and reply by email.') }],
    st: { ...st, intake: { ...it, stage: 'done' } },
    submitted: { urgent: it.urgent, rows },
  }
}

/** 접수 중인 대화에서 고객의 답을 받아 저장하고 다음 질문으로 넘어간다 */
function answerIntake(text: string, lang: Lang, st: BotState): BotResult {
  const it = st.intake!
  const unknownWord = /^(모르겠|모르|잘 ?모|i ?don.?t know|not sure|unknown)/i.test(text)
  if (it.stage === 'cat') {
    const c = CAT_ORDER.find((x) => text.includes(CAT[x]) || text.toLowerCase().includes(CAT_EN[x].toLowerCase()))
    if (!c) return { msgs: [{ who: 'bot', text: L(lang, '아래에서 골라 주시겠어요?', 'Could you pick one below?'), chips: CAT_ORDER.map((x) => catName(lang, x)) }], st }
    const n = nextQuestion(lang, { ...st, intake: { ...it, cat: c, stage: 'fields' } })
    return { msgs: n.msgs, st: n.st }
  }
  if (it.stage === 'fields' && it.cat) {
    const keys = fieldsOf(it.cat), k = keys[it.idx], d = FIELD_DEFS[k]
    if (unknownWord) {
      if (isBlocking(it.cat, k)) {
        return { msgs: [{ who: 'bot', text: L(lang, `이 항목은 꼭 필요해서 건너뛸 수 없어요. ${d?.help?.[0] ?? ''} 확인해서 알려 주시겠어요?`, `This item is essential and cannot be skipped. ${d?.help?.[1] ?? ''} Could you check and tell me?`) }], st }
      }
      return nextQuestion(lang, { ...st, intake: { ...it, vals: { ...it.vals, [k]: UNKNOWN }, idx: it.idx + 1 } })
    }
    if (d?.type === 'number' && !(Number(text.replace(/[^\d.]/g, '')) > 0)) return { msgs: [{ who: 'bot', text: L(lang, '숫자로 알려 주시겠어요? (예: 10)', 'Could you give a number? (e.g. 10)') }], st }
    if (k === 'product_model') { const p = findProduct(text); if (p) st = { ...st, product: p } }
    const val = d?.type === 'number' ? text.replace(/[^\d.]/g, '') : text
    return nextQuestion(lang, { ...st, intake: { ...it, vals: { ...it.vals, [k]: val }, idx: it.idx + 1 } })
  }
  if (it.stage === 'email') {
    if (!/.+@.+\..+/.test(text)) return { msgs: [{ who: 'bot', text: L(lang, '이메일 주소 형식을 확인해 주시겠어요? (예: name@company.com)', 'Could you check the email format? (e.g. name@company.com)') }], st }
    return finish(lang, st)
  }
  return { msgs: [{ who: 'bot', text: L(lang, '이미 접수된 문의예요. 새 문의는 “새로 문의하기”를 눌러 주세요.', 'This inquiry is already filed. Use “New inquiry” to start another.') }], st }
}

/** 고객의 한 마디에 대한 챗봇의 대답 */
export function botReply(textIn: string, lang: Lang, prev: BotState): BotResult {
  const text = textIn.trim()
  const st: BotState = { ...prev }
  const product = findProduct(text)
  const code = findError(text) ?? text.match(/\b[A-Z]{1,2}\.[A-Z0-9]{1,4}\b/)?.[0]
  if (product) st.product = product
  if (code) st.error = code
  const pName = st.product ? PRODUCTS[st.product]?.product_name : ''
  if (st.intake && st.intake.stage !== 'done') return answerIntake(text, lang, st)
  if (st.intake?.stage === 'done') return answerIntake(text, lang, st)
  const reply = (msgs: BotMsg[], over?: Partial<BotState>): BotResult => ({ msgs, st: { ...st, ...over } })
  const ask = (q: string, topic: BotState['topic']): BotResult => reply([{ who: 'bot', text: q, chips: PRODUCT_CHIPS }], { topic })

  // 1) 안전 문제는 무엇보다 먼저: 긴급 안내를 보이고 이메일만 받아 긴급(P1)으로 바로 접수
  if (SAFETY.test(text)) {
    const r = startIntake(lang, st, L(lang, '안전 문제 신고', 'Safety issue'), 'DEFECT', true)
    return { msgs: [{ who: 'bot', emergency: true, text: L(lang,
      '연기, 화재, 감전, 불꽃이 있다면 즉시 전원을 차단하고 장비에서 떨어져 주세요. 위험이 계속되면 119 또는 현지 긴급 번호로 먼저 연락하세요.\n24시간 안전 상담 전화: +82-00-0000-0000 (샘플 번호)',
      'If there is smoke, fire, electric shock or sparks, switch off the power immediately and move away from the equipment. If the danger continues, call your local emergency number first.\n24/7 safety hotline: +82-00-0000-0000 (sample number)') }, ...r.msgs], st: r.st }
  }
  // 2) 상담원에게 문의하고 싶다는 말: 대화에서 알게 된 유형이 있으면 그대로, 없으면 유형부터 묻는다
  if (HUMAN.test(text)) {
    const r = startIntake(lang, st, L(lang, '상담원 문의 요청', 'Request for a specialist'), st.topic === 'fault' ? 'DEFECT' : undefined)
    return { msgs: r.msgs, st: r.st }
  }
  // 3) 견적·주문·반품 요청은 항상 사람이 처리: 유형별 필요한 정보를 받아 문의로 접수
  if (ACTION.test(text)) {
    const cat = /견적|가격|단가|quot|price/i.test(text) ? 'QUOTE' : /반품|교환|return|exchange/i.test(text) ? 'RETURN' : 'ORDER_LEAD'
    const r = startIntake(lang, st, L(lang, '견적·주문·반품 요청', 'Quote, order or return request'), cat)
    return { msgs: [{ who: 'bot', text: L(lang, '견적, 주문, 반품·교환 요청은 담당 상담원이 처리해요.', 'Quotes, orders and returns are handled by a specialist.') }, ...r.msgs], st: r.st }
  }
  // 4) 고장·오류: 상담원이 확인해야 하니 필요한 정보(에러 코드, 시리얼 번호 등)를 받아 문의로 접수
  if (FAULT.test(text) || (st.topic === 'fault' && (product || code))) {
    st.topic = 'fault'
    const r = startIntake(lang, st, L(lang, '제품 오류·고장', 'Product fault'), 'DEFECT')
    return { msgs: [{ who: 'bot', text: L(lang, '불편을 드려 죄송해요. 점검하시기 전에 반드시 전원을 차단해 주세요.', 'Sorry for the trouble. Please switch off the power before inspecting the equipment.') }, ...r.msgs], st: r.st }
  }
  // 5) 정책 안내
  for (const [re, id] of POLICY) if (re.test(text) && !(st.topic && product && SPEC.test(text))) {
    const d = LIBRARY.find((x) => x.doc_id === id)
    if (!d) continue
    const secs = d.sections.filter((x) => x.body.length > 30).slice(0, 2)
    const cites = secs.map((s) => cite(id, s.section)).filter(Boolean) as Cite[]
    const body = secs.map((s) => (lang === 'ko' ? `• ${koSection(s.title)}: ${POLICY_KO[id]?.[s.title] ?? koTerms(clip(s.body, 160))}` : `• ${s.title}: ${clip(s.body, 200)}`)).join('\n')
    const warr = id === 'POL-WARRANTY' && st.product ? L(lang, `\n${pName}의 보증 기간은 ${PRODUCTS[st.product]?.warranty_months}개월이에요.`, `\nThe warranty period for the ${pName} is ${PRODUCTS[st.product]?.warranty_months} months.`) : ''
    return reply([{ who: 'bot', text: L(lang, `${koTitle(d.title)} 안내예요.\n${body}${warr}`, `Here is our ${d.title}.\n${body}${warr}`), cites, chips: [L(lang, '상담원에게 문의', 'Contact a specialist'), ...(id === 'POL-WARRANTY' ? [L(lang, '반품·교환 정책이 궁금해요', 'What is your return policy?')] : [L(lang, '보증 정책이 궁금해요', 'What is your warranty policy?')])] }])
  }
  // 6) 사양·문서·펌웨어: 제품이 필요하다
  const wantSpec = SPEC.test(text), wantFw = FW.test(text), wantDocs = DOCS.test(text)
  const topic: BotState['topic'] | undefined = wantSpec ? 'spec' : wantFw ? 'fw' : wantDocs ? 'docs' : product ? st.topic : undefined
  if (topic) {
    st.topic = topic
    if (!st.product) return ask(L(lang, '어떤 제품인지 알려 주세요. 제품 이름이나 모델명을 적거나 아래에서 골라 주세요.', 'Which product is it? Type the product name or model, or pick one below.'), topic)
    const next = [L(lang, '설치 가이드를 보고 싶어요', 'I need an installation guide'), L(lang, `${pName} 펌웨어는 무엇인가요?`, `What is the latest firmware for the ${pName}?`), L(lang, '상담원에게 문의', 'Contact a specialist')]
    if (topic === 'spec') {
      const ds = productDoc(st.product, 'DS')
      const sec = ds && (sectionBy(ds.doc_id, 'Ratings') ?? sectionBy(ds.doc_id, 'Technical specifications'))
      if (ds && sec) return reply([{ who: 'bot', text: L(lang, `${pName}의 주요 사양이에요.\n${koTerms(clip(sec.body, 220))}\n전체 사양은 데이터시트에서 확인하실 수 있어요.`, `Key specifications of the ${pName}:\n${clip(sec.body, 220)}\nSee the datasheet for the full list.`), cites: [cite(ds.doc_id, sec.section)!].filter(Boolean), chips: next }])
    }
    if (topic === 'fw') {
      const rn = productDoc(st.product, 'RN')
      const m = rn && sectionBy(rn.doc_id, 'Summary')?.body.match(/Latest firmware: \**([\w.]+)/)
      if (rn && m) return reply([{ who: 'bot', text: L(lang, `${pName}의 최신 펌웨어는 ${m[1]}이에요. 업데이트 전에는 릴리스 노트의 절차와 호환성을 꼭 확인해 주세요.`, `The latest firmware for the ${pName} is ${m[1]}. Please check the update procedure and compatibility in the release notes first.`), cites: [cite(rn.doc_id)!].filter(Boolean), chips: next }])
      return reply([{ who: 'bot', text: L(lang, `${pName}은 별도의 펌웨어가 없는 제품이에요.`, `The ${pName} has no separate firmware.`), chips: next }])
    }
    const docs = LIBRARY.filter((d) => d.product_code === st.product && ['DS', 'IG', 'RN', 'MG'].includes(d.doc_type))
    const ig = docs.find((d) => d.doc_type === 'IG')
    const list = docs.map((d) => `• ${lang === 'ko' ? koTitle(d.title) : d.title} (${d.doc_id})`).join('\n')
    const ex = ig && (sectionBy(ig.doc_id, 'Commissioning procedure') ?? ig.sections[0])
    return reply([{ who: 'bot', text: L(lang, `${pName}의 문서예요.\n${list}\n설치·시운전은 가이드의 절차를 따라 주세요. 막히는 부분이 있으면 말씀해 주세요.`, `Documents for the ${pName}:\n${list}\nFollow the installation guide for commissioning. Tell me if you get stuck.`), cites: ex && ig ? [cite(ig.doc_id, ex.section)!].filter(Boolean) : [], chips: next }])
  }
  // 7) 인사와 이해하지 못한 말
  if (GREET.test(text) && text.length < 20) return reply([greeting(lang)])
  const fails = st.fails + 1
  const offer = fails >= 2
  return reply([{ who: 'bot', text: offer
    ? L(lang, '제가 정확히 도와드리기 어려운 내용이에요. 상담원에게 문의로 접수해 드릴까요?', 'I am not able to help with this precisely. Shall I file an inquiry for a specialist?')
    : L(lang, '조금 더 자세히 알려 주시겠어요? 제품 이름이나 궁금한 내용(사양, 문서, 정책, 오류)을 함께 적어 주세요.', 'Could you tell me a bit more? Please include the product name and what you need (specifications, documents, policy, or an error).'),
    chips: offer ? [L(lang, '상담원에게 문의', 'Contact a specialist')] : topicChips(lang).slice(0, 3) }], { fails })
}
