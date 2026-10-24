# Design: 고장 진단

## Context

고장 사전은 ref.fault(fault_catalog.csv 97행: fault_id, family, error_code, symptom, root_cause, diagnosis, action, needs_onsite, needs_rma …)와 ref.fault_product(고장 × 제품 156행)에 이미 적재되어 있다(근거: schema.sql ref.fault·ref.fault_product, 테이블 정의서 v1.3). 같은 제품군·같은 에러 코드 행이 둘 이상인 묶음이 14개 있다(예: DRIVE E.OC 4행)(근거: fault_catalog.csv family·error_code 집계). tickets.csv의 에러 코드는 DEFECT 550건 중 234건에만 있고 INSTALL·WARRANTY에는 없다(근거: tickets.csv category_code·error_code_reported 집계). 기술 명세서 §4-6은 증상 벡터를 `ref.fault.symptom_embedding`(제안 열)에 두자고 했으나 테이블 정의서에 없고, 조장은 새 열 없이 파일 캐시와 메모리에 두기로 했다(근거: §4-6 2번, schema.sql, 조장 결정 2026-10-23).

## Decisions

### 1. 진단 (`backend/app/retrieval/fault.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 실행 대상 | category_code ∈ {DEFECT, INSTALL, WARRANTY}. 아니면 아무것도 하지 않고 단계도 남기지 않는다 | FR-018 처리 1, §2-5 분기⑦, AC-018-3 |
| 제품군 | 하위 문의의 product_family(Q2가 채움). ref.fault.family로 거른다. 제품군을 모르거나 그 제품군 행이 없으면 진단 없음 "고장 사전에 해당 제품군 없음" | FR-018 처리 3, 예외 1행, 구현 선택 C-135 |
| 정확 조회 | error_code가 있으면 같은 family·같은 error_code 행. 찾으면 EXACT, 점수 1.0. 같은 행이 여럿이면 ref.fault_product에 그 제품이 있는 행으로 좁히고, 그래도 여럿이면 모두 EXACT로 두고 증상 유사도 순(계산 못 하면 fault_id 순) | FR-018 처리 2, §4-6 1번(정확 조회). 좁히기는 구현 선택 C-133 |
| 증상 검색 | 정확 조회가 없거나 에러 코드가 없으면 같은 family 행 중 코사인 유사도 상위 3건, SYMPTOM. 에러 코드가 있는데 정확 조회가 없으면 "에러 코드 미등록" 표시 | FR-018 처리 3, 예외 2행, §4-6 2번, T39 제안 |
| 질문 글 | query_en(L1 영어 검색문) + " " + error_code. query_en이 없으면 근거 문장 | §4-6 2번, 구현 선택 C-140 |
| 관련성 낮음 | 점수가 모두 0.5 미만이면 후보는 보이고 "관련성 낮음" | FR-018 예외 3행, T39 미정이라 구현 선택 C-134 |
| 실패 | 임베딩이 두 번 실패하는 등 오류면 진단 없음 "진단 실패". 오류를 올리지 않아 흐름은 계속. 실행 기록 Q8a 행은 result FAILED, error_kind UNKNOWN으로 남긴다 | FR-018 예외 4행 "실행 로그에 기록, 흐름은 계속", §2 Q8a 행, 구현 선택 C-141 |
| 표시 문구 | 위 문구는 Q8a 단계 결과의 notes에만 둔다. 하위 문의 flags·self_check에는 넣지 않는다(검토 표시와 무관) | §4-6 4번 "문서 근거가 아님", 구현 선택 C-138 |

- 후보 모양(상태 객체 FaultCandidate): fault_id, cause(root_cause), check(diagnosis), action, onsite_required(needs_onsite), replace_required(needs_rma), method, score(근거: §4-6 3번, 화면 정의서 v1 C-08 "원인·점검·조치", state.py FaultCandidate).
- 임베딩은 언어 모델 호출 계층의 `embed_texts`로만 부른다. 이 모듈은 규칙 코드가 아니다(근거: CLAUDE.md 규칙 1·2, `app/retrieval/search.py`와 같은 방식).

### 2. 증상 벡터 캐시

- 파일 하나(`backend/.cache/fault_symptoms.json`): 키 = sha256(임베딩 모델 이름 + 줄바꿈 + 증상 문장), 값 = 벡터(근거: 조장 결정 2026-10-23, 구현 선택 C-132).
- 서버가 켜질 때 언어 모델을 부르지 않고 캐시 파일만 읽어 메모리에 올린다. 진단할 때 없는 키(처음 실행, 새 행, 바뀐 문장, 바뀐 모델)만 "document" 임베딩으로 만들어 파일에 다시 쓴다. 그 뒤는 메모리에서 계산한다(근거: 조장 결정 2026-10-23 "서버가 켜지면 캐시 파일을 읽어 메모리에 올림", 구현 선택 C-132). 기술 명세서 §4-6·에이전트 설계서는 색인 작업(W1)에서 만든다고 했다. 첫 진단에서 만드는 것은 그와 다르다(C-132).
- 캐시 파일을 못 읽거나 못 쓰면 메모리만 쓴다(근거: 구현 선택).
- `.gitignore`에 `.cache/`를 더하고, docker-compose의 api에 캐시 볼륨을 붙인다(근거: CLAUDE.md 규칙 8, 구현 선택).

