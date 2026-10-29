"""기준정보 보기 (변경 add-reference-views, FR 초안 02·03·04). 문서·제품·규칙표를 읽기만 한다. 고치는 주소는 없다.

규칙은 규칙 코드를 부르지 않고 ref 테이블만 읽는다. 언어 모델 호출 계층도 import하지 않는다(design 결정 3, CLAUDE.md 규칙 1·2).
제품 목록 `GET /ref/products`와 부서 목록 `GET /ref/departments`는 선택 목록과 같은 주소라 ref_lists.py에 있다.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn

router = APIRouter()
MSG_NO_DOC = "문서를 찾을 수 없음"  # design 결정 1
MSG_NO_PRODUCT = "제품을 찾을 수 없음"  # 구현 선택(문서와 같은 말투)
MSG_NO_KIND = "규칙 종류를 찾을 수 없음"  # design 결정 3 "그 밖 404"


def _rows(conn: Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


# ---- 문서 (design 결정 1) ----

@router.get("/ref/documents", response_model=list[schemas.DocumentRow], response_model_exclude_unset=True)
def documents(q: str = "", doc_type: str | None = None, conn: Connection = Depends(get_conn)) -> list[dict]:
    """q는 문서 ID·제목 부분 일치. chunk_count = 0이면 화면이 "색인 없음"을 보인다."""
    like = f"%{q.strip()}%"
    return _rows(conn, """
        SELECT d.doc_id, d.title, d.doc_type, d.product_code, d.family, d.revision, d.chars,
               (SELECT count(*) FROM ref.doc_chunk c WHERE c.doc_id = d.doc_id)::int AS chunk_count
          FROM ref.document d
         WHERE (d.doc_id ILIKE %s OR d.title ILIKE %s) AND (%s::text IS NULL OR d.doc_type = %s)
         ORDER BY d.doc_id""", (like, like, doc_type or None, doc_type or None))


@router.get("/ref/documents/{doc_id}", response_model=schemas.DocumentDetail, response_model_exclude_unset=True)
def document(doc_id: str, conn: Connection = Depends(get_conn)) -> dict:
    """문서 정보와 절 목록(절 번호 순). 절 본문은 GET /chunks/{chunk_id}."""
    found = _rows(conn, "SELECT doc_id, title, doc_type, product_code, family, revision, chars FROM ref.document WHERE doc_id = %s",
                  (doc_id,))
    if not found:
        raise HTTPException(404, MSG_NO_DOC)
    out = found[0]
    sections = _rows(conn, "SELECT chunk_id, section_no, section_title FROM ref.doc_chunk WHERE doc_id = %s", (doc_id,))
    out["sections"] = sorted(sections, key=lambda r: (_section_key(r["section_no"]), r["chunk_id"]))
    return out


def _section_key(no: str | None) -> list[tuple[int, int | str]]:
    """절 번호는 글자("3.10", "Q2")라 마디마다 숫자는 숫자로 비교한다(3.2 < 3.10)."""
    parts = re.findall(r"\d+|[^\d.]+", no or "")
    return [(0, int(p)) if p.isdigit() else (1, p) for p in parts]


# ---- 제품 (design 결정 2) ----

@router.get("/ref/products/{product_code}", response_model=schemas.ProductDetail, response_model_exclude_unset=True)
def product(product_code: str, conn: Connection = Depends(get_conn)) -> dict:
    found = _rows(conn, """SELECT product_code, product_name, family, list_price_usd, std_lead_time_weeks, lifecycle_status,
                                  warranty_months FROM ref.product WHERE product_code = %s""", (product_code,))
    if not found:
        raise HTTPException(404, MSG_NO_PRODUCT)
    out = found[0]
    out["specs"] = _rows(conn, "SELECT attribute, value, doc_id, section FROM ref.product_spec WHERE product_code = %s ORDER BY attribute",
                         (product_code,))
    out["standards"] = [r["standard"] for r in _rows(
        conn, "SELECT standard FROM ref.product_standard WHERE product_code = %s ORDER BY standard", (product_code,))]
    out["certifications"] = [r["certification"] for r in _rows(
        conn, "SELECT certification FROM ref.product_certification WHERE product_code = %s ORDER BY certification", (product_code,))]
    out["firmware"] = _rows(conn, """SELECT fw_version, release_date, is_latest, changes, doc_id FROM ref.firmware_release
                                      WHERE product_code = %s ORDER BY release_date DESC, fw_version DESC""", (product_code,))
    return out


# ---- 규칙 (design 결정 3). 원본 순서대로 ----

_RULES: dict[str, str] = {
    "priority": """
        SELECT r.rule_id, r.rule_order, r.condition, r.priority,
               coalesce((SELECT array_agg(u.urgency ORDER BY u.urgency) FROM ref.priority_rule_urgency u WHERE u.rule_id = r.rule_id), '{}') AS urgencies,
               coalesce((SELECT array_agg(c.category ORDER BY c.category) FROM ref.priority_rule_category c WHERE c.rule_id = r.rule_id), '{}') AS categories
          FROM ref.priority_rule r ORDER BY r.rule_order""",
    "routing": """
        SELECT rule_id, family, category, rule_source, primary_dept, escalation_dept, escalation_condition
          FROM ref.routing_rule ORDER BY rule_id""",
    "required-info": """
        SELECT r.family, r.category,
               coalesce((SELECT json_agg(json_build_object('field', f.field, 'field_order', f.field_order, 'is_blocking', f.is_blocking)
                                         ORDER BY f.field_order)
                           FROM ref.required_info_field f WHERE f.family = r.family AND f.category = r.category), '[]') AS fields
          FROM ref.required_info_rule r ORDER BY r.family, r.category""",
    "sla": """
        SELECT sla_id, category, customer_tier, priority, first_response_hours, resolution_hours
          FROM ref.sla_policy ORDER BY sla_id""",
}


@router.get("/ref/rules/{kind}", response_model=schemas.RuleRows, response_model_exclude_unset=True)
def rules(kind: str, conn: Connection = Depends(get_conn)) -> dict:
    """kind = priority, routing, required-info, sla. 그 밖은 404."""
    sql = _RULES.get(kind)
    if sql is None:
        raise HTTPException(404, MSG_NO_KIND)
    rows = _rows(conn, sql)
    for r in rows:
        for k in ("urgencies", "categories"):
            if k in r:
                r[k] = list(r[k])
    return {"kind": kind, "rows": rows}
