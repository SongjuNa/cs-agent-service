# Proposal: 고객 관리 화면 (add-customer-views)

## Why

목업(ONCE v1.41)의 접수 › 고객 관리(목록·상세·나라별 지도)에는 API가 없다. 지금 있는 `GET /ref/customers`는 선택 목록용이라 ID·회사명·나라·등급만, 최대 20행만 돌려준다(근거: `backend/app/api/ref_lists.py`, 갭 목록 문서 2026-10-29, 저장소 밖). 고객 관리는 ref.customer와 svc의 티켓을 읽기만 하므로 새 표가 필요 없고, 조장이 FR 초안 01을 승인했다(근거: 목업 기능 FR 초안 문서 "정하실 것 1 → 승인", 2026-10-29, 저장소 밖).

## What Changes

- **고객 목록 (FR-초안-01 처리 1)**: `GET /customers`(q, tier, country, page, size)는 고객 ID, 고객사, 나라, 등급, 세그먼트, 문의 수, 미해결 수, 최근 문의 시각을 돌려준다(근거: schema.sql ref.customer·svc.ticket·svc.sub_ticket, 테이블 정의서 v1.3).
- **고객 상세 (처리 2)**: `GET /customers/{customer_id}`는 고객 정보와 문의 이력(ticket_id, 하위 문의 순번, 제품, 유형, 우선순위, 상태, 살아 있는 경고, 접수 시각)을 접수 시각 내림차순으로 돌려준다. 최근 티켓의 연락처(contact_email)와 언어를 "최근 연락처", "최근 문의 언어"로 함께 준다(근거: schema.sql svc.ticket contact_*·language, FR-030 처리 1 연락처 원문 표시, 목업 기능 FR 초안 01 확인할 것).
- **나라별 집계 (처리 3)**: `GET /customers/countries`는 나라별 고객 수, 전체 문의 수, 미해결 문의 수를 돌려준다(근거: 목업 viewCustMap "고객 수·전체 문의·미해결 문의", schema.sql ref.customer.country).
- **화면**: 접수 › 고객 관리에 목록, 상세(행 클릭), 나라별 표(지도 대신 표로 시작). 문의 이력 행을 누르면 티켓 상세로 간다(근거: 목업 viewCustomers·viewCustomer·viewCustMap, FR-030).
- **읽기만**: 고객 정보를 고치는 주소는 없다(근거: openspec/config.yaml 기준정보 관리 화면은 범위 밖, CLAUDE.md 규칙 4).

## Capabilities

### New Capabilities
- `customer-views`: 고객 목록·상세·나라별 집계의 읽기 전용 API와 화면.

## 범위 밖

- **목업의 지도 그림**: 나라별 값은 표로 먼저 보이고, 지도 그림은 화면 작업 때 정한다(근거: 구현 선택. 지도 라이브러리는 기술 명세서 v1.4 §1 스택에 없음).
- **ref.customer의 대표 연락처 열**: customers.csv에 값이 없어 비어 있으므로 쓰지 않는다(근거: schema.sql ref.customer 주석 "customers.csv에는 값이 없어 비어 있다").

## Impact

- 새 파일: `backend/app/db/customers.py`, `backend/app/api/customers.py`, 화면 `CustomersPage.tsx`·`CustomerPage.tsx`, 시험 `backend/tests/acceptance/test_customer_views.py`(근거: design 결정 1~3).
- 고치는 파일: `app/main.py`, `app/api/schemas.py`, 화면 `App.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~3).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
