"""고장 진단 (FR-018, 기술 명세서 v1.4 §4-6). 처리 흐름의 Q8a.

정확 조회(같은 제품군·에러 코드, EXACT 1.0) → 없으면 같은 제품군 증상 검색(SYMPTOM, 상위 3건).
진단 후보는 상담원 참고용이며 답변 초안 입력에 넣지 않는다(FR-018 처리 5).
증상 벡터는 새 열 없이 파일 캐시와 서버 메모리에 둔다(조장 결정 2026-10-23, design 결정 2).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from psycopg import Connection

from app.llm.embed import Embedder, embed_texts
from app.pipeline.state import FaultCandidate

log = logging.getLogger(__name__)

DIAGNOSED = ("DEFECT", "INSTALL", "WARRANTY")  # FR-018 처리 1
TOP_K = 3  # §4-6 2번 (제안, T39)
LOW_SCORE = 0.5  # "관련성 낮음" 기준 (T39 미정, 구현 선택 C-134)
CACHE_FILE = Path(__file__).resolve().parents[2] / ".cache" / "fault_symptoms.json"

NOTE_NO_FAMILY = "고장 사전에 해당 제품군 없음"  # FR-018 예외 1행
NOTE_CODE_UNKNOWN = "에러 코드 미등록"  # 예외 2행
NOTE_LOW = "관련성 낮음"  # 예외 3행
NOTE_FAILED = "진단 실패"  # 예외 4행


@dataclass
class Diagnosis:
    candidates: list[FaultCandidate] = field(default_factory=list)
    method: str | None = None  # EXACT / SYMPTOM / None(진단 없음)
    notes: list[str] = field(default_factory=list)

    def as_output(self) -> dict:
        """실행 기록 Q8a output_json(§4-6 4번)."""
        return {"fault_candidates": [c.model_dump() for c in self.candidates], "method": self.method,
                "notes": self.notes}


class SymptomVectors:
    """증상 문장 벡터. 키 = sha256(모델 이름 + 줄바꿈 + 문장). 없는 키만 만들어 파일에 다시 쓴다."""

    def __init__(self, path: Path | None = CACHE_FILE):
        self.path = path
        self._memory: dict[str, list[float]] | None = None

    @staticmethod
    def key(model: str, text: str) -> str:
        return hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()

    def warm(self) -> int:
        """서버가 켜질 때: 언어 모델을 부르지 않고 캐시 파일만 메모리에 올린다. 올린 벡터 수."""
        return len(self._load())

    def _load(self) -> dict[str, list[float]]:
        if self._memory is None:
            self._memory = {}
            if self.path is not None:
                try:
                    self._memory = json.loads(self.path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    pass
                except Exception:  # 깨진 파일은 무시하고 다시 만든다
                    log.warning("고장 사전 벡터 캐시를 읽지 못함: %s", self.path)
        return self._memory

    def get(self, embedder: Embedder, texts: list[str]) -> list[list[float]]:
        """texts의 벡터. 캐시에 없으면 "document" 임베딩(두 번 실패하면 embed_texts의 LlmError)."""
        model = getattr(embedder, "model", type(embedder).__name__)
        memory = self._load()
        keys = [self.key(model, t) for t in texts]
        missing = sorted({t for t, k in zip(texts, keys) if k not in memory})
        if missing:
            for text, vector in zip(missing, embed_texts(embedder, "Q8a", missing, "document")):
                memory[self.key(model, text)] = vector
            self._save()
        return [memory[k] for k in keys]

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._memory), encoding="utf-8")
        except OSError:
            log.warning("고장 사전 벡터 캐시를 쓰지 못함: %s (메모리만 씀)", self.path)


_default_vectors = SymptomVectors()


def warm_cache() -> int:
    return _default_vectors.warm()


def _cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def _candidate(row: tuple, method: str, score: float) -> FaultCandidate:
    fault_id, _symptom, cause, check, action, onsite, rma = row
    return FaultCandidate(fault_id=fault_id, cause=cause, check=check, action=action, onsite_required=onsite,
                          replace_required=rma, method=method, score=round(score, 6))


def diagnose(conn: Connection, embedder: Embedder, category_code: str | None, family: str | None,
             product_code: str | None, error_code: str | None, query_text: str | None,
             vectors: SymptomVectors | None = None) -> Diagnosis | None:
    """진단 대상 유형이 아니면 None(단계 없음, AC-018-3). 오류는 올리지 않고 "진단 실패"로 둔다."""
    if category_code not in DIAGNOSED:
        return None
    vectors = vectors or _default_vectors
    out = Diagnosis()
    rows = conn.execute(
        """SELECT f.fault_id, f.symptom, f.root_cause, f.diagnosis, f.action, f.needs_onsite, f.needs_rma, f.error_code,
                  EXISTS (SELECT 1 FROM ref.fault_product fp WHERE fp.fault_id = f.fault_id AND fp.product_code = %s)
             FROM ref.fault f WHERE f.family = %s ORDER BY f.fault_id""",
        (product_code, family),
    ).fetchall() if family else []
    if not rows:
        out.notes.append(NOTE_NO_FAMILY)
        return out
    question = " ".join(t for t in (query_text, error_code) if t)

    def ranked(group: list[tuple]) -> list[tuple[tuple, float]]:
        (qvec,) = embed_texts(embedder, "Q8a", [question], "query")
        svecs = vectors.get(embedder, [r[1] for r in group])
        scored = [(r, _cosine(qvec, v)) for r, v in zip(group, svecs)]
        return sorted(scored, key=lambda x: (-x[1], x[0][0]))

    exact = [r for r in rows if error_code and r[7] == error_code]
    if exact:
        exact = [r for r in exact if r[8]] or exact  # 그 제품에 걸린 행으로 좁힌다(C-133)
        if len(exact) > 1 and question:
            try:
                exact = [r for r, _ in ranked(exact)]
            except Exception:  # noqa: BLE001 — 순서만 fault_id 순으로 둔다
                pass
        out.method = "EXACT"
        out.candidates = [_candidate(r[:7], "EXACT", 1.0) for r in exact]
        return out
    if error_code:
        out.notes.append(NOTE_CODE_UNKNOWN)
    if not question:
        out.notes.append(NOTE_FAILED)
        return out
    try:
        scored = ranked(rows)[:TOP_K]
    except Exception as exc:  # noqa: BLE001 — 진단 실패여도 흐름은 계속(FR-018 예외 4행)
        log.warning("고장 진단 실패: %s", exc)
        out.notes.append(NOTE_FAILED)
        return out
    out.method = "SYMPTOM"
    out.candidates = [_candidate(r[:7], "SYMPTOM", s) for r, s in scored]
    if all(c.score < LOW_SCORE for c in out.candidates):
        out.notes.append(NOTE_LOW)
    return out
