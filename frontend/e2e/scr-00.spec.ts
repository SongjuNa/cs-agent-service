// SCR-00 공통 틀 수용 기준 (docs/frontend/screens/SCR-00-shell.md)
import { expect, test } from "@playwright/test";
import { api, useSession } from "./session";

test("SCR-00-AC-1: 부서 QA_CLAIM의 상담원 목록에 시연용 상담원이 '시연용'과 함께 보인다", async ({ page, request }) => {
  // 명단의 시연용 상담원 이름은 명세 예시(QA_CLAIM_AGENT_01)와 달라 명단에서 찾는다
  const roster: { name: string; dept: string; demo: boolean }[] = await (await request.get(api("/ref/agents"))).json();
  const demo = roster.find((a) => a.dept === "QA_CLAIM" && a.demo);
  expect(demo, "QA_CLAIM 시연용 상담원").toBeTruthy();
  await useSession(page, { dept: "QA_CLAIM" });
  await page.goto("/inbox");
  await page.getByTitle("부서·상담원 바꾸기").click();
  const select = page.getByRole("dialog", { name: "내 정보" }).getByLabel("상담원");
  await expect(select.locator("option", { hasText: `${demo!.name} · 시연용` })).toHaveCount(1);
});

test("SCR-00-AC-2: 고른 상담원이 요청 머리 X-Agent-Id로 간다", async ({ page }) => {
  // 쓰기 요청(임시 저장)은 상세 슬라이스에서 시험한다. 여기서는 틀이 보내는 요청으로 본다
  await useSession(page, { dept: "TS_LV" });
  await page.goto("/inbox");
  await page.getByTitle("부서·상담원 바꾸기").click();
  const req = page.waitForRequest((r) => r.url().includes("/api/me/workload"));
  const select = page.getByRole("dialog", { name: "내 정보" }).getByLabel("상담원");
  const first = await select.locator("option").nth(1).getAttribute("value");
  await select.selectOption(first!);
  expect((await req).headers()["x-agent-id"]).toBe(first);
});

test("SCR-00-AC-3: 부서를 고르지 않으면 '부서를 선택하세요'만 보이고 목록 요청을 보내지 않는다", async ({ page }) => {
  await useSession(page, {});
  const lists: string[] = [];
  page.on("request", (r) => { if (/\/api\/tickets(\?|$)/.test(r.url())) lists.push(r.url()); });
  await page.goto("/inbox");
  await expect(page.getByText("부서를 선택하세요", { exact: true })).toBeVisible();
  await expect(page.locator("table")).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(lists).toEqual([]);
});

test("SCR-00-AC-4: 미해결 360건 재생 + 스냅샷 + TS_LV, 종 알림은 1차 응답 경고가 먼저이고 CSV1-003951이 그 묶음에 있으며 12건 이하다", async ({ page }) => {
  // CSV1-003951의 담당은 명단 이름 zara(재생 W6, 운영진 ID → 명단 이름 C-131). 종 알림은 내 담당의 경고다(FR-047)
  await useSession(page, { dept: "TS_LV", agent: "zara", snapshot: true });
  await page.goto("/inbox");
  await page.getByRole("button", { name: /알림/ }).click();
  const items = page.getByTestId("bell-list").locator("[data-alert]");
  await expect(items.first()).toBeVisible();
  const list = await items.evaluateAll((els) => els.map((e) => [e.getAttribute("data-alert") ?? "", e.textContent ?? ""]));
  expect(list.length).toBeLessThanOrEqual(12);
  const kinds = list.map(([k]) => k);
  const firstRes = kinds.findIndex((k) => k.startsWith("RES_"));
  const lastFr = kinds.map((k) => k.startsWith("FR_")).lastIndexOf(true);
  if (firstRes >= 0) expect(lastFr).toBeLessThan(firstRes);
  expect(list.some(([k, text]) => k === "FR_AT_RISK" && text.includes("CSV1-003951"))).toBe(true);
});

test("SCR-00-AC-5: 새로고침해도 고른 부서·상담원·기준 시각이 그대로다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/inbox");
  await page.getByTitle("부서·상담원 바꾸기").click();
  const dialog = page.getByRole("dialog", { name: "내 정보" });
  await dialog.getByLabel("부서").selectOption("TS_LV");
  const agent = await dialog.getByLabel("상담원").locator("option").nth(1).getAttribute("value");
  await dialog.getByLabel("상담원").selectOption(agent!);
  await dialog.getByLabel("기준 시각").selectOption("snapshot");
  await page.reload();
  await expect(page.getByTitle("부서·상담원 바꾸기")).toContainText(agent!);
  await expect(page.getByTitle("부서·상담원 바꾸기")).toContainText("TS_LV");
  await expect(page.getByText("기준 시각: 스냅샷 2026-09-30 23:59 UTC")).toBeVisible();
});
