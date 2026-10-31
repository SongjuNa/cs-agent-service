// SCR-06 운영 대시보드 (최신 목업 `#/admin` "운영 현황", FR-034). 관리자가 팀 전체를 한눈에 본다. 숫자는 서버가 센 값(GET /dashboard/summary)을 그대로 보인다.
// 문장 풀이(요약 한 줄, 해석)는 그 숫자로 화면이 만든다. 모델이 만든 글이 아니다. 개별 문의 처리는 접수함, 담당 변경은 문의 배정 관리에서 한다.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type DashboardSummary } from "../../api";
import { useDepartments } from "../../app/queries";
import { useSession } from "../../app/session";
import { Banner, Button, EmptyState, PageHeader } from "../../ui";
import "./ops.css";

const REFRESH_MS = 5 * 60 * 1000;
const RANGES: [number, string][] = [[30, "30일"], [90, "90일"], [365, "1년"]];
const STAGE_LABEL: Record<string, [string, string]> = {
  NEW: ["신규 접수", "분류 완료, 초안 없음"], REVIEW: ["상담원 검토", "승인 대기 초안"], IN_PROGRESS: ["처리 중", "초안 없이 진행"],
  WAITING_CUSTOMER: ["고객 회신 대기", "정보 요청 뒤"], ESCALATED: ["전문 부서 이관", "부서 회신 대기"],
};
const pct = (n: number, d: number) => (d ? Math.round((n / d) * 100) : null);
const mmdd = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

export function OpsDashboardPage({ navigate }: { navigate: (path: string) => void }) {
  const { asOf } = useSession();
  const depts = useDepartments();
  const [days, setDays] = useState(30);
  const q = useQuery({
    queryKey: ["ops-dashboard", { days, asOf }],
    queryFn: () => { const p = new URLSearchParams({ days: String(days) }); if (asOf) p.set("as_of", asOf); return api.dashboard(p); },
    placeholderData: keepPreviousData, refetchInterval: REFRESH_MS,
  });
  const deptName = (code: string) => depts.data?.find((d) => d.dept_code === code)?.dept_name_ko ?? code;
  const d = q.data;
  if (!d) {
    return <><PageHeader title="운영 대시보드" />{q.isError ? <Banner tone="neg" action={<Button size="sm" onClick={() => void q.refetch()}>새로고침</Button>}>불러오지 못함. 새로고침</Banner> : <div className="ops-skel" aria-busy="true" />}</>;
  }
  return <Body d={d} days={days} setDays={setDays} stale={q.isError} refetch={() => void q.refetch()} deptName={deptName} navigate={navigate} />;
}

