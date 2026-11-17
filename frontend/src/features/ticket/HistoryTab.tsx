// 탭 ④ 이력 (SCR-03 B-01·B-03, FR-035·025·027·028). 배치는 목업 v1.42 탭 "이력"(시각 | 종류 칩 | 내용 + 누가).
// "누가"는 계약에 공통 칸이 없어 종류별 칸에서 꺼낸다(화면 명세 "목업과 다른 곳" 마지막 줄).
import { api, ApiError, type TimelineItem } from "../../api";
import { ALERT, label, STATUS } from "../../app/labels";
import { useState } from "react";
import { useMailConfig } from "../../app/queries";
import { Banner, Button, Chip, type Tone } from "../../ui";
import { useRefresh, useTimeline } from "./ticketQuery";

const TYPE: Record<string, string> = {
  INQUIRY: "문의 접수", INFO_REQUEST: "정보 요청", FINAL_REPLY: "답변", PROGRESS_NOTICE: "진행 안내",
  CUSTOMER_REPLY: "고객 회신", ESCALATION_NOTE: "이관 메모",
};
const MSG_STATUS: Record<string, string> = { SENT: "발송", RECEIVED: "받음", DRAFT: "초안", APPROVED: "승인" };
const WHO: Record<string, string> = { SYSTEM: "시스템", CUSTOMER: "고객", AGENT: "상담원", DEPT: "부서" };

function line(item: TimelineItem): { chip: string; tone: Tone; text: string; who?: string } {
  switch (item.kind) {
    case "STATUS":
      return { chip: "상태", tone: "neu", text: `${label(STATUS, item.from_status as string)} → ${label(STATUS, item.to_status as string)} (${item.event_kind})`, who: WHO[String(item.changed_by)] ?? String(item.changed_by ?? "") };
    case "PRIORITY":
      return { chip: "조정", tone: "brand", text: `우선순위 ${item.from_priority} → ${item.to_priority}, SLA ${item.from_fr_target_h}/${item.from_res_target_h} h → ${item.to_fr_target_h}/${item.to_res_target_h} h (${item.reason})`, who: String(item.adjusted_by ?? "") };
    case "ASSIGNEE":
      return { chip: "담당", tone: "outline", text: `담당 변경 ${item.from_assignee ?? "없음"} → ${item.to_assignee}`, who: String(item.changed_by ?? "") };
    case "ALERT_RAISED":
      return { chip: "경고", tone: String(item.alert_type).endsWith("BREACHED") ? "neg" : "crit", text: `경고: ${label(ALERT, item.alert_type as string)}` };
    case "ALERT_CLEARED":
      return { chip: "경고", tone: "pos", text: `경고 해제: ${label(ALERT, item.alert_type as string)}` };
    default: {
      if (item.message_type === "ESCALATION_NOTE" && item.via_mail) {
        return item.message_status === "RECEIVED"
          ? { chip: "메일", tone: "info", text: "회신 메일 수신 (이관 부서가 메일로 답장)", who: String(item.sent_by_name ?? "") }
          : { chip: "메일", tone: "info", text: "이관 요청 메일 발송 (부서 메일함, 답장하면 이 문의에 연결)", who: String(item.sent_by_name ?? "") };
      }
      if (item.sender === "SYSTEM" && item.notice_transition === "REMINDER") return { chip: "메시지", tone: "info", text: "리마인드 자동 발송", who: "시스템" };
      const name = item.sent_by_name && item.sent_by_name !== item.sender ? String(item.sent_by_name) : WHO[String(item.sender)];
      return { chip: "메시지", tone: "info", text: `${TYPE[String(item.message_type)] ?? item.message_type} ${MSG_STATUS[String(item.message_status)] ?? ""}, ${item.language}${item.edited_yn ? ", 상담원 수정" : ""}`, who: name };
    }
  }
}

/** 부서가 메일로 답장하길 기다리는 하위 문의(seq → sub_ticket_id): 그 문의가 ESCALATED이고 마지막 이관 메모가 "메일로 보낸 것"일 때 */
function awaitingMail(items: TimelineItem[], escalated: Map<number, string>): Map<number, string> {
  const out = new Map<number, string>();
  for (const [seq, subId] of escalated) {
    const last = [...items].reverse().find((i) => i.kind === "MESSAGE" && i.message_type === "ESCALATION_NOTE" && i.seq === seq);
    if (last && last.message_status === "SENT" && last.via_mail) out.set(seq, subId);
  }
  return out;
}

/** 메일 연동이 켜졌을 때 부서 답장 시연에 넣는 처음 글(고쳐서 보낼 수 있다) */
const DEMO_REPLY = "확인했습니다. RMA-2026-0042를 발급했고, 교체품은 3주 뒤 출하 예정입니다.";

