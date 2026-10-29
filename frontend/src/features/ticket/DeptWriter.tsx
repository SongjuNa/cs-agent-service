// 부서 영역 SCR-03-C (명세서 FR-033 처리 8·9, FR-031 처리 9, 기술 명세서 v1.4 §8-2, add-dept-reply C-164). 배치는 목업 v1.42 `deptArea`.
// 이관받은 부서: 회신 작성란 + [회신 등록](메일 아님, 임시 저장 없음). 예외 부서(FIELD_SVC, SALES_OPS): 고객 메일 + [임시 저장]·[승인].
import { useState } from "react";
import { api, ApiError, type SubTicket } from "../../api";
import { Button } from "../../ui";
import { utc } from "./CustomerTab";

/** C/S 쪽에서 보는 "전문 부서 회신" 목록(ESCALATED 이후) */
export function DeptReplies({ sub }: { sub: SubTicket }) {
  if (!sub.dept_replies.length && !sub.dept_mails.some((m) => m.message_status === "SENT")) return null;
  return (
    <section className="tk-dept" aria-label="전문 부서 회신" data-testid="dept-replies">
      <h3>전문 부서 회신{sub.sub_ticket.escalated_to ? `, ${sub.sub_ticket.escalated_to}` : ""}</h3>
      <ul className="tk-dept__lines">
        {sub.dept_replies.map((r) => (
          <li key={r.message_id}>
            <span className="tk-note">{utc(r.sent_at_utc)} · {r.sent_by_name}</span>
            <pre className="tk-text">{r.body}</pre>
          </li>
        ))}
        {sub.dept_mails.filter((m) => m.message_status === "SENT").map((m) => (
          <li key={m.message_id}>
            <span className="tk-note">고객에게 보낸 메일 {utc(m.sent_at_utc)} · {m.sent_by_name}</span>
            <pre className="tk-text">{m.body}</pre>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function DeptWriter({ sub, language, onDone, onFail }: {
  sub: SubTicket; language: string; onDone: () => void; onFail: (message: string) => void;
}) {
  const st = sub.sub_ticket;
  const mail = sub.writer === "DEPT_MAIL";
  const draft = sub.dept_mails.find((m) => m.message_status === "DRAFT");
  const [body, setBody] = useState(draft?.body ?? "");
  const [busy, setBusy] = useState<"" | "save" | "send">("");
  const open = st.status === "ESCALATED";

  async function run(kind: "save" | "send", fn: () => Promise<unknown>, fallback: string) {
    setBusy(kind);
    try {
      await fn();
      onDone();
    } catch (e) {
      onFail(e instanceof ApiError ? e.message : fallback);
    } finally {
      setBusy("");
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
    <section className="tk-dept" aria-label={mail ? "예외 부서 고객 메일" : "부서 회신 작성"} data-testid="dept-writer" data-writer={sub.writer}>
      <h3>{mail ? "고객에게 보낼 메일" : "C/S 팀에 회신"}</h3>
      <span className="tk-note">
        {mail ? `받는 사람: 고객 · 언어 ${language} · 숫자 검사·검증 없음` : "메일이 아니며 고객에게 가지 않습니다"}
      </span>
      {!mail && sub.dept_replies.map((r) => (
        <p key={r.message_id} className="tk-note">등록함 {utc(r.sent_at_utc)} · {r.sent_by_name}</p>
      ))}
      {mail && sub.dept_mails.filter((m) => m.message_status === "SENT").map((m) => (
        <p key={m.message_id} className="tk-note">보냄 {utc(m.sent_at_utc)} · {m.sent_by_name}</p>
      ))}
      <textarea className="tk-editor" aria-label={mail ? "고객 메일 본문" : "회신 본문"} value={body} disabled={!open || busy !== ""}
                onChange={(e) => setBody(e.target.value)} />
      {mail && draft?.gloss && <div className="tk-text tk-gloss" data-testid="gloss">{draft.gloss}</div>}
      {!open ? <p className="tk-muted">{mail ? "보냄 — C/S 팀이 마무리합니다" : "회신 등록됨 — C/S 팀이 처리 중"}</p>
        : mail ? (
          <div className="tk-draft__foot">
            <span className="tk-note">고객에게 가는 글은 승인해야 발송됩니다</span>
            <Button busy={busy === "save"} disabled={busy !== "" || empty} onClick={() => void run("save", saved, "저장하지 못함. 다시 시도")}>임시 저장</Button>
            <Button variant="primary" busy={busy === "send"} disabled={busy !== "" || empty}
                    onClick={() => void run("send", async () => api.send(await saved(), body, false), "발송 실패")}>승인</Button>
          </div>
        ) : (
          <div className="tk-draft__foot">
            <span className="tk-note">등록하면 C/S 팀이 답변을 만듭니다</span>
            <Button variant="primary" busy={busy === "send"} disabled={busy !== "" || empty}
                    onClick={() => void run("send", () => api.deptReply(st.sub_ticket_id, body), "회신 등록 실패")}>회신 등록</Button>
          </div>
        )}
    </section>
  );
}