function Body({ d, days, setDays, stale, refetch, deptName, navigate }: {
  d: DashboardSummary; days: number; setDays: (n: number) => void; stale: boolean; refetch: () => void;
  deptName: (c: string) => string; navigate: (p: string) => void;
}) {
  const fr = pct(d.sla.fr_met, d.sla.fr_met + d.sla.fr_breached);
  const res = pct(d.sla.res_ok, d.sla.window_total);
  const worstDept = [...d.by_dept].sort((a, b) => b.breach - a.breach)[0];
  const topStage = [...d.stages].sort((a, b) => b.open - a.open)[0];
  const perDay = d.daily.map((x) => x.n);
  const avg = perDay.reduce((s, n) => s + n, 0) / Math.max(1, perDay.length);
  const peak = perDay.indexOf(Math.max(...perDay));
  const loadAvg = d.by_agent.reduce((s, a) => s + a.open, 0) / Math.max(1, d.by_agent.length);
  const heavy = d.by_agent[0];
  const edited = d.edited.sent ? pct(d.edited.edited, d.edited.sent) : null;
  const deptMax = Math.max(1, ...d.by_dept.map((x) => x.open));
  const agentMax = Math.max(1, ...d.by_agent.map((x) => x.open));
  const stageMax = Math.max(1, ...d.stages.map((x) => x.open));

  return (
    <div className={stale ? "ops is-stale" : "ops"} data-testid="ops">
      <PageHeader title="운영 대시보드" meta={`전체 부서 · 기준 ${d.as_of.slice(0, 16).replace("T", " ")} UTC · 기한 충족과 접수 추이는 최근 ${d.days}일 접수분`} />
      {stale && <Banner tone="neg" action={<Button size="sm" onClick={refetch}>새로고침</Button>}>불러오지 못함. 새로고침</Banner>}
      <p className="ops-lead" data-testid="ops-lead">
        미해결 <b>{d.open.total}건</b> 중 <b className={d.open.breach ? "is-bad" : undefined}>{d.open.breach}건</b>이 기한을 넘겼고 {d.open.risk}건이 임박했습니다.
        {worstDept && worstDept.breach > 0 && <> 기한 위반이 가장 많은 곳은 <b>{deptName(worstDept.dept)}</b>({worstDept.breach}건)입니다.</>}
        {topStage && topStage.open > 0 && <> 가장 많이 머무는 단계는 <b>{STAGE_LABEL[topStage.stage][0]}</b>({topStage.open}건)입니다.</>}
      </p>

      <div className="ops-kpis">
        <div className="ops-kpi" data-kpi="fr"><span>1차 응답 충족률</span><b>{fr ?? "—"}{fr !== null && <small>%</small>}</b><em>충족 {d.sla.fr_met} · 위반 {d.sla.fr_breached} (최근 {d.days}일 접수)</em></div>
        <div className="ops-kpi" data-kpi="res"><span>해결 기한 내 비율</span><b>{res ?? "—"}{res !== null && <small>%</small>}</b><em>위반 {d.sla.window_total - d.sla.res_ok}건 제외 (최근 {d.days}일 접수)</em></div>
        <div className="ops-kpi" data-kpi="open"><span>미해결 문의</span><b>{d.open.total}<small>건</small></b><em>기준일 새로 접수 {d.open.new_today}건</em></div>
        <button type="button" className="ops-kpi is-link" data-kpi="breach" onClick={() => navigate("/admin/assign?kind=breach")}>
          <span>기한 위반</span><b className={d.open.breach ? "is-bad" : undefined}>{d.open.breach}<small>건</small></b><em>임박 {d.open.risk}건 · 누르면 배정 관리</em>
        </button>
        <div className="ops-kpi" data-kpi="edited"><span>고쳐 보낸 비율</span><b>{edited ?? "—"}{edited !== null && <small>%</small>}</b>
          <em>{d.edited.sent ? `AI 초안을 고쳐 보낸 ${d.edited.edited}건 / 보낸 ${d.edited.sent}건` : "이 시스템에서 보낸 답변이 아직 없어 계산하지 않음"}</em></div>
      </div>

      <div className="ops-grid">
        <section className="ui-card ops-card" aria-label="일별 접수 추이">
          <header className="ops-card__h"><b>일별 접수 추이</b>
            <span className="ops-range" role="group" aria-label="기간">{RANGES.map(([n, l]) => <button key={n} type="button" aria-pressed={days === n} className={days === n ? "is-on" : ""} onClick={() => setDays(n)}>{l}</button>)}</span></header>
          <LineChart days={d.daily.map((x) => mmdd(x.date))} values={perDay} avg={avg} peak={peak} />
          <p className="ops-insight">하루 평균 <b>{avg.toFixed(0)}건</b>이 들어옵니다. 가장 많았던 날은 {d.daily[peak] ? mmdd(d.daily[peak].date) : "—"}({perDay[peak] ?? 0}건)입니다.</p>
        </section>
        <section className="ui-card ops-card" aria-label="나라별 먼저 볼 곳">
          <header className="ops-card__h"><b>먼저 볼 나라</b><span className="ops-sub">안전 → 위반 → 이관 지연 순</span></header>
          <ol className="ops-rank">
            {d.by_country.slice(0, 5).map((c, i) => (
              <li key={c.country}><span className="ops-rank__n">{i + 1}</span><b>{c.country}</b>
                <span>{[c.safety && `안전 ${c.safety}`, c.breach && `위반 ${c.breach}`, c.esc_late && `이관 지연 ${c.esc_late}`, c.risk && `임박 ${c.risk}`].filter(Boolean).join(" · ") || "지연 없음"}</span>
                <em>미해결 {c.open}</em></li>
            ))}
          </ol>
          <p className="ops-insight">나라별 건수는 고객의 국가 값을 코드로 센 것입니다.</p>
        </section>
      </div>

      <div className="ops-grid">
        <section className="ui-card ops-card" aria-label="부서별 병목">
          <header className="ops-card__h"><b>부서별 병목</b><span className="ops-sub">미해결 많은 순</span></header>
          <Bars rows={d.by_dept.slice(0, 7).map((x) => ({ key: x.dept, label: deptName(x.dept), n: x.open, bad: x.breach, tags: x.esc_late ? [`이관 지연 ${x.esc_late}`] : [], to: `/admin/assign?dept=${x.dept}` }))} max={deptMax} navigate={navigate} />
          <p className="ops-insight">{d.by_dept[0] ? <><b>{deptName(d.by_dept[0].dept)}</b>에 미해결 {d.by_dept[0].open}건이 가장 많이 쌓여 있습니다. 이관 지연은 전문 부서로 넘긴 뒤 168시간이 지난 건입니다.</> : "미해결 문의가 없습니다."}</p>
        </section>
        <section className="ui-card ops-card" aria-label="상담원별 업무량">
          <header className="ops-card__h"><b>상담원별 업무량</b><Button size="sm" onClick={() => navigate("/admin/assign")}>문의 배정 관리</Button></header>
          <Bars rows={d.by_agent.slice(0, 8).map((x) => ({ key: x.agent, label: x.agent, n: x.open, bad: x.breach, tags: [...(x.risk ? [`임박 ${x.risk}`] : []), ...(x.open > loadAvg * 1.25 ? ["집중"] : [])], to: `/admin/assign?dept=${x.dept ?? ""}&who=${encodeURIComponent(x.agent)}` }))} max={agentMax} navigate={navigate} />
          <p className="ops-insight">{heavy && heavy.open > loadAvg * 1.25 ? <><b>{heavy.agent}</b>에게 {heavy.open}건이 몰려 있습니다(평균 {loadAvg.toFixed(0)}건). 재배정을 검토하세요.</> : <>업무량이 고르게 나뉘어 있습니다(평균 {loadAvg.toFixed(0)}건).</>}</p>
        </section>
      </div>

      <section className="ui-card ops-card" aria-label="처리 단계별 현황">
        <header className="ops-card__h"><b>처리 단계별 현황</b><span className="ops-sub">지금 각 단계에 머무는 미해결 문의</span></header>
        <Bars rows={d.stages.map((x) => ({ key: x.stage, label: STAGE_LABEL[x.stage][0], sub: STAGE_LABEL[x.stage][1], n: x.open, bad: x.breach, tags: [] }))} max={stageMax} navigate={navigate} />
        <p className="ops-insight">{topStage && topStage.open > 0 ? <><b>{STAGE_LABEL[topStage.stage][0]}</b> 단계에 {topStage.open}건이 가장 많이 머뭅니다.</> : "쌓인 문의가 없습니다."}</p>
      </section>
      {d.by_dept.length === 0 && <EmptyState title="집계할 미해결 문의가 없습니다" />}
    </div>
  );
}

