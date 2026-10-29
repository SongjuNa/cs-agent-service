"""해결사례 직접 검색 완료 기준 (FR 초안 06, 변경 add-case-search design 결정 3).

시험 DB의 팀 정답지는 비어 있어, 빼는 것은 가짜 팀 정답지 행을 넣고 색인을 새로 만들어 확인한다(롤백).
"""

from __future__ import annotations

import csv

import pytest

from app.config import get_settings
from app.retrieval import cases
from app.retrieval.cases import CaseIndex
from app.retrieval.fault import SymptomVectors
from tests.acceptance.test_drafts import WordCountEmbedder
from tests.acceptance.test_similar_cases import gold_row
from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api·index 픽스처)


@pytest.fixture
def fresh_index():
    """팀 정답지를 넣은 뒤 색인을 새로 만들도록 기본 색인을 빈 것으로 바꿔 둔다."""
    saved = cases._default_index
    cases._default_index = CaseIndex(None, SymptomVectors(None, step="Q8b"))
    yield
    cases._default_index = saved


def eoc_ticket() -> tuple[str, str]:
    """E.OC 사례 하나의 (원래 티켓, 사례 번호). resolution_cases.csv에서 읽는다."""
    with (get_settings().data_path / "resolution_cases.csv").open(encoding="utf-8-sig") as f:
        r = next(r for r in csv.DictReader(f) if r["error_code"] == "E.OC")
    return r["ticket_id"], r["case_id"]


def test_error_code_first_and_no_gold(api, fresh_index):
    """AC 초안(FR-초안-06): 에러 코드 E.OC로 찾으면 앞쪽 결과가 모두 E.OC이고 팀 정답지 문의의 사례는 없다."""
    ticket, case = eoc_ticket()
    gold_row(api[2], ticket)
    res = api[0].get("/cases", params={"error_code": "E.OC"})
    assert res.status_code == 200, res.text
    got = res.json()
    assert got["rows"] and all(r["error_code"] == "E.OC" and r["same_error_code"] for r in got["rows"])
    assert case not in {r["case_id"] for r in got["rows"]} and ticket not in {r["ticket_id"] for r in got["rows"]}
    # 에러 코드는 거르지 않고 순서에만 쓴다: 뜻 검색과 함께여도 같은 코드가 먼저
    mixed = api[0].get("/cases", params={"error_code": "E.OC", "q": "inverter overcurrent trip at start"}).json()["rows"]
    flags = [r["same_error_code"] for r in mixed]
    assert flags == sorted(flags, reverse=True)


def test_empty_input_400(api):
    """design 결정 1: 네 칸이 모두 비면 400 "검색어를 입력하세요"."""
    res = api[0].get("/cases", params={"q": "  "})
    assert res.status_code == 400 and res.json()["detail"] == "검색어를 입력하세요"


def test_gold_case_detail_404(api, fresh_index):
    """design 결정 2: 팀 정답지 문의의 사례 상세는 404, 그 밖 사례는 원인·조치·결과가 있다."""
    ticket, case = eoc_ticket()
    ok = api[0].get(f"/cases/{case}").json()
    assert ok["root_cause"] and ok["action_taken"] and ok["resolution_result"]
    cases._default_index = CaseIndex(None, SymptomVectors(None, step="Q8b"))
    gold_row(api[2], ticket)
    res = api[0].get(f"/cases/{case}")
    assert res.status_code == 404 and res.json()["detail"] == "사례를 찾을 수 없음"


def test_query_masked_before_embedding(api, fresh_index):
    """CLAUDE.md 규칙 2: 상담원 검색어도 보내기 직전 가린다(이메일이 임베딩 대역에 그대로 가지 않는다)."""
    sent: list[str] = []

    class Spy(WordCountEmbedder):
        def embed(self, texts, task):
            sent.extend(texts)
            return super().embed(texts, task)

    api[1].embedder = lambda: Spy()
    res = api[0].get("/cases", params={"q": "trip after start, contact john.doe@example.com"})
    assert res.status_code == 200, res.text
    assert sent and all("john.doe@example.com" not in t for t in sent)


def test_semantic_failure_falls_back(api, fresh_index):
    """design 결정 1 "실패": 임베딩이 실패하면 거르기 결과 + "뜻 검색 실패"."""
    api[1].embedder = lambda: WordCountEmbedder(fail_times=99)
    got = api[0].get("/cases", params={"q": "trip", "error_code": "E.OC"}).json()
    assert got["notes"] == ["뜻 검색 실패. 에러 코드·제품으로만 찾았습니다"] and got["rows"][0]["error_code"] == "E.OC"


def test_read_only():
    """proposal: 고치는 주소가 없다."""
    from app.main import app

    methods = {m for r in app.routes if getattr(r, "path", "").startswith("/cases") for m in r.methods}
    assert methods <= {"GET", "HEAD"}
