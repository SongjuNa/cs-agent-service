# Design: 접수함

## Context

- 명세서 v1.5 FR-029(AC-029-1~5), FR-027 처리 5, FR-033 처리 6.
- 기술 명세서 v1.4 §6-4(inquiry_sla(as_of)), §6-4 티켓 대표값 문단(v_inquiry_inbox), §8-1 GET /tickets, §8-2 접수함·자동 갱신.
- 화면 정의서 v1 SCR-00, SCR-02, 화면 정의서 v2 부록 B-1·B-2·B-3.
- schema.sql svc.v_inquiry_inbox(scoring에도 같은 뷰), 함수 inquiry_sla(as_of), svc.sub_ticket.priority_adjusted_by_agent.

## Decisions

### 1. 목록 조회 (`backend/app/db/inbox.py`)

- `v_inquiry_inbox`의 줄에 `inquiry_sla(as_of)`의 fr_status·res_status·remaining_h를 붙여 기준 시각으로 SLA를 다시 계산한다. 뷰는 now() 기준이라 as_of가 다르면 바꿔 끼운다(근거: schema.sql 뷰 주석 "SLA는 지금 기준", 화면 정의서 v1 SCR-00-04, SCR-02 열 11 "inquiry_sla(as_of)").
- schema 인자(svc / scoring)를 받는다. 시험은 운영진 4,000건을 scoring에 재생해 본다(근거: 1순위 test_ac_027_4와 같은 방식, schema.sql scoring "svc와 같은 모양". 인자는 구현 선택).
- 범위: `assigned_dept = dept OR escalated_to = dept`, include_closed가 아니면 status가 NEW·IN_PROGRESS·WAITING_CUSTOMER·ESCALATED(근거: FR-029 처리 1, §8-1 "dept는 assigned_dept 또는 escalated_to", AC-029-5).
- 줄 값 더하기: product_name(제품 칸 마우스 올림), priority_adjusted_by_agent("조정"), 이관 표시 escalated_in(= escalated_to가 이 부서이고 assigned_dept가 아님, 원 부서 이름) (근거: 화면 정의서 v1 SCR-02 열 5·8·9, FR-029 처리 1 "{원 부서}에서 이관됨").

| 필터·검색 | 조건 | 근거 |
|---|---|---|
| status | 쉼표로 여럿 | FR-029 처리 4, SCR-02-F1 |
| priority | P1~P4 여럿 | FR-029 처리 4, SCR-02-F2 |
| alert | FR_AT_RISK, FR_BREACHED, RES_AT_RISK, RES_BREACHED 중 하나라도 풀리지 않음 | FR-029 처리 4, SCR-02-F3 |
| needs_info | 막는 항목 있음 | FR-029 처리 4, AC-029-2 |
| has_draft | 승인 대기 초안 있음 | FR-029 처리 4, 뷰 has_unsent_draft |
| composite | 하위 문의 2개 이상 | FR-029 처리 4, 뷰 inquiry_count |
| channel | 5값 여럿 | FR-029 처리 4 |
| q | 문의 번호 또는 고객사 부분 일치(대소문자 무시) | FR-029 입력, SCR-02-F9 |

- 정렬 기본: 경고 있음 → 해결 남은 시간 오름차순(없으면 맨 아래) → 접수 시각 → 하위 문의 번호(근거: FR-029 처리 3, FR-027 처리 5, 예외 3행. 뒤 두 단계는 구현 선택). 화면 정의서 v1 ⑤의 "우선순위" 단계는 명세서에 없어 넣지 않는다(C-99).
- sort: received_at, priority, remaining, status, ticket_id, 앞에 "-"면 내림차순. 그 밖이면 기본(근거: FR-029 처리 3 "열 머리글 클릭", §8-1 sort. 이름은 구현 선택).
- 건수 요약(필터 범위): total, alert, needs_info, has_draft, waiting(회신 대기)(근거: FR-029 출력 "전체 / 경고 / 정보 요청 필요 / 미발송 초안", 화면 정의서 v1 SCR-02-S1 "회신 대기").
- 페이지: page(1부터), size 기본 50, 최대 200(근거: FR-029 처리 7, §8-1 size=50. 최대는 구현 선택).

