# 화면 명세: SCR-02 접수함

- 연결 요구사항: FR-029 (AC-029-1~5), FR-026·027(남은 시간·경고 표시), FR-013(정보 요청 필요), FR-031(승인 대기), FR-023(리마인드)
- 기준 목업: cs-agent-mockup_v1.42.html `viewInbox`, `inboxRows` (레이아웃 기준선: 요약 버튼 → 필터 → 표 → 쪽 넘김)
- 화면 정의서: v1 SCR-02
- 사용 API: `GET /tickets?dept=&status=&priority=&alert=&channel=&needs_info=&has_draft=&composite=&include_closed=&q=&page=&size=50&sort=&as_of=`

## 영역

| 요소 ID | 영역 | 표시 | 계약 칸 |
|---|---|---|---|
| SCR-02-S1 | 요약 버튼 4개 | 전체 n / 경고 n / 정보 요청 필요 n / 미발송 초안 n. 누르면 그 필터를 켬 | counts.total, alert, needs_info, has_draft |
| SCR-02-F1~F8 | 필터 | 상태 / 우선순위 / 경고(아무 경고, 또는 4종) / 채널 / 정보 요청 필요 / 미발송 초안 / 복합 문의 / 종료 포함 | status, priority, alert, channel, needs_info, has_draft, composite, include_closed |
| SCR-02-F9 | 검색 | 한 칸 "티켓 번호 또는 고객사" | q |
| SCR-02-T | 표 | 아래 열. 하위 문의 1행. 맨 앞에 선택 칸 | rows[] |
| SCR-02-B | 선택 막대 | 행을 하나라도 고르면 표 위에 "n건 선택" + [내보내기 (CSV)] + [선택 해제]. 최신 목업(Frontend 폴더) 접수함 | (화면 계산) |
| SCR-02-PG | 쪽 넘김 | "n건 중 a–b" + 쪽 번호 | page, size, rows 길이 |

표 열 (FR-029 처리 2 순서, 목업 열 이름)

| 열 | 표시 | 계약 칸 |
|---|---|---|
| 선택 | 체크 칸. 머리 칸은 이 쪽 전체 선택. 누르면 상세로 가지 않음 | (화면 계산) |
| 순번 | 이 쪽 안의 번호 | (화면 계산) |
| 티켓 번호 | ticket_id, 복합이면 "#k". 누르면 상세. 정렬 가능 | ticket_id, seq |
| 채널 | 이름. 티켓 번호 바로 오른쪽. 상태가 신규(NEW)면 "NEW" 태그 | channel, status |
| 접수 시각 | UTC. 정렬 가능 | received_at_utc |
| 고객사·등급 | company_masked + 등급 칩 | company_masked, customer_tier |
| 제품 | product_code, 없으면 "미확인" 칩. 마우스 올리면 product_name | product_code, product_name |
| 유형 | category_code 이름, 복합이면 "복합 n건 중 k" | category_code, seq, inquiry_count |
| 우선순위 | P1~P4 배지, P1은 빨간 점, 조정이면 "(조정)". 정렬 가능 | priority, priority_adjusted |
| 처리 상태 | 상태 배지(CP-1). 이관받은 행은 "{원 부서}에서 이관됨", 이관 보낸 행은 "→ {부서}" | status, escalated_in_from, escalated_to |
| 남은 시간 | 해결 남은 시간. 대기 중 "멈춤", 없으면 "SLA 미정". 정렬 가능 | remaining_h, res_status |
| 경고 | 경고 칩(노랑 위험, 빨강 위반) | alerts[] |
| 정보 요청 | "필요" | needs_info |
| 승인 대기 | "있음" | has_unsent_draft |
| 리마인드 | WAITING_CUSTOMER이고 보냈으면 "발송됨" | reminder_sent, status |

## 화면 상태

- 로딩: 표 자리에 스켈레톤 10행.
- 부서 미선택: API가 주는 message "부서를 선택하세요"만 보임(목록 요청 안 함).
- 데이터 없음: "처리할 티켓이 없습니다"(API message). 필터가 켜져 있으면 [필터 지우기]도.
- 오류: 이전 목록을 흐리게 두고 "목록을 불러오지 못함. 새로고침" 띠 + [새로고침].
- 종료 포함: RESOLVED·CLOSED 행을 연회색으로.
- SLA 미정 행: 남은 시간 "SLA 미정", 정렬 맨 아래.
- 자동 갱신: 5분마다. 갱신 때 필터·정렬·쪽은 그대로.

## 사용자 동작 → 시스템 반응

