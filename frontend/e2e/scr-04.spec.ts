// SCR-04 나의 업무 현황 수용 기준 (docs/frontend/screens/SCR-04-my-work.md). 실제 API. 목은 쓰지 않는다.
// AC-2~5·7은 정답지 문의를 지금 시각으로 새로 접수한 사본을 쓴다(e2e/ticket.ts, Gemini 호출). 데모 DB에는 앞선 시험의
// 사본도 남아 있으므로 "몇 건"은 시험 전후 서버 값의 차이와 화면 = 서버 값으로 본다.
// 시간이 흘러야 생기는 상태(정보 요청 뒤 130h, 접수 뒤 200h)는 백엔드 시험(tests/acceptance/test_my_work.py)처럼
// 시험 준비로만 DB 시각을 옮긴다. 옮기는 행은 이 시험이 만든 사본뿐이다.
import { execFileSync } from "node:child_process";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { api, useSession } from "./session";
import { H, intakeCopy } from "./ticket";

const DB = process.env.E2E_DATABASE_URL ?? "postgresql://cs:change-me@localhost:5432/cs_agent"; // .env.example 기본값
const sql = (q: string) => execFileSync("psql", ["-v", "ON_ERROR_STOP=1", "-qAtc", q, DB], { encoding: "utf8" }).trim();

const SNAPSHOT = "2026-09-30T23:59:00Z";
const AGENT = "zara"; // TS_LV 명단(app/roster/agent_roster.json)
const rows = (page: Page) => page.locator("table.ui-table tbody tr.is-link");
const ago = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();
const tile = (page: Page, area: string) => page.locator(`[data-tile="${area}"] b`);

