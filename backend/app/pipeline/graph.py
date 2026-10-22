"""처리 흐름 그래프 (기술 명세서 v1.4 §1-2 LangGraph, §2-1 하위 문의 그래프, §2-5 분기③④).

understand(T1·T2·Q1) → rules(Q2~Q6) → 분기③ 막는 정보?
  예     → info_request(Q7, L3) → gloss(Q13, L7) → 끝
  아니오 → evidence(Q8·Q9) → reply(분기④ 근거 있음? → Q10 L4 + Q11 대조) → gloss → 끝
1순위는 하위 문의 1개라 병렬 실행(T3)과 메일 구성(T5)은 없다. 고객에게 가는 글은 모두 DRAFT다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from psycopg import Connection

from app.llm.client import Transport
from app.llm.drafts import Draft, Source, write_gloss, write_info_request, write_reply
from app.llm.embed import Embedder
from app.pipeline.evidence import add_evidence
from app.pipeline.rules_step import apply_rules
from app.pipeline.state import TicketState
from app.pipeline.understand import understand_ticket
from app.rules.lookup import CustomerNotFound


class GraphState(TypedDict, total=False):
    ticket_input: dict[str, Any]
    state: TicketState
    labels: dict[str, dict[str, str]]  # 하위 문의별 항목 라벨(Q5 결과)
    drafts: list[Draft]
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


def build_graph(conn: Connection, transport: Transport, embedder: Embedder):
    def understand(gs: GraphState) -> GraphState:
        out = understand_ticket(conn, transport, gs["ticket_input"])
        return {"state": out.state, "run_status": out.run_status, "error_type": out.error_type,
                "message": out.message, "drafts": []}

    def rules(gs: GraphState) -> GraphState:
        try:
            required = apply_rules(conn, gs["state"])
        except CustomerNotFound as exc:  # §2-2 Q2 "고객 없음 → 접수 거부(D25)"
            return {"run_status": "FAILED", "error_type": "VALIDATION", "message": str(exc)}
        return {"labels": {k: v.labels for k, v in required.items()}}

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
        state, drafts = gs["state"], []
        for sub in state.sub_tickets:
            sources = []
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
        return {"drafts": drafts}

    def gloss(gs: GraphState) -> GraphState:
        return {"drafts": [write_gloss(transport, d) for d in gs["drafts"]]}

    def after_understand(gs: GraphState) -> str:
        return "rules" if gs["run_status"] == "SUCCESS" else END

    def branch_info(gs: GraphState) -> str:  # 분기③
        if gs.get("run_status") != "SUCCESS":
            return END
        return "info_request" if any(s.missing_blocking_info for s in gs["state"].sub_tickets) else "evidence"

    graph = StateGraph(GraphState)
    for name, node in [("understand", understand), ("rules", rules), ("info_request", info_request),
                       ("evidence", evidence), ("reply", reply), ("gloss", gloss)]:
        graph.add_node(name, node)
    graph.add_edge(START, "understand")
    graph.add_conditional_edges("understand", after_understand, ["rules", END])
    graph.add_conditional_edges("rules", branch_info, ["info_request", "evidence", END])
    graph.add_edge("info_request", "gloss")
    graph.add_edge("evidence", "reply")
    graph.add_edge("reply", "gloss")
    graph.add_edge("gloss", END)
    return graph.compile()


def run_ticket(conn: Connection, transport: Transport, embedder: Embedder, ticket_input: dict[str, Any]) -> RunOutcome:
    final = build_graph(conn, transport, embedder).invoke({"ticket_input": ticket_input})
    return RunOutcome(final.get("state"), final["run_status"], final.get("drafts", []),
                      final.get("error_type"), final.get("message"))