| 동작 | 호출 API | 성공 시 | 실패 시 |
|---|---|---|---|
| 화면 열기 | `GET /tickets?dept={상단 부서}&page=1&size=50` | 표·요약 그림. 정렬은 서버 기본(경고 있음 → 남은 시간 → 접수 시각) | 오류 상태 |
| 요약 버튼 누르기 | `GET /tickets?...&alert=` 등 | 해당 필터를 켜고 1쪽부터 | 이전 목록 유지 + 오류 띠 |
| 필터 바꾸기 | `GET /tickets?...` | 1쪽부터 다시 읽음. 필터는 브라우저에 기억 | 같음 |
| 검색어 입력(입력 멈춘 뒤 0.3초) | `GET /tickets?q=` | 1쪽부터 | 같음 |
| 열 머리 누르기 | `GET /tickets?sort=ticket_id` / `-ticket_id` (priority, remaining, received_at, status) | 오름 → 내림 → 기본 순으로 바뀜 | 같음 |
| 쪽 넘기기 | `GET /tickets?page=n` | 그 쪽 | 같음 |
| 행 누르기 | — | 그 티켓 상세(SCR-03, 주소 `/tickets/{ticket_id}`). 누른 하위 문의(seq)의 구역을 먼저 보임 | — |
| 상세에서 [접수함으로] | — | 필터·정렬·쪽이 그대로인 접수함 | — |

## 입력 검증

- 검색어: 앞뒤 공백 제거, 100자 이하(구현 선택). 빈 값이면 q를 보내지 않는다.
- page는 1 이상, size는 50 고정.

## 수용 기준 (Given / When / Then)

- SCR-02-AC-1 (AC-029-1): Given 미해결 360건 재생 + 스냅샷, When 부서 TS_LV로 열면, Then 요약 "전체 69"(담당 67 + 이관받은 2)가 보이고 맨 위 행은 경고가 있으며 남은 시간이 가장 적다.
- SCR-02-AC-2 (AC-029-2): Given 같은 상태, When "정보 요청 필요" 요약 버튼을 누르면, Then 모든 행의 정보 요청 열이 "필요"다.
- SCR-02-AC-3 (AC-029-3): Given CSV1-000008을 접수한 상태, When 담당 부서 접수함을 보면, Then 유형 칸이 "복합 2건 중 1"과 "복합 2건 중 2"인 행이 있다.
- SCR-02-AC-4 (AC-029-4): Given 표의 한 행, When 누르면, Then 그 티켓의 상세가 열린다.
- SCR-02-AC-5 (AC-029-5): Given 종료 포함이 꺼진 상태, When 목록을 보면, Then RESOLVED·CLOSED 행이 없다.
- SCR-02-AC-6: Given 부서를 고르지 않은 상태, When 접수함을 열면, Then "부서를 선택하세요"만 보인다.
- SCR-02-AC-7: Given 목록 요청이 실패하는 상태, When 새로고침을 누르면, Then 이전 목록이 흐리게 남고 "목록을 불러오지 못함. 새로고침"이 보인다.
- SCR-02-AC-9: Given 접수함에 행이 보이는 상태, When 행 두 개의 체크 칸을 고르면, Then "2건 선택" 막대가 보이고(상세로 가지 않음), [내보내기 (CSV)]는 머리 + 2행짜리 파일을 저장하며, [선택 해제]를 누르면 막대가 사라진다.
- SCR-02-AC-10: Given TS_LV 스냅샷, When 접수함을 보면, Then 채널 열이 티켓 번호 열 바로 오른쪽에 있고 "NEW" 태그는 처리 상태가 신규인 행에만 붙는다.
- SCR-02-AC-8: Given 2쪽을 보다가 행을 눌러 상세로 간 상태, When [접수함으로]를 누르면, Then 같은 필터의 2쪽이 보인다.

## 목업과 다른 곳

2026-10-31 기준: 팀 결정으로 **목업이 최신 기준**이다. 아래 표의 "명세" 쪽은 목업을 따르도록 차례로 고치는 중이다. 이번 변경(feat/mockup-inbox)은 서버 값이 필요 없는 것(선택·CSV, 채널·NEW)만 맞췄다. 요약 한 줄·국가·담당자·내 차례·검토 모드는 서버 값이 필요해 다음 변경에서 한다.

| 목업 | 명세 | 이유 |
|---|---|---|
| 제목 열 = 본문 한국어 번역 첫 문장 | 제목 열 없음. 유형 + 제품으로 알아봄 | API에 번역 없음. 번역은 FR-030 여유 시 항목(정할 것 Q1) |
| 정보 요청 "필요 n"(막는 항목 수) | "필요"만 | 계약은 needs_info(참·거짓) |
| 검색 대상 고르기(전체·티켓 번호·고객사) | 한 칸 | q가 둘을 함께 찾음 |
| 한 쪽 10건 | 50건 | FR-029 처리 7, API 기본 size 50 |
| 화면이 기본 정렬을 계산 | 서버 기본 정렬 | backend/app/db/inbox.py DEFAULT_ORDER(FR-029 처리 3, C-99) |
| 화면 정의서 v1의 긴급도·1차 응답 남은 시간 열 | 넣지 않음(목업 따름) | FR-029 처리 2 열 목록에 없음. 화면 정의서 v1이 더한 열이라 목업과 FR을 따름 |
