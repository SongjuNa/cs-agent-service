"""근거 문서 검색과 숫자 조회 완료 기준 (W2, FR-016·017, 변경 add-evidence-lookup).

- 검색 규칙은 단어를 세는 대역 임베딩으로 만든 색인으로 시험한다(언어 모델 없음).
- 실제 임베딩 시험은 GEMINI_API_KEY가 있을 때만 돈다.
"""

from __future__ import annotations

import hashlib
import math
import re

import pytest

from app.config import get_settings
from app.llm.client import LlmTimeout
from app.pipeline.evidence import add_evidence
from app.pipeline.state import ProvidedField, SubTicketState, TicketState
from app.retrieval.numbers import lookup_numbers, version_key
from app.retrieval.search import search_evidence
from jobs.build_doc_index import build, missing_gold_sections

DIM = 64


class WordCountEmbedder:
    """글자를 단어로 나눠 64칸 벡터에 센다. 같은 글이면 늘 같은 벡터(결정적)."""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0

    def embed(self, texts, task):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise LlmTimeout("t")
        out = []
        for text in texts:
            v = [0.0] * DIM
            for word in re.findall(r"[a-z0-9.]+", text.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm + 1e-6 for x in v])
        return out


@pytest.fixture(scope="module")
def index(conn):
    count = build(conn, get_settings().data_path, WordCountEmbedder())
    conn.commit()
    return count


def ticket_input(conn, ticket_id):
    cur = conn.execute("SELECT * FROM gold.v_inputs WHERE ticket_id = %s", (ticket_id,))
    return dict(zip([d.name for d in cur.description], cur.fetchone()))


def product_doc_ids(conn, product_code):
    return {r[0] for r in conn.execute("SELECT doc_id FROM ref.document WHERE product_code = %s", (product_code,))}


# --- W2 색인 ---


def test_w2_gold_sections_all_chunked(conn, index):
    """§9 W2: 정답의 (reference_doc_id, reference_section) 쌍이 모두 청크로 있다."""
    assert index > 800
    assert missing_gold_sections(conn) == []


def test_w2_parent_section_split(conn, index):
    """§4-2: ## 아래 ###가 있으면 따로 나뉘고, ## 청크에는 ### 본문이 없다."""
    rows = dict(conn.execute(
        "SELECT section_no, text FROM ref.doc_chunk WHERE doc_id = 'TG-ACB-AS-2000' AND section_no IN ('3', '3.1')"
    ).fetchall())
    assert set(rows) == {"3", "3.1"}
    assert rows["3.1"] and rows["3.1"] not in rows["3"]


# --- FR-016 ---


def test_ac_016_1_defect_only_own_product_docs(conn, index):
    """AC-016-1: CSV1-000017(ACB-AS-2000, DEFECT) → TG-ACB-AS-2000 절이 있고 다른 제품 문서는 없다."""
    found = search_evidence(conn, WordCountEmbedder(), "Terminal overheating and discoloration on ACB",
                            "DEFECT", "ACB-AS-2000", "LV_BREAKER")
    docs = {c.doc_id for c in found.candidates}
    assert "TG-ACB-AS-2000" in docs
    others = {r[0] for r in conn.execute(
        "SELECT doc_id FROM ref.document WHERE product_code IS NOT NULL AND product_code <> 'ACB-AS-2000'")}
    assert not docs & others


def test_ac_016_2_quote_top_is_pol_order(conn, index):
    """AC-016-2: CSV1-000004(QUOTE) → 1순위가 POL-ORDER의 절."""
    found = search_evidence(conn, WordCountEmbedder(), "Price quotation for XGT Panel eXP60, 1 unit, CIF Le Havre",
                            "QUOTE", "HMI-XGT-eXP60", "HMI")
    assert found.candidates[0].doc_id == "POL-ORDER"


def test_ac_016_3_no_product_only_policy_and_faq(conn, index):
    """AC-016-3: product_code가 없으면 제품 문서 없이 정책·FAQ만, "제품 문서 미검색"."""
    found = search_evidence(conn, WordCountEmbedder(), "Terminal overheating and discoloration",
                            "DEFECT", None, None)
    types = {r[0] for r in conn.execute(
        "SELECT DISTINCT doc_type FROM ref.document WHERE doc_id = ANY(%s)", ([c.doc_id for c in found.candidates],))}
    assert found.candidates and types <= {"POL", "FAQ"}
    assert "제품 문서 미검색" in found.flags


