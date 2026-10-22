"""propose 문서의 근거 점검 (기계 점검).

사용: python scripts/check_sources.py <변경 이름>

openspec/changes/<변경 이름>/ 의 문서를 읽어, 기계로 확인할 수 있는 것만 검사한다.
- 근거 꼬리표: proposal·design의 목록 항목과 표 행에 근거 표시가 있는가
- FR·AC 번호가 명세서에 있는가, §절 번호가 기술 명세서·테이블 정의서 제목에 있는가
- ticket_id가 tickets.csv에, 규칙 ID(PR-, RT-, SLA-)가 ref CSV에 있는가
- 스키마.표 이름과 표.열 이름이 docs/database/schema.sql에 있는가

"뜻이 같은가"는 보지 않는다. 그것은 검증 에이전트(.claude/agents/source-checker.md)가 본다.
결과는 Markdown 표로 출력하고, 없는 이름·번호가 하나라도 있으면 종료 코드 1을 돌려준다.
"""

import csv
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FR_DOC = REPO_ROOT / "docs/requirements/functional-requirements.md"
TECH_DOC = REPO_ROOT / "docs/technical/technical-specification.md"
TABLE_DOC = REPO_ROOT / "docs/database/table-specification.md"
SCHEMA = REPO_ROOT / "docs/database/schema.sql"

# 정규식은 \w 대신 영문·숫자만 쓴다. 한국어 조사("표의")가 \w에 들어가 이름에 붙기 때문이다
# 근거 표시로 인정하는 글자. 표 행은 근거 열에 문서 번호가 있으면 인정한다
TAG_WORDS = ("근거:", "구현 선택")
TABLE_SOURCE_WORDS = ("FR-0", "AC-0", "§", "CLAUDE.md", "config.yaml", "명세서", "정의서", "구조 1순위", ".csv")
# 꼬리표 검사를 하지 않는 절 (목록이 아닌 이름 나열)
SKIP_SECTIONS = ("Capabilities", "New Capabilities", "Modified Capabilities", "Context", "Goals / Non-Goals")


def data_dir() -> Path:
    value = os.environ.get("DATA_DIR")
    if value is None:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATA_DIR="):
                    value = line.split("=", 1)[1].strip()
    path = Path(value or "data/CS_AI_Agent_Training_Data_v1")
    return path if path.is_absolute() else REPO_ROOT / path


def headings(path: Path) -> set[str]:
    """'### 5-3. 제목' → '5-3', '## 5. 제목' → '5'"""
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#{2,4}\s+(\d+(?:-\d+)*)\.", line)
        if m:
            found.add(m.group(1))
    return found


def schema_tables() -> dict[str, set[str]]:
    """{'ref.customer': {'customer_id', ...}, ...} (뷰는 열 없이)"""
    tables: dict[str, set[str]] = {}
    current = None
    for line in SCHEMA.read_text(encoding="utf-8").splitlines():
        m = re.match(r"CREATE (?:TABLE|VIEW|OR REPLACE VIEW) (\w+\.\w+)", line)
        if m:
            current = m.group(1)
            tables[current] = set()
            if "VIEW" in line:
                current = None
            continue
        if current:
            if line.startswith(")"):
                current = None
                continue
            col = re.match(r"\s+(\w+)\s+\w", line)
            if col and col.group(1).upper() not in ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT"):
                tables[current].add(col.group(1))
    return tables


def csv_column(path: Path, column: str) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {row[column] for row in csv.DictReader(f)}


def section_of(lines: list[str], index: int) -> str:
    for line in reversed(lines[: index + 1]):
        if line.startswith("## ") or line.startswith("### "):
            return line.lstrip("#").strip()
    return ""


