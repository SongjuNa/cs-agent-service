"""W1 기준정보 적재: 운영진 ref/*.csv 12개 + docs/doc_index.csv → ref 스키마 표 24개.

원본에서 바꾸는 방법은 테이블 정의서 v1.3 §2-0을 따른다.
표를 비우고 처음부터 다시 넣으며, 전체가 트랜잭션 하나다(실패하면 아무것도 바뀌지 않는다).

실행: 저장소 루트에서 python -m jobs.load_reference
"""

import csv
from pathlib import Path

import psycopg

from app.config import get_settings

# 테이블 정의서 §2-0: priority_rules.csv condition 원문을 (긴급도, 유형) 조건 표로 옮긴 것.
# 빈 목록 = 조건 없음(모든 값). PR-06·PR-07의 생략된 유형은 정보성 4종.
INFO_CATEGORIES = ["TECH_SPEC", "MANUAL", "COMPLIANCE", "QUOTE"]
PRIORITY_CONDITIONS = {
    "PR-01": (["SAFETY"], []),
    "PR-02": (["SITE_DOWN"], ["DEFECT", "INSTALL", "FW_UPDATE"]),
    "PR-03": (["SITE_DOWN"], ["ORDER_LEAD", "RETURN", "WARRANTY"]),
    "PR-04": (["PROD_IMPACT", "COMMISSION"], []),
    "PR-05": ([], ["DEFECT", "INSTALL", "FW_UPDATE", "WARRANTY", "RETURN", "ORDER_LEAD"]),
    "PR-06": (["DEADLINE"], INFO_CATEGORIES),
    "PR-07": ([], INFO_CATEGORIES),
}

# 부모 표부터 넣는 순서. 비울 때는 이 목록 전체를 한 번에 비운다.
TABLES = [
    "department", "product_family", "inquiry_category", "priority_level", "customer_tier",
    "urgency", "info_field", "customer", "product", "document", "product_standard",
    "product_certification", "product_spec", "firmware_release", "fault", "fault_product",
    "priority_rule", "priority_rule_urgency", "priority_rule_category", "routing_rule",
    "required_info_rule", "required_info_field", "sla_policy", "sla_setting",
]


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:  # 모든 CSV가 BOM으로 시작한다
        return list(csv.DictReader(f))


def blank_to_none(value: str | None) -> str | None:
    return value if value not in ("", None) else None


def split_values(value: str) -> list[str]:
    return [v for v in (value or "").split(";") if v]


def yes(value: str) -> bool:
    return value == "Y"


