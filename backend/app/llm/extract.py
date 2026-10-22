"""L2 제공 항목 추출 (FR-008, 기술 명세서 v1.4 §3-2, 에이전트 설계서 v1.1 4-4절).

본문에서 고객이 이미 준 항목을 {항목, 원문 값, 정리 값, 위치}로 받고, 코드로 다시 정리·검사한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.llm.client import LlmError, Transport, generate_json
from app.pipeline.state import ProvidedField

PROMPT_FILE = "l2_extract_v1.md"

FLAG_FORMAT = "형식 확인"
FLAG_CONFLICT = "값 충돌"
FLAG_EXTRACT_FAILED = "추출 실패"
FLAG_PRODUCT_UNCONFIRMED = "제품 미확정"

# 값 정리 규칙을 적용할 항목 (info_field_codebook.csv 라벨 기준, FR-008 처리 3)
FW_FIELDS = {"current_fw"}
DATE_FIELDS = {"required_date", "install_date"}
INT_FIELDS = {"quantity"}

_FW = re.compile(r"[0-9]+(?:\.[0-9]+)*")
_FW_PREFIX = re.compile(r"^(?:version|ver\.?|v)\s*", re.IGNORECASE)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def build_schema(field_codes: list[str]) -> dict:
    """보내는 스키마: field는 코드북 열거형(§3-2)."""
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": field_codes},
                        "value_raw": {"type": "string"},
                        "value_norm": {"type": "string"},
                        "span": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["field", "value_raw", "value_norm", "span"],
                },
            }
        },
        "required": ["fields"],
    }


# 코드 검사 스키마: 코드북 밖 항목은 응답 전체 실패가 아니라 그 항목만 버린다(FR-008 처리 2)
CHECK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value_raw": {"type": "string"},
                    "value_norm": {"type": ["string", "null"]},
                    "span": {"type": ["array", "null"], "items": {"type": "integer"}},
                },
                "required": ["field", "value_raw"],
            },
        }
    },
    "required": ["fields"],
}


@dataclass
class Extraction:
    provided_fields: list[ProvidedField] = field(default_factory=list)
    product_code: str | None = None  # 본문에서 찾아 ref.product와 맞춘 제품 코드
    error_code: str | None = None
    current_fw: str | None = None
    return_reason: str | None = None
    flags: list[str] = field(default_factory=list)
    field_names: list[str] = field(default_factory=list)
    prompt_version: str | None = None


def _key(code: str) -> str:
    return re.sub(r"\s+", "", code).lower()


def normalize_fw(value: str) -> str | None:
    """숫자와 점만, 끝 0 보존("v3.40" → "3.40"). 그렇게 못 만들면 None(FR-008 예외 3행 "v3.4a")."""
    text = _FW_PREFIX.sub("", value.strip())
    return text if _FW.fullmatch(text) else None


def normalize_date(value: str) -> str | None:
    text = value.strip()
    if not _DATE.fullmatch(text):
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def normalize_int(value: str) -> str | None:
    text = value.strip()
    return str(int(text)) if re.fullmatch(r"[0-9]+", text) else None


def clean_fields(
    raw_fields: list[dict],
    body_masked: str,
    field_codes: set[str],
    product_codes: list[str],
) -> tuple[list[ProvidedField], list[str]]:
    """코드북 밖 항목 버리기, 값 정리, 위치 확인 (FR-008 처리 2·3, 에이전트 설계서 4-4 코드 검사)."""
    by_key = {_key(code): code for code in product_codes}
    out: list[ProvidedField] = []
    flags: list[str] = []
    for item in raw_fields:
        name = item["field"]
        if name not in field_codes:
            continue
        raw = item["value_raw"]
        norm = item.get("value_norm")
        source = norm if norm not in (None, "") else raw
        if name in FW_FIELDS:
            norm = normalize_fw(source)
        elif name in DATE_FIELDS:
            norm = normalize_date(source)
        elif name in INT_FIELDS:
            norm = normalize_int(source)
        elif name == "product_model":
            norm = by_key.get(_key(source), source)
        else:
            norm = source
        if norm is None and f"{FLAG_FORMAT}({name})" not in flags:
            flags.append(f"{FLAG_FORMAT}({name})")

        span = item.get("span")
        if not (isinstance(span, list) and len(span) == 2 and 0 <= span[0] < span[1] <= len(body_masked)
                and body_masked[span[0]:span[1]] == raw):
            span = None
        out.append(ProvidedField(field=name, value_raw=raw, value_norm=norm,
                                 span=tuple(span) if span else None))

    # 같은 항목에 값이 둘 이상 (FR-008 예외 2행): 둘 다 두고 표시
    seen: dict[str, set[str]] = {}
    for pf in out:
        seen.setdefault(pf.field, set()).add(pf.value_norm or pf.value_raw)
    for name, values in seen.items():
        if len(values) > 1:
            flags.append(f"{FLAG_CONFLICT}({name})")
    return out, flags


def _first(fields: list[ProvidedField], name: str) -> str | None:
    for pf in fields:
        if pf.field == name and pf.value_norm:
            return pf.value_norm
    return None


def extract(
    transport: Transport,
    body_masked: str,
    evidence_sentences: list[str],
    info_fields: list[tuple[str, str]],
    required_fields: list[str],
    product_family: str | None,
    category_code: str | None,
    input_product_code: str | None,
    product_codes: list[str],
) -> Extraction:
    """L2를 부르고 정리한다. 두 번 실패하면 빈 목록 + "추출 실패"로 계속한다(FR-008 예외 4행)."""
    codes = [code for code, _ in info_fields]
    fields = {
        "info_field_codebook": "\n".join(f"- {code}: {label}" for code, label in info_fields),
        "product_family": product_family or "unknown",
        "category_code": category_code or "unknown",
        "required_fields": ", ".join(required_fields) if required_fields else "(none)",
        "evidence_sentences": "\n".join(f"- {s}" for s in evidence_sentences) or "(none)",
        "body_masked": body_masked,
    }
    try:
        result = generate_json(transport, "L2", PROMPT_FILE, fields, build_schema(codes), CHECK_SCHEMA)
    except LlmError:
        return Extraction(flags=[FLAG_EXTRACT_FAILED], field_names=list(fields),
                          prompt_version=PROMPT_FILE.removesuffix(".md"))

    provided, flags = clean_fields(result.data["fields"], body_masked, set(codes), product_codes)
    ext = Extraction(provided_fields=provided, flags=flags,
                     field_names=result.field_names, prompt_version=result.prompt_version)

    # 따로 복사 (FR-008 처리 5)
    ext.error_code = _first(provided, "error_code")
    ext.current_fw = _first(provided, "current_fw")
    ext.return_reason = _first(provided, "return_reason")

    # 제품 코드 보완 (FR-008 처리 4, 예외 2행: 입력값 우선)
    known = set(product_codes)
    models = [pf.value_norm for pf in provided if pf.field == "product_model" and pf.value_norm in known]
    if input_product_code:
        if models and any(m != input_product_code for m in models):
            if f"{FLAG_CONFLICT}(product_model)" not in ext.flags:
                ext.flags.append(f"{FLAG_CONFLICT}(product_model)")
    elif models:
        ext.product_code = models[0]
    elif any(pf.field == "product_model" for pf in provided):
        ext.flags.append(FLAG_PRODUCT_UNCONFIRMED)
    return ext
