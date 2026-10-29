import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { queryClient } from "./queryClient";
import "./styles/tokens.css";
import "./styles.css";

// /ui 견본 화면은 개발 서버에서만 연다(공통 컴포넌트 검토용, 서비스 화면 아님)
const Gallery = lazy(() => import("./ui/Gallery").then((m) => ({ default: m.Gallery })));
const showGallery = import.meta.env.DEV && window.location.pathname === "/ui";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {showGallery ? <Suspense fallback={null}><Gallery /></Suspense> : <App />}
    </QueryClientProvider>
  </StrictMode>,
);
