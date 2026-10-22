# Design: 문의 이해

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 명세서 v1.5 FR-004, 005, 007, 008의 처리, 예외, 완료 기준.
- 기술 명세서 v1.4: §2-2(T1·T2·Q1 행), §2-3(상태 객체), §2-4(시간 상한), §3-1~3-3(호출·스키마·지시문 원칙), §3-5(모델), §3-6(확신도 기준).
- 에이전트 설계서 v1.1: 4-2(공통 규칙), 4-3(L1), 4-4(L2), 7-1(예외), 7-2(시작값).
- 팀 정답지 작성 기준서(머리 제목 v0.1, 상태 줄 v0.3 확정): 1-1장 유형 정의, 2장 긴급도 판단 기준, 6장 결정 K4. 프로젝트 업로드 파일 41d8707c…와 팀 정답지 v1 묶음 안의 같은 문서.
- 4번 변경의 `app/llm/inputs.py`의 `prepare_llm_input`, 3번 변경의 `app/rules/`.

## Goals / Non-Goals

**Goals**
- 접수 입력 한 건을 받아 SubTicketState 1개가 들어 있는 TicketState를 만든다. category_code, urgency_flag, provided_fields, product_code, error_code, current_fw를 채운다(근거: 기술 명세서 §2-3).
- 언어 모델 호출은 한 곳에서만 한다(근거: CLAUDE.md 규칙 2).

**Non-Goals**
- DB 저장, 규칙 엔진 연결(Q2 뒤), 그래프 엔진, 화면(proposal "범위 밖").

## Decisions

### 1. 언어 모델 호출 계층 (`app/llm/client.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 라이브러리 | Google 공식 `google-genai` | 기술 명세서 §1-2(Gemini). 라이브러리 이름은 구현 선택 |
| 호출 모양 | `generate_json(transport, call_name, prompt_file, fields, schema, check_schema=None) -> LlmResult`. 응답 MIME `application/json`과 JSON 스키마를 지정하고, 코드에서 스키마를 한 번 더 검사한다 | 기술 명세서 §3-2. 함수 모양은 구현 선택 |
| 입력 가리기 | 지시문의 {자리}에 넣을 값 묶음 전체를 `generate_json` 안에서 `prepare_llm_input`에 통과시키고, 가린 값으로 지시문을 채운다 | CLAUDE.md 규칙 2, 기술 명세서 §7 |
| 시간 상한·재시도 | 1회 30초. 시간 초과는 LLM_TIMEOUT, JSON이 아니거나 스키마·열거값을 어기면 LLM_INVALID_OUTPUT. 두 경우 모두 1회 다시 부르고, 그래도 실패하면 `LlmError(error_type)`를 낸다 | 기술 명세서 §2-4, §3-2, §6-5 오류 종류, 에이전트 설계서 7-2 |
| 모델 | `LLM_MODEL_SMALL`(기본 `gemini-3.8-flash`). L1·L2는 소형 등급 | 기술 명세서 §1-5, §3-1, §3-5 |
| 시험용 바꿔 끼우기 | 실제로 보내는 일은 `Transport`(send 하나)가 하고 Gemini용은 `GeminiTransport`다. 처리 함수는 Transport를 인자로 받는다. 실패 AC(AC-004-3, AC-005-3)는 정해진 응답 글을 내는 대역 Transport로 시험해, 재시도와 스키마 검사까지 실제 코드로 돈다 | AC-004-3 "판정 도구가 실패하는 상태", AC-005-3 "코드값 밖 응답을 두 번". 방식은 구현 선택 |
| 서버 로그 | 호출마다 호출 이름, 지시문 버전, 넣은 항목 이름, 결과 종류를 서버 로그에 남긴다. 본문은 남기지 않는다 | 기술 명세서 §3-3 "입력 항목 이름 목록", 실행 로그 FR-036은 2순위라 서버 로그(프로젝트 구조 1순위 판 4장) |

### 2. 지시문 파일 (`prompts/`)

