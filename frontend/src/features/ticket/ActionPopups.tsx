// 팝업 P3 우선순위 조정, P4 이관, P6 고객 회신 입력 (화면 정의서 v1 SCR-03-P3·P4·P6, FR-028, FR-033, FR-032).
import { useEffect, useState } from "react";
import { api, ApiError, type AdjustPreview, type SubTicket } from "../../api";
import { CATEGORY, label } from "../../app/labels";
import { useDepartments } from "../../app/queries";
import { Banner, Button, Field, Modal } from "../../ui";

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
    let current = true; // 우선순위를 빨리 바꾸면 앞 요청의 답이 늦게 올 수 있다. 마지막 고른 값의 답만 쓴다
    setPreview(null);
    api.adjustPreview(id, priority).then((p) => current && setPreview(p))
      .catch((e) => current && setError(errorText(e, "미리 보기 실패")));
    return () => { current = false; };
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
    <Modal title={`우선순위 조정, 문의 ${sub.sub_ticket.seq}`} onClose={onClose} locked={busy}
           footer={<><Button onClick={onClose}>취소</Button><Button variant="primary" busy={busy} onClick={() => void submit()}>조정</Button></>}>
      <div className="tk-form">
        <Field label="새 우선순위" required hint={`현재 ${current ?? "—"}`}>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.filter((p) => p !== current).map((p) => <option key={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="사유 분류" required>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">고르세요</option>
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <div className="is-wide"><Field label="사유" required><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} /></Field></div>
      </div>
      {preview && (
        <p data-testid="adjust-preview">
          SLA 목표 {preview.from_fr_target_h ?? "?"}/{preview.from_res_target_h ?? "?"} h → {preview.to_fr_target_h ?? "?"}/{preview.to_res_target_h ?? "?"} h
          {preview.to_sla_id && <span className="tk-muted"> ({preview.to_sla_id})</span>}
        </p>
      )}
      {preview?.becomes_breached && <Banner tone="crit">이 조정으로 SLA 위반 상태가 됩니다. 계속할까요?</Banner>}
      {error && <Banner tone="neg">{error}</Banner>}
    </Modal>
  );
}

