"""해결사례 직접 검색 (변경 add-case-search, FR 초안 06). 읽기만, 고치는 주소는 없다.

FR-019 색인(app/retrieval/cases.py)을 그대로 쓴다. 팀 정답지 문의의 사례는 색인에 없어 결과·상세에 나오지 않는다(D30).
결과는 상담원 화면에만 보이고 초안 입력·인용에 쓰지 않는다(FR-019, AC-019-3).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.api import schemas
from app.api.deps import get_clients, get_conn
from app.retrieval.cases import default_index, rank

router = APIRouter()
log = logging.getLogger(__name__)
LIMIT = 20  # design 결정 1
MAX_Q = 200  # 화면 명세 SCR-09 입력 검증(구현 선택)
MSG_EMPTY = "검색어를 입력하세요"
MSG_NOT_FOUND = "사례를 찾을 수 없음"
NOTE_SEMANTIC_FAILED = "뜻 검색 실패. 에러 코드·제품으로만 찾았습니다"  # 화면 명세 N-09-04

ROW_KEYS = ("case_id", "ticket_id", "category_code", "product_code", "product_family", "error_code", "symptom",
            "resolution_result", "case_summary")


@router.get("/cases", response_model=schemas.CaseRows, response_model_exclude_unset=True)
def search(q: str = "", error_code: str = "", product_code: str = "", category_code: str = "",
           conn: Connection = Depends(get_conn), clients=Depends(get_clients)) -> dict:
    """같은 에러 코드를 먼저, 그다음 q의 뜻이 가까운 순(q가 없으면 case_id 순)으로 20건(design 결정 1)."""
    q, error_code, product_code, category_code = (v.strip() for v in (q, error_code, product_code, category_code))
    if not (q or error_code or product_code or category_code):
        raise HTTPException(400, MSG_EMPTY)
    if len(q) > MAX_Q:
        raise HTTPException(400, f"검색어는 {MAX_Q}자 이하")
    index = default_index()
    group = [r for r in index.rows(conn)
             if (not product_code or r["product_code"] == product_code) and (not category_code or r["category_code"] == category_code)]
    same = lambda r: bool(error_code) and r["error_code"] == error_code  # noqa: E731
    notes: list[str] = []
    scores: dict[str, float] = {}
    if q and group:
        try:  # 언어 모델 호출 계층의 embed_texts만 부르고, 검색어는 보내기 직전 가린다(CLAUDE.md 규칙 2)
            ranked = rank(clients.embedder(), index, group, q, "CASE_SEARCH", error_code or None)
            group, scores = [r for r, _ in ranked], {r["case_id"]: s for r, s in ranked}
        except Exception as exc:  # noqa: BLE001 — 거르기 결과만 낸다(design 결정 1 "실패")
            log.warning("해결사례 뜻 검색 실패: %s", exc)
            notes.append(NOTE_SEMANTIC_FAILED)
            group = sorted(group, key=lambda r: (not same(r), r["case_id"]))
    else:
        group = sorted(group, key=lambda r: (not same(r), r["case_id"]))
    rows = [{**{k: r[k] for k in ROW_KEYS}, "score": round(scores[r["case_id"]], 6) if r["case_id"] in scores else None,
             "same_error_code": same(r)} for r in group[:LIMIT]]
    return {"rows": rows, "total": len(group), "notes": notes}


@router.get("/cases/{case_id}", response_model=schemas.CaseDetail, response_model_exclude_unset=True)
def detail(case_id: str, conn: Connection = Depends(get_conn)) -> dict:
    """사례 상세(design 결정 2). 없는 사례·팀 정답지 사례는 404."""
    row = default_index().get(conn, case_id)
    if row is None:
        raise HTTPException(404, MSG_NOT_FOUND)
    return row
