"""나의 업무 현황 (기술 명세서 v1.4 §8-1 `GET /me/workload?as_of=`, 명세서 v1.5 FR-047)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_conn
from app.db.performance import DEFAULT_DAYS, MAX_DAYS, performance
from app.db.workload import workload

router = APIRouter()


@router.get("/me/workload", response_model=schemas.Workload, response_model_exclude_unset=True)
def get_workload(dept: str | None = None, scope: str | None = None, as_of: datetime | None = None,
                 x_agent_id: str | None = Header(default=None), conn: Connection = Depends(get_conn)) -> dict:
    """상담원은 X-Agent-Id, 부서는 접수함과 같이 dept 쿼리(§8-1). scope=mine|dept(C-118)."""
    return workload(conn, (dept or "").strip() or None, x_agent_id, scope, as_of)


MSG_NO_AGENT = "상단에서 상담원을 먼저 고르세요"


@router.get("/me/performance", response_model=schemas.Performance, response_model_exclude_unset=True)
def get_performance(as_of: datetime | None = None, days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS),
                    x_agent_id: str | None = Header(default=None), conn: Connection = Depends(get_conn)) -> dict:
    """내 실적(변경 add-my-performance): 최근 days일 동안 내가 한 발송·이관·조정을 날짜별로, 내 담당 문의의 기한 충족을."""
    agent = (x_agent_id or "").strip()
    if not agent:
        raise HTTPException(400, MSG_NO_AGENT)
    return performance(conn, agent, as_of, days)
