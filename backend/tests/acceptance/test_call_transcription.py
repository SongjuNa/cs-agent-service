"""통화 받아쓰기와 통화 메모 초안 완료 기준 (FR-050 AC-050-1~6, 변경 add-call-transcription).

운영진 데이터에 녹음이 없어(FR-050 완료 기준 머리말) 녹음은 코드로 만든 무음 WAV이고, 받아쓰기 L9와 메모 초안 L10은
대역 Transport가 미리 정한 응답을 낸다(구현 선택 C-183). 실제 Gemini 시험은 키와 CALL_TEST_AUDIO(팀이 녹음한
시험 통화)가 있을 때만 돈다.
"""

from __future__ import annotations

import io
import json
import logging
import os
import wave
from contextlib import nullcontext
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clients, get_conn, get_connect
from app.checks.call_check import NOT_FOUND
from app.config import get_settings
from app.llm.client import LlmTimeout, transcribe_transport
from app.llm.call_note import transcribe
from app.main import app
from tests.acceptance.test_drafts import (  # noqa: F401  (index 픽스처를 함께 쓴다)
    L2_DEFECT, FakeTransport, WordCountEmbedder, index, l1,
)
from tests.acceptance.test_ticket_detail import INFO_REPLY, defect_l1, gold_input

L10_START = "You write a short English call note"


