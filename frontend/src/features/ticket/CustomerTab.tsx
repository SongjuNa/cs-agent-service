// 탭 ① 고객이 보낸 것 (SCR-03 L-01~L-04, FR-030 처리 1). 배치는 목업 v1.42 탭 "고객이 보낸 것"(위 3열 항목, 아래 원문).
// 목업의 한국어 번역 칸은 넣지 않는다(FR-030 "번역 토글은 여유 시", 화면 명세 Q1).
import { useState, type ReactNode } from "react";
import type { Detail, Field } from "../../api";
import { CHANNEL, label } from "../../app/labels";
import { Button, Chip } from "../../ui";

const FOLD = 600; // 이보다 긴 원문은 접는다(FR-030 예외 5행). 길이는 구현 선택
const LANG: Record<string, string> = {
  ar: "아랍어", de: "독일어", en: "영어", es: "스페인어", fr: "프랑스어", id: "인도네시아어", it: "이탈리아어", ja: "일본어",
  pl: "폴란드어", pt: "포르투갈어", ru: "러시아어", th: "태국어", tr: "튀르키예어", vi: "베트남어", zh: "중국어", ko: "한국어",
};
export const langName = (code: string | null | undefined) => (code ? `${LANG[code] ?? code} ${code}` : "—");
export const utc = (at: string | null | undefined) => (at ? `${at.replace("T", " ").slice(0, 16)} UTC` : "—");

/** 원문에서 뽑은 값 위치. span이 있으면 그것, 없으면 값 글자를 찾는다(C-109) */
function marks(body: string, fields: Field[]): { start: number; end: number; label: string }[] {
  const out: { start: number; end: number; label: string }[] = [];
  for (const f of fields) {
    let start = f.span_start ?? -1;
    let end = f.span_end ?? -1;
    if (start < 0 || end <= start) {
      const value = (f.value_raw ?? "").trim();
      if (value.length < 2) continue;
      start = body.toLowerCase().indexOf(value.toLowerCase());
      end = start + value.length;
    }
    if (start >= 0 && !out.some((m) => start < m.end && end > m.start)) out.push({ start, end, label: f.label });
  }
  return out.sort((a, b) => a.start - b.start);
}

export function Highlighted({ body, fields }: { body: string; fields: Field[] }) {
  const parts: ReactNode[] = [];
  let at = 0;
  for (const m of marks(body, fields)) {
    parts.push(body.slice(at, m.start));
    parts.push(<mark key={m.start} title={m.label}>{body.slice(m.start, m.end)}</mark>);
    at = m.end;
  }
  parts.push(body.slice(at));
  return <>{parts}</>;
}

export function CustomerTab({ detail }: { detail: Detail }) {
  const t = detail.ticket;
  const [open, setOpen] = useState(t.inquiry_body.length <= FOLD);
  const fields = detail.sub_tickets.flatMap((s) => s.fields.filter((f) => f.source === "INQUIRY"));
  const body = open ? t.inquiry_body : `${t.inquiry_body.slice(0, FOLD)}…`;
  const replies = detail.messages.filter((m) => m.message_type === "CUSTOMER_REPLY" || m.message_type === "ESCALATION_NOTE");
  const products = detail.sub_tickets.map((s) => s.sub_ticket.product_code);
  const bodyLang = t.body_language && t.body_language !== t.language ? `, 본문 ${langName(t.body_language)}` : "";
  const contact = [t.contact_name, t.contact_email, t.contact_phone].filter(Boolean).join(", ");
  const rtl = (t.body_language ?? t.language) === "ar";

  return (
    <div className="tk-pane">
      <dl className="tk-kv">
        <div><dt>접수</dt><dd>{utc(t.received_at_utc)}</dd></div>
        <div><dt>채널</dt><dd>{label(CHANNEL, t.channel)}</dd></div>
        <div><dt>고객사</dt><dd>{t.company_masked} <Chip tone="outline">{t.customer_tier}</Chip></dd></div>
        <div><dt>고객</dt><dd>{t.customer_id}, {t.country}</dd></div>
        <div><dt>제품</dt><dd>{products.some(Boolean) ? [...new Set(products.filter(Boolean))].join(", ") : <Chip tone="crit">미확인</Chip>}</dd></div>
        <div><dt>언어</dt><dd>{langName(t.language)}{bodyLang}{t.body_language_uncertain && <> <Chip tone="crit">본문 언어 판정 불확실</Chip></>}</dd></div>
        {contact && <div><dt>보낸 사람</dt><dd>{contact}</dd></div>}
      </dl>

      {t.channel === "PHONE" && <p className="tk-note">영어 메모, 답장은 {langName(t.language)}로 씁니다</p>}
      <div>
        <div className="tk-text-head"><span>원문 ({langName(t.body_language ?? t.language)})</span>{fields.length > 0 && <span>노란 표시: 뽑은 값</span>}</div>
        <pre className="tk-text" dir={rtl ? "rtl" : undefined} data-testid="inquiry-body"><Highlighted body={body} fields={open ? fields : []} /></pre>
        {t.inquiry_body.length > FOLD && <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>{open ? "접기" : "펼치기"}</Button>}
      </div>

      {replies.length > 0 && (
        <div className="tk-replies">
          <div className="tk-text-head"><span>회신 (시각순)</span></div>
          {replies.map((m) => (
            <div key={m.message_id}>
              <div className="tk-text-head">
                <span>{m.message_type === "CUSTOMER_REPLY" ? "고객 회신" : `부서 회신 ${m.sent_by_name}`}{m.seq ? `, 문의 ${m.seq}` : ""}</span>
                <span>{utc(m.sent_at_utc)}, {m.language}</span>
              </div>
              <pre className="tk-text">{m.body}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
