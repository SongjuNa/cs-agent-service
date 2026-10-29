"""유사 해결사례 (FR-019, 기술 명세서 v1.4 §4-7, 변경 add-similar-cases). 처리 흐름의 Q8b와 사례 직접 검색(add-case-search)이 쓴다.

색인 = resolution_cases.csv에서 팀 정답지 문의(eval.gold_set.source_ticket_id)의 사례를 뺀 것(FR-019 처리 3, D30).
새 표 없이 파일 캐시(backend/.cache, Git 제외)와 서버 메모리에 둔다(2026-10-29 조장 결정, design 결정 1).
벡터는 고장 사전과 같은 방식(sha256(모델 이름 + 줄바꿈 + 글))으로 case_summary의 "document" 임베딩을 쓴다.
해결사례는 상담원 참고용이며 답변 초안 입력에 넣지 않는다(FR-019, AC-019-3).
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from psycopg import Connection

from app.config import get_settings
from app.llm.embed import Embedder, embed_texts
from app.retrieval.fault import SymptomVectors, _cosine

log = logging.getLogger(__name__)

SEARCHED = ("DEFECT", "INSTALL", "WARRANTY", "FW_UPDATE", "RETURN")  # FR-019 처리 1
TOP_K = 3  # FR-019 처리 2 "3건(제안)"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CASES_FILE = CACHE_DIR / "resolution_cases.json"
VECTORS_FILE = CACHE_DIR / "resolution_case_vectors.json"

NOTE_NONE = "비슷한 사례 없음"  # FR-019 예외 1행
NOTE_FAILED = "사례 검색 실패"  # 예외 2행

# 색인에 남기는 열(resolution_cases.csv 열 이름 그대로). 앞 11개는 Q8b(design 결정 1), 나머지는 사례 상세(add-case-search 결정 2)
COLUMNS = ("case_id", "ticket_id", "category_code", "product_code", "product_family", "error_code", "symptom",
           "root_cause", "action_taken", "resolution_result", "case_summary",
           "initial_hypothesis", "diagnosis_method", "replacement_part", "onsite_visit", "time_to_resolve_hours",
           "recurrence_prevention")


def build_index(conn: Connection, data_dir: Path) -> list[dict[str, Any]]:
    """resolution_cases.csv → 팀 정답지 문의의 사례를 뺀 목록(case_id 순). 빈 값은 None."""
    gold = {r[0] for r in conn.execute("SELECT source_ticket_id FROM eval.gold_set WHERE source_ticket_id IS NOT NULL")}
    with (data_dir / "resolution_cases.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = [{c: (r.get(c) or None) for c in COLUMNS} for r in csv.DictReader(f) if r["ticket_id"] not in gold]
    return sorted(rows, key=lambda r: r["case_id"])


def write_index(rows: list[dict[str, Any]], path: Path = CASES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


class CaseIndex:
    """색인 파일을 메모리에 한 번 올린다. 파일이 없으면 DATA_DIR의 원본에서 만들어 쓴다(jobs/build_case_index.py와 같은 함수)."""

    def __init__(self, path: Path | None = CASES_FILE, vectors: SymptomVectors | None = None):
        self.path = path
        self.vectors = vectors or SymptomVectors(VECTORS_FILE, step="Q8b")
        self._rows: list[dict[str, Any]] | None = None

    def rows(self, conn: Connection) -> list[dict[str, Any]]:
        if self._rows is None:
            try:
                self._rows = json.loads(self.path.read_text(encoding="utf-8")) if self.path else None
            except FileNotFoundError:
                self._rows = None
            if self._rows is None:
                self._rows = build_index(conn, get_settings().data_path)
                if self.path is not None:
                    try:
                        write_index(self._rows, self.path)
                    except OSError:
                        log.warning("해결사례 색인을 쓰지 못함: %s (메모리만 씀)", self.path)
        return self._rows

    def get(self, conn: Connection, case_id: str) -> dict[str, Any] | None:
        return next((r for r in self.rows(conn) if r["case_id"] == case_id), None)


_default_index = CaseIndex()


def default_index() -> CaseIndex:
    return _default_index


@dataclass
class SimilarCases:
    cases: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_output(self) -> dict[str, Any]:
        """실행 기록 Q8b output_json(design 결정 3)."""
        return {"cases": self.cases, "notes": self.notes}


def rank(embedder: Embedder, index: CaseIndex, group: list[dict[str, Any]], question: str, call: str,
         error_code: str | None) -> list[tuple[dict[str, Any], float]]:
    """같은 에러 코드를 먼저, 그다음 코사인 유사도 순(design 결정 2). 임베딩 실패는 embed_texts의 LlmError로 올린다."""
    (qvec,) = embed_texts(embedder, call, [question], "query")
    vecs = index.vectors.get(embedder, [r["case_summary"] or "" for r in group])
    scored = [(r, _cosine(qvec, v)) for r, v in zip(group, vecs)]
    same = lambda r: bool(error_code) and r["error_code"] == error_code  # noqa: E731
    return sorted(scored, key=lambda x: (not same(x[0]), -x[1], x[0]["case_id"]))


def similar_cases(conn: Connection, embedder: Embedder, category_code: str | None, family: str | None,
                  error_code: str | None, query_text: str | None, source_ticket_id: str | None,
                  index: CaseIndex | None = None) -> SimilarCases | None:
    """찾는 유형이 아니면 None(단계 없음, AC-019-2). 오류는 올리지 않고 "사례 검색 실패"로 둔다(흐름은 계속)."""
    if category_code not in SEARCHED:
        return None
    index = index or _default_index
    out = SimilarCases()
    try:
        # 같은 제품군만. 자기 사례(같은 원본 번호)는 뺀다(proposal "뺄 사례")
        group = [r for r in index.rows(conn) if family and r["product_family"] == family
                 and not (source_ticket_id and r["ticket_id"] == source_ticket_id)]
        question = " ".join(t for t in (query_text, error_code) if t)
        if not group:
            out.notes.append(NOTE_NONE)
            return out
        if not question:
            raise ValueError("질문 글이 없다")
        scored = rank(embedder, index, group, question, "Q8b", error_code)[:TOP_K]
    except Exception as exc:  # noqa: BLE001 — 사례 검색 실패여도 흐름은 계속(FR-019 예외 2행)
        log.warning("유사 해결사례 검색 실패: %s", exc)
        out.notes.append(NOTE_FAILED)
        return out
    out.cases = [{"case_id": r["case_id"], "cause": r["root_cause"], "action": r["action_taken"],
                  "result": r["resolution_result"], "error_code": r["error_code"], "score": round(s, 6),
                  "method": "ERROR_CODE" if error_code and r["error_code"] == error_code else "SEMANTIC"}
                 for r, s in scored]
    return out
