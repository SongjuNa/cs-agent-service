# 화면 명세: SCR-07 고객 관리 (임시 번호)

- 연결 요구사항: FR-초안-01(고객 관리), FR-030(연락처 표시)
- 기준 목업: cs-agent-mockup_v1.42.html `viewCustomers`, `viewCustomer`, `viewCustMap`, `viewCountry` (레이아웃 기준선: 탭 "고객 목록 / 나라별 지도" → 등급 요약 → 필터 → 표)
- 화면 정의서: 없음
- 사용 API (변경 add-customer-views, 로컬 브랜치 feat/customer-views-api): `GET /customers?q=&tier=&country=&page=&size=50`, `GET /customers/{customer_id}`, `GET /customers/countries`

## 영역

| 요소 ID | 화면 | 표시 | API 칸 |
|---|---|---|---|
| N-07-01 | 목록 | 등급 요약 버튼: 등록 고객 n, PLATINUM / GOLD / SILVER / STANDARD n. 누르면 그 등급으로 거름 | 목록 건수 |
| N-07-02 | 목록 | 필터: 검색(고객 ID·고객사), 나라 | q, country |
| N-07-03 | 목록 | 표: 고객 ID, 고객사, 등급, 나라, 미해결, 전체 문의, 최근 문의 | customer_id, company_masked, tier, country, open_count, ticket_count, last_received_at |
| N-07-04 | 상세 | 머리: 고객 ID, 고객사, 등급, 미해결 문의, 기한 위험·위반, 나라, 최근 답장 언어, 최근 연락처 이메일 | CustomerDetail |
| N-07-05 | 상세 | 문의 이력 표: 티켓(#k), 원본 번호, 접수 시각, 유형, 제품(없으면 "미확인"), 우선순위, 상태, 경고. 접수 시각 내림차순 | 이력 행 (source_ticket_id 포함) |
| N-07-06 | 나라별 | 나라별 표(지도는 목업 그림): 나라, 고객 수, 전체 문의, 미해결. 누르면 그 나라 고객 목록 | countries |

## 화면 상태

- 로딩: 표 스켈레톤.
- 데이터 없음: "조건에 맞는 고객이 없습니다" + "검색어나 등급 필터를 바꿔 보세요".
- 고객 없음: "고객을 찾을 수 없습니다 {ID}" + [고객 관리로] (404 "고객을 찾을 수 없음").
- 오류: 이전 값을 두고 "불러오지 못함. 새로고침".

## 사용자 동작 → 시스템 반응

| 동작 | 호출 API | 성공 시 | 실패 시 |
|---|---|---|---|
| 목록 열기 / 필터·쪽 바꾸기 | `GET /customers?...` | 표 그림 | 이전 목록 유지 + 오류 띠 |
| 행 누르기 | `GET /customers/{id}` | 상세 화면(주소 `#c-{customer_id}`) | 404 → 고객 없음 상태 |
| 이력 행 누르기 | — | 티켓 상세(SCR-03) | — |
| 나라별 탭 | `GET /customers/countries` | 나라별 표 | 같음 |
| 나라 누르기 | `GET /customers?country=` | 그 나라 고객 목록 | 같음 |

## 입력 검증

- 검색어: 앞뒤 공백 제거, 빈 값이면 보내지 않음.

## 수용 기준 (Given / When / Then)

- SCR-07-AC-1 (FR-초안-01 AC 초안): Given 고객 CUST-0350, When 상세를 열면, Then 그 고객의 티켓이 접수 시각 내림차순으로 모두 보이고 원본 번호 CSV1-000017로 접수한 티켓이 있다(2026-10-29 조장 결정).
- SCR-07-AC-2 (FR-초안-01 AC 초안): Given 나라별 탭, When TH를 고르면, Then 고객 33명이 보인다.
- SCR-07-AC-3: Given 나라별 탭, When 표를 보면, Then 나라가 20개다.
- SCR-07-AC-4: Given 없는 고객 CUST-9999, When 상세 주소를 열면, Then "고객을 찾을 수 없습니다"가 보인다.

## 목업과 다른 곳

| 목업 | 명세 | 이유 |
|---|---|---|
| "답장 언어", "담당자 이메일" 열(고객 정보) | 상세 머리에 "최근 답장 언어", "최근 연락처 이메일"(최근 티켓 값) | ref.customer에 언어 열이 없고 이메일은 비어 있음(FR-초안-01 확인할 것, 조장 승인) |
| "미해결 문의 있는 고객만" 체크 | 넣지 않음 | add-customer-views 필터에 없음. 미해결 열로 정렬해 대신 |
| 목록 기본 정렬 = 위험 → 미해결 → 등급 | 최근 문의 시각 내림차순 | add-customer-views 결정 1(구현 선택) |
| 미해결 옆 "기한" 칩 | 상세 머리에만 | 목록 API에 경고 칸 없음 |
| 나라별 지도 그림 | 목업 그림 위에 API 숫자를 얹음 | 지도 그림은 화면 몫 |