def test_exact_term_bonus(conn, index):
    """FR-016 처리 3: 에러 코드가 든 절에 가점 0.2."""
    plain = search_evidence(conn, WordCountEmbedder(), "breaker trips", "DEFECT", "ACB-AS-2000", "LV_BREAKER")
    boosted = search_evidence(conn, WordCountEmbedder(), "breaker trips", "DEFECT", "ACB-AS-2000", "LV_BREAKER",
                              ["T.GF"])
    texts = dict(conn.execute("SELECT chunk_id, text FROM ref.doc_chunk WHERE doc_id = 'TG-ACB-AS-2000'").fetchall())
    before = {c.chunk_id: c.score for c in plain.candidates}
    common = [c for c in boosted.candidates if c.chunk_id in before]
    assert common
    for c in common:
        expected = 0.2 if "T.GF" in texts[c.chunk_id] else 0.0
        assert round(c.score - before[c.chunk_id], 6) == expected
    assert any("T.GF" in texts[c.chunk_id] for c in boosted.candidates)


def test_widen_when_priority_type_missing(conn, index):
    """§4-4 2번: 우선 종류(RN)가 없는 제품이면 범위 전체로 넓힌다."""
    no_rn = conn.execute(
        """SELECT p.product_code, p.family FROM ref.product p
            WHERE NOT EXISTS (SELECT 1 FROM ref.document d WHERE d.product_code = p.product_code AND d.doc_type = 'RN')
            LIMIT 1""").fetchone()
    found = search_evidence(conn, WordCountEmbedder(), "firmware update", "FW_UPDATE", *no_rn)
    assert found.candidates and "근거 없음" not in found.flags


def test_search_failure_after_retry(conn, index):
    """FR-016 예외 2행: 검색 임베딩이 두 번 실패 → 후보 없음 + "검색 실패" + "근거 없음"."""
    emb = WordCountEmbedder(fail_times=2)
    found = search_evidence(conn, emb, "price", "QUOTE", "HMI-XGT-eXP60", "HMI")
    assert emb.calls == 2 and found.candidates == []
    assert {"검색 실패", "근거 없음"} <= set(found.flags)


# --- FR-017 ---


def test_ac_017_1_quote_price_total_lead(conn):
    """AC-017-1: HMI-XGT-eXP60 수량 1 → 단가 520, 합계 520, 표준 납기 4주, 출처 product_master.csv."""
    data = ticket_input(conn, "CSV1-000004")
    res = lookup_numbers(conn, "QUOTE", data["product_code"], data["received_at_utc"], quantity="1")
    by = {lv.item: lv for lv in res.lookups}
    assert by["list_price_usd"].value == 520 and by["list_price_usd"].unit == "USD"
    assert by["line_total_usd"].value == 520
    assert by["std_lead_time_weeks"].value == 4
    assert {lv.source_table for lv in res.lookups} == {"product_master.csv"}
    assert by["list_price_usd"].source_key == "HMI-XGT-eXP60"


def test_ac_017_1_source_row_is_14(conn):
    """AC-017-1의 "14행": product_master.csv 파일의 14번째 줄이 HMI-XGT-eXP60이다."""
    lines = (get_settings().data_path / "ref" / "product_master.csv").read_text(encoding="utf-8-sig").splitlines()
    assert lines[13].startswith("HMI-XGT-eXP60,")


def test_ac_017_2_already_latest_at_intake(conn):
    """AC-017-2: ESS-BMS-V3, 접수 2025-10-01, 고객 3.40 → 접수 시점 최신 3.40(2025-05-19), "이미 최신"."""
    data = ticket_input(conn, "CSV1-000008")
    res = lookup_numbers(conn, "FW_UPDATE", data["product_code"], data["received_at_utc"], current_fw="3.40")
    assert res.firmware.fw_latest_at_intake == "3.40"
    assert str(res.firmware.release_date) == "2025-05-19"
    assert res.firmware.verdict == "이미 최신"
    assert all(lv.value != "3.50" for lv in res.lookups)


def test_ac_017_3_update_when_intake_later(conn):
    """AC-017-3: 접수일 2026-02-01 → 접수 시점 최신 3.50, "업데이트 안내"."""
    res = lookup_numbers(conn, "FW_UPDATE", "ESS-BMS-V3", "2026-02-01", current_fw="3.40")
    assert res.firmware.fw_latest_at_intake == "3.50" and res.firmware.verdict == "업데이트 안내"


