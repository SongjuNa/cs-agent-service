// 열어 둔 문의 탭 막대 (변경 add-ticket-look, 최신 목업 TabBar). 접수함 탭 + 연 문의마다 한 탭, 닫을 수 있다.
// 서버와 무관한 화면 상태라 이 브라우저 탭(sessionStorage)에만 둔다. 저장을 못 쓰면 막대가 없을 뿐이다.
import { useEffect, useState } from "react";
import { Icon } from "../../app/icons";
import { lastInboxUrl } from "../inbox/inboxQuery";
import "./openTabs.css";

const KEY = "cs-open-tabs";
const CHANGED = "cs-open-tabs-changed";
const MAX = 8;
export interface OpenTab { id: string; sum: string }

function read(): OpenTab[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((t): t is OpenTab => typeof t?.id === "string") : [];
  } catch {
    return [];
  }
}
function write(tabs: OpenTab[]) {
  try { sessionStorage.setItem(KEY, JSON.stringify(tabs)); } catch { /* 저장 불가 환경 */ }
  window.dispatchEvent(new Event(CHANGED)); // 떠 있는 막대가 다시 읽는다
}

/** 문의를 열었을 때 한 번 부른다. 이미 있으면 요약만 갱신하고, 가득 차면 가장 오래된 탭을 뺀다 */
export function rememberOpenTab(id: string, sum: string) {
  const tabs = read();
  const i = tabs.findIndex((t) => t.id === id);
  if (i >= 0) { if (tabs[i].sum === sum) return; tabs[i] = { id, sum }; } else tabs.push({ id, sum });
  write(tabs.slice(-MAX));
}

export function OpenTabs({ current, navigate }: { current: string | null; navigate: (path: string) => void }) {
  const [list, setTabs] = useState<OpenTab[]>(read);
  useEffect(() => {
    const sync = () => setTabs(read());
    window.addEventListener(CHANGED, sync);
    sync(); // 이 막대가 그려지기 전에 저장된 변경도 반영
    return () => window.removeEventListener(CHANGED, sync);
  }, []);
  if (!list.length) return null;
  const close = (id: string) => {
    const i = list.findIndex((t) => t.id === id);
    const next = list.filter((t) => t.id !== id);
    write(next);
    if (id === current) { const to = next[i] ?? next[i - 1]; navigate(to ? `/tickets/${encodeURIComponent(to.id)}` : lastInboxUrl()); }
  };
  return (
    <div className="otabs" role="tablist" aria-label="열어 둔 문의">
      <a className={`otabs__tab otabs__tab--fixed${current === null ? " is-on" : ""}`} role="tab" aria-selected={current === null}
         href="/inbox" onClick={(e) => { e.preventDefault(); navigate(lastInboxUrl()); }}><Icon name="inbox" />접수함</a>
      {list.map((t) => (
        <div key={t.id} className={`otabs__tab${current === t.id ? " is-on" : ""}`} role="tab" aria-selected={current === t.id}>
          <a className="otabs__main" href={`/tickets/${encodeURIComponent(t.id)}`} title={`${t.id} · ${t.sum}`}
             onClick={(e) => { e.preventDefault(); navigate(`/tickets/${encodeURIComponent(t.id)}`); }}>
            <b>{t.id.replace("CSV1-", "")}</b><span>{t.sum}</span>
          </a>
          <button type="button" className="otabs__x" aria-label={`${t.id} 탭 닫기`} onClick={() => close(t.id)}>×</button>
        </div>
      ))}
    </div>
  );
}
