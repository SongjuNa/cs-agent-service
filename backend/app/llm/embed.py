"""임베딩 호출 (기술 명세서 v1.4 §1-2, §4-2, §4-3). 언어 모델 호출 계층의 일부다(CLAUDE.md 규칙 2).

- 보내기 전에 모든 글을 prepare_llm_input으로 가린다.
- 1회 30초, 실패하면 1회 다시(§2-4, FR-016 예외 2행). 두 번 실패하면 LlmError.
- 실제 전송은 Embedder가 한다. 시험은 정해진 벡터를 내는 대역 Embedder를 넣는다.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.llm.client import MAX_ATTEMPTS, TIMEOUT_SEC, LlmError, LlmTimeout
from app.llm.inputs import prepare_llm_input

log = logging.getLogger(__name__)

BATCH_SIZE = 100  # 색인할 때 한 번에 보내는 글 수 (구현 선택)


class Embedder(Protocol):
    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        """글마다 벡터 하나. task는 "document"(색인) 또는 "query"(검색문). 시간 초과면 LlmTimeout."""


class GeminiEmbedder:
    """Gemini 임베딩. 모델 이름은 EMBEDDING_MODEL(기본 gemini-embedding-2), 차원은 모델 기본값(§1-2)."""

    _TASKS = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}

    def __init__(self, api_key: str, model: str, timeout_sec: int = TIMEOUT_SEC):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_sec * 1000))
        self.model = model

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        import httpx

        config = self._types.EmbedContentConfig(task_type=self._TASKS[task])
        try:
            result = self._client.models.embed_content(model=self.model, contents=texts, config=config)
        except httpx.TimeoutException as exc:
            raise LlmTimeout(str(exc)) from exc
        return [list(e.values) for e in result.embeddings]


def embed_texts(embedder: Embedder, call_name: str, texts: list[str], task: str) -> list[list[float]]:
    """글을 가린 뒤 벡터로 바꾼다. 묶음마다 두 번 실패하면 LlmError."""
    masked = list(prepare_llm_input({str(i): t for i, t in enumerate(texts)}).fields.values())
    vectors: list[list[float]] = []
    for start in range(0, len(masked), BATCH_SIZE):
        batch = masked[start:start + BATCH_SIZE]
        last_type = "UNKNOWN"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                out = embedder.embed(batch, task)
                if len(out) != len(batch) or not all(out):
                    raise ValueError("벡터 수가 글 수와 다르다")
            except LlmTimeout:
                last_type = "LLM_TIMEOUT"
            except Exception:
                log.exception("embed call=%s attempt=%d error", call_name, attempt)
                last_type = "UNKNOWN"
            else:
                vectors += out
                break
            log.warning("embed call=%s attempt=%d result=%s", call_name, attempt, last_type)
        else:
            raise LlmError(last_type, f"{call_name}: {MAX_ATTEMPTS}회 실패({last_type})")
    log.info("embed call=%s texts=%d result=OK", call_name, len(texts))
    return vectors


def default_embedder() -> GeminiEmbedder:
    from app.config import get_settings

    settings = get_settings()
    if not settings.gemini_api_key:
        raise LlmError("UNKNOWN", "GEMINI_API_KEY가 없다")
    return GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
