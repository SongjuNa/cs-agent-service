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

test("SCR-02-AC-1: 미해결 360건 재생 + 스냅샷, TS_LV 요약 '전체 n'과 맨 위 행(경고 있음, 남은 시간 최소)", async ({ page, request }) => {
  // "전체 69" = 담당 67 + 이관받은 2(조장 결정 2026-10-29). 데모 접수·시험 사본이 TS_LV에 더해지므로 화면 수는 서버 counts.total로 본다
  const api = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=1")).json();
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  await expect(page.getByRole("tab", { name: new RegExp(`^전체\\s*${api.counts.total}$`) })).toBeVisible();
  expect(api.counts.total).toBeGreaterThanOrEqual(69);
  const alerts = await column(page, "경고");
  expect(alerts[0].trim()).not.toBe("");
  const left = (await column(page, "남은 시간")).map((t) => Number(t.replace("−", "-").replace(/[^\d.-]/g, "")));
  const withAlert = left.filter((v, i) => alerts[i].trim() !== "" && !Number.isNaN(v));
  expect(left[0]).toBe(Math.min(...withAlert));
});

test("SCR-02-AC-2: '정보 요청 필요' 요약을 누르면 모든 행의 정보 요청 열이 '필요'다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV", snapshot: true });
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

test("SCR-02-AC-8: 2쪽을 보다가 상세로 갔다가 [접수함으로]를 누르면 같은 필터의 2쪽이 보인다", async ({ page }) => {
  // TS_LV 스냅샷은 50건이 넘어 2쪽이 있다(재생 W6). 상세의 버튼 이름은 상세 슬라이스에서 [접수함으로]로 바꾼다
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/inbox?sort=-received_at");
  await expect(rows(page).first()).toBeVisible();
  const firstOnPage1 = await rows(page).first().locator(".ui-tid").innerText();
  await page.getByRole("button", { name: "2", exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  // 응답이 느리면 화면이 이전 목록(1쪽)을 흐리게 남겨 두므로, 2쪽의 새 목록이 올 때까지 기다린 뒤 첫 줄을 읽는다
  await expect(rows(page).first().locator(".ui-tid")).not.toHaveText(firstOnPage1);
  await expect(page.locator("table.ui-table--stale")).toHaveCount(0);
  const firstOnPage2 = await rows(page).first().locator(".ui-tid").innerText();
  await rows(page).first().click();
  await expect(page).toHaveURL(/\/tickets\//);
  await page.getByRole("button", { name: /목록으로|접수함으로/ }).click();
  await expect(page).toHaveURL(/\/inbox\?.*sort=-received_at/);
  await expect(page).toHaveURL(/page=2/);
  await expect(rows(page).first().locator(".ui-tid")).toHaveText(firstOnPage2);
});

test("SCR-02-AC-9: 행을 고르면 선택 막대가 나오고 [내보내기 (CSV)]가 고른 행만 저장한다", async ({ page }) => {
  await useSession(page, { dept: "TS_AUTO" });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "선택한 문의 일괄 처리" })).toHaveCount(0);
  const ids = await rows(page).locator(".ui-tid").allInnerTexts();
  await rows(page).nth(0).getByRole("checkbox").check();
  await rows(page).nth(1).getByRole("checkbox").check();
  await expect(page.getByText("2건 선택")).toBeVisible();
  await expect(page).toHaveURL(/\/inbox/); // 체크 칸을 눌러도 상세로 가지 않는다
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "내보내기 (CSV)" }).click()]);
  expect(download.suggestedFilename()).toBe("접수함_2건.csv");
  const text = (await (await import("node:fs/promises")).readFile(await download.path()!, "utf8"));
  expect(text.split("\r\n")).toHaveLength(3); // 머리 + 2행
  expect(text).toContain(ids[0]);
  expect(text).toContain(ids[1]);
  await page.getByRole("button", { name: "선택 해제" }).click();
  await expect(page.getByText("2건 선택")).toHaveCount(0);
});

test("SCR-02-AC-10: 채널 칸은 티켓 번호 옆에 있고, 새로 접수된(신규) 행에만 NEW 태그가 붙는다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  const heads = (await page.locator("table.ui-table thead th").allInnerTexts()).map((h) => h.trim());
  expect(heads.indexOf("채널")).toBe(heads.indexOf("티켓 번호") + 1);
  const status = await column(page, "처리 상태");
  const chan = await column(page, "채널");
  chan.forEach((c, i) => expect(c.includes("NEW")).toBe(status[i].trim().startsWith("신규")));
});

