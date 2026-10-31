// SCR-10 상담원 도우미 (화면 명세 SCR-10, 변경 add-agent-assistant). 모든 화면의 오른쪽 아래에 떠 있는 창.
// 문서 절 안에서만 답하고 출처를 붙인다. 답은 상담원 참고용이라 초안·고객 발송에 쓰이지 않는다(CLAUDE.md 규칙 3).
// 대화는 이 컴포넌트 상태에만 둔다(서버에 저장하지 않는다, 규칙 4). 이어 묻기는 직전 대화를 같이 보낸다.
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type AssistAnswer } from "../../api";
import { Banner, Button } from "../../ui";
import { SourcePopup, type SourceTarget } from "../ticket/Popups";
import "./assistant.css";

const MAX_QUESTION = 500; // 서버와 같은 값(SCR-10 입력 검증)
const MAX_HISTORY = 6;

type Msg =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; found: boolean; sources: AssistAnswer["sources"]; followups: string[]; notes: string[] }
  | { role: "error"; text: string; question: string };

export function AssistantDock() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [inputError, setInputError] = useState<string | null>(null);
  const [source, setSource] = useState<SourceTarget | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: ({ question, history }: { question: string; history: { role: "user" | "assistant"; text: string }[] }) =>
      api.assist(question, history, null),
  });

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
    ask.mutate({ question, history }, {
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
    return <button type="button" className="as-fab" onClick={() => setOpen(true)} aria-label="상담원 도우미 열기" data-testid="assist-open">도우미</button>;
  }

  return (
    <section className="as-panel" role="dialog" aria-label="상담원 도우미" data-testid="assist-panel">
      <header className="as-head">
        <b>상담원 도우미</b>
        <span className="as-spacer" />
        <Button size="sm" variant="ghost" onClick={() => setMsgs([])} disabled={!msgs.length || ask.isPending}>새 대화</Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)} aria-label="도우미 닫기">닫기</Button>
      </header>
      <Banner tone="info">문서 근거로 답하며 상담원 참고용입니다. 고객에게 보내는 글의 근거로 쓰지 않습니다.</Banner>

      <div className="as-log" role="log" aria-live="polite">
        {!msgs.length && <p className="as-hint">오류 코드나 제품 이름을 넣어 물어보세요. 문서에 없는 내용은 찾지 못했다고 답합니다.</p>}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="as-msg as-msg--me">{m.text}</div>
        ) : m.role === "error" ? (
          <div key={i} className="as-msg as-msg--bot as-msg--err" role="alert">
            {m.text} <Button size="sm" onClick={() => send(m.question)} disabled={ask.isPending}>다시 시도</Button>
          </div>
        ) : (
          <div key={i} className="as-msg as-msg--bot" data-testid="assist-answer">
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
