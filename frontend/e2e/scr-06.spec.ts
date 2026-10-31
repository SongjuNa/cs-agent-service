// SCR-06 운영 대시보드 수용 기준 (docs/frontend/screens/SCR-06-ops-dashboard.md). 실제 API(스냅샷), 읽기 실패만 page.route로 만든다.
import { expect, test } from "@playwright/test";
import { useSession } from "./session";

const API = "http://localhost:8000";
const AS_OF = "2026-09-30T23:59:00Z";
const summary = async (request: import("@playwright/test").APIRequestContext, days = 30) =>
  (await request.get(`${API}/dashboard/summary?as_of=${AS_OF}&days=${days}`)).json();
const kpi = (page: import("@playwright/test").Page, k: string) => page.locator(`[data-kpi="${k}"]`);

test.beforeEach(async ({ page }) => useSession(page, { dept: "TS_LV", agent: "leo", snapshot: true }));

test("SCR-06-AC-1: 숫자 카드와 한 줄 요약이 서버 집계와 같고 일별 접수 그래프가 보인다", async ({ page, request }) => {
  const d = await summary(request);
  await page.goto("/dashboard");
  await expect(page.getByTestId("ops-chart")).toBeVisible();
  await expect(kpi(page, "open").locator("b")).toContainText(String(d.open.total));
  await expect(kpi(page, "breach").locator("b")).toContainText(String(d.open.breach));
  const fr = Math.round((d.sla.fr_met / (d.sla.fr_met + d.sla.fr_breached)) * 100);
  await expect(kpi(page, "fr").locator("b")).toContainText(String(fr));
  await expect(page.getByTestId("ops-lead")).toContainText(`미해결 ${d.open.total}건 중 ${d.open.breach}건이 기한을 넘겼고 ${d.open.risk}건이 임박했습니다`);
  await expect(page.getByRole("link", { name: "운영 대시보드" })).toHaveAttribute("aria-current", "page");
});

test("SCR-06-AC-2: 기간을 90일로 바꾸면 서버에 days=90으로 다시 묻고 카드 설명이 '최근 90일'이 된다", async ({ page, request }) => {
  const d90 = await summary(request, 90);
  await page.goto("/dashboard");
  await expect(kpi(page, "fr")).toContainText("최근 30일");
  const asked = page.waitForRequest((r) => r.url().includes("/dashboard/summary") && r.url().includes("days=90"));
  await page.getByRole("group", { name: "기간" }).getByRole("button", { name: "90일" }).click();
  await asked;
  await expect(kpi(page, "fr")).toContainText("최근 90일");
  await expect(kpi(page, "fr")).toContainText(`충족 ${d90.sla.fr_met} · 위반 ${d90.sla.fr_breached}`);
});

test("SCR-06-AC-3: '기한 위반' 카드를 누르면 문의 배정 관리가 kind=breach로 열린다", async ({ page }) => {
  await page.goto("/dashboard");
  await kpi(page, "breach").click();
  await expect(page).toHaveURL(/\/admin\/assign\?kind=breach/);
  await expect(page.getByRole("heading", { name: "문의 배정 관리" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "사유" })).toHaveValue("breach");
});

test("SCR-06-AC-4: 부서 막대를 누르면 문의 배정 관리가 그 부서로 열린다", async ({ page, request }) => {
  const d = await summary(request);
  await page.goto("/dashboard");
  const bars = page.getByRole("region", { name: "부서별 병목" });
  await bars.locator("button.ops-bars__row").first().click();
  await expect(page).toHaveURL(new RegExp(`/admin/assign\\?dept=${d.by_dept[0].dept}`));
  await expect(page.getByRole("combobox", { name: "부서" })).toHaveValue(d.by_dept[0].dept);
});

test("SCR-06-AC-5: 읽기 요청이 실패하면 '불러오지 못함. 새로고침'이 보이고 [새로고침]을 누르면 다시 읽는다", async ({ page }) => {
  let fail = true;
  await page.route(/\/api\/dashboard\/summary/, (r) => (fail ? r.fulfill({ status: 500, body: "{}" }) : r.continue()));
  await page.goto("/dashboard");
  await expect(page.getByText("불러오지 못함. 새로고침")).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "새로고침" }).click();
  await expect(page.getByTestId("ops-chart")).toBeVisible();
});
