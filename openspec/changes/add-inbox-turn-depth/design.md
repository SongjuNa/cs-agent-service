# Design: 접수함 내 담당·내 차례·검토 모드

## Decisions

### 1. 담당 필터와 건수

| 항목 | 정한 것 | 근거 |
|---|---|---|
| `assignee` | 이름이 같은 줄만(`assignee_masked = %s`). 비우면 거르지 않음 | 목업 `내 담당 / 팀 전체`, 상담원 목록 거르기 |
| `me` | 건수 `mine`을 셀 상담원 이름(요청 머리 `X-Agent-Id`가 아니라 쿼리로 받는다) | 변경 add-agent-assistant와 같은 이유: 머리 값을 답에 쓰지 않는다(D23·D33) |
| `counts.mine` | 부서 접수함 중 `assignee_masked = me`인 미해결 줄 수 | 목업 `내 담당 n` |
| `counts.turn_me` | 내 차례인 줄 수 | 목업 부제 "지금 처리할 문의 n건" |

### 2. 내 차례 (`turn`)와 다음 행동 (`next_action`)

기준은 목업 `turnOf`·`actionOf`. 서버 상태로 옮기면 다음과 같다. **이관 회신이 오면 서버는 ESCALATED → IN_PROGRESS로 바꾸므로**(`ticket_status_history` DEPT_REPLY) 목업의 "부서 회신 도착"은 서버에서 "IN_PROGRESS이고 ESCALATION_NOTE RECEIVED가 있음"이다.

| 조건(위에서부터) | `turn` | `next_action` |
|---|---|---|
| status RESOLVED·CLOSED | DONE | DONE |
| status ESCALATED | DEPT | WAIT_DEPT |
| status WAITING_CUSTOMER | CUSTOMER | WAIT_CUSTOMER |
| 막는 정보 누락(`needs_info`)이고 정보 요청 미발송 | ME | SEND_INFO_REQUEST |
| ESCALATION_NOTE RECEIVED가 있고 최종 답 미발송 | ME | CHECK_DEPT_REPLY |
| 미발송 초안(`has_unsent_draft`) | ME | APPROVE_DRAFT |
| 그 밖 | ME | WRITE_ANSWER |

- 화면은 코드를 한국어 문구로 바꾼다(`app/labels.ts`). 서버는 문장을 만들지 않는다.
- 줄마다 부가 질의가 늘지 않게 `rows` CTE에 `dept_replied`(EXISTS) 하나만 더한다.

### 3. 기본 정렬

`ORDER BY turn_rank, 지금 정렬`. `turn_rank`: ME 0, DEPT·CUSTOMER 1, DONE 2. 열 머리 정렬(`sort=`)을 누르면 묶음 없이 그 열 순서로 간다(목업과 같다).

### 4. 검토 모드 (`review_depth`)

목업 문구 그대로 "조건은 팀 제안안이라 조장이 확정하면 이 규칙만 고치면 된다".

- **DEEP**: `urgency_flag`가 NONE이 아님, 또는 `priority = P1`, 또는 이관 후보가 있음(`ref` 라우팅 규칙에 이 문의 유형·제품군의 `ESCALATION` 행이 있음).
- **QUICK**: DEEP이 아니고, 막는 정보 누락 없고, `priority`가 P3·P4.
- **NORMAL**: 그 밖.
- 목업은 "검토 표시 ①②③ 걸림", "AI 분류 신뢰도 낮음"도 DEEP 조건으로 쓴다. 서버에서 이 값이 어디에 저장되는지(실행 기록 단계인지)는 확인하지 못했다. 1차에는 넣지 않고, 확인 뒤 같은 함수에 조건만 더한다.
- 규칙 코드는 `backend/app/rules/turn.py`의 순수 함수(`turn_of`, `depth_of`)로 두고, SQL에서 한 번에 계산하지 않고 줄을 읽은 뒤 파이썬에서 붙인다(규칙을 시험하기 쉽게).

### 5. 시험

| 시험 | 내용 |
|---|---|
| 규칙 단위 시험 | `turn_of`·`depth_of`의 표(위 2·4절) 조건별. DB 필요 없음 |
| 접수함 시험 | `assignee`로 거르면 그 이름만, `turn=ME`면 ME만, 기본 정렬에서 ME 묶음이 앞, `counts.mine`·`turn_me`가 줄과 일치 |
| 기존 AC-029-1 | 맨 위 행 검사를 "ME 묶음 안에서" 로 고친다(요구사항 명세서 확인 뒤) |

## Risks

- 기본 정렬 변경은 요구사항(FR-029 처리 3)을 바꾼다. 팀·조장 확인 필요.
- `X-Agent-Id`를 쓰지 않고 쿼리로 이름을 받으면 아무 이름이나 넣을 수 있다. 로그인이 없는 시연 환경(D23)이라 허용하고, 실제 인증은 범위 밖.
- 검토 모드 1차 규칙이 목업보다 느슨해 DEEP이 덜 나올 수 있다.
