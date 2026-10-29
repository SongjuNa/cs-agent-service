// 티켓 상세 읽기 (SCR-03 "사용자 동작 → 시스템 반응" 화면 열기). 처리 중이면 2초마다 다시 읽고 끝나면 멈춘다.
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

const POLL_MS = 2000; // SCR-03 화면 상태 "처리 중: 2초마다 다시 읽고"

export const ticketKey = (id: string, asOf: string | null) => ["ticket", id, asOf] as const;

export function useTicket(id: string, asOf: string | null) {
  return useQuery({
    queryKey: ticketKey(id, asOf),
    queryFn: () => api.ticket(id, asOf),
    placeholderData: keepPreviousData, // 읽기 실패 때 이전 값을 흐리게 둔다(SCR-03 "상세 읽기 실패")
    refetchInterval: (q) => (q.state.data?.processing ? POLL_MS : false),
  });
}

export function useTimeline(id: string, enabled: boolean) {
  return useQuery({ queryKey: ["timeline", id], queryFn: () => api.timeline(id), enabled });
}

/** 쓰기 뒤 상세·이력·접수함을 다시 읽게 한다 */
export function useRefresh(id: string) {
  const qc = useQueryClient();
  return () => Promise.all([
    qc.invalidateQueries({ queryKey: ["ticket", id] }),
    qc.invalidateQueries({ queryKey: ["timeline", id] }),
    qc.invalidateQueries({ queryKey: ["inbox"] }),
  ]);
}
