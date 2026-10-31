// 상태 배지와 같은 무리 (principles §4).
// 상태 이름은 목업 STATUS, 경고 이름은 목업 WARN, 색은 목업 v1.42 칩 색(조장 결정 2026-10-29)이고, 뜻 나눔(통과·임박·위반·대기)은 기술 명세서 §8-2와 같다.
import { Chip, type Tone } from "./Chip";

const STATUS: Record<string, { label: string; tone: Tone; icon?: string }> = {
  NEW: { label: "신규", tone: "outline" },
  IN_PROGRESS: { label: "처리 중", tone: "info" },
  WAITING_CUSTOMER: { label: "고객 회신 대기", tone: "neu", icon: "⏸" }, // 해결 시계 멈춤(CP-1)
  ESCALATED: { label: "이관됨", tone: "brand", icon: "→" },
  RESOLVED: { label: "해결", tone: "pos", icon: "✓" },
  CLOSED: { label: "종료", tone: "neu" },
};

/** 하위 문의 상태 6개 (CP-1, FR-025) */
export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: "neu" as Tone };
  return <Chip tone={s.tone} icon={s.icon} title={status}>{s.label}</Chip>;
}

const ALERT: Record<string, { label: string; tone: Tone; icon?: string }> = {
  FR_AT_RISK: { label: "1차 응답 임박", tone: "crit" },
  FR_BREACHED: { label: "1차 응답 지남", tone: "neg" },
  RES_AT_RISK: { label: "해결 기한 임박", tone: "crit" },
  RES_BREACHED: { label: "해결 기한 지남", tone: "neg" },
};

/** SLA 경고 칩 (FR-027) */
export function AlertChip({ alert }: { alert: string }) {
  const a = ALERT[alert] ?? { label: alert, tone: "crit" as Tone };
  return <Chip tone={a.tone} icon={a.icon} title={alert}>{a.label}</Chip>;
}

const SLA: Record<string, { label: string; tone: Tone; icon?: string }> = {
  ON_TRACK: { label: "정상", tone: "pos" },
  MET: { label: "충족", tone: "pos", icon: "✓" },
  AT_RISK: { label: "임박", tone: "crit" },
  BREACHED: { label: "위반", tone: "neg" },
  PAUSED: { label: "멈춤", tone: "neu", icon: "⏸" },
};

/** SLA 상태 (CP-2). N/A면 아무것도 그리지 않는다 */
export function SlaBadge({ status }: { status: string | null | undefined }) {
  if (!status || status === "N/A") return null;
  const s = SLA[status] ?? { label: status, tone: "neu" as Tone };
  return <Chip tone={s.tone} icon={s.icon} title={status}>{s.label}</Chip>;
}

/** 우선순위 P1~P4 (목업 .prio). 조정된 값이면 "(조정)"을 붙인다(FR-028) */
export function PriorityBadge({ priority, adjusted = false }: { priority: string | null | undefined; adjusted?: boolean }) {
  if (!priority) return <span className="ui-prio ui-prio--p4">—</span>;
  return (
    <span>
      <span className={`ui-prio ui-prio--${priority.toLowerCase()}`}>{priority}</span>
      {adjusted && <span className="ui-prio__adjusted">(조정)</span>}
    </span>
  );
}

/** 남은 시간 표시(FR-029 출력): "36.2h", 넘었으면 "−12.5h", 대기 중 "멈춤", 값 없음 "SLA 미정" */
/** 기한까지 남은(넘긴) 시간을 말로: "6일 10시간 초과", "2시간 남음", "37시간 12분 남음"(목업 fmtLeft) */
export function formatLeft(hours: number): string {
  const a = Math.abs(hours);
  const min = Math.round((a % 1) * 60) % 60;
  const span = a >= 48 ? `${Math.floor(a / 24)}일 ${Math.floor(a % 24)}시간` : a >= 1 ? `${Math.floor(a)}시간${min ? ` ${min}분` : ""}` : `${Math.max(1, Math.round(a * 60))}분`;
  return `${span} ${hours < 0 ? "초과" : "남음"}`;
}

export function formatRemaining(hours: number | null | undefined, paused = false): string {
  if (paused) return "멈춤";
  if (hours === null || hours === undefined) return "SLA 미정";
  const v = Math.round(hours * 10) / 10;
  return v < 0 ? `−${Math.abs(v).toFixed(1)}h` : `${v.toFixed(1)}h`;
}
