// 고객 챗봇이 질문에서 제품·에러 코드를 찾고 문서 표를 문장으로 풀어 쓰는 작은 도구(목업 lib/assist.ts에서 포털이 쓰는 것만)
import { ERROR_CODES, PRODUCTS } from "./portalData";

/** 질문에서 제품 찾기: 제품 코드 또는 제품명(예: MCCB 400AF)이 들어 있으면 그 제품 */
export function findProduct(q: string): string | undefined {
  const ql = q.toLowerCase().replace(/\s+/g, "");
  return Object.entries(PRODUCTS).find(([code, p]) => ql.includes(code.toLowerCase()) || ql.includes(p.product_name.toLowerCase().replace(/\s+/g, "")))?.[0];
}
export const findError = (q: string) => ERROR_CODES.find((c) => q.toLowerCase().includes(c.toLowerCase()));

/** 본문의 표(마크다운)를 "항목 값, 항목 값" 같은 문장으로 풀어 쓴다 */
export function flatten(body: string): string {
  const rows = body.split("\n").map((l) => l.trim()).filter((l) => l.startsWith("|") && !/^\|[\s|:-]+\|?$/.test(l)).map((l) => l.split("|").slice(1, -1).map((c) => c.trim()));
  if (rows.length < 2) return body;
  const [head, ...rest] = rows;
  return rest.slice(0, 4).map((r) => (head.length === 2 ? `${r[0]} ${r[1]}` : r.map((c, i) => (i === 0 ? c : `${head[i]} ${c}`)).join(", "))).join(" / ");
}
export const clip = (t: string, n: number) => { const x = flatten(t).replace(/\s+/g, " ").trim(); return x.length > n ? x.slice(0, n - 1) + "…" : x; };
