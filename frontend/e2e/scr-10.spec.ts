// SCR-10 상담원 도우미 수용 기준 (docs/frontend/screens/SCR-10-assistant.md).
// 답은 Gemini를 부르므로 시험이 흔들리지 않게 POST /api/assist/ask와 절 본문(/api/chunks)은 page.route 목으로 대신한다.
// 서버 쪽 동작(출처 검사, 가리기, 저장 안 함)은 backend/tests/acceptance/test_agent_assistant.py가 실제 DB로 확인한다.
import { expect, test, type Page, type Route } from "@playwright/test";
import { useSession } from "./session";

const SOURCE = { no: 1, chunk_id: "TG-DOC§2", doc_id: "TG-DOC", section_no: "2", title: "Overcurrent trip" };
const FOUND = { found: true, answer: "문서에 따르면 정격 전류를 넘으면 차단됩니다.", sources: [SOURCE], followups: ["복구 절차는?"], notes: [] };
const NOT_FOUND = { found: false, answer: "찾지 못했습니다.", sources: [], followups: [], notes: [] };

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function open(page: Page) {
  await useSession(page, {});
  await page.route("**/api/chunks/**", (r) => json(r, 200, { chunk_id: "TG-DOC§2", doc_id: "TG-DOC", doc_title: "Troubleshooting", section_no: "2", section_title: "Overcurrent trip", text: "Trips above rated current." }));
  await page.goto("/my");
  await page.getByTestId("assist-open").click();
}
const ask = async (page: Page, q: string) => {
  await page.getByLabel("질문").fill(q);
  await page.getByRole("button", { name: "보내기" }).click();
};

test("SCR-10-AC-1 오른쪽 아래 도우미를 누르면 창이 열린다", async ({ page }) => {
  await open(page);
  await expect(page.getByTestId("assist-panel")).toBeVisible();
  await expect(page.getByText("상담원 참고용입니다")).toBeVisible();
  await expect(page.getByLabel("질문")).toBeVisible();
});

test("SCR-10-AC-2·3 근거 있는 답에는 출처 칩이 있고, 누르면 절 본문이 열린다", async ({ page }) => {
  await page.route("**/api/assist/ask", (r) => json(r, 200, FOUND));
  await open(page);
  await ask(page, "과전류 트립이 뭐예요?");
  await expect(page.getByTestId("assist-answer")).toContainText("정격 전류를 넘으면");
  const chip = page.getByTestId("assist-source");
  await expect(chip).toHaveText("TG-DOC §2");
  await chip.click();
  await expect(page.getByRole("dialog", { name: /인용/ })).toContainText("Trips above rated current.");
});

test("SCR-10-AC-4 근거 없으면 '찾지 못했습니다'이고 출처 칩이 없다", async ({ page }) => {
  await page.route("**/api/assist/ask", (r) => json(r, 200, NOT_FOUND));
  await open(page);
  await ask(page, "점심 메뉴 추천");
  await expect(page.getByTestId("assist-answer")).toContainText("찾지 못했습니다.");
  await expect(page.getByTestId("assist-source")).toHaveCount(0);
});

test("SCR-10-AC-5 서버 오류면 [다시 시도]가 보이고 누르면 같은 질문을 다시 보낸다", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/assist/ask", (r) => { calls += 1; return calls === 1 ? json(r, 500, { detail: "x" }) : json(r, 200, FOUND); });
  await open(page);
  await ask(page, "과전류 트립이 뭐예요?");
  await expect(page.getByText("답을 가져오지 못했습니다.")).toBeVisible();
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page.getByTestId("assist-answer")).toContainText("정격 전류를 넘으면");
  expect(calls).toBe(2);
});

test("SCR-10-AC-6 서버가 400을 주면 입력 칸 아래에 문구가 보이고 보낸 글이 남는다", async ({ page }) => {
  await page.route("**/api/assist/ask", (r) => json(r, 400, { detail: "질문을 입력하세요" }));
  await open(page);
  await ask(page, "질문");
  await expect(page.getByRole("alert")).toHaveText("질문을 입력하세요");
  await expect(page.getByLabel("질문")).toHaveValue("질문");
});

test("SCR-10-AC-7 이어 묻기 칩을 누르면 직전 대화와 함께 그 질문을 보낸다", async ({ page }) => {
  const bodies: { question: string; history: { role: string; text: string }[] }[] = [];
  await page.route("**/api/assist/ask", (r) => { bodies.push(r.request().postDataJSON()); return json(r, 200, FOUND); });
  await open(page);
  await ask(page, "과전류 트립이 뭐예요?");
  await expect(page.getByTestId("assist-answer")).toBeVisible();
  await page.getByRole("button", { name: "복구 절차는?" }).click();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[1].question).toBe("복구 절차는?");
  expect(bodies[1].history.map((h) => h.role)).toEqual(["user", "assistant"]);
});

test("SCR-10-AC-8 [새 대화]를 누르면 대화 목록이 비고 안내 글이 보인다", async ({ page }) => {
  await page.route("**/api/assist/ask", (r) => json(r, 200, FOUND));
  await open(page);
  await ask(page, "과전류 트립이 뭐예요?");
  await expect(page.getByTestId("assist-answer")).toBeVisible();
  await page.getByRole("button", { name: "새 대화" }).click();
  await expect(page.getByTestId("assist-answer")).toHaveCount(0);
  await expect(page.getByText("오류 코드나 제품 이름을 넣어 물어보세요")).toBeVisible();
});

test("SCR-10-AC-9 (최신 목업): 첫 화면에 질문 후보가 있고, 누르면 그 질문이 그대로 가서 답이 나온다", async ({ page }) => {
  const bodies: { question: string; product_code: string | null }[] = [];
  await page.route("**/api/assist/ask", (r) => { bodies.push(r.request().postDataJSON()); return json(r, 200, FOUND); });
  await open(page);
  const chips = page.getByTestId("assist-chips").getByRole("button");
  await expect(chips).toHaveCount(4);
  await page.getByTestId("assist-chips").getByRole("button", { name: "반품 정책" }).click();
  await expect(page.getByTestId("assist-answer")).toBeVisible();
  expect(bodies[0].question).toBe("반품 정책");
  await expect(page.getByTestId("assist-chips")).toHaveCount(0); // 대화가 시작되면 후보는 사라지고 이어 묻기 칩이 대신한다
});

test("SCR-10-AC-10 (최신 목업): 문의 화면에서는 그 문의의 제품·오류 코드로 후보가 바뀌고, 질문에 제품 코드가 실려 간다", async ({ page, request }) => {
  const list = await (await request.get("http://localhost:8000/tickets?dept=TS_LV&size=1&as_of=2026-09-30T23:59:00Z")).json();
  const id = list.rows[0].ticket_id as string;
  const bodies: { question: string; product_code: string | null }[] = [];
  await page.route("**/api/assist/ask", (r) => { bodies.push(r.request().postDataJSON()); return json(r, 200, FOUND); });
  await useSession(page, { dept: "TS_LV", snapshot: true });
  await page.goto(`/tickets/${id}`);
  await page.getByTestId("assist-open").click();
  await expect(page.getByText(id, { exact: true })).toBeVisible(); // "지금은 {번호}를 보고 있어…"
  const first = page.getByTestId("assist-chips").getByRole("button").first();
  await expect(first).not.toHaveText("E.OC 오류 원인과 조치");
  await first.click();
  await expect(page.getByTestId("assist-answer")).toBeVisible();
  expect(bodies[0].product_code).not.toBeNull();
});
