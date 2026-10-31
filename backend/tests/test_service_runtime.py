"""service-runtime 시나리오 시험 (openspec/changes/setup-project-structure)."""

import psycopg
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

# 테이블 정의서 §1 (뷰 제외). svc는 처음 11개에 최신 목업 반영으로 더한 4개: internal_note(add-internal-notes),
# assignment_history(add-reassign), auto_setting·auto_review(add-auto-send). scoring은 svc의 추가 표를 따라 만들지 않는다.
EXPECTED_TABLES = {"ref": 25, "gold": 2, "svc": 15, "scoring": 11, "eval": 8}


def test_w7_1_db_table_counts_match_table_spec():
    with psycopg.connect(get_settings().database_url) as conn:
        rows = conn.execute(
            "SELECT schemaname, count(*) FROM pg_tables"
            " WHERE schemaname = ANY(%s) GROUP BY schemaname",
            (list(EXPECTED_TABLES),),
        ).fetchall()
        has_v_inputs = conn.execute(
            "SELECT 1 FROM pg_views WHERE schemaname = 'gold' AND viewname = 'v_inputs'"
        ).fetchone()

    assert dict(rows) == EXPECTED_TABLES
    assert has_v_inputs is not None


def test_w7_2_docs_page_opens():
    response = TestClient(app).get("/docs")

    assert response.status_code == 200
