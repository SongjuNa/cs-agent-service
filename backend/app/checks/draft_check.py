"""초안 자체 대조 Q11 (FR-021 처리 5, 기술 명세서 v1.4 §3-4, 에이전트 설계서 v1.1 6-1절). 언어 모델을 쓰지 않는다.

1. 인용 검사: 본문의 (DOC_ID §절)이 모두 근거 후보 안에 있어야 한다.
2. 숫자 검사: 본문의 숫자와 날짜가 모두 허용 목록 안에 있어야 한다.
   허용 목록 = 조회값 + 제공 항목 값(수량·버전·날짜) + 인용 절 번호 + 근거 절 본문의 숫자.
   날짜(2025-10-28, 28/10/2025, 28.10.2025)는 연·월·일을 함께 비교한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

CITATION = re.compile(r"\(\s*([A-Z]{2,4}-[A-Za-z0-9_.-]+?)\s*§\s*(Q?[0-9]+(?:\.[0-9]+)*)\s*\)")

# 아라비아(٠-٩)·페르시아(۰-۹) 숫자와 아랍 소수점(٫)·천 단위(٬)를 ASCII로
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
# 숫자 하나: 천 단위 묶음(쉼표·점·공백류)이나 소수부가 붙을 수 있다. 영문자·숫자·하이픈에 붙은 것은 제외
NUMBER = re.compile(
    r"(?<![A-Za-z0-9_\-.])"
    r"[0-9]+(?:[,.   ][0-9]{3})*(?:[.,][0-9]+)?"
    r"(?![A-Za-z0-9_\-])"
)
# 날짜: 연-월-일, 또는 일/월/연·월/일/연(점·빗금)
DATE_YMD = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?![0-9])")
DATE_DMY = re.compile(r"(?<![0-9.])([0-9]{1,2})[./]([0-9]{1,2})[./]([0-9]{4})(?![0-9])")
# 펌웨어 버전 앞의 v(예: v3.40)는 떼고 숫자로 읽는다
VERSION_PREFIX = re.compile(r"(?<![A-Za-z0-9_\-])[vV](?=[0-9])")


@dataclass
class CheckResult:
    passed: bool
    bad_citations: list[str] = field(default_factory=list)
    bad_numbers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"passed": self.passed, "bad_citations": self.bad_citations, "bad_numbers": self.bad_numbers}


def normalize_digits(text: str) -> str:
    return text.translate(_DIGITS)


def citations(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in CITATION.finditer(normalize_digits(text))]


def number_values(token: str) -> set[Decimal]:
    """숫자 글자 하나를 가능한 값들로 읽는다. 쉼표·점을 소수점으로 보는 해석과 천 단위로 보는 해석을 모두 낸다."""
    t = re.sub(r"[   ]", "", token)
    readings = {t.replace(",", ""), t.replace(".", "").replace(",", "."), t.replace(",", ".")}
    if t.count(".") > 1:
        readings.add(t.replace(".", ""))
    values = set()
    for r in readings:
        try:
            values.add(Decimal(r).normalize())
        except InvalidOperation:
            continue
    return values


def _date_values(m: re.Match, ymd: bool) -> set[tuple[int, int, int]]:
    a, b, c = (int(g) for g in m.groups())
    if ymd:
        return {(a, b, c)}
    return {(c, b, a), (c, a, b)}  # 일/월/연과 월/일/연을 둘 다 본다


def dates(text: str) -> list[tuple[str, set[tuple[int, int, int]]]]:
    """본문의 날짜 글자와 가능한 (연, 월, 일) 값들. 인용 표시 안은 뺀다."""
    plain = CITATION.sub(" ", normalize_digits(text))
    found = [(m.group(0), _date_values(m, True)) for m in DATE_YMD.finditer(plain)]
    plain = DATE_YMD.sub(" ", plain)
    return found + [(m.group(0), _date_values(m, False)) for m in DATE_DMY.finditer(plain)]


def numbers(text: str) -> list[str]:
    """본문의 숫자 글자들. 인용 표시와 날짜 안의 숫자는 빼고 센다."""
    plain = CITATION.sub(" ", normalize_digits(text))
    plain = DATE_DMY.sub(" ", DATE_YMD.sub(" ", plain))
    plain = VERSION_PREFIX.sub(" ", plain)  # "v3.40" → "3.40"
    return [m.group(0).strip() for m in NUMBER.finditer(plain)]


def allowed_values(texts: list[str]) -> set[Decimal]:
    allowed: set[Decimal] = set()
    for text in texts:
        for token in numbers(text):
            allowed |= number_values(token)
        for _, section in citations(text):
            allowed |= number_values(section.lstrip("Q"))
        for _, values in dates(text):  # 날짜의 연·월·일도 숫자로 허용
            allowed |= {Decimal(n) for ymd in values for n in ymd}
    return allowed


def allowed_dates(texts: list[str]) -> set[tuple[int, int, int]]:
    return {ymd for text in texts for _, values in dates(text) for ymd in values}


def check_draft(
    body: str,
    candidate_sections: set[tuple[str, str]],
    allowed_texts: list[str],
) -> CheckResult:
    """candidate_sections = {(doc_id, section_no)}, allowed_texts = 조회값·제공 항목 값·근거 절 본문 글."""
    bad_cites = [f"({d} §{s})" for d, s in citations(body) if (d, s) not in candidate_sections]
    allowed = allowed_values(allowed_texts)
    for doc_id, section in candidate_sections:  # 인용 절 번호
        allowed |= number_values(section.lstrip("Q"))
    bad_nums = [tok for tok in numbers(body) if not (number_values(tok) & allowed)]
    ok_dates = allowed_dates(allowed_texts)
    bad_nums += [tok for tok, values in dates(body) if not (values & ok_dates)]
    return CheckResult(passed=not bad_cites and not bad_nums, bad_citations=bad_cites, bad_numbers=bad_nums)


def same_citations_and_numbers(original: str, gloss: str) -> bool:
    """대역 검사(§3-2 L7): 원문과 대역의 인용 집합과 숫자 값 집합이 같은가."""
    def num_set(text: str) -> set[frozenset]:
        return {frozenset(number_values(t)) for t in numbers(text)} | {frozenset(v) for _, v in dates(text)}

    return set(citations(original)) == set(citations(gloss)) and num_set(original) == num_set(gloss)
