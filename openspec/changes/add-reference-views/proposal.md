# Proposal: 기준정보 보기 화면 (add-reference-views)

## Why

목업(ONCE v1.41)의 지식 관리 메뉴(문서 관리, 제품 관리, 규칙·부서 보기)는 API가 없다(근거: 갭 목록 문서 2026-10-29, 저장소 밖). 이 화면들은 이미 적재된 ref 표를 읽기만 하므로 새 표 없이 만들 수 있고, 조장이 FR 초안 02·03·04를 승인했다(근거: 목업 기능 FR 초안 문서 "정하실 것 1 → 승인", 2026-10-29, 저장소 밖). 상세의 「왜?」(FR-024)가 가리키는 규칙 행과 인용 절을 전체 표 안에서 찾아볼 수 있게 된다(근거: FR-024 기능 설명).

## What Changes

- **문서 보기 (FR-초안-02)**: `GET /ref/documents`(검색어, 종류)는 문서 ID, 제목, 종류, 제품·제품군, 판(revision), 글자 수, 청크 수를 돌려준다. `GET /ref/documents/{doc_id}`는 절 목록(chunk_id, section_no, section_title)을 돌려주고, 절 본문은 기존 `GET /chunks/{chunk_id}`로 연다(근거: schema.sql ref.document·ref.doc_chunk, 기술 명세서 v1.4 §8-1 chunks 행).
- **제품 보기 (FR-초안-03)**: `GET /ref/products`에 제품군, 단가, 표준 납기, 수명 상태, 보증 개월을 더하고, `GET /ref/products/{product_code}`는 사양값·규격·인증·펌웨어 출시 이력을 돌려준다(근거: schema.sql ref.product·product_spec·product_standard·product_certification·firmware_release).
- **규칙·부서 보기 (FR-초안-04)**: `GET /ref/rules/{kind}`(kind = priority, routing, required-info, sla)는 규칙표 행을 원본 순서대로 돌려준다. 부서 목록은 기존 `GET /ref/departments`를 쓴다(근거: schema.sql ref.priority_rule·routing_rule·required_info_rule·required_info_field·sla_policy·department).
- **고치기 없음**: 모든 주소는 읽기만 한다. 규칙표·문서·제품을 바꾸는 화면은 만들지 않는다(근거: openspec/config.yaml "규칙표·고장 사전의 DB 표와 관리 화면은 이번 범위가 아니다", 목업 기능 FR 초안 라 묶음 "목업 화면으로 둔다").
- **화면**: 지식 관리 메뉴에 문서·제품·규칙 세 화면을 둔다. 문서 표의 행을 누르면 절 목록, 절을 누르면 본문 팝업(기존 인용 팝업과 같음)(근거: 목업 viewDocs·viewKnow, 화면 정의서 v2 SCR-03M-P2).

## Capabilities

### New Capabilities
- `reference-views`: ref 스키마 기준정보(문서, 제품, 규칙표)를 읽기 전용으로 보는 API와 화면.

## 범위 밖

- **부서별 미해결·기한 위험 건수**: 운영 대시보드 `GET /dashboard/summary`가 낸다. 부서 화면이 그 값을 붙이는 것은 add-ops-dashboard가 들어간 뒤 한다(근거: 변경 add-ops-dashboard 결정 2).
- **목업 문서 표의 "언어"·"수정일" 열**: ref.document에 그 열이 없다. 판(revision)으로 대신한다(근거: schema.sql ref.document, CLAUDE.md 규칙 4).

## Impact

- 새 파일: `backend/app/api/reference.py`, 화면 `DocsPage.tsx`·`ProductsPage.tsx`·`RulesPage.tsx`, 시험 `backend/tests/acceptance/test_reference_views.py`(근거: design 결정 1~4).
- 고치는 파일: `app/api/ref_lists.py`(제품 목록 열), `app/main.py`, `app/api/schemas.py`, 화면 `App.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~3).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
