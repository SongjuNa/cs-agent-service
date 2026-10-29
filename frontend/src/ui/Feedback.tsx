// 안내 띠, 빈 상태, 입력 칸 (principles §4·§6). 목업 .strip / .empty-state / .field.
import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";
import { Chip } from "./Chip";

export type BannerTone = "neg" | "crit" | "info" | "neu";

/** 화면 위 안내 띠. 읽기 실패 띠는 tone="neg" + action에 [새로고침] */
export function Banner({ tone = "info", title, children, action }: { tone?: BannerTone; title?: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`ui-banner ui-banner--${tone}`} role={tone === "neg" ? "alert" : "status"}>
      {title && <b>{title}</b>}
      <span className="ui-banner__body">{children}</span>
      {action}
    </div>
  );
}

export function EmptyState({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <div className="ui-empty">
      <b className="ui-empty__title">{title}</b>
      {children}
    </div>
  );
}

export interface FieldProps {
  label: string;
  required?: boolean;
  hint?: ReactNode;
  /** 서버 오류 문구(400 detail.errors[].message)나 화면 검사 문구 */
  error?: string | null;
  /** input, select, textarea 하나 */
  children: ReactElement;
}

export function Field({ label, required = false, hint, error, children }: FieldProps) {
  const id = useId();
  const errId = `${id}-err`;
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": error ? errId : undefined,
      })
    : children;
  return (
    <div className={error ? "ui-field is-invalid" : "ui-field"}>
      <label className="ui-field__label" htmlFor={id}>
        {label}
        {required && <Chip tone="neg">필수</Chip>}
      </label>
      {control}
      {hint && !error && <span className="ui-field__hint">{hint}</span>}
      {error && <span className="ui-field__error" id={errId}>{error}</span>}
    </div>
  );
}
