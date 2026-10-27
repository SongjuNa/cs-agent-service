"""API 의존성: DB 연결과 언어 모델 연결 (design 결정 6). 시험은 이것을 바꿔 끼운다.

서비스 연결은 autocommit으로 열고, 쓰기는 모두 `with conn.transaction():` 안에서 한다.
그래서 시험이 바깥 트랜잭션을 롤백하면 쓴 것이 남지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import psycopg
from psycopg import Connection

from app.config import get_settings
from app.llm.client import AudioTransport, Transport, default_transport, transcribe_transport
from app.llm.embed import Embedder, default_embedder


@contextmanager
def open_connection() -> Iterator[Connection]:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        yield conn


def get_connect() -> Callable[[], AbstractContextManager[Connection]]:
    """백그라운드 작업이 새 연결을 여는 함수."""
    return open_connection


def get_conn() -> Iterator[Connection]:
    with open_connection() as conn:
        yield conn


class Clients:
    """언어 모델 연결. 키가 없으면 부를 때 LlmError가 난다(처리 실패로 기록된다)."""

    def transport(self) -> Transport:
        return default_transport()

    def embedder(self) -> Embedder:
        return default_embedder()

    def transcriber(self) -> AudioTransport:
        """통화 받아쓰기 L9용(시간 상한 120초, 모델 LLM_MODEL_TRANSCRIBE, FR-050)."""
        return transcribe_transport()


def get_clients() -> Clients:
    return Clients()
