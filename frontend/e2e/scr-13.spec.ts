// SCR-13 고객 포털 미리보기 수용 기준 (docs/frontend/screens/SCR-13-portal.md). 서버 호출이 없는 화면이라 목 없이 그대로 본다.
import { expect, test } from "@playwright/test";
import { useSession } from "./session";

test("SCR-13-AC-1: 왼쪽 메뉴 시연 › 고객 포털 미리보기로 열면 상담원 틀 없이 두 방법 카드가 보이고, 상담원 시스템 링크로 돌아간다", async ({ page }) => {
  await useSession(page, { dept: "TS_LV" });
  await page.goto("/inbox");
  await page.getByRole("link", { name: "고객 포털 미리보기" }).click();
  await expect(page).toHaveURL(/\/portal$/);
  await expect(page.getByRole("heading", { name: "무엇을 도와드릴까요?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "챗봇으로 문의하기" })).toBeVisible();
  await expect(page.getByRole("button", { name: "웹 폼으로 문의하기" })).toBeVisible();
  await expect(page.locator("nav.shell-nav")).toHaveCount(0); // 상담원 틀 밖
  await page.getByRole("link", { name: /상담원 시스템/ }).click();
  await expect(page).toHaveURL(/\/inbox/);
});

test("SCR-13-AC-2: 웹 폼에서 고장을 고르고 비운 채 보내면 필수 항목 수와 개인정보 동의 오류가 보이고, 모두 채우고 동의하면 접수 완료가 보인다", async ({ page }) => {
  await page.goto("/portal");
  await page.getByRole("button", { name: "웹 폼으로 문의하기" }).click();
  await page.getByRole("radio", { name: "고장" }).click();
  await page.getByRole("button", { name: "문의 보내기" }).click();
  await expect(page.getByRole("alert")).toContainText(/입력하지 않은 필수 항목이 \d+개/);
  await expect(page.getByText("개인정보 수집·이용에 동의해 주세요")).toBeVisible();
  // 모두 채운다: 막지 않는 항목은 "모르겠어요", 막는 항목은 값을 넣는다
  for (const f of await page.locator(".pt-field").all()) {
    const unk = f.getByLabel("모르겠어요");
    if (await unk.count()) { await unk.check(); continue; }
    const sel = f.locator("select"), txt = f.locator("input.input, textarea");
    if (await sel.count()) await sel.selectOption({ index: 1 });
    else if (await txt.count()) await txt.first().fill("E.OC 2306-A12345 70% load");
  }
  await page.locator("#f-body").fill("정격 전류를 넘는 상태에서 차단기가 자꾸 트립됩니다. 확인 부탁드립니다.");
  await page.locator("#f-email").fill("buyer@example.com");
  await page.getByLabel(/개인정보 수집·이용에 동의합니다/).check();
  await page.getByRole("button", { name: "문의 보내기" }).click();
  await expect(page.getByRole("heading", { name: "문의를 접수했어요" })).toBeVisible();
});

test("SCR-13-AC-3: 챗봇에 반품 정책을 물으면 답과 '근거: POL-RETURN' 칩이 보인다", async ({ page }) => {
  await page.goto("/portal");
  await page.getByRole("button", { name: "챗봇으로 문의하기" }).click();
  await page.getByLabel("메시지").fill("반품 정책이 궁금해요");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /근거: POL-RETURN/ }).first()).toBeVisible();
});

test("SCR-13-AC-4: English를 누르면 화면 글이 영어로 바뀐다", async ({ page }) => {
  await page.goto("/portal");
  await page.getByRole("button", { name: "English" }).click();
  await expect(page.getByRole("heading", { name: "How can we help you?" })).toBeVisible();
});