### 3. 처리 흐름 (`graph.py`, `pipeline/diagnose.py`, `runlog.py`, `store.py`)

- 노드 `diagnose`를 rules 뒤, info_request 앞에 둔다. 모든 하위 문의(막는 정보가 있어도)에 대해 돈다(근거: §2-1 흐름, §2 "정보 요청 여부와 상관없이 규칙 단계 바로 뒤").
- 실행 기록: 노드 시간은 단계 Q8a(NODE_STEPS). 저장할 때 Q6 뒤에 단계 Q8a 행 하나 — output_json = {fault_candidates, method, notes}(근거: §4-6 4번 "step 1개", FR-036 처리 2).
- 진단이 실패해도 하위 문의 pipeline_error로 두지 않는다(근거: FR-018 예외 4행 "흐름은 계속").
- L4 입력 항목 이름: write_reply가 넣은 항목 이름 목록을 초안에 담고, 저장할 때 Q10 input_json = {field_names: […]}(근거: 에이전트 설계서 v1.1 "넣지 않는 것: 고장 진단 후보 … 실행 기록의 넣은 항목 이름 목록으로 확인", 구현 선택 C-139).
- 다시 처리·고객 회신 재처리·상담원 수정도 rules 뒤에서 진단을 다시 한다(근거: §2-4 재실행, 구현 선택).

### 4. 상세 응답과 화면 (`detail.py`, `DetailTabs.tsx`)

- `GET /tickets/{id}`의 하위 문의마다 `diagnosis` = 마지막 실행의 Q8a 결과(없으면 null)(근거: 기술 명세서 §8-1 "하위 문의별 결과(진단 후보·이관 후보 포함)").
- 근거 줄 "고장 진단": 값 = 1순위 fault_id와 찾은 방법, 없으면 "없음({사유})". "왜?"는 Q8a 단계와 고장 사전 행을 보여 준다. 고장 계열이 아닌 문의는 줄을 두지 않는다(근거: FR-024 입력, AC-024-1, 화면 정의서 v1 P1 "진단 → fault_catalog.csv 행과 찾은 방법·점수").
- 구역 "고장 진단 후보"(고장 계열만): 1순위 카드(원인·점검·조치·현장 출동·교체 필요·찾은 방법·점수), 2·3순위는 접힘, 보조 글 "참고용, 초안에는 쓰지 않음", notes 표시. 기존 레이아웃은 그대로, 안내 문구 자리만 바꾼다(근거: 화면 정의서 v1 SCR-03 C-08, 조장 결정 2026-10-23).

### 5. 시험 (`tests/acceptance/test_fault_diagnosis.py`)

- AC-018-1·2: 진단 함수를 CSV1-000007·CSV1-000055의 실제 제품·에러 코드로 부른다(대역 임베딩)(근거: tickets.csv, AC-018-1·2).
- AC-018-3·4: 처리 흐름(대역 언어 모델)으로 CSV1-000004 접수 → Q8a 행 없음 / 고장 문의 접수 → Q10 input_json의 항목 이름과 L4 지시문에 진단 후보가 없음(근거: AC-018-3·4).
- AC-018-5: tickets.csv의 고장 문의 중 에러 코드가 있어 결정적으로 진단되는 행(DEFECT 234건. INSTALL·WARRANTY에는 에러 코드가 없음)에서 ① 1순위의 교체 필요 또는 현장 출동 표시 ↔ 정답 escalated(이관 여부), ② 교체 필요 ↔ escalation_reason RMA_REQUIRED, 현장 출동 ↔ ONSITE_REQUIRED 일치율을 출력한다. P1·SAFETY 이관은 ①에서 "이관됨", ②에서 두 사유가 아닌 것으로 센다. 증상 검색 행은 대역 임베딩이라 넣지 않는다. 정답 열을 읽는 시험 코드다(근거: AC-018-5 "이관 여부", §4-6 5번 "escalated·escalation_reason", CLAUDE.md 규칙 6 예외, 구현 선택 C-137).
- AC-024-1: 기존 시험(CSV1-000017)에 근거 줄 "고장 진단"이 있는지를 더한다(근거: AC-024-1).
- 예외 "제품군 항목 없음"·"에러 코드 미등록"은 운영진 데이터에 해당 문의가 없어(고장 계열 제품군은 모두 고장 사전에 있고, 에러 코드 234건은 모두 등록됨) 만든 입력으로 시험한다(근거: tickets.csv 집계, 구현 선택).
- 예외 4개, 캐시(두 번째 진단은 임베딩을 다시 부르지 않음, 문장이 바뀐 행만 다시), 상세 응답(근거: FR-018 예외 표, 조장 결정 2026-10-23).
- 시험은 롤백 안에서 돌고 캐시 파일은 임시 폴더를 쓴다(근거: 1·2순위 합의 "svc DB에 시험 데이터 넣지 않음").

## Risks / Trade-offs

- 증상 검색 질문 벡터를 Q8의 것과 따로 만든다(§4-6 2번의 질문 글이 Q8과 다름). 고장 계열 하위 문의마다 임베딩 호출이 1회 늘어나, 에이전트 설계서 v1.1의 비용 추정("검색할 때 하위 문의마다 1회")과 어긋난다(구현 선택 C-136).
- 0.5 기준과 상위 3건은 임시값이다. 팀 정답지 측정 뒤 정한다(근거: T39 제안, C-134).
