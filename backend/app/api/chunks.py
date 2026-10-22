"""인용 절 본문 (FR-024 처리 3, 기술 명세서 v1.4 §8-1 GET /chunks/{chunk_id}, 화면 정의서 v2 P2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api.deps import get_conn

router = APIRouter()


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str, conn: Connection = Depends(get_conn)) -> dict:
    row = conn.execute(
        """SELECT c.chunk_id, c.doc_id, d.title, c.section_no, c.section_title, c.text
             FROM ref.doc_chunk c JOIN ref.document d ON d.doc_id = c.doc_id WHERE c.chunk_id = %s""",
        (chunk_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "본문 열기 실패")
    keys = ("chunk_id", "doc_id", "doc_title", "section_no", "section_title", "text")
    return dict(zip(keys, row))
