"""처리 흐름 그래프 (기술 명세서 v1.4 §1-2 LangGraph, §2-1 하위 문의 그래프, §2-5 분기③④).

understand(T1·T2·Q1) → rules(Q2~Q6) → diagnose(Q8a 고장 진단, 고장 계열만) → info_request(분기③ 막는 정보가 있는 하위 문의: Q7, L3)
  → evidence(나머지 하위 문의: Q8·Q9) → reply(분기④ 근거 있음? → Q10 L4 + Q11 대조)
  → compose(복합 문의면 T5 메일 구성, L5) → gloss(Q13, L7) → verify(Q14, L8) → 끝
노드는 하위 문의를 순번 순으로 처리하고, 한 하위 문의의 오류는 그 문의에만 남긴다(FR-006 예외 3행, C-90).
단일 문의는 n = 1인 같은 흐름이다(§2-1). 고객에게 가는 글은 모두 DRAFT다.
노드는 RunLog.timed로 감싸 시간과 언어 모델 사용량을 모은다(FR-036, §6-5, 변경 add-run-log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from psycopg import Connection

from app.llm.client import RecordingTransport, Transport
from app.llm.drafts import Draft, Source, write_gloss, write_info_request, write_reply
from app.pipeline.compose import compose_mail
from app.llm.embed import Embedder
from app.llm.verify import verify_draft
from app.pipeline.diagnose import add_diagnosis
from app.pipeline.evidence import add_evidence
from app.pipeline.rules_step import apply_rules
from app.pipeline.runlog import RunLog, track
from app.pipeline.state import SubTicketState, TicketState
from app.rules.required_info import RequiredInfoResult
from app.pipeline.understand import MESSAGE_RETRY, understand_ticket
from app.rules.lookup import CustomerNotFound


class GraphState(TypedDict, total=False):
    ticket_input: dict[str, Any]
    state: TicketState
    labels: dict[str, dict[str, str]]  # 하위 문의별 항목 라벨(Q5 결과)
    required: dict[str, RequiredInfoResult]  # 하위 문의별 필수정보 결과(저장용)
    llm_field_names: dict[str, list[str]]  # 호출별 넣은 항목 이름(실행 기록용)
    drafts: list[Draft]
    sources: dict[str, list[Source]]  # 하위 문의별 근거 절(L4·L8 입력)
    run_status: str  # SUCCESS / FAILED (schema.sql agent_run.status)
    error_type: str | None
    message: str | None


@dataclass
class RunOutcome:
    state: TicketState | None
    run_status: str
    drafts: list[Draft] = field(default_factory=list)
    error_type: str | None = None
    message: str | None = None
    required: dict[str, RequiredInfoResult] = field(default_factory=dict)
    sources: dict[str, list[Source]] = field(default_factory=dict)
    llm_field_names: dict[str, list[str]] = field(default_factory=dict)
    runlog: RunLog | None = None  # 단계별 시간·사용량(FR-036)


def build_graph(conn: Connection, transport: Transport, embedder: Embedder, understand_fn=None,
                runlog: RunLog | None = None):
    """understand_fn: 첫 노드(T1·T2·Q1)를 바꿔 끼운다. 고객 회신 재처리는 Q1부터(§2-4, reprocess.reextract).

    runlog: 있으면 노드를 감싸고 Transport의 호출을 그 기록에 남긴다(FR-036 처리 2).
    """
    first = understand_fn or understand_ticket
    if runlog is not None:
        transport = RecordingTransport(transport, runlog)

    def understand(gs: GraphState) -> GraphState:
        out = first(conn, transport, gs["ticket_input"])
        return {"state": out.state, "run_status": out.run_status, "error_type": out.error_type,
                "message": out.message, "drafts": [], "llm_field_names": out.llm_field_names or {}}

    def rules(gs: GraphState) -> GraphState:
        try:
            required = apply_rules(conn, gs["state"])
        except CustomerNotFound as exc:  # §2-2 Q2 "고객 없음 → 접수 거부(D25)"
            return {"run_status": "FAILED", "error_type": "VALIDATION", "message": str(exc)}
        return {"labels": {k: v.labels for k, v in required.items()}, "required": required}

    def each(subs: list[SubTicketState], work, step: str) -> None:
        """하위 문의마다 work(sub). 오류가 나면 그 하위 문의만 실패로 두고 나머지는 계속(FR-006 예외 3행, §2-2 T3)."""
        for sub in sorted(subs, key=lambda s: s.seq):
            if sub.pipeline_error:
                continue
            try:
                with track(transport, sub.sub_ticket_id), conn.transaction():  # 저장점: DB 오류도 그 문의만
                    work(sub)
            except Exception as exc:  # noqa: BLE001 — 어떤 오류든 그 하위 문의의 실패로 남긴다
                sub.pipeline_error = f"{getattr(exc, 'error_type', 'UNKNOWN')}: {MESSAGE_RETRY}"
                sub.failed_step = step

    def blocking(gs: GraphState) -> list[SubTicketState]:  # 분기③
        return [s for s in gs["state"].sub_tickets if s.missing_blocking_info]

    def answering(gs: GraphState) -> list[SubTicketState]:
        return [s for s in gs["state"].sub_tickets if not s.missing_blocking_info]

    def diagnose(gs: GraphState) -> GraphState:  # Q8a: 정보 요청 여부와 상관없이 규칙 단계 바로 뒤(§2)
        state = gs["state"]
        each(state.sub_tickets, lambda sub: add_diagnosis(conn, embedder, sub), "Q8a")
        return {"state": state}

    def info_request(gs: GraphState) -> GraphState:
        state, drafts = gs["state"], list(gs.get("drafts", []))

        def work(sub: SubTicketState) -> None:
            optional = [f for f in sub.missing_info if f not in sub.missing_blocking_info]
            name = conn.execute("SELECT product_name FROM ref.product WHERE product_code = %s",
                                (sub.product_code,)).fetchone()
            draft = write_info_request(transport, sub.sub_ticket_id, state.language, sub.category_code,
                                       name[0] if name else None, sub.missing_blocking_info, optional,
                                       gs["labels"].get(sub.sub_ticket_id, {}))
            sub.flags += [f for f in draft.flags if f not in sub.flags]
            drafts.append(draft)

        each(blocking(gs), work, "Q7")
        return {"drafts": drafts}

    def evidence(gs: GraphState) -> GraphState:
        state = gs["state"]
        each(answering(gs), lambda sub: add_evidence(conn, embedder, state, [sub]), "Q8")
        return {"state": state}

    def reply(gs: GraphState) -> GraphState:
        state, drafts, by_sub = gs["state"], list(gs.get("drafts", [])), {}

        def work(sub: SubTicketState) -> None:
            sources = by_sub[sub.sub_ticket_id] = []
            for c in sub.doc_candidates:
                row = conn.execute("SELECT section_title, text FROM ref.doc_chunk WHERE chunk_id = %s",
                                   (c.chunk_id,)).fetchone()
                if row:
                    sources.append(Source(c.doc_id, c.section_no, row[0], row[1]))
            labels = gs["labels"].get(sub.sub_ticket_id, {})
            draft, flags = write_reply(
                transport, sub.sub_ticket_id, state.language, sub.category_code, sub.evidence_sentences,
                [(pf.field, pf.value_norm or pf.value_raw) for pf in sub.provided_fields],
                [(lv.item, lv.value, lv.unit, f"{lv.source_table}:{lv.source_key}") for lv in sub.lookups],
                sources, [labels.get(f, f) for f in sub.missing_info], composite=state.multi_yn,
            )
            sub.flags += [f for f in flags if f not in sub.flags]
            if draft is not None:
                sub.draft_check = draft.check
                drafts.append(draft)

        each(answering(gs), work, "Q10")
        return {"drafts": drafts, "sources": by_sub}

    def compose(gs: GraphState) -> GraphState:  # T5: 복합 문의만(FR-022)
        state = gs["state"]
        if not state.multi_yn:
            return {}
        subs = {s.sub_ticket_id: s for s in state.sub_tickets}
        rows = conn.execute("SELECT sub_ticket_id, seq, category_code, status FROM svc.sub_ticket WHERE ticket_id = %s",
                            (state.ticket_id,)).fetchall()
        statuses = {r[0]: r[3] for r in rows}
        # 상태 목록은 이 티켓의 하위 문의 n개 모두(FR-022 처리 3). 회신 재처리처럼 일부만 처리해도 나머지 줄을 넣는다
        everyone = list(state.sub_tickets) + [
            SubTicketState(sub_ticket_id=r[0], ticket_id=state.ticket_id, seq=r[1], category_code=r[2])
            for r in rows if r[0] not in subs]
        replied = {d.sub_ticket_id for d in gs["drafts"] if d.message_type == "FINAL_REPLY"}
        # 처리 실패, 또는 답변으로 갔는데 초안이 없음(근거 없음·생성 실패) → "담당자 확인 중"(FR-022 처리 7, 예외 3행)
        checking = {s.sub_ticket_id for s in state.sub_tickets
                    if s.pipeline_error or (not s.missing_blocking_info and s.sub_ticket_id not in replied)}
        mails = [d for d in gs["drafts"] if d.message_type == "FINAL_REPLY"]

        def work(sub: SubTicketState) -> None:
            draft = next(d for d in mails if d.sub_ticket_id == sub.sub_ticket_id)
            compose_mail(transport, draft, sub, everyone, statuses, checking,
                         gs.get("sources", {}).get(sub.sub_ticket_id, []))
            sub.draft_check = draft.check
            sub.flags += [f for f in draft.flags if f not in sub.flags]

        each([subs[d.sub_ticket_id] for d in mails], work, "T5")
        # 구성에 실패한 문의의 단락만 있는 초안은 내보내지 않는다(인사말·상태 목록 없는 메일 방지)
        return {"drafts": [d for d in gs["drafts"] if not (d.message_type == "FINAL_REPLY"
                                                          and subs[d.sub_ticket_id].failed_step == "T5")]}

    def gloss(gs: GraphState) -> GraphState:
        out = []
        for d in gs["drafts"]:
            with track(transport, d.sub_ticket_id):
                out.append(write_gloss(transport, d))
        return {"drafts": out}

    def verify(gs: GraphState) -> GraphState:  # Q14: 실패해도 실행은 SUCCESS(FR-049 예외 2행)
        subs = {s.sub_ticket_id: s for s in gs["state"].sub_tickets}
        for draft in gs["drafts"]:
            sub = subs[draft.sub_ticket_id]
            lookups = [(lv.item, lv.value, lv.unit, f"{lv.source_table}:{lv.source_key}") for lv in sub.lookups]
            with track(transport, sub.sub_ticket_id):
                draft.verify = verify_draft(transport, draft, sub.evidence_sentences,
                                            gs.get("sources", {}).get(sub.sub_ticket_id, []), lookups)
            sub.verify_findings = None if draft.verify.error else draft.verify.findings
        return {"drafts": gs["drafts"]}

    def after_understand(gs: GraphState) -> str:
        return "rules" if gs["run_status"] == "SUCCESS" else END

    def after_rules(gs: GraphState) -> str:
        return "diagnose" if gs.get("run_status") == "SUCCESS" else END

    graph = StateGraph(GraphState)
    order = [("understand", understand), ("rules", rules), ("diagnose", diagnose), ("info_request", info_request), ("evidence", evidence),
             ("reply", reply), ("compose", compose), ("gloss", gloss), ("verify", verify)]
    for name, node in order:
        graph.add_node(name, runlog.timed(name, node) if runlog is not None else node)
    graph.add_edge(START, "understand")
    graph.add_conditional_edges("understand", after_understand, ["rules", END])
    graph.add_conditional_edges("rules", after_rules, ["diagnose", END])
    for (a, _), (b, _) in zip(order[2:], order[3:]):
        graph.add_edge(a, b)
    graph.add_edge("verify", END)
    return graph.compile()


def run_ticket(conn: Connection, transport: Transport, embedder: Embedder, ticket_input: dict[str, Any],
               understand_fn=None, runlog: RunLog | None = None) -> RunOutcome:
    runlog = runlog if runlog is not None else RunLog.from_settings()
    final = build_graph(conn, transport, embedder, understand_fn, runlog).invoke({"ticket_input": ticket_input})
    return RunOutcome(final.get("state"), final["run_status"], final.get("drafts", []),
                      final.get("error_type"), final.get("message"), final.get("required", {}),
                      final.get("sources", {}), final.get("llm_field_names", {}), runlog)
