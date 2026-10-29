# Design: 기준정보 보기 화면

## Context

ref 스키마에는 문서 107행과 절 청크, 제품 23행과 사양·규격·인증·펌웨어, 규칙표 4종이 적재되어 있다(근거: schema.sql ref.*, 기술 명세서 v1.4 §5-1). 지금 API는 선택 목록용 `GET /ref/*`(코드·이름만)과 절 본문 `GET /chunks/{id}`뿐이다(근거: `backend/app/api/ref_lists.py`, `chunks.py`).

## Goals / Non-Goals

- 목표: 상담원이 근거 문서, 제품 기준값, 규칙표를 화면에서 찾아본다(근거: 목업 기능 FR 초안 02·03·04).
- 목표 아님: 기준정보 고치기, 색인 다시 만들기(근거: proposal 범위 밖).

## Decisions

### 1. 문서 (`GET /ref/documents`, `/ref/documents/{doc_id}`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 목록 열 | doc_id, title, doc_type, product_code, family, revision, chars, chunk_count(ref.doc_chunk 행 수) | 테이블 정의서 v1.3, schema.sql ref.document·doc_chunk |
| 필터 | q(문서 ID·제목 부분 일치), doc_type | 목업 viewDocs "문서 ID·범위", "종류", 구현 선택 |
| 색인 표시 | chunk_count = 0이면 화면에 "색인 없음" | 목업 viewDocs "색인" 열, 구현 선택 |
| 상세 | 절 목록(chunk_id, section_no, section_title) section_no 순. 본문은 `GET /chunks/{id}` | 기술 명세서 §8-1 chunks 행 |
| 없는 문서 | 404 "문서를 찾을 수 없음" | 구현 선택 |

### 2. 제품 (`GET /ref/products`, `/ref/products/{product_code}`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 목록 열 | 지금 열(product_code, product_name) + family, list_price_usd, std_lead_time_weeks, lifecycle_status, warranty_months | 테이블 정의서 v1.3, schema.sql ref.product. 시뮬레이터 선택 목록은 앞 두 열만 쓰므로 그대로 동작(구현 선택) |
| 상세 | 사양값(attribute, value, doc_id, section), 규격, 인증, 펌웨어(fw_version, release_date, is_latest, changes) | 테이블 정의서 v1.3, schema.sql ref.product_spec·product_standard·product_certification·firmware_release |
| 정렬 | 사양 attribute 순, 펌웨어 release_date 내림차순 | 구현 선택 |

### 3. 규칙 (`GET /ref/rules/{kind}`)

| kind | 돌려주는 행 | 근거 |
|---|---|---|
| priority | rule_id, rule_order, condition, priority, 긴급도 목록, 유형 목록. rule_order 순 | 테이블 정의서 v1.3, schema.sql ref.priority_rule·_urgency·_category |
| routing | rule_id, family, category, rule_source, primary_dept, escalation_dept, escalation_condition | 테이블 정의서 v1.3, schema.sql ref.routing_rule |
| required-info | family, category, 항목 목록(field, field_order, is_blocking) | 테이블 정의서 v1.3, schema.sql ref.required_info_rule·_field |
| sla | sla_id, category, customer_tier, priority, first_response_hours, resolution_hours | 테이블 정의서 v1.3, schema.sql ref.sla_policy |
| 그 밖 | 404 | 구현 선택 |

- 이 모듈은 규칙 코드를 부르지 않고 표만 읽는다. 언어 모델 호출 계층도 import하지 않는다(근거: CLAUDE.md 규칙 1·2).

### 4. 화면과 시험

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 메뉴 | 지식 관리 › 문서 관리, 제품 관리, 규칙 보기 | 목업 ONCE v1.41 메뉴(저장소 밖), 구현 선택 |
| 「왜?」 연결 | 상세의 「왜?」 팝업에 "규칙표에서 보기" 링크(규칙 보기 화면, 그 rule_id 강조) | FR-024 기능 설명, 구현 선택 |
| 응답 모델 | DocumentRow, DocumentDetail, ProductRow, ProductDetail, RuleRows | 구현 선택, 변경 add-api-response-models 결정 1 |
| 시험 | 목록 107행, chunk_count = 0 문서 표시, CSV1-000004 제품의 단가 520·납기 4주, priority 규칙에 PR-02 행, 없는 kind 404 | 목업 기능 FR 초안 AC 초안, AC-030-2·AC-030-4 |

## Risks / Trade-offs

- `GET /ref/products`에 열이 늘어 응답이 커진다(23행이라 작다)(근거: schema.sql ref.product 주석, 구현 선택).
