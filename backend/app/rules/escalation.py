"""이관 후보 (FR-020, 기술 명세서 v1.4 §5-6). 처리 흐름의 Q9a.

운영진 이관 행(routing_rules.csv rule_source = ESCALATION)은 표에서 읽고, 조건 문구 "조치 유형 = X"의 X로 판정한다.
팀 보충 이관 규칙 2개는 설정 파일(config/escalation_rules_team.yaml)에 둔다(조장 결정 2026-10-23).
표시만 하고 상태는 바꾸지 않는다(AC-020-4). 규칙 코드라 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from psycopg import Connection

from app.config import REPO_ROOT

TEAM_RULES_FILE = REPO_ROOT / "config" / "escalation_rules_team.yaml"
DIAGNOSED = ("DEFECT", "INSTALL", "WARRANTY")  # 고장 진단 대상(FR-018 처리 1)

ACTION = re.compile(r"조치 유형\s*=\s*([A-Z_]+)")
# 조치 유형 X → 켜지는 조건 이름·이유 표시·이관 사유 코드(§5-6 표, schema.sql escalation_reason, C-146)
ACTIONS = {"SAFETY": ("SAFETY", "SAFETY"), "RMA": ("교체", "RMA_REQUIRED"), "ONSITE": ("현장 출동", "ONSITE_REQUIRED")}

NOTE_NO_DIAGNOSIS = "진단 없음 — 이관 조건만 표시"  # FR-020 예외 1행
NOTE_RULES_FAILED = "이관 규칙을 읽을 수 없음"  # 예외 2행


@dataclass(frozen=True)
class Candidate:
    rule_id: str
    dept: str
    reason: str  # 화면 이유 표시(SAFETY / 교체 / 현장 출동 / 팀 규칙의 사유 코드)
    reason_code: str  # escalation_reason 11값 중 하나([이관] 기본값용)
    team: bool = False


@dataclass
class EscalationResult:
    candidates: list[Candidate] = field(default_factory=list)
    escalation_condition: str | None = None  # FR-012가 기록한 이관 조건 문구(후보가 없을 때 보임)
    notes: list[str] = field(default_factory=list)
    failed: bool = False

    def as_output(self) -> dict[str, Any]:
        """실행 기록 Q9a output_json(§5-6 저장)."""
        return {"escalation_candidates": [c.__dict__ for c in self.candidates],
                "escalation_condition": self.escalation_condition, "notes": self.notes}


@lru_cache(maxsize=4)
def load_team_rules(path: Path = TEAM_RULES_FILE) -> tuple[dict[str, Any], ...]:
    rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    for r in rules:
        if not {"rule_id", "category", "escalation_dept", "escalation_reason"} <= r.keys():
            raise ValueError(f"팀 이관 규칙 모양이 다르다: {r}")
    return tuple(rules)


def _ops_rows(conn: Connection) -> list[tuple[str, str | None, str, str]]:
    return conn.execute("""SELECT rule_id, category, escalation_dept, escalation_condition FROM ref.routing_rule
                            WHERE rule_source = 'ESCALATION' ORDER BY rule_id""").fetchall()


def escalation_candidates(conn: Connection, category: str | None, urgency: str | None,
                          top_fault: tuple[bool | None, bool | None] | None, return_reason: str | None,
                          priority: str | None, escalation_condition: str | None,
                          team_rules_file: Path = TEAM_RULES_FILE) -> EscalationResult:
    """top_fault = 진단 1순위의 (onsite_required, replace_required). 진단 후보가 없으면 None."""
    out = EscalationResult(escalation_condition=escalation_condition)
    try:
        rows, team = _ops_rows(conn), load_team_rules(team_rules_file)
    except Exception:  # noqa: BLE001 — 후보 없음, 기록만(FR-020 예외 2행)
        out.notes.append(NOTE_RULES_FAILED)
        out.failed = True
        return out
    if category in DIAGNOSED and top_fault is None:
        out.notes.append(NOTE_NO_DIAGNOSIS)
    onsite, replace = top_fault or (None, None)
    on = {"SAFETY": urgency == "SAFETY", "RMA": bool(replace), "ONSITE": bool(onsite)}
    for rule_id, _category, dept, condition in rows:  # 켜지는 조건에 유형 제한이 없다(§5-6 표, FR-020 처리 2, C-149)
        m = ACTION.search(condition or "")
        if not m or m.group(1) not in ACTIONS:
            continue
        if on[m.group(1)]:
            reason, code = ACTIONS[m.group(1)]
            out.candidates.append(Candidate(rule_id, dept, reason, code))
    text = (return_reason or "").lower()
    for r in team:
        if r["category"] != category:
            continue
        words = r.get("return_reason_words")
        if words is not None and not any(w in text for w in words):  # §5-3과 같은 방식(소문자, 단어 포함)
            continue
        if r.get("priority") and r["priority"] != priority:
            continue
        out.candidates.append(Candidate(r["rule_id"], r["escalation_dept"], r["escalation_reason"],
                                        r["escalation_reason"], team=True))
    return out
