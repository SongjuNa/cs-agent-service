// A안 사이드바형 틀 (화면 정의서 v2 0-7절): 왼쪽 사이드바 + 위 머리 막대(M-H-01, M-H-02, SCR-00-03·04) + 작업 영역.
import { useCallback, useEffect, useState } from "react";
import {
  agentDept, agentId, api, asOfMode, saveAgentDept, saveAgentId, saveAsOfMode, SNAPSHOT,
  type Agent, type AsOfMode, type Department,
} from "./api";
import { InboxPage, lastInboxUrl } from "./InboxPage";
import { IntakePage } from "./IntakePage";
import { MyWorkPage } from "./MyWorkPage";
import { TicketDetailPage } from "./TicketDetailPage";

type Page = { kind: "inbox" } | { kind: "intake" } | { kind: "my" } | { kind: "ticket"; id: string };

function pageFromPath(): Page {
  const path = window.location.pathname;
  const m = path.match(/^\/tickets\/([^/]+)$/);
  if (m) return { kind: "ticket", id: decodeURIComponent(m[1]) };
  if (path === "/intake") return { kind: "intake" };
  if (path === "/my") return { kind: "my" }; // SCR-04 (§8-2)
  return { kind: "inbox" }; // "/"와 "/inbox": 접수함이 기본 화면(SCR-00-05)
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromPath());
  const [input, setInput] = useState(page.kind === "ticket" ? page.id : "");
  const [agent, setAgent] = useState(agentId());
  const [dept, setDept] = useState(agentDept());
  const [mode, setMode] = useState<AsOfMode>(asOfMode());
  const [depts, setDepts] = useState<Department[]>([]);
  const [roster, setRoster] = useState<Agent[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const onPop = () => setPage(pageFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    api.departments().then(setDepts).catch(() => setDepts([]));
    api.agents().then((list) => {
      setRoster(list);
      // 명단 전의 상담원 ID(예: TS_LV_AGENT_09)가 브라우저에 남아 있으면 비운다(담당 값이 이름이라 거를 수 없음)
      setAgent((cur) => { if (cur && !list.some((a) => a.name === cur)) { saveAgentId(""); return ""; } return cur; });
    }).catch(() => setRoster([]));
  }, []);

  function navigate(path: string, next: Page) {
    window.history.pushState(null, "", path);
    setPage(next);
  }

  // [목록으로]: 마지막 접수함 주소(필터·정렬·쪽)로(화면 정의서 v1 SCR-02 ③). 없는 번호면 안내를 띄운다(FR-030 예외 1행)
  const back = useCallback((message?: string) => {
    window.history.pushState(null, "", lastInboxUrl());
    setPage({ kind: "inbox" });
    setFlash(message ?? null);
  }, []);

  function go(id: string) {
    setFlash(null);
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
            <a className={page.kind === "my" ? "active" : ""} href="/my" onClick={menu("/my", { kind: "my" })}>나의 업무 현황</a>
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
            <select value={dept} onChange={(e) => {
              const next = e.target.value;
              setDept(next);
              saveAgentDept(next);
              if (next && roster.some((a) => a.name === agent && a.dept !== next)) { setAgent(""); saveAgentId(""); } // 다른 부서 사람은 비운다
            }}>
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
            상담원{" "}
            {/* 가상 상담원 명단에서 고른다(조장 결정 2026-10-23, add-agent-roster). 고른 부서의 사람만 */}
            <select value={agent} onChange={(e) => { setAgent(e.target.value); saveAgentId(e.target.value); }}>
              <option value="">상담원을 고르세요</option>
              {agent && !roster.some((a) => a.name === agent) && <option value={agent}>{agent}</option>}
              {roster.filter((a) => !dept || a.dept === dept).map((a) => (
                <option key={a.name} value={a.name}>{a.name}{dept ? "" : ` (${a.dept})`}{a.demo ? " · 시연용" : ""}</option>
              ))}
            </select>
          </label>
        </header>
        <main>
          {page.kind === "intake" ? <IntakePage onCreated={go} />
            : page.kind === "my" ? <MyWorkPage key={`${dept}|${mode}|${agent.trim()}`} dept={dept} agent={agent.trim()}
                                               asOf={mode === "snapshot" ? SNAPSHOT : null} onOpen={go} />
            : page.kind === "ticket" ? <TicketDetailPage key={`${page.id}|${dept}`} ticketId={page.id} agent={agent.trim()} onBack={back} />
            : <InboxPage key={`${dept}|${mode}`} flash={flash} dept={dept} asOf={mode === "snapshot" ? SNAPSHOT : null} onOpen={go} />}
        </main>
      </div>
    </div>
  );
}
