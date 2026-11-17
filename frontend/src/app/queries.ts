// 틀과 여러 화면이 같이 쓰는 서버 읽기 (principles §4: 서버 데이터는 TanStack Query).
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export const REFRESH_MS = 5 * 60 * 1000; // 접수함·업무 현황 5분 갱신 (화면 정의서 v1 0-4, FR-029 처리 6)

export function useDepartments() {
  return useQuery({ queryKey: ["ref", "departments"], queryFn: api.departments, staleTime: Infinity });
}

/** 이관 메일 연동 설정(add-escalation-mail-live). 켜져 있으면 실제 메일을 보내고 받는다 */
export function useMailConfig() {
  return useQuery({ queryKey: ["mail", "config"], queryFn: api.mailConfig, staleTime: Infinity });
}

export function useAgents() {
  return useQuery({ queryKey: ["ref", "agents"], queryFn: api.agents, staleTime: Infinity });
}

/** 부서의 접수함 건수만(요약 버튼, 왼쪽 메뉴 접수함 옆 수). 필터를 걸지 않은 값 */
export function useInboxCounts(dept: string, asOf: string | null, includeClosed = false, me = "") {
  return useQuery({
    queryKey: ["inbox-counts", { dept, asOf, includeClosed, me }],
    queryFn: () => {
      const q = new URLSearchParams({ dept, page: "1", size: "1" });
      if (asOf) q.set("as_of", asOf);
      if (includeClosed) q.set("include_closed", "true");
      if (me) q.set("me", me);
      return api.inbox(q);
    },
    select: (d) => d.counts,
    enabled: !!dept,
    refetchInterval: REFRESH_MS,
  });
}

/** 종 알림과 업무 현황이 같이 쓰는 GET /me/workload. 상담원은 요청 머리 X-Agent-Id로 간다 */
export function useWorkload(dept: string, agent: string, asOf: string | null) {
  return useQuery({
    queryKey: ["workload", { dept, agent, asOf }],
    queryFn: () => {
      const q = new URLSearchParams({ dept });
      if (asOf) q.set("as_of", asOf);
      return api.workload(q);
    },
    enabled: !!dept,
    refetchInterval: REFRESH_MS,
  });
}

/** 왼쪽 프로필 카드의 숫자(변경 add-shell-look): 내 담당 미해결·경고가 있는 건, 오늘 내가 처리한 건수 */
export function useMyStats(dept: string, asOf: string | null, agent: string) {
  const mine = useQuery({
    queryKey: ["my-stats", { dept, asOf, agent }],
    queryFn: () => {
      const q = new URLSearchParams({ dept, page: "1", size: "1", assignee: agent, me: agent });
      if (asOf) q.set("as_of", asOf);
      return api.inbox(q);
    },
    select: (d) => ({ open: d.counts.total, alert: d.counts.alert }),
    enabled: !!dept && !!agent,
    refetchInterval: REFRESH_MS,
  });
  const today = useQuery({
    queryKey: ["my-performance", { agent, asOf, span: 1 }],
    queryFn: () => { const p = new URLSearchParams({ days: "1" }); if (asOf) p.set("as_of", asOf); return api.performance(p); },
    select: (d) => d.daily[d.daily.length - 1]?.n ?? 0,
    enabled: !!agent,
    refetchInterval: REFRESH_MS,
  });
  return { open: mine.data?.open, alert: mine.data?.alert, today: today.data };
}