### 2. API (`GET /tickets`)

- 응답 `{"dept", "as_of", "page", "size", "counts", "rows", "message"}`. dept가 없으면 rows 빈 목록, message "부서를 선택하세요". 줄이 없으면 message "처리할 티켓이 없습니다"(근거: FR-029 예외 1·2행, 모양은 구현 선택).
- 부서는 쿼리 dept로 받는다. 화면은 머리 막대에서 고른 부서를 넣는다(근거: §8-1 dept 인자, D23).

### 3. 화면 (`frontend/src/InboxPage.tsx`, `App.tsx`)

| 요소 | 내용 | 근거 |
|---|---|---|
| 주소·메뉴 | `/inbox`, 첫 화면(`/`)도 접수함. 사이드바 "접수함" 켬 | 화면 정의서 v1 SCR-00-05 "접수함(기본)", 부록 B-2 |
| 머리 막대 | 부서 선택 13개(코드 + 이름, `GET /ref/departments`), 기준 시각 "실제 시각 / 스냅샷 2026-09-30 23:59 UTC", 브라우저에 기억 | 화면 정의서 v1 SCR-00-03·04, D23 |
| 요약 띠 | 미해결(필터 범위 전체) / 경고 / 정보 요청 필요 / 승인 대기 / 회신 대기 | FR-029 출력, SCR-02-S1 |
| 필터 | 상태·우선순위·경고 종류·채널 칩, 정보 요청 필요·승인 대기·복합 문의 체크, 종료 포함 스위치, 검색 | 화면 정의서 v1 SCR-02-F1~F9 |
| 표 | FR-029 열 순서. 문의 번호 아래 "복합 n건 중 k", 유형 칸 "FW_UPDATE (복합 2건 중 1)", 우선순위 "(조정)", 상태 배지(부록 B-3 색 + 기호), 이관 표시, 남은 시간 "36.2h"·"−12.5h"·"멈춤"·"SLA 미정", 경고 아이콘, 표시 3개 | FR-029 처리 2·5, 출력 사용자 표시, SCR-02 열 1~13, AC-029-3 |
| 정렬 | 열 머리 클릭(접수 시각·우선순위·상태·남은 시간·문의 번호) | FR-029 처리 3 |
| 행 클릭 | `/tickets/{ticket_id}` | AC-029-4 |
| 갱신 | 들어올 때, [새로고침], 5분마다. 실패하면 이전 목록을 흐리게 두고 "목록을 불러오지 못함. 새로고침" | FR-029 처리 6, 예외 4행, §8-2 자동 갱신 |
| 상태 기억 | 필터·정렬·페이지를 주소 쿼리에 둬 상세에서 뒤로 오면 그대로 | SCR-02 ③ "돌아올 때 필터·정렬·페이지 유지" (주소 쿼리는 구현 선택) |
| 요청 머리 | 모든 요청에 `X-Agent-Dept`도 싣는다 | 화면 정의서 v1 공통 "상담원 식별", §8-1 |

### 4. 시험 (`backend/tests/acceptance/test_inbox.py`)

- AC-029-1: 운영진 4,000건을 scoring에 재생, 담당 부서(정답 assigned_dept)를 넣고 팀 정답지 5건을 빼고 스냅샷 경고를 단 뒤 TS_LV → 67줄, 맨 위는 경고가 있고 남은 시간이 가장 적다(근거: AC-029-1, AC-027-4 시험과 같은 재생).
- AC-029-2: 막는 항목(정답 missing_blocking_info)을 넣고 needs_info 필터 → 모두 막는 항목이 있다(근거: AC-029-2).
- AC-029-3: CSV1-000008을 API로 접수(복합) → 두 하위 문의 담당 부서 접수함에 "n건 중 k" 줄(근거: AC-029-3).
- AC-029-4: 줄의 ticket_id로 상세 API가 열린다(근거: AC-029-4. 화면 클릭은 브라우저 확인).
- AC-029-5: 종료 포함이 꺼지면 RESOLVED·CLOSED 없음, 켜면 있음(근거: AC-029-5).
- 그 밖: 부서 미선택, 이관 줄(escalated_to), 필터 조합, 검색, 정렬, SLA 미정 맨 아래, 페이지, 건수 요약(근거: FR-029 처리·예외).
- 화면은 `npm run build`와 브라우저 확인(근거: 17번과 같은 방식, 구현 선택).

