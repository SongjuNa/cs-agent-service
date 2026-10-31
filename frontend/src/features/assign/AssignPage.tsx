// SCR-11 문의 배정 관리 (최신 목업 `#/admin/assign`). 부서·담당 상담원·사유로 미해결 문의를 거르고 담당 상담원을 바꾼다.
// 새 API 없이 접수함 목록(GET /tickets)과 담당 변경(POST /sub-tickets/assign, 변경 add-reassign)을 쓴다.
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, ApiError, type InboxRow } from "../../api";
import { CATEGORY, label } from "../../app/labels";
import { useAgents, useDepartments } from "../../app/queries";
import { useSession } from "../../app/session";
import { AlertChip, Banner, Button, DataTable, EmptyState, formatRemaining, PageHeader, Pager, PriorityBadge, StatusBadge, type Column } from "../../ui";
import "./assign.css";

const SIZE = 15; // 목업 쪽당 15건
const ALL_MAX = 200; // [필터된 n건 모두 선택]은 서버 한 번 응답(최대 200건)까지
const KINDS: [string, string][] = [
  ["breach", "기한 초과"], ["risk", "기한 임박"], ["p1", "우선순위 P1"],
];
const ALERT_OF: Record<string, string> = { breach: "FR_BREACHED,RES_BREACHED", risk: "FR_AT_RISK,RES_AT_RISK" };

function useParam(key: string): [string, (v: string) => void] {
  const [value, set] = useState(() => new URLSearchParams(window.location.search).get(key) ?? "");
  const setter = (v: string) => {
    const url = new URL(window.location.href);
    if (v) url.searchParams.set(key, v); else url.searchParams.delete(key);
    window.history.replaceState(null, "", url);
    set(v);
  };
  return [value, setter];
}

