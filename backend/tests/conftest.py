"""시험 공통 준비: ref·gold를 한 번 적재하고 DB 연결을 나눠 쓴다."""

import psycopg
import pytest

from app.config import get_settings
from jobs import load_gold, load_reference


@pytest.fixture(scope="session")
def conn():
    settings = get_settings()
    load_reference.load(settings.database_url, settings.data_path)
    load_gold.load(settings.database_url, settings.data_path)
    with psycopg.connect(settings.database_url) as connection:
        yield connection


@pytest.fixture(autouse=True, scope="session")
def _fault_vector_cache(tmp_path_factory):
    """시험은 개발자의 고장 사전 벡터 캐시(backend/.cache)를 건드리지 않는다(add-fault-diagnosis)."""
    from app.retrieval import fault

    saved = fault._default_vectors
    fault._default_vectors = fault.SymptomVectors(tmp_path_factory.mktemp("fault-cache") / "fault_symptoms.json")
    yield
    fault._default_vectors = saved
