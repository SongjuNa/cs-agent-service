"""언어 모델 호출 계층 (CLAUDE.md 규칙 2, 기술 명세서 v1.4 §3, 에이전트 설계서 v1.1 4-2절).

모든 호출은 generate_json 하나를 지난다.
- 지시문 파일(prompts/)의 {자리}를 채우기 전에 모든 값을 prepare_llm_input으로 가린다.
- JSON 스키마를 지정해 받고(구조화 출력), 코드에서 스키마를 한 번 더 검사한다.
- 1회 30초. 시간 초과(LLM_TIMEOUT)나 스키마 위반(LLM_INVALID_OUTPUT)이면 1회 다시 부른다.
- 서버 로그에는 호출 이름, 지시문 버전, 넣은 항목 이름, 결과 종류만 남긴다. 본문은 남기지 않는다.
- 시도마다 Transport의 on_call(있을 때만)에 알린다. 실행 로그(FR-036)가 호출 수·토큰을 단계에 붙인다.

실제로 보내는 일은 Transport가 한다. 시험은 정해진 응답을 내는 대역 Transport를 넣는다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.config import REPO_ROOT
from app.llm.inputs import prepare_llm_input
from app.pipeline.runlog import LlmCall, RunLog

log = logging.getLogger(__name__)

PROMPTS_DIR = REPO_ROOT / "prompts"
TIMEOUT_SEC = 30  # 기술 명세서 §2-4
MAX_ATTEMPTS = 2  # 처음 1회 + 다시 1회 (§3-2, 에이전트 설계서 4-2절 1·2번)
# 모델이 답하기 전 생각하는 단계의 길이. 기본값이면 호출이 30초 상한에 자주 걸려 "low"로 둔다(구현 선택)
THINKING_LEVEL = "low"


class LlmError(Exception):
    """두 번 모두 실패. error_type은 기술 명세서 §6-5의 오류 종류."""

    def __init__(self, error_type: str, message: str = ""):
        super().__init__(message or error_type)
        self.error_type = error_type


class LlmTimeout(Exception):
    """Transport가 시간 상한을 넘겼을 때 낸다."""


class Transport(Protocol):
    def send(self, prompt: str, schema: dict) -> str:
        """지시문을 보내고 응답 글(JSON 문자열)을 돌려준다. 시간 초과면 LlmTimeout."""


class GeminiTransport:
    """Gemini 호출 (기술 명세서 §1-2, §3-5). 모델 이름은 LLM_MODEL_SMALL."""

    def __init__(self, api_key: str, model: str, timeout_sec: int = TIMEOUT_SEC):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_sec * 1000),
        )
        self.model = model
        self.last_usage: tuple[int | None, int | None] | None = None  # (입력, 출력) 토큰. 실행 로그용(§3-5)

    def send(self, prompt: str, schema: dict) -> str:
        import httpx

        from google.genai import errors

        config = self._types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
            thinking_config=self._types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        )
        self.last_usage = None
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except httpx.TimeoutException as exc:
            raise LlmTimeout(str(exc)) from exc
        except errors.ServerError as exc:
            # 30초 상한을 서버가 지키면 504 DEADLINE_EXCEEDED로 돌아온다. 이것도 시간 초과다
            if exc.code == 504:
                raise LlmTimeout(str(exc)) from exc
            raise
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            self.last_usage = (usage.prompt_token_count, usage.candidates_token_count)
        return response.text or ""


class RecordingTransport:
    """Transport를 감싸 호출마다 실행 로그(RunLog)에 남긴다(FR-036 처리 2, §3-5). 보내는 일은 안쪽 Transport가 한다."""

    def __init__(self, inner: Transport, log: RunLog):
        self.inner = inner
        self.log = log

    def on_call(self, call_name: str, prompt_version: str, prompt: str) -> None:
        self.log.calls.append(LlmCall(call_name, prompt_version, prompt))

    def send(self, prompt: str, schema: dict) -> str:
        record = self.log.calls[-1] if self.log.calls and self.log.calls[-1].prompt == prompt else None
        try:
            raw = self.inner.send(prompt, schema)
        finally:
            usage = getattr(self.inner, "last_usage", None)
            if record is not None and usage:
                record.input_tokens, record.output_tokens = usage
        if record is not None:
            record.response = raw
        return raw

    def __getattr__(self, name: str) -> Any:  # 모델 이름 등은 안쪽 것을 쓴다
        return getattr(self.inner, name)


@dataclass(frozen=True)
class LlmResult:
    data: dict[str, Any]
    prompt_version: str
    field_names: list[str] = field(default_factory=list)
    mask_count: int = 0
    attempts: int = 1


_SLOT = re.compile(r"\{([a-z_]+)\}")


def load_prompt(prompt_file: str) -> str:
    return (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")


def fill_prompt(template: str, values: dict[str, Any]) -> str:
    """{자리}를 한 번에 채운다. 채운 값 안의 중괄호는 다시 채우지 않는다."""

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            raise KeyError(f"지시문 자리 {{{key}}}에 넣을 값이 없다")
        return str(values[key])

    return _SLOT.sub(repl, template)


def generate_json(
    transport: Transport,
    call_name: str,
    prompt_file: str,
    fields: dict[str, Any],
    schema: dict,
    check_schema: dict | None = None,
) -> LlmResult:
    """지시문을 채워 보내고 스키마에 맞는 JSON을 돌려준다. 두 번 실패하면 LlmError.

    check_schema: 코드에서 검사할 스키마가 보낸 스키마와 다를 때(예: L2는 코드북 밖 항목을
    응답 전체 실패로 보지 않고 그 항목만 버린다). 없으면 schema로 검사한다.
    """
    prepared = prepare_llm_input(fields)  # MaskingError는 그대로 올라간다(VALIDATION)
    prompt = fill_prompt(load_prompt(prompt_file), prepared.fields)
    version = Path(prompt_file).stem

    last_type = "UNKNOWN"
    notify = getattr(transport, "on_call", None)  # 실행 로그(FR-036 처리 2): 시도마다 알린다
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if notify:
                notify(call_name, version, prompt)
            raw = transport.send(prompt, schema)
            data = json.loads(raw)
            problems = validate(data, check_schema or schema)
            if problems:
                raise _Invalid("; ".join(problems[:3]))
        except LlmTimeout:
            last_type = "LLM_TIMEOUT"
        except (json.JSONDecodeError, _Invalid):
            last_type = "LLM_INVALID_OUTPUT"
        except Exception:  # 네트워크·서버 오류 등
            log.exception("llm call=%s version=%s attempt=%d error", call_name, version, attempt)
            last_type = "UNKNOWN"
        else:
            log.info(
                "llm call=%s version=%s fields=%s attempt=%d result=OK",
                call_name, version, ",".join(prepared.field_names), attempt,
            )
            return LlmResult(data, version, prepared.field_names, prepared.mask_count, attempt)
        log.warning(
            "llm call=%s version=%s fields=%s attempt=%d result=%s",
            call_name, version, ",".join(prepared.field_names), attempt, last_type,
        )
    raise LlmError(last_type, f"{call_name}: {MAX_ATTEMPTS}회 실패({last_type})")


class _Invalid(Exception):
    pass


# --- 스키마 검사 (지시문 스키마가 쓰는 범위만: type, enum, properties, required, items, minItems) ---
_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def validate(value: Any, schema: dict, path: str = "$") -> list[str]:
    """스키마를 어긴 곳 목록을 돌려준다. 비어 있으면 통과."""
    problems: list[str] = []
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        ok = any(
            isinstance(value, _TYPES[n]) and not (n in ("integer", "number") and isinstance(value, bool))
            for n in names
        )
        if not ok:
            return [f"{path}: 형식이 {names}가 아님"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: 열거값 밖 {value!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}.{key}: 없음")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                problems += validate(value[key], sub, f"{path}.{key}")
    if isinstance(value, list) and len(value) < schema.get("minItems", 0):
        problems.append(f"{path}: 항목이 {schema['minItems']}개 미만")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            problems += validate(item, schema["items"], f"{path}[{i}]")
    return problems


def default_transport() -> GeminiTransport:
    """환경 변수의 키와 소형 등급 모델로 Transport를 만든다."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.gemini_api_key:
        raise LlmError("UNKNOWN", "GEMINI_API_KEY가 없다")
    return GeminiTransport(settings.gemini_api_key, settings.llm_model_small)