export function HistoryTab({ ticketId, canReply, onReply, escalated, onMailReply }: {
  ticketId: string; canReply: boolean; onReply: () => void;
  /** ESCALATED인 하위 문의(seq → sub_ticket_id)와 "회신 메일 도착(시연)" 실행 */
  escalated: Map<number, string>; onMailReply: (subTicketId: string) => void;
}) {
  const live = useMailConfig().data;
  const refresh = useRefresh(ticketId);
  const [demo, setDemo] = useState(DEMO_REPLY);
  const [mailNote, setMailNote] = useState<string | null>(null); // 메일 동작 결과 한 줄(add-escalation-mail-live)
  const [mailBusy, setMailBusy] = useState(false);

  async function mailAction(run: () => Promise<string>) {
    setMailBusy(true);
    try {
      setMailNote(await run());
    } catch (e) {
      setMailNote(e instanceof ApiError ? e.message : "메일 서버에 연결하지 못함");
    } finally {
      setMailBusy(false);
      void refresh();
    }
  }
  const poll = () => void mailAction(async () => {
    const r = await api.mailPoll();
    const mine = r.accepted.filter((a) => a.sub_ticket_id.startsWith(`${ticketId}-`)).length;
    return mine ? `부서 회신 메일 ${mine}건을 연결했습니다. AI가 회신을 근거로 초안을 다시 쓰는 중입니다.`
      : "아직 이 문의에 온 새 답장이 없습니다.";
  });
  const demoReply = (subId: string) => void mailAction(async () => {
    const r = await api.mailDemoReply(subId, demo.trim());
    return `${r.sender} → ${r.to} 답장을 보냈습니다. [지금 확인]을 누르거나 ${live?.poll_seconds ?? 30}초 기다리세요.`;
  });
  const timeline = useTimeline(ticketId, true);
  // 최근 것이 위(목업 .tl). 서버는 시각 오름차순으로 준다
  const items = [...(timeline.data ?? [])].reverse();
  const waitingMail = awaitingMail(timeline.data ?? [], escalated);
  return (
    <div className="tk-pane">
      <div className="tk-pane__bar">
        메시지, 상태 변경, 경고, 조정을 시각순으로
        <Button size="sm" disabled={!canReply} onClick={onReply}>고객 회신 입력</Button>
      </div>
      {[...waitingMail].map(([seq, subId]) => live?.enabled ? (
        <div key={subId} className="tk-mailwait" data-testid="mail-wait" data-live="true">
          <span>부서 메일함으로 이관 요청 메일을 보냈습니다{waitingMail.size > 1 ? ` (문의 ${seq})` : ""}. 부서가 답장하면 {live.poll_seconds}초 안에 이 문의에 자동으로 연결되고, AI가 회신을 근거로 초안을 다시 씁니다.</span>
          <a href={live.inbox_url} target="_blank" rel="noreferrer">메일함 열기</a>
          <Button size="sm" busy={mailBusy} onClick={poll}>지금 확인</Button>
          <details>
            <summary>부서 답장 보내기 (시연)</summary>
            <p className="tk-note">부서 메일 프로그램 대신 부서 메일함 주소로 실제 답장을 보냅니다. 연결은 다른 메일과 똑같이 받은 메일함 확인이 합니다.</p>
            <textarea aria-label="부서 답장 본문" rows={2} value={demo} onChange={(e) => setDemo(e.target.value)} />
            <Button size="sm" disabled={!demo.trim() || mailBusy} onClick={() => demoReply(subId)}>답장 보내기</Button>
          </details>
          {mailNote && <p className="tk-note" role="status" style={{ flexBasis: "100%" }}>{mailNote}</p>}
        </div>
      ) : (
        <div key={subId} className="tk-mailwait" data-testid="mail-wait">
          <span>부서 회신 메일을 기다리는 중입니다{waitingMail.size > 1 ? ` (문의 ${seq})` : ""}. 실제 메일은 연결되어 있지 않아, 부서가 메일로 답장한 것처럼 회신을 자동 반영해 볼 수 있습니다.</span>
          <Button size="sm" onClick={() => onMailReply(subId)}>회신 메일 도착 (시연)</Button>
        </div>
      ))}
      {timeline.isError && <Banner tone="neg">이력을 불러오지 못함. 새로고침</Banner>}
      {timeline.isPending ? <p className="tk-muted">읽는 중…</p> : (
        <ol className="tk-tl" data-testid="timeline">
          {items.map((item) => {
            const l = line(item);
            return (
              <li key={`${item.kind}-${item.id}`} data-kind={item.kind}>
                <span className="tk-tl__at">{item.at.replace("T", " ").slice(0, 16)}</span>
                <span><Chip tone={l.tone}>{l.chip}</Chip></span>
                <div>
                  {item.seq ? <Chip tone="outline">문의 {item.seq}</Chip> : null} {l.text}
                  {l.who && <span className="tk-tl__who">{l.who}</span>}
                  {item.kind === "MESSAGE" && typeof item.body === "string" && (
                    <details><summary>본문</summary><pre className="tk-text">{item.body}</pre></details>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
