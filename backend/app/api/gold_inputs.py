"""시연용 불러오기 (명세서 v1.5 FR-003, 기술 명세서 v1.4 §8-1 `GET /gold/tickets/{source_ticket_id}`, §6-1).

운영진 문의(CSV1-)는 `gold.v_inputs`(입력 열 6개)만 읽는다(CLAUDE.md 규칙 6). 제목과 정답 열은 없다.
팀이 만든 문의(GS-, 화면 정의서 v2 부록 B-1)는 `eval.gold_set`의 입력 열만 읽는다(schema.sql 서비스 계정 열 권한).
data_split은 보지 않는다(FR-003 처리 2). 팀 정답지 문의면 gold_set: true.
"""

from __future__ import annotations

import re

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api.deps import get_conn

router = APIRouter()
ID_FORMAT = re.compile(r"^CSV1-\d{6}$")  # 운영진 번호(FR-003 입력)
GS_FORMAT = re.compile(r"^GS-\d{3}$")  # 팀 정답지 번호(화면 정의서 v2 부록 B-1 GS-001~GS-080)
MSG_FORMAT = "형식: CSV1-000000 또는 GS-001"  # FR-003 예외 1행 + 부록 B-1 번호 형식
MSG_NOT_FOUND = "문의를 찾을 수 없음"  # FR-003 예외 2행
FIELDS = ("channel", "customer_id", "product_code", "language", "inquiry_body", "received_at_utc")


@router.get("/gold/tickets/{source_ticket_id}")
def load(source_ticket_id: str, conn: Connection = Depends(get_conn)) -> dict:
    tid = source_ticket_id.strip().upper()
    cols = ", ".join(FIELDS)
    if ID_FORMAT.match(tid):
        row = conn.execute(f"SELECT {cols} FROM gold.v_inputs WHERE ticket_id = %s", (tid,)).fetchone()
        gold_set = row is not None and conn.execute(
            "SELECT EXISTS (SELECT 1 FROM eval.gold_set WHERE source_ticket_id = %s)", (tid,)).fetchone()[0]
    elif GS_FORMAT.match(tid):  # 팀 정답지 문의는 모두 채점용
        row = conn.execute(f"SELECT {cols} FROM eval.gold_set WHERE gold_set_id = %s", (tid,)).fetchone()
        gold_set = True
    else:
        raise HTTPException(400, MSG_FORMAT)
    if row is None:
        raise HTTPException(404, MSG_NOT_FOUND)
    out = dict(zip(FIELDS, row))
    out["product_code"] = out["product_code"] or None
    if out["received_at_utc"] is not None:  # 시각은 모두 UTC(§8-1)
        out["received_at_utc"] = out["received_at_utc"].astimezone(timezone.utc)
    return {"source_ticket_id": tid, **out, "gold_set": gold_set}