export function ReplyPopup({ ticketId, language, subs, sentAt, onDone, onClose }: {
  ticketId: string; language: string; subs: SubTicket[]; sentAt: string | null; onDone: () => void; onClose: () => void;
}) {
  const waiting = subs.filter((s) => s.sub_ticket.status === "WAITING_CUSTOMER");
  const [body, setBody] = useState("");
  const [lang, setLang] = useState(language);
  const [at, setAt] = useState("");
  const [targets, setTargets] = useState<string[]>(waiting.map((s) => s.sub_ticket.sub_ticket_id));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!body.trim()) { setError("회신 내용을 입력하세요"); return; } // SCR-03 입력 검증 P6 본문
    const when = at ? new Date(`${at}Z`) : null;
    if (when && sentAt && when < new Date(sentAt)) { setError("회신 시각은 요청 발송 이후여야 합니다"); return; }
    if (when && when > new Date()) { setError("회신 시각은 지금보다 뒤일 수 없습니다"); return; }
    setBusy(true);
    try {
      await api.reply(ticketId, { body, language: lang, received_at: when ? when.toISOString() : null,
                                  target_sub_ticket_ids: waiting.length > 1 ? targets : null });
      onDone();
    } catch (e) {
      setError(errorText(e, "회신 입력 실패"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="고객 회신 입력" onClose={onClose} wide locked={busy}
           footer={<><Button onClick={onClose}>취소</Button><Button variant="primary" busy={busy} onClick={() => void submit()}>입력</Button></>}>
      <div className="tk-form">
        <div className="is-wide">
          <Field label="회신 본문" required hint={`${body.length}/2,000자`}>
            <textarea rows={6} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
          </Field>
        </div>
        <Field label="회신 언어"><input value={lang} onChange={(e) => setLang(e.target.value)} /></Field>
        <Field label="회신 시각(UTC)" hint="비우면 지금"><input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></Field>
        {waiting.length > 1 && (
          <fieldset className="is-wide">
            <legend>대상 문의</legend>
            {waiting.map((s) => {
              const sid = s.sub_ticket.sub_ticket_id;
              return (
                <label key={sid}>
                  <input type="checkbox" checked={targets.includes(sid)}
                         onChange={(e) => setTargets(e.target.checked ? [...targets, sid] : targets.filter((t) => t !== sid))} />
                  {" "}문의 {s.sub_ticket.seq}: {label(CATEGORY, s.sub_ticket.category_code)}
                </label>
              );
            })}
          </fieldset>
        )}
      </div>
      {error && <Banner tone="neg">{error}</Banner>}
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
  const [mail, setMail] = useState(true); // 최신 목업: 이관 요청을 메일로도 보내기(처음부터 켜짐)
  const depts = useDepartments();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const deptName = depts.data?.find((d) => d.dept_code === dept)?.dept_name_ko ?? dept;
  const subject = `[${subId.replace(/-\d+$/, "")}] 이관 요청 · ${reason || "사유 선택 전"}`;

  function pick(id: string) {
    const c = open.find((s) => s.sub_ticket.sub_ticket_id === id)?.escalation?.escalation_candidates[0];
    setSubId(id); setDept(c?.dept ?? ""); setReason(c?.reason_code ?? ""); setError(null);
  }

  async function submit() {
    if (!sub) return;
    if (!reason) { setError("이관 사유를 고르세요"); return; } // FR-033 예외 1행
    setBusy(true);
    try {
      await api.escalate(subId, { dept, reason_code: reason, memo: memo.trim(), expected_version: sub.version, send_mail: mail });
      onDone();
    } catch (e) {
      setError(errorText(e, "이관 실패"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="이관" onClose={onClose} locked={busy}
           footer={<><Button onClick={onClose}>취소</Button><Button variant="primary" busy={busy} disabled={!sub} onClick={() => void submit()}>이관</Button></>}>
      <div className="tk-form">
        {open.length > 1 && (
          <div className="is-wide">
            <Field label="문의">
              <select value={subId} onChange={(e) => pick(e.target.value)}>
                {open.map((s) => <option key={s.sub_ticket.sub_ticket_id} value={s.sub_ticket.sub_ticket_id}>
                  문의 {s.sub_ticket.seq}: {label(CATEGORY, s.sub_ticket.category_code)}</option>)}
              </select>
            </Field>
          </div>
        )}
        <Field label="이관 부서" required>
          <select value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">고르세요</option>
            {(depts.data ?? []).map((d) => <option key={d.dept_code} value={d.dept_code}>{d.dept_name_ko} ({d.dept_code}){d.dept_code === top?.dept ? ", 이관 후보" : ""}</option>)}
          </select>
        </Field>
        <Field label="이관 사유" required>
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">고르세요</option>
            {ESCALATION_REASONS.map((r) => <option key={r}>{r}</option>)}
          </select>
        </Field>
        <div className="is-wide"><Field label="메모" hint="선택"><textarea rows={3} value={memo} onChange={(e) => setMemo(e.target.value)} /></Field></div>
      </div>
      <div className="tk-mailbox" data-testid="mail-box">
        <label className="tk-mailbox__h"><input type="checkbox" checked={mail} onChange={(e) => setMail(e.target.checked)} />이관 요청을 메일로도 보내기</label>
        <p className="tk-note">이관 부서는 이 시스템을 열지 않아도 됩니다. 부서가 메일에 답장하면 회신이 이 문의에 자동으로 연결되어, 따로 입력하지 않아도 됩니다.</p>
        {mail && (
          <dl className="tk-mailbox__prev">
            <div><dt>받는 곳</dt><dd>{dept ? `${deptName} 담당 메일함` : "이관 부서를 고르세요"}</dd></div>
            <div><dt>제목</dt><dd>{subject}</dd></div>
            <div><dt>내용</dt><dd>{memo.trim() || <span className="tk-muted">메모를 쓰면 여기에 들어갑니다</span>}<span className="tk-note"> 문의 요약과 원문, 회신 방법이 함께 들어갑니다</span></dd></div>
          </dl>
        )}
        <p className="tk-note">메일 연동은 화면 예시입니다. 실제 발송과 회신 인식은 아직 연결되어 있지 않습니다.</p>
      </div>
      {sub && <p className="tk-note">현재 담당 {sub.sub_ticket.assigned_dept ?? "—"}. 고객 이관 안내 초안은 만들지 않습니다.</p>}
      {error && <Banner tone="neg">{error}</Banner>}
    </Modal>
  );
}
