# Design: 고객 관리 화면

## Context

ref.customer는 600행(customer_id, company_masked, country, tier, segment, account_since, contact_count)이고 나라는 20개다(근거: customers.csv, 테이블 정의서 v1.3 ref.customer). 티켓은 svc.ticket(customer_id, contact_*, language, received_at_utc)과 svc.sub_ticket(상태, 우선순위, 유형)에 있다(근거: schema.sql svc.ticket·sub_ticket). 팀 정답지 문의는 svc에 넣지 않으므로 고객 이력에도 나오지 않는다(근거: D30, 기술 명세서 §6).

## Goals / Non-Goals

- 목표: 상담원이 고객사별 문의 이력과 나라별 분포를 본다(근거: 목업 기능 FR 초안 01).
- 목표 아님: 고객 정보 고치기, 지도 그림(근거: proposal 범위 밖).

## Decisions

### 1. 목록 (`GET /customers`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 열 | customer_id, company_masked, country, tier, segment, ticket_count, open_count, last_received_at | 테이블 정의서 v1.3 ref.customer·svc.ticket |
| 미해결 | 하위 문의 상태가 NEW·IN_PROGRESS·WAITING_CUSTOMER·ESCALATED인 티켓 수 | FR-034 처리 2와 같은 정의 |
| 필터·쪽 | q(ID·회사명 부분 일치), tier, country, page, size(기본 50) | FR-029 처리 7의 쪽 크기와 같게, 구현 선택 |
| 정렬 | 최근 문의 시각 내림차순, 문의 없는 고객은 뒤 | 구현 선택 |
| 등급 요약 | tier_counts = 검색·나라 거르기 뒤, 등급 거르기 전의 등급별 고객 수 | 화면 명세 SCR-07 N-07-01, 구현 선택 |

### 2. 상세 (`GET /customers/{customer_id}`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 고객 | ref.customer 한 행 | 테이블 정의서 v1.3 ref.customer |
| 최근 연락처·언어 | 가장 최근 티켓의 contact_email, language | FR-030 처리 1, 목업 기능 FR 초안 01 |
| 문의 이력 | 하위 문의 1행씩: ticket_id, seq, source_ticket_id(원본 번호), product_code, category_code, priority, status, 살아 있는 경고 종류, received_at_utc. 접수 시각 내림차순 | 테이블 정의서 v1.3 svc.sub_ticket·svc.ticket·sla_alert, FR-029 처리 1과 같은 단위. 원본 번호는 2026-10-29 조장 결정(검토 자료 ①) |
| 기준 시각 | as_of(기본 지금). 경고는 그 시각에 살아 있는 것 | 나의 업무 현황과 같음, 구현 선택 |
| 없는 고객 | 404 "고객을 찾을 수 없음" | 구현 선택 |

### 3. 나라별 (`GET /customers/countries`)와 화면

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 열 | country, customer_count, ticket_count, open_count | 목업 viewCustMap(저장소 밖), 구현 선택 |
| 화면 | 고객 관리 목록·상세·나라별 표. 이력 행 클릭 → 티켓 상세 | FR-030, 구현 선택 |
| 응답 모델 | CustomerRows, CustomerDetail, CountryRow | 구현 선택, 변경 add-api-response-models 결정 1 |
| 이 모듈 | 표만 읽는다. 규칙 코드·언어 모델 호출 계층을 import하지 않는다 | CLAUDE.md 규칙 1·2 |

### 4. 시험 (`backend/tests/acceptance/test_customer_views.py`)

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| 상세 이력 | CSV1-000017을 접수한 뒤 CUST-0350 상세에 그 티켓(원본 번호 CSV1-000017)이 있고, 이력이 접수 시각 내림차순이다 | 목업 기능 FR 초안 01 AC 초안, tickets.csv |
| 나라별 고객 수 | TH의 customer_count = 33(ref.customer의 TH 행 수) | 목업 기능 FR 초안 01 AC 초안, customers.csv |
| 없는 고객 | 404 | 구현 선택(결정 2) |
| 미해결 수 | 상태를 RESOLVED로 바꾸면 open_count가 1 줄어든다 | 구현 선택(결정 1) |

## Risks / Trade-offs

- 고객 600행 × 티켓 집계를 한 번에 하므로 쪽 단위(size)로 자른다(근거: 구현 선택).