- `l1_understand_v1.md`, `l2_extract_v1.md`: 에이전트 설계서 4-3, 4-4절의 영어 지시문 초안을 글자 그대로 쓴다. `{중괄호}`는 코드가 채운다(근거: 에이전트 설계서 4-2절 8번).
- `l1_category_definitions_v1.md`: 기준서 v0.3 1-1장 표를 그대로 옮긴다. 팀 정답지 번호(GS-0xx)는 언어 모델에 의미가 없어 뺀다(구현 선택). 원본이 한국어이므로 한국어 그대로 넣는다(근거: 에이전트 설계서 4-2절 4번 "원본이 한국어인 표는 원본 그대로").
- `l1_urgency_criteria_v1.md`: 기준서 2장의 판단 표를 옮긴다(GS 번호와 예시 열은 뺌). 표 밖에 있는 6장 K4 결정(단자 과열·변색 = SAFETY)을 SAFETY 행에 넣고, 통화 메모 행의 "위 기준과 다르면 [결정 필요 K4]"는 "위 기준을 따른다"로 바꾼다(근거: 기준서 6장 K4, 명세서 FR-007 처리 1·AC-007-1. CSV1-000017 본문에 "Urgency: SITE_DOWN"이 그대로 있어 표만 옮기면 SAFETY가 나오지 않는다. 문장을 바꾼 것은 구현 선택이며 결정 기록에 남긴다). 6값 설명은 ref.urgency.description에서 읽어 판단 표 앞에 붙여 `{urgency_codebook}` 자리에 넣는다(근거: 기술 명세서 §3-1 L1 입력. 한 자리에 함께 넣는 것은 구현 선택).
- 지시문 버전(파일 이름의 v1)을 서버 로그에 남긴다(근거: 기술 명세서 §3-3).

### 3. L1 결과 검사 (`app/llm/understand.py`)

| 검사 | 동작 | 근거 |
|---|---|---|
| 스키마 | body_language(15개), category_code(10종), urgency_flag(6값)는 열거형 | 기술 명세서 §3-2 |
| 같은 유형 두 번 | 하나로 합치고 근거 문장을 이어 붙인다 | §3-2, 에이전트 설계서 4-3 |
| 요청이 둘 이상 | 1순위는 첫 요청(seq 1)의 유형·근거 문장·검색문만 하위 문의로 쓰고 "복합 문의 가능(FR-006, 2순위)"을 표시한다 | config.yaml "하위 문의 1개". 첫 요청을 고르는 것과 표시 방식은 구현 선택 |
| 긴급도 순서 | 같은 유형을 합칠 때와, 요청이 둘 이상일 때 모두 우선순서로 가장 높은 긴급도와 그 근거를 하위 문의에 쓴다 | FR-007 처리 3, §3-2. 다른 요청의 긴급도까지 보는 것은 안전 놓침(대표 지표 ③)을 막기 위한 구현 선택 |
| 확신도 | body_language_confidence < 0.6 → body_language = language + "언어 판정 불확실". category_confidence < 0.6 → "확신 낮음" | §3-6, FR-004 처리 3, FR-005 처리 4 |
| 두 번 실패 | 열거값 밖 응답 두 번(LLM_INVALID_OUTPUT) → category_code None + "분류 실패", urgency_flag NONE + "긴급도 판정 실패", body_language = language + "언어 판정 불확실". 흐름은 L2로 계속 | FR-004 예외·AC-004-3, FR-005 처리 3·AC-005-3, FR-007 처리 4 |
| 시간 초과·오류 두 번 | 실행 FAILED, 오류 종류 LLM_TIMEOUT 등, 화면 문구 "자동 처리 실패. 다시 시도" | FR-005 예외 2행, 기술 명세서 §2-2 T2, 에이전트 설계서 7-1 |

두 번 실패의 처리는 명세서가 갈래를 둘로 나눈다: "코드값 밖 응답"은 비우고 계속, "LLM 실패(시간 초과, 오류)"는 실행 FAILED. 기술 명세서 §2-2 T2는 "1회 재시도 → run FAILED"만 적었다. 그래서 오류 종류로 나눈다: LLM_INVALID_OUTPUT은 비우고 계속, 그 밖은 FAILED(명세서 FR-005 예외 표의 두 행을 따름).

### 4. L2 결과 검사 (`app/llm/extract.py`)

