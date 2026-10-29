// SCR-03 시험 도우미. 상태를 바꾸는 시험(발송·이관·회신·조정)은 시연 티켓을 건드리지 않도록
// 정답지 입력 6칸으로 새 사본을 접수해 쓴다(시뮬레이터 "불러오기"와 같은 길, 접수 시각은 지금). 처리에 Gemini를 부른다.
import { expect, type APIRequestContext } from "@playwright/test";
import { api } from "./session";

export const H = (dept = "TS_LV", agent = "leo") => ({ "X-Agent-Dept": dept, "X-Agent-Id": agent });

export async function waitDone(request: APIRequestContext, id: string, dept = "TS_LV") {
  await expect.poll(async () => (await (await request.get(api(`/tickets/${id}`), { headers: H(dept) })).json()).processing,
    { timeout: 240_000, intervals: [2000] }).toBe(false);
  return (await request.get(api(`/tickets/${id}`), { headers: H(dept) })).json();
}

/** 정답지 문의 하나를 지금 시각(received를 주면 그 시각)으로 새로 접수하고 처리가 끝날 때까지 기다린다 */
export async function intakeCopy(request: APIRequestContext, sourceId: string, dept = "TS_LV", received: string | null = null): Promise<string> {
  const g = await (await request.get(api(`/gold/tickets/${sourceId}`))).json();
  const res = await request.post(api("/tickets"), {
    headers: H(dept),
    data: { channel: g.channel, customer_id: g.customer_id, product_code: g.product_code ?? null, language: g.language,
            inquiry_subject: null, inquiry_body: g.inquiry_body, received_at_utc: received, source_ticket_id: g.source_ticket_id,
            contact_name: null, contact_email: null, contact_phone: null },
  });
  expect(res.ok()).toBeTruthy();
  const { ticket_id } = await res.json();
  await waitDone(request, ticket_id, dept);
  return ticket_id;
}
