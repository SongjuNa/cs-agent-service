"""W2 문서 색인: docs/ 107개 → 절 단위 청크 → 임베딩 → ref.doc_chunk (기술 명세서 v1.4 §4-2, §4-5, §9 W2).

ref.doc_chunk를 비우고 처음부터 다시 만든다. 전체가 트랜잭션 하나다.
끝에 W2 확인(정답 절이 모두 청크로 있는지)을 돌리고, 빠진 것이 있으면 실패로 끝낸다.

실행: 저장소 루트에서 python -m jobs.build_doc_index [--no-embed]
  --no-embed  키 없이 청크만 넣는다. 이때 검색은 "검색 실패"가 된다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from app.config import get_settings
from app.llm.embed import Embedder, default_embedder, embed_texts
from app.retrieval.chunking import split_sections


def build(conn: psycopg.Connection, data_dir: Path, embedder: Embedder | None) -> int:
    docs = conn.execute(
        "SELECT doc_id, title, doc_type, product_code, family, path FROM ref.document ORDER BY doc_id"
    ).fetchall()
    rows = []
    for doc_id, title, doc_type, product_code, family, path in docs:
        markdown = (data_dir / path).read_text(encoding="utf-8")
        for chunk in split_sections(doc_id, markdown):
            rows.append((chunk, title, doc_type, product_code, family))

    vectors: list[list[float] | None] = [None] * len(rows)
    if embedder is not None:
        texts = [chunk.embed_text(title) for chunk, title, *_ in rows]
        vectors = embed_texts(embedder, "W2", texts, "document")

    conn.execute("DELETE FROM ref.doc_chunk")
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO ref.doc_chunk
                 (chunk_id, doc_id, doc_type, product_code, family, section_no, section_title, text, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)""",
            [
                (c.chunk_id, c.doc_id, doc_type, product_code, family, c.section_no, c.section_title, c.text,
                 None if v is None else "[" + ",".join(map(str, v)) + "]")
                for (c, _, doc_type, product_code, family), v in zip(rows, vectors)
            ],
        )
    return len(rows)


def missing_gold_sections(conn: psycopg.Connection) -> list[tuple[str, str]]:
    """W2 확인: 정답의 (reference_doc_id, reference_section) 쌍 중 청크가 없는 것.

    정답 열을 읽으므로 색인 확인과 시험에서만 쓴다(CLAUDE.md 규칙 6의 채점·시험 예외).
    """
    return [tuple(r) for r in conn.execute(
        """SELECT DISTINCT g.reference_doc_id, g.reference_section
             FROM gold.ticket_gold g
            WHERE coalesce(g.reference_doc_id, '') <> '' AND coalesce(g.reference_section, '') <> ''
              AND NOT EXISTS (SELECT 1 FROM ref.doc_chunk c
                               WHERE c.doc_id = g.reference_doc_id AND c.section_no = g.reference_section)
            ORDER BY 1, 2"""
    ).fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-embed", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    embedder = None if args.no_embed else default_embedder()
    with psycopg.connect(settings.database_url) as conn:
        count = build(conn, settings.data_path, embedder)
        missing = missing_gold_sections(conn)
        if missing:
            conn.rollback()
            raise SystemExit(f"정답 절 {len(missing)}개가 청크에 없어 색인을 넣지 않았습니다: {missing[:5]}")
    print(f"ref.doc_chunk: {count} (임베딩 {'없음' if embedder is None else '있음'})")


if __name__ == "__main__":
    main()
