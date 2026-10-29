// 칩 (principles §4). 목업 .chip(neg / crit / pos / info / out). neg·crit·pos는 목업처럼 앞에 점을 찍고, icon을 주면 점 대신 기호를 쓴다.
// 색만으로 뜻을 나누지 않도록 늘 글자(임박·지남 등)와 함께 쓴다(화면 정의서 v2 0-5).
import type { ReactNode } from "react";

export type Tone = "neu" | "neg" | "crit" | "pos" | "info" | "brand" | "outline";

export function Chip({ tone = "neu", icon, title, children }: { tone?: Tone; icon?: string; title?: string; children: ReactNode }) {
  return (
    <span className={[ "ui-chip", tone !== "neu" && `ui-chip--${tone}`, icon && "has-icon"].filter(Boolean).join(" ")} title={title}>
      {icon && <span className="ui-chip__icon" aria-hidden="true">{icon}</span>}
      {children}
    </span>
  );
}
