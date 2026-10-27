# Design: 통화 받아쓰기와 통화 메모 초안

## Context

지금 언어 모델 호출 계층은 글 지시문만 보낸다. `generate_json`이 모든 글 칸을 `prepare_llm_input`으로 가린 뒤 Transport의 `send(prompt, schema)`로 보내고, 시간 상한은 30초다(근거: `backend/app/llm/client.py`, 기술 명세서 §2-4·§7). 접수는 `POST /tickets` 하나이고 채널 PHONE을 이미 받는다(근거: `backend/app/api/tickets.py`, FR-001 입력 표). 이 변경 전에는 녹음을 보내는 길과 음성 길이를 읽는 도구가 없었다. 운영진 데이터에 통화 녹음은 없다(근거: FR-050 완료 기준 머리말). Gemini 공식 문서는 요청 1회의 인라인 크기 상한을 20MB로, 지원 형식을 WAV·MP3·AIFF·AAC·OGG·FLAC로 적고, 음성 1초를 25토큰으로 센다(근거: [Gemini 음성 이해 문서](https://ai.google.dev/gemini-api/docs/audio)).

## Decisions

### 1. 음성 보내기 (`backend/app/llm/client.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 자리 | `generate_json`에 `audio=(bytes, mime_type)` 인자를 더한다. 글 칸은 지금처럼 `prepare_llm_input`으로 가리고, 음성만 그대로 Transport의 `send_audio(prompt, audio, mime_type, schema)`로 보낸다 | CLAUDE.md 규칙 2(호출은 한 곳), D35 확정, 구현 선택 C-170 |
| 서버 로그 | 지금처럼 호출 이름·지시문 버전·넣은 항목 이름·결과만. 음성 대신 크기(바이트)를, API는 녹음 길이(초)·크기를 서버 로그에 남긴다. agent_step 실행 기록은 접수 전이라 없다(T47) | D35 "음성 대신 파일 길이·크기만", §12-7 T47, 구현 선택 C-170 |
| 시간 상한 | L9 120초, L10 30초. 받아쓰기용 Transport는 `transcribe_transport()`가 120초 상한으로 만든다 | §12-3 시간 상한 |
| 재시도 | 다른 호출과 같이 1회 | §12-3, §2-4 |
| L9 모델 | 환경 변수 `LLM_MODEL_TRANSCRIBE`, 비우면 `LLM_MODEL_SMALL`(`gemini-3.8-flash`) | T46은 받아쓰기 전용 모델 후보(Gemini 3.5 Transcribe)로 시작하라고 하나, 모델 이름을 공식 문서로 확인하지 못해 기본값은 이미 확정된 소형 모델로 두고 환경 변수로 바꾸게 한다. 구현 선택 C-171(팀 확인) |

### 2. 받아쓰기 L9 (`prompts/l9_transcribe_v1.md`, `backend/app/llm/call_note.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | 녹음, 고객 언어 이름(받아쓰기 언어 힌트) | §12-3 L9 입력 |
| 출력 스키마 | `{"utterances": [{"speaker": "AGENT"/"CUSTOMER", "start_sec": number, "end_sec": number, "text": string}]}` | §12-3 L9 출력 |
| 지시문 원칙 | 요약 금지·들린 말 모두, 말한 사람 둘, 말로 부른 숫자는 숫자로, 알아들을 수 없는 부분은 `[inaudible]` 표시를 담은 발화로 남김(화면은 "알아들을 수 없음"으로 보임), 번역 금지 | FR-050 처리 1, §12-3 L9 지시문 원칙("[알아들을 수 없음]"). 지시문이 영어라 모델에게는 영어 표시 글자를 쓰게 한 것은 구현 선택 C-172 |
| 검사 | 시작 ≤ 끝, 끝 ≤ 녹음 길이 + 2초가 아닌 발화는 버리지 않고 그대로 두되 빈 구간 계산에서 시각을 녹음 길이로 자른다 | 구현 선택 C-173 |

### 3. 받아쓰지 못한 구간 (`backend/app/checks/call_check.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 빈 시간 | 발화를 시작 시각순으로 놓고 녹음 시작~첫 발화, 발화 사이(앞 발화들의 끝 중 가장 늦은 것 기준, 겹쳐 말한 발화 때문. 구현 선택 C-174), 마지막~녹음 끝의 빈 시간이 10초를 넘으면 구간 하나 | FR-050 처리 2, §12-4 확인 ① |
| 알아들을 수 없음 | 글이 `[inaudible]`을 담은 발화의 시작~끝도 구간 하나 | FR-050 처리 2 |
| 결과 | `[{"start_sec", "end_sec", "reason": "NO_SPEECH"/"INAUDIBLE"}]`. 막지 않고 표시만 | FR-050 처리 2 "막지 않고 표시만", 이유 값은 구현 선택 C-174 |
| 녹음 길이 | 파일에서 읽는다(mutagen). 못 읽으면 "받을 수 없는 녹음 파일" | FR-050 예외 1행, 도구는 구현 선택 C-175 |

### 4. 메모 초안 L10 (`prompts/l10_call_note_v1.md`, `backend/app/llm/call_note.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | 받아쓴 글을 `[n] AGENT (mm:ss): 글` 줄로 만든 것(`<customer_message>` 안), 고객 언어, 고른 제품(코드·이름), 항목 코드북 32개 | §12-3 L10 입력, CLAUDE.md 규칙 5. 줄 모양은 구현 선택 C-176 |
| 가리기 | `generate_json`이 받아쓴 글 칸을 가린다. 가린 곳 수를 응답에 준다 | FR-050 처리 3, §7, AC-050-5 |
| 출력 스키마 | `{"summary_en": string, "urgency": 긴급도 6값, "provided": [{"field_code": 코드북 32개, "value": string, "utterance_no": integer}]}` | §12-3 L10 출력(provided), urgency 값은 urgency_codebook.csv. summary와 urgency를 나눈 것은 구현 선택 C-177 |
| 메모 조립 | 코드가 `[Call note] {summary_en} Urgency: {urgency}. Provided: {라벨}={값}; …`로 붙인다. urgency가 NONE이면 Urgency 부분을 뺀다. 라벨은 info_field_codebook.csv label | FR-050 처리 4 형식, §12-3 L10 형식, 운영진 메모 모양(tickets.csv inquiry_body: urgency_flag=NONE 411건에 "Urgency:" 없음). Provided가 비면 그 부분도 뺀다. §12-3의 출력 `note_en`을 summary_en·urgency로 받고 코드가 조립하는 것은 구현 선택 C-177(팀 확인) |
| 금지 | 유형·우선순위·부서를 쓰지 않음, 받아쓴 글에 없는 값 금지(지시문) | FR-050 처리 4, 설계 원칙 2 |

### 5. 값 대조 (`backend/app/checks/call_check.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 방법 | value가 utterance_no 발화의 원래 글(가리기 전)에 있으면 FOUND. 없으면 받아쓴 글 전체에서 찾는다. 대소문자와 공백 차이는 무시 | FR-050 처리 5, §12-4 확인 ②. 대소문자·공백 무시는 구현 선택 C-178 |
| 결과 | 항목마다 `found: true/false`, 못 찾으면 화면 문구 "받아쓴 글에서 찾지 못함" | FR-050 처리 5, AC-050-4 |

### 6. API (`backend/app/api/calls.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| `POST /calls/transcribe` | multipart: file, customer_id, language, product_code(선택). 검사 → L9 → 구간 확인 → L10 → 값 대조. 녹음은 나누지 않는다(T46의 "조각 10분"은 음성을 자르는 도구가 따로 필요해 이번에는 15분 상한으로 대신함, 구현 선택 C-179, 팀 확인). 응답: duration_sec, utterances, gaps, note_en, summary_en, urgency, provided(+label, found), mask_count, usage(호출별 토큰) | §12-5, FR-050 출력, T47 결정 전("응답에 사용량만") |
| `POST /calls/note-draft` | JSON: utterances, language, product_code. L10 → 값 대조만 | §12-5 |
| 입력 검사 | customer_id는 ref.customer, product_code는 ref.product, language는 15개 코드. 실패하면 400과 항목별 오류(접수와 같은 모양) | FR-050 입력 표("FR-001과 같음"), FR-001 처리 1 |
| 녹음 검사 | 확장자·형식 wav·mp3·flac·ogg, 크기 20MB 이하, 길이 15분 이하. 아니면 400 "받을 수 없는 녹음 파일" | FR-050 예외 1행. §12-5의 제안 형식은 wav·mp3·m4a이나 m4a는 Gemini 문서 형식 목록에 없어 빼고 flac·ogg를 더함. 20MB는 Gemini 문서, 15분은 §12-3 "착수 때 다시 확인" 값 중 작은 쪽. 구현 선택 C-179(팀 확인) |
| 실패 | L9가 두 번 실패하면 502 "받아쓰기 실패", L10이 두 번 실패하면 받아쓴 글과 구간은 주고 note_en은 null, note_error "메모 초안 실패". 발화가 없으면 "받아쓴 내용 없음"이고 L10을 부르지 않음. 가리기 오류는 400 "개인정보 검사 오류" | FR-050 예외 2~5행. 상태 코드는 구현 선택 C-180 |
| 저장 | DB에 쓰지 않는다 | D36, AC-050-6 |

### 7. 화면 (`frontend/src/IntakePage.tsx`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 자리 | 채널 PHONE일 때만 본문 위에 "통화 녹음" 칸: 파일 고르기 + [받아쓰기] | §12-5 화면, FR-050 처리 6 |
| 결과 | 처리 중 "받아쓰기 중". 왼쪽 받아쓴 글(말한 사람·mm:ss, 받아쓰지 못한 구간은 빨간 줄), 오른쪽 메모 초안과 Provided 대조(찾지 못한 값 빨간 표시). 메모 초안은 본문 칸에 바로 채운다. [메모 다시 만들기], 받아쓰기 실패 때 [다시 받아쓰기]. 녹음 없이 본문을 직접 써서 접수하는 길은 그대로 | FR-050 처리 6, 예외 2행, 출력 사용자 표시, §12-5 화면 |
| 접수 | 상담원이 본문을 고친 뒤 기존 [접수]. 접수 시각이 비어 있으면 받아쓰기를 누른 시각에서 녹음 길이를 뺀 시각(통화 시작 추정)을 넣는다 | FR-050 처리 7, 입력 표 received_at "비우면 통화 시작 시각". 추정 방법은 구현 선택 C-181 |

## Risks / Trade-offs

- Gemini 음성 문서는 "영어 음성에 대해서만 응답을 추론한다"고 적는다. 영어가 아닌 고객(전화 문의 272건)의 받아쓰기 품질은 시험 녹음으로 확인해야 한다(근거: [Gemini 음성 이해 문서](https://ai.google.dev/gemini-api/docs/audio), tickets.csv language, 결정 기록 C-182로 팀 확인).
- 메모 초안의 Provided 값은 가린 받아쓴 글에서 나오므로, 전화번호처럼 가려진 값은 값 대조에서 "찾지 못함"이 된다. 막지 않고 표시만 하므로 상담원이 녹음과 대조한다(구현 선택 C-178).
- 받아쓴 일련번호가 "2024 00117"처럼 숫자만 띄어 적히면 가리기 규칙 (나)가 전화번호로 가릴 수 있다. L9 지시문은 부른 값을 한 덩어리로 적게 하고, 남는 위험은 단어로 남은 번호와 함께 실제 녹음 시험으로 확인한다(§12-6).
- 녹음 동의(D37): 시험·시연은 팀이 만든 녹음만 쓴다. 실제 고객 통화에 쓰기 전 나라별 동의 확인이 먼저다.
- 시험은 대역 Transport와 코드로 만든 무음 WAV로 한다. 실제 받아쓰기 품질은 팀이 녹음한 시험 통화가 생기면 `CALL_TEST_AUDIO` 경로로 실제 Gemini 시험을 돌린다(근거: FR-050 완료 기준 머리말, D37, 구현 선택 C-183).
