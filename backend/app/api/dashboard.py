"""운영 대시보드 (변경 add-ops-overview). 읽기만 한다. 집계는 app/db/dashboard.py."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn
from app.db.dashboard import DEFAULT_DAYS, MAX_DAYS, dashboard

router = APIRouter()


@router.get("/dashboard/summary", response_model=schemas.DashboardSummary, response_model_exclude_unset=True)
def get_summary(as_of: datetime | None = None, days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS),
                conn: Connection = Depends(get_conn)) -> dict:
    """미해결 현황, 기한 충족, 일별 접수, 부서·상담원·나라별 쌓임, 처리 단계별 현황(기간은 as_of 이전 days일)."""
    return dashboard(conn, as_of, days)
