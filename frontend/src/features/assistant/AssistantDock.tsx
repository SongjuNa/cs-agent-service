// SCR-10 상담원 도우미 (화면 명세 SCR-10, 변경 add-agent-assistant). 모든 화면의 오른쪽 아래에 떠 있는 창.
// 문서 절 안에서만 답하고 출처를 붙인다. 답은 상담원 참고용이라 초안·고객 발송에 쓰이지 않는다(CLAUDE.md 규칙 3).
// 대화는 이 컴포넌트 상태에만 둔다(서버에 저장하지 않는다, 규칙 4). 이어 묻기는 직전 대화를 같이 보낸다.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react";
import { api, ApiError, type AssistAnswer } from "../../api";
import { useSession } from "../../app/session";
import { Banner, Button } from "../../ui";
import { repOf } from "../ticket/HeadCard";
import { ticketKey } from "../ticket/ticketQuery";
import ello from "../../assets/ello.png";
import { SourcePopup, type SourceTarget } from "../ticket/Popups";
import "./assistant.css";

const MAX_QUESTION = 500; // 서버와 같은 값(SCR-10 입력 검증)
const MAX_HISTORY = 6;

type Msg =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; found: boolean; sources: AssistAnswer["sources"]; followups: string[]; notes: string[] }
  | { role: "error"; text: string; question: string };

// 목업 ELLO처럼 단추와 창이 같은 자리를 쓰고, 끌어서 옮기며(두 번 누르면 제자리), 위치는 이 브라우저에만 기억한다
interface Pos { r: number; b: number }
const POS_KEY = "cs.ello.pos";
const HOME: Pos = { r: 24, b: 96 }; // 오른쪽 아래 승인·발송 줄을 가리지 않게 그 위
const readPos = (): Pos => {
  try { const v = JSON.parse(localStorage.getItem(POS_KEY) ?? ""); if (typeof v?.r === "number" && typeof v?.b === "number") return v; } catch { /* 저장된 위치 없음 */ }
  return HOME;
};
const keepInside = (p: Pos, el: HTMLElement | null): Pos => {
  const w = el?.offsetWidth ?? 52, h = el?.offsetHeight ?? 52;
  return { r: Math.min(Math.max(8, p.r), Math.max(8, window.innerWidth - w - 8)), b: Math.min(Math.max(8, p.b), Math.max(8, window.innerHeight - h - 8)) };
};

const FIRST_CHIPS = ["E.OC 오류 원인과 조치", "MCCB 400AF 사양", "보증 기간과 RMA 절차", "반품 정책"];
const CAT_CHIP: Record<string, string> = { RETURN: "반품 정책", WARRANTY: "보증 기간과 RMA 절차", QUOTE: "납기와 주문 정책", ORDER_LEAD: "납기와 주문 정책" };

/** 지금 보고 있는 문의(/tickets/{번호})가 있으면 그 문의의 제품·에러 코드·유형을 돌려준다(목업 suggestions의 ctx) */
function useTicketContext() {
  const { asOf } = useSession();
  const id = decodeURIComponent(window.location.pathname.match(/^\/tickets\/([^/]+)$/)?.[1] ?? "");
  const q = useQuery({ queryKey: ticketKey(id, asOf), queryFn: () => api.ticket(id, asOf), enabled: !!id });
  const rep = q.data ? repOf(q.data) : undefined;
  if (!id || !rep) return null;
  const code = rep.fields.find((f) => f.field === "error_code");
  return { id, product: rep.sub_ticket.product_code, error: code?.value_norm ?? code?.value_raw ?? null, category: rep.sub_ticket.category_code };
}

/** 시작 화면의 질문 후보. 문의 화면에서는 그 문의에 맞춘다(목업 ELLO와 같은 구성) */
function chipsFor(ctx: ReturnType<typeof useTicketContext>): string[] {
  if (!ctx) return FIRST_CHIPS;
  const out: string[] = [];
  if (ctx.error) out.push(`${ctx.error} 오류 원인과 조치`);
  out.push(`${ctx.product ?? "이 제품"} 관련 문서`);
  if (ctx.category && CAT_CHIP[ctx.category]) out.push(CAT_CHIP[ctx.category]);
  return out.slice(0, 4);
}

