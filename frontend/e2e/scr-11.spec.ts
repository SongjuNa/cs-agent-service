// SCR-11 문의 배정 관리 수용 기준 (docs/frontend/screens/SCR-11-assign.md). 실제 API.
// 상태를 바꾸는 시험은 시험용 접수본(CSV1-004…)만 건드리고 끝나면 원래 담당으로 되돌린다. 시연 재생 데이터는 건드리지 않는다.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { useSession } from "./session";

const API = "http://localhost:8000";
const rows = (page: Page) => page.locator("table.ui-table tbody tr.is-link");

type Row = { sub_ticket_id: string; ticket_id: string; assignee_masked: string | null; assigned_dept: string };

/** 시험용 접수본(번호가 CSV1-004로 시작) 중 TS_LV 미해결을 n개 고른다 */
async function copies(request: APIRequestContext, n: number): Promise<Row[]> {
  const res = await (await request.get(`${API}/tickets?dept=TS_LV&q=CSV1-004&size=200`)).json();
  const mine = (res.rows as Row[]).filter((r) => r.assignee_masked && r.assigned_dept === "TS_LV");
  expect(mine.length, "시험용 접수본(python -m jobs.run_tickets CSV1-000017)").toBeGreaterThanOrEqual(n);
  return mine.slice(0, n);
}
const revert = (request: APIRequestContext, list: Row[]) =>
  Promise.all(list.map((r) => request.post(`${API}/sub-tickets/assign`, { headers: { "X-Agent-Id": "leo" }, data: { sub_ticket_ids: [r.sub_ticket_id], assignee: r.assignee_masked } })));

test("SCR-11-AC-1: 열면 내 부서 미해결 문의가 한 쪽 15건 이하로 나오고 '○건'이 서버 건수와 같다", async ({ page, request }) => {
  const api = await (await request.get(`${API}/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=1`)).json();
  await useSession(page, { dept: "TS_LV", agent: "leo", snapshot: true });
  await page.goto("/admin/assign");
  await expect(page.getByRole("heading", { name: "문의 배정 관리" })).toBeVisible();
  await expect(rows(page).first()).toBeVisible();
  expect(await rows(page).count()).toBeLessThanOrEqual(15);
  await expect(page.locator(".asg-count")).toHaveText(`${api.counts.total}건`);
  await expect(page.getByRole("combobox", { name: "부서" })).toHaveValue("TS_LV");
  await expect(page.getByRole("link", { name: "문의 배정 관리" })).toHaveAttribute("aria-current", "page"); // 왼쪽 메뉴에서 현재 화면
});

test("SCR-11-AC-2: 사유 '기한 초과'로 거르면 건수가 서버 값과 같고 모든 줄에 기한 지남 표시가 있다", async ({ page, request }) => {
  const api = await (await request.get(`${API}/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=1&alert=FR_BREACHED,RES_BREACHED`)).json();
  await useSession(page, { dept: "TS_LV", agent: "leo", snapshot: true });
  await page.goto("/admin/assign");
  await expect(rows(page).first()).toBeVisible();
  await page.getByRole("combobox", { name: "사유" }).selectOption("breach");
  await expect(page.locator(".asg-count")).toHaveText(`${api.counts.total}건`);
  await expect(page).toHaveURL(/kind=breach/);
  const first = rows(page).first();
  await expect(first).toContainText("지남");
});

test("SCR-11-AC-3: 줄의 담당 상담원을 바꾸면 안내 띠가 뜨고 서버의 담당이 바뀐다", async ({ page, request }) => {
  const [row] = await copies(request, 1);
  const agents: { name: string }[] = await (await request.get(`${API}/ref/agents?dept=TS_LV`)).json();
  const to = agents.find((a) => a.name !== row.assignee_masked)!.name;
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  try {
    await page.goto(`/admin/assign?q=${row.ticket_id}`);
    await expect(rows(page).first()).toBeVisible();
    await rows(page).first().getByRole("combobox", { name: /담당 상담원 변경/ }).selectOption(to);
    await expect(page.getByRole("status").filter({ hasText: `1건을 ${to}에게 재배정했습니다` })).toBeVisible();
    const after = await (await request.get(`${API}/tickets?dept=TS_LV&q=${row.ticket_id}&size=50`)).json();
    expect(after.rows.find((r: Row) => r.sub_ticket_id === row.sub_ticket_id).assignee_masked).toBe(to);
  } finally { await revert(request, [row]); }
});

test("SCR-11-AC-4: 여러 줄을 골라 [재배정]하면 모두 바뀌고 선택이 풀리며, [필터된 n건 모두 선택]이 거른 건수만큼 고른다", async ({ page, request }) => {
  const two = await copies(request, 2);
  const agents: { name: string }[] = await (await request.get(`${API}/ref/agents?dept=TS_LV`)).json();
  const to = agents.find((a) => !two.some((r) => r.assignee_masked === a.name))?.name ?? agents.find((a) => a.name !== two[0].assignee_masked)!.name;
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  try {
    await page.goto("/admin/assign?q=CSV1-004");
    await expect(rows(page).first()).toBeVisible();
    await rows(page).nth(0).getByRole("checkbox").check();
    const bar = page.getByRole("region", { name: "선택한 문의 재배정" });
    await expect(bar).toContainText("1건 선택");
    await bar.getByRole("button", { name: /필터된 \d+건 모두 선택/ }).click();
    const total = Number((await page.locator(".asg-count").innerText()).replace("건", ""));
    await expect(bar).toContainText(`${total}건 선택`);
    await bar.getByRole("button", { name: "선택 해제" }).click();
    // 두 건만 골라 재배정
    await page.goto(`/admin/assign?q=${two[0].ticket_id}`);
    await rows(page).first().getByRole("checkbox").check();
    await page.getByRole("region", { name: "선택한 문의 재배정" }).getByRole("combobox", { name: "받을 상담원" }).selectOption(to);
    await expect(page.getByRole("region", { name: "선택한 문의 재배정" }).getByRole("button", { name: "재배정" })).toBeEnabled();
    await page.getByRole("region", { name: "선택한 문의 재배정" }).getByRole("button", { name: "재배정" }).click();
    await expect(page.getByRole("status").filter({ hasText: `${to}에게 재배정했습니다` })).toBeVisible();
    await expect(page.getByRole("region", { name: "선택한 문의 재배정" })).toHaveCount(0); // 선택이 풀린다
  } finally { await revert(request, two); }
});
