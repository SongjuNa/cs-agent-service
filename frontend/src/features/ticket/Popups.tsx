// 팝업 P1 "왜?", P2 절 본문·조회값 출처, P7 발송 전 확인, P8 충돌·실패 안내 (SCR-03 팝업 표, 화면 정의서 v2 SCR-03M).
// 대화 창은 공통 Modal(목업 .dialog)을 쓴다.
import { Fragment, useEffect, useState, type ReactNode } from "react";
import { api, type Chunk, type Lookup, type Mark, type SendIssue } from "../../api";
import { Banner, Button, Modal } from "../../ui";

function Value({ value }: { value: unknown }): ReactNode {
  if (value === null || value === undefined || value === "") return <span className="tk-muted">없음</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="tk-muted">없음</span>;
    return <ul className="tk-lines">{value.map((v, i) => <li key={i}><Value value={v} /></li>)}</ul>;
  }
  if (typeof value === "object") {
    return (
      <dl className="tk-kvs">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd><Value value={v} /></dd></Fragment>)}
      </dl>
    );
  }
  if (typeof value === "boolean") return <>{value ? "예" : "아니오"}</>;
  return <>{String(value)}</>;
}

export function WhyPopup({ label, why, onClose, onRule }: { label: string; why: Record<string, unknown>; onClose: () => void; onRule?: () => void }) {
  return (
    <Modal title={`근거 보기: ${label}`} onClose={onClose} wide
      footer={<>{onRule && <Button variant="ghost" onClick={onRule}>규칙표에서 보기</Button>}<Button onClick={onClose}>닫기</Button></>}>
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
  const close = <Button onClick={onClose}>닫기</Button>;
  if (target.kind === "lookup") {
    const lv = target.lookup;
    return (
      <Modal title="조회값 출처" onClose={onClose} footer={close}>
        <dl className="tk-kvs">
          <dt>항목</dt><dd>{lv.item}</dd>
          <dt>값</dt><dd>{String(lv.value)} {lv.unit ?? ""}</dd>
          <dt>출처</dt><dd>{lv.source_table}: {lv.source_key}</dd>
        </dl>
      </Modal>
    );
  }
  return (
    <Modal title={`인용 ${target.text}`} onClose={onClose} wide footer={close}>
      {failed && <Banner tone="neg">본문 열기 실패</Banner>}
      {!failed && !chunk && <p className="tk-muted">여는 중…</p>}
      {chunk && (
        <>
          <p><b>{chunk.doc_id}</b> {chunk.doc_title}</p>
          <p>§{chunk.section_no} {chunk.section_title}{target.score !== undefined && <span className="tk-muted">, 점수 {target.score.toFixed(3)}</span>}</p>
          <pre className="tk-text">{chunk.text}</pre>
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
  if (state.issues === null && verify?.state === "FAILED") notes.push("⑤ 검증 못 함: 검증 없이 보냅니다");
  const shown = new Set(failed.map((m) => m.full_text ?? m.text)); // 서버 안내가 검토 표시와 같은 글이면 한 번만
  const extra = [...new Set(notes)].filter((n) => !shown.has(n));
  const needsOverride = state.issues !== null && state.issues.length > 0;
  return (
    <Modal title="발송 전 확인" onClose={onClose} locked={state.busy}
           footer={
             <>
               <Button onClick={onClose} disabled={state.busy}>돌아가서 고치기</Button>
               {needsOverride
                 ? <Button variant="danger" busy={state.busy} onClick={() => onSend(true)}>그래도 발송</Button>
                 : <Button variant="primary" busy={state.busy} onClick={() => onSend(false)}>발송</Button>}
             </>
           }>
      <p className="tk-muted">고객 언어: {state.language}. 고객에게 가는 글은 상담원이 승인해야 발송됩니다.</p>
      {failed.length === 0 && !needsOverride && <p>검사 5개 통과. 발송할까요?</p>}
      <ul className="tk-lines" data-testid="send-issues">
        {failed.map((m) => <li key={m.no} className={markTone(m) === "neg" ? "tk-neg" : undefined}>{m.full_text ?? m.text}</li>)}
        {state.issues?.map((issue, i) => <li key={`i${i}`} className="tk-neg">{issue.text}: {issue.items.join(", ")}</li>)}
        {extra.map((n) => <li key={n} className="tk-muted">{n}</li>)}
      </ul>
      {needsOverride && <p>[그래도 발송]을 누르면 확인하고 보냈다는 기록(override_check)이 남습니다.</p>}
    </Modal>
  );
}

/** P8 충돌·실패 안내. 409 "이미 발송된 초안" 등 쓰기 실패 때 자동으로 뜬다 */
export function FailPopup({ message, onRefresh, onClose }: { message: string; onRefresh: () => void; onClose: () => void }) {
  return (
    <Modal title="처리하지 못했습니다" onClose={onClose}
           footer={<><Button onClick={onClose}>닫기</Button><Button variant="primary" onClick={() => { onRefresh(); onClose(); }}>새로고침</Button></>}>
      <Banner tone="neg">{message}</Banner>
    </Modal>
  );
}

/** 검토 표시 한 개의 색: 통과 pos, 확인 필요 crit, 검증 못 함·고친 뒤 neu, 그 밖 걸림 neg */
export function markTone(m: Mark): "pos" | "crit" | "neu" | "neg" {
  if (m.passed) return "pos";
  if (m.state === "CHECK") return "crit";
  if (m.state === "FAILED" || m.state === "STALE" || m.state === null) return m.no === 5 ? "neu" : "neg";
  return "neg";
}
