"""나의 업무 현황 (기술 명세서 v1.4 §8-1 `GET /me/workload?as_of=`, 명세서 v1.5 FR-047)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn
from app.db.workload import workload

router = APIRouter()


@router.get("/me/workload", response_model=schemas.Workload, response_model_exclude_unset=True)
def get_workload(dept: str | None = None, scope: str | None = None, as_of: datetime | None = None,
                 x_agent_id: str | None = Header(default=None), conn: Connection = Depends(get_conn)) -> dict:
    """상담원은 X-Agent-Id, 부서는 접수함과 같이 dept 쿼리(§8-1). scope=mine|dept(C-118)."""
    return workload(conn, (dept or "").strip() or None, x_agent_id, scope, as_of)