def main() -> int:
    if len(sys.argv) != 2:
        print("사용: python scripts/check_sources.py <변경 이름>")
        return 2
    change_dir = REPO_ROOT / "openspec/changes" / sys.argv[1]
    files = sorted(p for p in change_dir.rglob("*.md") if p.name != "근거_점검표.md")
    if not files:
        print(f"문서가 없다: {change_dir}")
        return 2

    fr_text = FR_DOC.read_text(encoding="utf-8")
    fr_ids = set(re.findall(r"^### (FR-\d{3})", fr_text, re.M))
    ac_ids = set(re.findall(r"AC-\d{3}-\d+", fr_text))
    sections = headings(TECH_DOC) | headings(TABLE_DOC)
    tables = schema_tables()
    table_short = {name.split(".")[1]: cols for name, cols in tables.items()}

    data = data_dir()
    ticket_ids = csv_column(data / "tickets.csv", "ticket_id") if (data / "tickets.csv").exists() else None
    rule_ids = None
    if (data / "ref").exists():
        rule_ids = (
            csv_column(data / "ref/priority_rules.csv", "rule_id")
            | csv_column(data / "ref/routing_rules.csv", "rule_id")
            | csv_column(data / "ref/sla_policy.csv", "sla_id")
        )

    errors: list[tuple[str, int, str, str]] = []
    untagged: list[tuple[str, int, str]] = []

    for path in files:
        rel = path.relative_to(change_dir).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        check_tags = path.name in ("proposal.md", "design.md")
        for no, line in enumerate(lines, start=1):
            for fr in re.findall(r"FR-\d{3}", line):
                if fr not in fr_ids:
                    errors.append((rel, no, fr, "명세서에 없는 FR 번호"))
            for ac in re.findall(r"AC-\d{3}-\d+", line):
                if ac not in ac_ids:
                    errors.append((rel, no, ac, "명세서에 없는 AC 번호"))
            for sec in re.findall(r"§(\d+(?:-\d+)*)", line):
                if sec not in sections:
                    errors.append((rel, no, f"§{sec}", "기술 명세서·테이블 정의서 제목에 없는 절 (다른 문서의 절이면 무시)"))
            if ticket_ids is not None:
                for tid in re.findall(r"CSV1-\d{6}", line):
                    if tid not in ticket_ids:
                        errors.append((rel, no, tid, "tickets.csv에 없는 ticket_id"))
            if rule_ids is not None:
                for rid in re.findall(r"(?<![A-Za-z0-9_])(?:PR-\d{2}|RT-[A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)+|SLA-[A-Z_]+-[A-Z]+-P\d)(?![A-Za-z0-9_])", line):
                    if rid not in rule_ids:
                        errors.append((rel, no, rid, "ref CSV에 없는 규칙 ID"))
            for schema, table in re.findall(r"(?<![A-Za-z0-9_])(ref|svc|gold|scoring|eval)\.([a-z0-9_]+)", line):
                if f"{schema}.{table}" not in tables:
                    errors.append((rel, no, f"{schema}.{table}", "schema.sql에 없는 표"))
            for table, column in re.findall(r"(?<![A-Za-z0-9_.])([a-z_]+)\.([a-z_]+)(?![A-Za-z0-9_.(])", line):
                if table in table_short and table_short[table] and column not in table_short[table]:
                    errors.append((rel, no, f"{table}.{column}", "schema.sql의 그 표에 없는 열"))

            if not check_tags:
                continue
            stripped = line.strip()
            if section_of(lines, no - 1) in SKIP_SECTIONS:
                continue
            if stripped.startswith("- ") or stripped.startswith("* "):
                if not any(word in stripped for word in TAG_WORDS):
                    untagged.append((rel, no, stripped[:80]))
            elif stripped.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", stripped):
                previous = lines[no] if no < len(lines) else ""
                is_header = re.match(r"^\|[\s:|-]+\|$", previous.strip()) is not None
                if not is_header and not any(word in stripped for word in TAG_WORDS + TABLE_SOURCE_WORDS):
                    untagged.append((rel, no, stripped[:80]))

    print(f"# 기계 점검 결과: {sys.argv[1]}\n")
    if ticket_ids is None or rule_ids is None:
        print(f"> 데이터 폴더({data})가 없어 ticket_id·규칙 ID 검사를 건너뛰었다.\n")
    print(f"## 1. 없는 이름·번호 ({len(errors)}건)\n")
    if errors:
        print("| 파일 | 줄 | 값 | 문제 |\n|---|---|---|---|")
        for rel, no, value, problem in errors:
            print(f"| {rel} | {no} | `{value}` | {problem} |")
    else:
        print("없음")
    print(f"\n## 2. 근거 꼬리표가 없는 줄 ({len(untagged)}건)\n")
    if untagged:
        print("| 파일 | 줄 | 내용 |\n|---|---|---|")
        for rel, no, text in untagged:
            print(f"| {rel} | {no} | {text.replace('|', '/')} |")
    else:
        print("없음")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
