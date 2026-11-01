// SCR-09 접수 이력(해결사례 검색) 수용 기준 (docs/frontend/screens/SCR-09-case-search.md). 실제 API, 목 없음.
// 팀 정답지는 2026-10-29 조장이 준 gold_set v1(80건)을 시연 DB eval.gold_set에 넣은 상태에서 본다.
// 마지막 시험(AC 아님)은 정답지 문의 사본을 새로 접수해(Gemini 호출) 티켓 상세 "비슷한 해결사례"와 [접수 이력에서 보기]를 본다.
import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { useSession } from "./session";
import { intakeCopy } from "./ticket";

const DB = process.env.E2E_DATABASE_URL ?? "postgresql://cs:change-me@localhost:5432/cs_agent"; // .env.example 기본값
const sql = (q: string) => execFileSync("psql", ["-v", "ON_ERROR_STOP=1", "-qAtc", q, DB], { encoding: "utf8" }).trim();
const rows = (page: Page) => page.locator("table.ui-table tbody tr.is-link");
const col = (page: Page, n: number) => page.locator(`table.ui-table tbody tr.is-link td:nth-child(${n})`);

test("SCR-09-AC-1 에러 코드 E.OC만 넣고 찾으면 같은 에러 코드 사례가 먼저 보이고 팀 정답지 문의의 사례가 없다", async ({ page }) => {
  const gold = new Set(sql("SELECT source_ticket_id FROM eval.gold_set WHERE source_ticket_id IS NOT NULL").split("\n").filter(Boolean));
  expect(gold.size).toBeGreaterThan(0); // 팀 정답지를 넣은 상태
  await useSession(page, {});
  await page.goto("/history");
  await expect(page.getByText("증상, 에러 코드, 제품 중 하나 이상을 넣어 찾으세요")).toBeVisible();
  await page.getByLabel("에러 코드").fill("E.OC");
  await page.getByRole("button", { name: "찾기" }).click();
  await expect(rows(page)).toHaveCount(20);
  const codes = (await col(page, 5).allInnerTexts()).map((t) => t.trim());
  expect(codes.every((c) => c.startsWith("E.OC"))).toBe(true); // E.OC 사례가 41건이라 20건 모두
  const tickets = (await col(page, 2).allInnerTexts()).map((t) => t.trim());
  expect(tickets.filter((t) => gold.has(t))).toEqual([]);
});

test("SCR-09-AC-2 네 칸이 모두 빈 채로 찾으면 '검색어를 입력하세요'가 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/history");
  await page.getByRole("button", { name: "찾기" }).click();
  await expect(page.getByText("검색어를 입력하세요")).toBeVisible();
  await expect(rows(page)).toHaveCount(0);
});

test("SCR-09-AC-3 결과 행을 누르면 원인·조치·결과가 있는 사례 상세가 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/history?error_code=E.OC");
  await rows(page).first().click();
  const detail = page.getByTestId("case-detail");
  await expect(detail).toBeVisible();
  for (const field of ["root_cause", "action_taken", "resolution_result"]) {
    const dd = detail.locator(`[data-field="${field}"] dd`);
    await expect(dd).not.toHaveText("—");
    await expect(dd).not.toBeEmpty();
  }
});

// AC는 아니다. FR-019 티켓 상세 "비슷한 해결사례"와 화면 명세 동작 표 [접수 이력에서 보기]
test("SCR-09 티켓 상세의 비슷한 해결사례에서 [접수 이력에서 보기]로 열면 그 제품으로 찾은 결과가 보인다", async ({ page, request }) => {
  test.setTimeout(300_000);
  const id = await intakeCopy(request, "CSV1-000017");
  await useSession(page, { dept: "TS_LV" });
  await page.goto(`/tickets/${id}?tab=system`);
  const block = page.getByTestId("judge-1").getByTestId("similar-cases");
  await expect(block).toContainText("참고용, 초안에는 쓰지 않음");
  const shown = await block.locator("[data-case]").evaluateAll((els) => els.map((e) => e.getAttribute("data-case")));
  expect(shown.length).toBeGreaterThan(0);
  expect(shown.length).toBeLessThanOrEqual(3);
  expect(shown).not.toContain("RC-0006"); // CSV1-000017 자기 사례
  await block.getByRole("button", { name: "접수 이력에서 보기" }).click();
  await expect(page).toHaveURL(/\/history\?.*product_code=ACB-AS-2000/);
  await expect(page.getByLabel("제품 코드")).toHaveValue("ACB-AS-2000");
  await expect(rows(page).first()).toBeVisible();
  expect(new Set((await col(page, 4).allInnerTexts()).map((t) => t.trim()))).toEqual(new Set(["ACB-AS-2000"]));
});
