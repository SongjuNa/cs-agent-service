// 상세 전체판 팝업: P3 우선순위 조정, P6 고객 회신 입력 (화면 정의서 v1 SCR-03-P3·P6, FR-028, FR-032).
import { useEffect, useState } from "react";
import { api, ApiError, type AdjustPreview, type SubTicket } from "./api";
import { Modal } from "./Popups";

const PRIORITIES = ["P1", "P2", "P3", "P4"];
const REASONS: [string, string][] = [["CUSTOMER_REQUEST", "고객 요청"], ["IMPACT_REASSESSED", "영향 범위 재평가"], ["OTHER", "기타"]]; // FR-028 처리 6

const errorText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

export function AdjustPopup({ sub, onDone, onClose }: { sub: SubTicket; onDone: () => void; onClose: () => void }) {
  const current = sub.sub_ticket.priority;
  const [priority, setPriority] = useState(PRIORITIES.find((p) => p !== current) ?? "P1");
  const [kind, setKind] = useState("");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<AdjustPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = sub.sub_ticket.sub_ticket_id;

  useEffect(() => {
    setPreview(null);
    api.adjustPreview(id, priority).then(setPreview).catch((e) => setError(errorText(e, "미리 보기 실패")));
  }, [id, priority]);

  async function submit() {
    if (!kind || !text.trim()) { setError("조정 사유를 입력하세요"); return; } // FR-028 예외 1행
    setBusy(true);
    try {
      await api.adjust(id, { new_priority: priority, reason_kind: kind, reason_text: text.trim(),
                             confirm_breach: !!preview?.becomes_breached, expected_version: preview?.version ?? sub.version });
      onDone();
    } catch (e) {
      setError(errorText(e, "조정 실패"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`우선순위 조정 · 문의 ${sub.sub_ticket.seq}`} onClose={onClose}
           buttons={<><button onClick={onClose}>취소</button><button className="primary" disabled={busy} onClick={() => void submit()}>조정</button></>}>
      <div className="form-grid">
        <label>새 우선순위
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.filter((p) => p !== current).map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label>사유 분류
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">고르세요</option>
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="wide">사유 <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} /></label>
      </div>
      {preview && (
        <p>
          SLA 목표 {preview.from_fr_target_h ?? "?"}/{preview.from_res_target_h ?? "?"}h → {preview.to_fr_target_h ?? "?"}/{preview.to_res_target_h ?? "?"}h
          {preview.to_sla_id && <span className="muted"> ({preview.to_sla_id})</span>}
        </p>
      )}
      {preview?.becomes_breached && <p className="bad">! 이 조정으로 기한 위반 상태가 됩니다. 계속할까요?</p>}
      {error && <p className="bad">! {error}</p>}
    </Modal>
  );
}

export function ReplyPopup({ ticketId, language, subs, onDone, onClose }: {
  ticketId: string; language: string; subs: SubTicket[]; onDone: () => void; onClose: () => void;
}) {
  const waiting = subs.filter((s) => s.sub_ticket.status === "WAITING_CUSTOMER");
  const [body, setBody] = useState("");
  const [lang, setLang] = useState(language);
  const [at, setAt] = useState("");
  const [targets, setTargets] = useState<string[]>(waiting.map((s) => s.sub_ticket.sub_ticket_id));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!body.trim()) { setError("회신 내용을 입력하세요"); return; } // SCR-03-P6 오류 문구
    setBusy(true);
    try {
      await api.reply(ticketId, { body, language: lang, received_at: at ? new Date(`${at}Z`).toISOString() : null,
                                  target_sub_ticket_ids: waiting.length > 1 ? targets : null });
      onDone();
    } catch (e) {
      setError(errorText(e, "회신 입력 실패"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="고객 회신 입력" onClose={onClose}
           buttons={<><button onClick={onClose}>취소</button><button className="primary" disabled={busy} onClick={() => void submit()}>입력</button></>}>
      <div className="form-grid">
        <label className="wide">회신 본문 <textarea rows={6} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} /></label>
        <label>회신 언어 <input value={lang} onChange={(e) => setLang(e.target.value)} /></label>
        <label>회신 시각(UTC, 비우면 지금) <input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></label>
        {waiting.length > 1 && (
          <fieldset className="wide">
            <legend>대상 하위 문의</legend>
            {waiting.map((s) => {
              const sid = s.sub_ticket.sub_ticket_id;
              return (
                <label key={sid}>
                  <input type="checkbox" checked={targets.includes(sid)}
                         onChange={(e) => setTargets(e.target.checked ? [...targets, sid] : targets.filter((t) => t !== sid))} />
                  문의 {s.sub_ticket.seq}: {s.sub_ticket.category_code}
                </label>
              );
            })}
          </fieldset>
        )}
      </div>
      {error && <p className="bad">! {error}</p>}
    </Modal>
  );
}
