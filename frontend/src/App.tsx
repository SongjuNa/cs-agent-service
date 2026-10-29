// 주소 나누기와 공통 틀(SCR-00). 화면은 AppShell 안에 그린다. 주소는 화면 정의서 v2 0-2절과 기존 경로를 그대로 쓴다.
import { useCallback, useEffect, useState } from "react";
import { AppShell, MENU, type Crumb } from "./app/AppShell";
import { useSession } from "./app/session";
import { InboxPage } from "./features/inbox/InboxPage";
import { lastInboxUrl } from "./features/inbox/inboxQuery";
import { IntakePage } from "./features/intake/IntakePage";
import { PhonePage } from "./features/phone/PhonePage";
import { MyWorkPage } from "./features/mywork/MyWorkPage";
import { TicketPage } from "./features/ticket/TicketPage";
import { EmptyState, PageHeader } from "./ui";

type Page = { kind: "inbox" } | { kind: "intake" } | { kind: "my" } | { kind: "phone" } | { kind: "ticket"; id: string } | { kind: "menu"; key: string };

// 목업 메뉴 중 목업 화면으로만 두는 것 (docs/frontend/screens/README "명세를 쓰지 않은 목업 화면").
// 운영 대시보드는 보여 줄 화면을 정하기 전이라 목업 화면으로 둔다(2026-10-29 조장 결정)
const MOCK_ONLY = new Set(["notice", "sysnote", "chatbot", "portal", "ops"]);
const MOCK_REASON: Record<string, string> = {
  ops: "보여 줄 화면을 정하기 전이라 목업 화면으로 둡니다(2026-10-29 조장 결정).",
};

function pageFromPath(): Page {
  const path = window.location.pathname;
  const m = path.match(/^\/tickets\/([^/]+)$/);
  if (m) return { kind: "ticket", id: decodeURIComponent(m[1]) };
  if (path === "/intake") return { kind: "intake" };
  if (path === "/my") return { kind: "my" };
  if (path === "/phone") return { kind: "phone" };
  if (path === "/" || path === "/inbox") return { kind: "inbox" }; // 접수함이 기본 화면(SCR-00-05)
  const item = MENU.flatMap((g) => g.items).find((i) => i.path === path);
  return item ? { kind: "menu", key: item.key } : { kind: "inbox" };
}

function activeKey(page: Page): string {
  if (page.kind === "my") return "home";
  if (page.kind === "phone") return "phone";
  if (page.kind === "intake" || page.kind === "ticket" || page.kind === "inbox") return "inbox";
  return page.key;
}

function crumbsOf(page: Page): Crumb[] {
  if (page.kind === "ticket") return [{ label: "접수", path: "/my" }, { label: "접수함", path: lastInboxUrl() }, { label: page.id }];
  if (page.kind === "intake") return [{ label: "접수", path: "/my" }, { label: "접수함", path: "/inbox" }, { label: "접수 시뮬레이터" }];
  if (page.kind === "my") return [{ label: "접수", path: "/my" }, { label: "나의 업무 현황" }];
  if (page.kind === "phone") return [{ label: "접수", path: "/my" }, { label: "전화 상담" }];
  if (page.kind === "inbox") return [{ label: "접수", path: "/my" }, { label: "접수함" }];
  const group = MENU.find((g) => g.items.some((i) => i.key === page.key));
  const item = group?.items.find((i) => i.key === page.key);
  return [{ label: group?.label ?? "" }, { label: item?.label ?? "" }];
}

export function App() {
  const { agent, dept, mode } = useSession();
  const [page, setPage] = useState<Page>(pageFromPath());
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const onPop = () => setPage(pageFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((path: string) => {
    window.history.pushState(null, "", path);
    setFlash(null);
    setPage(pageFromPath());
    window.scrollTo(0, 0);
  }, []);

  // [접수함으로]: 마지막 접수함 주소(필터·정렬·쪽)로 (SCR-02-AC-8). 없는 번호면 안내를 띄운다(FR-030 예외 1행)
  const back = useCallback((message?: string) => {
    window.history.pushState(null, "", lastInboxUrl());
    setPage({ kind: "inbox" });
    setFlash(message ?? null);
  }, []);

  const open = (id: string) => navigate(`/tickets/${encodeURIComponent(id)}`);

  return (
    <AppShell active={activeKey(page)} crumbs={crumbsOf(page)} navigate={navigate}>
      {page.kind === "intake" ? <IntakePage onOpen={open} navigate={navigate} />
        : page.kind === "phone" ? <PhonePage onOpen={open} />
        : page.kind === "my" ? <MyWorkPage key={`${dept}|${mode}|${agent}`} onOpen={open} navigate={navigate} />
        : page.kind === "ticket" ? <TicketPage key={`${page.id}|${dept}`} ticketId={page.id} agent={agent} onBack={back} />
        : page.kind === "inbox" ? <InboxPage key={`${dept}|${mode}`} flash={flash} navigate={navigate} onOpen={(id) => open(id)} />
        : <MenuPlaceholder pageKey={page.key} />}
    </AppShell>
  );
}

function MenuPlaceholder({ pageKey }: { pageKey: string }) {
  const item = MENU.flatMap((g) => g.items).find((i) => i.key === pageKey);
  return (
    <>
      <PageHeader title={item?.label ?? ""} />
      <EmptyState title={MOCK_ONLY.has(pageKey) ? "목업 화면으로만 두는 메뉴입니다" : "다음 슬라이스에서 만듭니다"}>
        {MOCK_ONLY.has(pageKey) ? MOCK_REASON[pageKey] ?? "우리 시스템 밖의 기능이라 만들지 않습니다(화면 명세 README)." : "화면 명세는 docs/frontend/screens/에 있습니다."}
      </EmptyState>
    </>
  );
}
