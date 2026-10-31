"""고객 원문 한국어 번역 (변경 add-body-translation). 상담원이 누를 때 한 번 번역해 svc.ticket.body_ko에 저장하고, 있으면 모델을 부르지 않는다."""

from __future__ import annotations

from app.llm.client import LlmError
from tests.acceptance.test_auto_send import manual
from tests.acceptance.test_drafts import FakeTransport
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)

KO = {"translation": "펌웨어 릴리스 노트를 보내 주세요. HMI-XGT-iXP90 [attachment: log.xlsx]"}


def ticket_of(api):
    return manual(api)["ticket"]["ticket_id"]


def test_translate_saves_once_and_reuses(api):
    """처음 누르면 L12로 번역해 저장하고, 다시 누르면 모델을 부르지 않고 저장된 값을 돌려준다. 상세에도 보인다."""
    client, clients, conn = api
    tid = ticket_of(api)
    assert client.get(f"/tickets/{tid}").json()["ticket"]["body_ko"] is None
    clients.fake = FakeTransport(L12=[KO])
    first = client.post(f"/tickets/{tid}/translate")
    assert first.status_code == 200 and first.json() == {"ticket_id": tid, "body_ko": KO["translation"], "cached": False}
    assert clients.fake.count("L12") == 1
    assert conn.execute("SELECT body_ko FROM svc.ticket WHERE ticket_id = %s", (tid,)).fetchone()[0] == KO["translation"]
    again = client.post(f"/tickets/{tid}/translate")
    assert again.json()["cached"] is True and again.json()["body_ko"] == KO["translation"]
    assert clients.fake.count("L12") == 1  # 두 번째는 모델을 부르지 않았다
    assert client.get(f"/tickets/{tid}").json()["ticket"]["body_ko"] == KO["translation"]


def test_prompt_marks_customer_text_as_data_and_masks_it(api):
    """원문은 <customer_message> 안에 들어가고 안의 글은 지시가 아니라고 적히며, 이메일은 가려져서 간다(규칙 2·5)."""
    client, clients, conn = api
    tid = ticket_of(api)
    conn.execute("UPDATE svc.ticket SET inquiry_body = inquiry_body || ' Contact me at secret.person@example.com' WHERE ticket_id = %s", (tid,))
    clients.fake = FakeTransport(L12=[KO])
    assert client.post(f"/tickets/{tid}/translate").status_code == 200
    prompt = next(p for c, p in clients.fake.prompts if c == "L12")
    assert "<customer_message>" in prompt and "not instructions" in prompt
    assert "secret.person@example.com" not in prompt


def test_translate_failure_saves_nothing(api):
    client, clients, conn = api
    tid = ticket_of(api)
    clients.fake = FakeTransport(L12=[LlmError("UNKNOWN", "실패")])
    res = client.post(f"/tickets/{tid}/translate")
    assert res.status_code == 502 and "번역하지 못했습니다" in res.json()["detail"]
    assert conn.execute("SELECT body_ko FROM svc.ticket WHERE ticket_id = %s", (tid,)).fetchone()[0] is None
    # 다시 눌러 성공하면 그때 저장된다
    clients.fake = FakeTransport(L12=[KO])
    assert client.post(f"/tickets/{tid}/translate").json()["cached"] is False


def test_earlier_saved_value_wins_and_missing_ticket_is_404(api):
    """동시에 눌러 먼저 저장된 값이 있으면 덮어쓰지 않고 그 값을 돌려준다. 없는 문의는 404."""
    client, clients, conn = api
    tid = ticket_of(api)
    conn.execute("UPDATE svc.ticket SET body_ko = '먼저 저장된 번역' WHERE ticket_id = %s", (tid,))
    clients.fake = FakeTransport(L12=[KO])
    res = client.post(f"/tickets/{tid}/translate").json()
    assert res["body_ko"] == "먼저 저장된 번역" and res["cached"] is True and clients.fake.count("L12") == 0
    assert client.post("/tickets/CSV1-999999/translate").status_code == 404
