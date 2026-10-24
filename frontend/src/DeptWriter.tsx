// 이관 부서·예외 부서의 작성 영역 (명세서 FR-033 처리 8·9, FR-031 처리 9, 기술 명세서 v1.4 §8-2, add-dept-reply C-164).
// 이관받은 부서: 회신 작성란 + [회신 등록](메일 아님, 임시 저장 없음). 예외 부서(FIELD_SVC, SALES_OPS): 고객 메일 + [임시 저장]·[승인].
import { useState } from "react";
import { api, ApiError, type SubTicket } from "./api";

export function DeptWriter({ sub, language, onDone, onFail }: {
  sub: SubTicket; language: string; onDone: () => void; onFail: (message: string) => void;
}) {
  const st = sub.sub_ticket;
  const mail = sub.writer === "DEPT_MAIL";
  const draft = sub.dept_mails.find((m) => m.message_status === "DRAFT");
  const [body, setBody] = useState(draft?.body ?? "");
  const [busy, setBusy] = useState(false);
  const open = st.status === "ESCALATED";

  async function run(fn: () => Promise<unknown>, fallback: string) {
    setBusy(true);
    try {
      await fn();
      onDone();
    } catch (e) {
      onFail(e instanceof ApiError ? e.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  // [임시 저장]: 처음이면 초안을 만든 뒤 저장(대역을 만든다, C-165). [승인]: 저장 뒤 발송(대조·검증 없음)
  async function saved(): Promise<number> {
    const id = draft?.message_id ?? (await api.deptMail(st.sub_ticket_id, body)).message_id;
    await api.save(id, body);
    return id;
  }

  const empty = !body.trim();
  return (
    <div className="card dept-writer">
      <header>
        <h5>{mail ? "고객에게 보낼 메일" : "C/S 팀에 회신"}</h5>
        <span className="muted small">
          {mail ? `받는 사람: 고객 · 언어 ${language} · 숫자 검사·검증 없음` : "메일이 아니며 고객에게 가지 않습니다"}
        </span>
      </header>
      {!mail && sub.dept_replies.map((r) => (
        <p key={r.message_id} className="small muted">등록함 {r.sent_at_utc.replace("T", " ").slice(0, 16)} · {r.sent_by_name}</p>
      ))}
      {mail && sub.dept_mails.filter((m) => m.message_status === "SENT").map((m) => (
        <p key={m.message_id} className="small muted">보냄 {m.sent_at_utc.replace("T", " ").slice(0, 16)} · {m.sent_by_name}</p>
      ))}
      <textarea aria-label={mail ? "고객 메일 본문" : "회신 본문"} rows={6} value={body} disabled={!open || busy}
                onChange={(e) => setBody(e.target.value)} />
      {mail && draft?.gloss && <p className="small muted">대역: {draft.gloss}</p>}
      {!open ? <p className="gray">{mail ? "보냄 — C/S 팀이 마무리합니다" : "회신 등록됨 — C/S 팀이 처리 중"}</p>
        : mail ? (
          <div className="actions">
            <button type="button" disabled={busy || empty} onClick={() => void run(saved, "저장하지 못함. 다시 시도")}>임시 저장</button>
            <button type="button" className="primary" disabled={busy || empty}
                    onClick={() => void run(async () => api.send(await saved(), body, false), "발송 실패")}>승인</button>
          </div>
        ) : (
          <div className="actions">
            <button type="button" className="primary" disabled={busy || empty}
                    onClick={() => void run(() => api.deptReply(st.sub_ticket_id, body), "회신 등록 실패")}>회신 등록</button>
          </div>
        )}
    </div>
  );
}
