// SCR-03 머리 영역 (최신 목업에 맞춤, 변경 add-inbox-turn-depth): 접수 정보 줄, 지금 할 일·검토 모드 띠, 이전·다음 문의 이동.
import { expect, test } from "@playwright/test";
import { useSession } from "./session";

const rows = (page: import("@playwright/test").Page) => page.locator("table.ui-table tbody tr.is-link");

test("SCR-03-AC-22: 접수 정보 줄과 '지금 할 일' 띠(검토 모드 포함)가 머리 아래에 보인다", async ({ page, request }) => {
  // 재생 데이터 티켓은 처리 기록이 없어 "처리 중"으로 보이므로, 처리가 끝난 티켓(시연 접수본)을 API로 찾는다
  const list = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&size=200&include_closed=true")).json();
  let id = "";
  for (const r of list.rows) {
    const d = await (await request.get(`http://localhost:8000/tickets/${r.ticket_id}`)).json();
    if (!d.processing && d.run) { id = r.ticket_id; break; }
  }
  expect(id, "처리가 끝난 TS_LV 티켓(python -m jobs.run_tickets CSV1-000017)").not.toBe("");
  await useSession(page, { dept: "TS_LV" });
  await page.goto(`/tickets/${id}`);
  const now = page.getByTestId("now-strip");
  await expect(now).toBeVisible();
  await expect(now).toContainText(/내 차례|대기|완료/);
  await expect(now).toContainText(/검토 모드 · (상세 검토|일반 확인|빠른 확인)/);
  await expect(page.locator(".tk-recv")).toContainText(/접수 \d{4}-\d{2}-\d{2} \d{2}:\d{2} · /);
});

test("SCR-03-AC-23: 접수함에서 열면 'n / 전체'가 보이고, 다음 문의 버튼과 j·k 키로 접수함 순서대로 이동한다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  const ids = [...new Set((await rows(page).locator(".ui-tid").allInnerTexts()).map((t) => t.replace(/ #\d+$/, "").trim()))];
  expect(ids.length).toBeGreaterThan(2);
  await rows(page).first().click();
  await expect(page).toHaveURL(new RegExp(`/tickets/${ids[0]}$`));
  const nav = page.getByRole("group", { name: "이전·다음 문의" });
  await expect(nav).toContainText(`1 / ${ids.length}`);
  await expect(nav.getByRole("button", { name: /이전 문의/ })).toBeDisabled();
  await nav.getByRole("button", { name: /다음 문의/ }).click();
  await expect(page).toHaveURL(new RegExp(`/tickets/${ids[1]}$`));
  await page.keyboard.press("j");
  await expect(page).toHaveURL(new RegExp(`/tickets/${ids[2]}$`));
  await page.keyboard.press("k");
  await expect(page).toHaveURL(new RegExp(`/tickets/${ids[1]}$`));
});

test("SCR-03-AC-24: 탭 없이 '고객이 보낸 것'과 '보낼 것'이 나란히 있고, 그 아래에 '시스템이 판단한 것'과 '이력'이 순서대로 있다", async ({ page, request }) => {
  const list = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&size=200&include_closed=true")).json();
  let id = "";
  for (const r of list.rows) {
    const d = await (await request.get(`http://localhost:8000/tickets/${r.ticket_id}`)).json();
    if (!d.processing && d.run) { id = r.ticket_id; break; }
  }
  expect(id).not.toBe("");
  await useSession(page, { dept: "TS_LV" });
  await page.goto(`/tickets/${id}`);
  const customer = page.getByRole("region", { name: "고객이 보낸 것" });
  const send = page.getByRole("region", { name: "보낼 것" });
  await expect(customer).toBeVisible();
  await expect(send).toBeVisible();
  await expect(page.getByRole("tab", { name: /^고객이 보낸 것/ })).toHaveCount(0);
  const [c, s, sys, hist] = await Promise.all([customer.boundingBox(), send.boundingBox(),
    page.getByRole("region", { name: "시스템이 판단한 것" }).boundingBox(), page.getByRole("region", { name: "이력" }).boundingBox()]);
  expect(c!.x).toBeLessThan(s!.x); // 왼쪽 읽기, 오른쪽 쓰기
  expect(Math.abs(c!.y - s!.y)).toBeLessThan(5); // 같은 줄
  expect(sys!.y).toBeGreaterThan(Math.max(c!.y + c!.height, s!.y + s!.height) - 1); // 두 칸 아래
  expect(hist!.y).toBeGreaterThan(sys!.y);
  // 옛 탭 주소는 그 구역으로 스크롤한다
  await page.goto(`/tickets/${id}?tab=history`);
  await expect(page.getByRole("region", { name: "이력" })).toBeInViewport();
});
