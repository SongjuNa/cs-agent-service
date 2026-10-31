// 시험 시작 때 자동 발송(변경 add-auto-send)을 끄고, 끝나면 원래 설정으로 되돌린다.
// 기존 화면 시험은 새로 접수한 문의의 초안을 상담원이 조작한다고 가정한다. 자동 발송이 켜져 있으면 매뉴얼·기술 사양 문의가
// 사람 손이 닿기 전에 발송되어 시험이 어긋난다. 자동 발송을 보는 시험(scr-12)은 시험 안에서 직접 켜고 되돌린다.
// 서버가 꺼져 있으면 조용히 건너뛴다(각 시험이 알아서 실패한다).
const API = "http://localhost:8000";
const HEADERS = { "X-Agent-Id": "e2e", "Content-Type": "application/json" };

export default async function globalSetup() {
  let original: { enabled: boolean; cats: Record<string, boolean>; channels: Record<string, boolean> } | null = null;
  try {
    const res = await fetch(`${API}/auto-rules`);
    if (!res.ok) return;
    const r = await res.json();
    original = { enabled: r.enabled, cats: r.cats, channels: r.channels };
    await fetch(`${API}/auto-rules`, { method: "PUT", headers: HEADERS, body: JSON.stringify({ ...original, enabled: false }) });
  } catch {
    return;
  }
  return async () => {
    if (original) await fetch(`${API}/auto-rules`, { method: "PUT", headers: HEADERS, body: JSON.stringify(original) }).catch(() => undefined);
  };
}
