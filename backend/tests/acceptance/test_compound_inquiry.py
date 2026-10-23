"""복합 문의 분리와 답변 구성 완료 기준 (FR-006, FR-022, AC-036-4, 변경 add-compound-inquiry).

CSV1-000008(아랍어, 펌웨어 + 매뉴얼)을 API로 접수한다. 언어 모델은 대역 Transport, DB 쓰기는 모두 롤백한다.
"""

from __future__ import annotations

import re

from app.llm.client import LlmTimeout
from app.llm.wrap import F2_CLOSING, F2_GREETING
from app.pipeline.compose import FLAG_STATUS_LIST_MISSING, status_lines
from app.pipeline.state import SubTicketState
from tests.acceptance.test_drafts import field
from tests.acceptance.test_run_log import runs_of, steps_of
from tests.acceptance.test_ticket_detail import api, index, intake, send  # noqa: F401  (api 픽스처)

SOURCE = "CSV1-000008"
FW_PARAGRAPH = "Your firmware is already the latest version (RN-ESS-BMS-V3 §1)."
MANUAL_PARAGRAPH = "The installation guide for your controller is listed in our documents (DS-ESS-BMS-V3 §1)."
WRAP = {"greeting": "مرحبا،", "closing": "مع التحية."}
GLOSS = {"gloss": "대역"}
L2_FW = {"fields": [field("product_model", "ESS-BMS-V3"), field("current_fw", "3.40")]}


def request(seq, category, query, urgency="NONE"):
    return {"seq": seq, "category_code": category, "category_confidence": 0.9, "evidence_sentences": [f"s{seq}"],
            "urgency_flag": urgency, "urgency_evidence": None, "query_en": query}


def l1_compound(*requests):
    return {"body_language": "ar", "body_language_confidence": 0.95, "sub_tickets": list(requests)}


FW = request(1, "FW_UPDATE", "latest firmware ESS BMS Controller V3 release notes", "PROD_IMPACT")
MANUAL = request(2, "MANUAL", "ESS BMS Controller V3 manual datasheet document")


def compound(api, l4=None, l5=None, l1=None, **extra):
    replies = {"L1": [l1 or l1_compound(FW, MANUAL)], "L2": [L2_FW],
               "L4": l4 or [{"body": FW_PARAGRAPH, "citations": [], "numbers_used": []},
                            {"body": MANUAL_PARAGRAPH, "citations": [], "numbers_used": []}],
               "L5": l5 or [WRAP], "L7": [GLOSS], **extra}
    return intake(api, SOURCE, **replies)


def sub(detail, seq):
    return next(s for s in detail["sub_tickets"] if s["sub_ticket"]["seq"] == seq)


def mail(detail, seq):
    (draft,) = [d for d in sub(detail, seq)["drafts"] if d["message_type"] == "FINAL_REPLY"]
    return draft


def no_evidence(api, part):
    """svc.sub_ticket.no_evidence_flag (FR-021 근거 없음 표시)."""
    return api[2].execute("SELECT no_evidence_flag FROM svc.sub_ticket WHERE sub_ticket_id = %s",
                          (part["sub_ticket"]["sub_ticket_id"],)).fetchone()[0]


def status_part(body):
    return body[body.index("Status of your requests:"):]


# --- FR-006 ---