## Risks / Trade-offs

- C-99: 기본 정렬에 화면 정의서 v1은 "우선순위" 단계가 있고 명세서·FR-027은 없다. 명세서를 따른다(근거: FR-029 처리 3, FR-027 처리 5, 화면 정의서 v1 SCR-02 ⑤).
- C-100: 화면 정의서 v1은 1차 응답 남은 시간 열(열 10)을 두지만 명세서 열 목록에는 없다. 명세서를 따르고 1차 응답은 경고 아이콘으로 보인다(근거: FR-029 처리 2, SCR-02 열 10).
- C-101: AC-029-1의 67건은 담당 부서만 센 수다. 처리 1대로 이관받은 문의(escalated_to = TS_LV, CSV1-003280·CSV1-003449)까지 넣으면 69줄이다. 시험은 두 수를 모두 확인한다(근거: FR-029 처리 1, AC-029-1, tickets.csv escalated_to).
- C-102: 뷰 v_inquiry_inbox를 그대로 읽으면 inquiry_sla가 줄마다 다시 계산돼 4,000건에서 1분을 넘는다. 목록 조회는 inquiry_sla(as_of)를 한 번만 계산하고 뷰와 같은 열·계산을 직접 쓴다. 뷰와 같은 값인지는 시험 test_same_rows_as_view가 서비스 DB의 복합 문의 줄로 본다(뷰의 열 가운데 now() 순간에 따라 달라지는 remaining_h만 뺀다). 뷰·DB 구조는 바꾸지 않는다(근거: schema.sql v_inquiry_inbox, 화면 정의서 v1 SCR-00-04, 구현 선택). 시험은 롤백할 재생 4,000건에 통계가 없어 실행 계획이 몇 분짜리가 되므로 픽스처에서 ANALYZE를 한다(구현 선택).
- C-103: 빈 목록 문구가 명세서는 "처리할 티켓이 없습니다", 화면 정의서 v1은 "처리할 문의가 없습니다"다. 명세서를 따른다(근거: FR-029 예외 2행, 화면 정의서 v1 SCR-02 ⑥).
- C-104: 서비스 DB(svc)에는 문의가 없고 상태 이력·경고는 지울 수 없어 화면 확인용 문의를 svc에 넣지 않는다. 브라우저 확인은 scoring 재생(롤백) 결과를 `GET /tickets` 응답으로 끼워 넣어 했다(근거: schema.sql guard_append_only, 구현 선택).
- C-105: 상태 칩 RESOLVED·CLOSED는 "종료 포함"이 켜져야 누를 수 있고, 끄면 그 칩 선택도 풀린다. 끝나지 않은 문의만 보이는 기본 범위와 칩이 서로 막아 빈 목록이 되지 않게 한다(근거: FR-029 처리 1·4, AC-029-5, 화면 정의서 v1 SCR-02-F1, 구현 선택).
- C-106: 긴급도 열은 명세서 FR-029 처리 2 열 목록에는 없고 화면 정의서 v1 SCR-02 열 7에 있다. SAFETY·SITE_DOWN 빨간 글자가 급한 문의를 고르는 데 쓰여 화면 정의서대로 둔다(C-100과 달리 둠)(근거: SCR-02 열 7, FR-029 처리 2).
- C-107: "리마인드 발송됨"은 회신 대기(WAITING_CUSTOMER) 줄에만 보인다. 쪽 수가 줄어 빈 쪽이 되면 "첫 쪽으로"를 보인다(근거: FR-029 처리 2 "회신 대기 중일 때", 처리 7, 구현 선택).
