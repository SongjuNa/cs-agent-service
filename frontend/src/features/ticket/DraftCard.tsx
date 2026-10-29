// 초안 카드 R-01~R-05·CP-7·M-R-01·M-R-02 (FR-031, FR-039, FR-049, 화면 정의서 v2 SCR-03M ④ R).
// 왼쪽 "보낼 글(고객 언어), 고칠 수 있음" / 오른쪽 "한국어 대역, 검토용, 발송 안 함". 인용·숫자는 P2 링크.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Draft, type Lookup, type Mark, type SendIssue } from "../../api";
import { Button, Chip } from "../../ui";
import { renderBody, type BodyLink } from "./body";
import { utc } from "./CustomerTab";
import { markTone, SendPopup, type SendState, type SourceTarget } from "./Popups";

const TYPE_NAMES = { INFO_REQUEST: "정보 요청", FINAL_REPLY: "답변" } as const;
// 걸린 번호를 누르면 옮겨 갈 근거 줄 (화면 정의서 v2 0-7절)
const MARK_TARGET: Record<number, string> = { 1: "C-10", 2: "C-07", 3: "C-10", 4: "C-02" };
const CIRCLED = ["", "①", "②", "③", "④", "⑤"];

export function DraftCard({ agent, draft, seqLabel, lookups, candidates, ticketLanguage, onSource, onJump, onFail, onSent, refresh }: {
  agent: string;
  draft: Draft;
  seqLabel: string | null;
  lookups: Lookup[];
  candidates: { doc_id: string; section: string; chunk_id: string; score: number }[];
  ticketLanguage: string;
  onSource: (t: SourceTarget) => void;
  onJump: (rowId: string) => void;
  onFail: (message: string) => void;
  onSent: () => void;
  refresh: () => Promise<unknown>;
}) {
  const [body, setBody] = useState(draft.body);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "gloss" | "verify">("");
  const [glossOld, setGlossOld] = useState(false);
  const [send, setSend] = useState<SendState | null>(null);
  const [emptyError, setEmptyError] = useState(false);
  const findingRef = useRef<HTMLElement | null>(null);
  useEffect(() => setBody(draft.body), [draft.message_id, draft.body]);
  const dirty = body !== draft.body;
  const marks = draft.review_marks.marks;
  const verify = marks.find((m) => m.no === 5);
  const findings = verify?.state === "FOUND" ? verify.findings ?? [] : [];
  const bad = draft.check && !draft.check.passed_yn ? [...draft.check.detail.bad_citations, ...draft.check.detail.bad_numbers] : [];
  const title = `${TYPE_NAMES[draft.message_type]}${seqLabel ? `, ${seqLabel}` : ""}`;

  if (draft.sent) {
    // M-R-02 보낸 글: 읽기 전용
    return (
      <article className="tk-draft tk-draft--sent" data-testid="draft-card" data-state="sent" data-type={draft.message_type}>
        <header className="tk-draft__head">
          <b>{title}</b>
          <span data-testid="sent-line">발송됨 {utc(draft.sent.sent_at_utc)} · {draft.sent.sent_by_name}</span>
          <Chip tone={draft.sent.edited_yn ? "brand" : "info"}>{draft.sent.edited_yn ? "상담원 수정" : "AI 제안 그대로"}</Chip>
          {draft.sent.override_check && <Chip tone="crit">확인하고 발송</Chip>}
        </header>
        <pre className="tk-text" dir={draft.language === "ar" ? "rtl" : undefined}>{draft.sent.body}</pre>
      </article>
    );
  }

  const onLink = (link: BodyLink) => {
    if (link.kind === "lookup") return onSource(link);
    const c = candidates.find((x) => x.doc_id === link.doc_id && x.section === link.section);
    onSource({ kind: "cite", chunk_id: c?.chunk_id ?? `${link.doc_id}§${link.section}`, text: link.text, score: c?.score });
  };

  async function save(): Promise<boolean> {
    if (!body.trim()) { setEmptyError(true); return false; }
    setBusy("save");
    setGlossOld(true);
    try {
      const res = await api.save(draft.message_id, body);
      await refresh();
      setGlossOld(!res.gloss);
      return true;
    } catch (e) {
      onFail(e instanceof ApiError ? e.message : "저장하지 못함. 다시 시도");
      return false;
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
      await refresh();
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
      await refresh();
      setBusy("");
    }
  }

  async function openSend() {
    if (!body.trim()) { setEmptyError(true); return; }
    // 고친 글이면 먼저 임시 저장해 검토 표시를 최신 본문으로 다시 계산한다(P7 "최신값")
    if (dirty && !(await save())) return;
    setSend({ marks, language: draft.language, issues: null, notes: [], busy: false });
  }

  async function doSend(override: boolean) {
    if (!send) return;
    setSend({ ...send, busy: true });
    try {
      await api.send(draft.message_id, body, override);
      setSend(null);
      onSent();
      await refresh();
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
  const rtl = draft.language === "ar"; // 아랍어는 오른쪽에서 왼쪽(FR-030 처리 1과 같게)
  const allPassed = marks.every((m) => m.passed);
  return (
    <article className="tk-draft" data-testid="draft-card" data-state="draft" data-type={draft.message_type}>
      <header className="tk-draft__head">
        <b>{title} 초안</b>
        <Chip tone="outline">{draft.language}</Chip>
        <Chip tone="info">AI 제안</Chip>
        {draft.check && !draft.check.passed_yn && <Chip tone="neg">자체 대조 불일치</Chip>}
        <span className="tk-muted">만든 시각 {utc(draft.made_at_utc)}</span>
      </header>

      {/* CP-7 검토 표시 5개. 발송을 막지 않는다 */}
      <div className="tk-marks" aria-label="검토 표시" data-testid="review-marks">
        {allPassed ? <span className="tk-mark tk-mark--pos">검사 5개 통과</span> : (
          <>
            {marks.map((m) => (
              <button key={m.no} type="button" className={`tk-mark tk-mark--${markTone(m)}`} data-no={m.no} data-state={m.state ?? ""}
                      onClick={() => jump(m)} title={m.full_text ?? undefined}>
                {m.passed ? `${CIRCLED[m.no]} 통과` : m.no === 5 && busy === "verify" ? "⑤ 검증 중" : m.text}
              </button>
            ))}
            <span className="tk-marks__note">발송은 막지 않습니다. 확인한 뒤 보내세요</span>
          </>
        )}
        {(verify?.state === "FAILED" || verify?.state === "STALE") && (
          <Button size="sm" busy={busy === "verify"} disabled={busy !== "" && busy !== "verify"} onClick={() => void reverify()}>다시 검증</Button>
        )}
      </div>

      <div className="tk-panes">
        <div>
          <div className="tk-text-head"><b>보낼 글({draft.language}), 고칠 수 있음</b>
            <button type="button" className="tk-link" onClick={() => setEditing(!editing)}>{editing ? "링크 보기" : "본문 고치기"}</button>
          </div>
          {editing ? (
            <textarea className="tk-editor" dir={rtl ? "rtl" : undefined} value={body} aria-label="초안 본문" onChange={(e) => { setBody(e.target.value); setEmptyError(false); }} />
          ) : (
            <div className="tk-text tk-view" dir={rtl ? "rtl" : undefined} data-testid="draft-body">
              {renderBody(body, { lookups, bad, findings, onLink, findingRef: (el) => (findingRef.current = el) })}
            </div>
          )}
          {emptyError && <p className="tk-neg" role="alert">보낼 글이 비어 있습니다. 내용을 쓴 뒤 발송하세요</p>}
        </div>
        <div>
          <div className="tk-text-head"><b>한국어 대역</b><span>검토용, 발송 안 함</span></div>
          {gloss ? (
            <div className={glossOld || dirty ? "tk-text tk-gloss is-old" : "tk-text tk-gloss"} data-testid="gloss">{gloss.body}</div>
          ) : (
            <div className="tk-text tk-gloss tk-empty" data-testid="gloss">대역 없음(번역 실패)</div>
          )}
          {(!gloss || glossOld) && <Button size="sm" busy={busy === "gloss"} disabled={busy !== "" && busy !== "gloss"} onClick={() => void regloss()}>다시 만들기</Button>}
        </div>
      </div>

      <footer className="tk-draft__foot">
        <span className="tk-note">고객에게 가는 글은 상담원이 승인해야 발송됩니다</span>
        <Button busy={busy === "save"} disabled={!dirty || (busy !== "" && busy !== "save")} onClick={() => void save()}>임시 저장</Button>
        <Button variant="primary" disabled={!agent || busy !== ""} onClick={() => void openSend()}
                title={agent ? undefined : "왼쪽 위 프로필에서 상담원을 고르세요"}>승인하고 발송</Button>
      </footer>
      {send && <SendPopup state={{ ...send, language: ticketLanguage }} onSend={(o) => void doSend(o)} onClose={() => setSend(null)} />}
    </article>
  );
}
