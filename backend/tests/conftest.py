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
