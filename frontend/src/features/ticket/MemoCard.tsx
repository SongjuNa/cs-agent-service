// 내부 메모 (변경 add-internal-notes, 최신 목업 "내부 메모"). 상담원끼리만 보며 고객에게 보이지 않는다.
// 수정·삭제는 없다. 남긴 사람과 시각이 기록으로 남는다.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../../api";
import { Button } from "../../ui";
import { utc } from "./CustomerTab";

const MAX = 2000;

export function MemoCard({ ticketId, agent }: { ticketId: string; agent: string }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const notes = useQuery({ queryKey: ["notes", ticketId], queryFn: () => api.notes(ticketId) });
  const add = useMutation({
    mutationFn: (body: string) => api.addNote(ticketId, body),
    onSuccess: () => { setText(""); setError(""); void qc.invalidateQueries({ queryKey: ["notes", ticketId] }); void qc.invalidateQueries({ queryKey: ["inbox"] }); },
    onError: (e) => setError(e instanceof ApiError ? e.message : "메모를 저장하지 못했습니다. 다시 시도하세요"),
  });
  const list = notes.data ?? [];
  return (
    <section className="tk-sec tk-memo" id="tk-sec-memo" aria-label="내부 메모">
      <h2 className="tk-sec__h">내부 메모 <span className="tk-memo__hint">고객에게 보이지 않습니다</span></h2>
      <div className="tk-pane">
        {notes.isError && <p className="tk-neg" role="alert">메모를 불러오지 못했습니다</p>}
        {list.length > 0 && (
          <ul className="tk-memo__list" data-testid="memo-list">
            {list.map((n) => (
              <li key={n.note_id}>
                <span className="tk-note">{n.author} · {utc(n.created_at_utc)}</span>
                <p>{n.body}</p>
              </li>
            ))}
          </ul>
        )}
        <textarea className="tk-editor tk-memo__input" aria-label="내부 메모" value={text} maxLength={MAX}
                  placeholder="통화 내용, 확인한 것, 다음 담당자에게 남길 말"
                  onChange={(e) => { setText(e.target.value); setError(""); }} />
        {error && <p className="tk-neg" role="alert">{error}</p>}
        <div className="tk-draft__foot">
          <span className="tk-note">{agent ? `${agent}님 이름으로 남습니다` : "상단에서 상담원을 먼저 고르세요"}</span>
          <Button variant="primary" disabled={!agent || !text.trim()} busy={add.isPending} onClick={() => add.mutate(text)}>메모 남기기</Button>
        </div>
      </div>
    </section>
  );
}
