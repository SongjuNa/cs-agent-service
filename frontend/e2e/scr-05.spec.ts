// SCR-05 전화 상담 수용 기준 (docs/frontend/screens/SCR-05-phone.md). 실제 API(받아쓰기 L9·메모 초안 L10 = Gemini).
// 운영진 데이터에 녹음이 없어 시험 통화는 e2e/calls/make_calls.py가 대본을 기계 음성으로 읽혀 만든다(없으면 여기서 만든다).
// 목은 두 곳만: AC-4(받아쓴 글에 없는 값이 든 메모 = 언어 모델이 잘못 쓴 상태, 실제 모델로는 일부러 만들 수 없음)와
// AC-6(받아쓰기 실패).
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { api, useSession } from "./session";

const CALLS = path.join(path.dirname(fileURLToPath(import.meta.url)), "calls");
const OUT = path.join(CALLS, "out");
const DB = process.env.E2E_DATABASE_URL ?? "postgresql://cs:change-me@localhost:5432/cs_agent"; // .env.example 기본값
const lastTicket = () => execFileSync("psql", [DB, "-qAtc", "SELECT max(ticket_id) FROM svc.ticket"], { encoding: "utf8" }).trim();
const plain = (s: string) => s.replace(/[\s-]/g, "").toUpperCase();

type Meta = { duration_sec: number; garbled: { start_sec: number; end_sec: number }; serial: string };
function calls(): Meta {
  if (!existsSync(path.join(OUT, "calls.json"))) execFileSync("python3", [path.join(CALLS, "make_calls.py")]);
  return JSON.parse(readFileSync(path.join(OUT, "calls.json"), "utf8"));
}

async function openPhone(page: Page) {
  await useSession(page, { dept: "TS_LV", agent: "zara" });
  await page.goto("/phone");
}

async function transcribe(page: Page, file: string) {
  await page.locator('input[type="file"]').setInputFiles(path.join(OUT, file));
  await page.getByLabel("고객 ID").fill("CUST-0350"); // CSV1-000017의 고객
  await page.getByLabel("제품 코드").fill("ACB-AS-2000");
  await page.getByTestId("transcribe").click();
  await expect(page.getByText("받아쓰기 중")).toBeVisible();
  await expect(page.getByTestId("utterance").first()).toBeVisible({ timeout: 240_000 });
}

test.describe.serial("또렷한 시험 통화", () => {
  test.setTimeout(300_000);
  let page: Page;
  let before = "";
  test.beforeAll(async ({ browser }) => {
    calls();
    page = await browser.newPage();
    await openPhone(page);
    await expect(page.getByText("통화가 끝난 뒤 녹음을 올리면 AI가 받아쓰고 영어 메모 초안을 만듭니다").first()).toBeVisible();
    before = lastTicket();
    await transcribe(page, "clear.wav");
  });
  test.afterAll(async () => page.close());

  test("SCR-05-AC-1: 상담원·고객이 번갈아 말하는 영어 통화 → 발화마다 말한 사람과 시작 시각, '받아쓰지 못한 구간' 없음", async () => {
    const lines = page.getByTestId("utterance");
    expect(await lines.count()).toBeGreaterThanOrEqual(10);
    const speakers = await lines.evaluateAll((els) => els.map((e) => e.getAttribute("data-speaker")));
    expect(new Set(speakers)).toEqual(new Set(["AGENT", "CUSTOMER"]));
    const turns = speakers.filter((s, i) => i > 0 && s !== speakers[i - 1]).length;
    expect(turns).toBeGreaterThanOrEqual(speakers.length / 2); // 번갈아 말함
    for (const who of await lines.locator(".ph-who").allInnerTexts()) expect(who).toMatch(/^(상담원|고객)\s+\d+:\d{2}$/);
    await expect(page.getByTestId("gap")).toHaveCount(0);
    await expect(page.getByTestId("call-info")).toContainText(/2:\d{2}/);
    await expect(page.getByTestId("call-info")).toContainText("COMPANY_2801_0350");
  });

  test("SCR-05-AC-3: 고객이 'LVB-2024-00117'을 불러 준 통화 → 필수 정보에 제조번호 ✓와 그 값, 메모 Provided에 같은 값", async () => {
    const serial = page.locator('[data-testid="provided"][data-field="serial_no"]');
    await expect(serial).toHaveClass(/is-found/);
    const value = await serial.locator(".ph-req__val b").innerText();
    expect(plain(value)).toBe(plain(calls().serial)); // 받아쓰기는 하이픈 없이 LVB202400117로 적기도 한다
    const memo = await page.getByTestId("memo").inputValue();
    expect(memo).toMatch(/Provided:/);
    expect(memo.slice(memo.indexOf("Provided:"))).toContain(value);
  });

  test("SCR-05-AC-5: 메모를 확인하고 [접수] → 채널 PHONE·본문 = 확인한 메모인 티켓, '티켓으로 저장됨'. [접수] 전에는 티켓이 없다", async ({ request }) => {
    expect(lastTicket()).toBe(before); // 받아쓰기·메모 초안은 저장하지 않는다(D36)
    const memo = `${await page.getByTestId("memo").inputValue()} Agent checked.`;
    await page.getByTestId("memo").fill(memo);
    await page.getByRole("button", { name: "접수", exact: true }).click();
    const saved = page.getByText(/CSV1-\d{6} 티켓으로 저장됨/);
    await expect(saved).toBeVisible({ timeout: 30_000 });
    const id = (await saved.innerText()).match(/CSV1-\d{6}/)![0];
    const t = (await (await request.get(api(`/tickets/${id}`))).json()).ticket;
    expect([t.channel, t.inquiry_body, t.customer_id]).toEqual(["PHONE", memo, "CUST-0350"]);
    await page.getByRole("button", { name: "티켓 상세 보기" }).click();
    await expect(page).toHaveURL(new RegExp(`/tickets/${id}`));
  });
});

