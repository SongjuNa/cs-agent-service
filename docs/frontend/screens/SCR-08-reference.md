# 화면 명세: SCR-08 기준정보 보기 (문서·제품·규칙·부서) (임시 번호)

- 연결 요구사항: FR-초안-02(문서 관리, 보기 전용), FR-초안-03(제품 관리, 보기 전용), FR-초안-04(규칙·부서 보기), FR-024([근거 보기], 예전 "왜?"가 가리키는 행), 2026-10-23 조장 결정(규칙표 관리 화면은 범위 밖)
- 기준 목업: cs-agent-mockup_v1.42.html `viewDocs`, `viewKnow`, `KTABS` (레이아웃 기준선: 지식 관리 메뉴 4개 → 탭 → 요약 → 필터 → 표)
- 화면 정의서: 없음
- 사용 API (아직 없음, 변경 add-reference-views): `GET /ref/documents`, `/ref/documents/{doc_id}`, `GET /ref/products`, `/ref/products/{product_code}`, `GET /ref/rules/{kind}` (kind = priority, routing, required-info, sla), `GET /chunks/{chunk_id}`(있음), `GET /ref/departments`(있음)

## 영역

| 요소 ID | 메뉴 › 탭 | 표시 | API 칸 |
|---|---|---|---|
| N-08-01 | 문서 관리 | 종류 요약 버튼, 필터(문서 ID·범위, 종류), 표: 문서 ID, 제목, 종류, 제품·제품군, 개정, 글자 수, 절 수. 절이 0이면 "색인 없음" 칩과 위 띠 "색인 안 됨 n건" | doc_id, title, doc_type, product_code, family, revision, chars, chunk_count |
| N-08-02 | 문서 관리 › 행 펼침 | 절 목록(절 번호, 절 제목). 절을 누르면 P2와 같은 창에 본문 | `/ref/documents/{id}` sections, `GET /chunks/{id}` |
| N-08-03 | 제품 관리 › 제품 목록 | 제품 코드, 이름, 제품군, 단가(USD), 표준 납기(주), 수명 상태, 보증(개월) | product_code, product_name, family, list_price_usd, std_lead_time_weeks, lifecycle_status, warranty_months |
| N-08-04 | 제품 관리 › 상세 | 사양 항목, 규격, 인증, 펌웨어 출시 이력 | `/ref/products/{code}` |
| N-08-05 | 규칙 관리 › 우선순위 규칙 | 순서, 규칙 ID, 조건(원문), 우선순위, 긴급도 목록, 유형 목록 | rules/priority |
| N-08-06 | 규칙 관리 › 부서 배정 규칙 | 규칙 ID, 제품군, 유형, 출처, 1차 부서, 이관 부서, 이관 조건 | rules/routing |
| N-08-07 | 규칙 관리 › 필수 정보 | 제품군, 유형, 항목(순서, 막는 항목 여부) | rules/required-info |
| N-08-08 | 기타 관리 › 처리 기한 | SLA ID, 유형, 등급, 우선순위, 1차 응답 h, 해결 h | rules/sla |
| N-08-09 | 부서 관리 | 부서 코드, 이름 (+ 운영 대시보드의 부서별 미해결 수) | `GET /ref/departments`, `/dashboard/summary` |

## 화면 상태

- 로딩: 표 스켈레톤.
- 데이터 없음: "조건에 맞는 문서가 없습니다" 등 표별 문구.
- 탭에 API가 없음(아래 "목업과 다른 곳"): 탭은 보이되 "이 표는 아직 보기 화면이 없습니다".
- 오류: 이전 값을 두고 "불러오지 못함. 새로고침".
- 모든 표는 읽기 전용. 고치기·올리기 버튼은 두지 않는다.

## 사용자 동작 → 시스템 반응

| 동작 | 호출 API | 성공 시 | 실패 시 |
|---|---|---|---|
| 문서 관리 열기 / 필터 | `GET /ref/documents` (거르기는 화면에서, 107행) | 표 그림 | 오류 띠 |
| 문서 행 누르기 | `GET /ref/documents/{doc_id}` | 절 목록 펼침 | 404 "문서를 찾을 수 없음" |
| 절 누르기 | `GET /chunks/{chunk_id}` | 절 본문 창 | "본문 열기 실패" |
| 제품 목록 / 행 누르기 | `GET /ref/products` / `/ref/products/{code}` | 표 / 상세 | 같음 |
| 규칙 탭 누르기 | `GET /ref/rules/{kind}` | 표 그림 | 404면 탭 비활성 |
| (티켓 상세 P1에서) "규칙표에서 보기" | — | 해당 탭을 열고 그 규칙 ID 행을 강조 | — |
| [CSV 내려받기] | — | 지금 보이는 표를 CSV 파일로(화면에서 만듦) | — |

## 입력 검증

- 검색어: 앞뒤 공백 제거. 화면 안 거르기라 서버 호출 없음.

## 수용 기준 (Given / When / Then)

- SCR-08-AC-1 (FR-초안-02 AC 초안): Given 문서 관리, When 화면을 열면, Then 표가 107행이고 절이 0인 문서에 "색인 없음"이 보인다.
- SCR-08-AC-2 (FR-초안-03 AC 초안, AC-030-4): Given 제품 목록, When CSV1-000004의 제품 HMI-XGT-eXP60 행을 보면, Then 단가 520과 표준 납기 4주가 보인다.
- SCR-08-AC-3 (FR-초안-04 AC 초안, AC-030-2): Given 우선순위 규칙 탭, When PR-02 행을 보면, Then 조건이 "urgency=SITE_DOWN 이고 Category ∈ {DEFECT, INSTALL, FW_UPDATE}"이고 우선순위가 P1이다.
- SCR-08-AC-4: Given 어느 표, When 화면을 보면, Then 고치기·올리기·색인 다시 만들기 버튼이 없다.

## 목업과 다른 곳

| 목업 | 명세 | 이유 |
|---|---|---|
| [색인 다시 만들기], [표 올리기] | 두지 않음 | 보기 전용(FR-초안-02·04 범위 밖, 2026-10-23 결정) |
| 문서 "초안 인용" 횟수, 언어 열 | 넣지 않음 | add-reference-views 목록 열에 없음 |
| 규칙 관리의 긴급도·정보 항목 탭, 제품 관리의 사양·고장 사전 탭, 기타 관리의 문의 유형·이관 사유·언어·채널 탭 | 탭은 두고 "아직 보기 화면이 없습니다" | add-reference-views는 문서·제품·규칙 4종만. 더할지는 다음 변경에서 |
| 부서 관리의 "배정 현황" | 부서 목록 + 부서별 미해결 수 | FR-초안-04 처리 |
