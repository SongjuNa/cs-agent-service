"""통화 받아쓰기와 통화 메모 초안 (FR-050, 기술 명세서 v1.4.1 §12-5, design 결정 6).

DB에는 ref 표를 읽기만 하고 아무것도 쓰지 않는다(D36). 상담원이 메모를 확인한 뒤 기존 POST /tickets로 접수한다.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from psycopg import Connection
from pydantic import BaseModel

from app.api import schemas
from app.api.deps import Clients, get_clients, get_conn
from app.checks.call_check import NOT_FOUND, check_provided, find_gaps
from app.db.store import LANGUAGES, MSG_CUSTOMER, MSG_LANGUAGE, MSG_PRODUCT
from app.llm.call_note import CallNote, Usage, Utterance, draft_note, transcribe
from app.llm.client import LlmError
from app.masking import MaskingError

router = APIRouter(prefix="/calls")
log = logging.getLogger(__name__)

# 받는 녹음 (FR-050 예외 1행). 형식·20MB는 Gemini 음성 문서, m4a 제외와 15분은 구현 선택 C-179
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mp3", ".flac": "audio/flac", ".ogg": "audio/ogg"}
MAX_BYTES = 20 * 1024 * 1024
MAX_SEC = 15 * 60
MSG_BAD_AUDIO = "받을 수 없는 녹음 파일"
MSG_TRANSCRIBE_FAILED = "받아쓰기 실패"  # FR-050 예외 2행
MSG_EMPTY = "받아쓴 내용 없음"  # FR-050 예외 3행
MSG_NOTE_FAILED = "메모 초안 실패"  # FR-050 예외 4행
MSG_MASKING = "개인정보 검사 오류"  # FR-050 예외 5행


def _bad_request(errors: list[tuple[str, str]]) -> HTTPException:
    """접수(POST /tickets)와 같은 모양의 400."""
    return HTTPException(400, {"message": errors[0][1],
                               "errors": [{"field": f, "message": m} for f, m in errors]})


def _check_inputs(conn: Connection, customer_id: str | None, language: str | None,
                  product_code: str | None) -> None:
    """입력 검사는 FR-001과 같다(FR-050 입력 표). customer_id가 None이면 건너뛴다(note-draft)."""
    errors: list[tuple[str, str]] = []
    if customer_id is not None and conn.execute(
            "SELECT 1 FROM ref.customer WHERE customer_id = %s", (customer_id,)).fetchone() is None:
        errors.append(("customer_id", MSG_CUSTOMER))
    if product_code and conn.execute(
            "SELECT 1 FROM ref.product WHERE product_code = %s", (product_code,)).fetchone() is None:
        errors.append(("product_code", MSG_PRODUCT))
    if language not in LANGUAGES:
        errors.append(("language", MSG_LANGUAGE))
    if errors:
        raise _bad_request(errors)


def audio_duration(audio: bytes) -> float | None:
    """녹음 길이(초). 읽지 못하면 None (design 결정 3, 도구는 구현 선택 C-175)."""
    import mutagen  # 서버를 켤 때 꼭 필요하지 않아 여기서 읽는다

    try:
        parsed = mutagen.File(io.BytesIO(audio))
    except Exception:  # noqa: BLE001 — 깨진 파일은 모두 "받을 수 없는 녹음 파일"
        return None
    length = getattr(getattr(parsed, "info", None), "length", None)
    return float(length) if length else None


def _check_audio(filename: str | None, audio: bytes) -> tuple[str, float]:
    mime_type = AUDIO_TYPES.get(Path(filename or "").suffix.lower())
    duration = audio_duration(audio) if mime_type and 0 < len(audio) <= MAX_BYTES else None
    if duration is None or duration > MAX_SEC:
        raise _bad_request([("file", MSG_BAD_AUDIO)])
    return mime_type, duration


def _ref_context(conn: Connection, product_code: str | None):
    info_fields = [tuple(r) for r in conn.execute("SELECT field, label FROM ref.info_field ORDER BY field").fetchall()]
    urgency_rows = [tuple(r) for r in conn.execute("SELECT urgency, description FROM ref.urgency").fetchall()]
    product = None
    if product_code:
        row = conn.execute("SELECT product_name FROM ref.product WHERE product_code = %s", (product_code,)).fetchone()
        product = f"{product_code} ({row[0]})" if row else product_code
    return product, info_fields, urgency_rows


def _usage(u: Usage) -> dict[str, Any]:
    return {"call": u.call, "prompt_version": u.prompt_version, "attempts": u.attempts,
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


def _note(conn: Connection, clients: Clients, utterances: list[Utterance], language: str,
          product_code: str | None) -> dict[str, Any]:
    """L10 → 값 대조(확인 ②). L10이 두 번 실패하면 note_en은 null, note_error를 준다."""
    if not utterances:
        return {"note_en": None, "note_error": MSG_EMPTY, "summary_en": None, "urgency": None, "provided": [],
                "mask_count": 0, "usage": []}
    product, info_fields, urgency_rows = _ref_context(conn, product_code)
    try:
        note: CallNote = draft_note(clients.transport(), utterances, language, product, info_fields, urgency_rows)
    except MaskingError:
        raise HTTPException(400, {"message": MSG_MASKING}) from None
    except LlmError:
        return {"note_en": None, "note_error": MSG_NOTE_FAILED, "summary_en": None, "urgency": None,
                "provided": [], "mask_count": 0, "usage": []}
    check_provided(note.provided, utterances)
    return {
        "note_en": note.note_en,
        "note_error": None,
        "summary_en": note.summary_en,
        "urgency": note.urgency,
        "provided": [{"field_code": p.field_code, "label": p.label, "value": p.value,
                      "utterance_no": p.utterance_no, "found": p.found,
                      "message": None if p.found else NOT_FOUND} for p in note.provided],
        "mask_count": note.mask_count,
        "usage": [_usage(note.usage)],
    }


@router.post("/transcribe", response_model=schemas.CallResult, response_model_exclude_unset=True)
def transcribe_call(
    file: UploadFile = File(...),
    customer_id: str = Form(""),
    language: str = Form(""),
    product_code: str = Form(""),
    conn: Connection = Depends(get_conn),
    clients: Clients = Depends(get_clients),
) -> dict[str, Any]:
    """녹음 → L9 → 받아쓰지 못한 구간(확인 ①) → L10 → 값 대조(확인 ②). 저장하지 않는다(D36)."""
    product_code = product_code or None
    _check_inputs(conn, customer_id, language, product_code)
    audio = file.file.read(MAX_BYTES + 1)
    mime_type, duration = _check_audio(file.filename, audio)
    log.info("call audio duration_sec=%.1f bytes=%d type=%s", duration, len(audio), mime_type)  # 음성 대신 길이·크기(D35)
    try:
        transcript = transcribe(clients.transcriber(), audio, mime_type, language)
    except MaskingError:
        raise HTTPException(400, {"message": MSG_MASKING}) from None
    except LlmError:
        raise HTTPException(502, {"message": MSG_TRANSCRIBE_FAILED}) from None
    note = _note(conn, clients, transcript.utterances, language, product_code)
    return {
        "duration_sec": round(duration, 1),
        "utterances": [u.as_dict() for u in transcript.utterances],
        "gaps": find_gaps(transcript.utterances, duration),
        **note,
        "usage": [_usage(transcript.usage), *note["usage"]],
    }


class UtteranceIn(BaseModel):
    no: int
    speaker: str
    start_sec: float
    end_sec: float
    text: str


class NoteDraftIn(BaseModel):
    utterances: list[UtteranceIn]
    language: str | None = None
    product_code: str | None = None


@router.post("/note-draft", response_model=schemas.CallNote, response_model_exclude_unset=True)
def note_draft(body: NoteDraftIn, conn: Connection = Depends(get_conn),
               clients: Clients = Depends(get_clients)) -> dict[str, Any]:
    """[메모 다시 만들기]: 앞 응답의 받아쓴 글로 L10 → 값 대조만 다시 한다(§12-5)."""
    product_code = body.product_code or None
    _check_inputs(conn, None, body.language, product_code)
    utterances = [Utterance(u.no, u.speaker, u.start_sec, u.end_sec, u.text.strip())
                  for u in body.utterances if u.text.strip()]
    return _note(conn, clients, utterances, body.language, product_code)
