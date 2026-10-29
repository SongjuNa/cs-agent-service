// 서버 데이터 기반 (principles §3). 서버에서 오는 값은 TanStack Query로만 읽고 바꾼다.
// 4xx는 다시 해도 같은 답이라 되풀이하지 않고, 5xx·연결 끊김만 한 번 더 시도한다.
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: { retry: false }, // 승인·보내기 같은 쓰기는 저절로 되풀이하지 않는다
  },
});