export function AssignPage({ onOpen }: { onOpen: (ticketId: string) => void }) {
  const { dept: sessionDept, asOf } = useSession();
  const depts = useDepartments();
  const agents = useAgents();
  const qc = useQueryClient();
  const [deptParam, setDeptParam] = useParam("dept");
  const dept = deptParam || sessionDept;
  const [who, setWho] = useParam("who");
  const [kind, setKind] = useParam("kind");
  const [text, setText] = useParam("q");
  const [pageParam, setPageParam] = useParam("page");
  const page = Number(pageParam) || 1;
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [to, setTo] = useState("");
  const [notice, setNotice] = useState<{ tone: "info" | "neg"; text: string } | null>(null);
  const deptAgents = (agents.data ?? []).filter((a) => a.dept === dept);

  // 거르는 값이 바뀌면 1쪽부터, 선택은 풀린다
  const change = (fn: () => void) => { fn(); setPageParam(""); setPicked(new Set()); };

  function query(size: number, p: number): URLSearchParams {
    const q = new URLSearchParams({ dept, size: String(size), page: String(p) });
    if (who) q.set("assignee", who);
    if (kind === "p1") q.set("priority", "P1"); else if (kind && ALERT_OF[kind]) q.set("alert", ALERT_OF[kind]);
    if (text.trim()) q.set("q", text.trim());
    if (asOf) q.set("as_of", asOf);
    return q;
  }
  const list = useQuery({ queryKey: ["assign-list", dept, who, kind, text, page, asOf], queryFn: () => api.inbox(query(SIZE, page)), enabled: !!dept, placeholderData: keepPreviousData });
  const rows = list.data?.rows ?? [];
  const total = list.data?.counts.total ?? 0;
  const pageAll = rows.length > 0 && rows.every((r) => picked.has(r.sub_ticket_id));
  useEffect(() => { setPicked((p) => new Set([...p])); }, [dept]);

  async function reassign(ids: string[], name: string) {
    try {
      const res = await api.assign(ids, name);
      const skipped = res.skipped.length ? ` · ${res.skipped.length}건은 바꾸지 못함(${[...new Set(res.skipped.map((s) => s.reason))].join(", ")})` : "";
      setNotice({ tone: res.moved.length ? "info" : "neg", text: res.moved.length ? `${res.moved.length}건을 ${name}에게 재배정했습니다${skipped}` : `바뀐 문의가 없습니다${skipped}` });
      setPicked(new Set()); setTo("");
      for (const k of ["assign-list", "inbox", "inbox-counts", "workload", "mywork-now"]) void qc.invalidateQueries({ queryKey: [k] });
    } catch (e) {
      setNotice({ tone: "neg", text: e instanceof ApiError ? e.message : "담당을 바꾸지 못했습니다. 다시 시도하세요" });
    }
  }
  async function selectAll() {
    const all = await api.inbox(query(ALL_MAX, 1));
    setPicked(new Set(all.rows.map((r) => r.sub_ticket_id)));
  }

  const columns: Column<InboxRow>[] = [
    { key: "pick", header: <input type="checkbox" aria-label="이 쪽 전체 선택" checked={pageAll}
        onChange={() => setPicked((p) => { const n = new Set(p); rows.forEach((r) => (pageAll ? n.delete(r.sub_ticket_id) : n.add(r.sub_ticket_id))); return n; })} onClick={(e) => e.stopPropagation()} />,
      render: (r) => <input type="checkbox" aria-label={`${r.ticket_id} #${r.seq} 선택`} checked={picked.has(r.sub_ticket_id)} onClick={(e) => e.stopPropagation()}
        onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(r.sub_ticket_id)) n.delete(r.sub_ticket_id); else n.add(r.sub_ticket_id); return n; })} /> },
    { key: "ticket", header: "문의", render: (r) => (
      <span className="asg-ticket">
        <b>{r.ticket_id}{r.inquiry_count > 1 ? ` #${r.seq}` : ""}</b>
        <span className="asg-sub" title={r.summary_ko ?? r.inquiry_subject ?? undefined}>{r.summary_ko ?? r.inquiry_subject ?? label(CATEGORY, r.category_code)}</span>
        <span className="asg-sub">{r.company_masked}</span>
      </span>) },
    { key: "dept", header: "부서", render: (r) => depts.data?.find((d) => d.dept_code === r.assigned_dept)?.dept_name_ko ?? r.assigned_dept ?? "—" },
    { key: "prio", header: "우선순위", render: (r) => r.priority ? <PriorityBadge priority={r.priority} adjusted={!!r.priority_adjusted} /> : "—" },
    { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status} /> },
    { key: "reason", header: "사유", render: (r) => <span className="asg-chips">{r.alerts.map((a) => <AlertChip key={a} alert={a} />)}</span> },
    { key: "left", header: "해결 기한까지", align: "right", render: (r) => (r.remaining_h === null || r.remaining_h === undefined || r.status === "WAITING_CUSTOMER" ? "—" : formatRemaining(Number(r.remaining_h))) },
    { key: "who", header: "담당 상담원", render: (r) => (
      <select className="asg-select" aria-label={`${r.ticket_id} #${r.seq} 담당 상담원 변경`} value={r.assignee_masked ?? ""} onClick={(e) => e.stopPropagation()}
        onChange={(e) => void reassign([r.sub_ticket_id], e.target.value)}>
        {!r.assignee_masked && <option value="">미배정</option>}
        {(agents.data ?? []).filter((a) => a.dept === (r.assigned_dept ?? dept)).map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
      </select>) },
  ];

  if (!dept) return <><PageHeader title="문의 배정 관리" /><EmptyState title="부서를 선택하세요">왼쪽 위 프로필을 눌러 부서를 고릅니다.</EmptyState></>;
  return (
    <div className="asg">
      <PageHeader title="문의 배정 관리" meta="부서와 담당 상담원, 사유로 미해결 문의를 거르고 담당을 바꿉니다" />
      {notice && <Banner tone={notice.tone} action={<Button size="sm" variant="ghost" onClick={() => setNotice(null)}>닫기</Button>}>{notice.text}</Banner>}
      {list.isError && <Banner tone="neg" action={<Button size="sm" onClick={() => void list.refetch()}>새로고침</Button>}>목록을 불러오지 못함. 새로고침</Banner>}
      <section className="ui-card">
        <div className="asg-filters" role="group" aria-label="거르기">
          <select aria-label="부서" value={dept} onChange={(e) => change(() => { setDeptParam(e.target.value); setWho(""); })}>
            {(depts.data ?? []).map((d) => <option key={d.dept_code} value={d.dept_code}>{d.dept_name_ko}</option>)}
          </select>
          <select aria-label="담당 상담원" value={who} onChange={(e) => change(() => setWho(e.target.value))}>
            <option value="">상담원 전체</option>
            {deptAgents.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
          </select>
          <select aria-label="사유" value={kind} onChange={(e) => change(() => setKind(e.target.value))}>
            <option value="">미해결 전체</option>
            {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input type="search" aria-label="검색어" placeholder="문의 번호, 고객사" value={text} onChange={(e) => change(() => setText(e.target.value))} />
          <span className="asg-count">{total}건</span>
        </div>
        {picked.size > 0 && (
          <div className="asg-bulk" role="region" aria-label="선택한 문의 재배정">
            <b>{picked.size}건 선택</b><span>→ 담당을</span>
            <select aria-label="받을 상담원" value={to} onChange={(e) => setTo(e.target.value)}>
              <option value="">고르세요</option>
              {deptAgents.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
            </select>
            <Button size="sm" variant="primary" disabled={!to} onClick={() => void reassign([...picked], to)}>재배정</Button>
            {picked.size < total && total <= ALL_MAX && <Button size="sm" variant="ghost" onClick={() => void selectAll()}>필터된 {total}건 모두 선택</Button>}
            <span className="asg-grow" />
            <Button size="sm" variant="ghost" onClick={() => setPicked(new Set())}>선택 해제</Button>
          </div>
        )}
        <DataTable<InboxRow> caption="문의 배정 목록" columns={columns} rows={list.data ? rows : undefined} loading={list.isPending} stale={list.isError}
          rowKey={(r) => r.sub_ticket_id} onRowClick={(r) => onOpen(r.ticket_id)} empty={<EmptyState title="해당하는 문의가 없습니다" />} />
        {list.data && <Pager total={total} page={page} size={SIZE} onPage={(p) => setPageParam(p > 1 ? String(p) : "")} />}
      </section>
    </div>
  );
}