interface BarRow { key: string; label: string; sub?: string; n: number; bad: number; tags: string[]; to?: string }

function Bars({ rows, max, navigate }: { rows: BarRow[]; max: number; navigate: (p: string) => void }) {
  return (
    <div className="ops-bars">
      {rows.map((r) => {
        const inner = (
          <>
            <span className="ops-bars__l">{r.label}{r.sub && <small>{r.sub}</small>}</span>
            <span className="ops-bars__t"><i className="all" style={{ width: `${(r.n / max) * 100}%` }}><i className="bad" style={{ width: `${r.n ? (r.bad / r.n) * 100 : 0}%` }} /></i></span>
            <span className="ops-bars__v"><b>{r.n}</b>{r.bad > 0 && <em>위반 {r.bad}</em>}{r.tags.map((t) => <em key={t} className="w">{t}</em>)}</span>
          </>
        );
        return r.to
          ? <button key={r.key} type="button" className="ops-bars__row" onClick={() => navigate(r.to!)} title="누르면 문의 배정 관리에서 봅니다">{inner}</button>
          : <div key={r.key} className="ops-bars__row is-static">{inner}</div>;
      })}
      <div className="ops-legend"><span><i className="all" />미해결</span><span><i className="bad" />그중 기한 위반</span></div>
    </div>
  );
}

/** 일별 접수 선 그래프: 평균선과 가장 많은 날 표시. 라이브러리 없이 SVG로 그린다 */
function LineChart({ days, values, avg, peak }: { days: string[]; values: number[]; avg: number; peak: number }) {
  const W = 620, H = 210, L = 34, R = 12, T = 18, B = 26;
  const max = Math.max(5, Math.ceil(Math.max(...values, 0) / 5) * 5);
  const x = (i: number) => L + (i / Math.max(1, values.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const pts = values.map((v, i) => `${x(i)},${y(v)}`);
  const step = Math.max(1, Math.ceil(days.length / 10));
  return (
    <svg className="ops-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`일별 접수 건수 선 그래프. 하루 평균 ${avg.toFixed(0)}건`} data-testid="ops-chart">
      {[0, max / 2, max].map((t) => <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid" /><text x={L - 6} y={y(t) + 4} className="axis" textAnchor="end">{t}</text></g>)}
      <line x1={L} x2={W - R} y1={y(avg)} y2={y(avg)} className="avg" /><text x={W - R} y={y(avg) - 5} className="axis" textAnchor="end">평균 {avg.toFixed(0)}</text>
      <polygon points={`${x(0)},${y(0)} ${pts.join(" ")} ${x(values.length - 1)},${y(0)}`} className="area" />
      <polyline points={pts.join(" ")} className="line" />
      {values.map((v, i) => (days.length <= 60 || i === peak || i === values.length - 1) && <circle key={i} cx={x(i)} cy={y(v)} r={i === peak || i === values.length - 1 ? 4 : 2.5} className={i === peak ? "dot peak" : "dot"}><title>{days[i]} · {v}건</title></circle>)}
      <text x={x(peak)} y={y(values[peak] ?? 0) - 9} className="peak-l" textAnchor="middle">{values[peak]}</text>
      {days.map((dd, i) => (i % step === 0 || i === days.length - 1) && <text key={i} x={x(i)} y={H - 7} className="axis" textAnchor="middle">{dd}</text>)}
    </svg>
  );
}
