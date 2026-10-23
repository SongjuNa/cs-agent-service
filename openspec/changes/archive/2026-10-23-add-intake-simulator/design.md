# Design: 접수 시뮬레이터와 시연용 불러오기

## Context

- 명세서 v1.5 FR-001(AC-001-1~4), FR-003(AC-003-1~3), D25, D30.
- 기술 명세서 v1.4 §2-3, §2-4(실행 시작, 재처리), §6-1 gold 행, §7, §8-1, §8-2.
- 화면 정의서 v1 SCR-00, SCR-01, SCR-01-P1, 화면 정의서 v2 부록 B-1·B-2.
- 테이블 정의서 v1.3 / schema.sql svc.ticket, gold.v_inputs, eval.gold_set, ref.customer·product·department.

## Decisions

### 1. 접수 검증 (`app/db/store.py create_ticket`, `app/api/tickets.py`)

| 항목 | 검사 | 오류 문구 | 근거 |
|---|---|---|---|
| channel | EMAIL, CHAT, PHONE, WEB_FORM, PARTNER_PORTAL | "채널을 고르세요" (구현 선택 문구) | FR-001 입력 표, schema.sql svc.ticket CHECK |
| customer_id | ref.customer에 있음 | "고객 ID를 찾을 수 없음" | FR-001 예외 1행, AC-001-2, D25 |
| product_code | 비우면 통과, 있으면 ref.product에 있음 | "제품 코드를 찾을 수 없음(모르면 비우세요)" | FR-001 예외 2행, 화면 정의서 v1 SCR-01 ⑥ |
| language | 15개 코드 | "고객 언어를 고르세요" (구현 선택 문구) | FR-001 입력 표 |
| inquiry_body | 공백만이면 거부, 2,000자 이하 | "내용을 입력하세요"(SCR-01 ⑥), "본문은 2000자 이하여야 합니다"(구현 선택 문구) | FR-001 입력 표·예외 3행, 화면 정의서 v1 SCR-01 ⑥ |
| source | SIMULATOR·LOAD·REPLAY, LOAD·REPLAY는 원본 번호 필요 | 구현 선택 문구 | schema.sql svc.ticket source CHECK |
| received_at_utc | 비우면 지금, 미래면 거부 | "접수 시각은 미래일 수 없음" | FR-001 입력 표, SCR-01 ⑥ |

- 모든 항목을 한 번에 검사해 400과 `{"detail": {"message": 첫 오류, "errors": [{"field", "message"}]}}`를 돌려준다. 하나라도 있으면 티켓을 만들지 않는다(근거: FR-001 처리 1 "항목별 오류", 응답 모양은 구현 선택).
- 연락처 contact_name·contact_email·contact_phone은 받은 그대로 저장하고 `ticket_input`(처리 흐름 입력)에는 넣지 않는다(근거: FR-001 입력 표 가-7, schema.sql 주석 "LLM 입력·실행 로그에 넣지 않는다").
- source: source_ticket_id가 있으면 LOAD, 없으면 SIMULATOR(근거: FR-003 처리 4, schema.sql CHECK "source = 'SIMULATOR' OR source_ticket_id IS NOT NULL". 판정 방식은 구현 선택).

### 2. 선택 목록 (`backend/app/api/ref_lists.py`)

| 주소 | 돌려주는 것 | 근거 |
|---|---|---|
| `GET /ref/customers?q=` | customer_id, company_masked, country, tier. q가 있으면 ID·회사명에 부분 일치(대소문자 무시), 최대 20건, ID 순 | §8-1, 화면 정의서 v1 SCR-01-04 "ID·회사명·국가·등급". 20건은 구현 선택 |
| `GET /ref/products` | product_code, product_name (23종) | §8-1, SCR-01-05 |
| `GET /ref/departments` | dept_code, dept_name_ko, dept_name_en (13개) | §8-1, 화면 정의서 v1 SCR-00-03 |

### 3. 불러오기 (`backend/app/api/gold_inputs.py`)

- 번호 형식: 운영진 `CSV1-` + 6자리, 팀 정답지 `GS-` + 3자리(대소문자 무시). 아니면 400과 형식 안내 문구(근거: FR-003 예외 1행 형식 안내 문구에 화면 정의서 v2 부록 B-1 GS-001~GS-080. GS 형식을 더한 문구는 구현 선택).
- 운영진 번호는 `gold.v_inputs`에서 channel, customer_id, product_code, language, inquiry_body, received_at_utc만 읽는다(근거: FR-003 처리 1·3, §6-1, CLAUDE.md 규칙 6).
- 팀 번호는 `eval.gold_set`에서 같은 6열만 읽는다. 서비스 계정은 이 표의 입력 열만 읽을 수 있다(근거: §6-1 "팀이 만든 문의도 같은 모양으로", schema.sql GRANT SELECT (gold_set_id, …, received_at_utc) ON eval.gold_set). 지금은 팀 정답지(W9)가 적재되지 않아 404다(근거: C-3).
- 없으면 404 "문의를 찾을 수 없음"(근거: FR-003 예외 2행). 시각은 UTC로 돌려준다(근거: §8-1 "모든 시각은 UTC").
- data_split은 보지 않는다. 운영진 번호는 `eval.gold_set.source_ticket_id`와, 팀 번호는 늘 채점용으로 `gold_set: true`. 상세의 "채점용 문의"도 원본 번호가 gold_set_id 또는 source_ticket_id와 맞으면 켠다(근거: FR-003 처리 2, §6-1 "같은 맞대 보기").

### 4. 다시 시도 (`POST /tickets/{id}/reprocess`, `app/db/runs.py`)

