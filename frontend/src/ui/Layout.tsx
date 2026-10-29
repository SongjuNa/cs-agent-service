// 페이지 머리, 카드, 탭, 쪽 넘김 (principles §4). 목업 .page-head / .card / .card-h / .tabs / .tab / .pager.
import type { ReactNode } from "react";
import { Button } from "./Button";

export function PageHeader({ title, meta, actions }: { title: ReactNode; meta?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="ui-page-head">
      <h1 className="ui-page-head__title">{title}</h1>
      {meta && <span className="ui-page-head__meta">{meta}</span>}
      {actions && <div className="ui-page-head__actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children, padded = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; padded?: boolean }) {
  return (
    <section className="ui-card">
      {(title || actions) && (
        <div className="ui-card__head">
          {title && <h2 className="ui-card__title">{title}</h2>}
          {actions && <div className="ui-card__actions">{actions}</div>}
        </div>
      )}
      {padded ? <div className="ui-card__body">{children}</div> : children}
    </section>
  );
}

export interface TabItem {
  key: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

export function Tabs({ items, value, onChange, label }: { items: TabItem[]; value: string; onChange: (key: string) => void; label: string }) {
  return (
    <div className="ui-tabs" role="tablist" aria-label={label}>
      {items.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          className="ui-tab"
          aria-selected={t.key === value}
          disabled={t.disabled}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.count ? <span className="ui-tab__count">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

/** 쪽 넘김. page는 1부터(API page 파라미터와 같게) */
export function Pager({ total, page, size, onPage, unit = "건" }: { total: number; page: number; size: number; onPage: (page: number) => void; unit?: string }) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (total <= size) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(total, page * size);
  return (
    <nav className="ui-pager" aria-label="쪽 넘김">
      <span>{total}{unit} 중 {from}–{to}</span>
      <Button size="sm" onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="이전 쪽">‹</Button>
      <span>{page} / {pages}</span>
      <Button size="sm" onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="다음 쪽">›</Button>
    </nav>
  );
}