def wav(seconds: float, rate: int = 8000) -> bytes:
    """무음 WAV (16비트 모노)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def utt(speaker, start, end, text):
    return {"speaker": speaker, "start_sec": start, "end_sec": end, "text": text}


class CallFake:
    """L9(send_audio)와 L10(send) 대역. 받은 지시문과 음성 크기를 남긴다."""

    def __init__(self, l9=None, l10=None):
        self.l9 = l9 if isinstance(l9, list) else [l9]
        self.l10 = l10 if isinstance(l10, list) else [l10]
        self.prompts: list[tuple[str, str]] = []
        self.audio_sizes: list[int] = []

    @staticmethod
    def _next(q):
        reply = q.pop(0) if len(q) > 1 else q[0]
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply, ensure_ascii=False)

    def send_audio(self, prompt, audio, mime_type, schema):
        self.prompts.append(("L9", prompt))
        self.audio_sizes.append(len(audio))
        return self._next(self.l9)

    def send(self, prompt, schema):
        assert prompt.startswith(L10_START), prompt[:60]
        self.prompts.append(("L10", prompt))
        return self._next(self.l10)

    def prompt(self, call):
        return [p for c, p in self.prompts if c == call]


class Clients:
    def __init__(self):
        self.call: CallFake | None = None
        self.fake: FakeTransport | None = None  # 접수 뒤 처리 흐름용

    def transcriber(self):
        return self.call

    def transport(self):
        return self.fake or self.call

    def embedder(self):
        return WordCountEmbedder()


@pytest.fixture
def api(conn, index):
    clients = Clients()

    def shared_conn():
        yield conn

    app.dependency_overrides[get_conn] = shared_conn
    app.dependency_overrides[get_connect] = lambda: (lambda: nullcontext(conn))
    app.dependency_overrides[get_clients] = lambda: clients
    with conn.transaction(force_rollback=True):
        yield TestClient(app), clients, conn
    app.dependency_overrides.clear()


NOTE_EMPTY = {"summary_en": "Customer asks about a breaker.", "urgency": "NONE", "provided": []}


def upload(api, l9, l10=NOTE_EMPTY, seconds=180.0, **form):
    client, clients, _ = api
    clients.call = CallFake({"utterances": l9} if not isinstance(l9, Exception) else l9, l10)
    data = {"customer_id": "CUST-0001", "language": "en", **form}
    return client.post("/calls/transcribe", data=data, files={"file": ("call.wav", wav(seconds), "audio/wav")})


def counts(conn):
    return tuple(conn.execute(f"SELECT count(*) FROM svc.{t}").fetchone()[0]
                 for t in ("ticket", "ticket_message", "agent_run"))


# CSV1-000017 대본(차단기 과열, 영어). 상담원·고객이 번갈아 말하고 빈 시간은 10초 이하다
SCRIPT_017 = [
    utt("AGENT", 0.5, 8.0, "LS Electric support, this is Mina. How can I help you?"),
    utt("CUSTOMER", 9.0, 30.0, "Hi, our air circuit breaker keeps tripping and the terminal feels hot."),
    utt("AGENT", 31.0, 45.0, "I'm sorry to hear that. Which model is it?"),
    utt("CUSTOMER", 46.0, 70.0, "It is the ACB-AS-2000 in our main panel."),
    utt("AGENT", 72.0, 95.0, "Could you read me the serial number on the nameplate?"),
    utt("CUSTOMER", 97.0, 120.0, "The serial is LVB-2024-00117."),
    utt("AGENT", 121.0, 150.0, "Thank you. Is the plant stopped right now?"),
    utt("CUSTOMER", 151.0, 172.0, "No, we are running on the backup feeder."),
    utt("AGENT", 173.0, 179.5, "Understood. We will get back to you shortly."),
]


# --- AC-050-1 ---


def test_ac_050_1_two_speakers_no_gaps(api):
    res = upload(api, SCRIPT_017)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["duration_sec"] == 180.0
    assert [u["no"] for u in body["utterances"]] == list(range(1, len(SCRIPT_017) + 1))
    assert {u["speaker"] for u in body["utterances"]} == {"AGENT", "CUSTOMER"}
    assert all(u["start_sec"] is not None for u in body["utterances"])
    assert body["utterances"][0]["start_sec"] <= 10 and body["utterances"][-1]["end_sec"] >= 170
    assert body["gaps"] == []
    assert api[1].call.audio_sizes == [len(wav(180.0))]  # 녹음 전체를 한 번에 보냄


# --- AC-050-2 ---


@pytest.mark.parametrize("middle, reason", [
    ([utt("CUSTOMER", 80.0, 100.0, "[inaudible]")], "INAUDIBLE"),  # 모델이 표시를 남긴 경우
    ([], "NO_SPEECH"),  # 모델이 아무것도 적지 않은 경우
])
def test_ac_050_2_inaudible_part_marked(api, middle, reason):
    script = [utt("AGENT", 0.5, 40.0, "How can I help you?"), utt("CUSTOMER", 41.0, 79.0, "The breaker trips."),
              *middle, utt("AGENT", 101.0, 140.0, "Could you repeat that?"),
              utt("CUSTOMER", 141.0, 179.0, "Yes, it trips every hour.")]
    body = upload(api, script).json()
    assert body["gaps"] == [{"start_sec": 79.0 if reason == "NO_SPEECH" else 80.0,
                             "end_sec": 101.0 if reason == "NO_SPEECH" else 100.0, "reason": reason}]
    in_gap = [u for u in body["utterances"] if 79 < u["start_sec"] < 101]
    assert [u["text"] for u in in_gap] == (["[inaudible]"] if middle else [])  # 지어낸 글이 없다


# --- AC-050-3 ---


def test_ac_050_3_spoken_serial_in_note(api):
    note = {"summary_en": "ACB-AS-2000 trips and the terminal is hot", "urgency": "NONE",
            "provided": [{"field_code": "serial_no", "value": "LVB-2024-00117", "utterance_no": 6},
                         {"field_code": "product_model", "value": "ACB-AS-2000", "utterance_no": 4}]}
    body = upload(api, SCRIPT_017, note).json()
    assert "Serial number (nameplate)=LVB-2024-00117" in body["note_en"]
    assert body["note_en"].startswith("[Call note] ACB-AS-2000 trips and the terminal is hot.")
    serial = next(p for p in body["provided"] if p["field_code"] == "serial_no")
    assert serial["found"] is True and serial["message"] is None
    assert "LVB-2024-00117" in api[1].call.prompt("L10")[0]  # 가리기가 일련번호를 지우지 않음


# --- AC-050-4 ---


def test_ac_050_4_value_not_in_transcript(api):
    client, clients, _ = api
    clients.call = CallFake(None, {"summary_en": "Breaker trips.", "urgency": "NONE",
                                   "provided": [{"field_code": "serial_no", "value": "LVB-2024-99999",
                                                 "utterance_no": 6}]})
    utterances = [dict(u, no=i) for i, u in enumerate(SCRIPT_017, start=1)]
    res = client.post("/calls/note-draft", json={"utterances": utterances, "language": "en"})
    assert res.status_code == 200, res.text
    [value] = res.json()["provided"]
    assert value["found"] is False and value["message"] == NOT_FOUND == "받아쓴 글에서 찾지 못함"


# --- AC-050-5 ---


def test_ac_050_5_contact_masked_before_l10(api, caplog):
    phone, email = "+49 151 2345 6789", "hans.mueller@example.de"
    script = [utt("AGENT", 0.5, 9.0, "May I have a phone number and email for the follow-up?"),
              utt("CUSTOMER", 10.0, 25.0, f"Sure, my number is {phone} and my email is {email}."),
              utt("AGENT", 26.0, 35.0, "Thank you.")]
    with caplog.at_level(logging.DEBUG):
        body = upload(api, script, seconds=40.0).json()
    [prompt] = api[1].call.prompt("L10")
    assert phone not in prompt and email not in prompt
    assert body["mask_count"] >= 2
    logged = "\n".join(r.getMessage() for r in caplog.records)  # 접수 전이라 실행 기록 대신 서버 로그(T47)
    assert phone not in logged and email not in logged
    assert phone in body["utterances"][1]["text"]  # 화면에는 원래 받아쓴 글


# --- AC-050-6 ---


def test_ac_050_6_intake_with_confirmed_note(api):
    client, clients, conn = api
    before = counts(conn)
    note = {"summary_en": "ACB-AS-2000 trips and the terminal is hot", "urgency": "NONE",
            "provided": [{"field_code": "serial_no", "value": "LVB-2024-00117", "utterance_no": 6}]}
    body = upload(api, SCRIPT_017, note).json()
    client.post("/calls/note-draft", json={"utterances": body["utterances"], "language": "en"})
    assert counts(conn) == before  # [접수] 전에는 아무것도 생기지 않는다(D36)

    confirmed = body["note_en"] + " Checked by agent."
    data = gold_input(conn, "CSV1-000017") | {"channel": "PHONE", "inquiry_body": confirmed}
    clients.fake = FakeTransport(L1=[defect_l1()], L2=[L2_DEFECT], L3=[INFO_REPLY],
                                 L7=[{"gloss": "명판의 제조번호를 보내 주세요."}])
    res = client.post("/tickets", json=data)
    assert res.status_code == 201, res.text
    ticket_id = res.json()["ticket_id"]
    row = conn.execute("SELECT channel, inquiry_body FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone()
    assert row == ("PHONE", confirmed)
    assert clients.fake.count("L1") >= 1  # 처리 흐름이 FR-001과 같이 시작됨
    assert counts(conn)[0] == before[0] + 1


# --- 예외 (FR-050 예외 표) ---


def test_bad_audio_rejected(api):
    client, clients, _ = api
    clients.call = CallFake({"utterances": []}, NOTE_EMPTY)
    res = client.post("/calls/transcribe", data={"customer_id": "CUST-0001", "language": "en"},
                      files={"file": ("call.m4a", b"not audio", "audio/mp4")})
    assert res.status_code == 400 and res.json()["detail"]["message"] == "받을 수 없는 녹음 파일"
    assert clients.call.prompts == []


def test_unknown_customer_rejected(api):
    res = upload(api, SCRIPT_017, customer_id="NOPE")
    assert res.status_code == 400
    assert res.json()["detail"]["errors"][0]["field"] == "customer_id"


def test_transcribe_failure_and_empty(api):
    assert upload(api, LlmTimeout("t")).status_code == 502
    body = upload(api, []).json()
    assert body["note_en"] is None and body["note_error"] == "받아쓴 내용 없음"
    assert api[1].call.prompt("L10") == []


def test_note_failure_keeps_transcript(api):
    body = upload(api, SCRIPT_017, LlmTimeout("t")).json()
    assert body["note_en"] is None and body["note_error"] == "메모 초안 실패"
    assert len(body["utterances"]) == len(SCRIPT_017)


# --- 실제 Gemini (키와 팀 시험 녹음이 있을 때만) ---


@pytest.mark.skipif(not (get_settings().gemini_api_key and os.environ.get("CALL_TEST_AUDIO")),
                    reason="키 또는 CALL_TEST_AUDIO(팀이 녹음한 시험 통화)가 없어 건너뜀")
def test_ac_050_1_live():
    path = Path(os.environ["CALL_TEST_AUDIO"])
    mime = {".wav": "audio/wav", ".mp3": "audio/mp3", ".flac": "audio/flac", ".ogg": "audio/ogg"}[path.suffix.lower()]
    transcript = transcribe(transcribe_transport(), path.read_bytes(), mime, "en")
    assert {u.speaker for u in transcript.utterances} == {"AGENT", "CUSTOMER"}
