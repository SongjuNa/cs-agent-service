// A안 사이드바형 틀 (화면 정의서 v2 0-7절): 왼쪽 사이드바 + 위 머리 막대(M-H-01, M-H-02, SCR-00-03·04) + 작업 영역.
import { useEffect, useState } from "react";
import {
  agentDept, agentId, api, asOfMode, saveAgentDept, saveAgentId, saveAsOfMode, SNAPSHOT,
  type AsOfMode, type Department,
} from "./api";
import { InboxPage } from "./InboxPage";
import { IntakePage } from "./IntakePage";
import { TicketDetailPage } from "./TicketDetailPage";

type Page = { kind: "inbox" } | { kind: "intake" } | { kind: "ticket"; id: string };

function pageFromPath(): Page {
  const path = window.location.pathname;
  const m = path.match(/^\/tickets\/([^/]+)$/);
  if (m) return { kind: "ticket", id: decodeURIComponent(m[1]) };
  if (path === "/intake") return { kind: "intake" };
  return { kind: "inbox" }; // "/"와 "/inbox": 접수함이 기본 화면(SCR-00-05)
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromPath());
  const [input, setInput] = useState(page.kind === "ticket" ? page.id : "");
  const [agent, setAgent] = useState(agentId());
  const [dept, setDept] = useState(agentDept());
  const [mode, setMode] = useState<AsOfMode>(asOfMode());
  const [depts, setDepts] = useState<Department[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const onPop = () => setPage(pageFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    api.departments().then(setDepts).catch(() => setDepts([]));
  }, []);

  function navigate(path: string, next: Page) {
    window.history.pushState(null, "", path);
    setPage(next);
  }

  function go(id: string) {
    navigate(`/tickets/${encodeURIComponent(id)}`, { kind: "ticket", id });
    setInput(id);
  }

  function open(e: React.FormEvent) {
    e.preventDefault();
    const id = input.trim();
    if (id) go(id);
  }

  function menu(path: string, next: Page) {
    return (e: React.MouseEvent) => { e.preventDefault(); navigate(path, next); };
  }

  return (
    <div className={`shell ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <button type="button" className="collapse" onClick={() => setCollapsed(!collapsed)} aria-label="사이드바 접기">
          {collapsed ? "»" : "«"}
        </button>
        {!collapsed && (
          <nav>
            <a className="brand" href="/inbox" onClick={menu("/inbox", { kind: "inbox" })}>C/S Agent</a>
            <a className={page.kind === "inbox" ? "active" : ""} href="/inbox" onClick={menu("/inbox", { kind: "inbox" })}>접수함</a>
            <span className="disabled">나의 업무 현황 <small>2순위</small></span>
            <a className={page.kind === "intake" ? "active" : ""} href="/intake" onClick={menu("/intake", { kind: "intake" })}>접수 시뮬레이터</a>
            {page.kind === "ticket" && <a className="active" href={`/tickets/${page.id}`}>문의 상세</a>}
          </nav>
        )}
      </aside>
      <div className="main">
        <header className="topbar">
          <form onSubmit={open}>
            <label>문의 번호 <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="CSV1-004001" /></label>
            <button type="submit">열기</button>
          </form>
          <label className={dept ? "" : "bad"}>
            부서{" "}
            <select value={dept} onChange={(e) => { setDept(e.target.value); saveAgentDept(e.target.value); }}>
              <option value="">부서를 선택하세요</option>
              {depts.map((d) => <option key={d.dept_code} value={d.dept_code}>{d.dept_code} {d.dept_name_ko}</option>)}
            </select>
          </label>
          <label>
            기준 시각{" "}
            <select value={mode} onChange={(e) => { const m = e.target.value as AsOfMode; setMode(m); saveAsOfMode(m); }}>
              <option value="now">실제 시각</option>
              <option value="snapshot">스냅샷 2026-09-30 23:59 UTC</option>
            </select>
          </label>
          <label className={agent ? "" : "bad"}>
            상담원 ID{" "}
            <input value={agent} onChange={(e) => { setAgent(e.target.value); saveAgentId(e.target.value.trim()); }}
                   placeholder="상담원 ID를 입력하세요" />
          </label>
        </header>
        <main>
          {page.kind === "intake" ? <IntakePage onCreated={go} />
            : page.kind === "ticket" ? <TicketDetailPage ticketId={page.id} agent={agent.trim()} />
            : <InboxPage key={`${dept}|${mode}`} dept={dept} asOf={mode === "snapshot" ? SNAPSHOT : null} onOpen={go} />}
        </main>
      </div>
    </div>
  );
}
