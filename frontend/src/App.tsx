// A안 사이드바형 틀 (화면 정의서 v2 0-7절): 왼쪽 사이드바 + 위 머리 막대(M-H-01, M-H-02) + 작업 영역.
import { useEffect, useState } from "react";
import { agentId, saveAgentId } from "./api";
import { TicketDetailPage } from "./TicketDetailPage";

function ticketFromPath(): string | null {
  const m = window.location.pathname.match(/^\/tickets\/([^/]+)$/);
  return m ? decodeURIComponent(m[1]) : null;
}

export function App() {
  const [ticketId, setTicketId] = useState<string | null>(ticketFromPath());
  const [input, setInput] = useState(ticketId ?? "");
  const [agent, setAgent] = useState(agentId());
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const onPop = () => setTicketId(ticketFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function open(e: React.FormEvent) {
    e.preventDefault();
    const id = input.trim();
    if (!id) return;
    window.history.pushState(null, "", `/tickets/${encodeURIComponent(id)}`);
    setTicketId(id);
  }

  return (
    <div className={`shell ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <button type="button" className="collapse" onClick={() => setCollapsed(!collapsed)} aria-label="사이드바 접기">
          {collapsed ? "»" : "«"}
        </button>
        {!collapsed && (
          <nav>
            <div className="brand">C/S Agent</div>
            <a className="active" href={ticketId ? `/tickets/${ticketId}` : "/"}>문의 상세</a>
            <span className="disabled">접수 시뮬레이터 <small>2순위</small></span>
            <span className="disabled">접수함 <small>2순위</small></span>
            <span className="disabled">나의 업무 현황 <small>2순위</small></span>
          </nav>
        )}
      </aside>
      <div className="main">
        <header className="topbar">
          <form onSubmit={open}>
            <label>문의 번호 <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="CSV1-004001" /></label>
            <button type="submit">열기</button>
          </form>
          <label className={agent ? "" : "bad"}>
            상담원 ID{" "}
            <input value={agent} onChange={(e) => { setAgent(e.target.value); saveAgentId(e.target.value.trim()); }}
                   placeholder="상담원 ID를 입력하세요" />
          </label>
        </header>
        <main>
          {ticketId ? <TicketDetailPage ticketId={ticketId} agent={agent.trim()} />
            : <p className="muted page-msg">문의 번호를 넣고 [열기]를 누르세요.</p>}
        </main>
      </div>
    </div>
  );
}
