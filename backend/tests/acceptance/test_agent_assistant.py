"""상담원 도우미 완료 기준 (FR-초안-07, 변경 add-agent-assistant design 결정 5).

API를 TestClient로 부른다. 언어 모델은 대역 Transport, 임베딩은 WordCountEmbedder, DB는 바깥 트랜잭션을 롤백한다.
"""

from __future__ import annotations

import json

import pytest

from app.llm.client import LlmTimeout
from tests.acceptance.test_drafts import WordCountEmbedder
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api·index 픽스처)

ASK = "/assist/ask"


class AssistTransport:
    """L11 지시문에 정해진 응답을 낸다. 받은 지시문을 남긴다."""

    def __init__(self, reply=None):
        self.reply = reply
        self.prompts: list[str] = []

    def send(self, prompt, schema):
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return json.dumps(self.reply, ensure_ascii=False)


def first_chunk(conn):
    """색인된 절 하나. 영어 낱말이 세 개 이상 이어진 80~450자 절(질문은 500자 이하, 대역 임베딩은 영어 낱말만 센다).
    그 절 본문을 그대로 물으면 대역 임베딩에서 가장 가깝다."""
    row = conn.execute(
        r"""SELECT chunk_id, doc_id, section_no, section_title, text FROM ref.doc_chunk
             WHERE embedding IS NOT NULL AND length(text) BETWEEN 80 AND 450
               AND text ~ '[A-Za-z]{4,} [A-Za-z]{4,} [A-Za-z]{4,}'
             ORDER BY chunk_id LIMIT 1"""
    ).fetchone()
    assert row is not None, "시험에 쓸 절이 색인에 없다(문서 색인이 비었거나 영어 절이 없음)"
    return row


def service_rows(conn) -> dict[str, int]:
    tables = conn.execute(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('svc', 'eval') AND table_type = 'BASE TABLE'"
    ).fetchall()
    return {f"{s}.{t}": conn.execute(f'SELECT count(*) FROM "{s}"."{t}"').fetchone()[0] for s, t in tables}


def test_grounded_answer_has_existing_source(api, index):
    """AC-1: 색인에 있는 절을 물으면 found이고, 출처가 그 절이며 chunk_id가 실제로 있다."""
    client, clients, conn = api
    chunk_id, doc_id, section_no, title, text = first_chunk(conn)
    clients.fake = AssistTransport({"found": True, "answer": "문서에 따르면 그렇습니다.", "used_sources": [1], "followups": ["다음 질문"]})
    res = client.post(ASK, json={"question": text})
    assert res.status_code == 200, res.text
    got = res.json()
    assert got["found"] is True and got["answer"] and got["followups"] == ["다음 질문"]
    assert len(got["sources"]) == 1 and got["sources"][0]["no"] == 1
    # 같은 글이 여러 문서에 되풀이될 수 있어, 출처가 실제로 있는 절이고 본문이 질문과 같은지로 본다
    src = conn.execute("SELECT doc_id, text FROM ref.doc_chunk WHERE chunk_id = %s", (got["sources"][0]["chunk_id"],)).fetchone()
    assert src is not None and src[1] == text and src[0] == got["sources"][0]["doc_id"]
    # 출처 본문은 지시문의 <sources>에 들어갔다
    assert text[:50] in clients.fake.prompts[0]
    assert chunk_id and doc_id and section_no and title  # 고른 절의 칸이 모두 있다


def test_not_found_has_no_sources(api, index):
    """AC-2: 모델이 근거 없음으로 답하면 found가 거짓이고 출처가 비며 답은 "찾지 못했습니다"로 시작한다."""
    client, clients, conn = api
    clients.fake = AssistTransport({"found": False, "answer": "", "used_sources": [1], "followups": ["x"]})
    got = client.post(ASK, json={"question": "completely unrelated gardening question"}).json()
    assert got["found"] is False and got["sources"] == [] and got["followups"] == []
    assert got["answer"].startswith("찾지 못했습니다")


