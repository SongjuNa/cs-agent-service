"""고장 진단 완료 기준 (FR-018, 변경 add-fault-diagnosis).

AC-018-1·2와 예외는 진단 함수를 운영진 데이터의 실제 제품·에러 코드로 부른다(대역 임베딩).
AC-018-3·4와 상세 표시는 접수 API로 처리 흐름을 돌린다(대역 언어 모델, 롤백).
AC-018-5는 정답의 이관 사유를 읽는 채점 시험이다(CLAUDE.md 규칙 6 예외, 팀 정답지 대신 tickets.csv, C-137).
"""

from __future__ import annotations

from app.llm.client import LlmTimeout
from app.retrieval.fault import (
    LOW_SCORE, NOTE_CODE_UNKNOWN, NOTE_FAILED, NOTE_LOW, NOTE_NO_FAMILY, SymptomVectors, diagnose,
)
from tests.acceptance.test_drafts import WordCountEmbedder, field, l1
from tests.acceptance.test_ticket_detail import api, index, intake, quote  # noqa: F401  (api·index 픽스처)


class CountingEmbedder(WordCountEmbedder):
    """보낸 글 수를 센다(캐시 확인용)."""

    def __init__(self, fail_times: int = 0):
        super().__init__(fail_times)
        self.texts: list[str] = []

    def embed(self, texts, task):
        self.texts += texts
        return super().embed(texts, task)


def run(conn, category="DEFECT", family="PLC", product="PLC-XGB-XBM-DR16S", code=None, query="cpu does not start",
        embedder=None, vectors=None, tmp=None):
    return diagnose(conn, embedder or WordCountEmbedder(), category, family, product, code, query,
                    vectors or SymptomVectors(tmp))


def test_ac_018_1_exact(conn, tmp_path):
    """AC-018-1: CSV1-000007(PLC-XGB-XBM-DR16S, P.06) → FLT-028이 정확 일치로 1순위."""
    row = conn.execute("""SELECT t.product_code, t.error_code_reported, p.family FROM gold.ticket_gold t
                            JOIN ref.product p USING (product_code) WHERE t.ticket_id = 'CSV1-000007'""").fetchone()
    assert row == ("PLC-XGB-XBM-DR16S", "P.06", "PLC")  # 시험 준비 확인(정답지 값)
    got = run(conn, family=row[2], product=row[0], code=row[1], tmp=tmp_path / "c.json")
    top = got.candidates[0]
    assert (top.fault_id, top.method, top.score, got.method) == ("FLT-028", "EXACT", 1.0, "EXACT")
    assert top.replace_required is True and top.onsite_required is False and top.cause and top.action and top.check


def test_ac_018_2_symptom_same_family(conn, tmp_path):
    """AC-018-2: 에러 코드 없는 CSV1-000055(HMI-XGT-iXP90) → 같은 제품군(HMI) 항목만, 찾은 방법 증상 검색."""
    got = run(conn, family="HMI", product="HMI-XGT-iXP90", query="Logging stops, memory full warning", tmp=tmp_path / "c.json")
    assert got.method == "SYMPTOM" and 1 <= len(got.candidates) <= 3
    families = {r[0] for r in conn.execute("SELECT family FROM ref.fault WHERE fault_id = ANY(%s)",
                                           ([c.fault_id for c in got.candidates],)).fetchall()}
    assert families == {"HMI"} and all(c.method == "SYMPTOM" for c in got.candidates)
    scores = [c.score for c in got.candidates]
    assert scores == sorted(scores, reverse=True)


def test_exceptions(conn, tmp_path):
    """FR-018 예외 4행: 제품군 없음 / 에러 코드 미등록 → 증상 검색 / 관련성 낮음 / 검색 실패(흐름 계속)."""
    cache = tmp_path / "c.json"
    none = run(conn, family=None, product=None, tmp=cache)
    assert (none.candidates, none.notes) == ([], [NOTE_NO_FAMILY])
    unknown = run(conn, code="Z.99", tmp=cache)
    assert unknown.method == "SYMPTOM" and NOTE_CODE_UNKNOWN in unknown.notes
    low = run(conn, query="zzzz qqqq", tmp=cache)
    assert all(c.score < LOW_SCORE for c in low.candidates) and NOTE_LOW in low.notes
    failed = run(conn, embedder=WordCountEmbedder(fail_times=9), vectors=SymptomVectors(None))
    assert (failed.candidates, failed.notes) == ([], [NOTE_FAILED])


