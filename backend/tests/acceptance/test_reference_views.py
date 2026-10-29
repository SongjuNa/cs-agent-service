"""기준정보 보기 완료 기준 (FR 초안 02·03·04, 변경 add-reference-views design 결정 4).

ref 테이블만 읽으므로 티켓을 접수하지 않는다. api 픽스처는 기준정보를 적재한 시험 DB를 준다.
"""

from __future__ import annotations

from pathlib import Path

from tests.acceptance.test_ticket_detail import api, index  # noqa: F401  (api 픽스처)


def get(api, path: str, **params):
    res = api[0].get(path, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def test_documents_107_and_chunk_count(api):
    """AC 초안(FR-초안-02): 문서 목록은 107행이고 문서마다 절 수(chunk_count)가 있다. 0이면 화면이 "색인 없음"을 보인다."""
    rows = get(api, "/ref/documents")
    assert len(rows) == 107
    (chunks,) = api[2].execute("SELECT count(*) FROM ref.doc_chunk").fetchone()
    assert sum(r["chunk_count"] for r in rows) == chunks
    assert all(isinstance(r["chunk_count"], int) and r["chunk_count"] >= 0 for r in rows)
    ig = get(api, "/ref/documents", doc_type="IG")
    assert ig and {r["doc_type"] for r in ig} == {"IG"}


def test_document_sections_and_404(api):
    """design 결정 1: 상세는 절 목록(절 번호 순), 절 본문은 GET /chunks/{id}. 없는 문서는 404 "문서를 찾을 수 없음"."""
    doc = get(api, "/ref/documents")[0]
    d = get(api, f"/ref/documents/{doc['doc_id']}")
    assert len(d["sections"]) == doc["chunk_count"] > 0
    first = d["sections"][0]
    assert get(api, f"/chunks/{first['chunk_id']}")["doc_id"] == doc["doc_id"]
    res = api[0].get("/ref/documents/NO-SUCH-DOC")
    assert res.status_code == 404 and res.json()["detail"] == "문서를 찾을 수 없음"


def test_product_price_and_lead_time(api):
    """AC 초안(FR-초안-03, AC-030-4): CSV1-000004의 제품 HMI-XGT-eXP60은 단가 520, 표준 납기 4주."""
    (code,) = api[2].execute("SELECT product_code FROM gold.v_inputs WHERE ticket_id = 'CSV1-000004'").fetchone()
    assert code == "HMI-XGT-eXP60"
    row = next(r for r in get(api, "/ref/products") if r["product_code"] == code)
    assert row["list_price_usd"] == 520 and row["std_lead_time_weeks"] == 4
    d = get(api, f"/ref/products/{code}")
    assert d["list_price_usd"] == 520 and d["std_lead_time_weeks"] == 4
    dates = [f["release_date"] for f in d["firmware"]]
    assert dates and dates == sorted(dates, reverse=True)
    assert api[0].get("/ref/products/NO-SUCH").status_code == 404


def test_priority_rule_pr02(api):
    """AC 초안(FR-초안-04, AC-030-2): 우선순위 규칙 PR-02의 조건과 P1. 행은 rule_order 순."""
    got = get(api, "/ref/rules/priority")
    rows = got["rows"]
    assert [r["rule_order"] for r in rows] == sorted(r["rule_order"] for r in rows)
    pr02 = next(r for r in rows if r["rule_id"] == "PR-02")
    assert pr02["condition"] == "urgency=SITE_DOWN 이고 Category ∈ {DEFECT, INSTALL, FW_UPDATE}" and pr02["priority"] == "P1"
    assert pr02["urgencies"] == ["SITE_DOWN"] and set(pr02["categories"]) == {"DEFECT", "INSTALL", "FW_UPDATE"}


def test_other_rule_kinds_and_unknown(api):
    """design 결정 3: 배정·필수 정보·처리 기한은 테이블 행 수 그대로, 없는 종류는 404."""
    for kind, table in (("routing", "routing_rule"), ("required-info", "required_info_rule"), ("sla", "sla_policy")):
        (n,) = api[2].execute(f"SELECT count(*) FROM ref.{table}").fetchone()
        assert len(get(api, f"/ref/rules/{kind}")["rows"]) == n
    fields = get(api, "/ref/rules/required-info")["rows"][0]["fields"]
    assert [f["field_order"] for f in fields] == sorted(f["field_order"] for f in fields)
    assert api[0].get("/ref/rules/unknown").status_code == 404


def test_read_only_and_no_rule_code():
    """proposal "고치기 없음", CLAUDE.md 규칙 1·2·6: 고치는 주소가 없고, 규칙 코드·언어 모델·정답지를 읽지 않는다."""
    from app.main import app

    paths = ("/ref/documents", "/ref/products", "/ref/rules", "/ref/departments")
    methods = {m for r in app.routes if getattr(r, "path", "").startswith(paths) for m in r.methods}
    assert methods <= {"GET", "HEAD"}
    src = (Path(__file__).resolve().parents[2] / "app" / "api" / "reference.py").read_text(encoding="utf-8")
    assert "gold." not in src and "app.rules" not in src and "app.llm" not in src
