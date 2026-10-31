// "AI 판단" 칩 줄 (변경 add-ticket-look, 최신 목업 .ai-chips). 같은 값이 아래 "시스템이 판단한 것"에 근거와 함께 있고,
// 칩을 누르면 그 줄로 이동한다. 값은 서버가 준 것을 그대로 보인다(새로 계산하지 않는다).
import { useState } from "react";
import type { Detail } from "../../api";
import { CATEGORY, label, URGENCY } from "../../app/labels";
import { useDepartments } from "../../app/queries";
import { Icon } from "../../app/icons";
import { PriorityBadge } from "../../ui";
import { repOf } from "./HeadCard";

export function AiChips({ detail, onJump }: { detail: Detail; onJump: (rowId: string) => void }) {
  const depts = useDepartments();
  const [more, setMore] = useState(false);
  const rep = repOf(detail);
  if (!rep || detail.processing) return null;
  const st = rep.sub_ticket;
  const items = rep.evidence_rows.find((r) => r.id === "C-07")?.items ?? [];
  const got = items.filter((i) => i.state === "provided").length;
  const blocking = items.some((i) => i.state === "blocking");
  const deptName = depts.data?.find((d) => d.dept_code === st.assigned_dept)?.dept_name_ko ?? st.assigned_dept;
  const urgent = st.urgency_flag === "SAFETY" || st.urgency_flag === "SITE_DOWN";
  const chip = (key: string, name: string, value: React.ReactNode, tone: "line" | "warn" | "bad" | "ok", row?: string) => (
    <button key={key} type="button" className={`tk-aichip tk-aichip--${tone}`} data-chip={key} disabled={!row} onClick={() => row && onJump(row)}>
      <span>{name}</span><b>{value}</b>
    </button>
  );
  return (
    <div className="tk-aichips" data-testid="ai-chips" aria-label="AI 판단">
      <span className="tk-aichips__cap" title="AI Agent가 정한 값입니다(우선순위·부서·기한은 규칙표, 유형·긴급도는 AI). 누르면 아래 근거 줄로 이동합니다">AI 판단</span>
      {chip("priority", "우선순위", <PriorityBadge priority={st.priority} adjusted={rep.adjustments.length > 0} />, "line", "C-03")}
      {chip("category", "유형", label(CATEGORY, st.category_code), "line", "C-01")}
      {chip("urgency", "긴급도", label(URGENCY, st.urgency_flag), urgent ? "bad" : "line", "C-02")}
      {chip("required", "필수 정보", items.length ? `${got}/${items.length}` : "해당 없음", items.length && (blocking || got < items.length) ? "warn" : "ok", items.length ? "C-07" : undefined)}
      {more && <>
        {chip("dept", "담당", deptName ?? "—", "line")}
        {chip("sla", "기한", rep.sla?.res_target_h ? `해결 ${rep.sla.res_target_h}h` : "미정", "line")}
      </>}
      <button type="button" className="tk-aichips__more" aria-expanded={more} onClick={() => setMore(!more)}>
        {more ? "접기" : "더보기"}<Icon name="chev" className={more ? "tk-aichips__chev is-open" : "tk-aichips__chev"} />
      </button>
    </div>
  );
}
