# Proposal: 접수 시뮬레이터와 시연용 불러오기 (add-intake-simulator)

## Why

MVP에는 메일·채팅 연동이 없으므로 시연·테스트 담당자가 화면에서 문의를 입력하거나 운영진 데이터의 문의를 불러와 접수 API를 불러야 한다(근거: 명세서 v1.5 FR-001 기능 설명, FR-003 기능 설명). 1순위는 접수 API(`POST /tickets`)만 만들었고 화면, 선택 목록 API, 불러오기 API, 항목별 검증, 다시 시도가 없다(근거: 이 변경 전 `backend/app/api/tickets.py`, `frontend/src/App.tsx` 메뉴 "접수 시뮬레이터 2순위").

## What Changes

- **접수 검증 (FR-001)**: 채널 5값, 고객 언어 15값, 고객 ID, 제품 코드, 본문 1~2,000자·공백 거부, 접수 시각(미래 거부)을 검사하고 실패하면 항목별 오류를 돌려주며 티켓을 만들지 않는다(근거: FR-001 입력 표, 처리 1, 예외 1~3행, 화면 정의서 v1 SCR-01 ⑥ 검증 오류 문구).
  - 보낸 사람 연락처(이름·이메일·전화)를 받아 ticket에 원문으로 저장한다. 처리 흐름 입력에는 넣지 않는다(근거: FR-001 입력 표 v1.5 가-7, schema.sql svc.ticket contact_name·contact_email·contact_phone, 기술 명세서 §7).
  - 제목은 저장만 하고 처리 흐름에 넣지 않는다(1순위 그대로, 시험만 더한다)(근거: FR-001 입력 표, AC-001-3, §2-3).
- **선택 목록 API**: `GET /ref/customers?q=`, `GET /ref/products`, `GET /ref/departments`(근거: 기술 명세서 §8-1 첫 행, 화면 정의서 v1 SCR-01-04·05).
- **불러오기 API (FR-003)**: `GET /gold/tickets/{source_ticket_id}`가 운영진 번호(CSV1-)는 `gold.v_inputs`에서, 팀이 만든 문의 번호(GS-)는 `eval.gold_set`의 입력 열에서 입력 열 6개를 돌려주고, 팀 정답지 문의면 `gold_set: true`를 더한다. 형식이 틀리면 400, 없으면 404 "문의를 찾을 수 없음"(근거: FR-003 처리 1~3, 예외 표, §8-1 "4,000건 전부와 팀이 만든 문의", 화면 정의서 v2 부록 B-1 "SCR-01-P1 팀 정답지 번호 형식 GS-001~GS-080", schema.sql 서비스 계정의 eval.gold_set 입력 열 권한, CLAUDE.md 규칙 6).
  - 불러온 값으로 접수하면 ticket.source = LOAD, source_ticket_id = 원본 번호를 남긴다(근거: FR-003 처리 4, schema.sql svc.ticket source CHECK).
- **다시 시도 (AC-001-4)**: `POST /tickets/{id}/reprocess`가 마지막 처리 흐름 실행이 실패한 티켓을 같은 티켓으로 새 run(RETRY)에서 다시 처리한다(근거: FR-001 예외 4행, AC-001-4, §8-1 reprocess 행, §2-4 재처리 "새 run").
  - 실행 행은 응답 전에 열고, 다시 처리가 도는 동안 상세가 "처리 중"을 보이도록 처리 흐름 실행 판정을 고친다(근거: §2-4 실행 시작 "화면이 처리 중을 보여 주고", 개발_결정_기록 C-87).
- **화면 (SCR-01 접수 시뮬레이터)**: `/intake`에 접수 폼, [문의 번호로 불러오기] 팝업(SCR-01-P1), 원본 표시와 "채점용 문의" 배지, 칸별 오류, 접수 성공 시 티켓 상세로 이동. 사이드바 메뉴를 켠다(근거: 화면 정의서 v1 SCR-01·SCR-01-P1, v2 부록 B-2 A안 사이드바, 기술 명세서 §8-2).
  - 티켓 상세 머리의 "자동 처리 실패" 옆에 [다시 시도] 버튼을 둔다. 버튼을 보일지는 서버의 다시 시도 조건과 같은 값(상세 응답 can_retry)으로 정한다(근거: FR-001 예외 4행 "다시 시도 버튼", AC-001-4. can_retry는 구현 선택).

## Capabilities

### New Capabilities
- `intake-simulator`: 접수 검증, 선택 목록, 시연용 불러오기, 다시 시도, 접수 시뮬레이터 화면.

## 범위 밖

- **실패가 아닌 티켓의 다시 처리**: 이전 DRAFT를 superseded로 바꾸는 일반 다시 처리는 티켓 상세 전체판(FR-030, 19번)에서 붙인다(근거: §2-4 재처리, 화면 정의서 v1 H-05, C-85, C-98).
- **AC-003-3 추적표 9건 재현**: 그룹 2·3 AC가 상세화했고 1순위 시험(4,000건 재현, 추적표 시험)이 확인한다(근거: AC-003-3 "그룹 2·3의 AC로 상세화", 1순위 rule-engine 시험).
- **접수 경로별 입력 양식, 외부 연계**(근거: 화면 정의서 v1 SCR-01 ⑨, FR-001 기능 설명 "MVP에는 외부 연동이 없으므로").

## Impact

- 새 파일: `backend/app/api/ref_lists.py`(선택 목록), `backend/app/api/gold_inputs.py`(불러오기), `backend/tests/acceptance/test_intake_simulator.py`, `frontend/src/IntakePage.tsx`(근거: design 결정 1~5).
- 고치는 파일: `app/db/store.py`(검증·연락처·출처), `app/api/tickets.py`(오류 모양, reprocess), `app/db/runs.py`(처리 흐름 실행 판정), `app/main.py`(라우터), `frontend/src/App.tsx`·`api.ts`·`TicketDetailPage.tsx`·`styles.css`(근거: design 결정 1~5).
- 기존 시험 `test_unknown_customer_rejected`는 오류 문구와 응답 모양이 바뀌어 고친다(근거: FR-001 예외 1행 "고객 ID를 찾을 수 없음").
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
