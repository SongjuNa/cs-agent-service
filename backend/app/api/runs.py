"""처리 기록 조회 (명세서 v1.5 FR-036 처리 7, 기술 명세서 v1.4 §8-1 `GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api.deps import get_conn
from app.db.runs import run_steps, ticket_runs

router = APIRouter()


@router.get("/tickets/{ticket_id}/runs")
def get_runs(ticket_id: str, conn: Connection = Depends(get_conn)) -> dict:
    runs = ticket_runs(conn, ticket_id)
    if runs is None:
        raise HTTPException(404, "문의를 찾을 수 없음")
    return {"ticket_id": ticket_id, "runs": runs}


@router.get("/runs/{run_id}/steps")
def get_steps(run_id: int, conn: Connection = Depends(get_conn)) -> dict:
    out = run_steps(conn, run_id)
    if out is None:
        raise HTTPException(404, "실행 기록을 찾을 수 없음")
    return out