| 검사 | 동작 | 근거 |
|---|---|---|
| 항목 이름 | ref.info_field 32개 밖이면 그 항목만 버린다 | FR-008 처리 2, §3-2 |
| 펌웨어 버전 (current_fw) | 앞의 "v", "ver", "version"만 떼고, 남은 글이 숫자와 점만이면 그대로 둔다(끝 0 보존, "v3.40" → "3.40"). 아니면("v3.4a") 정리 값을 비우고 "형식 확인" | FR-008 처리 3·예외 3행, §3-2. 뗄 글자 범위는 구현 선택 |
| 날짜 (required_date, install_date) | L2의 정리 값이 YYYY-MM-DD 꼴의 실제 날짜가 아니면 정리 값을 비우고 "형식 확인" | FR-008 처리 3 |
| 수량 (quantity) | 정수로 읽을 수 없으면 정리 값을 비우고 "형식 확인" | FR-008 처리 3 |
| 제품 코드 (product_model) | ref.product의 product_code와 대소문자·공백 무시로 같으면 그 표기로 통일 | FR-008 처리 3. 대조 방식은 구현 선택 |
| 코드북 밖 항목 | 보내는 스키마는 field를 32개 열거형으로 막고, 코드 검사 스키마는 field를 글자로만 받아 밖의 항목만 버린다(응답 전체를 실패로 보지 않음) | FR-008 처리 2, §3-2 |
| 위치 (span) | 가린 본문의 그 위치 글자가 value_raw와 다르면 span만 비운다 | 에이전트 설계서 4-4 코드 검사, §3-2 "span은 가린 본문 기준" |
| 같은 항목에 값 둘 | 둘 다 두고 "값 충돌" 표시. 제품 코드면 입력값 우선 | FR-008 예외 2행 |
| 제품 코드 보완 | 입력 product_code가 비어 있고 product_model 값이 ref.product에 있으면 채운다. product_model은 있는데 대조에 실패하면 "제품 미확정" | FR-008 처리 4 |
| 따로 복사 | error_code → error_code_reported, current_fw → fw_version_reported | FR-008 처리 5, 테이블 정의서 sub_ticket 열 |
| 실패 | 빈 목록 + "추출 실패", 흐름 계속 | FR-008 예외 4행 |

정리 규칙을 적용할 항목(current_fw, required_date, install_date, quantity)은 info_field_codebook.csv 라벨을 보고 골랐다(구현 선택. 값 형식 규칙 자체는 FR-008 처리 3). install_date는 기준서 v0.3 3장대로 예정일도 받는다.

### 5. 처리 흐름 앞부분 (`app/pipeline/`)

- `state.py`: 기술 명세서 §2-3의 SubTicketState, TicketState를 Pydantic 모델로 옮긴다. 이번 변경이 쓰지 않는 필드도 이름과 형식은 그대로 둔다(뒤 변경이 채움).
- `understand.py`: `understand_ticket(conn, llm, ticket_input) -> UnderstandOutcome`.
  1. T1: 본문을 `prepare_llm_input`으로 가려 body_masked를 만든다. `MaskingError`면 언어 모델을 부르지 않고 실행 FAILED(VALIDATION)(근거: §2-2 T1, §7).
  2. product_code가 있으면 `rules.lookup_product`로 product_family를 구한다(L1 입력, 근거: §3-1 L1 "product_family(있으면)").
  3. T2: L1.
  4. Q1: L2. 필수 항목은 `rules.check_required_info`의 required_info로 구한다(근거: §3-1 L2 입력 "그 제품군×유형의 필수 항목").
  5. L2가 product_code를 채우면 product_family를 다시 구한다(구현 선택. FR-008 처리 4가 채운 코드를 뒤 단계가 쓰게 하기 위함).
- 결과 `UnderstandOutcome`은 상태 객체, 실행 상태(SUCCESS/FAILED, schema.sql agent_run.status 값), 오류 종류, 화면 문구를 담는다(구현 선택. 값 이름은 schema.sql·§6-5).
- 입력 사전에 제목(inquiry_subject)이 있어도 읽지 않고 버린다(근거: §2-3 "TicketState에 넣지 않는다").
- pipeline은 rules와 llm을 둘 다 부를 수 있다. rules가 llm을 부르지 않는 규칙(CLAUDE.md 규칙 1)은 3번 변경 시험이 계속 확인한다.

### 6. 시험

- 언어 모델을 실제로 부르는 시험(AC-004-1·2, 005-1·2, 007-1~3, 008-1~4)은 `GEMINI_API_KEY`가 있을 때만 돈다. 없으면 "키 없음"을 이유로 건너뛰었다고 표시한다(구현 선택).
- 대역 Transport로 하는 시험: AC-004-3, AC-005-3, 시간 초과 두 번이면 FAILED, 그리고 AC-005-2의 "보낸 글에 제목 없음"(대역이 받은 지시문을 확인)과 L2 정리 규칙.
- 시험 입력은 gold.v_inputs에서 읽는다(서비스와 같은 입력 열). AC-005-2만 제목 문자열을 gold.ticket_gold.inquiry_subject에서 읽어 입력에 일부러 넣는다. 제목은 정답 열이 아니고 시험 코드이므로 CLAUDE.md 규칙 6에 걸리지 않는다. 기대값은 명세서 AC에 적힌 값이다.

## Risks / Trade-offs

- 언어 모델 결과는 매번 조금씩 다를 수 있다. 시험이 한 번 실패하면 같은 입력을 다시 돌려 보고, 계속 틀리면 지시문 문제로 기록한다(지시문 버전을 올려 고침, 에이전트 설계서 4-2절 8번).
- CSV1-000031은 명세서(MANUAL)와 기준서 정의(릴리스 노트 → FW_UPDATE)가 다르다(proposal "범위 밖").
