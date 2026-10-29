// SCR-00 공통 틀. 목업 v1.42 updateShell·renderProf·MENU의 배치: 남색 머리 막대 + 왼쪽 메뉴(프로필, 메뉴 묶음) + 경로 표시.
// 목업의 글자 크기·세션 시간·설정·로그아웃은 로그인이 없어(D23) 두지 않는다. 근무 상태는 저장하지 않는 목업 요소(N-00-01).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Banner, Field } from "../ui";
import { Bell } from "./Bell";
import { Icon, Wordmark } from "./icons";
import { useAgents, useDepartments, useInboxCounts } from "./queries";
import { useSession } from "./session";
import "./shell.css";

export interface MenuItem { key: string; label: string; path: string; ready?: boolean; external?: boolean }
export interface MenuGroup { key: string; label: string; items: MenuItem[] }

// 목업 MENU 그대로(SCR-00-05). ready = 이 화면이 있다. 나머지는 다음 슬라이스이거나 목업 화면으로 둔다(README)
export const MENU: MenuGroup[] = [
  { key: "main", label: "홈", items: [
    { key: "notice", label: "공지사항", path: "/notice" },
    { key: "sysnote", label: "시스템 알림", path: "/sysnote" },
  ] },
  { key: "recv", label: "접수", items: [
    { key: "home", label: "나의 업무 현황", path: "/my", ready: true },
    { key: "inbox", label: "접수함", path: "/inbox", ready: true },
    { key: "phone", label: "전화 상담", path: "/phone", ready: true },
    { key: "similar", label: "접수 이력", path: "/history" },
    { key: "customers", label: "고객 관리", path: "/customers" },
    { key: "chatbot", label: "챗봇 관리", path: "/chatbot" },
    { key: "portal", label: "고객포털 바로가기", path: "/portal", external: true },
  ] },
  { key: "docs", label: "지식 관리", items: [
    { key: "docs", label: "문서 관리", path: "/docs" },
    { key: "rules", label: "규칙 관리", path: "/rules" },
    { key: "products", label: "제품 관리", path: "/products" },
    { key: "depts", label: "부서 관리", path: "/depts" },
    { key: "etc", label: "기타 관리", path: "/etc" },
  ] },
  { key: "ops", label: "대시보드", items: [{ key: "ops", label: "운영 대시보드", path: "/dashboard" }] },
];

export interface Crumb { label: string; path?: string }