export function AssistantDock() {
  const ctx = useTicketContext();
  const [pos, setPos] = useState<Pos>(readPos);
  const box = useRef<HTMLElement>(null);
  const drag = useRef<{ x: number; y: number; p: Pos; moved: boolean } | null>(null);
  const dragged = useRef(false);
  const save = (p: Pos) => { try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch { /* 저장 불가 환경 */ } };
  const down = (e: PointerEvent<HTMLElement>) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest("button:not(.as-fab)")) return;
    drag.current = { x: e.clientX, y: e.clientY, p: pos, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < 4) return;
    d.moved = true;
    setPos(keepInside({ r: d.p.r - dx, b: d.p.b - dy }, box.current));
  };
  const up = () => {
    const d = drag.current;
    drag.current = null;
    if (d?.moved) { dragged.current = true; setTimeout(() => { dragged.current = false; }, 0); setPos((p) => { save(p); return p; }); }
  };
  const reset = () => { setPos(HOME); save(HOME); };
  const drags = { onPointerDown: down, onPointerMove: move, onPointerUp: up, onPointerCancel: up, onDoubleClick: reset };

  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [inputError, setInputError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceTarget | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: ({ question, history, product }: { question: string; history: { role: "user" | "assistant"; text: string }[]; product: string | null }) =>
      api.assist(question, history, product),
  });

  useLayoutEffect(() => { setPos((p) => keepInside(p, box.current)); }, [open]);
  useEffect(() => {
    const h = () => setPos((p) => keepInside(p, box.current));
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, []);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs, ask.isPending, open]);

  const send = (raw: string) => {
    const question = raw.trim();
    if (!question || ask.isPending) return;
    if (question.length > MAX_QUESTION) { setInputError(`질문은 ${MAX_QUESTION}자 이하로 입력하세요`); return; }
    setInputError(null);
    // 이어 묻기: 직전 대화(오류 줄 제외) 최대 6줄을 같이 보낸다
    const history = msgs
      .filter((m): m is Extract<Msg, { role: "user" | "assistant" }> => m.role !== "error")
      .slice(-MAX_HISTORY)
      .map((m) => ({ role: m.role, text: m.role === "assistant" && !m.found ? "" : m.text }))
      .filter((m) => m.text);
    setMsgs((cur) => [...cur.filter((m) => m.role !== "error"), { role: "user", text: question }]);
    setText("");
    ask.mutate({ question, history, product: ctx?.product ?? null }, {
      onSuccess: (a) => setMsgs((cur) => [...cur, { role: "assistant", text: a.answer, found: a.found, sources: a.sources, followups: a.followups, notes: a.notes }]),
      onError: (e) => {
        // 400은 입력 칸 아래에 서버 문구 그대로, 그 밖은 말풍선에 다시 시도 단추(frontend/CLAUDE.md 규칙 3)
        if (e instanceof ApiError && e.status === 400) {
          setMsgs((cur) => cur.slice(0, -1));
          setText(question);
          setInputError(e.message);
        } else {
          setMsgs((cur) => [...cur, { role: "error", text: "답을 가져오지 못했습니다.", question }]);
        }
      },
    });
  };

  if (!open) {
    return (
      <button ref={box as React.RefObject<HTMLButtonElement>} type="button" className="as-fab" style={{ right: pos.r, bottom: pos.b }} {...drags}
        onClick={() => { if (!dragged.current) setOpen(true); }} aria-label="ELLO 상담원 도우미 열기" title="ELLO · 상담원 도우미 (끌어서 옮길 수 있어요)" data-testid="assist-open">
        <img src={ello} alt="" draggable={false} />
      </button>
    );
  }

  return (
    <section ref={box as React.RefObject<HTMLElement>} className="as-panel" style={{ right: pos.r, bottom: pos.b }} role="dialog" aria-label="ELLO 상담원 도우미" data-testid="assist-panel">
      <header className="as-head" {...drags} title="끌어서 옮길 수 있어요 · 두 번 누르면 원래 자리로">
        <span className="as-av"><img src={ello} alt="" /></span>
        <b>ELLO <span className="as-sub">상담원 도우미</span></b>
        <span className="as-spacer" />
        <Button size="sm" variant="ghost" onClick={() => setMsgs([])} disabled={!msgs.length || ask.isPending}>새 대화</Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)} aria-label="도우미 닫기">닫기</Button>
      </header>
      <Banner tone="info">문서 근거로 답하며 상담원 참고용입니다. 고객에게 보내는 글의 근거로 쓰지 않습니다.</Banner>

      <div className="as-log" role="log" aria-live="polite">
        {!msgs.length && (
          <div className="as-hello">
            <img className="as-big" src={ello} alt="LS 캐릭터" />
            <b>안녕하세요, ELLO예요. 무엇을 찾으세요?</b>
            <p className="as-hint">오류 코드나 제품 이름을 넣어 물어보세요. 문서에 없는 내용은 찾지 못했다고 답합니다.{ctx && <> 지금은 <b>{ctx.id}</b>를 보고 있어 이 문의의 제품 기준으로 찾습니다.</>}</p>
            <div className="as-chips" aria-label="추천 문구" data-testid="assist-chips">
              {chipsFor(ctx).map((c) => <button key={c} type="button" className="as-chip" onClick={() => send(c)} disabled={ask.isPending}>{c}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="as-msg as-msg--me">{m.text}</div>
        ) : m.role === "error" ? (
          <div key={i} className="as-msg as-msg--bot as-msg--err" role="alert">
            {m.text} <Button size="sm" onClick={() => send(m.question)} disabled={ask.isPending}>다시 시도</Button>
          </div>
        ) : (
          <div key={i} className="as-bot" data-testid="assist-answer"><span className="as-av as-av--sm"><img src={ello} alt="" /></span>
          <div className="as-msg as-msg--bot">
            {m.text ? <p className="as-text">{m.text}</p> : null}
            {m.notes.map((n) => <p key={n} className="as-note">{n}</p>)}
            {m.sources.length > 0 && (
              <div className="as-sources" aria-label="출처">
                {m.sources.map((s) => (
                  <button key={s.chunk_id} type="button" className="as-source" data-testid="assist-source"
                    onClick={() => setSource({ kind: "cite", chunk_id: s.chunk_id, text: `${s.doc_id} §${s.section_no}` })}
                    title={s.title}>{s.doc_id} §{s.section_no}</button>
                ))}
              </div>
            )}
            {m.followups.length > 0 && (
              <div className="as-follow" aria-label="이어서 물어보기">
                {m.followups.map((f) => <button key={f} type="button" className="as-chip" onClick={() => send(f)} disabled={ask.isPending}>{f}</button>)}
              </div>
            )}
          </div>
          </div>
        ))}
        {ask.isPending && <div className="as-msg as-msg--bot as-muted" data-testid="assist-pending">찾는 중…</div>}
        <div ref={end} />
      </div>

      <form className="as-form" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <textarea
          value={text} maxLength={MAX_QUESTION} rows={2} aria-label="질문" placeholder="질문을 입력하세요 (Enter로 보내기, Shift+Enter 줄바꿈)"
          onChange={(e) => { setText(e.target.value); if (inputError) setInputError(null); }}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(text); } }}
        />
        <Button type="submit" variant="primary" busy={ask.isPending} disabled={!text.trim()}>보내기</Button>
      </form>
      {inputError && <p className="as-input-error" role="alert">{inputError}</p>}

      {source && <SourcePopup target={source} onClose={() => setSource(null)} />}
    </section>
  );
}