def test_forged_source_is_dropped(api, index):
    """AC-3: 모델이 보낸 번호 밖 출처만 적으면 버려지고 found가 거짓이 된다. 일부만 밖이면 남은 것만 쓴다."""
    client, clients, conn = api
    text = first_chunk(conn)[4]
    clients.fake = AssistTransport({"found": True, "answer": "지어낸 출처", "used_sources": [99], "followups": []})
    got = client.post(ASK, json={"question": text}).json()
    assert got["found"] is False and got["sources"] == []
    clients.fake = AssistTransport({"found": True, "answer": "일부만 맞음", "used_sources": [99, 1], "followups": []})
    got = client.post(ASK, json={"question": text}).json()
    assert got["found"] is True and len(got["sources"]) == 1


def test_question_masked_before_embedding_and_model(api, index):
    """AC-4 (CLAUDE.md 규칙 2): 질문과 이어 묻기 대화의 이메일이 임베딩과 모델에 그대로 가지 않는다."""
    client, clients, conn = api
    sent: list[str] = []

    class Spy(WordCountEmbedder):
        def embed(self, texts, task):
            sent.extend(texts)
            return super().embed(texts, task)

    clients.embedder = lambda: Spy()
    clients.fake = AssistTransport({"found": False, "answer": "", "used_sources": [], "followups": []})
    body = {"question": "trip after start, contact john.doe@example.com",
            "history": [{"role": "user", "text": "mail me at jane.roe@example.com"}]}
    assert client.post(ASK, json=body).status_code == 200
    assert sent and all("john.doe@example.com" not in t for t in sent)
    assert "john.doe@example.com" not in clients.fake.prompts[0] and "jane.roe@example.com" not in clients.fake.prompts[0]


def test_empty_and_long_question_400(api, index):
    """AC-5: 빈 질문과 500자 넘는 질문은 400."""
    client = api[0]
    res = client.post(ASK, json={"question": "   "})
    assert res.status_code == 400 and res.json()["detail"] == "질문을 입력하세요"
    res = client.post(ASK, json={"question": "a" * 501})
    assert res.status_code == 400 and res.json()["detail"] == "질문은 500자 이하로 입력하세요"


def test_model_failure_returns_sections_only(api, index):
    """AC-6: 모델이 두 번 실패하면 답 없이 찾은 절 목록과 안내 문구가 온다."""
    client, clients, conn = api
    text = first_chunk(conn)[4]
    clients.fake = AssistTransport(LlmTimeout("t"))
    got = client.post(ASK, json={"question": text}).json()
    assert got["found"] is False and got["answer"] == "" and len(got["sources"]) >= 1
    assert got["notes"] == ["답을 만들지 못했습니다. 아래 문서를 직접 확인하세요"]


def test_nothing_is_stored(api, index):
    """AC-7 (규칙 4): 질문하고 답을 받아도 svc·eval 표 행 수가 같다."""
    client, clients, conn = api
    text = first_chunk(conn)[4]
    before = service_rows(conn)
    clients.fake = AssistTransport({"found": True, "answer": "답", "used_sources": [1], "followups": []})
    assert client.post(ASK, json={"question": text}).status_code == 200
    assert service_rows(conn) == before


def test_number_outside_source_is_noted(api, index):
    """답의 숫자가 쓴 절에 없으면 notes에 알린다(막지 않는다)."""
    client, clients, conn = api
    text = first_chunk(conn)[4]
    clients.fake = AssistTransport({"found": True, "answer": "정격은 987654321입니다.", "used_sources": [1], "followups": []})
    got = client.post(ASK, json={"question": text}).json()
    assert got["found"] is True and any("987654321" in n for n in got["notes"])


def test_model_names_are_not_numbers_outside_source():
    """모델 이름·문서 번호 속 숫자(0750, 100, 2026-0123)는 "근거 밖 숫자"로 알리지 않고, 진짜 낯선 숫자만 알린다."""
    from app.llm.assist import answer_question
    from app.retrieval.docs_free import DocHit

    hit = DocHit("c§1", "POL-WARRANTY", "1", "Warranty", "The warranty is 24 months. Starts at commissioning, within 6 months after shipment.", 1.0)

    def run(answer):
        t = AssistTransport({"found": True, "answer": answer, "used_sources": [1], "followups": []})
        return answer_question(t, "q", [], [hit]).notes

    assert run("TG-INV-LSLV0750-iS7, H100, S100 모델의 보증은 24 months이고 RMA-2026-0123을 참고하세요. 선적 후 6 months.") == []
    assert run("보증은 987 months입니다.") == ["근거 밖 숫자: 987"]