export function AppShell({ active, crumbs, navigate, children }: {
  /** 켜진 메뉴 key */
  active: string;
  crumbs: Crumb[];
  navigate: (path: string) => void;
  children: ReactNode;
}) {
  const { dept, asOf } = useSession();
  const counts = useInboxCounts(dept, asOf);
  const [collapsed, setCollapsed] = useState(false);
  const group = MENU.find((g) => g.items.some((i) => i.key === active))?.key;

  const go = (path: string) => (e: React.MouseEvent) => { e.preventDefault(); navigate(path); };

  return (
    <div className={collapsed ? "shell is-collapsed" : "shell"}>
      <header className="shell-top">
        <a className="shell-logo" href="/my" onClick={go("/my")} aria-label="나의 업무 현황"><Wordmark /></a>
        <nav className="shell-gnav" aria-label="대메뉴">
          {MENU.map((g) => (
            <a key={g.key} href={g.items[0].path} className={g.key === group ? "is-on" : undefined}
               aria-current={g.key === group ? "true" : undefined}
               onClick={go(g.key === "recv" ? "/my" : g.items[0].path)}>{g.label}</a>
          ))}
        </nav>
        <div className="shell-spacer" />
        <Bell onOpen={(id) => navigate(`/tickets/${encodeURIComponent(id)}`)} />
      </header>

      <div className="shell-frame">
        <nav className="shell-nav" aria-label="주 메뉴">
          <Profile />
          {MENU.map((g) => (
            <div key={g.key} className={g.key === group ? "shell-grp is-on" : "shell-grp"}>
              <div className="shell-grp__h">{g.label}</div>
              {g.items.map((i) => (
                <a key={i.key} href={i.path} className={i.key === active ? "is-on" : undefined} title={i.label}
                   aria-current={i.key === active ? "page" : undefined} onClick={go(i.path)}>
                  <Icon name={i.key} />
                  <span className="shell-nav__label">{i.label}</span>
                  {i.key === "inbox" && counts.data && <span className="shell-nav__count" data-testid="nav-inbox-count">{counts.data.total}</span>}
                  {i.external && <Icon name="ext" className="shell-nav__ext" />}
                </a>
              ))}
            </div>
          ))}
          <button type="button" className="shell-collapse" onClick={() => setCollapsed(!collapsed)}>
            <Icon name="collapse" /><span className="shell-nav__label">{collapsed ? "메뉴 펼치기" : "메뉴 접기"}</span>
          </button>
        </nav>

        <main className="shell-main">
          <div className="shell-crumb">
            <a className="shell-crumb__home" href="/my" onClick={go("/my")} aria-label="나의 업무 현황"><Icon name="crumbHome" /></a>
            {crumbs.map((c, i) => (
              <span key={i} className="shell-crumb__part">
                <Icon name="chev" className="shell-crumb__chev" />
                {c.path && i < crumbs.length - 1
                  ? <a className="shell-crumb__seg" href={c.path} onClick={go(c.path)}>{c.label}</a>
                  : <span className="shell-crumb__seg" aria-current={i === crumbs.length - 1 ? "page" : undefined}>{c.label}</span>}
              </span>
            ))}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

/** 왼쪽 위 프로필. 누르면 부서·상담원·기준 시각을 고르는 창(목업 openMe) */
function Profile() {
  const s = useSession();
  const depts = useDepartments();
  const agents = useAgents();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const deptName = depts.data?.find((d) => d.dept_code === s.dept)?.dept_name_ko;
  const me = agents.data?.find((a) => a.name === s.agent);

  // 명단에 없는 상담원이 기억돼 있으면 지운다(SCR-00 입력 검증)
  useEffect(() => {
    if (agents.data && s.agent && !agents.data.some((a) => a.name === s.agent)) s.setAgent("");
  }, [agents.data, s]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const listFailed = depts.isError || agents.isError;
  const roster = (agents.data ?? []).filter((a) => !s.dept || a.dept === s.dept);

  return (
    <div className="shell-prof shell-pop-anchor" ref={box}>
      <button type="button" className="shell-prof__top" title="부서·상담원 바꾸기" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="shell-prof__av" aria-hidden="true">{s.agent ? s.agent.slice(0, 1).toUpperCase() : "?"}</span>
        <span className="shell-prof__id shell-nav__label">
          <b>{s.agent || "상담원을 고르세요"}</b>
          <span>{deptName ?? (s.dept || "부서를 고르세요")}</span>
          <span className="shell-mono">{s.dept || "—"}{me?.demo ? " · 시연용" : ""}</span>
        </span>
      </button>
      <div className="shell-prof__body shell-nav__label">
        <span className={s.mode === "snapshot" ? "shell-prof__asof is-snap" : "shell-prof__asof"}>
          기준 시각: {s.mode === "snapshot" ? "스냅샷 2026-09-30 23:59 UTC" : "실제 시각"}
        </span>
      </div>
      {open && (
        <div className="shell-pop shell-pop--left" role="dialog" aria-label="내 정보">
          <h4>내 정보</h4>
          <div className="shell-pop__form">
            {listFailed && <Banner tone="neg">목록을 불러오지 못함. 새로고침</Banner>}
            <Field label="부서">
              <select value={s.dept} onChange={(e) => {
                const next = e.target.value;
                s.setDept(next);
                // 다른 부서 사람이 골라져 있으면 비운다
                if (next && agents.data?.some((a) => a.name === s.agent && a.dept !== next)) s.setAgent("");
              }}>
                <option value="">부서를 선택하세요</option>
                {(depts.data ?? []).map((d) => <option key={d.dept_code} value={d.dept_code}>{d.dept_name_ko} ({d.dept_code})</option>)}
              </select>
            </Field>
            <Field label="상담원">
              <select value={s.agent} onChange={(e) => s.setAgent(e.target.value)}>
                <option value="">상담원을 고르세요</option>
                {roster.map((a) => (
                  <option key={a.name} value={a.name}>{a.name}{s.dept ? "" : ` (${a.dept})`}{a.demo ? " · 시연용" : ""}</option>
                ))}
              </select>
            </Field>
            <Field label="기준 시각">
              <select value={s.mode} onChange={(e) => s.setMode(e.target.value === "snapshot" ? "snapshot" : "now")}>
                <option value="now">실제 시각</option>
                <option value="snapshot">스냅샷 2026-09-30 23:59 UTC</option>
              </select>
            </Field>
            <p className="shell-pop__note">로그인 대신 부서와 상담원을 고릅니다(D23).</p>
          </div>
        </div>
      )}
    </div>
  );
}
