"""W3 뒤 해결사례 색인: resolution_cases.csv → 팀 정답지 문의의 사례를 뺀 목록 → backend/.cache (변경 add-similar-cases 결정 1).

새 표를 만들지 않는다(2026-10-29 조장 결정, 파일 캐시). 벡터는 서버가 처음 검색할 때 없는 것만 만든다.
load_reference·load_gold 뒤 한 번 돌린다. 팀 정답지(eval.gold_set)가 바뀌면 다시 돌린다.
서버는 색인 파일이 없으면 같은 함수로 스스로 만들므로, 이 작업은 미리 만들어 두는 용도다.

실행: 저장소 루트에서 python -m jobs.build_case_index
"""

from __future__ import annotations

import psycopg

from app.config import get_settings
from app.retrieval.cases import CASES_FILE, build_index, write_index


def main() -> None:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        rows = build_index(conn, settings.data_path)
    write_index(rows)
    print(f"해결사례 {len(rows)}건을 썼다: {CASES_FILE}")


if __name__ == "__main__":
    main()
