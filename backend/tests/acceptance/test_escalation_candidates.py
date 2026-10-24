"""이관 후보 완료 기준 (FR-020, 변경 add-escalation-candidates).

AC-020-1~4·6~8은 접수 API로 처리 흐름을 돌린다(대역 언어 모델, 대역 임베딩, 롤백).
AC-020-5는 정답의 이관 부서를 읽는 채점 시험이다(CLAUDE.md 규칙 6 예외, 팀 정답지 대신 tickets.csv, C-147).
판정 함수의 예외는 함수 단위로 본다.
"""

from __future__ import annotations

from app.retrieval.fault import NOTE_FAILED, Diagnosis
from app.rules.escalation import NOTE_NO_DIAGNOSIS, NOTE_RULES_FAILED, escalation_candidates
from tests.acceptance.test_drafts import field, l1
from tests.acceptance.test_fault_diagnosis import defect_plc, steps
from tests.acceptance.test_ticket_detail import api, index, info_request, intake, rows  # noqa: F401  (api·index 픽스처)

GLOSS = [{"gloss": "제조번호를 보내 주세요."}]


def info(lang_body="Please send the serial number (nameplate).", fields=("serial_no",)):
    return [{"body": lang_body, "requested_fields": list(fields)}]


def found(detail):
    """첫 하위 문의의 이관 후보 (rule_id, 부서, 팀 규칙) 목록."""
    esc = detail["sub_tickets"][0]["escalation"]
    return [(c["rule_id"], c["dept"], c["team"]) for c in esc["escalation_candidates"]]


def test_ac_020_1_safety(api):
    """AC-020-1: 긴급도 SAFETY인 고장 문의 CSV1-000202 → 근거 RT-ESC-DEFECT-SAFETY. 같은 부서 후보는 한 줄(예외 3행)."""
    detail = intake(api, "CSV1-000202", L1=[l1("DEFECT", "ar", "SAFETY", "battery smoke")],
                    L2=[{"fields": [field("product_model", "ESS-BMS-V3"), field("error_code", "G.05")]}],
                    L3=info("يرجى إرسال Serial number (nameplate)."), L4=[{"body": "x", "citations": [], "numbers_used": []}],
                    L7=GLOSS)
    got = found(detail)
    assert ("RT-ESC-DEFECT-SAFETY", "FIELD_SVC", False) in got
    assert {c["reason"] for c in detail["sub_tickets"][0]["escalation"]["escalation_candidates"]} >= {"SAFETY"}
    row = rows(detail)["C-09"]
    assert row["label"] == "⑩ 이관 후보" and row["result"].startswith("FIELD_SVC — ") and "RT-ESC-DEFECT-SAFETY (SAFETY)" in row["result"]
    assert len({c[1] for c in got}) == len(row["result"].split(" / "))  # 부서별 한 줄


def test_ac_020_2_rma(api):
    """AC-020-2: 진단 1순위 FLT-028(교체 필요 Y)인 CSV1-000007 → RT-ESC-DEFECT-RMA의 부서 QA_CLAIM."""
    detail = defect_plc(api)
    assert detail["sub_tickets"][0]["diagnosis"]["fault_candidates"][0]["fault_id"] == "FLT-028"
    assert found(detail) == [("RT-ESC-DEFECT-RMA", "QA_CLAIM", False)]
    c = detail["sub_tickets"][0]["escalation"]["escalation_candidates"][0]
    assert (c["reason"], c["reason_code"]) == ("교체", "RMA_REQUIRED")
    assert rows(detail)["C-09"]["why"]["rules"][0]["rule_id"] == "RT-ESC-DEFECT-RMA"


def test_ac_020_3_none(api, monkeypatch):
    """AC-020-3: 진단 후보가 없고 SAFETY가 아닌 CSV1-000017 → "없음"과 FR-012의 이관 조건 문구, 진단 없음 표시."""
    monkeypatch.setattr("app.pipeline.diagnose.diagnose", lambda *a, **k: Diagnosis(notes=[NOTE_FAILED]))
    detail = info_request(api)
    esc = detail["sub_tickets"][0]["escalation"]
    assert esc["escalation_candidates"] == [] and NOTE_NO_DIAGNOSIS in esc["notes"]
    condition = api[2].execute("SELECT escalation_condition FROM ref.routing_rule WHERE rule_id = 'RT-LV_BREAKER-DEFECT'").fetchone()[0]
    assert esc["escalation_condition"] == condition
    assert rows(detail)["C-09"]["result"] == f"없음 — 이관 조건: {condition}"


