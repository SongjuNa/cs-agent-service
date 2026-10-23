"""시뮬레이터·상담원 선택 목록 (기술 명세서 v1.4 §8-1 `GET /ref/*`, 화면 정의서 v1 SCR-01-04·05, SCR-00-03)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.api.deps import get_conn
from app.db.assignees import agents

router = APIRouter()
CUSTOMER_LIMIT = 20  # 검색 선택 목록 한 번에 보일 수(구현 선택)


def _rows(conn: Connection, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


@router.get("/ref/customers")
def customers(q: str = "", conn: Connection = Depends(get_conn)) -> list[dict]:
    """ID·회사명·국가·등급. q는 ID·회사명 부분 일치(대소문자 무시)."""
    like = f"%{q.strip()}%"
    return _rows(conn, """SELECT customer_id, company_masked, country, tier FROM ref.customer
                           WHERE customer_id ILIKE %s OR company_masked ILIKE %s
                           ORDER BY customer_id LIMIT %s""", (like, like, CUSTOMER_LIMIT))


@router.get("/ref/products")
def products(conn: Connection = Depends(get_conn)) -> list[dict]:
    return _rows(conn, "SELECT product_code, product_name FROM ref.product ORDER BY product_code")


@router.get("/ref/departments")
def departments(conn: Connection = Depends(get_conn)) -> list[dict]:
    return _rows(conn, "SELECT dept_code, dept_name_ko, dept_name_en FROM ref.department ORDER BY dept_code")


@router.get("/ref/agents")
def agent_list(dept: str | None = None) -> list[dict]:
    """가상 상담원 명단(조장 결정 2026-10-23). 상단 막대 상담원 선택이 쓴다."""
    return agents((dept or "").strip() or None)
