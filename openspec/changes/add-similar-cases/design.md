# Design: 유사 해결사례 검색

## Context

resolution_cases.csv는 800건이며 유형은 DEFECT 468, INSTALL 165, WARRANTY 103, FW_UPDATE 36, RETURN 28이다(근거: resolution_cases.csv category_code 집계). 800건 모두 tickets.csv 한 행과 연결된다(tickets.csv resolution_case_id = case_id)(근거: 두 파일 대조). DB에는 gold.resolution_case_gold로 적재되지만 서비스 계정은 gold에서 v_inputs만 읽는다(근거: schema.sql gold 권한 주석, CLAUDE.md 규칙 6). 고장 진단(Q8a)은 ref 표 + 파일 캐시 벡터로 이미 돈다(근거: 변경 add-fault-diagnosis design 결정 2).

## Goals / Non-Goals

- 목표: 고장 계열 5유형 하위 문의마다 비슷한 해결사례 3건까지를 실행 기록과 상세 화면에 남긴다(근거: FR-019 처리·출력).
- 목표 아님: 답변 초안에 사례를 쓰는 것, 상담원이 직접 검색하는 화면(근거: AC-019-3, proposal 범위 밖).

## Decisions

### 1. 색인 만들기 (`jobs/build_case_index.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 읽는 곳 | DATA_DIR의 resolution_cases.csv(utf-8-sig) | 기술 명세서 v1.4 §1-5 DATA_DIR, 구현 선택 |
| 뺄 사례 | eval.gold_set.source_ticket_id에 있는 ticket_id의 사례 | FR-019 처리 3, D30, §6 "거르는 방법은 eval.gold_set과 원본 ID를 맞대 보는 것 하나로 통일" |
| 남길 열 | case_id, ticket_id, category_code, product_code, product_family, error_code, symptom, root_cause, action_taken, resolution_result, case_summary | FR-019 출력(사례 ID, 원인, 조치, 결과), 구현 선택 |
| 쓰는 곳 | `backend/.cache/resolution_cases.json`(Git 제외, 이미 `.cache/`가 .gitignore에 있음) | 조장 결정 2026-10-23(고장 사전 방식), CLAUDE.md 규칙 8 |
| 벡터 | case_summary를 "document" 임베딩으로, 고장 진단 캐시와 같은 키 방식(sha256(모델 이름 + 줄바꿈 + 글))으로 `resolution_case_vectors.json`에 둔다. 서버가 처음 검색할 때 없는 키만 만든다 | add-fault-diagnosis design 결정 2, §4-7 "문서 청크와 같은 임베딩 모델" |
| 실행 | load_reference·load_gold 뒤 한 번. 팀 정답지가 바뀌면 다시 돌린다 | 기술 명세서 §9 W3·W9 순서, 구현 선택 |

### 2. 검색 (`backend/app/retrieval/cases.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 실행 대상 | category_code ∈ {DEFECT, INSTALL, WARRANTY, FW_UPDATE, RETURN}. 아니면 단계를 남기지 않는다 | FR-019 처리 1, AC-019-2 |
| 질문 글 | query_en(L1 영어 검색문) + " " + error_code. query_en이 없으면 근거 문장 | add-fault-diagnosis C-140과 같은 방식, 구현 선택 |
| 후보 거르기 | 같은 product_family만. 그 안에서 같은 ticket_id(= ticket.source_ticket_id) 사례는 뺀다 | FR-019 처리 2 "제품", proposal "뺄 사례", 구현 선택 |
| 순서 | 같은 error_code(둘 다 있을 때) 먼저, 그다음 코사인 유사도 | FR-019 처리 2 "에러 코드", 구현 선택 |
| 개수 | 상위 3건 | FR-019 처리 2 "3건(제안)" |
| 임베딩 호출 | 언어 모델 호출 계층의 `embed_texts`만. 질문 벡터는 Q8a와 같은 글이면 다시 쓰고, 아니면 1회 | CLAUDE.md 규칙 2, 구현 선택 |
| 결과 없음 | 빈 목록 + notes "비슷한 사례 없음" | FR-019 예외 1행 |
| 실패 | 빈 목록 + notes "사례 검색 실패", Q8b 행 result FAILED. 흐름은 계속 | FR-019 예외 2행, add-fault-diagnosis C-141과 같은 방식 |

### 3. 처리 흐름과 기록

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 노드 자리 | diagnose(Q8a) 바로 뒤 `similar`(Q8b). 정보 요청 여부와 상관없이 돈다 | §4-7 "Q8a 뒤 Q8b", §2 "규칙 단계 바로 뒤" |
| 기록 | agent_step Q8b output_json = {cases: [{case_id, cause, action, result, score, method}], notes} | FR-019 처리 5, §4-7 출력 |
| 초안 입력 | write_reply가 넣는 항목 이름 목록(Q10 input_json.field_names)에 사례가 없다 | AC-019-3, add-fault-diagnosis C-139 |
| 다시 처리 | 다시 처리·고객 회신·상담원 수정 때도 Q8a 뒤에서 다시 찾는다 | §2-4 재실행, 구현 선택 |

### 4. 상세 응답과 화면

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 응답 | `GET /tickets/{id}`의 하위 문의마다 `similar_cases` = 마지막 실행의 Q8b 결과(없으면 null). 응답 모델 SimilarCases | 기술 명세서 §8-1 상세 묶음, 변경 add-api-response-models 결정 1 |
| 위치 | "시스템이 판단한 것" 탭, 고장 진단 후보 구역 아래 "비슷한 해결사례" | FR-019 출력 "가운데 칸", 화면 정의서 v2 SCR-03(가운데 칸 = 시스템이 판단한 것), 구현 선택 |
| 카드 | 사례 ID, 원인(root_cause), 조치(action_taken), 결과(resolution_result), 점수. 보조 글 "참고용, 초안에는 쓰지 않음" | FR-019 출력, add-fault-diagnosis 결정 4와 같은 문구 |

### 5. 시험 (`backend/tests/acceptance/test_similar_cases.py`)

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| AC-019-1 | CSV1-000017(DEFECT)을 불러와 처리하면 사례가 3건 이하이고, 팀 정답지 문의의 사례와 자기 사례 RC-0006이 없다 | AC-019-1, 결정 1·2 |
| AC-019-2 | CSV1-000004(QUOTE)를 처리하면 Q8b 행이 없다 | AC-019-2 |
| AC-019-3 | 사례가 보이는 문의의 답변 초안 인용과 Q10 field_names에 사례가 없다 | AC-019-3 |
| 예외 2개 | 같은 제품군 사례가 없는 입력 → "비슷한 사례 없음", 임베딩 실패 → "사례 검색 실패"·흐름 계속 | FR-019 예외 표 |
| 색인 | 팀 정답지 source_ticket_id의 사례가 색인 파일에 없다 | FR-019 처리 3 |

시험은 대역 임베딩과 임시 캐시 폴더를 쓰고 롤백 안에서 돈다(근거: add-fault-diagnosis 결정 5와 같은 방식).

## Risks / Trade-offs

- 운영진 데이터의 4,000건 중 800건만 사례가 있어, 사례가 연결된 문의를 불러와 시연하면 다른 문의의 사례가 정답처럼 보일 수 있다. 자기 사례를 빼는 것으로만 막는다(근거: 두 파일 대조, 구현 선택).
- 사례 원인·조치는 영어다. 화면에서 번역하지 않는다(근거: resolution_cases.csv 글 언어, FR-019에 번역 처리 없음).
