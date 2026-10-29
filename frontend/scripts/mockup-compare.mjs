// 5단계 "기준 목업과 나란히 놓고 비교": 화면마다 목업 v1.42와 구현 화면을 같은 크기(1440×900, 첫 화면)로 찍어 한 장에 붙인다.
// 배치가 어긋났는지 사람이 눈으로 보는 자료다(값·문구는 기준 문서를 따르므로 다른 것이 정상인 곳이 있다. 화면 명세 "목업과 다른 곳").
// 실행: 백엔드(8000)·화면(5179)을 띄운 뒤 frontend에서
//   MOCKUP=<목업 html 경로> OUT=<저장 폴더> node scripts/mockup-compare.mjs
// 목업 파일은 저장소에 없다(조장이 준 파일). 시연 DB에 W6 재생과 CSV1-004001~004009가 있어야 화면에 값이 나온다.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const MOCKUP = process.env.MOCKUP;
const OUT = process.env.OUT ?? "mockup-compare";
const APP = process.env.APP ?? "http://localhost:5179";
if (!MOCKUP) throw new Error("MOCKUP=<목업 html 경로>가 필요합니다");

// [파일 이름, 화면, 목업 주소(#뒤) 또는 null(접수함 첫 행), 구현 주소, 세션]
const ONLY = process.env.ONLY; // 파일 이름 앞부분으로 한 화면만
const SCREENS = [
  ["SCR-02_접수함", "접수함", "inbox", "/inbox", { dept: "TS_LV", agent: "leo", snapshot: true }],
  ["SCR-01_접수시뮬레이터", "접수 시뮬레이터", "sim", "/intake", { dept: "TS_LV", agent: "leo" }],
  ["SCR-03_티켓상세", "티켓 상세", null, "/tickets/CSV1-004004?tab=customer", { dept: "TS_LV", agent: "leo" }],
  ["SCR-04_나의업무현황", "나의 업무 현황", "home", "/my", { dept: "TS_LV", agent: "zara", snapshot: true, myScope: "dept" }],
  ["SCR-05_전화상담", "전화 상담", "phone", "/phone", { dept: "TS_LV", agent: "leo" }],
  ["SCR-07_고객관리", "고객 관리", "customers", "/customers", { dept: "TS_LV", agent: "leo" }],
  ["SCR-08_문서관리", "기준정보 › 문서", "docs", "/docs", { dept: "TS_LV", agent: "leo" }],
  ["SCR-08_규칙관리", "기준정보 › 규칙", "rules", "/rules", { dept: "TS_LV", agent: "leo" }],
  ["SCR-08_제품관리", "기준정보 › 제품", "products", "/products", { dept: "TS_LV", agent: "leo" }],
  ["SCR-08_부서관리", "기준정보 › 부서", "depts", "/depts", { dept: "TS_LV", agent: "leo" }],
  ["SCR-09_접수이력", "접수 이력", "similar", "/history?error_code=E.OC", { dept: "TS_LV", agent: "leo" }],
];
const VIEW = { width: 1440, height: 900 };

async function shotMockup(browser, hash) {
  const page = await browser.newPage({ viewport: VIEW });
  await page.goto(`file://${MOCKUP}#${hash ?? "inbox"}`);
  await page.waitForTimeout(2000);
  if (!hash) { // 목업 티켓 상세는 접수함 첫 행에서 연다
    await page.locator("table tbody tr").first().click();
    await page.waitForTimeout(1500);
  }
  const png = await page.screenshot();
  await page.close();
  return png;
}

async function shotApp(browser, path, s) {
  const ctx = await browser.newContext({ viewport: VIEW });
  await ctx.addInitScript((v) => {
    localStorage.setItem("cs-agent-dept", v.dept);
    localStorage.setItem("cs-agent-id", v.agent);
    if (v.snapshot) localStorage.setItem("cs-as-of", "snapshot");
    if (v.myScope) localStorage.setItem("cs-my-scope", v.myScope); // 나의 업무 현황 "부서 전체"
  }, s);
  const page = await ctx.newPage();
  await page.goto(APP + path);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  const png = await page.screenshot();
  await ctx.close();
  return png;
}

async function sideBySide(browser, title, left, right) {
  const page = await browser.newPage({ viewport: { width: 2 * 720 + 48, height: 500 } });
  const img = (b) => `data:image/png;base64,${b.toString("base64")}`;
  await page.setContent(`<body style="margin:0;padding:16px;font:14px sans-serif;background:#f2f4f7">
    <h2 style="margin:0 0 8px">${title}</h2>
    <div style="display:flex;gap:16px">
      <figure style="margin:0;width:720px"><figcaption><b>기준 목업 v1.42</b></figcaption><img src="${img(left)}" style="width:720px;border:1px solid #98a2b3"></figure>
      <figure style="margin:0;width:720px"><figcaption><b>구현 화면(실제 API)</b></figcaption><img src="${img(right)}" style="width:720px;border:1px solid #98a2b3"></figure>
    </div></body>`);
  const png = await page.screenshot({ fullPage: true });
  await page.close();
  return png;
}

mkdirSync(OUT, { recursive: true });
readFileSync(MOCKUP); // 목업 경로 확인
const browser = await chromium.launch();
for (const [file, title, hash, path, s] of SCREENS.filter(([f]) => !ONLY || f.startsWith(ONLY))) {
  const left = await shotMockup(browser, hash);
  const right = await shotApp(browser, path, s);
  writeFileSync(`${OUT}/${file}.png`, await sideBySide(browser, title, left, right));
  console.log(`${file}.png`);
}
await browser.close();
