"""고객 관리 (변경 add-customer-views, FR 초안 01). 읽기 전용 주소 3개, 고치는 주소는 없다."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn
from app.db.customers import MSG_NOT_FOUND, PAGE_SIZE, countries, customer_detail, customer_list

router = APIRouter()


@router.get("/customers", response_model=schemas.CustomerRows, response_model_exclude_unset=True)
def get_customers(q: str | None = None, tier: str | None = None, country: str | None = None, page: int = 1,
                  size: int = PAGE_SIZE, conn: Connection = Depends(get_conn)) -> dict:
    """목록(design 결정 1). q는 고객 ID·고객사 부분 일치."""
    return customer_list(conn, q, (tier or "").strip() or None, (country or "").strip() or None, page, size)


@router.get("/customers/countries", response_model=list[schemas.CountryRow], response_model_exclude_unset=True)
def get_countries(conn: Connection = Depends(get_conn)) -> list[dict]:
    """나라별 집계(design 결정 3). /customers/{id}보다 먼저 둔다."""
    return countries(conn)


@router.get("/customers/{customer_id}", response_model=schemas.CustomerDetail, response_model_exclude_unset=True)
def get_customer(customer_id: str, as_of: datetime | None = None, conn: Connection = Depends(get_conn)) -> dict:
    """상세와 문의 이력(design 결정 2). as_of는 경고를 보는 기준 시각(나의 업무 현황과 같음)."""
    found = customer_detail(conn, customer_id, as_of)
    if found is None:
        raise HTTPException(404, MSG_NOT_FOUND)
    return found
