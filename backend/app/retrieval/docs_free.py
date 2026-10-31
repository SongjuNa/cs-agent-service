"""범위 제한 없는 문서 절 검색 (변경 add-agent-assistant design 결정 2).

search_evidence(app/retrieval/search.py)는 티켓의 유형·제품 범위를 전제로 한다. 상담원이 자유롭게 묻는 질문에는
범위가 없으므로, 같은 점수 방식(코사인 유사도 + 정확 문자열 가산점, 상위 5개)을 범위 없이 쓴다.
기준 점수(기술 명세서 §4-4 T27)는 아직 없어서 점수가 낮아도 상위 5개를 돌려주고, 판단은 답 만들기 단계가 한다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from psycopg import Connection

from app.llm.client import LlmError
from app.llm.embed import Embedder, embed_texts
from app.retrieval.search import EXACT_BONUS, TOP_K

log = logging.getLogger(__name__)

CALL_NAME = "Q15"  # 상담원 도우미 질문 검색 (기술 명세서 Q 번호와 겹치지 않는지 확인 필요)
# 질문에서 정확히 맞춰 볼 말: 오류 코드(E.OC, F-12), 펌웨어 버전(v1.2.3), 제품 코드(ACB-AS-2000)
_EXACT = re.compile(r"\b(?:[A-Z]{1,4}[.\-]\d{1,3}[A-Z]{0,2}|[A-Z]{1,5}\.[A-Z]{1,4}|v?\d+\.\d+(?:\.\d+)+|[A-Z]{2,}(?:-[A-Z0-9]+){2,})\b")


@dataclass
class DocHit:
    chunk_id: str
    doc_id: str
    section_no: str
    title: str
    text: str
    score: float


def exact_terms(question: str) -> list[str]:
    """질문에 든 오류 코드·버전·제품 코드 모양의 말. 절 본문에 그대로 있으면 점수를 더한다."""
    return list(dict.fromkeys(_EXACT.findall(question)))


def search_docs(
    conn: Connection,
    embedder: Embedder,
    question: str,
    product_code: str | None = None,
    top_k: int = TOP_K,
) -> list[DocHit]:
    """질문과 뜻이 가까운 절 상위 top_k개. product_code가 있으면 그 제품 문서와 정책·제품군 FAQ 안에서만 찾는다.

    색인(embedding)이 비어 있거나 임베딩이 실패하면 LlmError를 그대로 올린다. 부르는 쪽이 안내 문구로 바꾼다.
    """
    scope, scope_params = "TRUE", []
    if product_code:
        scope = """(doc_type = 'POL' OR product_code = %s
                    OR (doc_type = 'FAQ' AND family = (SELECT family FROM ref.product WHERE product_code = %s)))"""
        scope_params = [product_code, product_code]

    empty = conn.execute(f"SELECT count(*) FROM ref.doc_chunk WHERE {scope} AND embedding IS NOT NULL", scope_params).fetchone()[0]
    if not empty:
        raise LlmError("UNKNOWN", "문서 색인이 비어 있다")

    (vector,) = embed_texts(embedder, CALL_NAME, [question], "query")  # 질문은 보내기 직전 가린다(규칙 2)
    qvec = "[" + ",".join(map(str, vector)) + "]"
    terms = exact_terms(question)
    rows = conn.execute(
        f"""SELECT chunk_id, doc_id, section_no, section_title, text, 1 - (embedding <=> %s::vector) AS similarity
              FROM ref.doc_chunk
             WHERE {scope} AND embedding IS NOT NULL""",
        [qvec, *scope_params],
    ).fetchall()
    hits = []
    for chunk_id, doc_id, section_no, title, text, similarity in rows:
        bonus = EXACT_BONUS if any(t in text for t in terms) else 0.0
        hits.append(DocHit(chunk_id, doc_id, section_no, title, text, round(float(similarity) + bonus, 6)))
    hits.sort(key=lambda h: (-h.score, h.chunk_id))
    return hits[:top_k]
