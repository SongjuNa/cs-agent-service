// 접수함 주소 쿼리 ↔ GET /tickets 쿼리 (SCR-02, principles §4: 필터·정렬·쪽은 주소에 둔다).
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { REFRESH_MS } from "../../app/queries";

export const SIZE = 50; // FR-029 처리 7, SCR-02 입력 검증 "size는 50 고정"
export const ALL_ALERTS = "FR_AT_RISK,FR_BREACHED,RES_AT_RISK,RES_BREACHED"; // "아무 경고"
export const FILTER_KEYS = ["status", "priority", "alert", "channel", "needs_info", "has_draft", "composite", "include_closed", "q"] as const;

const LAST_KEY = "cs-inbox-url";

/** 접수함이 마지막으로 쓴 주소(상세의 [접수함으로]가 쓴다, SCR-02-AC-8). 탭을 닫으면 잊는다 */
export function lastInboxUrl(): string {
  try {
    return sessionStorage.getItem(LAST_KEY) ?? "/inbox";
  } catch {
    return "/inbox";
  }
}

export function rememberInboxUrl(url: string): void {
  try {
    sessionStorage.setItem(LAST_KEY, url);
  } catch {
    // 저장을 못 쓰면 [접수함으로]는 /inbox
  }
}

const ORDER_KEY = "cs-inbox-order";

/** 접수함이 지금 보여 주는 문의 번호 순서(복합 문의는 한 번). 상세의 이전·다음 문의 이동이 쓴다 */
export function rememberInboxOrder(ticketIds: string[]): void {
  try {
    sessionStorage.setItem(ORDER_KEY, JSON.stringify([...new Set(ticketIds)]));
  } catch {
    // 저장을 못 쓰면 이전·다음 이동이 없을 뿐이다
  }
}

export function inboxOrder(): string[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(ORDER_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function hasFilters(search: URLSearchParams): boolean {
  return FILTER_KEYS.some((k) => search.has(k));
}

/** 주소 쿼리 → GET /tickets 쿼리. 부서·기준 시각·쪽 크기를 더하고, 빈 값은 보내지 않는다 */
export function requestQuery(search: URLSearchParams, dept: string, asOf: string | null, agent = ""): URLSearchParams {
  const q = new URLSearchParams();
  for (const [k, v] of search) if (k !== "m" && v.trim()) q.set(k, v.trim()); // m은 화면의 보기 범위(주소에만 둔다)
  if (agent) {
    q.set("me", agent);
    if (search.get("m") !== "0") q.set("assignee", agent); // 처음 열면 내 담당만, m=0이면 팀 전체
  }
  q.set("dept", dept);
  q.set("size", String(SIZE));
  if (!q.has("page")) q.set("page", "1");
  if (asOf) q.set("as_of", asOf);
  return q;
}

export function useInbox(search: URLSearchParams, dept: string, asOf: string | null, agent = "") {
  const query = requestQuery(search, dept, asOf, agent);
  return useQuery({
    queryKey: ["inbox", query.toString()],
    queryFn: () => api.inbox(query),
    enabled: !!dept, // 부서를 고르지 않으면 목록 요청을 보내지 않는다 (SCR-00-AC-3)
    placeholderData: keepPreviousData, // 읽기 실패·다시 읽는 동안 이전 목록을 둔다 (화면 정의서 v1 0-4)
    refetchInterval: REFRESH_MS,
  });
}
