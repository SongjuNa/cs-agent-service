# Design: 가상 상담원 명단과 담당 배정

## Context

assignee_masked는 "담당 상담원 ID, 나의 업무 현황의 내 담당 거르기"다(근거: 테이블 정의서 v1.3 assignee_masked, 기술 명세서 v1.4 §8-3). 운영진 데이터는 11개 부서마다 12명의 상담원 ID(예: TS_LV_AGENT_09)를 쓰고 QA_CLAIM·RND_FW에는 상담원이 없다(근거: tickets.csv assignee_masked, 명세서 v1.5 FR-033 처리 10). 조장은 2026-10-23에 지어낸 사람 이름으로 채우기로 정했다(근거: 조장 결정 2026-10-23).

## Decisions

### 1. 명단 (`backend/app/roster/agent_roster.json`, `backend/app/db/assignees.py`)

- 11개 부서 × 12명(source_id = 운영진 상담원 ID) + QA_CLAIM·RND_FW 각 1명(source_id QA_CLAIM_AGENT_01, RND_FW_AGENT_01, demo = 시연용). 이름은 흔한 성과 이름을 짝지어 만든 지어낸 이름이고 134개가 모두 다르다(근거: tickets.csv, FR-033 처리 10, 조장 결정 2026-10-23).
- 담당 값(assignee_masked)과 상단 막대 값(X-Agent-Id)에 이름을 쓴다. 그래서 발송·조정·전이 기록(sent_by_name, adjusted_by, changed_by)에도 이름이 남는다(근거: 조장 결정 2026-10-23, 명세서 D23 "상담원 이름", 구현 선택 C-128).
- 명단 파일은 처음 읽을 때 한 번 읽는다. 파일을 `data/` 아래에 두지 않는다(.gitignore가 운영진 원본 데이터용으로 data/를 무시)(근거: .gitignore, CLAUDE.md 규칙 8, 구현 선택).
- 이 모듈은 언어 모델 호출 계층을 import하지 않는다(근거: CLAUDE.md 규칙 1).

### 2. 새 문의 배정 (`backend/app/db/store.py`)

- 처리 흐름 결과를 저장할 때(접수·다시 처리·고객 회신 재처리·상담원 수정) 하위 문의의 담당 부서가 있고, 담당 상담원이 비었거나 다른 부서 명단 사람이면 배정한다. 명단에 없는 값(손으로 넣은 ID 등)은 그대로 둔다(근거: 조장 결정 2026-10-23, 구현 선택 C-127·C-128).
- 고르는 법: 그 부서 명단에서 지금 맡은 미해결(NEW·IN_PROGRESS·WAITING_CUSTOMER·ESCALATED) 하위 문의 수가 가장 적은 사람, 같으면 명단 순서(근거: FR-029 처리 1 미해결 상태, 구현 선택 C-127).
- 상담원 수정으로 담당 부서가 바뀌면 새 부서 사람으로 다시 배정한다. 부서가 그대로면 담당도 그대로다(근거: FR-030 처리 6, 구현 선택 C-127).
- 담당 부서가 없으면 비워 둔다(근거: FR-012 예외).

### 3. 재생 채점 (`jobs/replay_gold.py`)

- scoring.sub_ticket에 넣을 때 정답지 assignee_masked(source_id)를 명단 이름으로 바꿔 넣는다. 명단에 없는 ID면 그대로 둔다(근거: 조장 결정 2026-10-23 "이름으로 바꿔 넣기", C-118).
- scoring은 화면(`GET /me/workload`, svc)이 읽지 않는다. 재생 담당 값은 workload 함수(schema=scoring)와 시험으로 본다. 화면에 보이게 하는 svc 재생(W6)은 이 변경 밖이다(근거: 기술 명세서 W6, jobs/replay_gold.py "svc에는 아무것도 쓰지 않는다").
- 재생 채점은 정답 열을 읽는 채점 코드다(근거: CLAUDE.md 규칙 6 예외).

### 4. API와 화면

- `GET /ref/agents?dept=` → [{name, dept, demo}]. dept가 없으면 전부(근거: `GET /ref/departments`와 같은 모양, 구현 선택).
- 상단 막대 상담원 칸: 자유 입력을 고른 부서의 명단 선택으로 바꾼다. 시연용은 "시연용"을 붙인다. 부서를 바꾸면 다른 부서 사람은 비우고, 브라우저에 남은 명단 밖 값(옛 ID)도 비운다(근거: 조장 결정 2026-10-23, FR-033 처리 10, 화면 정의서 v1 SCR-00-02와 다름 C-129).
- 문의 상세 머리 줄에 "담당 {이름}"을 더한다(근거: 구현 선택 C-130).

### 5. 시험 (`backend/tests/acceptance/test_agent_roster.py`)

- 명단: 11개 부서 × 12명 + 시연용 2명, 이름이 모두 다름, 운영진 상담원 ID가 모두 명단 이름으로 바뀜(근거: design 결정 1).
- 접수 두 건 → 같은 규칙으로 센 가장 적게 맡은 사람에게 차례로(시작 상태에 기대지 않음)(근거: design 결정 2).
- 상담원 수정으로 부서가 바뀌면 새 부서 사람, 명단 밖 값은 그대로(근거: design 결정 2).
- 재생 → 정답지 ID 대신 이름, workload(scoring)의 [내 담당]이 그 사람 문의만 셈(근거: design 결정 3).
- `GET /ref/agents`(근거: design 결정 4).

## Risks / Trade-offs

- C-127: 시스템이 저장 때 담당을 자동으로 배정한다. 테이블 정의서는 "새 접수는 비어 있다가 상담원이 맡으면 채운다", 기술 명세서 §5(sub_ticket 표)는 "그래프는 쓰지 않고 화면·API가 채움"이라 다르다. 배정 규칙(가장 적게 맡은 사람, 부서가 바뀌면 다시)도 구현 선택이다(근거: 테이블 정의서 v1.3 assignee_masked, 기술 명세서 v1.4, 조장 결정 2026-10-23).
- C-128: 상담원 값에 ID 대신 이름을 쓴다. 테이블 정의서 v1.3(assignee_masked·sent_by_name·changed_by·adjusted_by·agent_feedback.agent_id "상담원 ID"), schema.sql 주석, 명세서 FR-038 처리 1("assignee_masked는 그대로 쓴다")과 다르다. 문서를 이름 기준으로 고쳐야 한다. 명단 밖 값은 덮어쓰지 않는다(근거: 조장 결정 2026-10-23, 명세서 D23).
- C-129: 화면 정의서 v1 SCR-00-02는 상담원 칸을 자유 입력(운영진 ID 권장)으로 두었는데 명단 선택으로 바꾼다(근거: 조장 결정 2026-10-23, FR-033 처리 10).
- C-130: 상세 머리의 담당 표시는 화면 정의서 H-03에 없는 것을 더한 것이다(근거: 화면 정의서 v1 SCR-03 H-03, 구현 선택).
- C-131: 재생 담당 값은 scoring에만 들어가 화면에서는 아직 보이지 않는다. svc 시연 재생(W6)이 생기면 같은 이름 바꾸기를 써야 한다(근거: 기술 명세서 W6, jobs/replay_gold.py).
