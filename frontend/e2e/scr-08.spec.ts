// SCR-08 기준정보 보기 수용 기준 (docs/frontend/screens/SCR-08-reference.md). 실제 API, 읽기만.
// 목은 AC-1의 "색인 없음" 한 곳뿐이다. 시연 DB의 문서 107개는 모두 절이 있어서, 실제 응답에서 한 문서의 절 수만 0으로 바꾼다
// (빈 상태, 2026-10-29 검토 자료 ①).
import { expect, test, type Page } from "@playwright/test";
import { api, useSession } from "./session";

const rows = (page: Page) => page.locator("table.ui-table tbody tr");

async function search(page: Page, text: string) {
  await page.getByRole("searchbox").fill(text);
  await page.getByRole("button", { name: "검색" }).click();
}

test("SCR-08-AC-1 문서 관리: 표가 107행이고, 절이 0인 문서에 '색인 없음'이 보인다", async ({ page, request }) => {
  await useSession(page, {});
  await page.goto("/docs");
  let seen = 0;
  for (let from = 1; from <= 107; from += 10) {
    await expect(page.getByText(`107행 중 ${from}–${Math.min(107, from + 9)}`)).toBeVisible();
    seen += await rows(page).count();
    if (from + 10 <= 107) await page.getByRole("button", { name: "다음 쪽" }).click();
  }
  expect(seen).toBe(107);
  await expect(page.getByText("색인 없음")).toHaveCount(0); // 실제 데이터에는 없다

  const real = await (await request.get(api("/ref/documents"))).json();
  const target = real[0].doc_id as string;
  await page.route("**/api/ref/documents", (route) =>
    route.fulfill({ json: real.map((d: { doc_id: string }) => (d.doc_id === target ? { ...d, chunk_count: 0 } : d)) }));
  await page.goto("/docs");
  await expect(page.getByText("색인 안 됨 1건")).toBeVisible();
  const first = rows(page).first(); // 색인 없는 문서가 맨 앞
  await expect(first).toContainText(target);
  await expect(first).toContainText("색인 없음");
});

test("SCR-08-AC-2 제품 목록: CSV1-000004의 제품 HMI-XGT-eXP60은 단가 520, 표준 납기 4주", async ({ page, request }) => {
  const gold = await (await request.get(api("/gold/tickets/CSV1-000004"))).json();
  expect(gold.product_code).toBe("HMI-XGT-eXP60");
  await useSession(page, {});
  await page.goto("/products");
  await search(page, "HMI-XGT-eXP60");
  const row = rows(page).filter({ hasText: "HMI-XGT-eXP60" });
  await expect(row).toHaveCount(1);
  // 열: 제품 코드, 이름, 제품군, 단가(USD), 표준 납기(주), 수명 상태, 보증(개월)
  await expect(row.locator("td").nth(3)).toHaveText("520");
  await expect(row.locator("td").nth(4)).toHaveText("4");
  await row.click();
  const detail = page.getByTestId("product-detail");
  await expect(detail).toContainText("520 USD");
  await expect(detail).toContainText("4주");
});

test("SCR-08-AC-3 우선순위 규칙: PR-02 조건과 P1", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/rules");
  await expect(page.getByRole("tab", { name: "우선순위 규칙" })).toHaveAttribute("aria-selected", "true");
  const row = rows(page).filter({ hasText: "PR-02" });
  await expect(row).toHaveCount(1);
  await expect(row.locator("td").nth(2)).toHaveText("urgency=SITE_DOWN 이고 Category ∈ {DEFECT, INSTALL, FW_UPDATE}");
  await expect(row.locator("td").nth(3)).toHaveText("P1");
});

test("SCR-08-AC-4 어느 표에도 고치기·올리기·색인 다시 만들기 버튼이 없다", async ({ page }) => {
  await useSession(page, {});
  const screens = ["/docs", "/rules", "/rules?tab=route", "/rules?tab=req", "/products", "/depts", "/etc?tab=sla"];
  for (const path of screens) {
    await page.goto(path);
    await expect(rows(page).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /고치|수정|편집|올리기|업로드|색인 다시|삭제|저장|추가/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "CSV 내려받기" })).toBeVisible();
  }
});

// AC는 아니다. 변경 add-reference-views 결정 4 「왜?」 → "규칙표에서 보기"가 그 규칙 행을 강조하는지 본다
test("SCR-08 「왜?」의 규칙표에서 보기: 우선순위·부서 배정 규칙 행이 강조된다", async ({ page, request }) => {
  const id = "CSV1-004004"; // 시연 티켓(원본 CSV1-000017)
  const sub = (await (await request.get(api(`/tickets/${id}`), { headers: { "X-Agent-Dept": "TS_LV" } })).json()).sub_tickets[0].sub_ticket;
  await useSession(page, { dept: "TS_LV" });
  for (const [rowId, ruleId, tab] of [["C-03", sub.priority_rule_id, "우선순위 규칙"], ["C-04", sub.routing_rule_id, "부서 배정 규칙"]]) {
    await page.goto(`/tickets/${id}?tab=system`);
    await page.getByTestId("judge-1").locator(`[data-row="${rowId}"]`).getByRole("button", { name: "왜?" }).click();
    await page.getByRole("button", { name: "규칙표에서 보기" }).click();
    await expect(page).toHaveURL(new RegExp(`/rules\\?.*rule=${ruleId}`));
    await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("tr.is-marked")).toContainText(ruleId);
  }
});
