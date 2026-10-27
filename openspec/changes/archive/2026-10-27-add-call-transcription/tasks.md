# Tasks: 통화 받아쓰기와 통화 메모 초안

## 1. 범위 문구

- [x] 1.1 명세서 FR-050·기능 목록, 기술 명세서 §12 범위의 "동결 전에는 만들지 않음"과 CLAUDE.md·openspec/config.yaml의 "현재 범위"를 조장 결정(2026-10-27)으로 고침

## 2. 서버

- [x] 2.1 `client.py` 음성 보내기·시간 상한, `config.py`·`.env.example` 모델 이름 (design 결정 1)
- [x] 2.2 지시문 `l9_transcribe_v1.md`, `l10_call_note_v1.md`와 `llm/call_note.py` (design 결정 2·4)
- [x] 2.3 `checks/call_check.py` 받아쓰지 못한 구간·값 대조 (design 결정 3·5)
- [x] 2.4 `api/calls.py`, `main.py`, `deps.py`, `pyproject.toml` (design 결정 6)

## 3. 화면

- [x] 3.1 접수 시뮬레이터 "통화 녹음" 칸 (design 결정 7)

## 4. 시험

- [x] 4.1 `tests/acceptance/test_call_transcription.py` AC-050-1~6
- [x] 4.2 `pytest` 전체 실행, `npm run build`
