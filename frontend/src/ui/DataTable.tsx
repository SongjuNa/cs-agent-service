// 표 (principles §4). 목업 table / th.sortable / td.r 와 화면 명세의 공통 상태(로딩·빈 목록·읽기 실패)를 한곳에 둔다.
import { Fragment, type ReactNode } from "react";
import { EmptyState } from "./Feedback";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  /** 서버 정렬 이름(예: "received_at"). 있으면 머리를 눌러 정렬한다 */
  sortKey?: string;
  align?: "left" | "right";
  wrap?: boolean;
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[] | undefined;
  rowKey: (row: Row) => string;
  onRowClick?: (row: Row) => void;
  /** "received_at" 오름차순, "-received_at" 내림차순, undefined = 서버 기본 */
  sort?: string;
  onSortChange?: (sort: string | undefined) => void;
  loading?: boolean;
  /** 읽기 실패 뒤 이전 값을 흐리게 보일 때 true */
  stale?: boolean;
  empty?: ReactNode;
  faded?: (row: Row) => boolean;
  /** 강조할 행(예: 「왜?」에서 연 규칙 행) */
  marked?: (row: Row) => boolean;
  caption?: string;
  /** 이전 행과 묶음이 바뀌는 행 앞에 묶음 머리 줄을 넣는다(없으면 null). 접수함 "내가 처리할 문의" 등 */
  groupHeader?: (row: Row, prev: Row | undefined) => ReactNode | null;
}

/** 머리를 누를 때마다 오름 → 내림 → 기본 순으로 바뀐다(화면 명세 SCR-02) */
export function nextSort(current: string | undefined, key: string): string | undefined {
  if (current === key) return `-${key}`;
  if (current === `-${key}`) return undefined;
  return key;
}

export function DataTable<Row>({
  columns, rows, rowKey, onRowClick, sort, onSortChange, loading = false, stale = false, empty, faded, marked, caption, groupHeader,
}: DataTableProps<Row>) {
  const arrow = (key?: string) => (key && sort === key ? " ▲" : key && sort === `-${key}` ? " ▼" : "");
  const ariaSort = (key?: string) => (key && sort === key ? "ascending" : key && sort === `-${key}` ? "descending" : undefined);

  if (!loading && rows && rows.length === 0) return <>{empty ?? <EmptyState title="표시할 항목이 없습니다" />}</>;
  return (
    <div className="ui-table-wrap">
      <table className={stale ? "ui-table ui-table--stale" : "ui-table"}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={[c.sortKey && onSortChange && "is-sortable", c.align === "right" && "is-right"].filter(Boolean).join(" ") || undefined}
                aria-sort={ariaSort(c.sortKey)}
                onClick={c.sortKey && onSortChange ? () => onSortChange(nextSort(sort, c.sortKey!)) : undefined}
              >
                {c.header}{arrow(c.sortKey)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && !rows
            ? Array.from({ length: 10 }, (_, i) => (
                <tr key={`sk-${i}`} aria-hidden="true">
                  {columns.map((c) => <td key={c.key}><span className="ui-skeleton" /></td>)}
                </tr>
              ))
            : (rows ?? []).map((row, i) => (
                <Fragment key={rowKey(row)}>
                {groupHeader?.(row, rows?.[i - 1]) != null && (
                  <tr className="ui-table__group"><td colSpan={columns.length}>{groupHeader(row, rows?.[i - 1])}</td></tr>
                )}
                <tr
                  className={[onRowClick && "is-link", faded?.(row) && "is-faded", marked?.(row) && "is-marked"].filter(Boolean).join(" ") || undefined}
                  aria-current={marked?.(row) ? "true" : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onKeyDown={onRowClick ? (e) => { if (e.key === "Enter") onRowClick(row); } : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={[c.align === "right" && "is-right", c.wrap && "is-wrap"].filter(Boolean).join(" ") || undefined}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
                </Fragment>
              ))}
        </tbody>
      </table>
    </div>
  );
}
