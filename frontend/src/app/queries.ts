// 틀과 여러 화면이 같이 쓰는 서버 읽기 (principles §4: 서버 데이터는 TanStack Query).
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export const REFRESH_MS = 5 * 60 * 1000; // 접수함·업무 현황 5분 갱신 (화면 정의서 v1 0-4, FR-029 처리 6)

export function useDepartments() {
  return useQuery({ queryKey: ["ref", "departments"], queryFn: api.departments, staleTime: Infinity });
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
