// 탭 ④ 이력 (SCR-03 B-01·B-03, FR-035·025·027·028). 배치는 목업 v1.42 탭 "이력"(시각 | 종류 칩 | 내용 + 누가).
// "누가"는 계약에 공통 칸이 없어 종류별 칸에서 꺼낸다(화면 명세 "목업과 다른 곳" 마지막 줄).
import type { TimelineItem } from "../../api";
import { ALERT, label, STATUS } from "../../app/labels";
import { Banner, Button, Chip, type Tone } from "../../ui";
import { useTimeline } from "./ticketQuery";

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
      if (item.sender === "SYSTEM" && item.notice_transition === "REMINDER") return { chip: "메시지", tone: "info", text: "리마인드 자동 발송", who: "시스템" };
      const name = item.sent_by_name && item.sent_by_name !== item.sender ? String(item.sent_by_name) : WHO[String(item.sender)];
      return { chip: "메시지", tone: "info", text: `${TYPE[String(item.message_type)] ?? item.message_type} ${MSG_STATUS[String(item.message_status)] ?? ""}, ${item.language}${item.edited_yn ? ", 상담원 수정" : ""}`, who: name };
    }
  }
}

export function HistoryTab({ ticketId, canReply, onReply }: { ticketId: string; canReply: boolean; onReply: () => void }) {
  const timeline = useTimeline(ticketId, true);
  // 최근 것이 위(목업 .tl). 서버는 시각 오름차순으로 준다
  const items = [...(timeline.data ?? [])].reverse();
  return (
    <div className="tk-pane">
      <div className="tk-pane__bar">
        메시지, 상태 변경, 경고, 조정을 시각순으로
        <Button size="sm" disabled={!canReply} onClick={onReply}>고객 회신 입력</Button>
      </div>
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