def test_numbers_exceptions(conn):
    """FR-017 예외 1~3·5행."""
    assert lookup_numbers(conn, "QUOTE", None).flags == ["제품 확인 필요"]
    no_fw = conn.execute("SELECT product_code FROM ref.product WHERE NOT has_firmware LIMIT 1").fetchone()[0]
    assert "펌웨어 없는 제품 — 분류 재검토" in lookup_numbers(conn, "FW_UPDATE", no_fw, "2025-10-01").flags
    assert "접수 시점 최신 없음" in lookup_numbers(conn, "FW_UPDATE", "ESS-BMS-V3", "2020-01-01").flags
    early = lookup_numbers(conn, "QUOTE", "HMI-XGT-eXP60", "2025-10-01", required_date="2025-10-10")
    assert "요청 납기 < 표준 납기" in early.flags
    no_spec = conn.execute(
        "SELECT product_code FROM ref.product p WHERE NOT EXISTS (SELECT 1 FROM ref.product_spec s WHERE s.product_code = p.product_code) LIMIT 1"
    ).fetchone()
    if no_spec:  # §2-2 Q9 실패: 표에 행이 없음
        assert "표에 없음" in lookup_numbers(conn, "TECH_SPEC", no_spec[0]).flags


def test_spec_rows_follow_candidates(conn, index):
    """FR-017 처리 2: 근거 후보 절에 걸린 사양 행을 먼저, 못 정하면 전체 + "사양 항목 선택 필요"."""
    product, doc_id, section = conn.execute(
        "SELECT product_code, doc_id, section FROM ref.product_spec WHERE doc_id IS NOT NULL LIMIT 1").fetchone()
    from app.pipeline.state import DocCandidate
    cand = DocCandidate(chunk_id=f"{doc_id}§{section}", doc_id=doc_id, section_no=section)
    picked = lookup_numbers(conn, "TECH_SPEC", product, doc_candidates=[cand])
    everything = lookup_numbers(conn, "TECH_SPEC", product)
    assert 0 < len(picked.lookups) <= len(everything.lookups)
    assert "사양 항목 선택 필요" in everything.flags and "사양 항목 선택 필요" not in picked.flags
    assert all(lv.source_table == "product_spec_facts.csv" for lv in picked.lookups)


def test_version_key_numeric():
    assert version_key("3.10") > version_key("3.9")


def test_add_evidence_fills_state(conn, index):
    """§2-2 Q8·Q9: 상태 객체에 근거 후보와 조회값을 붙인다."""
    data = ticket_input(conn, "CSV1-000004")
    sub = SubTicketState(sub_ticket_id="CSV1-000004-1", ticket_id="CSV1-000004", seq=1, category_code="QUOTE",
                         query_en="Price for XGT Panel eXP60", product_code="HMI-XGT-eXP60", product_family="HMI",
                         provided_fields=[ProvidedField(field="quantity", value_raw="1", value_norm="1")])
    state = TicketState(ticket_id="CSV1-000004", channel=data["channel"], customer_id=data["customer_id"],
                        language=data["language"], body_masked="x", received_at=data["received_at_utc"],
                        sub_tickets=[sub])
    out = add_evidence(conn, WordCountEmbedder(), state).sub_tickets[0]
    assert out.doc_candidates[0].doc_id == "POL-ORDER"
    assert {lv.item for lv in out.lookups} >= {"list_price_usd", "line_total_usd"}


# --- 실제 임베딩 (키가 있을 때만) ---

needs_key = pytest.mark.skipif(not get_settings().gemini_api_key, reason="키 없음: GEMINI_API_KEY가 없어 실제 임베딩 시험을 건너뜀")


@needs_key
def test_live_index_and_search(conn):
    from app.llm.embed import default_embedder

    embedder = default_embedder()
    build(conn, get_settings().data_path, embedder)
    conn.commit()
    assert missing_gold_sections(conn) == []
    found = search_evidence(conn, embedder, "Terminal overheating and discoloration on the ACB",
                            "DEFECT", "ACB-AS-2000", "LV_BREAKER")
    assert found.candidates[0].chunk_id == "TG-ACB-AS-2000§3.1"
    quote = search_evidence(conn, embedder, "Price quotation for 1 unit", "QUOTE", "HMI-XGT-eXP60", "HMI")
    assert quote.candidates[0].doc_id == "POL-ORDER"
