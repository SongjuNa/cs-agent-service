// 상세 전체판 팝업: P3 우선순위 조정, P4 이관, P6 고객 회신 입력 (화면 정의서 v1 SCR-03-P3·P4·P6, FR-028, FR-033, FR-032).
import { useEffect, useState } from "react";
import { api, ApiError, type AdjustPreview, type Department, type SubTicket } from "./api";
import { Modal } from "./Popups";

const PRIORITIES = ["P1", "P2", "P3", "P4"];
const REASONS: [string, string][] = [["CUSTOMER_REQUEST", "고객 요청"], ["IMPACT_REASSESSED", "영향 범위 재평가"], ["OTHER", "기타"]]; // FR-028 처리 6

// 이관 사유 11값(화면 정의서 v1 CP-6, schema.sql escalation_reason)
const ESCALATION_REASONS = ["ONSITE_REQUIRED", "QUALITY_RETURN", "RMA_REQUIRED", "COMMERCIAL_TERMS", "CAUSE_ANALYSIS",
  "FW_UPDATE_FAILURE", "SPEC_INTERPRETATION", "P1", "OUT_OF_SCOPE_TEST", "CUSTOM_SPEC", "SAFETY"];

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

/** P4 이관(FR-033 처리 1~4): 부서 기본값 = 이관 후보 첫 부서, 사유 기본값 = 그 후보의 사유 코드(변경 23 C-146). */
export function EscalatePopup({ subs, onDone, onClose }: { subs: SubTicket[]; onDone: () => void; onClose: () => void }) {
  const open = subs.filter((s) => s.sub_ticket.status === "IN_PROGRESS");
  const [subId, setSubId] = useState(open[0]?.sub_ticket.sub_ticket_id ?? "");
  const sub = open.find((s) => s.sub_ticket.sub_ticket_id === subId);
  const top = sub?.escalation?.escalation_candidates[0];
  const [dept, setDept] = useState(top?.dept ?? "");
  const [reason, setReason] = useState(top?.reason_code ?? "");
  const [memo, setMemo] = useState("");
  const [depts, setDepts] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.departments().then(setDepts).catch(() => setDepts([])); }, []);

  function pick(id: string) {
    const c = open.find((s) => s.sub_ticket.sub_ticket_id === id)?.escalation?.escalation_candidates[0];
    setSubId(id); setDept(c?.dept ?? ""); setReason(c?.reason_code ?? ""); setError(null);
  }

  async function submit() {
    if (!sub) return;
    if (!reason) { setError("이관 사유를 고르세요"); return; } // FR-033 예외 1행
    setBusy(true);
    try {
      await api.escalate(subId, { dept, reason_code: reason, memo: memo.trim(), expected_version: sub.version });
      onDone();
    } catch (e) {
      setError(errorText(e, "이관 실패"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="이관" onClose={onClose}
           buttons={<><button onClick={onClose}>취소</button><button className="primary" disabled={busy || !sub} onClick={() => void submit()}>이관</button></>}>
      <div className="form-grid">
        {open.length > 1 && (
          <label className="wide">문의
            <select value={subId} onChange={(e) => pick(e.target.value)}>
              {open.map((s) => <option key={s.sub_ticket.sub_ticket_id} value={s.sub_ticket.sub_ticket_id}>
                문의 {s.sub_ticket.seq}: {s.sub_ticket.category_code ?? "유형 미정"}</option>)}
            </select>
          </label>
        )}
        <label>이관 부서
          <select value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">고르세요</option>
            {depts.map((d) => <option key={d.dept_code} value={d.dept_code}>{d.dept_code}{d.dept_code === top?.dept ? " (이관 후보)" : ""}</option>)}
          </select>
        </label>
        <label>이관 사유
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">고르세요</option>
            {ESCALATION_REASONS.map((r) => <option key={r}>{r}</option>)}
          </select>
        </label>
        <label className="wide">메모(선택) <textarea rows={3} value={memo} onChange={(e) => setMemo(e.target.value)} /></label>
      </div>
      {sub && <p className="muted small">현재 담당 {sub.sub_ticket.assigned_dept ?? "—"}. 고객 이관 안내 초안은 만들지 않습니다.</p>}
      {error && <p className="bad">! {error}</p>}
    </Modal>
  );
}
