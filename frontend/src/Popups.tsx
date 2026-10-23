// 팝업 4개: P1 "왜?", P2 절 본문·조회값 출처, P7 발송 전 확인, P8 실패 안내 (화면 정의서 v2 SCR-03M 팝업).
import { useEffect, useState, type ReactNode } from "react";
import { api, type Chunk, type Lookup, type Mark, type SendIssue } from "./api";

export function Modal({ title, children, buttons, onClose }: { title: string; children: ReactNode; buttons: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <div className="modal-body">{children}</div>
        <div className="modal-buttons">{buttons}</div>
      </div>
    </div>
  );
}

function Value({ value }: { value: unknown }): ReactNode {
  if (value === null || value === undefined || value === "") return <span className="muted">없음</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">없음</span>;
    return <ul>{value.map((v, i) => <li key={i}><Value value={v} /></li>)}</ul>;
  }
  if (typeof value === "object") {
    return (
      <table className="kv">
        <tbody>
          {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
            <tr key={k}><th>{k}</th><td><Value value={v} /></td></tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (typeof value === "boolean") return <>{value ? "예" : "아니오"}</>;
  return <>{String(value)}</>;
}

export function WhyPopup({ label, why, onClose }: { label: string; why: Record<string, unknown>; onClose: () => void }) {
  return (
    <Modal title={`왜? — ${label}`} onClose={onClose} buttons={<button onClick={onClose}>닫기</button>}>
      <Value value={why} />
    </Modal>
  );
}

export type SourceTarget = { kind: "cite"; chunk_id: string; text: string; score?: number } | { kind: "lookup"; lookup: Lookup };

export function SourcePopup({ target, onClose }: { target: SourceTarget; onClose: () => void }) {
  const [chunk, setChunk] = useState<Chunk | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (target.kind !== "cite") return;
    api.chunk(target.chunk_id).then(setChunk, () => setFailed(true));
  }, [target]);
  const close = <button onClick={onClose}>닫기</button>;
  if (target.kind === "lookup") {
    const lv = target.lookup;
    return (
      <Modal title="조회값 출처" onClose={onClose} buttons={close}>
        <table className="kv">
          <tbody>
            <tr><th>항목</th><td>{lv.item}</td></tr>
            <tr><th>값</th><td>{String(lv.value)} {lv.unit ?? ""}</td></tr>
            <tr><th>출처</th><td>{lv.source_table}: {lv.source_key}</td></tr>
          </tbody>
        </table>
      </Modal>
    );
  }
  return (
    <Modal title={`인용 ${target.text}`} onClose={onClose} buttons={close}>
      {failed && <p className="bad">! 본문 열기 실패</p>}
      {!failed && !chunk && <p className="muted">여는 중…</p>}
      {chunk && (
        <>
          <p><b>{chunk.doc_id}</b> {chunk.doc_title}</p>
          <p>§{chunk.section_no} {chunk.section_title}{target.score !== undefined && <span className="muted"> · 점수 {target.score.toFixed(3)}</span>}</p>
          <pre className="chunk">{chunk.text}</pre>
        </>
      )}
    </Modal>
  );
}

export interface SendState {
  marks: Mark[];
  language: string;
  issues: SendIssue[] | null; // null = 아직 서버 검사 전
  notes: string[];
  busy: boolean;
}

export function SendPopup({ state, onSend, onClose }: { state: SendState; onSend: (override: boolean) => void; onClose: () => void }) {
  const failed = state.marks.filter((m) => !m.passed);
  const verify = state.marks.find((m) => m.no === 5);
  const notes = [...state.notes];
  if (state.issues === null && verify?.state === "FAILED") notes.push("⑤ 검증 못 함 — 검증 없이 보냅니다");
  if (state.issues === null && verify?.state === "STALE") notes.push("⑤ 고친 뒤 검증 안 함");
  const needsOverride = state.issues !== null && state.issues.length > 0;
  return (
    <Modal
      title="발송 전 확인"
      onClose={onClose}
      buttons={
        <>
          {needsOverride ? (
            <button className="primary" disabled={state.busy} onClick={() => onSend(true)}>그래도 발송</button>
          ) : (
            <button className="primary" disabled={state.busy} onClick={() => onSend(false)}>발송</button>
          )}
          <button onClick={onClose}>돌아가서 고치기</button>
        </>
      }
    >
      <p className="muted">고객 언어: {state.language}</p>
      {failed.length === 0 && !needsOverride && <p className="ok">✓ 검사 5개 통과 — 발송할까요?</p>}
      <ul className="lines">
        {failed.map((m) => (
          <li key={m.no} className={markClass(m)}>{markSymbol(m)} {m.full_text ?? m.text}</li>
        ))}
        {state.issues?.map((issue, i) => (
          <li key={`i${i}`} className="bad">! {issue.text}: {issue.items.join(", ")}</li>
        ))}
        {notes.map((n) => <li key={n} className="gray">? {n}</li>)}
      </ul>
      {needsOverride && <p>[그래도 발송]을 누르면 확인하고 보냈다는 기록(override_check)이 남습니다.</p>}
    </Modal>
  );
}

export function FailPopup({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <Modal
      title="실패 안내"
      onClose={onClose}
      buttons={
        <>
          <button onClick={() => window.location.reload()}>새로고침</button>
          <button onClick={onClose}>닫기</button>
        </>
      }
    >
      <p className="bad">! {message}</p>
    </Modal>
  );
}

export function markClass(m: Mark): string {
  if (m.passed) return "ok";
  if (m.state === "CHECK") return "gold";
  if (m.state === "FAILED" || m.state === "STALE" || m.state === null) return m.no === 5 ? "gray" : "bad";
  return "bad";
}

export function markSymbol(m: Mark): string {
  const cls = markClass(m);
  return cls === "ok" ? "✓" : cls === "gold" ? "⚠" : cls === "gray" ? "?" : "!";
}