async function workload(request: APIRequestContext, q: Record<string, string>, agent?: string) {
  const res = await request.get(api(`/me/workload?${new URLSearchParams(q)}`), { headers: agent ? { "X-Agent-Id": agent } : {} });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/** 한 탭의 모든 쪽을 넘기며 행 글자를 모은다 */
async function allRows(page: Page): Promise<string[]> {
  const out: string[] = [];
  for (;;) {
    await expect(rows(page).first()).toBeVisible();
    out.push(...(await rows(page).allInnerTexts()));
    const next = page.getByRole("button", { name: /다음/ });
    if (!(await next.count()) || (await next.isDisabled())) return out;
    await next.click();
  }
}

async function openMine(page: Page, dept: string, agent: string, scope: "mine" | "dept", tab = "risks") {
  await useSession(page, { dept, agent });
  await page.addInitScript((s) => localStorage.setItem("cs-my-scope", s), scope);
  await page.goto(`/my?tab=${tab}`);
  await expect(page.getByTestId("greet")).toBeVisible();
}

async function firstSub(request: APIRequestContext, id: string) {
  const d = await (await request.get(api(`/tickets/${id}`))).json();
  return d.sub_tickets[0];
}

async function sendDraft(request: APIRequestContext, id: string, agent: string, dept: string) {
  const s = await firstSub(request, id);
  const draft = s.drafts.find((m: { message_status: string }) => m.message_status === "DRAFT");
  const res = await request.post(api(`/messages/${draft.message_id}/send`), {
    headers: H(dept, agent), data: { final_body: draft.body, override_check: true, expected_version: s.version } });
  expect(res.ok(), await res.text()).toBeTruthy();
  return s.sub_ticket.sub_ticket_id as string;
}

test("SCR-04-AC-1: 미해결 360건 재생 + 스냅샷 + TS_LV, 기한 위험·위반 표에 해결 AT_RISK 8, BREACHED 26, CSV1-003951", async ({ page, request }) => {
  // 재생 행(CSV1-004000 이하)만 센다. 그 위는 데모 접수·시험 사본
  await useSession(page, { dept: "TS_LV", agent: AGENT, snapshot: true });
  await page.addInitScript(() => localStorage.setItem("cs-my-scope", "dept"));
  await page.goto("/my");
  const replay = (await allRows(page)).filter((t) => (t.match(/CSV1-(\d{6})/)?.[1] ?? "999999") < "004001");
  const breached = replay.filter((t) => t.includes("해결 기한 지남"));
  const atRisk = replay.filter((t) => t.includes("해결 기한 임박") && !t.includes("해결 기한 지남"));
  const rest = replay.filter((t) => !breached.includes(t) && !atRisk.includes(t));
  expect([atRisk.length, breached.length]).toEqual([8, 26]);
  expect(rest.map((t) => t.match(/CSV1-\d{6}/)?.[0])).toEqual(["CSV1-003951"]);
  expect(rest[0]).toContain("1차 응답 임박");
  const w = await workload(request, { dept: "TS_LV", scope: "dept", as_of: SNAPSHOT });
  await page.goto("/my");
  await expect(tile(page, "risks")).toHaveText(String(w.tiles.risks));
});

test.describe.serial("새로 접수한 사본으로", () => {
  test.setTimeout(600_000);
  let a = ""; // CSV1-000017 사본 1 (TS_LV, 정보 요청 초안)
  let b = ""; // CSV1-000017 사본 2

  test("SCR-04-AC-2: 정보 요청 초안 2건을 만들면 타일 ①이 2 늘고 승인 대기 초안 표에 두 줄이 있다", async ({ page, request }) => {
    const before = (await workload(request, { dept: "TS_LV", scope: "dept" })).tiles.drafts;
    a = await intakeCopy(request, "CSV1-000017");
    b = await intakeCopy(request, "CSV1-000017");
    const after = await workload(request, { dept: "TS_LV", scope: "dept" });
    expect(after.tiles.drafts).toBe(before + 2);
    await openMine(page, "TS_LV", AGENT, "dept", "drafts");
    await expect(tile(page, "drafts")).toHaveText(String(after.tiles.drafts));
    const texts = await allRows(page);
    for (const id of [a, b]) {
      const row = texts.find((t) => t.includes(id));
      expect(row, id).toBeTruthy();
      expect(row).toContain("정보 요청");
    }
  });

  test("SCR-04-AC-4: CSV1-000017 사본을 FIELD_SVC로 이관하면 TS_LV 이관 회신 대기 줄에 이관 부서와 이관 시각", async ({ page, request }) => {
    const s = await firstSub(request, a);
    const res = await request.post(api(`/sub-tickets/${s.sub_ticket.sub_ticket_id}/escalate`), {
      headers: H("TS_LV", AGENT), data: { dept: "FIELD_SVC", reason_code: "ONSITE_REQUIRED", memo: "현장 방문 필요", expected_version: s.version } });
    expect(res.ok(), await res.text()).toBeTruthy();
    await openMine(page, "TS_LV", AGENT, "dept", "waiting_escalation");
    const row = (await allRows(page)).find((t) => t.includes(a));
    expect(row).toContain("FIELD_SVC");
    const day = new Date().toISOString().slice(0, 10);
    expect(row).toMatch(new RegExp(`${day} \\d{2}:\\d{2} UTC`));
  });

  test("SCR-04-AC-5: 이 상담원이 오늘 답변 1건 발송·이관 1건 → 오늘 처리한 건수 발송·이관이 1씩 는다", async ({ page, request }) => {
    // 같은 날 시험을 다시 돌리면 앞선 발송이 남아 있어 "1"이 아니라 "전보다 1"로 본다. 이관 1건은 AC-4에서 했다
    const mine = { dept: "TS_LV", scope: "mine" };
    const before = (await workload(request, mine, AGENT)).today;
    await sendDraft(request, b, AGENT, "TS_LV");
    const after = (await workload(request, mine, AGENT)).today;
    expect(after.sent).toBe(before.sent + 1);
    expect(after.escalated).toBeGreaterThanOrEqual(1);
    await openMine(page, "TS_LV", AGENT, "mine");
    const today = page.getByTestId("today");
    await expect(today).toContainText(new RegExp(`발송\\s*${after.sent}\\b`));
    await expect(today).toContainText(new RegExp(`이관\\s*${after.escalated}\\b`));
  });

  test("SCR-04-AC-3: CSV1-003578 사본, 정보 요청 뒤 130시간(리마인드 발송됨) → 그 줄에 '리마인드 발송됨'과 130h", async ({ page, request }) => {
    const id = await intakeCopy(request, "CSV1-003578", "TS_LV", ago(135));
    const s = await firstSub(request, id);
    const sub = s.sub_ticket.sub_ticket_id as string;
    const dept = s.sub_ticket.assigned_dept as string;
    const draft = s.drafts.find((m: { message_type: string; message_status: string }) => m.message_type === "INFO_REQUEST" && m.message_status === "DRAFT");
    expect(draft, "정보 요청 초안").toBeTruthy();
    // 시험 준비: 발송 API는 지금 시각으로만 보내므로, 발송 API가 남기는 것(SENT 행 + INFO_REQUEST_SENT 전이)을 130h 전
    // 시각으로 DB에 남기고 126h 리마인드 행을 둔다(리마인드 점검은 시연 서버에서 꺼 둠). svc.transition()으로 바꿔 상태 규칙은 그대로 탄다
    sql(`INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc, language,
                body, source_draft_id, sent_by_name)
         SELECT ticket_id, sub_ticket_id, 'AGENT', 'INFO_REQUEST', 'SENT', now() - interval '130 hours', language, body, message_id, '${AGENT}'
           FROM svc.ticket_message WHERE message_id = ${draft.message_id};
         SELECT svc.transition('${sub}', 'WAITING_CUSTOMER', 'INFO_REQUEST_SENT', now() - interval '130 hours', '${AGENT}', NULL, NULL);
         INSERT INTO svc.ticket_message (ticket_id, sub_ticket_id, sender, message_type, message_status, sent_at_utc, language,
                body, sent_by_name, notice_transition)
         VALUES ('${id}', '${sub}', 'SYSTEM', 'PROGRESS_NOTICE', 'SENT', now() - interval '4 hours', 'en', 'Reminder', 'SYSTEM', 'REMINDER');`);
    await openMine(page, dept, AGENT, "dept", "waiting_customer");
    const row = (await allRows(page)).find((t) => t.includes(id));
    expect(row).toContain("리마인드 발송됨");
    expect(row).toMatch(/130\.[01] h/);
  });

  test("SCR-04-AC-6: 표의 행을 누르면 그 티켓 상세가 열린다", async ({ page }) => {
    await openMine(page, "TS_LV", AGENT, "dept", "drafts");
    const first = rows(page).first();
    const id = (await first.innerText()).match(/CSV1-\d{6}/)![0];
    await first.click();
    await expect(page).toHaveURL(new RegExp(`/tickets/${id}`));
    await expect(page.getByTestId("ticket-page")).toBeVisible();
  });

  test("SCR-04-AC-7: 우선순위를 올려 경고가 새로 생긴 문의는 다음 갱신 뒤 기한 위험·위반 표에 나타난다", async ({ page, request }) => {
    // TECH_SPEC STANDARD P4는 해결 336h(75% = 252h). 접수 200h 뒤 P3(240h, 75% = 180h)로 올리면 해결 기한 임박
    const id = await intakeCopy(request, "CSV1-003578", "TS_LV", ago(200));
    const s = await firstSub(request, id);
    const sub = s.sub_ticket.sub_ticket_id as string;
    const dept = s.sub_ticket.assigned_dept as string;
    expect(s.sub_ticket.priority).toBe("P4");
    // 시험 준비: 1차 응답은 접수 1시간 뒤에 한 것으로 둔다(백엔드 AC-047-7 시험과 같음). 1차 응답 경고가 섞이지 않게
    sql(`UPDATE svc.sub_ticket SET first_response_at_utc = t.received_at_utc + interval '1 hour'
           FROM svc.ticket t WHERE t.ticket_id = svc.sub_ticket.ticket_id AND svc.sub_ticket.sub_ticket_id = '${sub}'`);
    await openMine(page, dept, AGENT, "dept");
    expect((await allRows(page).catch(() => [])).some((t) => t.includes(id))).toBe(false);
    const adj = await request.post(api(`/sub-tickets/${sub}/priority`), { headers: H(dept, AGENT),
      data: { new_priority: "P3", reason_kind: "CUSTOMER_REQUEST", reason_text: "고객이 납기 확인을 서둘러 요청", expected_version: s.version } });
    expect(adj.ok(), await adj.text()).toBeTruthy();
    await page.reload(); // 다음 갱신(5분 주기)을 새로고침으로 당긴다
    const row = (await allRows(page)).find((t) => t.includes(id));
    expect(row).toContain("해결 기한 임박");
    expect(row).toContain("P3");
  });
});

test("SCR-04-AC-8: 이름·부서를 고르지 않으면 '상단에서 이름과 부서를 고르세요'만 보인다", async ({ page }) => {
  await useSession(page, {});
  await page.goto("/my");
  await expect(page.getByText("상단에서 이름과 부서를 고르세요")).toBeVisible();
  await expect(page.locator("[data-tile]")).toHaveCount(0);
  await expect(page.locator("table.ui-table")).toHaveCount(0);
  await expect(page.getByTestId("today")).toHaveCount(0);
});

test("SCR-04-AC-9 (최신 목업): '새 문의' 타일, '지금 처리할 건', '가장 급한 내 문의'가 접수함 API의 내 담당·내 차례 값과 같다", async ({ page, request }) => {
  const url = (extra: string) => `http://localhost:8000/tickets?dept=TS_LV&as_of=${SNAPSHOT}&${extra}`;
  const team = await (await request.get(url("size=200"))).json();
  const name: string = team.rows.find((r: { assignee_masked: string | null; turn: string }) => r.assignee_masked && r.turn === "ME").assignee_masked;
  const mineList = await (await request.get(url(`size=8&turn=ME&assignee=${name}&me=${name}`))).json();
  const mineAll = await (await request.get(url(`size=1&assignee=${name}&me=${name}`))).json();
  await useSession(page, { dept: "TS_LV", agent: name, snapshot: true });
  await page.goto("/my");
  await expect(page.getByTestId("now-list")).toBeVisible();
  await expect(page.getByTestId("now-list")).toContainText(`${mineList.counts.total}건`);
  await expect(page.getByTestId("now-list").locator("li")).toHaveCount(mineList.rows.length);
  await expect(page.locator('[data-tile="new"] b')).toHaveText(String(mineAll.counts.new));
  const first = mineList.rows[0];
  await expect(page.getByTestId("now-list").locator("li").first()).toContainText(first.ticket_id);
  if (first.alerts.length) await expect(page.getByTestId("most-urgent")).toContainText(first.ticket_id);
  // 줄을 누르면 그 문의 상세가 열린다
  await page.getByTestId("now-list").locator("li").first().getByRole("button").click();
  await expect(page).toHaveURL(new RegExp(`/tickets/${first.ticket_id}$`));
});

test("SCR-04-AC-10 (최신 목업): '내 실적'의 오늘·기간 처리와 기한 충족이 서버 값과 같고, 오늘 처리한 건수 카드와 맞으며, 기간을 바꾸면 다시 묻는다", async ({ page, request }) => {
  const asOf = "2026-09-30T23:59:00Z";
  const agents: { name: string }[] = await (await request.get("http://localhost:8000/ref/agents?dept=TS_LV")).json();
  let name = "", perf: { total: number; days: number; daily: { n: number; sent: number; escalated: number; adjusted: number }[]; sla: { window_total: number; fr_met: number; fr_breached: number; res_ok: number } } | null = null;
  for (const a of agents) { // 재생 이력에서 이 기간에 처리한 기록이 있는 상담원
    const r = await (await request.get(`http://localhost:8000/me/performance?as_of=${asOf}&days=30`, { headers: { "X-Agent-Id": a.name } })).json();
    if (r.total > 0 && r.sla.window_total > 0) { name = a.name; break; }
  }
  expect(name, "30일 안에 처리 기록이 있는 TS_LV 상담원").not.toBe("");
  perf = await (await request.get(`http://localhost:8000/me/performance?as_of=${asOf}&days=7`, { headers: { "X-Agent-Id": name } })).json();
  const today = perf!.daily[perf!.daily.length - 1];
  await useSession(page, { dept: "TS_LV", agent: name, snapshot: true });
  await page.goto("/my");
  const card = page.getByTestId("my-performance");
  await expect(card).toBeVisible();
  await expect(card.locator('[data-stat="today"] b')).toHaveText(String(today.n));
  await expect(card.locator('[data-stat="total"] b')).toHaveText(String(perf!.total));
  await expect(card.locator('[data-stat="total"] span')).toContainText("최근 7일 처리");
  const fr = Math.round((perf!.sla.fr_met / (perf!.sla.fr_met + perf!.sla.fr_breached)) * 100);
  await expect(card.locator('[data-stat="fr"] b')).toContainText(String(fr));
  // 기존 '오늘 처리한 건수' 카드와 오늘 숫자가 같다(같은 정의)
  const t = page.getByTestId("today");
  await expect(t).toContainText(`발송${today.sent}`);
  await expect(t).toContainText(`이관${today.escalated}`);
  // 기간 바꾸기 → days=14로 다시 묻는다
  const asked = page.waitForRequest((r) => r.url().includes("/me/performance") && r.url().includes("days=14"));
  await card.getByRole("group", { name: "기간" }).getByRole("button", { name: "14일" }).click();
  await asked;
  await expect(card.locator('[data-stat="total"] span')).toContainText("최근 14일 처리");
});

test("SCR-04-AC-11: 상담원을 고르지 않은 '부서 전체' 보기에는 '내 실적'이 없다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto("/my");
  await expect(page.getByTestId("greet")).toBeVisible();
  await expect(page.getByTestId("my-performance")).toHaveCount(0);
});