def test_not_diagnosed_category(conn, tmp_path):
    """FR-018 처리 1: DEFECT·INSTALL·WARRANTY가 아니면 진단하지 않는다(None = 단계 없음)."""
    assert run(conn, category="QUOTE", tmp=tmp_path / "c.json") is None
    assert run(conn, category="INSTALL", tmp=tmp_path / "c.json") is not None


def test_symptom_cache(conn, tmp_path):
    """조장 결정 2026-10-23: 벡터는 파일 캐시. 두 번째부터는 증상 문장을 다시 임베딩하지 않고, 바뀐 문장만 만든다."""
    path = tmp_path / "c.json"
    first = CountingEmbedder()
    run(conn, family="HMI", product="HMI-XGT-iXP90", embedder=first, tmp=path)
    hmi = conn.execute("SELECT count(*) FROM ref.fault WHERE family = 'HMI'").fetchone()[0]
    assert len(first.texts) == hmi + 1 and path.exists()  # 증상 n개 + 질문 1개
    again = CountingEmbedder()
    run(conn, family="HMI", product="HMI-XGT-iXP90", embedder=again, vectors=SymptomVectors(path))  # 새 서버(파일만 남음)
    assert len(again.texts) == 1  # 질문만
    conn.execute("SAVEPOINT s")
    conn.execute("UPDATE ref.fault SET symptom = symptom || ' (edited)' WHERE fault_id = (SELECT min(fault_id) FROM ref.fault WHERE family = 'HMI')")
    changed = CountingEmbedder()
    run(conn, family="HMI", product="HMI-XGT-iXP90", embedder=changed, vectors=SymptomVectors(path))
    conn.execute("ROLLBACK TO SAVEPOINT s")
    assert len(changed.texts) == 2 and any(t.endswith("(edited)") for t in changed.texts)


def test_exact_narrowed_by_product(conn, tmp_path):
    """C-133: 같은 제품군·에러 코드 행이 여럿이면 그 제품에 걸린 행(ref.fault_product)으로 좁힌다."""
    rows = conn.execute("""SELECT f.error_code, fp.product_code, count(*) OVER (PARTITION BY f.family, f.error_code)
                             FROM ref.fault f JOIN ref.fault_product fp USING (fault_id)
                            WHERE f.family = 'DRIVE' AND f.error_code = 'E.OC'""").fetchall()
    code, product, _ = rows[0]
    allowed = {r[0] for r in conn.execute("""SELECT f.fault_id FROM ref.fault f JOIN ref.fault_product fp USING (fault_id)
                                              WHERE f.family = 'DRIVE' AND f.error_code = %s AND fp.product_code = %s""",
                                          (code, product)).fetchall()}
    got = run(conn, family="DRIVE", product=product, code=code, query="overcurrent trip", tmp=tmp_path / "c.json")
    assert {c.fault_id for c in got.candidates} == allowed and all(c.method == "EXACT" for c in got.candidates)


# --- 처리 흐름 ---

L2_PLC = {"fields": [field("product_model", "PLC-XGB-XBM-DR16S"), field("serial_no", "XBM-2024-001"),
                     field("error_code", "P.06")]}
PLC_REPLY = {"body": "Please check the base power supply (TG-PLC-XGB §3).", "citations": [], "numbers_used": []}


def defect_plc(api):
    return intake(api, "CSV1-000007", L1=[l1("DEFECT", "en", "NONE", "base power fault cpu does not start")],
                  L2=[L2_PLC], L4=[PLC_REPLY], L7=[{"gloss": "베이스 전원을 점검해 주세요."}])


def steps(api, detail):
    """그 문의의 마지막 실행 단계들(단계 이름 → (input_json, output_json))."""
    return {r[0]: (r[1], r[2]) for r in api[2].execute(
        "SELECT step_name, input_json, output_json FROM svc.agent_step WHERE run_id = %s ORDER BY step_order",
        (detail["run"]["run_id"],)).fetchall()}


def test_ac_018_3_quote_skips(api):
    """AC-018-3: CSV1-000004(QUOTE) → 진단 단계(Q8a)가 실행되지 않는다."""
    detail = quote(api)
    sub = detail["sub_tickets"][0]
    assert "Q8a" not in steps(api, detail) and "Q6" in steps(api, detail)
    assert sub["diagnosis"] is None and "C-08" not in {r["id"] for r in sub["evidence_rows"]}


