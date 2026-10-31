// SCR-12 자동 처리 규칙 수용 기준 (docs/frontend/screens/SCR-12-auto-rules.md). 실제 API. 설정을 바꾸는 시험은 끝나면 원래 값으로 되돌린다.
// 전역 준비(global-setup.ts)가 시험 시작 때 자동 발송을 꺼 두므로 "원래 값"은 꺼짐이다.
import { expect, test, type APIRequestContext } from "@playwright/test";
import { useSession } from "./session";

const API = "http://localhost:8000";
type Rules = { enabled: boolean; cats: Record<string, boolean>; channels: Record<string, boolean>; always_human: string[]; stats: { auto_total: number; auto_pending: number; total: number } };
const read = async (r: APIRequestContext): Promise<Rules> => (await r.get(`${API}/auto-rules`)).json();
const restore = (r: APIRequestContext, o: Rules) => r.put(`${API}/auto-rules`, { headers: { "X-Agent-Id": "leo" }, data: { enabled: o.enabled, cats: o.cats, channels: o.channels } });

test("SCR-12-AC-1: 스위치 상태와 '지금까지 자동 발송' 통계가 서버 값과 같고, 고위험 유형은 잠겨 있으며 고정 조건이 보인다", async ({ page, request }) => {
  const r = await read(request);
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  await page.goto("/admin/auto");
  await expect(page.getByRole("heading", { name: "자동 처리 규칙" })).toBeVisible();
  const sw = page.getByRole("switch", { name: "자동 발송" });
  await expect(sw).toBeChecked({ checked: r.enabled });
  await expect(page.getByTestId("auto-stat")).toContainText(`자동 발송 ${r.stats.auto_total}건`);
  await expect(page.getByTestId("auto-stat")).toContainText(`사후 검수 전 ${r.stats.auto_pending}건`);
  const cats = page.getByRole("region", { name: "문의 유형별" });
  await expect(cats.locator(".is-locked")).toHaveCount(r.always_human.length); // 항상 사람 확인 6종은 잠금
  await expect(cats.locator(".is-locked").first()).toContainText("항상 사람 확인");
  await expect(page.getByRole("region", { name: "자동 발송 조건" })).toContainText("우선순위 P3·P4");
  await expect(page.getByRole("link", { name: "자동 처리 규칙" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("실제 메일을 보내지 않습니다")).toBeVisible(); // 한계를 숨기지 않는다
});

test("SCR-12-AC-2: 스위치를 켜고 유형을 끄면 서버에 저장되고, 스위치를 끄면 유형·채널을 바꿀 수 없으며, [기본값으로]가 기본 설정으로 되돌린다", async ({ page, request }) => {
  const original = await read(request);
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  try {
    await page.goto("/admin/auto");
    const sw = page.getByRole("switch", { name: "자동 발송" });
    await sw.setChecked(false);
    await expect.poll(async () => (await read(request)).enabled).toBe(false);
    await expect(page.getByRole("checkbox", { name: "매뉴얼 자동 대상" })).toBeDisabled(); // 꺼지면 유형 설정을 막는다
    await sw.setChecked(true);
    await expect.poll(async () => (await read(request)).enabled).toBe(true);
    const manual = page.getByRole("checkbox", { name: "매뉴얼 자동 대상" });
    await expect(manual).toBeEnabled();
    await manual.setChecked(false);
    await expect.poll(async () => (await read(request)).cats.MANUAL).toBe(false);
    await page.getByRole("button", { name: "기본값으로" }).click();
    await expect.poll(async () => { const x = await read(request); return [x.enabled, x.cats.MANUAL, x.cats.COMPLIANCE, x.channels.PHONE]; }).toEqual([true, true, false, false]);
  } finally { await restore(request, original); }
});

test("SCR-12-AC-3: 상담원을 고르지 않으면 안내 띠가 보이고 스위치·유형·기본값 단추가 꺼져 있다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV" });
  await page.goto("/admin/auto");
  await expect(page.getByText("상단에서 상담원을 고르면 설정을 바꿀 수 있습니다")).toBeVisible();
  await expect(page.getByRole("switch", { name: "자동 발송" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "기본값으로" })).toBeDisabled();
});

// ---- 화면 연동 (변경 add-auto-send-views). 자동 발송 건이 없어도 성립하는 값만 본다: 숫자는 서버가 센 값 그대로여야 한다.

test("SCR-12-AC-4: 접수함 [자동 처리] 단추의 숫자가 서버 counts.auto와 같고, 누르면 auto=true로 거른 목록이 열리며 줄은 모두 자동 발송 표시가 있다", async ({ page, request }) => {
  await useSession(page, { dept: "TS_LV", agent: "leo" });
  const q = (extra = "") => `${API}/tickets?dept=TS_LV&size=50${extra}`;
  const all = (await (await request.get(q())).json()).counts;
  await page.goto("/inbox?m=0");
  const chip = page.getByRole("button", { name: /^자동 처리/ });
  await expect(chip).toContainText(String(all.auto));
  await chip.click();
  await expect(page).toHaveURL(/auto=true/);
  const filtered = await (await request.get(q("&auto=true"))).json();
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  if (filtered.rows.length) await expect(page.locator(".inbox-auto").first()).toBeVisible();
  else await expect(page.getByText("처리할 티켓이 없습니다")).toBeVisible();
  await chip.click();
  await expect(page).not.toHaveURL(/auto=true/);
});

test("SCR-12-AC-5: 운영 대시보드 'AI 자동 처리율'과 'AI와 사람 처리 비중'이 서버 집계와 같다", async ({ page, request }) => {
  await useSession(page, { dept: "TS_LV", agent: "leo", snapshot: true });
  const d = await (await request.get(`${API}/dashboard/summary?days=30`)).json();
  await page.goto("/dashboard");
  const kpi = page.locator('[data-kpi="auto"]');
  if (d.auto.total) await expect(kpi.locator("b")).toContainText(String(Math.round((d.auto.sent / d.auto.total) * 100)));
  else await expect(kpi.locator("b")).toContainText("—");
  await expect(page.getByTestId("ops-auto-share")).toBeVisible();
});
