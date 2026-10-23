"""처리 흐름 그래프 (기술 명세서 v1.4 §1-2 LangGraph, §2-1 하위 문의 그래프, §2-5 분기③④).

understand(T1·T2·Q1) → rules(Q2~Q6) → 분기③ 막는 정보?
  예     → info_request(Q7, L3) → gloss(Q13, L7) → verify(Q14, L8) → 끝
  아니오 → evidence(Q8·Q9) → reply(분기④ 근거 있음? → Q10 L4 + Q11 대조) → gloss → verify → 끝
1순위는 하위 문의 1개라 병렬 실행(T3)과 메일 구성(T5)은 없다. 고객에게 가는 글은 모두 DRAFT다.
노드는 RunLog.timed로 감싸 시간과 언어 모델 사용량을 모은다(FR-036, §6-5, 변경 add-run-log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from psycopg import Connection

from app.llm.client import RecordingTransport, Transport
from app.llm.drafts import Draft, Source, write_gloss, write_info_request, write_reply
from app.llm.embed import Embedder
from app.llm.verify import verify_draft
from app.pipeline.evidence import add_evidence
from app.pipeline.rules_step import apply_rules
from app.pipeline.runlog import RunLog
from app.pipeline.state import TicketState
from app.rules.required_info import RequiredInfoResult
from app.pipeline.understand import understand_ticket
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

    def info_request(gs: GraphState) -> GraphState:
        state, drafts = gs["state"], []
        for sub in state.sub_tickets:
            blocking = sub.missing_blocking_info
            optional = [f for f in sub.missing_info if f not in blocking]
            name = conn.execute("SELECT product_name FROM ref.product WHERE product_code = %s",
                                (sub.product_code,)).fetchone()
            draft = write_info_request(transport, sub.sub_ticket_id, state.language, sub.category_code,
                                       name[0] if name else None, blocking, optional,
                                       gs["labels"].get(sub.sub_ticket_id, {}))
            sub.flags += [f for f in draft.flags if f not in sub.flags]
            drafts.append(draft)
        return {"drafts": drafts}

    def evidence(gs: GraphState) -> GraphState:
        return {"state": add_evidence(conn, embedder, gs["state"])}

    def reply(gs: GraphState) -> GraphState:
        state, drafts, by_sub = gs["state"], [], {}
        for sub in state.sub_tickets:
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
                sources, [labels.get(f, f) for f in sub.missing_info],
            )
            sub.flags += [f for f in flags if f not in sub.flags]
            if draft is not None:
                sub.draft_check = draft.check
                drafts.append(draft)
        return {"drafts": drafts, "sources": by_sub}

    def gloss(gs: GraphState) -> GraphState:
        return {"drafts": [write_gloss(transport, d) for d in gs["drafts"]]}

    def verify(gs: GraphState) -> GraphState:  # Q14: 실패해도 실행은 SUCCESS(FR-049 예외 2행)
        subs = {s.sub_ticket_id: s for s in gs["state"].sub_tickets}
        for draft in gs["drafts"]:
            sub = subs[draft.sub_ticket_id]
            lookups = [(lv.item, lv.value, lv.unit, f"{lv.source_table}:{lv.source_key}") for lv in sub.lookups]
            draft.verify = verify_draft(transport, draft, sub.evidence_sentences,
                                        gs.get("sources", {}).get(sub.sub_ticket_id, []), lookups)
            sub.verify_findings = None if draft.verify.error else draft.verify.findings
        return {"drafts": gs["drafts"]}

    def after_understand(gs: GraphState) -> str:
        return "rules" if gs["run_status"] == "SUCCESS" else END

    def branch_info(gs: GraphState) -> str:  # 분기③
        if gs.get("run_status") != "SUCCESS":
            return END
        return "info_request" if any(s.missing_blocking_info for s in gs["state"].sub_tickets) else "evidence"

    graph = StateGraph(GraphState)
    for name, node in [("understand", understand), ("rules", rules), ("info_request", info_request),
                       ("evidence", evidence), ("reply", reply), ("gloss", gloss), ("verify", verify)]:
        graph.add_node(name, runlog.timed(name, node) if runlog is not None else node)
    graph.add_edge(START, "understand")
    graph.add_conditional_edges("understand", after_understand, ["rules", END])
    graph.add_conditional_edges("rules", branch_info, ["info_request", "evidence", END])
    graph.add_edge("info_request", "gloss")
    graph.add_edge("evidence", "reply")
    graph.add_edge("reply", "gloss")
    graph.add_edge("gloss", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


def run_ticket(conn: Connection, transport: Transport, embedder: Embedder, ticket_input: dict[str, Any],
               understand_fn=None, runlog: RunLog | None = None) -> RunOutcome:
    runlog = runlog if runlog is not None else RunLog.from_settings()
    final = build_graph(conn, transport, embedder, understand_fn, runlog).invoke({"ticket_input": ticket_input})
    return RunOutcome(final.get("state"), final["run_status"], final.get("drafts", []),
                      final.get("error_type"), final.get("message"), final.get("required", {}),
                      final.get("sources", {}), final.get("llm_field_names", {}), runlog)