def test_ac_018_4_not_in_draft_input(api):
    """AC-018-4: 진단 후보가 있는 문의 → 답변 초안 단계의 입력 기록과 L4 지시문에 진단 후보가 없다."""
    detail = defect_plc(api)
    sub = detail["sub_tickets"][0]
    rec = steps(api, detail)
    assert rec["Q8a"][1]["fault_candidates"][0]["fault_id"] == "FLT-028"
    names = rec["Q10"][0]["field_names"]
    assert names and not any("fault" in n or "diagnos" in n for n in names)
    # 고장 사전의 원인·점검 문장은 문제 해결 안내서(TG) 절에도 그대로 있어, 고장 사전 고유값(fault_id)으로 본다
    l4 = [p for c, p in api[1].fake.prompts if c == "L4"]  # 대조가 어긋나면 1회 다시 만든다(§3-4)
    assert l4 and all("FLT-" not in p for p in l4)


def test_detail_shows_diagnosis(api):
    """FR-018 출력, 화면 정의서 v1 C-08, AC-024-1: 상세에 진단 후보와 근거 줄 "고장 진단"."""
    detail = defect_plc(api)
    sub = detail["sub_tickets"][0]
    top = sub["diagnosis"]["fault_candidates"][0]
    assert (top["fault_id"], top["method"], top["replace_required"]) == ("FLT-028", "EXACT", True)
    row = {r["id"]: r for r in sub["evidence_rows"]}["C-08"]
    assert row["result"] == "FLT-028 (정확 일치)" and row["why"]["rule"]["fault_id"] == "FLT-028"
    assert row["why"]["step"]["step_name"] == "Q8a"
    assert sub["sub_ticket"]["evidence_json"] and all(c["doc_id"] != "FLT-028" for c in sub["sub_ticket"]["evidence_json"])


def test_blocking_still_diagnosed(api):
    """기술 명세서 §2: 진단은 정보 요청 여부와 상관없이 규칙 단계 바로 뒤에 돈다(막는 정보가 있는 CSV1-000017)."""
    from tests.acceptance.test_ticket_detail import info_request

    detail = info_request(api)
    sub = detail["sub_tickets"][0]
    assert sub["sub_ticket"]["missing_blocking_info"] and sub["diagnosis"] is not None


def test_diagnosis_failure_keeps_flow(api, monkeypatch):
    """FR-018 예외 4행: 진단이 실패해도 흐름은 계속되고 그 문의는 실패가 아니다."""
    from app.retrieval import fault

    monkeypatch.setattr(fault, "embed_texts", lambda *a, **k: (_ for _ in ()).throw(LlmTimeout("t")))
    detail = intake(api, "CSV1-000055", L1=[l1("DEFECT", "en", "NONE", "logging stops memory full")],
                    L2=[{"fields": [field("product_model", "HMI-XGT-iXP90")]}],
                    L3=[{"body": "Please send the serial number.", "requested_fields": ["serial_no"]}],
                    L7=[{"gloss": "제조번호를 보내 주세요."}])
    sub = detail["sub_tickets"][0]
    assert sub["diagnosis"]["notes"] == [NOTE_FAILED] and not sub["sub_ticket"]["pipeline_error"]


# --- 채점(정답 열을 읽는 시험) ---


def test_ac_018_5_escalation_agreement(conn, tmp_path):
    """AC-018-5: 에러 코드가 정확히 맞는 고장 문의에서 1순위의 교체·현장 출동 표시를 정답 이관 사유와 비교해 일치율을 보고한다."""
    gold = conn.execute("""SELECT t.ticket_id, t.product_code, p.family, t.error_code_reported, t.escalated, t.escalation_reason
                             FROM gold.ticket_gold t JOIN ref.product p USING (product_code)
                            WHERE t.category_code = 'DEFECT' AND t.error_code_reported IS NOT NULL""").fetchall()
    vectors = SymptomVectors(tmp_path / "c.json")
    escalated = rma = onsite = total = 0
    for _, product, family, code, was_escalated, reason in gold:
        got = diagnose(conn, WordCountEmbedder(), "DEFECT", family, product, code, code, vectors)
        if got.method != "EXACT":
            continue
        top = got.candidates[0]
        total += 1
        escalated += bool(top.replace_required or top.onsite_required) == (was_escalated == "Y")  # ① 이관 여부
        rma += top.replace_required == (reason == "RMA_REQUIRED")  # ② 사유별(P1·SAFETY는 두 사유가 아님)
        onsite += top.onsite_required == (reason == "ONSITE_REQUIRED")
    print(f"\nAC-018-5 정확 일치 {total}건: 이관 여부 일치 {escalated}/{total}, "
          f"교체↔RMA_REQUIRED {rma}/{total}, 현장 출동↔ONSITE_REQUIRED {onsite}/{total}")
    assert total == 234  # tickets.csv DEFECT 중 에러 코드가 있는 234건은 모두 고장 사전과 맞는다
    assert 0 < escalated <= total and 0 < rma <= total and 0 < onsite <= total
