"""통화 받아쓰기 L9와 통화 메모 초안 L10 (FR-050, 기술 명세서 v1.4.1 §12-3).

- L9: 녹음을 그대로 보낸다(가릴 수 없음, D35). 글 칸(고객 언어 이름)은 generate_json이 가린다.
- L10: 받아쓴 글을 줄로 만들어 <customer_message> 안에 넣고, generate_json이 가린 뒤 보낸다(FR-050 처리 3).
- 메모는 코드가 "[Call note] … Urgency: … Provided: 라벨=값; …" 모양으로 붙인다(design 결정 4, 구현 선택 C-177).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.llm.client import AudioTransport, Transport, generate_json
from app.llm.drafts import LANGUAGE_NAMES

L9_PROMPT = "l9_transcribe_v1.md"
L10_PROMPT = "l10_call_note_v1.md"
INAUDIBLE = "[inaudible]"  # 알아들을 수 없는 부분 표시 (FR-050 처리 1, 구현 선택 C-172)
SPEAKERS = ["AGENT", "CUSTOMER"]

L9_SCHEMA = {
    "type": "object",
    "properties": {
        "utterances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": SPEAKERS},
                    "start_sec": {"type": "number"},
                    "end_sec": {"type": "number"},
                    "text": {"type": "string"},
                },
                "required": ["speaker", "start_sec", "end_sec", "text"],
            },
        }
    },
    "required": ["utterances"],
}


@dataclass
class Utterance:
    no: int  # 1부터. L10 줄 번호 [n]과 같다
    speaker: str
    start_sec: float
    end_sec: float
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"no": self.no, "speaker": self.speaker, "start_sec": self.start_sec, "end_sec": self.end_sec,
                "text": self.text}


@dataclass
class Usage:
    """접수 전 호출이라 실행 로그에 남지 않는다. 응답에 사용량만 준다(§12-7 T47)."""

    call: str
    prompt_version: str
    attempts: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class Transcript:
    utterances: list[Utterance]
    usage: Usage


@dataclass
class ProvidedValue:
    field_code: str
    label: str
    value: str
    utterance_no: int | None
    found: bool = False  # 값 대조 결과 (checks.call_check)


@dataclass
class CallNote:
    summary_en: str
    urgency: str
    provided: list[ProvidedValue]
    mask_count: int
    usage: Usage
    note_en: str = ""


def _usage(transport: Any, call: str, result) -> Usage:
    tokens = getattr(transport, "last_usage", None) or (None, None)
    return Usage(call, result.prompt_version, result.attempts, *tokens)


def mmss(seconds: float) -> str:
    s = max(int(seconds), 0)
    return f"{s // 60:02d}:{s % 60:02d}"


def transcribe(transport: AudioTransport, audio: bytes, mime_type: str, language: str) -> Transcript:
    """L9. 두 번 실패하면 LlmError를 그대로 올린다(FR-050 예외 2행)."""
    fields = {"language_name": LANGUAGE_NAMES.get(language, language)}
    result = generate_json(transport, "L9", L9_PROMPT, fields, L9_SCHEMA, audio=(audio, mime_type))
    rows = sorted(result.data["utterances"], key=lambda u: (u["start_sec"], u["end_sec"]))
    utterances = [Utterance(i, u["speaker"], float(u["start_sec"]), float(u["end_sec"]), u["text"].strip())
                  for i, u in enumerate(rows, start=1)]
    return Transcript([u for u in utterances if u.text], _usage(transport, "L9", result))


def transcript_lines(utterances: list[Utterance]) -> str:
    return "\n".join(f"[{u.no}] {u.speaker} ({mmss(u.start_sec)}): {u.text}" for u in utterances)


def l10_schema(field_codes: list[str], urgencies: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "summary_en": {"type": "string"},
            "urgency": {"type": "string", "enum": urgencies},
            "provided": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_code": {"type": "string", "enum": field_codes},
                        "value": {"type": "string"},
                        "utterance_no": {"type": "integer"},
                    },
                    "required": ["field_code", "value", "utterance_no"],
                },
            },
        },
        "required": ["summary_en", "urgency", "provided"],
    }


def draft_note(transport: Transport, utterances: list[Utterance], language: str, product: str | None,
               info_fields: list[tuple[str, str]], urgency_rows: list[tuple[str, str]]) -> CallNote:
    """L10. 두 번 실패하면 LlmError(FR-050 예외 4행: 받아쓴 글만 보인다)."""
    labels = dict(info_fields)
    fields = {
        "language_name": LANGUAGE_NAMES.get(language, language),
        "product": product or "unknown",
        "info_field_codebook": "\n".join(f"- {code}: {label}" for code, label in info_fields),
        "urgency_codebook": "\n".join(f"- {code}: {desc}" for code, desc in urgency_rows),
        "transcript": transcript_lines(utterances),
    }
    schema = l10_schema(list(labels), [code for code, _ in urgency_rows])
    result = generate_json(transport, "L10", L10_PROMPT, fields, schema)
    provided = [ProvidedValue(p["field_code"], labels[p["field_code"]], p["value"].strip(), p["utterance_no"])
                for p in result.data["provided"] if p["value"].strip()]
    note = CallNote(result.data["summary_en"].strip(), result.data["urgency"], provided, result.mask_count,
                    _usage(transport, "L10", result))
    note.note_en = compose_note(note)
    return note


def compose_note(note: CallNote) -> str:
    """운영진 메모 모양(tickets.csv inquiry_body): "[Call note] … Urgency: X. Provided: 라벨=값; …"."""
    summary = note.summary_en.rstrip()
    if summary and summary[-1] not in ".!?":
        summary += "."
    parts = [f"[Call note] {summary}"]
    if note.urgency and note.urgency != "NONE":
        parts.append(f"Urgency: {note.urgency}.")
    if note.provided:
        parts.append("Provided: " + "; ".join(f"{p.label}={p.value}" for p in note.provided) + ".")
    return " ".join(parts)
