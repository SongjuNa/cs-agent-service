import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 서버: /api → FastAPI(8000). 화면 주소 /tickets/:id 는 index.html로 (화면 정의서 v2 0-2절)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