def test_ac_020_4_status_unchanged(api):
    """AC-020-4: 후보가 켜진 문의도 상태는 ESCALATED가 아니고 escalated는 그대로."""
    detail = defect_plc(api)
    assert found(detail)
    sub_id = detail["sub_tickets"][0]["sub_ticket"]["sub_ticket_id"]
    status, escalated, to = api[2].execute(
        "SELECT status, escalated, escalated_to FROM svc.sub_ticket WHERE sub_ticket_id = %s", (sub_id,)).fetchone()
    assert status != "ESCALATED" and not escalated and to is None
    assert not api[2].execute("SELECT 1 FROM svc.ticket_status_history WHERE sub_ticket_id = %s AND to_status = 'ESCALATED'",
                              (sub_id,)).fetchone()


def test_ac_020_5_recall(conn):
    """AC-020-5: 정답에서 이관된 행 → 예상 이관 부서가 정답 이관 부서를 포함하는 비율(재현율)을 보고한다.

    정답 값(유형·긴급도·우선순위·에러 코드의 정확 진단·본문)으로 판정 함수를 부른다(C-147). 수치는 보고만 한다.
    """
    gold = conn.execute(
        """SELECT g.category_code, g.urgency_flag, g.priority, g.inquiry_body, g.escalated_to, g.escalation_reason,
                  (SELECT ARRAY[f.needs_onsite, f.needs_rma] FROM ref.fault f
                     LEFT JOIN ref.fault_product fp ON fp.fault_id = f.fault_id AND fp.product_code = g.product_code
                    WHERE f.family = p.family AND f.error_code = g.error_code_reported
                    ORDER BY fp.product_code IS NULL, f.fault_id LIMIT 1)
             FROM gold.ticket_gold g LEFT JOIN ref.product p USING (product_code)
            WHERE g.escalated = 'Y'""").fetchall()
    hit, by_reason, diagnosed = 0, {}, [0, 0]
    for category, urgency, priority, body, to, reason, fault in gold:
        top = (fault[0], fault[1]) if fault else None  # 에러 코드가 없으면 진단 없음으로 본다(증상 검색은 대역이라 쓰지 않음)
        got = escalation_candidates(conn, category, urgency, top, body, priority, None)
        ok = to in {c.dept for c in got.candidates}
        hit += ok
        if fault and reason in ("RMA_REQUIRED", "ONSITE_REQUIRED"):
            diagnosed[0], diagnosed[1] = diagnosed[0] + 1, diagnosed[1] + ok
        n, k = by_reason.get(reason, (0, 0))
        by_reason[reason] = (n + 1, k + ok)
    recall = hit / len(gold)
    print(f"\nAC-020-5 이관 후보 재현율 {hit}/{len(gold)} = {recall:.3f}")
    for reason, (n, k) in sorted(by_reason.items(), key=lambda x: -x[1][0]):
        print(f"  {reason}: {k}/{n}")
    print(f"  (정확 진단이 있는 교체·현장 출동 이관: {diagnosed[1]}/{diagnosed[0]})")
    assert len(gold) > 0 and 0 < recall <= 1  # 목표 수치는 팀 정답지 첫 측정 뒤 확정(AC-020-5)
    assert by_reason["SAFETY"][1] == by_reason["SAFETY"][0]  # 긴급도만 보는 행은 진단과 상관없이 모두 맞는다


