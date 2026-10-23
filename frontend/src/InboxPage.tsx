// SCR-02 접수함 (화면 정의서 v1, 명세서 FR-029). 필터·정렬·쪽은 주소 쿼리에 둬 상세에서 돌아와도 그대로다.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Inbox, type InboxRow } from "./api";

const STATUSES = ["NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"];
const PRIORITIES = ["P1", "P2", "P3", "P4"];
const ALERTS = ["FR_AT_RISK", "FR_BREACHED", "RES_AT_RISK", "RES_BREACHED"];
const CHANNELS = ["EMAIL", "CHAT", "PHONE", "WEB_FORM", "PARTNER_PORTAL"];
const LISTS = ["status", "priority", "alert", "channel"] as const;
const CHECKS = [["needs_info", "정보 요청 필요"], ["has_draft", "승인 대기 초안 있음"], ["composite", "복합 문의"]] as const;
const REFRESH_MS = 5 * 60 * 1000; // FR-029 처리 6
const SIZE = 50; // FR-029 처리 7
const FAIL = "목록을 불러오지 못함. 새로고침"; // FR-029 예외 4행

// 상태 배지: 화면 정의서 v2 부록 B-3 색 + 기호(색만으로 뜻을 나누지 않는다)
const STATUS_BADGE: Record<string, { cls: string; mark: string }> = {
  NEW: { cls: "st-new", mark: "○" },
  IN_PROGRESS: { cls: "st-progress", mark: "▶" },
  WAITING_CUSTOMER: { cls: "st-waiting", mark: "⏸" },
  ESCALATED: { cls: "st-escalated", mark: "↗" },
  RESOLVED: { cls: "st-resolved", mark: "✓" },
  CLOSED: { cls: "st-closed", mark: "■" },
};

const ALERT_LABEL: Record<string, { text: string; cls: string }> = {
  FR_AT_RISK: { text: "⚠ 1차 위험", cls: "gold" },
  FR_BREACHED: { text: "! 1차 위반", cls: "bad" },
  RES_AT_RISK: { text: "⚠ 해결 위험", cls: "gold" },
  RES_BREACHED: { text: "! 해결 위반", cls: "bad" },
};

// 채널 아이콘 + 코드(SCR-02 열 3)
const CHANNEL_ICON: Record<string, string> = { EMAIL: "✉", CHAT: "💬", PHONE: "☎", WEB_FORM: "🗎", PARTNER_PORTAL: "⇄" };

const SORTABLE: Record<string, string> = {
  ticket_id: "문의 번호", received_at: "접수 시각", priority: "우선순위", status: "상태", remaining: "해결 남은 시간",
};

function remaining(row: InboxRow): { text: string; cls: string } {
  // 해결 남은 시간(FR-029 처리 2·5, 예외 3행, SCR-02 열 11)
  const h = row.remaining_h === null ? null : Number(row.remaining_h);
  if (row.res_status === "MET") return { text: "✓ MET", cls: "ok" };
  if (row.res_status === "N/A") return { text: "N/A", cls: "gray" };
  if (row.res_status === null || h === null) return { text: "SLA 미정", cls: "gray" };
  const value = `${h < 0 ? "−" : ""}${Math.abs(h).toFixed(1)}h`;
  const cls = row.res_status === "BREACHED" ? "bad" : row.res_status === "AT_RISK" ? "gold" : "ok";
  if (row.status === "WAITING_CUSTOMER") return { text: `⏸ 멈춤 ${value}`, cls: "gray" };
  return { text: `${row.res_status === "BREACHED" ? "! " : row.res_status === "AT_RISK" ? "⚠ " : ""}${value}`, cls };
}

function statusCell(row: InboxRow) {
  const badge = STATUS_BADGE[row.status] ?? { cls: "", mark: "" };
  return (
    <>
      <span className={`badge ${badge.cls}`}>{badge.mark} {row.status}</span>
      {row.escalated_in_from ? <div className="small">{row.escalated_in_from}에서 이관됨</div>
        : row.status === "ESCALATED" && row.escalated_to ? <div className="small">→ {row.escalated_to}</div> : null}
    </>
  );
}

/** 주소 쿼리 → GET /tickets 쿼리(부서·기준 시각을 더한다) */
function requestQuery(search: URLSearchParams, dept: string, asOf: string | null): URLSearchParams {
  const q = new URLSearchParams(search);
  q.set("dept", dept);
  q.set("size", String(SIZE));
  if (asOf) q.set("as_of", asOf);
  return q;
}