test("SCR-02-AC-11: 요약 탭에 회신 대기·이관이 있고, 새 문의 칩과 부제의 기한 초과·임박 수가 서버 counts와 같다", async ({ page, request }) => {
  const api = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=1")).json();
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  const c = api.counts;
  if (c.waiting) await expect(page.getByRole("tab", { name: new RegExp(`^회신 대기\\s*${c.waiting}$`) })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^이관/ })).toBeVisible();
  if (c.breach) await expect(page.getByText(new RegExp(`기한 초과 ${c.breach}`))).toBeVisible();
  if (c.risk) await expect(page.getByText(new RegExp(`기한 임박 ${c.risk}`))).toBeVisible();
  // 회신 대기 탭 → 모든 행이 고객 회신 대기
  await page.getByRole("tab", { name: /^회신 대기/ }).click();
  await expect(page).toHaveURL(/status=WAITING_CUSTOMER/);
  // 응답이 느리면 이전 목록이 남아 있으므로, 모든 줄이 고객 회신 대기가 될 때까지 기다린다
  await expect.poll(async () => { const v = await column(page, "처리 상태"); return v.length > 0 && v.every((t) => /^고객 회신 대기|^회신 대기/.test(t.trim())); }).toBe(true);
  // 새 문의 칩 → status=NEW, 다시 누르면 풀린다
  await page.getByRole("tab", { name: /^전체/ }).click();
  const chip = page.getByRole("button", { name: /^새 문의/ });
  await chip.click();
  await expect(page).toHaveURL(/status=NEW/);
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await chip.click();
  await expect(page).not.toHaveURL(/status=NEW/);
});

