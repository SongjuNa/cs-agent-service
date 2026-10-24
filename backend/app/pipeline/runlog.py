"""실행 로그의 노드 감싸기 (명세서 v1.5 FR-036 처리 2·4, 기술 명세서 v1.4 §6-5, §3-5).

노드마다 감싸는 함수 하나가 시작·끝 시각과 그 사이의 언어 모델 호출(호출 이름, 지시문 버전, 토큰, 시도 수)을 모은다.
노드 코드에는 로그 코드를 넣지 않는다. 모은 값은 결과를 저장할 때 단계 행(agent_step)에 들어간다(design 결정 1·2).
이 모듈은 언어 모델 호출 계층을 import하지 않는다. 호출을 남기는 Transport 감싸개는 호출 계층(app/llm/client.py)에 있다.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

# 호출 → 그 호출을 쓰는 단계 (기술 명세서 §2-2 단계 표)
STEP_OF_CALL = {"L1": "T2", "L2": "Q1", "L3": "Q7", "L4": "Q10", "L5": "T5", "L7": "Q13", "L8": "Q14"}
# 처리 흐름 노드 → 그 노드가 내는 단계 (graph.py, C-81: 한 노드의 단계들은 같은 시간을 쓴다)
NODE_STEPS = {"understand": ("T2", "Q1"), "rules": ("Q2", "Q3", "Q4", "Q5", "Q6"), "diagnose": ("Q8a",),
              "escalate": ("Q9a",),
              "info_request": ("Q7",),
              "evidence": ("Q8", "Q9"), "reply": ("Q10", "Q11"), "compose": ("T5",), "gloss": ("Q13",),
              "verify": ("Q14",)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LlmCall:
    call: str
    prompt_version: str
    prompt: str  # 가린 지시문(generate_json이 가린 뒤 채운 것)
    response: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    sub_ticket_id: str | None = None  # 그 호출을 한 하위 문의(티켓 단계면 None)


@dataclass
class NodeTime:
    started: datetime
    finished: datetime | None = None


@dataclass
class RunLog:
    full_io: bool = False  # LOG_FULL_LLM_IO (FR-036 처리 4)
    nodes: dict[str, NodeTime] = field(default_factory=dict)
    calls: list[LlmCall] = field(default_factory=list)
    current_sub: str | None = None  # 노드가 지금 처리하는 하위 문의(사용량 나누기, C-89)

    @contextmanager
    def sub(self, sub_ticket_id: str) -> Iterator[None]:
        """이 안에서 한 호출은 그 하위 문의 몫으로 센다."""
        before, self.current_sub = self.current_sub, sub_ticket_id
        try:
            yield
        finally:
            self.current_sub = before

    @classmethod
    def from_settings(cls) -> "RunLog":
        from app.config import get_settings

        return cls(full_io=get_settings().log_full_llm_io)

    def timed(self, node: str, fn: Callable) -> Callable:
        """노드 감싸기. 오류가 나도 끝 시각을 남기고 오류는 그대로 올린다."""

        def wrapper(state: Any) -> Any:  # 처리 흐름 노드는 상태 하나를 받는다
            self.nodes[node] = NodeTime(_now())
            try:
                return fn(state)
            finally:
                self.nodes[node].finished = _now()

        return wrapper

    def step_fields(self, step_name: str, sub_ticket_id: str | None = None) -> dict[str, Any]:
        """단계 행에 넣을 시간·사용량 열. 이 실행에서 그 단계를 낸 노드가 없으면 빈 dict.

        sub_ticket_id를 주면 그 하위 문의가 한 호출만 센다(복합 문의, C-89).
        """
        out: dict[str, Any] = {}
        node = next((n for n, steps in NODE_STEPS.items() if step_name in steps and n in self.nodes), None)
        if node:
            t = self.nodes[node]
            finished = t.finished or _now()
            out.update(started_at=t.started, finished_at=finished,
                       latency_ms=int((finished - t.started).total_seconds() * 1000))
        calls = [c for c in self.calls if STEP_OF_CALL.get(c.call) == step_name
                 and (sub_ticket_id is None or c.sub_ticket_id == sub_ticket_id)]
        if calls:
            ins = [c.input_tokens for c in calls if c.input_tokens is not None]
            outs = [c.output_tokens for c in calls if c.output_tokens is not None]
            out.update(prompt_version=calls[-1].prompt_version, llm_calls=len(calls),
                       input_tokens=sum(ins) if ins else None, output_tokens=sum(outs) if outs else None)
            if self.full_io:
                out["full_io"] = [{"call": c.call, "attempt": i, "prompt": c.prompt, "response": c.response}
                                  for i, c in enumerate(calls, 1)]
        return out


def track(transport: Any, sub_ticket_id: str) -> AbstractContextManager:
    """하위 문의 몫 표시. 기록하는 Transport(RecordingTransport)가 아니면 아무것도 하지 않는다."""
    log = getattr(transport, "log", None)
    return log.sub(sub_ticket_id) if isinstance(log, RunLog) else nullcontext()

