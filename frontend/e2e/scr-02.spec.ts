// SCR-02 접수함 수용 기준 (docs/frontend/screens/SCR-02-inbox.md). 실제 API, 실패 상태만 page.route로 만든다.
import { expect, test, type Page } from "@playwright/test";
import { useSession } from "./session";

const rows = (page: Page) => page.locator("table.ui-table tbody tr.is-link");

/** 열 이름으로 그 열의 칸들을 읽는다 */
async function column(page: Page, header: string): Promise<string[]> {
  const heads = await page.locator("table.ui-table thead th").allInnerTexts();
  const i = heads.findIndex((h) => h.trim().startsWith(header));
  expect(i, `열 ${header}`).toBeGreaterThanOrEqual(0);
  return rows(page).locator(`td:nth-child(${i + 1})`).allInnerTexts();
}

test("SCR-02-AC-1: 요약 '전체 n'이 보이고 맨 위 행은 경고가 있으며 남은 시간이 가장 적다", async ({ page }) => {
  // 명세 Given은 미해결 360건 재생(TS_LV 67건). 재생 작업이 없어 지금 데이터(TS_AUTO)의 정렬 규칙만 본다
  await useSession(page, { dept: "TS_AUTO", snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  const n = await rows(page).count();
  await expect(page.getByRole("tab", { name: new RegExp(`^전체\\s*${n}$`) })).toBeVisible();
  const alerts = await column(page, "경고");
  expect(alerts[0].trim()).not.toBe("");
  const left = (await column(page, "남은 시간")).map((t) => Number(t.replace("−", "-").replace(/[^\d.-]/g, "")));
  const withAlert = left.filter((_, i) => alerts[i].trim() !== "");
  expect(left[0]).toBe(Math.min(...withAlert));
});

test("SCR-02-AC-2: '정보 요청 필요' 요약을 누르면 모든 행의 정보 요청 열이 '필요'다", async ({ page }) => {
  await useSession(page, { dept: "TS_AUTO", snapshot: true });
  await page.goto("/inbox");
  await page.getByRole("tab", { name: /^정보 요청 필요/ }).click();
  await expect(page).toHaveURL(/needs_info=true/);
  await expect(rows(page).first()).toBeVisible();
  for (const v of await column(page, "정보 요청")) expect(v.trim()).toBe("필요");
});

test("SCR-02-AC-3: CSV1-000008(→ CSV1-004003)을 접수하면 담당 부서 접수함에 '복합 2건 중 1'·'2건 중 2' 행이 있다", async ({ page }) => {
  // 두 하위 문의가 다른 부서(TS_ENERGY, GCS_L1)로 갔다. 부서마다 연다
  const found: string[] = [];
  await useSession(page, { dept: "TS_ENERGY" });
  await page.goto("/inbox?q=CSV1-004003");
  for (const dept of ["TS_ENERGY", "GCS_L1"]) {
    await page.evaluate((d) => localStorage.setItem("cs-agent-dept", d), dept);
    await page.goto("/inbox?q=CSV1-004003");
    await expect(page.getByTitle("부서·상담원 바꾸기")).toContainText(dept);
    await expect(rows(page).first()).toBeVisible();
    found.push(...(await column(page, "유형")));
  }
  expect(found.some((t) => t.includes("복합 2건 중 1"))).toBe(true);
  expect(found.some((t) => t.includes("복합 2건 중 2"))).toBe(true);
});

test("SCR-02-AC-4: 행을 누르면 그 티켓의 상세가 열린다", async ({ page }) => {
  await useSession(page, { dept: "TS_AUTO" });
  await page.goto("/inbox");
  const id = (await rows(page).first().locator(".ui-tid").innerText()).replace(/#\d+$/, "").trim();
  await rows(page).first().click();
  await expect(page).toHaveURL(new RegExp(`/tickets/${id}$`));
  await expect(page.getByText(id).first()).toBeVisible();
});

test("SCR-02-AC-5: 종료 포함이 꺼져 있으면 RESOLVED·CLOSED 행이 없다", async ({ page }) => {
  await useSession(page, { dept: "TS_AUTO" });
  const asked: string[] = [];
  page.on("request", (r) => { if (r.url().includes("/api/tickets?")) asked.push(r.url()); });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  expect(asked.every((u) => !u.includes("include_closed=true"))).toBe(true);
  for (const v of await column(page, "처리 상태")) expect(v).not.toMatch(/^(해결|종료)/);
});

test("SCR-02-AC-6: 부서를 고르지 않으면 '부서를 선택하세요'만 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/inbox");
  await expect(page.getByText("부서를 선택하세요", { exact: true })).toBeVisible();
  await expect(page.locator("table")).toHaveCount(0);
  await expect(page.getByRole("tab")).toHaveCount(0);
});

test("SCR-02-AC-7: 목록 요청이 실패하면 이전 목록이 흐리게 남고 실패 안내가 보인다", async ({ page }) => {
  await useSession(page, { dept: "TS_AUTO" });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  const before = await rows(page).count();
  // 실패 상태만 가짜로 만든다(principles §6)
  await page.route(/\/api\/tickets\?(?!.*size=1(&|$))/, (r) => r.fulfill({ status: 500, body: "{}" }));
  await page.getByRole("checkbox", { name: "복합 문의" }).check(); // 새 목록 요청을 일으킨다(실패)
  await expect(page.getByText("목록을 불러오지 못함. 새로고침")).toBeVisible();
  await expect(page.locator("table.ui-table--stale")).toBeVisible();
  expect(await rows(page).count()).toBe(before);
  await page.getByRole("button", { name: "새로고침" }).click();
  await expect(page.getByText("목록을 불러오지 못함. 새로고침")).toBeVisible();
});

test("SCR-02-AC-8: 상세로 갔다가 [접수함으로]를 누르면 같은 필터·쪽으로 돌아온다", async ({ page }) => {
  // 명세는 2쪽(50건 넘음). 지금 데이터는 한 쪽이라 필터·정렬이 지켜지는지로 본다. 2쪽은 재생 데이터가 생기면 바꾼다
  await useSession(page, { dept: "TS_AUTO" });
  await page.goto("/inbox?has_draft=true&sort=-received_at");
  await expect(rows(page).first()).toBeVisible();
  await rows(page).first().click();
  await expect(page).toHaveURL(/\/tickets\//);
  await page.getByRole("button", { name: /목록으로|접수함으로/ }).click();
  await expect(page).toHaveURL(/\/inbox\?.*has_draft=true/);
  await expect(page).toHaveURL(/sort=-received_at/);
  await expect(page.getByRole("tab", { name: /^미발송 초안/ })).toHaveAttribute("aria-selected", "true");
});
