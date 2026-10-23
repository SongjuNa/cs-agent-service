# Proposal: 접수함 (add-inbox)

## Why

접수함은 상담원의 진입점이다. 자기 부서의 끝나지 않은 문의를 급한 순서로 보고 골라 상세로 가야 한다(근거: 명세서 v1.5 FR-029 기능 설명, 화면 정의서 v1 SCR-02 ① 목적). 지금은 목록 API(`GET /tickets`)와 화면이 없고, 문의 번호를 직접 넣어야 상세를 열 수 있다(근거: 이 변경 전 `backend/app/api/tickets.py`, `frontend/src/App.tsx` 메뉴 "접수함 2순위").

## What Changes

- **목록 API (FR-029)**: `GET /tickets?dept=&status=&priority=&alert=&needs_info=&has_draft=&composite=&channel=&q=&include_closed=&page=&size=&sort=&as_of=`가 하위 문의 한 줄씩 돌려준다(근거: FR-029 처리 1~7, 기술 명세서 v1.4 §8-1 GET /tickets 행, schema.sql svc.v_inquiry_inbox).
  - 범위: 고른 부서가 담당(assigned_dept)이거나 이관받은(escalated_to) 하위 문의 중 끝나지 않은 것. "종료 포함"이면 RESOLVED·CLOSED도(근거: FR-029 처리 1, AC-029-5).
  - 열: 문의 번호(복합이면 n건 중 k), 접수 시각, 채널, 고객사·등급, 제품, 유형, 긴급도, 우선순위(조정 표시), 상태(이관 표시), 해결 남은 시간, 경고, 정보 요청 필요, 승인 대기 초안, 리마인드 발송됨(근거: FR-029 처리 2·5, 화면 정의서 v1 SCR-02 목록 표 열).
  - 기본 정렬: 경고 있는 줄 위, 그 안에서 해결 남은 시간 오름차순, SLA 미정은 맨 아래. sort로 바꿀 수 있다(근거: FR-029 처리 3, FR-027 처리 5, 예외 3행).
  - 필터 7종을 함께 걸고, 검색어는 문의 번호 또는 고객사(근거: FR-029 입력·처리 4, §8-1).
  - 건수 요약과 페이지(50건)(근거: FR-029 출력, 처리 7, §8-1 size=50).
  - SLA는 기준 시각(as_of, 비우면 지금)으로 계산한다(근거: 화면 정의서 v1 SCR-00-04 "모든 조회의 as_of", 기술 명세서 §6-4 inquiry_sla(as_of)).
  - 부서를 고르지 않으면 빈 목록과 "부서를 선택하세요"(근거: FR-029 예외 1행).
- **화면 (SCR-02 접수함)**: `/inbox`(기본 화면). 요약 띠, 필터, 표, 페이지, 행 클릭 → 상세, 5분마다 갱신, 상태 배지 색. 머리 막대에 부서 선택과 기준 시각(실제 시각 / 스냅샷) 전환을 더한다(근거: 화면 정의서 v1 SCR-02, SCR-00-03·04, v2 부록 B-2·B-3, FR-029 처리 6, 기술 명세서 §8-2).

## Capabilities

### New Capabilities
- `inbox`: 부서 접수함 목록 API와 화면.

## 범위 밖

- **상세의 [목록으로] 버튼**: 티켓 상세 전체판(19번)에서 붙인다(근거: 화면 정의서 v1 SCR-03 ③ 길, H-05, 변경 순서).
- **관리자 전체 보기, 열 숨기기**(근거: 화면 정의서 v1 SCR-02 ⑨).
- **1차 응답 남은 시간 열**: 명세서 열 목록에는 해결 남은 시간만 있다. 1차 응답은 경고 아이콘(FR_AT_RISK·FR_BREACHED)으로 보인다(근거: FR-029 처리 2, 화면 정의서 v1 SCR-02 열 10, C-100).

## Impact

- 새 파일: `backend/app/db/inbox.py`, 시험 `backend/tests/acceptance/test_inbox.py`, `frontend/src/InboxPage.tsx`(근거: design 결정 1~4).
- 고치는 파일: `backend/app/api/tickets.py`(GET /tickets), `frontend/src/App.tsx`(라우팅·머리 막대), `api.ts`, `styles.css`(근거: design 결정 2~3).
- DB 구조는 고치지 않는다. 뷰 `v_inquiry_inbox`를 읽기만 한다(근거: CLAUDE.md 규칙 4, schema.sql).
