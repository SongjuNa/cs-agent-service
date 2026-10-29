// 화면 수용 기준(AC) 시험. 실제 API(localhost:8000)에 붙여 돈다(principles §6). 목은 오류·빈 상태에만 page.route로 쓴다.
// 실행: 백엔드를 띄운 뒤 npx playwright test
import { defineConfig } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 5179);

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false, // 같은 DB를 읽으므로 차례로 돈다
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
  webServer: { command: `npm run dev -- --port ${PORT} --strictPort`, port: PORT, reuseExistingServer: true },
});