def test_ac_020_6_return_quality(api):
    """AC-020-6: 반품 사유 "dead on arrival and does not power up"인 CSV1-000229 → QA_CLAIM, 팀 규칙."""
    detail = intake(api, "CSV1-000229", L1=[l1("RETURN", "en", "NONE", "return request")],
                    L2=[{"fields": [field("product_model", "TRF-OIL-1000"),
                                    field("return_reason", "The unit was dead on arrival and does not power up.")]}],
                    L3=info(), L4=[{"body": "x", "citations": [], "numbers_used": []}], L7=GLOSS)
    assert found(detail) == [("RT-ESC-TEAM-RETURN-QUALITY", "QA_CLAIM", True)]
    assert "(팀 규칙)" in rows(detail)["C-09"]["result"]
    assert rows(detail)["C-09"]["why"]["rules"][0]["escalation_dept"] == "QA_CLAIM"  # 설정 파일 행


def test_ac_020_7_damaged_packaging(api):
    """AC-020-7: 반품 사유 "damaged packaging and a cracked housing"인 CSV1-000200 → 이관 후보 없음."""
    detail = intake(api, "CSV1-000200", L1=[l1("RETURN", "en", "NONE", "return request")],
                    L2=[{"fields": [field("product_model", "RELAY-GMR-22"),
                                    field("return_reason", "The goods arrived with damaged packaging and a cracked housing.")]}],
                    L3=info(), L4=[{"body": "x", "citations": [], "numbers_used": []}], L7=GLOSS)
    assert found(detail) == [] and rows(detail)["C-09"]["result"].startswith("없음")


def test_ac_020_8_install_p1(api):
    """AC-020-8: 우선순위 P1인 설치 문의 CSV1-000133 → FIELD_SVC, 근거 RT-ESC-TEAM-INSTALL-P1(팀 규칙)."""
    detail = intake(api, "CSV1-000133", L1=[l1("INSTALL", "en", "SITE_DOWN", "commissioning stopped")],
                    L2=[{"fields": [field("product_model", "ESS-PCS-100kW")]}],
                    L3=info(), L4=[{"body": "x", "citations": [], "numbers_used": []}], L7=GLOSS)
    assert detail["sub_tickets"][0]["sub_ticket"]["priority"] == "P1"
    assert ("RT-ESC-TEAM-INSTALL-P1", "FIELD_SVC", True) in found(detail)
    assert "Q9a" in steps(api, detail)


def test_exceptions(conn, tmp_path):
    """FR-020 예외: 규칙을 읽을 수 없음 / 진단 없음 → SAFETY만 / 맞은 행 여럿은 모두."""
    broken = tmp_path / "rules.yaml"
    broken.write_text("- rule_id: X\n", encoding="utf-8")
    failed = escalation_candidates(conn, "DEFECT", "SAFETY", None, None, "P1", "cond", team_rules_file=broken)
    assert (failed.candidates, failed.notes, failed.failed) == ([], [NOTE_RULES_FAILED], True)
    safety_only = escalation_candidates(conn, "DEFECT", "SAFETY", None, None, "P1", None)
    assert [c.rule_id for c in safety_only.candidates] == ["RT-ESC-DEFECT-SAFETY"] and NOTE_NO_DIAGNOSIS in safety_only.notes
    every = escalation_candidates(conn, "DEFECT", "SAFETY", (True, True), None, "P1", None)
    assert [c.rule_id for c in every.candidates] == ["RT-ESC-DEFECT-ONSITE", "RT-ESC-DEFECT-RMA", "RT-ESC-DEFECT-SAFETY"]
    assert {c.dept for c in every.candidates} == {"FIELD_SVC", "QA_CLAIM"}
    quote = escalation_candidates(conn, "QUOTE", "NONE", None, None, "P3", None)
    assert (quote.candidates, quote.notes) == ([], [])  # 고장 계열이 아니면 진단 없음 표시도 없다


def test_q9a_step_failed_recorded(api, monkeypatch):
    """예외 2행: 규칙을 읽을 수 없으면 실행 기록 Q9a가 FAILED이고 흐름은 계속된다."""
    from app.rules import escalation
    monkeypatch.setattr(escalation, "_ops_rows", lambda conn: (_ for _ in ()).throw(RuntimeError("down")))
    detail = defect_plc(api)
    result, error = api[2].execute("SELECT result, error FROM svc.agent_step WHERE run_id = %s AND step_name = 'Q9a'",
                                   (detail["run"]["run_id"],)).fetchone()
    assert (result, error) == ("FAILED", NOTE_RULES_FAILED) and detail["sub_tickets"][0]["drafts"]
