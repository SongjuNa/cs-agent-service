// SCR-07 고객 관리 수용 기준 (docs/frontend/screens/SCR-07-customers.md). 실제 API. 목은 쓰지 않는다.
// AC-1은 정답지 CSV1-000017(고객 CUST-0350)을 지금 시각으로 새로 접수한 사본을 쓴다(e2e/ticket.ts, Gemini 호출).
// 데모 DB에는 앞선 시험의 사본도 남아 있으므로 "모두 보인다"는 화면 행 수 = 서버 이력 수로 본다.
import { expect, test } from "@playwright/test";
import { api, useSession } from "./session";
import { intakeCopy } from "./ticket";

const rows = (page: import("@playwright/test").Page) => page.locator("table.ui-table tbody tr.is-link");

test("SCR-07-AC-1 CUST-0350 상세: 이력이 접수 시각 내림차순으로 모두 보이고 원본 번호 CSV1-000017 티켓이 있다", async ({ page, request }) => {
  test.setTimeout(300_000);
  const id = await intakeCopy(request, "CSV1-000017");
  const detail = await (await request.get(api("/customers/CUST-0350"))).json();
  await useSession(page, {});
  await page.goto("/customers");
  await page.getByLabel("고객 ID·고객사").fill("CUST-0350");
  await page.getByRole("button", { name: "검색" }).click();
  await rows(page).filter({ hasText: "CUST-0350" }).first().click();
  await expect(page).toHaveURL(/\/customers\/CUST-0350$/);
  await expect(page.getByTestId("customer-page")).toBeVisible();
  await expect(rows(page)).toHaveCount(detail.history.length);

  const mine = rows(page).filter({ hasText: id });
  await expect(mine).toHaveCount(1);
  await expect(mine).toContainText("CSV1-000017");
  const times = (await page.locator("table.ui-table tbody tr.is-link td:nth-child(3)").allInnerTexts()).map((t) => t.trim());
  expect(times).toEqual([...times].sort().reverse());
});

test("SCR-07-AC-2 나라별 탭에서 TH를 고르면 고객 33명이 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/customers");
  await page.getByRole("tab", { name: "나라별" }).click();
  await rows(page).filter({ has: page.locator("td:first-child", { hasText: /^TH$/ }) }).click();
  await expect(page).toHaveURL(/country=TH/);
  await expect(page.getByText("나라 TH")).toBeVisible();
  await expect(rows(page)).toHaveCount(33);
  const countries = (await page.locator("table.ui-table tbody tr.is-link td:nth-child(4)").allInnerTexts()).map((t) => t.trim());
  expect(new Set(countries)).toEqual(new Set(["TH"]));
});

test("SCR-07-AC-3 나라별 표에 나라가 20개다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/customers?tab=countries");
  await expect(rows(page)).toHaveCount(20);
});

test("SCR-07-AC-4 없는 고객 CUST-9999 상세 주소를 열면 '고객을 찾을 수 없습니다'가 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/customers/CUST-9999");
  await expect(page.getByText("고객을 찾을 수 없습니다 CUST-9999")).toBeVisible();
  await page.getByRole("button", { name: "고객 관리로" }).click();
  await expect(page).toHaveURL(/\/customers$/);
});