test("SCR-05-AC-2: 가운데 20초를 알아들을 수 없게 만든 통화 → 그 자리에 '받아쓰지 못한 구간'과 시각, 지어낸 발화 없음", async ({ page }) => {
  test.setTimeout(300_000);
  calls();
  await openPhone(page);
  await transcribe(page, "garbled.wav");
  const gap = page.getByTestId("gap");
  await expect(gap.first()).toBeVisible();
  await expect(gap.first()).toHaveText(/^받아쓰지 못한 구간 \d+:\d{2}–\d+:\d{2} \(/);
  // 잡음이 통째로 덮은 줄(오류 코드 E17을 묻고 답하는 두 줄)이 받아쓴 글에 없어야 한다
  const said = (await page.locator(".ph-say").evaluateAll((els) => els.map((e) => (e as HTMLTextAreaElement).value))).join(" ");
  expect(said).not.toMatch(/E ?17|seventeen|error code/i);
  // 빈 구간 줄은 앞뒤 발화 사이에 있다(맨 앞도 맨 뒤도 아님)
  const items = await page.locator(".ph-lines > li").evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  const at = items.indexOf("gap");
  expect(at).toBeGreaterThan(0);
  expect(at).toBeLessThan(items.length - 1);
});

test("SCR-05-AC-4: 받아쓴 글에 없는 값이 든 메모 초안 → 그 항목에 '받아쓴 글에서 찾지 못함'", async ({ page, request }) => {
  // 목: 실제 받아쓰기 응답에서 제조번호 값 하나만 받아쓴 글에 없는 값으로 바꾼다. 대조 결과(found·message)는 서버 문구 그대로.
  // 실제 응답은 같은 녹음을 시험이 직접 보내 받는다(브라우저의 multipart 요청을 그대로 다시 보내면 파일이 깨짐)
  test.setTimeout(300_000);
  calls();
  await page.route("**/api/calls/transcribe", async (route) => {
    const res = await request.post(api("/calls/transcribe"), { timeout: 240_000, multipart: {
      file: { name: "clear.wav", mimeType: "audio/wav", buffer: readFileSync(path.join(OUT, "clear.wav")) },
      customer_id: "CUST-0350", language: "en", product_code: "ACB-AS-2000" } });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    body.provided = body.provided.map((p: { field_code: string }) => (p.field_code === "serial_no"
      ? { ...p, value: "LVB-2024-99999", found: false, message: "받아쓴 글에서 찾지 못함" } : p));
    await route.fulfill({ json: body });
  });
  await openPhone(page);
  await transcribe(page, "clear.wav");
  const serial = page.locator('[data-testid="provided"][data-field="serial_no"]');
  await expect(serial).toHaveClass(/is-missing/);
  await expect(serial).toContainText("LVB-2024-99999");
  await expect(serial).toContainText("받아쓴 글에서 찾지 못함");
  const n = await page.getByTestId("provided").count();
  await expect(page.getByTestId("provided-count")).toHaveText(`필수 정보 ${n - 1}/${n}`);
});

test("SCR-05-AC-6: 받아쓰기가 실패하면 '받아쓰기 실패'와 [다시 받아쓰기], 메모 칸에 직접 써서 접수할 수 있다", async ({ page, request }) => {
  test.setTimeout(120_000);
  calls();
  await page.route("**/api/calls/transcribe", (route) => route.fulfill({ status: 502, json: { detail: { message: "받아쓰기 실패" } } }));
  await openPhone(page);
  await page.locator('input[type="file"]').setInputFiles(path.join(OUT, "clear.wav"));
  await page.getByLabel("고객 ID").fill("CUST-0350");
  await page.getByTestId("transcribe").click();
  await expect(page.getByText("받아쓰기 실패")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 받아쓰기" }).first()).toBeVisible();
  const memo = "[Call note] Customer reports ACB terminals overheating. Urgency: SITE_DOWN. Provided: Serial number (nameplate)=LVB-2024-00117.";
  await page.getByTestId("memo").fill(memo);
  await page.getByRole("button", { name: "접수", exact: true }).click();
  const saved = page.getByText(/CSV1-\d{6} 티켓으로 저장됨/);
  await expect(saved).toBeVisible({ timeout: 30_000 });
  const id = (await saved.innerText()).match(/CSV1-\d{6}/)![0];
  const t = (await (await request.get(api(`/tickets/${id}`))).json()).ticket;
  expect([t.channel, t.inquiry_body]).toEqual(["PHONE", memo]);
});
