# Proposal: 가상 상담원 명단과 담당 배정 (add-agent-roster)

## Why

나의 업무 현황의 "내 담당"은 하위 문의의 담당 상담원 값(assignee_masked)으로 거르는데, 이 값을 채우는 곳이 없어 늘 비어 있다(근거: 기술 명세서 v1.4 §8-3, 개발 결정 기록 C-118). 조장이 2026-10-23에 "임의로 진짜 사람 이름을 넣어서 진행"하기로 정했다: 부서마다 가상 상담원 명단을 두고, 새 문의는 그 부서 상담원에게 배정하고, 시연 재생은 정답지 상담원 ID를 명단의 이름으로 바꿔 넣고, 상단 막대에서 명단으로 고른다(근거: 조장 결정 2026-10-23).

## What Changes

- **명단 (설정 파일)**: `backend/app/roster/agent_roster.json`에 지어낸 이름(실존 인물 아님)을 둔다. 운영진 데이터에 상담원이 있는 11개 부서는 12명씩(운영진 상담원 ID와 짝), 상담원이 없는 QA_CLAIM·RND_FW는 시연용 1명씩이다. 줄은 이름, 부서, 운영진 상담원 ID(source_id), 시연용 여부다. 새 표·열은 만들지 않는다(근거: tickets.csv assignee_masked 11개 부서 × 12명, 명세서 v1.5 FR-033 처리 10, CLAUDE.md 규칙 4, 조장 결정 2026-10-23).
- **새 문의 배정**: 처리 흐름 결과를 저장할 때 담당 부서가 있고 담당 상담원이 비었거나 다른 부서 명단 사람이면, 그 부서 명단에서 미해결 문의를 가장 적게 맡은 사람(같으면 명단 순서)을 넣는다. 테이블 정의서("상담원이 맡으면 채운다")·기술 명세서("그래프는 쓰지 않고 화면·API가 채움")와 다르다(근거: 조장 결정 2026-10-23, 구현 선택 C-127).
- **재생 채점**: `jobs/replay_gold.py`가 scoring에 넣을 때 정답지 assignee_masked를 명단 이름으로 바꿔 넣는다. svc에 재생하는 W6은 이 변경 밖이다(근거: 조장 결정 2026-10-23, C-118, CLAUDE.md 규칙 6 예외: 채점 코드).
- **명단 API**: `GET /ref/agents?dept=`(근거: 기존 `GET /ref/departments`와 같은 참조 목록, 구현 선택).
- **화면**: 상단 막대의 상담원 칸(자유 입력)을 명단 선택으로 바꾸고 시연용은 "시연용"으로 표시한다. 문의 상세 머리에 담당 상담원을 보인다(근거: 조장 결정 2026-10-23, 명세서 D23 "상담원 이름·부서를 고른다", FR-033 처리 10, 화면 정의서 v1 SCR-00-02, 구현 선택 C-129·C-130).

## Capabilities

### New Capabilities
- `agent-roster`: 가상 상담원 명단, 새 문의 담당 배정, 재생 담당 값, 상단 막대 선택.

## 범위 밖

- **상담원이 담당을 넘기거나 가져오는 기능**: 명세서에 없다(근거: 명세서 v1.5 FR-047·FR-030).
- **svc 시연 재생(W6)**: 아직 없는 작업이다(근거: 기술 명세서 W6, C-118).
- **로그인·권한**: 상단 막대에서 고르는 방식 그대로다(근거: 명세서 D23).

## Impact

- 새 파일: `backend/app/roster/agent_roster.json`, `backend/app/db/assignees.py`, 시험 `backend/tests/acceptance/test_agent_roster.py`(근거: design 결정 1~5).
- 고치는 파일: `backend/app/db/store.py`(저장 때 배정), `backend/app/api/ref_lists.py`, `backend/app/db/detail.py`, `jobs/replay_gold.py`, `frontend/src/App.tsx`·`api.ts`·`TicketDetailPage.tsx`, 시험 `test_my_work.py`(주석)(근거: design 결정 1~5).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
