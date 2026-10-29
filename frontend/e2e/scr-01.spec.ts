// SCR-01 접수 시뮬레이터 수용 기준 (docs/frontend/screens/SCR-01-intake-simulator.md). 실제 API, 실패 상태만 page.route로 만든다.
// AC-3·AC-5는 실제로 접수해 Gemini를 부르고, 만든 티켓은 DB에 남는다(e2e/ticket.ts와 같음).
import { expect, test, type Page } from "@playwright/test";
import { api, useSession } from "./session";

const field = (page: Page, name: string) => page.locator(".ui-field").filter({ has: page.locator(".ui-field__label", { hasText: name }) });
const input = (page: Page, name: string) => field(page, name).locator("input, select, textarea").first();
const step = (page: Page, name: string) => page.getByRole("list", { name: "접수 단계" }).getByText(name);

test.beforeEach(async ({ page }) => useSession(page, { dept: "TS_LV", agent: "leo" }));

test("SCR-01-AC-1: CSV1-000017을 불러오면 입력 6칸이 정답지 입력값으로 채워진다", async ({ page }) => {
  await page.goto("/intake");
  await page.getByLabel("시연용 문의 불러오기").selectOption("CSV1-000017");
  await expect(input(page, "고객 ID")).toHaveValue("CUST-0350");
  await expect(input(page, "채널")).toHaveValue("PHONE");
  await expect(input(page, "제품 코드")).toHaveValue("ACB-AS-2000");
  await expect(input(page, "고객 언어")).toHaveValue("en");
  await expect(input(page, "본문")).toHaveValue(/Terminal overheating/);
  // 접수 시각은 원본(2025-10-02T09:45:43)이 아니라 지금(FR-003 v1.5.2)
  const received = await input(page, "접수 시각").inputValue();
  expect(received.startsWith("2025-10-02")).toBe(false);
  expect(Math.abs(Date.parse(`${received}Z`) - Date.now())).toBeLessThan(5 * 60_000);
  await expect(field(page, "본문").getByText("불러옴")).toBeVisible();
  await expect(page.getByText("제목", { exact: true })).toHaveCount(0); // 제목·정답 칸은 없다(AC-003-1)
});

test("SCR-01-AC-2: 고객 ID CUST-9999로 접수하면 칸 아래 '고객 ID를 찾을 수 없음', ② 단계로 넘어가지 않는다", async ({ page }) => {
  await page.goto("/intake");
  await input(page, "고객 ID").fill("CUST-9999");
  await input(page, "본문").fill("The breaker trips repeatedly.");
  await page.getByRole("button", { name: "접수하고 처리 시작" }).click();
  await expect(field(page, "고객 ID")).toContainText("고객 ID를 찾을 수 없음");
  await expect(step(page, "문의 입력")).toHaveAttribute("aria-current", "step");
});

test("SCR-01-AC-6: 본문이 공백뿐이면 '내용을 입력하세요'", async ({ page }) => {
  await page.goto("/intake");
  await input(page, "고객 ID").fill("CUST-0350");
  await input(page, "본문").fill("   \n  ");
  await page.getByRole("button", { name: "접수하고 처리 시작" }).click();
  await expect(field(page, "본문")).toContainText("내용을 입력하세요");
});

test("SCR-01-AC-4: 언어 모델 호출 실패(목) — ② 단계에 '자동 처리 실패'와 [티켓 상세에서 다시 처리]", async ({ page, request }) => {
  const base = await (await request.get(api("/tickets/CSV1-004004"))).json();
  const failed = { ...base, processing: false, ticket: { ...base.ticket, ticket_id: "CSV1-900001" },
    run: { ...base.run, run_id: 999, status: "FAILED", last_step: "T2" },
    sub_tickets: base.sub_tickets.map((s: { sub_ticket: object }) => ({ ...s, drafts: [], sub_ticket: { ...s.sub_ticket, status: "NEW", pipeline_error: "언어 모델 호출 실패(시간 초과)" } })) };
  await page.route("**/api/tickets", (r) => r.request().method() === "POST"
    ? r.fulfill({ status: 201, json: { ticket_id: "CSV1-900001", processing: true, run_id: 999 } }) : r.fallback());
  await page.route(/\/api\/tickets\/CSV1-900001(\?.*)?$/, (r) => r.fulfill({ json: failed }));
  await page.route("**/api/runs/999/steps", (r) => r.fulfill({ json: { steps: [{ step_name: "T2", result: null, error: "LLM timeout" }] } }));
  await page.goto("/intake");
  await page.getByLabel("시연용 문의 불러오기").selectOption("CSV1-000017");
  await expect(input(page, "고객 ID")).toHaveValue("CUST-0350");
  await page.getByRole("button", { name: "접수하고 처리 시작" }).click();
  await expect(page.getByRole("heading", { name: "자동 처리 실패" })).toBeVisible();
  await expect(page.getByText("자동 처리 실패: T2")).toBeVisible();
  await expect(page.getByTestId("progress").locator('[data-state="fail"]')).toHaveText(/유형 분류와 요청 나누기/);
  await page.getByRole("button", { name: "티켓 상세에서 다시 처리" }).click();
  await expect(page).toHaveURL(/\/tickets\/CSV1-900001/);
});

test.describe("실제 접수", () => {
  test.setTimeout(300_000);

  test("SCR-01-AC-3: 유효한 입력을 접수하면 ② 진행 표시를 거쳐 ③에 티켓 번호와 담당 부서", async ({ page }) => {
    await page.goto("/intake");
    await page.getByLabel("시연용 문의 불러오기").selectOption("CSV1-000017");
    await expect(input(page, "고객 ID")).toHaveValue("CUST-0350");
    await page.getByRole("button", { name: "접수하고 처리 시작" }).click();
    await expect(page.getByTestId("progress")).toBeVisible();
    await expect(step(page, "자동 처리")).toHaveAttribute("aria-current", "step");
    await expect(page.getByTestId("done")).toBeVisible({ timeout: 240_000 });
    await expect(page.getByTestId("done-id")).toHaveText(/^CSV1-\d{6}$/);
    await expect(page.getByTestId("done-dept")).toContainText("저압기기 기술지원");
    await page.getByRole("button", { name: "티켓 상세 보기" }).click();
    await expect(page).toHaveURL(/\/tickets\/CSV1-\d{6}/);
  });

  test("SCR-01-AC-5: CSV1-000008(복합)을 접수하면 ③에 문의 2개가 유형·우선순위와 함께", async ({ page }) => {
    await page.goto("/intake");
    await page.getByLabel("시연용 문의 불러오기").selectOption("CSV1-000008");
    await expect(input(page, "고객 언어")).toHaveValue("ar");
    await page.getByRole("button", { name: "접수하고 처리 시작" }).click();
    await expect(page.getByTestId("done")).toBeVisible({ timeout: 240_000 });
    await expect(page.getByTestId("done-subs")).toHaveText(/^펌웨어 P\d, 매뉴얼 P\d$/);
    await expect(page.getByText(/접수함에 들어갔습니다/)).toBeVisible(); // 담당이 TS_LV가 아니다(N-01-03)
  });
});