def build_rows(data_dir: Path) -> dict[str, list[tuple]]:
    ref = data_dir / "ref"
    departments = read_csv(ref / "departments.csv")
    products = read_csv(ref / "product_master.csv")
    sla = read_csv(ref / "sla_policy.csv")
    priority_rules = read_csv(ref / "priority_rules.csv")
    customers = read_csv(ref / "customers.csv")
    firmware = read_csv(ref / "firmware_history.csv")
    faults = read_csv(ref / "fault_catalog.csv")
    routing = read_csv(ref / "routing_rules.csv")
    required = read_csv(ref / "required_info.csv")

    rows: dict[str, list[tuple]] = {t: [] for t in TABLES}

    rows["department"] = [
        (r["dept_code"], r["dept_name_ko"], r["dept_name_en"], r["level"], blank_to_none(r["scope"]))
        for r in departments
    ]

    families = {}
    for r in products:
        families.setdefault(r["family"], (r["family"], r["family_name"], r["tech_support_dept"]))
    rows["product_family"] = list(families.values())

    # 해결시간 계수 = 해결 목표 ÷ 같은 등급·우선순위의 TECH_SPEC 해결 목표 (README.html "Category 계수")
    base = {
        (r["customer_tier"], r["priority"]): int(r["resolution_hours"])
        for r in sla
        if r["category"] == "TECH_SPEC"
    }
    categories: dict[str, tuple] = {}
    for r in sla:
        coef = int(r["resolution_hours"]) / base[(r["customer_tier"], r["priority"])]
        known = categories.setdefault(r["category"], (r["category"], r["resolution_definition"], coef))
        if known[2] != coef:
            raise ValueError(f"{r['category']}: 해결시간 계수가 하나로 일정하지 않음 ({known[2]} / {coef})")
    rows["inquiry_category"] = list(categories.values())

    levels = {}
    for r in priority_rules:
        levels.setdefault(r["priority"], (r["priority"], r["priority_definition"]))
    rows["priority_level"] = list(levels.values())

    rows["customer_tier"] = [(t,) for t in dict.fromkeys(r["tier"] for r in customers)]
    rows["urgency"] = [(r["urgency"], r["description"]) for r in read_csv(ref / "urgency_codebook.csv")]
    rows["info_field"] = [(r["field"], r["label"]) for r in read_csv(ref / "info_field_codebook.csv")]

    rows["customer"] = [
        (r["customer_id"], r["company_masked"], r["country"], r["tier"], r["segment"],
         blank_to_none(r["account_since"]), blank_to_none(r["contact_count"]))
        for r in customers
    ]

    rows["product"] = [
        (r["product_code"], r["product_name"], r["family"], blank_to_none(r["description"]),
         yes(r["has_firmware"]), int(r["warranty_months"]), r["lifecycle_status"],
         int(r["std_lead_time_weeks"]), int(r["moq"]), int(r["list_price_usd"]),
         blank_to_none(r["weight_kg"]), blank_to_none(r["dimensions_mm"]),
         blank_to_none(r["ip_rating"]), blank_to_none(r["operating_temp"]))
        for r in products
    ]

    rows["document"] = [
        (r["doc_id"], r["title"], r["doc_type"], blank_to_none(r["product_code"]),
         blank_to_none(r["family"]), blank_to_none(r["revision"]), r["path"], int(r["chars"]))
        for r in read_csv(data_dir / "docs" / "doc_index.csv")
    ]

    for r in products:
        rows["product_standard"] += [(r["product_code"], s) for s in split_values(r["standards"])]
        rows["product_certification"] += [(r["product_code"], c) for c in split_values(r["certifications"])]

    rows["product_spec"] = [
        (r["product_code"], r["attribute"], r["value"], blank_to_none(r["doc_id"]), blank_to_none(r["section"]))
        for r in read_csv(ref / "product_spec_facts.csv")
    ]

    rows["firmware_release"] = [
        (r["product_code"], r["fw_version"], r["release_date"], yes(r["is_latest"]),
         blank_to_none(r["changes"]), blank_to_none(r["doc_id"]))
        for r in firmware
    ]

    released = {(r["product_code"], r["fw_version"]) for r in firmware}
    for r in faults:
        rows["fault"].append(
            (r["fault_id"], r["family"], blank_to_none(r["error_code"]), r["symptom"], r["root_cause"],
             r["diagnosis"], r["action"], r["severity_hint"], yes(r["needs_onsite"]), yes(r["needs_rma"]),
             blank_to_none(r["replacement_part"]), int(r["typical_resolution_hours"]))
        )
        # 수정 펌웨어 버전은 그 버전이 실제로 있는 제품 행에만 둔다 (정의서 §2-0, FLT-078)
        fix = blank_to_none(r["fw_fix_version"])
        applies_to = split_values(r["applies_to"])
        fixed = [p for p in applies_to if (p, fix) in released] if fix else []
        if fix and not fixed:
            raise ValueError(f"{r['fault_id']}: fw_fix_version {fix}을 가진 제품이 없음")
        rows["fault_product"] += [(r["fault_id"], p, fix if p in fixed else None) for p in applies_to]

    for r in priority_rules:
        rows["priority_rule"].append((r["rule_id"], int(r["order"]), r["condition"], r["priority"]))
        urgencies, cats = PRIORITY_CONDITIONS[r["rule_id"]]
        rows["priority_rule_urgency"] += [(r["rule_id"], u) for u in urgencies]
        rows["priority_rule_category"] += [(r["rule_id"], c) for c in cats]

    rows["routing_rule"] = [
        (r["rule_id"],
         None if r["family"] == "ALL" else r["family"],
         r["category"], r["rule_source"],
         None if r["primary_dept"] == "(제품군 기술지원)" else blank_to_none(r["primary_dept"]),
         blank_to_none(r["escalation_dept"]), blank_to_none(r["escalation_condition"]))
        for r in routing
    ]

    for r in required:
        rows["required_info_rule"].append((r["family"], r["category"]))
        blocking = set(split_values(r["blocking_fields"]))
        rows["required_info_field"] += [
            (r["family"], r["category"], f, order, f in blocking)
            for order, f in enumerate(split_values(r["required_fields"]), start=1)
        ]

    rows["sla_policy"] = [
        (r["sla_id"], r["category"], r["customer_tier"], r["priority"],
         int(r["first_response_hours"]), int(r["resolution_hours"]))
        for r in sla
    ]

    # 120행 모두 같은 값 3개 (정의서 §2-0)
    for key in ("clock", "at_risk_threshold", "pause_rule"):
        values = {r[key] for r in sla}
        if len(values) != 1:
            raise ValueError(f"sla_policy.csv {key}: 값이 하나가 아님 {values}")
        rows["sla_setting"].append((key, values.pop()))

    return rows


