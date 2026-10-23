# Proposal: 나의 업무 현황 (add-my-work)

## Why

상담원은 "지금 내가 손대야 할 것"(승인 대기 초안, 기한 위험·위반, 회신 대기, 오늘 처리 건수)을 한 화면에서 봐야 한다. 접수함이 처리 순서라면 이 화면은 할 일과 위험이다(근거: 명세서 v1.5 FR-047 기능 설명, D31, 화면 정의서 v1 SCR-04 ① 목적). 지금은 집계 API와 화면이 없고 메뉴는 "나의 업무 현황 2순위"로 흐리게만 있다(근거: 이 변경 전 `frontend/src/App.tsx`).

## What Changes

- **집계 API (FR-047)**: `GET /me/workload?dept=&scope=&as_of=`(상담원은 `X-Agent-Id`)가 영역 5개를 한 번에 돌려준다(근거: 기술 명세서 v1.4 §8-1 GET /me/workload 행, §8-3).
  - 범위: 상담원이 있으면 "내 담당" = sub_ticket.assignee_masked = 상담원 ID, 부서만 있으면 그 부서(assigned_dept) 전체. scope로 둘 중 하나를 고른다(근거: §8-3 첫 문단, D33, 화면 정의서 v1 SCR-04-01, 구현 선택 C-118).
  - 타일 4개: 승인 대기 초안 / 기한 위험·위반 / 고객 회신 대기 / 이관 회신 대기(근거: FR-047 처리 1, §8-3 타일 ①~④).
  - 기한 위험·위반 목록: 풀리지 않은 경고(FR_AT_RISK, FR_BREACHED, RES_AT_RISK, RES_BREACHED)가 있는 미해결 하위 문의, 남은 시간 오름차순. SLA 미정은 빼고 "SLA 미정 n건"(근거: FR-047 처리 2, 예외 2행, §8-3).
  - 승인 대기 초안 목록: 종류, 하위 문의, 만든 시각, 확인 표시 유무, 우선순위 → 만든 시각 순(근거: FR-047 처리 3, §8-3).
  - 회신 대기 목록 2개: 고객 회신 대기(정보 요청 뒤 경과, 126h·168h, 리마인드 발송 여부), 이관 회신 대기(이관 부서, 이관 시각, 경과)(근거: FR-047 처리 4, §8-3).
  - 오늘 처리한 건수: 기준 시각의 날짜(UTC)에 발송·이관·조정 수(근거: FR-047 처리 5, §8-3).
  - 저장·상태 변경 없음(근거: FR-047 출력).
- **화면 (SCR-04)**: `/my`. 범위 띠와 [내 담당]/[부서 전체], 타일(누르면 목록으로), 목록 4개, 오늘 처리 건수, 행 클릭 → 상세, 5분마다 갱신, 머리 막대를 바꾸면 다시 그림(근거: 화면 정의서 v1 SCR-04 ④~⑥, FR-047 처리 6·7, 기술 명세서 §8-2).

## Capabilities

### New Capabilities
- `my-work`: 상담원 한 명(또는 부서)의 할 일·위험 집계 API와 화면.

## 범위 밖

- **"전체 보기" 스위치(운영 대시보드 FR-034)**: 여유 시 기능(근거: 화면 정의서 v1 SCR-04 ⑨, openspec/config.yaml).
- **담당 상담원 정하기(assignee_masked 채우기)**: 새 접수 문의에 채우는 기능은 명세서에 없고, 시연 재생에서 채우는 일(W6)은 이 변경 밖이다. 읽기만 한다(근거: 테이블 정의서 v1.3 assignee_masked 설명, FR-047 입력, C-118).
- **이관하기(FR-033)**: 3순위. 이관 회신 대기 목록은 이미 이관된 문의를 읽기만 한다(근거: openspec/config.yaml).

## Impact

- 새 파일: `backend/app/db/workload.py`, `backend/app/api/me.py`, 시험 `backend/tests/acceptance/test_my_work.py`, `frontend/src/MyWorkPage.tsx`(근거: design 결정 1~4).
- 고치는 파일: `backend/app/main.py`(라우터), `frontend/src/App.tsx`(메뉴·`/my`), `api.ts`, `InboxPage.tsx`(배지·경고 표시 공유), `styles.css`(근거: design 결정 2·3).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4, schema.sql "나의 업무 현황은 뷰를 두지 않고 API가 계산한다").
