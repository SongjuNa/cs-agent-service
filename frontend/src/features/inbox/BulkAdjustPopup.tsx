// 접수함 선택 막대 [우선순위 조정] (최신 목업 BulkAdjustModal). 새 API 없이 기존 단건 조정 API(FR-028)를 건마다 부른다.
// 미리 보기(GET)로 건마다 새 기한과 위반 여부를 읽고, 적용은 한 건씩 차례로 한다. 일부 실패해도 나머지는 적용하고 실패 건수를 알린다.
import { useEffect, useState } from "react";
import { api, ApiError, type AdjustPreview, type InboxRow } from "../../api";
import { Banner, Button, Field, Modal } from "../../ui";

const PRIORITIES = ["P1", "P2", "P3", "P4"];
const REASONS: [string, string][] = [["CUSTOMER_REQUEST", "고객 요청"], ["IMPACT_REASSESSED", "영향 범위 재평가"], ["OTHER", "기타"]]; // FR-028 처리 6
export const MAX_BULK = 50; // 미리 보기를 건마다 읽으므로 한 번에 50건까지

export function BulkAdjustPopup({ rows, onClose, onDone }: { rows: InboxRow[]; onClose: () => void; onDone: (message: string) => void }) {
  const [priority, setPriority] = useState("P1");
  const [kind, setKind] = useState("");
  const [text, setText] = useState("");
  const [previews, setPreviews] = useState<Map<string, AdjustPreview | null> | null>(null); // null = 읽지 못함(건너뜀)
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const same = rows.filter((r) => r.priority === priority);
  const todo = rows.filter((r) => r.priority !== priority && previews?.get(r.sub_ticket_id));
  const unreadable = rows.length - same.length - todo.length;
  const breach = todo.filter((r) => previews?.get(r.sub_ticket_id)?.becomes_breached).length;

  useEffect(() => {
    let current = true; // 우선순위를 빨리 바꿔도 마지막 고른 값의 답만 쓴다
    setPreviews(null);
    const targets = rows.filter((r) => r.priority !== priority);
    Promise.all(targets.map((r) => api.adjustPreview(r.sub_ticket_id, priority).then((p) => [r.sub_ticket_id, p] as const, () => [r.sub_ticket_id, null] as const)))
      .then((list) => current && setPreviews(new Map(list)));
    return () => { current = false; };
  }, [rows, priority]);

  async function submit() {
    if (!kind || !text.trim()) { setError("조정 사유를 입력하세요"); return; } // FR-028 예외 1행
    setBusy(true);
    let ok = 0;
    for (const r of todo) {
      const p = previews!.get(r.sub_ticket_id)!;
      try {
        await api.adjust(r.sub_ticket_id, { new_priority: priority, reason_kind: kind, reason_text: text.trim(), confirm_breach: !!p.becomes_breached, expected_version: p.version });
        ok += 1;
      } catch (e) {
        if (!(e instanceof ApiError)) { setError("조정 중 연결이 끊겼습니다. 접수함을 새로고침해 확인하세요"); break; }
      }
    }
    setBusy(false);
    const failed = todo.length - ok;
    onDone(`${ok}건의 우선순위를 ${priority}로 조정했습니다${failed ? ` · ${failed}건은 조정하지 못함` : ""}${same.length ? ` · 이미 ${priority}인 ${same.length}건은 건너뜀` : ""}`);
  }

  return (
    <Modal title={`우선순위 일괄 조정 · ${rows.length}건`} onClose={onClose} locked={busy}
           footer={<><Button onClick={onClose}>취소</Button>
             <Button variant="primary" busy={busy} disabled={!todo.length || !kind || !text.trim() || rows.length > MAX_BULK} onClick={() => void submit()}>{todo.length}건 적용</Button></>}>
      <div className="tk-form">
        <Field label="새 우선순위" required>
          <select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="새 우선순위">{PRIORITIES.map((p) => <option key={p}>{p}</option>)}</select>
        </Field>
        <Field label="사유 분류" required>
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="사유 분류">
            <option value="">고르세요</option>
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <div className="is-wide"><Field label="사유" required hint="선택한 건 모두의 이력에 남습니다"><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} aria-label="사유" /></Field></div>
      </div>
      <p className="tk-note" data-testid="bulk-adjust-note">
        {previews === null ? "건마다 새 기한을 계산하는 중…" : `${same.length ? `이미 ${priority}인 ${same.length}건${unreadable ? `, 계산하지 못한 ${unreadable}건` : ""}은 건너뜁니다. ` : unreadable ? `계산하지 못한 ${unreadable}건은 건너뜁니다. ` : ""}해결 기한은 건마다 ${priority} 기준으로 다시 계산됩니다.`}
      </p>
      {breach > 0 && <Banner tone="crit">{breach}건은 이 조정으로 기한을 넘긴 상태(위반)가 됩니다.</Banner>}
      {rows.length > MAX_BULK && <Banner tone="neg">한 번에 {MAX_BULK}건까지 조정할 수 있습니다. 선택을 줄이세요</Banner>}
      {error && <Banner tone="neg">{error}</Banner>}
    </Modal>
  );
}
