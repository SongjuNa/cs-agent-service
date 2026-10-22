"""개인정보 가리기 (FR-038, 기술 명세서 v1.4 §7).

이메일 주소와 전화번호 꼴을 규칙(정규식)으로 가린다. 언어 모델은 쓰지 않는다.
원문은 바꾸지 않고 가린 새 글을 돌려준다. 원문은 DB에만 저장한다(가-7).

순서: 제외 목록 보호 → 가리기(이메일 → 전화 (가) → (나) → (다)) → 복원 (design 결정 2).
"""

from __future__ import annotations

import re
from typing import Any

MASKED_EMAIL = "user***@***.masked"
MASKED_PHONE = "*******"


class MaskingError(Exception):
    """가리기 검사 오류. 오류 종류는 실행 로그의 VALIDATION(기술 명세서 §6-5)."""

    kind = "VALIDATION"


# --- 제외 목록 (먼저 보호, 가리지 않음. 기술 명세서 §7) ---
_PROTECT = [
    # 날짜 꼴 YYYY-MM-DD, YYYY/MM/DD (뒤에 HH:MM[:SS]가 붙으면 한 덩어리)
    re.compile(r"(?<![0-9])[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}(?:[ T][0-9]{2}:[0-9]{2}(?::[0-9]{2})?)?(?![0-9])"),
    # 이미 가려진 값: user…@***.masked, COMPANY_…, …_AGENT_nn, **MASKED**
    re.compile(r"[A-Za-z0-9._%+-]+@\*\*\*\.masked"),
    re.compile(r"\bCOMPANY_[0-9_]+\b"),
    re.compile(r"\b[A-Z0-9_]+_AGENT_[0-9]+\b"),
    re.compile(r"\*\*MASKED\*\*"),
    # 규격 번호: 규격 기관 이름 바로 뒤의 숫자 묶음 (예 IEC 62271-200. 데이터 확인, design 결정 2)
    re.compile(r"\b(?:IEC|EN|UL|IEEE|ISO|ANSI|CSA|KS)\s?[0-9][0-9-]*(?:/[0-9-]+)*\b"),
    # 영문이 섞인 토큰: 제조번호 LVB-2024-00117, 에러 코드 E.OC, 제품 코드 SWGR-MV-12kV
    re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9./-]*[A-Za-z])(?=[A-Za-z0-9./-]*[0-9])[A-Za-z0-9][A-Za-z0-9./-]*(?<![./-])"),
    # 펌웨어 버전 꼴 숫자.숫자(.숫자…). 묶음은 1~3자리, 최대 4묶음 (firmware_history.csv 값 꼴: 1.2, 2.31).
    # 묶음이 4자리 이상이면 버전이 아니라 점으로 이은 전화번호(규칙 (나))일 수 있다
    re.compile(r"(?<![0-9.])[0-9]{1,3}(?:\.[0-9]{1,3}){1,3}(?![0-9.])"),
    # 금액·수량: 천 단위 쉼표가 든 수
    re.compile(r"(?<![0-9])[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?(?![0-9])"),
]

# --- 가리기 규칙 (기술 명세서 §7 검사식 표) ---
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# (가) +로 시작, 숫자·공백·-·.·괄호 묶음
_PHONE_A = re.compile(r"\+[0-9][0-9 ().-]*[0-9]")
# (나) 숫자 묶음이 구분 기호(공백, -, ., 괄호)로 이어진 것. 앞의 여는 괄호도 묶음에 넣는다
_PHONE_B = re.compile(r"(?<![A-Za-z0-9+])\(?[0-9][0-9 ().-]*[0-9](?![A-Za-z0-9])")
# (다) 구분 기호 없이 0으로 시작하는 10~11자리
_PHONE_C = re.compile(r"(?<![A-Za-z0-9.-])0[0-9]{9,10}(?![A-Za-z0-9.-])")

_HOLE = "\x00{}\x00"
_HOLE_RE = re.compile("\x00([0-9]+)\x00")


def _digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def mask_text(text: str) -> tuple[str, int]:
    """글 하나를 가린다. (가린 글, 가린 곳 수)를 돌려준다. 원문은 바꾸지 않는다."""
    if not isinstance(text, str):
        raise MaskingError(f"문자열이 아님: {type(text).__name__}")
    try:
        return _mask(text)
    except MaskingError:
        raise
    except Exception as exc:  # 규칙 오류 → VALIDATION (기술 명세서 §7 검사 오류)
        raise MaskingError(f"가리기 검사 실패: {exc}") from exc


def _mask(text: str) -> tuple[str, int]:
    holes: list[str] = []
    count = 0

    def protect(m: re.Match) -> str:
        holes.append(m.group(0))
        return _HOLE.format(len(holes) - 1)

    # 1. 보호 (이메일 꼴은 보호 전에 먼저 가려야 영문 토큰 규칙에 먹히지 않는다)
    def on_email(m: re.Match) -> str:
        nonlocal count
        if m.group(0).endswith("@***.masked"):
            return m.group(0)
        count += 1
        return MASKED_EMAIL

    out = _EMAIL.sub(on_email, text)
    for pattern in _PROTECT:
        out = pattern.sub(protect, out)

    # 2. 전화번호 가리기
    def on_phone_a(m: re.Match) -> str:
        nonlocal count
        if _digits(m.group(0)) >= 8:
            count += 1
            return MASKED_PHONE
        return m.group(0)

    out = _PHONE_A.sub(on_phone_a, out)

    def on_phone_b(m: re.Match) -> str:
        nonlocal count
        s = m.group(0)
        if _digits(s) >= 8 and re.search(r"[0-9][ ().-]+[0-9]", s):
            count += 1
            return MASKED_PHONE
        return s

    out = _PHONE_B.sub(on_phone_b, out)

    def on_phone_c(m: re.Match) -> str:
        nonlocal count
        count += 1
        return MASKED_PHONE

    out = _PHONE_C.sub(on_phone_c, out)

    # 3. 복원
    out = _HOLE_RE.sub(lambda m: holes[int(m.group(1))], out)
    return out, count


def mask_fields(fields: Any) -> tuple[Any, int]:
    """JSON 꼴 값(사전·목록·문자열·숫자)의 모든 문자열을 가린다. (가린 값, 가린 곳 수 합)."""
    if isinstance(fields, str):
        return mask_text(fields)
    if isinstance(fields, dict):
        total = 0
        out: dict[Any, Any] = {}
        for key, value in fields.items():
            masked, n = mask_fields(value)
            out[key] = masked
            total += n
        return out, total
    if isinstance(fields, (list, tuple)):
        total = 0
        items = []
        for value in fields:
            masked, n = mask_fields(value)
            items.append(masked)
            total += n
        return (items if isinstance(fields, list) else tuple(items)), total
    return fields, 0