test("SCR-02-AC-12: 상담원을 고르면 '내 담당'만 보이고 '팀 전체'로 바꿀 수 있으며, 내가 처리할 문의 묶음이 맨 위에 다음 행동과 함께 나온다", async ({ page, request }) => {
  const team = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=200")).json();
  const name: string = team.rows.find((r: { assignee_masked: string | null; turn: string }) => r.assignee_masked && r.turn === "ME").assignee_masked;
  const mine = await (await request.get(`http://localhost:8000/tickets?dept=TS_LV&as_of=2026-09-30T23:59:00Z&size=1&assignee=${name}&me=${name}`)).json();
  await useSession(page, { dept: "TS_LV", agent: name, snapshot: true });
  await page.goto("/inbox");
  await expect(rows(page).first()).toBeVisible();
  // 내 담당: 건수와 부제, 묶음 머리, 다음 행동, [다음 문의 처리 시작]
  await expect(page.getByRole("button", { name: /^내 담당/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: /^내 담당/ })).toContainText(String(mine.counts.mine));
  await expect(page.getByText(`내 담당 ${mine.counts.total}건 중`)).toBeVisible();
  await expect(page.locator("tr.ui-table__group").first()).toContainText("내가 처리할 문의");
  const status = await column(page, "처리 상태");
  expect(status.length).toBe(Math.min(mine.counts.total, 50));
  expect(status[0]).toMatch(/→ /); // 내 차례 줄은 "→ 다음 행동"
  const start = page.getByRole("button", { name: /다음 문의 처리 시작/ });
  const firstId = await rows(page).first().locator(".ui-tid").innerText();
  await expect(start).toContainText(firstId.replace(/ #\d+$/, ""));
  // 팀 전체
  await page.getByRole("button", { name: /^팀 전체/ }).click();
  await expect(page).toHaveURL(/m=0/);
  await expect(page.getByText(new RegExp(`팀 전체 ${team.counts.total}건 중`))).toBeVisible();
  // 열 머리 정렬을 누르면 묶음 머리가 사라진다
  await page.locator("table.ui-table thead th", { hasText: "접수 시각" }).click();
  await expect(page.locator("tr.ui-table__group")).toHaveCount(0);
});

test("SCR-02-AC-13 (최신 목업): 행을 골라 [담당자 변경…] → [변경]하면 담당이 바뀌고 안내 띠가 나오며, 이력에 '담당 변경'이 남는다", async ({ page, request }) => {
  // 시연 데이터를 건드리지 않도록 처리가 끝난 시험용 접수본(TS_LV)을 고르고, 시험이 끝나면 원래 담당으로 되돌린다
  const list = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&size=200&include_closed=true")).json();
  let row: { sub_ticket_id: string; ticket_id: string; assignee_masked: string } | null = null;
  for (const r of list.rows) {
    const d = await (await request.get(`http://localhost:8000/tickets/${r.ticket_id}`)).json();
    if (!d.processing && d.run && r.assignee_masked && r.assigned_dept === "TS_LV" && r.status !== "CLOSED" && r.status !== "RESOLVED") { row = r; break; }
  }
  expect(row, "처리가 끝난 TS_LV 접수본").not.toBeNull();
  const original = row!.assignee_masked;
  const agents: { name: string; dept: string }[] = await (await request.get("http://localhost:8000/ref/agents?dept=TS_LV")).json();
  const to = agents.find((a) => a.name !== original)!.name;
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  try {
    await page.goto(`/inbox?q=${row!.ticket_id}&m=0&include_closed=true`);
    const tr = page.locator("table.ui-table tbody tr.is-link").filter({ hasText: row!.ticket_id }).first();
    await tr.getByRole("checkbox").check();
    const bar = page.getByRole("region", { name: "선택한 문의 일괄 처리" });
    await expect(bar.getByRole("button", { name: "변경", exact: true })).toBeDisabled(); // 상담원을 고르기 전에는 꺼짐
    await bar.getByRole("combobox", { name: "넘길 상담원" }).selectOption(to);
    await bar.getByRole("button", { name: "변경", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: `${to}에게 넘겼습니다` })).toBeVisible();
    await expect(page.getByText("건 선택")).toHaveCount(0); // 선택이 풀린다
    const after = await (await request.get(`http://localhost:8000/tickets?dept=TS_LV&q=${row!.ticket_id}&include_closed=true`)).json();
    expect(after.rows.find((r: { sub_ticket_id: string }) => r.sub_ticket_id === row!.sub_ticket_id).assignee_masked).toBe(to);
    const events = (await (await request.get(`http://localhost:8000/tickets/${row!.ticket_id}/timeline`)).json()).filter((e: { kind: string }) => e.kind === "ASSIGNEE");
    expect(events.at(-1)).toMatchObject({ from_assignee: original, to_assignee: to, changed_by: "leo" });
  } finally {
    await request.post("http://localhost:8000/sub-tickets/assign", { headers: { "X-Agent-Id": "leo" }, data: { sub_ticket_ids: [row!.sub_ticket_id], assignee: original } });
  }
});

test("SCR-02-AC-14 (최신 목업): 행을 골라 [우선순위 조정]에서 새 우선순위·사유를 넣으면 건마다 조정되고 안내 띠가 뜨며, 이미 그 우선순위인 건은 건너뛴다", async ({ page, request }) => {
  type R = { sub_ticket_id: string; ticket_id: string; priority: string; assigned_dept: string; status: string };
  const res = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&q=CSV1-004&size=200")).json();
  const two: R[] = (res.rows as R[]).filter((r) => r.assigned_dept === "TS_LV" && r.priority).slice(0, 2); // 시험용 접수본만
  expect(two.length, "시험용 접수본 2건 이상").toBe(2);
  const target = ["P1", "P2", "P3", "P4"].find((p) => two.some((r) => r.priority !== p) && p !== "P1") ?? "P3"; // 적어도 한 건은 바뀌는 값
  const changing = two.filter((r) => r.priority !== target);
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  try {
    await page.goto("/inbox?q=CSV1-004&m=0&include_closed=true");
    await expect(rows(page).first()).toBeVisible();
    for (const r of two) await page.locator("table.ui-table tbody tr.is-link").filter({ hasText: r.ticket_id }).first().getByRole("checkbox").check();
    await page.getByRole("button", { name: "우선순위 조정" }).click();
    const dlg = page.getByRole("dialog", { name: /우선순위 일괄 조정/ });
    await dlg.getByRole("combobox", { name: "새 우선순위" }).selectOption(target);
    await expect(dlg.getByRole("button", { name: /건 적용$/ })).toBeDisabled(); // 사유를 쓰기 전에는 꺼짐
    await dlg.getByRole("combobox", { name: "사유 분류" }).selectOption("CUSTOMER_REQUEST");
    await dlg.getByRole("textbox", { name: "사유" }).fill("일괄 조정 시험");
    await expect(dlg.getByTestId("bulk-adjust-note")).toContainText("다시 계산됩니다");
    await dlg.getByRole("button", { name: `${changing.length}건 적용` }).click();
    await expect(page.getByRole("status").filter({ hasText: `${changing.length}건의 우선순위를 ${target}로 조정했습니다` })).toBeVisible();
    const after = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&q=CSV1-004&size=200&include_closed=true")).json();
    for (const r of two) expect(after.rows.find((x: R) => x.sub_ticket_id === r.sub_ticket_id).priority).toBe(target);
  } finally {
    // 원래 우선순위로 되돌린다(시험용 접수본이라 이력이 남아도 된다)
    for (const r of changing) {
      const p = await (await request.get(`http://localhost:8000/sub-tickets/${r.sub_ticket_id}/priority?new_priority=${r.priority}`)).json();
      await request.post(`http://localhost:8000/sub-tickets/${r.sub_ticket_id}/priority`, { headers: { "X-Agent-Id": "leo" },
        data: { new_priority: r.priority, reason_kind: "OTHER", reason_text: "시험 되돌리기", confirm_breach: true, expected_version: p.version } });
    }
  }
});
