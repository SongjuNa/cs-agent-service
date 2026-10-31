// SCR-00 공통 틀. 목업 v1.42 updateShell·renderProf·MENU의 배치: 남색 머리 막대 + 왼쪽 메뉴(프로필, 메뉴 묶음) + 경로 표시.
// 목업의 글자 크기·세션 시간·설정·로그아웃은 로그인이 없어(D23) 두지 않는다. 근무 상태는 저장하지 않는 목업 요소(N-00-01).
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { AssistantDock } from "../features/assistant/AssistantDock";
import { Banner, Field } from "../ui";
import { Bell } from "./Bell";
import { Icon, Wordmark } from "./icons";
import { useAgents, useDepartments, useInboxCounts, useMyStats } from "./queries";
import { useSession } from "./session";
import "./shell.css";

export interface MenuItem { key: string; label: string; path: string; ready?: boolean; external?: boolean; /** 이 항목부터 새 소제목(목업 side-label) */ section?: string }
export interface MenuGroup { key: string; label: string; items: MenuItem[] }

// 목업 MENU 그대로(SCR-00-05). ready = 이 화면이 있다. 나머지는 다음 슬라이스이거나 목업 화면으로 둔다(README)
export const MENU: MenuGroup[] = [
  { key: "main", label: "홈", items: [
    { key: "home", label: "나의 업무 현황", path: "/my", ready: true },
  ] },
  { key: "recv", label: "접수", items: [
    { key: "inbox", label: "접수함", path: "/inbox", ready: true },
    { key: "similar", label: "접수 이력", path: "/history", ready: true, section: "조회" },
    { key: "customers", label: "고객 관리", path: "/customers", ready: true },
    { key: "portal", label: "고객 포털 미리보기", path: "/portal", section: "시연" },
    { key: "phone", label: "전화 상담", path: "/phone", ready: true },
  ] },
  { key: "docs", label: "지식 관리", items: [
    { key: "docs", label: "문서 관리", path: "/docs", ready: true },
    { key: "rules", label: "규칙 관리", path: "/rules", ready: true },
    { key: "products", label: "제품 관리", path: "/products", ready: true },
    { key: "depts", label: "부서 관리", path: "/depts", ready: true },
    { key: "etc", label: "기타 관리", path: "/etc", ready: true },
  ] },
  { key: "ops", label: "대시보드", items: [
    { key: "ops", label: "운영 대시보드", path: "/dashboard" },
    { key: "assign", label: "문의 배정 관리", path: "/admin/assign", ready: true },
    { key: "auto", label: "자동 처리 규칙", path: "/admin/auto", ready: true },
  ] },
];

export interface Crumb { label: string; path?: string }

