"""SCR-05 시험 통화 만들기 (FR-050 AC-050-1~3). 운영진 데이터에 녹음이 없어 대본을 기계 음성(espeak-ng)으로 읽혀 만든다.

만드는 파일 (e2e/calls/out/, 커밋하지 않음):
- clear.wav   상담원·고객이 번갈아 말하는 영어 통화(약 3분). 고객이 제조번호 LVB-2024-00117을 불러 준다
- garbled.wav 같은 통화에서 가운데 20초를 잡음으로 덮은 것(제조번호 줄은 덮지 않음)

필요한 것: espeak-ng, ffmpeg. 쓰는 법: python3 e2e/calls/make_calls.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
RATE = 16000
PAUSE = 0.7  # 말 사이 쉼(초)
VOICE = {"AGENT": ("en-us+m3", 160), "CUSTOMER": ("en-gb+f2", 150)}

# CSV1-000017(차단기 단자 과열, 현장 정지)을 바탕으로 쓴 대본. 고객 말에 제조번호와 오류 코드가 있다
SCRIPT = [
    ("AGENT", "Thank you for calling customer support. My name is Emma. How can I help you today?"),
    ("CUSTOMER", "Hello Emma. This is Daniel from the maintenance team at our substation. We have a serious problem with one of your air circuit breakers."),
    ("AGENT", "I am sorry to hear that, Daniel. Let us sort it out together. Which product is it?"),
    ("CUSTOMER", "It is the two thousand amp air circuit breaker. The ordering code on the label is A C B dash A S dash two thousand."),
    ("AGENT", "Thank you. And what exactly is happening with the breaker?"),
    ("CUSTOMER", "The terminals are overheating. Our technician saw dark discoloration on the terminal connections this morning."),
    ("AGENT", "Is the breaker still in service right now?"),
    ("CUSTOMER", "No. It got so hot that we had to switch it off. Part of the site is down until we fix it."),
    ("AGENT", "Understood. That sounds urgent. Has anyone been hurt, or was there any smoke or fire?"),
    ("CUSTOMER", "No one was hurt and there was no smoke. We isolated it as soon as we saw the heat."),
    ("AGENT", "Good. That was the right thing to do. Does the trip unit display show any message?"),
    ("CUSTOMER", "Yes. The display showed error code E seventeen before we switched it off."),
    ("AGENT", "Error code E seventeen. Thank you. How long has this breaker been installed?"),
    ("CUSTOMER", "About two years. It was installed when the substation was extended."),
    ("AGENT", "And what is the normal load on this breaker?"),
    ("CUSTOMER", "Usually around fifteen hundred amps during the day, and less at night."),
    ("AGENT", "Thank you. To check the warranty and the production batch I need the serial number from the name plate."),
    ("CUSTOMER", "Sure, I have it here. The serial number is L V B, two zero two four, zero zero one one seven."),
    ("AGENT", "Let me read that back. L V B, two zero two four, zero zero one one seven. Is that correct?"),
    ("CUSTOMER", "Yes, that is correct."),
    ("AGENT", "Do you also have records of the load current or the temperature before the problem?"),
    ("CUSTOMER", "We log the load current every minute. I can send the trend file by email."),
    ("AGENT", "That would be very helpful. Please also send photos of the terminals and the name plate."),
    ("CUSTOMER", "I will send everything within the hour."),
    ("AGENT", "Thank you, Daniel. I will pass this to our technical team now, and we will contact you as soon as possible."),
    ("CUSTOMER", "Thank you very much, Emma. Goodbye."),
]
SERIAL_TURN = 17  # 0부터 센 제조번호 줄. 잡음은 이 줄을 덮지 않는다
GARBLE_SEC = 20.0


def say(text: str, speaker: str, path: Path) -> None:
    voice, speed = VOICE[speaker]
    subprocess.run(["espeak-ng", "-v", voice, "-s", str(speed), "-w", str(path), text], check=True)


def pcm(path: Path) -> bytes:
    """어떤 wav든 16kHz 16비트 모노로 바꿔 소리 바이트만"""
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


def write(path: Path, data: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    silence = b"\x00\x00" * int(PAUSE * RATE)
    parts, marks, t = [], [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (speaker, text) in enumerate(SCRIPT):
            f = Path(tmp) / f"{i}.wav"
            say(text, speaker, f)
            data = pcm(f)
            sec = len(data) / 2 / RATE
            marks.append({"no": i + 1, "speaker": speaker, "start_sec": round(t, 2), "end_sec": round(t + sec, 2), "text": text})
            parts += [data, silence]
            t += sec + PAUSE
    clear = b"".join(parts)
    write(OUT / "clear.wav", clear)

    # 가운데 20초를 잡음으로: 제조번호 줄보다 앞, 통화 가운데쯤에서 시작
    start = min(t / 2 - GARBLE_SEC / 2, marks[SERIAL_TURN]["start_sec"] - GARBLE_SEC - 1)
    start = max(start, 5.0)
    noise = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            f"anoisesrc=color=brown:amplitude=0.6:duration={GARBLE_SEC}:sample_rate={RATE}",
                            "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"], check=True, capture_output=True).stdout
    a = int(start * RATE) * 2
    garbled = clear[:a] + noise + clear[a + len(noise):]
    write(OUT / "garbled.wav", garbled)
    meta = {"duration_sec": round(t, 1), "garbled": {"start_sec": round(start, 1), "end_sec": round(start + GARBLE_SEC, 1)},
            "serial": "LVB-2024-00117", "turns": marks}
    (OUT / "calls.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("duration_sec", "garbled")}))


if __name__ == "__main__":
    sys.exit(main())
