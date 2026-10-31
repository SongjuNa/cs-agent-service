"""담당 변경 (변경 add-reassign, 최신 목업 접수함의 "담당자 변경 / 내가 맡기"와 문의 배정 관리).

한 번에 여러 문의의 담당을 바꾼다(문의 하나여도 같은 주소). 바꾼 사람·시각은 svc.assignment_history에 남고 이력 목록에 나온다.
담당은 그 문의를 맡은 부서(담당 부서 또는 이관받은 부서) 명단의 사람만 될 수 있다. 종료된 문의, 이미 그 사람 담당인 문의,
다른 부서 사람은 건너뛰고 사유를 돌려준다. 이 모듈은 언어 모델 호출 계층을 import하지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import get_conn
from app.db.assignees import agents

router = APIRouter()
MAX_IDS = 200
CLOSED = ("RESOLVED", "CLOSED")
MSG_NO_IDS = "담당을 바꿀 문의를 고르세요"
MSG_TOO_MANY = f"한 번에 {MAX_IDS}건까지 바꿀 수 있습니다"
MSG_NO_AGENT = "상단에서 상담원을 먼저 고르세요"
MSG_UNKNOWN = "명단에 없는 상담원입니다"
SKIP_NOT_FOUND = "없는 문의"
SKIP_CLOSED = "종료된 문의"
SKIP_SAME = "이미 그 상담원 담당"
SKIP_DEPT = "그 문의를 맡은 부서의 상담원이 아님"


class AssignIn(BaseModel):
    sub_ticket_ids: list[str]
    assignee: str


@router.post("/sub-tickets/assign", response_model=schemas.AssignResult, response_model_exclude_unset=True)
def assign_many(data: AssignIn, conn: Connection = Depends(get_conn), x_agent_id: str | None = Header(default=None)) -> dict:
    ids = list(dict.fromkeys(i.strip() for i in data.sub_ticket_ids if i.strip()))
    if not ids:
        raise HTTPException(400, MSG_NO_IDS)
    if len(ids) > MAX_IDS:
        raise HTTPException(400, MSG_TOO_MANY)
    by = (x_agent_id or "").strip()
    if not by:
        raise HTTPException(400, MSG_NO_AGENT)
    target = next((a for a in agents() if a["name"] == data.assignee.strip()), None)
    if target is None:
        raise HTTPException(400, MSG_UNKNOWN)
    moved: list[str] = []
    skipped: list[dict] = []
    with conn.transaction():  # 읽은 줄을 잠그고 바꾼다(같은 문의를 두 사람이 동시에 바꾸지 않게)
        found = {r[0]: r for r in conn.execute(
            """SELECT sub_ticket_id, status, assignee_masked, assigned_dept, escalated_to FROM svc.sub_ticket
                WHERE sub_ticket_id = ANY(%s) FOR UPDATE""", (ids,)).fetchall()}
        for sid in ids:
            row = found.get(sid)
            if row is None:
                skipped.append({"sub_ticket_id": sid, "reason": SKIP_NOT_FOUND})
                continue
            _, status, current, dept, escalated_to = row
            if status in CLOSED:
                skipped.append({"sub_ticket_id": sid, "reason": SKIP_CLOSED})
            elif current == target["name"]:
                skipped.append({"sub_ticket_id": sid, "reason": SKIP_SAME})
            elif target["dept"] not in (dept, escalated_to):
                skipped.append({"sub_ticket_id": sid, "reason": SKIP_DEPT})
            else:
                conn.execute("UPDATE svc.sub_ticket SET assignee_masked = %s WHERE sub_ticket_id = %s", (target["name"], sid))
                conn.execute("""INSERT INTO svc.assignment_history (sub_ticket_id, from_assignee, to_assignee, changed_by)
                                VALUES (%s, %s, %s, %s)""", (sid, current, target["name"], by))
                moved.append(sid)
    return {"moved": moved, "skipped": skipped}