COLUMNS = {
    "department": "dept_code, dept_name_ko, dept_name_en, level, scope",
    "product_family": "family, family_name, tech_support_dept",
    "inquiry_category": "category, resolution_definition, sla_resolution_coef",
    "priority_level": "priority, definition",
    "customer_tier": "tier",
    "urgency": "urgency, description",
    "info_field": "field, label",
    "customer": "customer_id, company_masked, country, tier, segment, account_since, contact_count",
    "product": "product_code, product_name, family, description, has_firmware, warranty_months, "
               "lifecycle_status, std_lead_time_weeks, moq, list_price_usd, weight_kg, dimensions_mm, "
               "ip_rating, operating_temp",
    "document": "doc_id, title, doc_type, product_code, family, revision, path, chars",
    "product_standard": "product_code, standard",
    "product_certification": "product_code, certification",
    "product_spec": "product_code, attribute, value, doc_id, section",
    "firmware_release": "product_code, fw_version, release_date, is_latest, changes, doc_id",
    "fault": "fault_id, family, error_code, symptom, root_cause, diagnosis, action, severity_hint, "
             "needs_onsite, needs_rma, replacement_part, typical_resolution_hours",
    "fault_product": "fault_id, product_code, fw_fix_version",
    "priority_rule": "rule_id, rule_order, condition, priority",
    "priority_rule_urgency": "rule_id, urgency",
    "priority_rule_category": "rule_id, category",
    "routing_rule": "rule_id, family, category, rule_source, primary_dept, escalation_dept, escalation_condition",
    "required_info_rule": "family, category",
    "required_info_field": "family, category, field, field_order, is_blocking",
    "sla_policy": "sla_id, category, customer_tier, priority, first_response_hours, resolution_hours",
    "sla_setting": "key, value",
}


def load(database_url: str, data_dir: Path) -> dict[str, int]:
    rows = build_rows(data_dir)
    with psycopg.connect(database_url) as conn:  # with 블록이 끝날 때 커밋, 오류면 되돌림
        try:
            # 자식 표부터 DELETE로 비운다. TRUNCATE는 비어 있는 svc 표가 가리키기만 해도 거부되고,
            # CASCADE는 svc 데이터까지 지우므로 쓰지 않는다. 실제로 가리키는 행이 있으면 여기서 멈춘다.
            for table in reversed(TABLES):
                conn.execute(f"DELETE FROM ref.{table}")
        except psycopg.errors.ForeignKeyViolation as e:
            raise SystemExit(
                "기준정보를 다른 표(svc 또는 ref.doc_chunk)가 가리키고 있어 비울 수 없습니다. "
                "아무것도 바꾸지 않았습니다. 그 데이터를 먼저 비우거나 'docker compose down -v' 뒤 다시 실행하세요.\n"
                f"{e}"
            ) from e
        with conn.cursor() as cur:
            for table in TABLES:
                columns = COLUMNS[table]
                marks = ", ".join(["%s"] * len(columns.split(",")))
                cur.executemany(f"INSERT INTO ref.{table} ({columns}) VALUES ({marks})", rows[table])
    return {t: len(rows[t]) for t in TABLES}


def main() -> None:
    settings = get_settings()
    counts = load(settings.database_url, settings.data_path)
    for table, n in counts.items():
        print(f"ref.{table}: {n}")


if __name__ == "__main__":
    main()