export function InboxPage({ dept, asOf, onOpen }: { dept: string; asOf: string | null; onOpen: (id: string) => void }) {
  const [search, setSearch] = useState(() => new URLSearchParams(window.location.search));
  const [data, setData] = useState<Inbox | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [text, setText] = useState(search.get("q") ?? "");

  const load = useCallback(async () => {
    if (!dept) return;
    setLoading(true);
    try {
      setData(await api.inbox(requestQuery(search, dept, asOf)));
      setFailed(null);
    } catch (e) {
      setFailed(e instanceof ApiError && e.status !== 500 ? `${FAIL} (${e.message})` : FAIL);
    } finally {
      setLoading(false);
    }
  }, [search, dept, asOf]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);
  useEffect(() => {
    const onPop = () => setSearch(new URLSearchParams(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function update(change: (q: URLSearchParams) => void, keepPage = false) {
    const q = new URLSearchParams(search);
    change(q);
    if (!keepPage) q.delete("page");
    const qs = q.toString();
    window.history.replaceState(null, "", `/inbox${qs ? `?${qs}` : ""}`);
    setSearch(q);
  }

  function toggle(name: string, value: string) {
    update((q) => {
      const values = new Set((q.get(name) ?? "").split(",").filter(Boolean));
      if (values.has(value)) values.delete(value); else values.add(value);
      if (values.size) q.set(name, [...values].join(",")); else q.delete(name);
    });
  }

  function flag(name: string, on: boolean) {
    update((q) => { if (on) q.set(name, "true"); else q.delete(name); });
  }

  function sortBy(key: string) {
    update((q) => q.set("sort", q.get("sort") === key ? `-${key}` : key));
  }

  if (!dept) return <p className="muted page-msg">부서를 선택하세요</p>;

  const counts = data?.counts;
  const page = Number(search.get("page") ?? "1");
  const pages = counts ? Math.max(1, Math.ceil(counts.total / SIZE)) : 1;
  const sort = search.get("sort") ?? "";
  const chosen = (name: string) => new Set((search.get(name) ?? "").split(",").filter(Boolean));

  return (
    <section className="inbox">
      <div className="intake-head">
        <h2>접수함 · {dept}</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>새로고침</button>
        {data && <span className="muted small">기준 {data.as_of.replace("T", " ").slice(0, 16)} UTC</span>}
      </div>

      {counts && (
        <div className="counts" aria-label="건수 요약">
          <span>전체 <b>{counts.total}</b></span>
          <span className="bad">경고 <b>{counts.alert}</b></span>
          <span>정보 요청 필요 <b>{counts.needs_info}</b></span>
          <span>승인 대기 <b>{counts.has_draft}</b></span>
          <span>회신 대기 <b>{counts.waiting}</b></span>
        </div>
      )}

      <div className="filters">
        {LISTS.map((name) => (
          <div key={name} className="filter-row">
            <span className="muted">{{ status: "상태", priority: "우선순위", alert: "경고", channel: "채널" }[name]}</span>
            {({ status: STATUSES, priority: PRIORITIES, alert: ALERTS, channel: CHANNELS }[name]).map((v) => (
              // 종료 상태 칩은 "종료 포함"이 켜져야 쓸 수 있다(FR-029 처리 1, C-105)
              <button key={v} type="button" className={`chip ${chosen(name).has(v) ? "on" : ""}`}
                      disabled={name === "status" && (v === "RESOLVED" || v === "CLOSED") && search.get("include_closed") !== "true"}
                      aria-pressed={chosen(name).has(v)} onClick={() => toggle(name, v)}>{v}</button>
            ))}
          </div>
        ))}
        <div className="filter-row">
          {CHECKS.map(([name, label]) => (
            <label key={name}>
              <input type="checkbox" checked={search.get(name) === "true"} onChange={(e) => flag(name, e.target.checked)} />
              {label}
            </label>
          ))}
          <label>
            <input type="checkbox" checked={search.get("include_closed") === "true"}
                   onChange={(e) => update((q) => {
                     if (e.target.checked) { q.set("include_closed", "true"); return; }
                     q.delete("include_closed");
                     const open = (q.get("status") ?? "").split(",").filter((v) => v && v !== "RESOLVED" && v !== "CLOSED");
                     if (open.length) q.set("status", open.join(",")); else q.delete("status");
                   })} />
            종료 포함
          </label>
          <form onSubmit={(e) => { e.preventDefault(); update((q) => { if (text.trim()) q.set("q", text.trim()); else q.delete("q"); }); }}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="문의 번호 또는 고객사" />
            <button type="submit">검색</button>
          </form>
        </div>
      </div>

      {failed && (
        <p className="bad">
          {failed} <button type="button" onClick={() => void load()}>새로고침</button>
        </p>
      )}
      {!data && loading && <p className="muted">불러오는 중…</p>}
      {data && (
        <div className={`table-wrap ${failed ? "stale" : ""}`}>
          <table className="inbox-table">
            <thead>
              <tr>
                {["ticket_id", "received_at", null, null, null, null, null, "priority", "status", "remaining", null, null].map((key, i) => {
                  const label = key ? SORTABLE[key]
                    : ["", "", "채널", "고객사·등급", "제품", "유형", "긴급도", "", "", "", "경고", "표시"][i];
                  if (!key) return <th key={i}>{label}</th>;
                  const mark = sort === key ? " ▲" : sort === `-${key}` ? " ▼" : "";
                  return (
                    <th key={i} aria-sort={sort === key ? "ascending" : sort === `-${key}` ? "descending" : "none"}>
                      <button type="button" className="link" onClick={() => sortBy(key)}>{label}{mark}</button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => {
                const left = remaining(row);
                const closed = row.status === "RESOLVED" || row.status === "CLOSED";
                return (
                  <tr key={row.sub_ticket_id} className={closed ? "closed" : ""} tabIndex={0}
                      onClick={() => onOpen(row.ticket_id)} onKeyDown={(e) => { if (e.key === "Enter") onOpen(row.ticket_id); }}>
                    <td>
                      {row.ticket_id}
                      {row.inquiry_count > 1 && <div className="small muted">복합 {row.inquiry_count}건 중 {row.seq}</div>}
                    </td>
                    <td>{row.received_at_utc.replace("T", " ").slice(0, 16)}</td>
                    <td><span aria-hidden="true">{CHANNEL_ICON[row.channel] ?? ""}</span> {row.channel}</td>
                    <td>{row.company_masked} {row.customer_tier && <span className="chip">{row.customer_tier}</span>}</td>
                    <td title={row.product_name ?? undefined}>{row.product_code ?? "—"}</td>
                    <td>
                      {row.category_code ?? "—"}
                      {row.inquiry_count > 1 && <span className="muted"> (복합 {row.inquiry_count}건 중 {row.seq})</span>}
                    </td>
                    <td className={row.urgency_flag === "SAFETY" || row.urgency_flag === "SITE_DOWN" ? "bad" : ""}>
                      {row.urgency_flag ?? "—"}
                    </td>
                    <td>
                      {row.priority ? <span className="badge">{row.priority}{row.priority_adjusted && " (조정)"}</span> : "—"}
                    </td>
                    <td>{statusCell(row)}</td>
                    <td className={left.cls}>{left.text}</td>
                    <td>
                      {row.alerts.map((a) => (
                        <span key={a} className={`chip ${ALERT_LABEL[a]?.cls ?? ""}`}>{ALERT_LABEL[a]?.text ?? a}</span>
                      ))}
                    </td>
                    <td>
                      {row.needs_info && <span className="chip bad">? 정보 요청 필요</span>}
                      {row.has_unsent_draft && <span className="chip ai">✎ 승인 대기</span>}
                      {row.reminder_sent && row.status === "WAITING_CUSTOMER" && <span className="chip gray">↻ 리마인드 발송됨</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {data.message && <p className="muted page-msg">{data.message}</p>}
          {!data.message && data.rows.length === 0 && page > 1 && (
            <p className="muted page-msg">
              이 쪽에는 줄이 없습니다. <button type="button" className="link" onClick={() => update(() => undefined)}>첫 쪽으로</button>
            </p>
          )}
          <div className="pager">
            <button type="button" disabled={page <= 1} onClick={() => update((q) => q.set("page", String(page - 1)), true)}>이전</button>
            <span>{page} / {pages}</span>
            <button type="button" disabled={page >= pages} onClick={() => update((q) => q.set("page", String(page + 1)), true)}>다음</button>
          </div>
        </div>
      )}
    </section>
  );
}
