// 칩 (principles §4). 목업 .chip(neg / crit / pos / info / out). 색만으로 뜻을 나누지 않도록 icon을 함께 쓴다(화면 정의서 v2 0-5).
import type { ReactNode } from "react";

export type Tone = "neu" | "neg" | "crit" | "pos" | "info" | "brand" | "outline";

export function Chip({ tone = "neu", icon, title, children }: { tone?: Tone; icon?: string; title?: string; children: ReactNode }) {
  return (
    <span className={tone === "neu" ? "ui-chip" : `ui-chip ui-chip--${tone}`} title={title}>
      {icon && <span className="ui-chip__icon" aria-hidden="true">{icon}</span>}
      {children}
    </span>
  );
}
