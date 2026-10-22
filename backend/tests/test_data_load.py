"""reference-data, gold-dataset 시나리오 시험 (openspec/changes/load-reference-and-gold).

시험이 적재 작업을 직접 실행하므로 시험 DB의 ref·gold 내용은 다시 채워진다.
"""

import csv

import psycopg
import pytest

from app.config import get_settings
from jobs import load_gold, load_reference

# 테이블 정의서 v1.3 §2 (doc_chunk 제외)
EXPECTED_REF_ROWS = {
    "department": 13, "product_family": 11, "inquiry_category": 10, "priority_level": 4,
    "customer_tier": 3, "urgency": 6, "info_field": 32, "customer": 600, "product": 23,
    "product_standard": 39, "product_certification": 61, "product_spec": 169,
    "firmware_release": 39, "fault": 97, "fault_product": 156, "priority_rule": 7,
    "priority_rule_urgency": 6, "priority_rule_category": 20, "routing_rule": 111,
    "required_info_rule": 110, "required_info_field": 437, "sla_policy": 120,
    "sla_setting": 3, "document": 107,
}

# 운영진 README.html "Category 계수"
EXPECTED_COEF = {
    "TECH_SPEC": 1.0, "INSTALL": 1.0, "WARRANTY": 1.5, "ORDER_LEAD": 0.5, "MANUAL": 0.5,
    "DEFECT": 1.0, "COMPLIANCE": 1.0, "QUOTE": 1.0, "FW_UPDATE": 1.0, "RETURN": 2.0,
}


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def loaded(settings):
    load_reference.load(settings.database_url, settings.data_path)
    load_gold.load(settings.database_url, settings.data_path)
    return settings


def ref_row_counts(database_url):
    with psycopg.connect(database_url) as conn:
        return {t: conn.execute(f"SELECT count(*) FROM ref.{t}").fetchone()[0] for t in EXPECTED_REF_ROWS}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_w1_1_ref_row_counts_match_table_spec(loaded):
    assert ref_row_counts(loaded.database_url) == EXPECTED_REF_ROWS


def test_w1_2_reload_gives_same_row_counts(loaded):
    load_reference.load(loaded.database_url, loaded.data_path)

    assert ref_row_counts(loaded.database_url) == EXPECTED_REF_ROWS


def test_w1_3_firmware_versions_keep_original_text(loaded):
    expected = {(r["product_code"], r["fw_version"]) for r in read_csv(loaded.data_path / "ref" / "firmware_history.csv")}
    with psycopg.connect(loaded.database_url) as conn:
        actual = set(conn.execute("SELECT product_code, fw_version FROM ref.firmware_release").fetchall())

    assert actual == expected
    assert len(actual) == 39


def test_w1_4_resolution_coef_matches_readme(loaded):
    with psycopg.connect(loaded.database_url) as conn:
        rows = conn.execute("SELECT category, sla_resolution_coef FROM ref.inquiry_category").fetchall()

    assert {c: float(v) for c, v in rows} == EXPECTED_COEF


def test_w3_1_gold_row_counts(loaded):
    with psycopg.connect(loaded.database_url) as conn:
        counts = [
            conn.execute(f"SELECT count(*) FROM gold.{name}").fetchone()[0]
            for name in ("ticket_gold", "resolution_case_gold", "v_inputs")
        ]

    assert counts == [4000, 800, 4000]


def test_w3_2_ticket_gold_matches_csv(loaded):
    expected = read_csv(loaded.data_path / "tickets.csv")
    columns = list(expected[0])
    with psycopg.connect(loaded.database_url) as conn:
        rows = conn.execute(f"SELECT {', '.join(columns)} FROM gold.ticket_gold").fetchall()

    actual = {r[0]: r for r in rows}
    assert len(actual) == 4000
    for row in expected:
        assert actual[row["ticket_id"]] == tuple(v if v != "" else None for v in row.values())
