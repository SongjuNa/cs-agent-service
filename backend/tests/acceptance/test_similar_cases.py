"""유사 해결사례 완료 기준 (FR-019, 변경 add-similar-cases design 결정 5).

AC-019-1~3은 접수 API로 처리 흐름을 돌린다(대역 언어 모델·대역 임베딩, 롤백). 예외와 색인은 검색 함수를 직접 부른다.
색인·벡터 캐시는 conftest가 임시 폴더로 바꿔 둔다. 시연 DB의 팀 정답지(eval.gold_set)는 비어 있어,
빼는 코드는 시험 안에서 가짜 팀 정답지 행을 넣어 확인한다(2026-10-29 검토 자료 ③).
"""

from __future__ import annotations

from app.config import get_settings
from app.llm.client import LlmTimeout
from app.retrieval import cases
from app.retrieval.cases import NOTE_FAILED, NOTE_NONE, CaseIndex, build_index, similar_cases
from app.retrieval.fault import SymptomVectors
from tests.acceptance.test_drafts import WordCountEmbedder
from tests.acceptance.test_fault_diagnosis import defect_plc, steps
from tests.acceptance.test_ticket_detail import api, index, info_request, quote  # noqa: F401  (api·index 픽스처)


def gold_row(conn, source_ticket_id: str) -> None:
    conn.execute("""INSERT INTO eval.gold_set (gold_set_id, set_version, source_ticket_id, language, inquiry_body, created_by)
                    VALUES ('GS-990', 'test', %s, 'en', 'x', 'test')""", (source_ticket_id,))


def test_ac_019_1_defect_cases(api):
    """AC-019-1: CSV1-000017(DEFECT, ACB-AS-2000) → 사례 3건 이하, 같은 제품군, 팀 정답지 문의의 사례와 자기 사례 RC-0006이 없다."""
    conn = api[2]
    gold = conn.execute("SELECT ticket_id FROM gold.ticket_gold WHERE ticket_id <> 'CSV1-000017' AND resolution_case_id IS NOT NULL "
                        "AND resolution_case_id IN (SELECT case_id FROM gold.resolution_case_gold WHERE product_family = 'LV_BREAKER') "
                        "ORDER BY ticket_id LIMIT 1").fetchone()[0]
    gold_row(conn, gold)
    saved = cases._default_index
    cases._default_index = CaseIndex(None, SymptomVectors(None, step="Q8b"))  # 팀 정답지를 넣은 뒤 색인을 새로 만든다
    try:
        detail = info_request(api)
    finally:
        cases._default_index = saved
    got = detail["sub_tickets"][0]["similar_cases"]
    ids = [c["case_id"] for c in got["cases"]]
    assert 1 <= len(ids) <= 3 and "RC-0006" not in ids
    (gold_case,) = conn.execute("SELECT resolution_case_id FROM gold.ticket_gold WHERE ticket_id = %s", (gold,)).fetchone()
    assert gold_case not in ids
    fams = {r[0] for r in conn.execute("SELECT product_family FROM gold.resolution_case_gold WHERE case_id = ANY(%s)", (ids,))}
    assert fams == {"LV_BREAKER"}
    assert steps(api, detail)["Q8b"][1]["cases"] == got["cases"]


def test_ac_019_2_quote_skips(api):
    """AC-019-2: CSV1-000004(QUOTE) → Q8b 단계가 실행 기록에 없다."""
    detail = quote(api)
    assert "Q8b" not in steps(api, detail) and detail["sub_tickets"][0]["similar_cases"] is None


def test_ac_019_3_not_in_draft(api):
    """AC-019-3: 사례가 보이는 문의 → Q10 입력 항목 이름과 L4 지시문, 초안 인용에 해결사례가 없다."""
    detail = defect_plc(api)
    sub = detail["sub_tickets"][0]
    assert sub["similar_cases"]["cases"]
    rec = steps(api, detail)
    names = rec["Q10"][0]["field_names"]
    assert names and not any("case" in n or "similar" in n for n in names)
    l4 = [p for c, p in api[1].fake.prompts if c == "L4"]
    assert l4 and all("RC-" not in p for p in l4)
    assert all(not str(c.get("doc_id", "")).startswith("RC-") for c in sub["sub_ticket"]["evidence_json"])


def test_no_same_family(conn):
    """FR-019 예외 1행: 같은 제품군 사례가 없으면 빈 목록 + "비슷한 사례 없음"."""
    idx = CaseIndex(None, SymptomVectors(None, step="Q8b"))
    got = similar_cases(conn, WordCountEmbedder(), "DEFECT", "NO_SUCH_FAMILY", None, "breaker trips", None, idx)
    assert (got.cases, got.notes) == ([], [NOTE_NONE])


def test_failure_keeps_flow(api, monkeypatch):
    """FR-019 예외 2행: 임베딩이 실패해도 "사례 검색 실패", Q8b 행은 FAILED, 답변 단계까지 간다."""
    monkeypatch.setattr(cases, "embed_texts", lambda *a, **k: (_ for _ in ()).throw(LlmTimeout("t")))
    detail = defect_plc(api)
    sub = detail["sub_tickets"][0]
    assert sub["similar_cases"] == {"cases": [], "notes": [NOTE_FAILED]}
    (result,) = api[2].execute("SELECT result FROM svc.agent_step WHERE run_id = %s AND step_name = 'Q8b'",
                               (detail["run"]["run_id"],)).fetchone()
    assert result == "FAILED" and "Q10" in steps(api, detail) and not sub["sub_ticket"]["pipeline_error"]


def test_index_excludes_gold_set(conn):
    """FR-019 처리 3, D30: 팀 정답지 source_ticket_id의 사례는 색인에 없다. 나머지는 800건 그대로."""
    data = get_settings().data_path
    before = build_index(conn, data)
    assert len(before) == 800 - conn.execute("SELECT count(*) FROM eval.gold_set WHERE source_ticket_id IS NOT NULL").fetchone()[0]
    with conn.transaction(force_rollback=True):
        gold_row(conn, "CSV1-000017")
        after = build_index(conn, data)
    assert "RC-0006" in {r["case_id"] for r in before} and "RC-0006" not in {r["case_id"] for r in after}
    assert len(after) == len(before) - 1


def test_order_same_error_code_first(conn):
    """design 결정 2: 같은 에러 코드 사례가 먼저(그다음 유사도)."""
    idx = CaseIndex(None, SymptomVectors(None, step="Q8b"))
    code = next(r["error_code"] for r in idx.rows(conn) if r["product_family"] == "DRIVE" and r["error_code"])
    got = similar_cases(conn, WordCountEmbedder(), "DEFECT", "DRIVE", code, "motor stops", None, idx)
    assert got.cases[0]["error_code"] == code and got.cases[0]["method"] == "ERROR_CODE"