def test_ac_006_1_split(api):
    """AC-006-1: CSV1-000008 → FW_UPDATE;MANUAL, 복합 문의 표시, 처리 2개(하위 문의 run 2개)."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    assert detail["ticket"]["category_code"] == "FW_UPDATE;MANUAL" and detail["ticket"]["multi_yn"]
    assert [s["sub_ticket"]["sub_ticket_id"] for s in detail["sub_tickets"]] == [f"{tid}-1", f"{tid}-2"]
    sub_runs = [r for r in runs_of(api, tid) if r["sub_ticket_id"]]
    assert sorted(r["sub_ticket_id"] for r in sub_runs) == [f"{tid}-1", f"{tid}-2"]
    assert all(r["status"] == "SUCCESS" for r in sub_runs)


def test_ac_006_2_single(api):
    """AC-006-2: CSV1-000004 → QUOTE, 복합 표시 꺼짐, 처리 1개."""
    from tests.acceptance.test_ticket_detail import quote
    detail = quote(api)
    assert detail["ticket"]["category_code"] == "QUOTE" and not detail["ticket"]["multi_yn"]
    (run,) = runs_of(api, detail["ticket"]["ticket_id"])
    assert run["sub_ticket_id"] is None and "T5" not in [s["step_name"] for s in steps_of(api, run["run_id"])]


def test_ac_006_3_rules_per_sub(api):
    """AC-006-3: 하위 문의 run마다 자기 유형으로 우선순위·부서·SLA 목표를 계산했다."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    by_sub = {r["sub_ticket_id"]: r for r in runs_of(api, tid) if r["sub_ticket_id"]}
    routing = set()
    for seq in (1, 2):
        row = sub(detail, seq)["sub_ticket"]
        steps = {s["step_name"]: s["output_json"] for s in steps_of(api, by_sub[row["sub_ticket_id"]]["run_id"])}
        assert steps["Q3"]["priority_rule_id"] == row["priority_rule_id"]
        assert steps["Q4"]["routing_rule_id"] == row["routing_rule_id"] and row["category_code"] in row["routing_rule_id"]
        assert steps["Q6"]["sla_id"] == row["sla_id"] and row["category_code"] in row["sla_id"]
        routing.add(row["routing_rule_id"])
    assert routing == {"RT-ESS-FW_UPDATE", "RT-ESS-MANUAL"}
    # 각자의 긴급도: 펌웨어는 PROD_IMPACT, 매뉴얼은 NONE
    assert (sub(detail, 1)["sub_ticket"]["urgency_flag"], sub(detail, 2)["sub_ticket"]["urgency_flag"]) == ("PROD_IMPACT", "NONE")


