// 탭 "보낼 것"의 초안 카드 = R 영역 (FR-031, FR-039, FR-049, 화면 정의서 v2 SCR-03M ④ R).
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Draft, type Lookup, type Mark, type SendIssue } from "./api";
import { renderBody } from "./body";
import { markClass, markSymbol, SendPopup, type SendState, type SourceTarget } from "./Popups";

const TYPE_NAMES = { INFO_REQUEST: "정보 요청", FINAL_REPLY: "답변" } as const;
// 걸린 번호를 누르면 옮겨 갈 근거 줄 (화면 정의서 v2 0-7절)
const MARK_TARGET: Record<number, string> = { 1: "C-10", 2: "C-07", 3: "C-10", 4: "C-02" };

function time(utc: string): string {
  return new Date(utc).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export function DraftCard({ agent, draft, lookups, candidates, ticketLanguage, onSource, onJump, onFail, reload }: {
  agent: string;
  draft: Draft;
  lookups: Lookup[];
  candidates: { doc_id: string; section: string; chunk_id: string; score: number }[];
  ticketLanguage: string;
  onSource: (t: SourceTarget) => void;
  onJump: (rowId: string) => void;
  onFail: (message: string) => void;
  reload: () => Promise<Draft | undefined>;
}) {
  const [body, setBody] = useState(draft.body);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "gloss" | "verify">("");
  const [glossOld, setGlossOld] = useState(false);
  const [send, setSend] = useState<SendState | null>(null);
  const findingRef = useRef<HTMLElement | null>(null);
  useEffect(() => setBody(draft.body), [draft.message_id, draft.body]);
  const dirty = body !== draft.body;
  const marks = draft.review_marks.marks;
  const verify = marks.find((m) => m.no === 5)!;
  const findings = verify.state === "FOUND" ? verify.findings ?? [] : [];
  const bad = draft.check && !draft.check.passed_yn
    ? [...draft.check.detail.bad_citations, ...draft.check.detail.bad_numbers] : [];

  if (draft.sent) {
    // M-R-02 발송 뒤 카드(읽기 전용)
    return (
      <article className="card sent">
        <header>
          <b>{TYPE_NAMES[draft.message_type]}</b> 발송됨 {time(draft.sent.sent_at_utc)} · {draft.sent.sent_by_name}
          <span className={draft.sent.edited_yn ? "chip human" : "chip ai"}>{draft.sent.edited_yn ? "상담원 수정" : "AI 제안"}</span>
          {draft.sent.override_check && <span className="chip gray">확인 후 발송</span>}
        </header>
        <pre className="draft-body">{draft.sent.body}</pre>
      </article>
    );
  }

  const onLink = (link: Parameters<Parameters<typeof renderBody>[1]["onLink"]>[0]) => {
    if (link.kind === "lookup") return onSource(link);
    const c = candidates.find((x) => x.doc_id === link.doc_id && x.section === link.section);
    onSource({ kind: "cite", chunk_id: c?.chunk_id ?? `${link.doc_id}§${link.section}`, text: link.text, score: c?.score });
  };

  async function save(): Promise<Draft | undefined> {
    setBusy("save");
    setGlossOld(true);
    try {
      const res = await api.save(draft.message_id, body);
      const next = await reload();
      setGlossOld(!res.gloss);
      return next;
    } catch (e) {
      onFail(e instanceof ApiError ? e.message : "저장하지 못함. 다시 시도");
      return undefined;
    } finally {
      setBusy("");
    }
  }

  async function regloss() {
    setBusy("gloss");
    try {
      await api.gloss(draft.message_id);
      setGlossOld(false);
    } catch (e) {
      onFail(e instanceof ApiError ? e.message : "대역을 만들지 못함");
    } finally {
      await reload();
      setBusy("");
    }
  }

  async function reverify() {
    setBusy("verify");
    try {
      const res = await api.verify(draft.message_id);
      if (res.state === "FAILED") onFail("검증을 하지 못함");
    } catch {
      onFail("검증을 하지 못함");
    } finally {
      await reload();
      setBusy("");
    }
  }

  async function openSend() {
    let current = draft;
    if (dirty) {  // 최신 본문으로 검토 표시를 다시 계산하려고 먼저 임시 저장한다(P7 "최신값")
      const next = await save();
      if (!next) return;
      current = next;
    }
    setSend({ marks: current.review_marks.marks, language: current.language, issues: null, notes: [], busy: false });
  }

  async function doSend(override: boolean) {
    if (!send) return;
    setSend({ ...send, busy: true });
    try {
      await api.send(draft.message_id, body, override);
      setSend(null);
      await reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body && typeof e.body === "object" && "issues" in e.body) {
        const b = e.body as { issues: SendIssue[]; notes: string[] };
        setSend({ ...send, issues: b.issues, notes: b.notes, busy: false });
        return;
      }
      setSend(null);
      onFail(e instanceof ApiError ? e.message : "발송하지 못함");
    }
  }

  function jump(m: Mark) {
    if (m.no === 5) findingRef.current?.scrollIntoView({ block: "center" });
    else if (MARK_TARGET[m.no]) onJump(MARK_TARGET[m.no]);
  }

  const gloss = draft.gloss;
  return (
    <article className="card">
      <header>
        <b>{TYPE_NAMES[draft.message_type]} 초안</b> <span className="muted">만든 시각 {time(draft.made_at_utc)} · {draft.language}</span>
        <span className="chip ai">AI 제안</span>
      </header>
      <div className="marks" aria-label="검토 표시">
        {draft.review_marks.summary === "검사 5개 통과" ? (
          <span className="ok">✓ 검사 5개 통과</span>
        ) : (
          marks.filter((m) => !m.passed).map((m) => (
            <button key={m.no} type="button" className={`mark ${markClass(m)}`} onClick={() => jump(m)}>
              {markSymbol(m)} {m.no === 5 && busy === "verify" ? "⑤ 검증 중" : m.full_text ?? m.text}
            </button>
          ))
        )}
        {(verify.state === "FAILED" || verify.state === "STALE") && (
          <button type="button" disabled={busy !== ""} onClick={reverify}>다시 검증</button>
        )}
      </div>
      <div className="editor">
        <div className="pane">
          <div className="pane-head">초안({draft.language})</div>
          {editing ? (
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={12} aria-label="초안 본문" />
          ) : (
            <div className="draft-body">
              {renderBody(body, { lookups, bad, findings, onLink, findingRef: (el) => (findingRef.current = el) })}
            </div>
          )}
          <button type="button" className="small" onClick={() => setEditing(!editing)}>{editing ? "고친 글 미리 보기" : "본문 고치기"}</button>
        </div>
        <div className="pane gloss">
          <div className="pane-head">대역(ko) {(glossOld || dirty) && gloss && <span className="chip gray">이전 내용</span>}</div>
          {gloss ? (
            <div className="draft-body">{gloss.body}</div>
          ) : (
            <p className="gray">? 대역 없음(번역 실패)</p>
          )}
          {(!gloss || glossOld) && <button type="button" className="small" disabled={busy !== ""} onClick={regloss}>다시 만들기</button>}
        </div>
      </div>
      <footer>
        <button type="button" disabled={!dirty || busy !== ""} onClick={() => void save()}>{busy === "save" ? "저장 중…" : "임시 저장"}</button>
        <button type="button" className="primary" disabled={!agent || busy !== "" || !body.trim()} onClick={() => void openSend()}
                title={agent ? undefined : "상담원 ID를 입력하세요"}>
          승인·발송
        </button>
      </footer>
      {send && <SendPopup state={{ ...send, language: ticketLanguage }} onSend={(o) => void doSend(o)} onClose={() => setSend(null)} />}
    </article>
  );
}
