// 버튼 (principles §4). 목업 .btn / .btn.primary / .btn.ghost / .btn.sm / .btn.danger.
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "default" | "primary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  /** 요청을 보내는 중이면 누를 수 없게 하고 글자 뒤에 "…"를 붙인다 */
  busy?: boolean;
}

export function Button({ variant = "default", size = "md", busy = false, disabled, className, children, type, ...rest }: ButtonProps) {
  const cls = ["ui-btn", variant !== "default" && `ui-btn--${variant}`, size === "sm" && "ui-btn--sm", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button {...rest} type={type ?? "button"} className={cls} disabled={disabled || busy} aria-busy={busy || undefined}>
      {children}
      {busy && "…"}
    </button>
  );
}
