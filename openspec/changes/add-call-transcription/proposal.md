# Proposal: 통화 받아쓰기와 통화 메모 초안 (add-call-transcription)

## Why

운영진 데이터의 전화 문의 591건은 모두 상담원이 통화 뒤 영어로 쓴 요약("[Call note] …")이고, 그중 268건(45.3%)이 추가 정보 요청으로 이어졌다(근거: 명세서 v1.5.1 FR-050 근거, tickets.csv channel·info_request_sent). 사람이 요약하며 값을 빠뜨린 예도 있다(근거: FR-050 근거, 기술 명세서 §12-1). AI가 통화 녹음 전체를 빠짐없이 받아쓰고 운영진 데이터와 같은 형식의 메모 초안을 만들어, 상담원이 확인한 메모를 지금의 접수로 넣는다(근거: FR-050 기능 설명, §12 T45 확정). 조장이 2026-10-27에 "동결 전에 만들지 않는 것이 아니라 지금 당장 만든다"고 정했다(근거: 조장 결정 2026-10-27, 개발_결정_기록.md에 적음). 그래서 문서의 범위 문구도 함께 고친다.

## What Changes

- **받아쓰기 L9 (FR-050 처리 1)**: 녹음 파일 하나를 언어 모델 호출 계층에서 Gemini에 보내 발화 목록(말한 사람 AGENT/CUSTOMER, 시작·끝 초, 내용)을 받는다. 요약하지 않고, 숫자는 숫자로, 알아들을 수 없으면 지어내지 않고 표시한다(근거: FR-050 처리 1, §12-3 L9 지시문 원칙). 녹음은 가리지 못한 채 보내고, 지시문의 글 칸은 지금처럼 가린다(근거: D35 확정, CLAUDE.md 규칙 2 예외). 시간 상한 120초(근거: §12-3 시간 상한).
- **받아쓰지 못한 구간 확인 (FR-050 처리 2)**: 녹음 처음·발화 사이·끝의 10초 넘는 빈 시간과 알아들을 수 없음 발화를 모아 표시만 한다(근거: FR-050 처리 2, §12-4 확인 ①).
- **메모 초안 L10 (FR-050 처리 3·4)**: 가린 받아쓴 글로 영어 메모를 만든다. 형식 "[Call note] … Urgency: … Provided: 라벨=값; …", 항목 라벨은 info_field_codebook.csv 32개(근거: FR-050 처리 4, §12-3 L10).
- **값 대조 (FR-050 처리 5)**: Provided 값이 받아쓴 글에 있는지 문자열로 확인하고, 없으면 "받아쓴 글에서 찾지 못함"을 표시한다(근거: FR-050 처리 5, §12-4 확인 ②).
- **API**: `POST /calls/transcribe`(녹음 → 받아쓰기·확인·메모 초안), `POST /calls/note-draft`(메모 다시 만들기). DB에 쓰지 않는다(근거: §12-5, D36).
- **화면**: 접수 시뮬레이터에서 채널 PHONE을 고르면 [통화 녹음 올리기]. 받아쓴 글·받아쓰지 못한 구간·메모 초안·대조 결과를 보이고, 메모를 본문 칸에 넣은 뒤 기존 [접수]를 누른다(근거: FR-050 처리 6·7, §12-5 화면).
- **범위 문구**: FR-050과 §12의 "동결 전에는 만들지 않는다", openspec/config.yaml과 CLAUDE.md의 현재 범위에 FR-050을 더한다(근거: 조장 결정 2026-10-27).

## Capabilities

### New Capabilities
- `call-transcription`: 통화 녹음 받아쓰기, 받아쓰지 못한 구간 표시, 영어 통화 메모 초안과 값 대조, 접수 시뮬레이터의 녹음 올리기.

## 범위 밖

- **녹음 나누기**: 이번에는 녹음을 나누지 않고 15분을 넘는 파일은 받지 않는다(근거: FR-050 예외 1행 "길이 상한을 넘음 → 받아쓰지 않음"). T46 결정 전 진행 방식(조각 10분)과 다르므로 구현 선택 C-179로 팀 확인에 올린다.
- **전화 시스템 연동**: 녹음은 상담원이 올린다(근거: FR-050 입력 표 아래, FR-037 제외).
- **받아쓴 글·녹음 저장**: 저장하지 않는다(근거: D36 결정 전 진행 방식).
- **L9·L10 실행 로그(agent_run)**: 접수 전이라 남기지 않고 응답에 사용량만 준다(근거: §12-7 T47 결정 전).
- **통화 중 체크리스트·실시간 제안(②·③ 단계)**(근거: §12 머리말).
- **실제 녹음 시험**: 운영진 데이터에 녹음이 없고 팀이 녹음한 시험 통화는 아직 없다. 시험은 대역 Transport로 하고, 실제 Gemini 시험은 키와 시험 녹음이 있을 때만 돈다(근거: FR-050 완료 기준 머리말, D37).

## Impact

- 새 파일: `prompts/l9_transcribe_v1.md`, `prompts/l10_call_note_v1.md`, `backend/app/llm/call_note.py`, `backend/app/checks/call_check.py`, `backend/app/api/calls.py`, 시험 `backend/tests/acceptance/test_call_transcription.py`(근거: design 결정 1~6).
- 고치는 파일: `backend/app/llm/client.py`(음성 보내기·시간 상한), `backend/app/api/deps.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/pyproject.toml`(python-multipart, mutagen), `.env.example`, `frontend/src/IntakePage.tsx`·`api.ts`·`styles.css`, 범위 문구(CLAUDE.md, openspec/config.yaml, 명세서 FR-050, 기술 명세서 §12)(근거: design 결정 1~7).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4, D36).
