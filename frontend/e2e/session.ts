// 시험마다 부서·상담원·기준 시각을 미리 정해 둔다(SCR-00 저장 키, src/api.ts)
import type { Page } from "@playwright/test";

export async function useSession(page: Page, s: { dept?: string; agent?: string; snapshot?: boolean }) {
  await page.addInitScript((v) => {
    if (sessionStorage.getItem("e2e-seeded")) return; // 새로고침 뒤에는 화면이 고른 값을 지킨다
    sessionStorage.setItem("e2e-seeded", "1");
    localStorage.clear();
    if (v.dept) localStorage.setItem("cs-agent-dept", v.dept);
    if (v.agent) localStorage.setItem("cs-agent-id", v.agent);
    if (v.snapshot) localStorage.setItem("cs-as-of", "snapshot");
  }, s);
}

export const api = (path: string) => `http://localhost:8000${path}`;