def test_ac_036_4_runs(api):
    """AC-036-4: 문의 1·2의 run이 따로 있고 답변 구성(T5)은 티켓 run(순번 없음)에 있다."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    runs = runs_of(api, tid)
    (ticket_run,) = [r for r in runs if r["sub_ticket_id"] is None]
    names = [s["step_name"] for s in steps_of(api, ticket_run["run_id"])]
    assert names[0] == "T2" and names.count("T5") == 2 and names[-1] == "T6"
    for r in runs:
        if r["sub_ticket_id"]:
            sub_names = [s["step_name"] for s in steps_of(api, r["run_id"])]
            assert sub_names[0] == "Q1" and "T5" not in sub_names and "T2" not in sub_names and "Q10" in sub_names


def test_failed_sub_keeps_others(api, monkeypatch):
    """FR-006 예외 3행: 한 하위 문의의 처리가 실패해도 나머지는 계속, 실패한 문의는 상태 목록에 "담당자 확인 중"."""
    from app.pipeline import graph
    real = graph.add_evidence

    def broken(conn, embedder, state, subs=None):
        if subs and subs[0].seq == 2:
            raise RuntimeError("검색 오류 시험")
        return real(conn, embedder, state, subs)

    monkeypatch.setattr(graph, "add_evidence", broken)
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    assert sub(detail, 2)["sub_ticket"]["pipeline_error"].endswith("자동 처리 실패. 다시 시도")
    assert sub(detail, 2)["sub_ticket"]["status"] == "NEW" and sub(detail, 1)["sub_ticket"]["status"] == "IN_PROGRESS"
    assert "2. Manual and document: a member of our team is checking this." in mail(detail, 1)["body"]
    (ticket_run,) = [r for r in runs_of(api, tid) if r["sub_ticket_id"] is None]
    assert ticket_run["status"] == "PARTIAL"


# --- FR-022 ---


def test_ac_022_1_mail(api):
    """AC-022-1: 펌웨어 하위 문의 메일 = 인사말 + 펌웨어 단락(RN 인용) + 상태 목록("2. …") + 맺음말."""
    detail = compound(api)
    body = mail(detail, 1)["body"]
    assert body.startswith(WRAP["greeting"]) and body.endswith(WRAP["closing"])
    assert FW_PARAGRAPH in body and "(RN-ESS-BMS-V3 §1)" in body
    assert status_part(body).splitlines()[1:3] == ["1. Firmware update: answered in this email.",
                                                   "2. Manual and document: we are still working on this."]


def test_ac_022_2_send_resolves_only_that_sub(api):
    """AC-022-2: 펌웨어 메일을 발송하면 FW_UPDATE 하위 문의만 RESOLVED, MANUAL은 그대로."""
    detail = compound(api)
    tid = detail["ticket"]["ticket_id"]
    before = sub(detail, 2)["sub_ticket"]["status"]
    res = send(api, mail(detail, 1), override=True)
    assert res.status_code == 200, res.text
    after = api[0].get(f"/tickets/{tid}").json()
    assert sub(after, 1)["state"]["status"] == "RESOLVED" and sub(after, 2)["state"]["status"] == before


def test_ac_022_3_no_evidence_sub(api, monkeypatch):
    """AC-022-3: 매뉴얼 하위 문의의 근거 후보가 비면 펌웨어 메일 상태 목록에 "담당자 확인 중", 매뉴얼에 "근거 없음"."""
    from app.pipeline import evidence
    real = evidence.search_evidence

    def empty_for_manual(conn, embedder, query, category, *args, **kwargs):
        found = real(conn, embedder, query, category, *args, **kwargs)
        if category == "MANUAL":
            found.candidates = []
            found.flags = [*found.flags, "근거 없음"]
        return found

    monkeypatch.setattr(evidence, "search_evidence", empty_for_manual)
    detail = compound(api, l4=[{"body": FW_PARAGRAPH, "citations": [], "numbers_used": []}])
    assert "2. Manual and document: a member of our team is checking this." in mail(detail, 1)["body"]
    manual = sub(detail, 2)
    assert not [d for d in manual["drafts"] if d["message_type"] == "FINAL_REPLY"]
    assert not manual["sub_ticket"]["pipeline_error"] and no_evidence(api, manual)


def test_ac_022_4_no_deadline(api):
    """AC-022-4: 상태 목록에 SLA 목표 시간이나 완료 예정 시각이 없다."""
    detail = compound(api)
    for seq in (1, 2):
        part = status_part(mail(detail, seq)["body"])
        assert not re.search(r"\b\d+\s*(h|hours?|days?)\b", part, re.I)
        assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", part)
        assert not re.search(r"\b(deadline|within|expected|estimated|by)\b", part, re.I)


def test_wrap_failure_uses_f2(api):
    """FR-022 출력, 부록 A-3 F-2: L5가 두 번 실패하면 고정 인사말·맺음말."""
    detail = compound(api, l5=[LlmTimeout("t")])
    body = mail(detail, 1)["body"]
    assert body.startswith(F2_GREETING) and body.endswith(F2_CLOSING)


def test_mail_check_allows_request_numbers(api):
    """FR-022 처리 5, 에이전트 설계서 6-1 2번: 상태 목록의 문의 번호(1, 2)는 숫자 대조를 통과한다."""
    detail = compound(api)
    for seq in (1, 2):
        draft = mail(detail, seq)
        assert draft["check"]["passed_yn"], draft["check"]


def test_info_request_sub_is_separate(api):
    """FR-022 처리 2: 정보 요청으로 간 하위 문의는 자기 정보 요청을 따로, 다른 하위 문의의 메일은 그대로."""
    l2 = [L2_FW, {"fields": []}]  # 매뉴얼 쪽은 제품 모델이 비어 막는 정보가 있으면 정보 요청
    detail = compound(api, L2=l2, L3=[{"body": "Please send the Product model / ordering code.",
                                         "requested_fields": ["product_model"]}])
    kinds = {seq: sorted(d["message_type"] for d in sub(detail, seq)["drafts"]) for seq in (1, 2)}
    assert kinds[1] == ["FINAL_REPLY"] and sub(detail, 2)["sub_ticket"]["missing_blocking_info"]
    assert kinds[2] == ["INFO_REQUEST"]
    assert "Status of your requests:" not in sub(detail, 2)["drafts"][0]["body"]
    assert "2. Manual and document: waiting for the information we requested in a separate email." not in mail(detail, 1)["body"]


def test_status_lines_cover_every_sub():
    """FR-022 예외 1행, 부록 A-2: 줄 수 = 하위 문의 수, 상태별 문장."""
    subs = [SubTicketState(sub_ticket_id=f"T-{n}", ticket_id="T", seq=n, category_code=c)
            for n, c in [(1, "QUOTE"), (2, "RETURN"), (3, "WARRANTY"), (4, "DEFECT")]]
    lines = status_lines(subs, "T-1", {"T-2": "WAITING_CUSTOMER", "T-3": "RESOLVED", "T-4": "ESCALATED"}, set())
    assert lines == ["1. Quotation: answered in this email.",
                     "2. Return and exchange: waiting for the information we requested in a separate email.",
                     "3. Warranty: answered previously.",
                     "4. Fault: being reviewed by our specialist team."]
    assert FLAG_STATUS_LIST_MISSING == "상태 목록 누락"


def test_reply_reprocess_lists_every_sub(api):
    """FR-022 처리 3·예외 1행: 회신으로 매뉴얼 문의만 다시 처리해도 그 메일의 상태 목록에 하위 문의 2개가 모두 있다."""
    from tests.acceptance.test_drafts import FakeTransport
    detail = compound(api, L2=[L2_FW, {"fields": []}], L3=[{"body": "Please send the Product model / ordering code.",
                                                           "requested_fields": ["product_model"]}])
    tid = detail["ticket"]["ticket_id"]
    (ask,) = sub(detail, 2)["drafts"]
    assert send(api, ask).status_code == 200
    client, clients, _ = api
    clients.fake = FakeTransport(L2=[{"fields": [field("product_model", "ESS-BMS-V3")]}],
                                 L4=[{"body": MANUAL_PARAGRAPH, "citations": [], "numbers_used": []}],
                                 L5=[WRAP], L7=[GLOSS])
    res = client.post(f"/tickets/{tid}/replies", headers={"X-Agent-Id": "TS_LV_AGENT_09"},
                      json={"body": "The model is ESS-BMS-V3."})
    assert res.status_code == 201, res.text
    after = client.get(f"/tickets/{tid}").json()
    body = mail(after, 2)["body"]
    assert status_part(body).splitlines()[1:3] == ["1. Firmware update: we are still working on this.",
                                                   "2. Manual and document: answered in this email."]
    assert FLAG_STATUS_LIST_MISSING not in str(mail(after, 2)["review_marks"])


def test_compose_failure_drops_bare_paragraph(api, monkeypatch):
    """FR-006 예외 3행: 메일 구성(T5)이 실패한 문의는 인사말·상태 목록 없는 단락을 초안으로 남기지 않는다."""
    from app.pipeline import graph
    real = graph.compose_mail

    def broken(transport, draft, sub, *args):
        if sub.seq == 2:
            raise RuntimeError("구성 오류 시험")
        return real(transport, draft, sub, *args)

    monkeypatch.setattr(graph, "compose_mail", broken)
    detail = compound(api)
    assert not [d for d in sub(detail, 2)["drafts"] if d["message_type"] == "FINAL_REPLY"]
    assert sub(detail, 2)["sub_ticket"]["pipeline_error"] and not no_evidence(api, sub(detail, 2))
    tid = detail["ticket"]["ticket_id"]
    (run,) = [r for r in runs_of(api, tid) if r["sub_ticket_id"] == f"{tid}-2"]
    assert [s["step_name"] for s in steps_of(api, run["run_id"])][-1] == "T5"