- 받는 조건: 티켓이 있고(없으면 404), 처리 흐름 실행이 돌고 있지 않으며(409 "처리 중"), 마지막 처리 흐름 실행이 FAILED일 때(아니면 409 "다시 처리할 실패가 없음"). 그 밖의 다시 처리는 19번(근거: AC-001-4, §2-4 재처리, C-98. 조건과 문구는 구현 선택).
- 티켓 행을 잠그고 RETRY 실행 행을 응답 전에 연 뒤, 같은 티켓으로 처리 흐름을 백그라운드로 돌린다. 그래서 응답 직후 상세가 바로 "처리 중"이고 겹친 요청은 409다. 이전 run은 남는다(근거: AC-001-4 "같은 티켓으로", FR-036 처리 5, §6-5. 잠금은 구현 선택).
- 상세 응답의 can_retry = 위 조건을 만족함. 화면은 이 값으로 [다시 시도]를 보인다(근거: AC-001-4, 구현 선택).
- 처리 흐름 실행 판정: RETRY 중 sub_ticket_id가 비어 있는 티켓 실행도 처리 흐름으로 본다. 대역 다시 만들기·다시 검증의 RETRY는 늘 하위 문의를 가리키므로 섞이지 않는다(근거: §6-5, 이 변경 전 `messages.py` start_run, C-87 해소).
- LLM 호출 1회 재시도는 1순위 호출 계층 그대로(근거: FR-001 예외 4행 "자동 재시도 1회", §2-2 T2 "1회 재시도").

### 5. 화면 (`frontend/src/IntakePage.tsx`)

| 요소 | 내용 | 근거 |
|---|---|---|
| 주소·메뉴 | `/intake`, 사이드바 "접수 시뮬레이터" 켬. 접수함·나의 업무 현황은 흐림 그대로 | §8-2, 화면 정의서 v2 부록 B-2, 18·20번 |
| 안내 띠 | "시연·테스트 담당자용 · 채널 연동 대체" | 화면 정의서 v1 SCR-01-01 |
| 폼 | 채널(기본 EMAIL), 접수 시각은 빈 칸에 "비우면 지금"(⑥ "시각 지금"을 서버가 채움, 구현 선택), 고객(검색 선택, `GET /ref/customers?q=`), 제품 코드(23종, 비움 허용), 고객 언어(15값), 제목("처리에는 쓰지 않음"), 본문(글자 수), 접수 시각(UTC, 비우면 지금), 보낸 사람 연락처 3칸 | SCR-01-03~09, ⑥ 빈 폼, FR-001 입력 표 가-7 |
| 불러오기 | [문의 번호로 불러오기] → 팝업에서 번호 입력, [불러오기]/[닫기]. 6칸만 채우고 제목은 비움. "원본 CSV1-xxxxxx에서 불러옴" + "채점용 문의" 배지 | SCR-01-02·10, SCR-01-P1, AC-003-1 |
| 접수 | [접수] → 접수 중 버튼 비활성 → 성공이면 `/tickets/{id}`로, 실패면 칸 아래 오류와 "접수 실패: {사유}", 폼 유지. [비우기] | 화면 정의서 v1 SCR-01-11·12, ⑤ 동작, ⑥ |
| 다시 시도 | 티켓 상세 머리의 실패 문구 옆 [다시 시도] → reprocess → 다시 읽기(처리 중이면 2초마다) | AC-001-4, FR-001 예외 4행, 화면 정의서 v1 H-04·H-05. 버튼 이름은 명세서 문구 |

### 6. 시험 (`tests/acceptance/test_intake_simulator.py`)

- AC-001-1: 유효한 입력 → NEW 티켓, INQUIRY 1건, NEW 이력 1건, 처리 흐름 run(근거: AC-001-1).
- AC-001-2: 없는 고객 → 400, 항목 customer_id 오류, 티켓 없음(근거: AC-001-2).
- AC-001-3: 제목을 넣고 전문 기록을 켜면 L1 지시문에 제목이 없다(근거: AC-001-3, FR-036 처리 4).
- AC-001-4: L1이 두 번 실패 → NEW, run FAILED → reprocess → 같은 티켓, RETRY run SUCCESS, IN_PROGRESS(근거: AC-001-4).
- AC-003-1: CSV1-000017 → PHONE, CUST-0350, ACB-AS-2000, en, 본문, 2025-10-02 09:45:43, 제목·정답 열 없음(근거: AC-003-1).
- AC-003-2: CSV1-001112(test split) → 똑같이 채워짐(근거: AC-003-2).
- 그 밖: 항목별 검증(채널·언어·제품·본문·미래 시각·출처), 형식 오류·없는 번호, 팀 번호(GS-) 불러오기와 채점용 표시, 선택 목록, 연락처 저장·처리 입력 제외, LOAD 출처, 다시 시도 거절 조건(근거: FR-001 예외 표, FR-003 예외 표, §8-1).
- 화면은 `npm run build`(타입 검사)와 브라우저 확인(근거: 1순위 화면과 같은 방식, 구현 선택).

## Risks / Trade-offs

- C-97: 연락처를 FR-001 입력 표는 "LLM 입력과 실행 로그에는 가린 값만", §7·schema.sql 주석은 "넣지 않는다"로 다르게 적었다. 더 엄격한 쪽(넣지 않음)을 따른다(근거: FR-001 입력 표 가-7, §7, schema.sql svc.ticket 주석).
- C-98: 다시 시도는 실패한 티켓에만. 화면 정의서 v1은 버튼 이름이 [다시 처리](H-05), 명세서는 "다시 시도"(근거: FR-001 예외 4행, 화면 정의서 v1 H-04·H-05).
