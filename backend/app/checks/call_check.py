"""통화 받아쓰기의 코드 확인 두 가지 (FR-050 처리 2·5, 기술 명세서 v1.4.1 §12-4). 언어 모델을 쓰지 않는다.

① 받아쓰지 못한 구간: 녹음 처음·발화 사이·끝의 빈 시간이 10초를 넘는 곳과 [inaudible] 발화.
② 값 대조: 메모의 Provided 값이 받아쓴 글(가리기 전)에 있는가.
둘 다 막지 않고 표시만 한다.
"""

from __future__ import annotations

import re

from app.llm.call_note import INAUDIBLE, ProvidedValue, Utterance

GAP_SEC = 10.0  # 빈 시간 기준 (§12-4 확인 ①, 제안값)
NOT_FOUND = "받아쓴 글에서 찾지 못함"  # FR-050 처리 5


def find_gaps(utterances: list[Utterance], duration_sec: float, gap_sec: float = GAP_SEC) -> list[dict]:
    """받아쓰지 못한 구간 목록. reason: NO_SPEECH(빈 시간) / INAUDIBLE(알아들을 수 없음)."""
    gaps: list[dict] = []

    def add(start: float, end: float, reason: str) -> None:
        gaps.append({"start_sec": round(start, 1), "end_sec": round(end, 1), "reason": reason})

    covered = 0.0  # 지금까지 발화가 덮은 가장 늦은 시각
    for u in sorted(utterances, key=lambda x: (x.start_sec, x.end_sec)):
        start = min(max(u.start_sec, 0.0), duration_sec)
        end = min(max(u.end_sec, start), duration_sec)
        if start - covered > gap_sec:
            add(covered, start, "NO_SPEECH")
        if INAUDIBLE in u.text.lower():
            add(start, end, "INAUDIBLE")
        covered = max(covered, end)
    if duration_sec - covered > gap_sec:
        add(covered, duration_sec, "NO_SPEECH")
    return sorted(gaps, key=lambda g: g["start_sec"])


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()  # 대소문자·공백 차이는 무시 (구현 선택 C-178)


def check_provided(provided: list[ProvidedValue], utterances: list[Utterance]) -> list[ProvidedValue]:
    """값마다 found를 채운다. 가리킨 발화에서 먼저 찾고, 없으면 받아쓴 글 전체에서 찾는다."""
    by_no = {u.no: u.text for u in utterances}
    whole = _plain(" ".join(by_no.values()))
    for p in provided:
        value = _plain(p.value)
        here = _plain(by_no.get(p.utterance_no, "")) if p.utterance_no is not None else ""
        p.found = bool(value) and (value in here or value in whole)
    return provided
