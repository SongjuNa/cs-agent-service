# Design: 해결사례 직접 검색

## Context

add-similar-cases가 resolution_cases.csv에서 팀 정답지 사례를 뺀 색인을 파일 캐시와 메모리에 둔다(근거: 변경 add-similar-cases 결정 1·2). 800건 중 에러 코드가 있는 사례는 422건이고 가장 많은 코드는 E.OC 42건이다(근거: resolution_cases.csv error_code 집계).

## Goals / Non-Goals

- 목표: 상담원이 증상·에러 코드·제품으로 해결사례를 찾아 읽는다(근거: 목업 기능 FR 초안 06).
- 목표 아님: 초안에 사례 쓰기, 검색 기록(근거: proposal).

## Decisions

### 1. 검색 (`GET /cases`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | q, error_code, product_code, category_code (하나 이상) | FR-019 처리 2, 구현 선택 |
| 거르기 | product_code·category_code는 같은 값만. error_code는 거르지 않고 순서에 쓴다 | 구현 선택 |
| 순서 | 같은 error_code 먼저, 그다음 q가 있으면 q의 "query" 임베딩과 사례 벡터의 코사인 유사도, q가 없으면 case_id 순 | FR-019 처리 2, 변경 add-similar-cases 결정 2와 같은 방식 |
| 개수 | 20건 | 구현 선택 |
| 임베딩 | 언어 모델 호출 계층의 `embed_texts`만. 상담원 검색어도 보내기 직전 가리기를 거친다 | CLAUDE.md 규칙 2 |
| 입력 없음 | 400 "검색어를 입력하세요" | 구현 선택 |
| 실패 | 임베딩이 실패하면 에러 코드·제품 거르기만으로 결과를 내고 "뜻 검색 실패" 표시 | FR-019 예외 2행과 같은 원칙, 구현 선택 |

### 2. 상세 (`GET /cases/{case_id}`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 열 | case_id, ticket_id, category_code, product_code, error_code, symptom, initial_hypothesis, root_cause, diagnosis_method, action_taken, replacement_part, onsite_visit, resolution_result, time_to_resolve_hours, recurrence_prevention, case_summary | resolution_cases.csv 열 |
| 색인 | build_case_index가 위 열을 모두 남기도록 늘린다 | 구현 선택, 변경 add-similar-cases 결정 1 |
| 없는 사례 | 404 "사례를 찾을 수 없음". 팀 정답지 사례도 404 | FR-019 처리 3, 구현 선택 |

### 3. 화면과 시험

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 화면 | 접수 › 접수 이력: 검색 칸 4개, 결과 표(사례 ID, 제품, 에러 코드, 증상, 결과), 상세 패널. 보조 글 "참고용, 초안에는 쓰지 않음" | 구현 선택, 목업 viewSimilar(저장소 밖), 변경 add-similar-cases 결정 4 |
| 응답 모델 | CaseRows, CaseDetail | 구현 선택, 변경 add-api-response-models 결정 1 |
| 시험: 에러 코드 | error_code = E.OC로 찾으면 앞 결과가 모두 E.OC이고 팀 정답지 사례가 없다 | 목업 기능 FR 초안 06 AC 초안, resolution_cases.csv |
| 시험: 입력 없음 | 400 | 구현 선택(결정 1) |
| 시험: 정답지 사례 | 팀 정답지 문의의 사례 상세는 404 | FR-019 처리 3 |
| 시험: 가리기 | q에 이메일을 넣으면 임베딩 대역에 가린 글이 간다 | CLAUDE.md 규칙 2 |

## Risks / Trade-offs

- 사례 글은 영어라 한국어 검색어는 뜻 검색 품질이 낮을 수 있다. 임베딩 모델이 다국어를 받으므로 그대로 두고, 낮으면 보고한다(근거: 기술 명세서 v1.4 임베딩 모델 gemini-embedding-2, 구현 선택).
