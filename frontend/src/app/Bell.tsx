// 종 알림 (SCR-00-07, FR-027). GET /me/workload의 risks를 1차 응답 경고 먼저, 그다음 남은 시간 오름차순으로 12건까지.
// 읽음 표시는 이 화면 안에서만 기억한다(명세 "브라우저에만". 저장소에는 두지 않는다, principles §4).
import { useEffect, useRef, useState } from "react";
import type { WorkRow } from "../api";
import { Chip, formatRemaining } from "../ui";
import { Icon } from "./icons";
import { ALERT, label } from "./labels";
import { useWorkload } from "./queries";
import { useSession } from "./session";

const MAX = 12;
const isFirstResponse = (a: string) => a.startsWith("FR_");

export interface BellItem { key: string; row: WorkRow & { alerts: string[]; remaining_h: number | null }; alert: string }

/** 경고 하나에 한 줄. 1차 응답 경고 → 해결 경고, 같은 묶음 안에서는 남은 시간 오름차순 (SCR-00-AC-4) */
export function bellItems(risks: { alerts: string[]; remaining_h: number | null; sub_ticket_id: string }[]): BellItem[] {
  const items = risks.flatMap((r) => r.alerts.map((alert) => ({ key: `${r.sub_ticket_id}|${alert}`, row: r as BellItem["row"], alert })));
  const rem = (i: BellItem) => (i.row.remaining_h === null ? Number.POSITIVE_INFINITY : Number(i.row.remaining_h));
  items.sort((a, b) => Number(isFirstResponse(b.alert)) - Number(isFirstResponse(a.alert)) || rem(a) - rem(b));
  return items.slice(0, MAX);
}

export function Bell({ onOpen }: { onOpen: (ticketId: string) => void }) {
  const { dept, agent, asOf } = useSession();
  const workload = useWorkload(dept, agent, asOf);
  const [open, setOpen] = useState(false);
  const [read, setRead] = useState<Set<string>>(new Set());
  const box = useRef<HTMLDivElement>(null);

  const items = workload.data ? bellItems(workload.data.risks as BellItem["row"][]) : [];
  const unread = items.filter((i) => !read.has(i.key)).length;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  function toggle() {
    if (!open) setRead((prev) => new Set([...prev, ...items.map((i) => i.key)])); // 펼친 알림은 읽음
    setOpen(!open);
  }

  return (
    <div className="shell-pop-anchor" ref={box}>
      <button type="button" className="shell-icon-btn" aria-label={`알림${unread ? ` ${unread}건` : ""}`} aria-expanded={open} onClick={toggle}>
        <Icon name="bell" />
        {!workload.isError && unread > 0 && <span className="shell-bell-badge">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <div className="shell-pop" role="dialog" aria-label="알림">
          <h4>알림</h4>
          {workload.isError ? <div className="shell-pop__empty">알림을 불러오지 못함</div>
            : !dept ? <div className="shell-pop__empty">상단에서 부서를 고르세요</div>
            : items.length === 0 ? <div className="shell-pop__empty">새 알림이 없습니다</div>
            : (
              <div className="shell-pop__group" data-testid="bell-list">
                {items.map((i) => (
                  <a key={i.key} className="shell-pop__item" href={`/tickets/${encodeURIComponent(i.row.ticket_id)}`}
                     data-alert={i.alert}
                     onClick={(e) => { e.preventDefault(); setOpen(false); onOpen(i.row.ticket_id); }}>
                    <Chip tone={i.alert.endsWith("BREACHED") ? "neg" : "crit"}>{label(ALERT, i.alert)}</Chip>{" "}
                    <span className="shell-mono">{i.row.ticket_id}{i.row.inquiry_count > 1 ? ` #${i.row.seq}` : ""}</span>
                    <div className="shell-pop__sub">
                      {i.row.company_masked ?? "—"}, {i.row.priority ?? "—"}, 해결 남은 시간 {formatRemaining(i.row.remaining_h, i.row.status === "WAITING_CUSTOMER")}
                    </div>
                  </a>
                ))}
              </div>
            )}
        </div>
      )}
    </div>
  );
}
