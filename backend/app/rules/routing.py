"""부서 배정과 반품 구분 (FR-012, 기술 명세서 §5-3)."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from psycopg import Connection

from app.config import REPO_ROOT

RETURN_WORDS_FILE = REPO_ROOT / "config" / "return_reason_words.yaml"
NON_DEFECT_RULE_ID = "RT-ALL-RETURN-NON_DEFECT"


@dataclass(frozen=True)
class ReturnKind:
    return_kind: str                      # DEFECT / NON_DEFECT / UNKNOWN
    matched_words: list[str] = field(default_factory=list)   # 화면 C-04 "걸린 단어"


@dataclass(frozen=True)
class RoutingResult:
    assigned_dept: str | None = None
    routing_rule_id: str | None = None
    escalation_dept: str | None = None
    escalation_condition: str | None = None
    dept_name_ko: str | None = None
    dept_name_en: str | None = None
    return_kind: str | None = None
    flags: list[str] = field(default_factory=list)


@lru_cache
def load_return_words(path: Path = RETURN_WORDS_FILE) -> dict[str, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {"non_defect": list(data["non_defect"]), "defect": list(data["defect"])}


def decide_return_kind(return_reason: str | None, words: dict[str, list[str]] | None = None) -> ReturnKind:
    """영어 반품 사유를 소문자로 바꿔 단어 목록과 비교한다. 사유가 없으면 UNKNOWN."""
    if not return_reason:
        return ReturnKind("UNKNOWN")
    words = words or load_return_words()
    text = return_reason.lower()
    non_defect = [w for w in words["non_defect"] if w in text]
    defect = [w for w in words["defect"] if w in text]
    if non_defect and not defect:
        return ReturnKind("NON_DEFECT", non_defect)
    if defect and not non_defect:
        return ReturnKind("DEFECT", defect)
    return ReturnKind("UNKNOWN", non_defect + defect)


def assign_dept(conn: Connection, product_family: str | None, category_code: str | None,
                return_kind: str | None = None) -> RoutingResult:
    """기본 행 RT-{family}-{category}. RETURN이고 NON_DEFECT면 RT-ALL-RETURN-NON_DEFECT."""
    if not product_family:
        return RoutingResult(flags=["제품 확인 뒤 배정됨"])
    if not category_code:
        return RoutingResult(flags=["분류 뒤 계산됨"])
    flags = []
    kind = None
    rule_id = f"RT-{product_family}-{category_code}"
    if category_code == "RETURN":
        kind = return_kind or "UNKNOWN"
        if kind == "NON_DEFECT":
            rule_id = NON_DEFECT_RULE_ID
        elif kind == "UNKNOWN":
            flags.append("반품 사유 확인 필요")
    row = conn.execute(
        """SELECT r.rule_id, COALESCE(r.primary_dept, f.tech_support_dept), r.escalation_dept, r.escalation_condition
             FROM ref.routing_rule r
             JOIN ref.product_family f ON f.family = %s
            WHERE r.rule_id = %s AND r.rule_source <> 'ESCALATION'""",
        (product_family, rule_id),
    ).fetchone()
    if row is None:
        return RoutingResult(return_kind=kind, flags=flags + ["배정 규칙 없음 — 분류 재검토"])
    rule_id, dept, esc_dept, esc_condition = row
    names = conn.execute(
        "SELECT dept_name_ko, dept_name_en FROM ref.department WHERE dept_code = %s", (dept,)
    ).fetchone()
    return RoutingResult(dept, rule_id, esc_dept, esc_condition, *(names or (None, None)),
                         return_kind=kind, flags=flags)
