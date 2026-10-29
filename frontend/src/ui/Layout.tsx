// 페이지 머리, 카드, 탭, 쪽 넘김 (principles §4). 목업 .page-head / .card / .card-h / .tabs / .tab / .pager.
import type { ReactNode } from "react";

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

/** variant="line" = 밑줄 탭(목업 문의 상세 .tabs), "seg" = 칸막이 탭(목업 접수함 .summary) */
export function Tabs({ items, value, onChange, label, variant = "line" }: { items: TabItem[]; value: string; onChange: (key: string) => void; label: string; variant?: "line" | "seg" }) {
  return (
    <div className={variant === "seg" ? "ui-tabs ui-tabs--seg" : "ui-tabs"} role="tablist" aria-label={label}>
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

/** 쪽 넘김. page는 1부터(API page 파라미터와 같게). 목업 numPager: 첫·끝 쪽과 지금 쪽 ±2만 번호, 사이는 … */
export function Pager({ total, page, size, onPage, unit = "건" }: { total: number; page: number; size: number; onPage: (page: number) => void; unit?: string }) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (total === 0) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(total, page * size);
  const nums: (number | "gap")[] = [];
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - page) <= 2) nums.push(p);
    else if (nums[nums.length - 1] !== "gap") nums.push("gap");
  }
  return (
    <nav className="ui-pager" aria-label="쪽 넘김">
      <span>{total}{unit} 중 {from}–{to}</span>
      {pages > 1 && (
        <span className="ui-pager__nums">
          <button type="button" onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="이전 쪽">‹</button>
          {nums.map((n, i) => n === "gap"
            ? <span key={`g${i}`} className="ui-pager__gap">…</span>
            : <button key={n} type="button" aria-current={n === page ? "page" : undefined} onClick={() => onPage(n)}>{n}</button>)}
          <button type="button" onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="다음 쪽">›</button>
        </span>
      )}
    </nav>
  );
}