export function AppShell({ active, crumbs, navigate, children }: {
  /** 켜진 메뉴 key */
  active: string;
  crumbs: Crumb[];
  navigate: (path: string) => void;
  children: ReactNode;
}) {
  const { dept, asOf, setAgent, setDept } = useSession();
  const counts = useInboxCounts(dept, asOf);
  const [collapsed, setCollapsed] = useState(false);
  const group = MENU.find((g) => g.items.some((i) => i.key === active))?.key;

  const go = (path: string) => (e: React.MouseEvent) => { e.preventDefault(); navigate(path); };
  // 로그인이 없어(D23) 로그아웃은 고른 부서·상담원을 비우는 것이다
  const logout = () => { setAgent(""); setDept(""); navigate("/my"); };

  return (
    <div className={collapsed ? "shell is-collapsed" : "shell"}>
      <header className="shell-top">
        <StarField />
        <a className="shell-logo" href="/my" onClick={go("/my")} aria-label="나의 업무 현황"><Wordmark /></a>
        <nav className="shell-gnav" aria-label="대메뉴">
          {MENU.map((g) => (
            <a key={g.key} href={g.items[0].path} className={g.key === group ? "is-on" : undefined}
               aria-current={g.key === group ? "true" : undefined}
               onClick={go(g.items[0].path)}>{g.label}</a>
          ))}
        </nav>
        <div className="shell-spacer" />
        <Bell onOpen={(id) => navigate(`/tickets/${encodeURIComponent(id)}`)} />
        <span className="shell-datechip" title={asOf ? "기준 시각(스냅샷)의 날짜" : "오늘"}>{dayLabel(asOf)}</span>
        <HelpButton />
        <SessionTimer onExpire={logout} />
        <button type="button" className="shell-icon-btn" aria-label="설정" title="부서·상담원 설정" onClick={() => window.dispatchEvent(new Event("cs-open-prof"))}><Icon name="sliders" /></button>
        <button type="button" className="shell-logout" onClick={logout}><Icon name="logout" />로그아웃</button>
      </header>

      <div className="shell-frame">
        <nav className="shell-nav" aria-label="주 메뉴">
          <Profile />
          {/* 목업 MENU처럼 위 탭(대메뉴)의 묶음 하나만 보인다(2026-10-29 조장 "목업처럼 맞춥니다") */}
          {MENU.filter((g) => g.key === (group ?? "main")).map((g) => (
            <div key={g.key} className="shell-grp is-on">
              <div className="shell-grp__h">{g.label}</div>
              {g.items.map((i) => (
                <Fragment key={i.key}>
                {i.section && <div className="shell-grp__sub">{i.section}</div>}
                <a href={i.path} className={i.key === active ? "is-on" : undefined} title={i.label}
                   aria-current={i.key === active ? "page" : undefined} onClick={go(i.path)}>
                  <Icon name={i.key} />
                  <span className="shell-nav__label">{i.label}</span>
                  {i.key === "inbox" && counts.data && <>{counts.data.new > 0 && <span className="shell-nav__new" data-testid="nav-inbox-new">새 {counts.data.new}</span>}<span className="shell-nav__count" data-testid="nav-inbox-count">{counts.data.total}</span></>}
                  {i.external && <Icon name="ext" className="shell-nav__ext" />}
                </a>
                </Fragment>
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
      <AssistantDock />
    </div>
  );
}

const SESSION_SEC = 30 * 60;
/** 목업의 세션 남은 시간과 [연장]. 로그인이 없어 0이 되면 로그아웃(부서·상담원 비움)한다 */
function SessionTimer({ onExpire }: { onExpire: () => void }) {
  const [end, setEnd] = useState(() => Date.now() + SESSION_SEC * 1000);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(i); }, []);
  const left = Math.max(0, Math.round((end - now) / 1000));
  useEffect(() => { if (left === 0) { onExpire(); setEnd(Date.now() + SESSION_SEC * 1000); } }, [left]); // eslint-disable-line react-hooks/exhaustive-deps
  const mm = String(Math.floor(left / 60)).padStart(2, "0"), ss = String(left % 60).padStart(2, "0");
  return (
    <span className={left <= 300 ? "shell-session is-low" : "shell-session"} title="세션 남은 시간">
      <Icon name="timer" />세션 <b className="shell-mono">{mm}:{ss}</b>
      <button type="button" onClick={() => setEnd(Date.now() + SESSION_SEC * 1000)}>연장</button>
    </span>
  );
}

function HelpButton() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div className="shell-pop-anchor" ref={box}>
      <button type="button" className="shell-icon-btn" aria-label="도움말" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="help" /></button>
      {open && <div className="shell-pop" role="dialog" aria-label="도움말"><h4>도움말</h4><div className="shell-pop__empty">도움말은 아직 연결되지 않았습니다.</div></div>}
    </div>
  );
}

const WEEK = ["일", "월", "화", "수", "목", "금", "토"];
/** 상단의 날짜 칩("9월 30일 (수)"). 스냅샷이면 그 시각의 UTC 날짜, 아니면 오늘 */
function dayLabel(asOf: string | null): string {
  if (asOf) { const d = new Date(asOf); return `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일 (${WEEK[d.getUTCDay()]})`; } // 스냅샷은 UTC 날짜 그대로
  const d = new Date();
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEK[d.getDay()]})`;
}

/** 상단 막대 뒤에서 반짝이는 별(목업 StarField). 움직임을 줄이는 설정이면 멈춘 채로 그린다 */
function StarField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const x = c?.getContext("2d");
    if (!c || !x) return;
    let w = 0, h = 0, raf = 0;
    const stars = Array.from({ length: 70 }, () => ({ x: Math.random(), y: Math.random(), s: 1 + Math.random() * 3, p: Math.random() * 6.28, v: 0.4 + Math.random() * 1.2, sq: Math.random() < 0.5 }));
    const fit = () => { const r = c.getBoundingClientRect(); const d = window.devicePixelRatio || 1; w = r.width; h = r.height; c.width = w * d; c.height = h * d; x.setTransform(d, 0, 0, d, 0, 0); };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(c);
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const draw = (t: number) => {
      x.clearRect(0, 0, w, h);
      for (const s of stars) {
        const a = still ? 0.35 : 0.12 + 0.5 * (0.5 + 0.5 * Math.sin((t / 1000) * s.v + s.p));
        x.strokeStyle = x.fillStyle = `rgba(160,190,255,${a})`;
        if (s.sq) { x.lineWidth = 1; x.strokeRect(s.x * w, s.y * h, s.s * 2, s.s * 2); } else x.fillRect(s.x * w, s.y * h, s.s, s.s);
      }
      if (!still) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);
  return <canvas ref={ref} className="shell-stars" aria-hidden="true" />;
}

type Presence = "online" | "away" | "offline";
const PRESENCE: Record<Presence, [string, string]> = { online: ["온라인", "ok"], away: ["자리 비움", "warn"], offline: ["오프라인", "off"] };
const readPresence = (): Presence => {
  try { const v = localStorage.getItem("cs-presence") as Presence; return v in PRESENCE ? v : "online"; } catch { return "online"; }
};

/** 왼쪽 위 프로필. 누르면 부서·상담원·기준 시각을 고르는 창(목업 openMe) */
function Profile() {
  const s = useSession();
  const depts = useDepartments();
  const agents = useAgents();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const deptName = depts.data?.find((d) => d.dept_code === s.dept)?.dept_name_ko;
  const me = agents.data?.find((a) => a.name === s.agent);
  const stats = useMyStats(s.dept, s.asOf, s.agent);
  const [pres, setPres] = useState<Presence>(readPresence); // 저장하지 않는 목업 요소(N-00-01): 이 브라우저에만 기억한다
  const changePresence = (v: Presence) => { setPres(v); try { localStorage.setItem("cs-presence", v); } catch { /* 저장 불가 환경 */ } };
  const synced = new Date((s.asOf ? new Date(s.asOf).getTime() : Date.now()) + 9 * 3600e3).toISOString().slice(11, 16);

  // 명단에 없는 상담원이 기억돼 있으면 지운다(SCR-00 입력 검증)
  useEffect(() => {
    if (agents.data && s.agent && !agents.data.some((a) => a.name === s.agent)) s.setAgent("");
  }, [agents.data, s]);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener("cs-open-prof", show);
    return () => window.removeEventListener("cs-open-prof", show);
  }, []);

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
        <span className="shell-prof__avwrap">
          <span className="shell-prof__av" aria-hidden="true">
            <svg viewBox="0 0 48 48"><circle cx="24" cy="18" r="8.5" fill="#fff" opacity=".92" /><path d="M7 46c1.2-10 8.4-15.5 17-15.5S39.8 36 41 46z" fill="#fff" opacity=".92" /></svg>
          </span>
          <i className={`shell-dot shell-dot--${PRESENCE[pres][1]} shell-dot--on-av`} />
        </span>
        <span className="shell-prof__id shell-nav__label">
          <b>{s.agent || "상담원을 고르세요"}</b>
          <span>{deptName ?? (s.dept || "부서를 고르세요")}</span>
          <span className="shell-mono">{s.dept || "—"}{me?.demo ? " · 시연용" : ""}</span>
        </span>
      </button>
      <div className="shell-prof__body shell-nav__label">
        <select className="shell-prof__sel" value={pres} aria-label="접속 상태" onChange={(e) => changePresence(e.target.value as Presence)}>
          {(Object.keys(PRESENCE) as Presence[]).map((k) => <option key={k} value={k}>{PRESENCE[k][0]}</option>)}
        </select>
        <span className={pres !== "offline" ? "shell-prof__live is-on" : "shell-prof__live"}>
          <i className={`shell-dot shell-dot--${pres !== "offline" ? "ok" : "off"}`} />{pres !== "offline" ? `연결 중 · ${synced} 동기화` : "연결 끊김"}
        </span>
        <span className="shell-prof__hours">09:00-18:00 KST{pres === "online" ? " · 채팅 가능" : " · 채팅 불가"}</span>
        {s.agent && (
          <div className="shell-prof__stats" data-testid="prof-stats">
            <div><b>{stats.open ?? "–"}</b><span>미해결</span></div>
            <div><b className={stats.alert ? "is-bad" : undefined}>{stats.alert ?? "–"}</b><span>기한 위험</span></div>
            <div><b>{stats.today ?? "–"}</b><span>오늘 처리</span></div>
          </div>
        )}
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
