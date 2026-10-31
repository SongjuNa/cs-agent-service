// 탭 ③ 보낼 것 (SCR-03 R-00~R-08, SCR-03-C 부서 영역, FR-031·039·049·033). 배치는 목업 v1.42 `sendColumn`.
// 위 띠 "고객에게 보낼 초안. 승인해야 발송됩니다" + [이관], 아래 탭 "정보 요청 n / 답변 n"(초안이 있는 탭이 먼저).
import { useState } from "react";
import type { Detail, Draft, SubTicket } from "../../api";
import { CATEGORY, label } from "../../app/labels";
import { Button, Tabs } from "../../ui";
import { DeptReplies, DeptWriter } from "./DeptWriter";
import { DraftCard } from "./DraftCard";
import type { SourceTarget } from "./Popups";

type Kind = Draft["message_type"];
const KINDS: Kind[] = ["INFO_REQUEST", "FINAL_REPLY"];
const live = (s: SubTicket) => s.drafts.filter((d) => !d.superseded_at);

/** R-06 초안이 없을 때의 사유. 답변 "근거 없음"이면 빈 편집기를 함께 둔다(add-manual-draft) */
function noDraftText(detail: Detail, sub: SubTicket, kind: Kind): { text: string; editor: boolean } {
  const st = sub.sub_ticket;
  if (detail.processing) return { text: "처리 중", editor: false };
  if (st.pipeline_error) return { text: "초안 생성 실패", editor: false };
  if (kind === "INFO_REQUEST") {
    return st.missing_blocking_info.length
      ? { text: "정보 요청 초안이 없습니다", editor: false }
      : { text: "막는 항목 없음. 정보 요청 초안이 필요하지 않습니다", editor: false };
  }
  if (st.missing_blocking_info.length && st.status !== "ESCALATED") return { text: "막는 정보 요청 중", editor: false };
  if (st.status === "ESCALATED") return { text: "전문 부서 회신을 기다리는 중", editor: false };
  return { text: "근거 없음 — 상담원 작성 필요", editor: true };
}

/** 근거 없음일 때의 빈 편집기. 저장·발송 API(POST /sub-tickets/{id}/drafts, add-manual-draft)가 아직 없어 버튼은 꺼 둔다 */
function ManualEditor({ sub }: { sub: SubTicket }) {
  const [body, setBody] = useState("");
  return (
    <div className="tk-empty" data-testid={`manual-${sub.sub_ticket.seq}`}>
      <textarea className="tk-editor" aria-label="직접 쓰는 답변" value={body} onChange={(e) => setBody(e.target.value)} />
      <div className="tk-draft__foot">
        <span className="tk-note">직접 쓴 답변 저장은 다음 변경(add-manual-draft)에서 연결합니다</span>
        <Button disabled>임시 저장</Button>
        <Button variant="primary" disabled>승인하고 발송</Button>
      </div>
    </div>
  );
}

export function SendTab({ detail, agent, kind, onKind, onSource, onJump, onFail, refresh }: {
  detail: Detail; agent: string; kind: Kind | null; onKind: (k: Kind) => void;
  onSource: (t: SourceTarget) => void; onJump: (rowId: string) => void; onFail: (message: string) => void;
  refresh: () => Promise<unknown>;
}) {
  const subs = detail.sub_tickets;
  const n = subs.length;
  const count = (k: Kind) => subs.reduce((a, s) => a + live(s).filter((d) => d.message_type === k).length, 0);
  // 초안이 있는 탭이 먼저(R-00). 둘 다 있으면 정보 요청이 먼저(1차 응답 인정, FR-027)
  const order = [...KINDS].sort((a, b) => Number(count(b) > 0) - Number(count(a) > 0));
  const active = kind ?? order[0];
  // 고른 부서가 이관받은 부서면 그 문의는 부서 작성 영역만(§8-2, AC-033-7). 모두 그렇면 C/S 띠·[이관]을 숨긴다
  const deptOnly = n > 0 && subs.every((s) => s.writer !== "CS");

  return (
    <div className="tk-pane">
      {!deptOnly && (
        <>
          <div className="tk-pane__bar">
            고객에게 보낼 초안. 승인해야 발송됩니다
          </div>
          <div className="tk-send-tabs">
            <Tabs label="보낼 글 종류" value={active} onChange={(k) => onKind(k as Kind)}
                  items={order.map((k) => ({ key: k, label: k === "INFO_REQUEST" ? "정보 요청" : "답변", count: count(k) }))} />
          </div>
        </>
      )}
      {subs.map((sub) => {
        const st = sub.sub_ticket;
        const seqLabel = n > 1 ? `문의 ${st.seq}/${n}` : null;
        const head = n > 1 && <div className="tk-sub__head">문의 {st.seq}/{n}: {label(CATEGORY, st.category_code)}</div>;
        if (sub.writer !== "CS") {
          return (
            <div key={st.sub_ticket_id} className="tk-sub">
              {head}
              <DeptWriter key={`${st.sub_ticket_id}-${sub.version}`} sub={sub} language={detail.ticket.language}
                          onDone={() => void refresh()} onFail={onFail} />
            </div>
          );
        }
        const drafts = live(sub).filter((d) => d.message_type === active);
        const old = sub.drafts.filter((d) => d.superseded_at && d.message_type === active);
        const lookups = sub.evidence_rows.find((r) => r.id === "M-C-02")?.lookups ?? [];
        const empty = drafts.length ? null : noDraftText(detail, sub, active);
        return (
          <div key={st.sub_ticket_id} className="tk-sub" data-testid={`send-${st.seq}`}>
            {head}
            {drafts.map((d) => (
              <DraftCard key={d.message_id} agent={agent} draft={d} seqLabel={seqLabel} lookups={lookups}
                         candidates={st.evidence_json} ticketLanguage={detail.ticket.language}
                         onSource={onSource} onJump={onJump} onFail={onFail} onSent={() => undefined} refresh={refresh} />
            ))}
            {empty && (
              <div className="tk-empty" data-testid="no-draft">
                <p>{empty.text}</p>
                {empty.editor && <ManualEditor sub={sub} />}
              </div>
            )}
            {active === "FINAL_REPLY" && <DeptReplies sub={sub} />}
            {old.length > 0 && (
              <details className="tk-old">
                <summary>이전 초안 {old.length}개</summary>
                {old.map((d) => <pre key={d.message_id} className="tk-text">{d.body}</pre>)}
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}
