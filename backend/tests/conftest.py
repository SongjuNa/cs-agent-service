"""시험 공통 준비: ref·gold를 한 번 적재하고 DB 연결을 나눠 쓴다."""

import os

import psycopg
import pytest

from app.config import get_settings
from jobs import load_gold, load_reference

# 자동 발송(변경 add-auto-send)은 설정을 저장하지 않은 시험에서는 꺼 둔다. 기존 시험은 초안이 DRAFT로 남는다고 가정한다.
# 자동 발송 시험은 설정을 직접 켠다(save_rules).
os.environ.setdefault("AUTO_SEND_DEFAULT", "false")


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


@pytest.fixture(autouse=True, scope="session")
def _case_index_cache(tmp_path_factory):
    """시험은 개발자의 해결사례 색인·벡터 캐시(backend/.cache)를 건드리지 않는다(add-similar-cases)."""
    from app.retrieval import cases, fault

    saved = cases._default_index
    tmp = tmp_path_factory.mktemp("case-cache")
    cases._default_index = cases.CaseIndex(tmp / "resolution_cases.json", fault.SymptomVectors(tmp / "vectors.json", step="Q8b"))
    yield
    cases._default_index = saved
