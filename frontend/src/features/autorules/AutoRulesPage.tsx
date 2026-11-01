// SCR-12 자동 처리 규칙 (최신 목업 `#/admin/auto`, 변경 add-auto-send). 어떤 문의를 검증을 통과하면 사람 승인 없이 보낼지 정한다.
// 자동 발송은 CLAUDE.md 규칙 3·D32를 바꾼 기능이다. 고위험 유형·우선순위·긴급도·복합 문의 등은 설정으로 풀 수 없는 고정 기준이다.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type AutoRules } from "../../api";
import { CHANNEL, label } from "../../app/labels";
import { useSession } from "../../app/session";
import { Banner, Button, EmptyState, PageHeader } from "../../ui";
import "./autorules.css";

const CRITERIA = ["우선순위 P3·P4", "긴급도 일반 (안전·설비 정지 아님)", "단일 문의 (복합 문의 제외)", "필수 정보가 모두 있음", "근거 문서가 있음",
  "답변 초안이 있고 발송 전 확인할 것이 없음 (인용·숫자, 막는 항목, 확인 표시)", "검증 AI 검사 통과 (⑤ 검증)"];
const DEFAULTS = { enabled: true, cats: { MANUAL: true, TECH_SPEC: true, FW_UPDATE: true, COMPLIANCE: false }, channels: { EMAIL: true, WEB_FORM: true, PHONE: false, CHAT: true, PARTNER_PORTAL: true } };

type Cfg = { enabled: boolean; cats: Record<string, boolean>; channels: Record<string, boolean> };

export function AutoRulesPage() {
  const { agent } = useSession();
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [local, setLocal] = useState<Cfg | null>(null); // 누른 값을 화면에 바로 보이는 임시 값(저장이 끝나면 서버 값으로 돌아간다)
  const q = useQuery({ queryKey: ["auto-rules"], queryFn: api.autoRules });
  const save = useMutation({
    mutationKey: ["auto-rules-save"],
    mutationFn: (body: Cfg) => api.saveAutoRules(body),
    onSuccess: () => { setError(""); void qc.invalidateQueries({ queryKey: ["inbox"] }); },
    onError: (e) => setError(e instanceof ApiError ? e.message : "저장하지 못했습니다. 다시 시도하세요"),
    // 연달아 누르면 앞 저장의 응답이 방금 바꾼 값을 덮어쓰지 않도록, 저장이 더 남아 있지 않을 때만 서버 값을 다시 읽고 임시 값을 버린다
    onSettled: async () => {
      if (qc.isMutating({ mutationKey: ["auto-rules-save"] }) <= 1) { await qc.invalidateQueries({ queryKey: ["auto-rules"] }); setLocal(null); }
    },
  });
  const server: AutoRules | undefined = q.data;
  if (!server) return <><PageHeader title="자동 처리 규칙" />{q.isError ? <Banner tone="neg" action={<Button size="sm" onClick={() => void q.refetch()}>새로고침</Button>}>불러오지 못함. 새로고침</Banner> : <EmptyState title="불러오는 중" />}</>;
  const r: AutoRules = local ? { ...server, ...local } : server;
  const set = (patch: Partial<Cfg>) => {
    const next: Cfg = { enabled: r.enabled, cats: r.cats, channels: r.channels, ...patch };
    setLocal(next);
    save.mutate(next);
  };
  const pct = r.stats.total ? Math.round((r.stats.auto_total / r.stats.total) * 100) : 0;
  const busy = false; // 저장 중에도 누를 수 있다(마지막 값이 서버에 남는다)

  return (
    <div className="auto">
      <PageHeader title="자동 처리 규칙"
        actions={<Button disabled={!agent || busy} onClick={() => set(DEFAULTS)}>기본값으로</Button>} />
      {!agent && <Banner tone="info">상단에서 상담원을 고르면 설정을 바꿀 수 있습니다. 바꾼 사람이 기록됩니다.</Banner>}
      {error && <Banner tone="neg">{error}</Banner>}

      <section className="ui-card auto-card" aria-label="자동 발송 스위치">
        <div className="auto-row">
          <div className="auto-grow"><b>검증 AI 자동 발송</b>
            <p className="auto-note">간단한 문의는 검증 AI가 확인해 사람 승인 없이 보내고, 복잡하거나 고위험인 문의는 상담원이 확인합니다. 켜면 아래 조건을 모두 만족하는 문의는 상담원 승인 없이 발송 기록이 남고, 상담원이 나중에 사후 검수합니다. 끄면 어떤 문의도 자동으로 보내지 않습니다.</p></div>
          <label className="auto-sw"><input type="checkbox" role="switch" aria-label="자동 발송" checked={r.enabled} disabled={!agent || busy} onChange={(e) => set({ enabled: e.target.checked })} />{r.enabled ? "켜짐" : "꺼짐"}</label>
        </div>
        <p className="auto-stat" data-testid="auto-stat">지금까지 자동 발송 <b>{r.stats.auto_total}건</b> (사후 검수 전 <b>{r.stats.auto_pending}건</b>) · 전체 {r.stats.total}건 중 {pct}%</p>
        <p className="auto-note">※ 이 시스템은 실제 메일을 보내지 않습니다. "발송"은 상담원 발송과 같이 발송 기록을 남기는 것입니다. 실제 메일을 연동하기 전에 먼저 이 스위치를 끄세요.</p>
      </section>

      <div className="auto-grid">
        <section className="ui-card auto-card" aria-label="문의 유형별">
          <h3>문의 유형별</h3>
          {r.auto_cats.map((c) => (
            <label key={c} className="auto-rule"><span className="auto-grow">{r.category_names[c] ?? c}</span>
              <span className="auto-sub">{r.cats[c] ? "자동 대상" : "사람 확인"}</span>
              <input type="checkbox" aria-label={`${r.category_names[c] ?? c} 자동 대상`} checked={!!r.cats[c]} disabled={!agent || !r.enabled || busy} onChange={(e) => set({ cats: { ...r.cats, [c]: e.target.checked } })} /></label>
          ))}
          {r.always_human.map((c) => (
            <div key={c} className="auto-rule is-locked"><span className="auto-grow">{r.category_names[c] ?? c}</span><span className="auto-sub">🔒 항상 사람 확인</span></div>
          ))}
        </section>
        <section className="ui-card auto-card" aria-label="채널별">
          <h3>채널별</h3>
          {r.channel_list.map((c) => (
            <label key={c} className="auto-rule"><span className="auto-grow">{label(CHANNEL, c)}</span>
              <span className="auto-sub">{r.channels[c] ? "자동 대상" : "사람 확인"}</span>
              <input type="checkbox" aria-label={`${label(CHANNEL, c)} 자동 대상`} checked={!!r.channels[c]} disabled={!agent || !r.enabled || busy} onChange={(e) => set({ channels: { ...r.channels, [c]: e.target.checked } })} /></label>
          ))}
          <p className="auto-note">어떤 채널이든 같은 기준으로 판정합니다.</p>
        </section>
      </div>

      <section className="ui-card auto-card" aria-label="자동 발송 조건">
        <h3>자동 발송 조건 <span className="auto-sub">모두 만족해야 함 · 고정 기준, 설정으로 바꿀 수 없음</span></h3>
        <ul className="auto-criteria">{CRITERIA.map((c) => <li key={c}>{c}</li>)}</ul>
        <p className="auto-note">하나라도 걸리면 상담원이 확인합니다. 자동 발송된 건은 접수함의 "자동 처리" 탭에서 사후 검수합니다.</p>
      </section>
    </div>
  );
}
