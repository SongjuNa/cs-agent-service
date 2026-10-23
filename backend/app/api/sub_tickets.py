"""하위 문의 동작: 우선순위 조정과 미리 보기 (FR-028, 기술 명세서 v1.4 §8-1, 화면 정의서 v1 SCR-03-P3)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg import Connection
from pydantic import BaseModel

from app.api.deps import get_conn
from app.sla.adjust import AdjustError, adjust, preview
from app.status.transitions import ConcurrentChange

router = APIRouter()

MSG_NOT_FOUND = "문의를 찾을 수 없음"


class PriorityIn(BaseModel):
    new_priority: str
    reason_kind: str | None = None
    reason_text: str | None = None
    confirm_breach: bool = False          # 즉시 위반 확인(FR-028 예외 3행)
    expected_version: int | None = None   # FR-025 예외 2행


def _error(exc: AdjustError) -> JSONResponse:
    content = {"detail": str(exc)}
    if exc.preview is not None:
        content["preview"] = exc.preview
    return JSONResponse(status_code=exc.status, content=jsonable_encoder(content))


@router.get("/sub-tickets/{sub_ticket_id}/priority")
def get_preview(sub_ticket_id: str, new_priority: str, conn: Connection = Depends(get_conn)):
    """저장 없이 이전·새 목표와 즉시 위반 여부(구현 선택, P3 미리 보기)."""
    try:
        return preview(conn, sub_ticket_id, new_priority, datetime.now(timezone.utc))
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except AdjustError as exc:
        return _error(exc)


@router.post("/sub-tickets/{sub_ticket_id}/priority")
def post_priority(sub_ticket_id: str, data: PriorityIn, conn: Connection = Depends(get_conn),
                  x_agent_id: str | None = Header(default=None)):
    if not x_agent_id or not x_agent_id.strip():
        raise HTTPException(400, "상담원 ID를 입력하세요")
    try:
        return adjust(conn, sub_ticket_id, data.new_priority, data.reason_kind, data.reason_text, x_agent_id.strip(),
                      datetime.now(timezone.utc), confirm_breach=data.confirm_breach,
                      expected_version=data.expected_version)
    except LookupError as exc:
        raise HTTPException(404, MSG_NOT_FOUND) from exc
    except ConcurrentChange as exc:
        raise HTTPException(409, str(exc)) from exc
    except AdjustError as exc:
        return _error(exc)
